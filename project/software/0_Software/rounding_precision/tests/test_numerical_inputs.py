import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from prepare_numerical_inputs import canonical_url,freeze_documents,wikitext_articles
from capture_numerical_inputs import linear_arrays
from numerical_document_stream import documents,tokenize_document,prepare_worker
from formal_numerical_inputs import build_plan,load_batch,load_batch_group,read_token_artifact
from formal_storage_plan import create_storage_policy,load_storage_policy
from run_numerical_fidelity import identity
import hashlib


def row(name,text,domain='web',split='test',url=None):
    return dict(doc_id=name,text=text,domain=domain,source_split=split,canonical_url=url)


class DocumentTests(unittest.TestCase):
    def test_global_text_and_url_clusters_excluded_as_a_unit(self):
        records=[row('a','old smoke text',url='https://x/a'),row('b','changed text',url='https://x/a'),
                 row('c',' old   smoke text '),row('d','clean1'),row('e','clean2'),
                 row('t1','train one','wiki','train'),row('t2','train two','wiki','train')]
        selected,inventory=freeze_documents(records,{'web':1},1,1,7,['smoke text'])
        self.assertEqual(inventory['excluded_smoke_clusters'],1)
        self.assertFalse({'a','b','c'} & {r['doc_id'] for r in selected})
        self.assertEqual(len({r['duplicate_cluster'] for r in selected}),3)

    def test_repeatable_role_disjoint_and_probabilities(self):
        records=[row(str(i),f'unique {i}') for i in range(6)]+[row('t'+str(i),f'training {i}','wiki','train') for i in range(6)]
        first,_=freeze_documents(copy.deepcopy(records),{'web':2},1,2,123,[])
        second,_=freeze_documents(copy.deepcopy(records),{'web':2},1,2,123,[])
        self.assertEqual(first,second)
        self.assertEqual(len({r['doc_id'] for r in first}),5)
        for r in first:
            expected={'eval':2/6,'train':1/6,'dev':2/6}[r['split']]
            self.assertEqual(r['selection_probability'],expected)

    def test_insufficient_pool_fails_not_replacement(self):
        with self.assertRaises(ValueError):
            freeze_documents([row('a','one')],{'web':2},0,0,1,[])

    def test_url_retains_content_query(self):
        self.assertEqual(canonical_url('HTTPS://EXAMPLE.COM/a/?id=3&utm_source=x#section'),'https://example.com/a?id=3')
        self.assertNotEqual(canonical_url('https://example.com/a?id=3'),canonical_url('https://example.com/a?id=4'))

    def test_article_boundaries_not_subsections(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rows.jsonl'
            p.write_text(''.join(json.dumps({'text':x})+'\n' for x in [' = A = ','body',' == Section == ','body2',' = B = ','next']))
            docs=list(wikitext_articles(p))
            self.assertEqual(len(docs),2)
            self.assertIn('Section',docs[0]['text'])
            self.assertEqual(docs[1]['source_index'],4)

    def test_linear_pack_keeps_full_group_order_and_lanes(self):
        qa=np.arange(2*3*32).reshape(2,3,32)%256
        qw=np.arange(4*3*32).reshape(4,3,32)%15-8
        zp=np.full((2,3),128)
        arrays,shape=linear_arrays(dict(q_a=qa,q_w=qw,zero_point=zp,act_code=np.ones((2,3),int),
                                      act_shift=np.ones((2,3),int)*12,weight_code=np.ones((4,3),int),weight_shift=np.ones((4,3),int)*20))
        self.assertEqual(shape,[2,4])
        self.assertEqual(arrays['dot'].shape,(8,3))
        for r in range(2):
            for c in range(4):
                for g in range(3):
                    self.assertEqual(arrays['dot'][r*4+c,g],sum((int(qa[r,g,k])-128)*int(qw[c,g,k]) for k in range(32)))


class DocumentStreamTests(unittest.TestCase):
    def test_short_document_not_padded_or_joined(self):
        class Tokenizer:
            def __call__(self,text,**kwargs):return {'input_ids':[1,2,3],'attention_mask':[1,1,1]}
        arrays=tokenize_document(Tokenizer(),'text',128)
        self.assertEqual(len(arrays['input_ids']),3)
        self.assertEqual(arrays['position_ids'].tolist(),[0,1,2])
        with self.assertRaises(ValueError):tokenize_document(Tokenizer(),'text',129)

    def test_payload_does_not_collide_with_supervisor_manifest(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        text='abc';sha=hashlib.sha256(text.encode()).hexdigest()
        row=dict(text=text,text_sha256=sha,normalized_text_sha256=sha,split='eval',evidence_role='formal_eval',
                 doc_id='doc',source_id='0',source_asset='test',domain='web',duplicate_cluster='cluster')
        class Tokenizer:
            def __call__(self,*args,**kwargs):return {'input_ids':[1,2,3],'attention_mask':[1,1,1]}
        fake=SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *args,**kw:Tokenizer()))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.jsonl';source.write_text(json.dumps(row)+'\n')
            output=root/'output';output.mkdir();(output/'document_stream_manifest.json').write_text('supervisor identity')
            args=SimpleNamespace(documents=source,split='eval',maximum_documents=1,model_dir=root,
                                 output_dir=output,max_tokens=128,audit_seed=1,audit_modulus=64)
            with patch.dict(sys.modules,{'transformers':fake}):self.assertEqual(prepare_worker(args),0)
            self.assertEqual((output/'document_stream_manifest.json').read_text(),'supervisor identity')
            self.assertTrue((output/'frozen_document_stream.json').exists())

    def test_duplicate_cluster_and_role_mutation_rejected(self):
        row=dict(text='abc',text_sha256=hashlib.sha256(b'abc').hexdigest(),split='eval',evidence_role='formal_eval',doc_id='a',duplicate_cluster='same')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'docs.jsonl'
            path.write_text(json.dumps(row)+'\n'+json.dumps({**row,'doc_id':'b'})+'\n')
            with self.assertRaises(ValueError):list(documents(path,'eval'))
            path.write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError):list(documents(path,'dev'))


