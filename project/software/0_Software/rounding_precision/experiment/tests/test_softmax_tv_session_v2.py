"""CPU dummy tests for orchestration only; no formal numerical data is fabricated."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_softmax_tv_session_v2 as session
import bounded_softmax_tv_session_v2 as supervisor
import run_formal_numerical_queue as ownership
from run_numerical_fidelity import identity


def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))


def fixture(directory):
    globaldir=directory/'session';globaldir.mkdir();source=directory/'source.py';source.write_text('frozen')
    source_id=identity(source);input_path=directory/'input.json';input_path.write_text('{}');input_id=identity(input_path)
    dump(globaldir/'session_launch_manifest.json',{'budget_started_monotonic':0})
    dump(globaldir/'session_worker.json',{'shared_worker_identity':{'pid':123,'pgid':123,'starttime':456,'argv':['CPU test fixture']}})
    groups=[]
    for i in range(2):
        groups.append(dict(group_id=f'G{i}',attempt_id=f'AT{i}',title='dummy_test',attempt_path=str(directory/f'group{i}'),
                           logical_batch_ids=[f'B{i}'],doc_ids=[f'd{i}'],actual_token_lengths=[1]))
    prep=dict(plan=dict(source_identities=[source_id],formal_batch_plan=input_id,formal_storage_plan=input_id,
                        limits=dict(total_wall_seconds=10000,group_wall_seconds=900,cleanup_reserve_seconds=30)),
              groups=groups,expected_doc_ids=['d0','d1'])
    return prep,globaldir,source


def fake_worker(group,missing=False):
    directory=Path(group['attempt_path']);doc=group['doc_ids'][0]
    d=dict(doc_id=doc,tokens=1,coverage=dict(complete=True,hidden_unique_layers=32,local_unique_coordinates=384,dynamic_unique_coordinates_per_arm=192),
           mlp_coverage=dict(complete=True,unique_coordinates=416),logit_coverage=dict(complete=True,real_positions=1,vocabulary=128256,score_pairs=128256))
    dump(directory/'paired_worker_manifest.json',{'unit_test_only':True})
    dump(directory/'paired_result.json',dict(execution_state='completed',required_extension_complete=True,source_unchanged=True,
         formal_eval_documents=1,formal_batch_ids=group['logical_batch_ids'],documents=[d]))
    for filename,n in [('tensor_metrics.jsonl',32),('local_tensor_metrics.jsonl',384),('mlp_metrics.jsonl',416),('logit_metrics.jsonl',1),('dynamic_metadata.jsonl',384)]:
        (directory/filename).write_text((json.dumps({'doc_id':doc})+'\n')*(n-1 if missing and filename=='mlp_metrics.jsonl' else n))
    dump(directory/'documents'/'doc0000'/'logit_metrics.json',{'softmax_tv':dict(complete=True,tokens=1,vocab_size=128256,probability_pairs=128256,tv=[0.],probability_mass_current=[1.],probability_mass_reference=[1.],document_mean=0.,document_max=0.)})
    (directory/'report.md').write_text('management')
    return 0


class PersistentExecutionTests(unittest.TestCase):
    def test_two_groups_success_atomic_update_and_management_hash_exclusion(self):
        with tempfile.TemporaryDirectory() as t:
            prep,directory,source=fixture(Path(t))
            result=session.execute_groups(prep,directory,fake_worker,clock=lambda:1)
            self.assertEqual(result['completed_doc_ids'],['d0','d1'])
            self.assertEqual(session.read(directory/'group_progress.json')['execution_state'],'completed')
            for g in prep['groups']:
                p=Path(g['attempt_path']);receipt=session.read(p/'execution_receipt.json')
                self.assertEqual(receipt['runtime_kind'],'segment_of_shared_gpu_worker')
                self.assertTrue(session.read(p/'paired_result.json')['shared_session'])
                hashes=receipt['output_identities'];(p/'report.md').write_text('registration changed')
                self.assertFalse(any(Path(x['path']).name=='report.md' for x in hashes))
                for item in hashes:self.assertEqual(identity(item['path'])['sha256'],item['sha256'])

    def test_second_group_failure_stops_and_preserves_first(self):
        with tempfile.TemporaryDirectory() as t:
            prep,directory,source=fixture(Path(t));called=[]
            def run(g):
                called.append(g['group_id'])
                return fake_worker(g) if len(called)==1 else 2
            with self.assertRaisesRegex(RuntimeError,'native exit2|native exit 2'):session.execute_groups(prep,directory,run,clock=lambda:1)
            self.assertEqual(called,['G0','G1'])
            self.assertEqual(session.read(Path(prep['groups'][0]['attempt_path'])/'execution_receipt.json')['execution_state'],'completed')
            self.assertEqual(session.read(Path(prep['groups'][1]['attempt_path'])/'execution_receipt.json')['execution_state'],'failed')
            self.assertFalse((directory/'session_worker_result.json').exists())

    def test_no_launch_after_deadline_and_incomplete_rows_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            prep,directory,source=fixture(Path(t))
            with self.assertRaisesRegex(RuntimeError,'remaining global budget'):
                session.execute_groups(prep,directory,lambda g:self.fail('must not start'),clock=lambda:9999)
            self.assertFalse(Path(prep['groups'][0]['attempt_path']).exists())
            with self.assertRaisesRegex(ValueError,'raw row coverage'):
                session.execute_groups(prep,directory,lambda g:fake_worker(g,missing=True),clock=lambda:1)

    def test_source_change_stops_and_sequence_not_resampled(self):
        with tempfile.TemporaryDirectory() as t:
            prep,directory,source=fixture(Path(t))
            def run(g):fake_worker(g);source.write_text('changed');return 0
            with self.assertRaisesRegex(ValueError,'identity changed'):session.execute_groups(prep,directory,run,clock=lambda:1)
            self.assertFalse(Path(prep['groups'][1]['attempt_path']).exists())
        with self.assertRaises(ValueError):session.check_sequence([{'logical_batch_ids':['B1'],'doc_ids':['d1']}],['B1','B2'],['d1','d2'])

    def test_atomic_partial_disappearance_does_not_stop_session(self):
        class Disappeared:
            def stat(self):raise FileNotFoundError('atomic replace')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'actual';p.write_bytes(b'abc')
            with patch.object(Path,'rglob',return_value=iter([Disappeared(),p])):
                self.assertEqual(supervisor.directory_bytes(t),3)

    def test_sibling_storage_is_counted_once(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'session').mkdir();(p/'group/child').mkdir(parents=True)
            (p/'session/data').write_bytes(b'a'*3);(p/'group/child/data').write_bytes(b'b'*7)
            self.assertEqual(supervisor.evidence_bytes(p/'session',[{'attempt_path':str(p/'group')},{'attempt_path':str(p/'group/child')}]),10)

    def test_missing_exec_identity_reaps_only_direct_dummy_child(self):
        process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        supervisor.stop_child(process,None)
        self.assertIsNotNone(process.poll())
        self.assertIsNone(ownership.process_identity(process.pid))

    def test_cpu_dummy_deadline_reaps_verified_owned_process(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t);command=[sys.executable,'-c','import time;time.sleep(30)']
            process=subprocess.Popen(command,start_new_session=True);proof=ownership.launched_identity(process,command)
            prep=dict(plan=dict(limits=dict(total_wall_seconds=1,cleanup_reserve_seconds=0,total_evidence_mib=1,group_wall_seconds=900)),groups=[])
            result=supervisor.monitor(process,proof,prep,directory,0,clock=lambda:2,sample=lambda:dict(rss=1,gpu=0,device={'free_bytes':20<<30}))
            self.assertEqual(result['exit_code'],124);self.assertTrue(result['worker_reaped'])
            self.assertIsNotNone(process.poll());self.assertFalse(ownership.same_process(proof))


if __name__=='__main__':unittest.main()