class FormalInputTests(unittest.TestCase):
    counts={'web':4,'news':2,'reviews':2}
    def fixture(self,root,audits=(0,4),counts=None):
        docs=[]
        counts=self.counts if counts is None else counts
        for i,domain in enumerate([domain for domain,count in counts.items() for _ in range(count)]):
            artifact=root/f'doc{i}.npz'
            np.savez(artifact,input_ids=np.array([128000,i+1,2],np.int64),attention_mask=np.ones(3,np.int64),position_ids=np.arange(3,dtype=np.int64))
            docs.append(dict(doc_id='d'+str(i),duplicate_cluster='c'+str(i),domain=domain,split='eval',evidence_role='formal_eval',
                             tokens=3,token_artifact=identity(artifact),raw_tensor_audit_selected=i in audits))
        path=root/'stream.json';path.write_text(json.dumps(dict(schema='m005_numerical_document_stream_v1',documents=docs,tokenizer_files=[],audit_selection={'method':'preselected'})))
        return path

    def test_weighted_order_and_audit_boundary_never_reselect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root)
            plan=build_plan(source,8,expected_counts=self.counts)
            self.assertEqual(plan['ordered_source_indices'],[0,1,4,6,2,3,5,7])
            self.assertEqual(plan['batches'][0]['source_indices'],[0,1])
            self.assertTrue(all(len(b['audit_doc_ids'])<=1 for b in plan['batches']))
            self.assertEqual(sorted(i for b in plan['batches'] for i in b['source_indices']),list(range(8)))

    def test_audit_free_batch_and_tampered_order_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root,audits=())
            plan=build_plan(source,8,expected_counts=self.counts)
            target=root/'plan.json';target.write_text(json.dumps(plan))
            selected=load_batch(target,'B001',expected_counts=self.counts)
            self.assertEqual(selected['audit_doc_ids'],[])
            self.assertEqual(len(selected['documents']),8)
            plan['batches'][0]['source_indices'].reverse();target.write_text(json.dumps(plan))
            with self.assertRaises(ValueError):load_batch(target,'B001',expected_counts=self.counts)

    def test_token_bytes_and_no_padding_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root)
            doc=json.loads(source.read_text())['documents'][0];path=Path(doc['token_artifact']['path'])
            with path.open('ab') as stream:stream.write(b'changed')
            with self.assertRaises(ValueError):read_token_artifact(doc)
            np.savez(path,input_ids=np.array([1,2,3],np.int64),attention_mask=np.array([1,1,0],np.int64),position_ids=np.arange(3,dtype=np.int64))
            doc['token_artifact']=identity(path)
            with self.assertRaises(ValueError):read_token_artifact(doc)

    def test_predeclared_full_raw_ids_and_storage_hash_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root,audits=(0,2,4,6))
            plan=build_plan(source,8,expected_counts=self.counts);target=root/'plan.json';target.write_text(json.dumps(plan))
            policy=create_storage_policy(target)
            self.assertEqual(set(policy['full_hidden_audit_doc_ids']),{'d0','d4','d6'})
            self.assertEqual(next(row for row in policy['records'] if row['doc_id']=='d2')['raw_hidden_layers'],[0,15,31])
            storage=root/'storage.json';storage.write_text(json.dumps(policy))
            self.assertEqual(load_storage_policy(target,storage),policy)
            policy['records'][0]['raw_hidden_layers']=[0];storage.write_text(json.dumps(policy))
            with self.assertRaises(ValueError):load_storage_policy(target,storage)

    def test_consecutive_logical_batches_reuse_order_without_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root,audits=())
            plan=build_plan(source,2,expected_counts=self.counts);target=root/'plan.json';target.write_text(json.dumps(plan))
            selected=load_batch_group(target,'B001,B002',expected_counts=self.counts)
            self.assertEqual(selected['batch_ids'],['B001','B002'])
            self.assertEqual([doc['doc_id'] for doc in selected['documents']],['d0','d1','d4','d6'])
            self.assertEqual(selected['audit_doc_ids'],[])
            for ids in ['B002,B001','B001,B003','B001,B001','B999','']:
                with self.subTest(ids=ids),self.assertRaises(ValueError):
                    load_batch_group(target,ids,expected_counts=self.counts)

    def test_merged_audit_and_document_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root)
            target=root/'plan.json';target.write_text(json.dumps(build_plan(source,8,expected_counts=self.counts)))
            with self.assertRaisesRegex(ValueError,'one preselected raw audit'):
                load_batch_group(target,'B001,B002',expected_counts=self.counts)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);counts={'web':44,'news':22,'reviews':22};source=self.fixture(root,audits=(),counts=counts)
            plan=build_plan(source,16,expected_counts=counts);target=root/'plan.json';target.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'at most80'):
                load_batch_group(target,[row['batch_id'] for row in plan['batches']],expected_counts=counts)

    def test_frozen_manifest_identity_or_missing_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root,audits=());plan=build_plan(source,8,expected_counts=self.counts)
            target=root/'plan.json';target.write_text(json.dumps(plan));source.write_text(source.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'manifest hash mismatch'):
                load_batch_group(target,'B001',expected_counts=self.counts)
            source=self.fixture(root,audits=());target.write_text(json.dumps(build_plan(source,8,expected_counts=self.counts)))
            (root/'doc0.npz').unlink()
            with self.assertRaises(FileNotFoundError):load_batch_group(target,'B001',expected_counts=self.counts)

    def test_wrong_role_or_full_target_quota_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=self.fixture(root)
            with self.assertRaises(ValueError):build_plan(source)
            data=json.loads(source.read_text());data['documents'][0]['split']='dev';source.write_text(json.dumps(data))
            with self.assertRaises(ValueError):build_plan(source,8,expected_counts=self.counts)


if __name__=='__main__':unittest.main()
