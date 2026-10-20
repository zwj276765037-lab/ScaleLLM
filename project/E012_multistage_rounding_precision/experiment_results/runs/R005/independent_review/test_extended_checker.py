"""CPU fixtures only; never additional model/experiment evidence."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import copy,hashlib,json,struct,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
EXPERIMENT=ROOT/'project/software/0_Software/rounding_precision/experiment'
sys.path.insert(0,str(EXPERIMENT))
from audit_extended_numerical import audit_logit_record,independent_logit_row,exact_dyadic_dot

class AuditTests(unittest.TestCase):
 def test_exact_binary_dot(self):
  from fractions import Fraction
  x=np.asarray([1.,2**-30,-1.,-2**-30],np.float32)
  self.assertEqual(exact_dyadic_dot(x,np.ones(4,np.float32)),Fraction(0))
  y=np.asarray([.5,-.25,.125,2.],np.float32)
  self.assertEqual(exact_dyadic_dot(x,y),sum((Fraction.from_float(float(a))*Fraction.from_float(float(b)) for a,b in zip(x,y)),Fraction()))
 def test_metrics_ties_shift_and_low_margin(self):
  a=np.array([3.,3.,1.,-2.],np.float32);b=a-2
  row=independent_logit_row(a,b)
  self.assertEqual(row['current_top1_ids'],0);self.assertEqual(row['current_top1_tie_counts'],2)
  self.assertEqual(row['reference_top1_margin'],0);self.assertFalse(row['margin_certified'])
  self.assertLess(row['max_abs_logprob_delta'],1e-14)
 def test_real_api_with_independent_source_and_raw_checks(self):
  import torch
  from logit_numerical_extension import load_output_head,measure_logits
  torch.set_num_threads(1)
  with tempfile.TemporaryDirectory(prefix='A014_head_fixture_') as directory:
   path=Path(directory);V,D,T=4101,7,3;rng=np.random.default_rng(1941)
   float_rows=rng.normal(size=(V,D)).astype(np.float32)
   bits=(float_rows.view(np.uint32)>>16).astype('<u2');body=bits.tobytes()
   header=json.dumps({'lm_head.weight':{'dtype':'BF16','shape':[V,D],'data_offsets':[0,len(body)]}},separators=(',',':')).encode()
   header+=b' '*((-len(header))%8)
   (path/'model.safetensors').write_bytes(struct.pack('<Q',len(header))+header+body)
   (path/'config.json').write_text(json.dumps({'vocab_size':V,'hidden_size':D,'tie_word_embeddings':False}))
   (path/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{'lm_head.weight':'model.safetensors'}}))
   head=load_output_head(path,torch.device('cpu'),path/'head')
   current=rng.normal(size=(T,D)).astype(np.float32);reference=current+np.float32(.015)
   for arm,value in [('current',current),('reference',reference)]:np.savez_compressed(path/f'final_hidden_{arm}.npz',hidden=value[None])
   doc={'doc_id':'synthetic_audit_fixture','domain':'fixture','_logit_audit_dir':str(path)}
   row=measure_logits(current,reference,head,doc)
   report=audit_logit_record(row,path,set())
   self.assertEqual(report['raw_positions'],[0,1,2]);self.assertGreater(report['head_roundoff']['dots_checked'],0)
   self.assertEqual(len(report['head_roundoff']['exact_dyadic_spots']),4)
   corrupted=copy.deepcopy(row);corrupted['per_token']['current_top1_tie_counts'][0]+=1
   with self.assertRaises(AssertionError):audit_logit_record(corrupted,path,set())
   corrupted=copy.deepcopy(row);corrupted['top1_match_count']-=1
   with self.assertRaises(AssertionError):audit_logit_record(corrupted,path,set())
   corrupted=copy.deepcopy(row);corrupted['vocab_chunks'][-1][1]-=1
   with self.assertRaises(AssertionError):audit_logit_record(corrupted,path,set())
   self.assertFalse(torch.cuda.is_initialized())

 def test_complete_mlp_cpu_fixture_and_rejections(self):
  import torch
  from unittest.mock import patch
  sys.path.insert(0,str(EXPERIMENT.parent/'tests'))
  import test_mlp_numerical_extension as fixture
  from mlp_numerical_extension import MLPNumericalObserver
  from audit_extended_numerical import audit_mlp_records
  torch.set_num_threads(1);v5=fixture._v5();model,audit=fixture.make_model(v5,count=32)
  source=torch.linspace(-.14,.17,64).reshape(1,2,32)
  with patch.object(v5,'grouped_linear_s24',fixture.cpu_linear),patch.object(fixture.gpu_reference,'grouped_linear_exact',fixture.cpu_exact):
   observer=MLPNumericalObserver(v5,model,backend=fixture.backend(),audit_doc_ids=['audit'],expected_layers=32,samples_per_layer=16)
   for arm in ['current','reference']:
    observer.set_context(doc_id='audit',arm=arm)
    from contextlib import nullcontext
    with (fixture.gpu_reference.arithmetic_context(v5) if arm=='reference' else nullcontext()):
     with observer.context():model(source)
   rows=observer.flush('audit')
  result=audit_mlp_records(rows,'audit',True)
  self.assertEqual(result['mlp_rows'],416);self.assertEqual(result['independent_product_samples'],1024)
  self.assertEqual(result['independent_host_conversion_samples'],1024)
  corrupted=copy.deepcopy(rows);sample=next(r for r in corrupted if r['op']=='silu_lookup')['metadata']['raw_samples'][0];sample['product_s32_actual']+=1
  with self.assertRaises(AssertionError):audit_mlp_records(corrupted,'audit',True)
  corrupted=copy.deepcopy(rows);sample=next(r for r in corrupted if r['op']=='down_host_total')['metadata']['raw_samples'][0];sample['current']+=1
  with self.assertRaises(AssertionError):audit_mlp_records(corrupted,'audit',True)
  with self.assertRaises(AssertionError):audit_mlp_records(rows[:-1],'audit',True)
  self.assertFalse(torch.cuda.is_initialized())

class RuntimeBindingTests(unittest.TestCase):
 def test_shared_receipt_binding_and_reject_bad_identity(self):
  from audit_extended_numerical import runtime_bindings,sha_file
  with tempfile.TemporaryDirectory(prefix='A014_runtime_fixture_only_') as directory:
   root=Path(directory);session=root/'session';group=root/'group';session.mkdir();group.mkdir()
   def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
   def identity(path):return {'path':str(path),'sha256':sha_file(path)}
   shared={'pid':123,'pgid':123,'starttime':456,'argv':['CPU metadata fixture; no GPU process']}
   launch=session/'session_launch_manifest.json';dump(launch,{'shared_worker_identity':shared})
   receipt=session/'session_gpu_receipt.json';terminal={'execution_state':'completed','exit_code':0,'native_exit_code':0,'worker_reaped':True,'source_unchanged':True,'stop_reason':None,'shared_worker_identity':shared,'worker_pid':123};dump(receipt,terminal)
   source=root/'source.py';source.write_text('fixture');code=[identity(source)]
   common={'runtime_kind':'segment_of_shared_gpu_worker','shared_session':str(session),'shared_worker_identity':shared}
   paired={**common,'formal_batch_ids':['B001'],'documents':[{'doc_id':'d0','tokens':1}]};dump(group/'paired_result.json',paired)
   dump(group/'paired_worker_manifest.json',{**common,'code':code})
   loader=session/'stream_loader_validation.json';dump(loader,{'fixture':True})
   head=session/'output_head/output_head_identity.json';dump(head,{'fixture_head':True})
   dump(group/'shared_loader_reference.json',{'global_loader':identity(loader)})
   dump(group/'output_head/shared_head_reference.json',{'global_head':identity(head)})
   dump(group/'output_head/output_head_identity.json',{'fixture_head':True})
   gr={'schema':'m005_r005_persistent_group_receipt_v1','execution_state':'completed','runtime_kind':'segment_of_shared_gpu_worker',
       'source_unchanged':True,'coverage_complete':True,'exit_code':0,'canonical_group_path':str(group),'session_path':str(session),
       'session_launch_identity':identity(launch),'global_receipt_path':str(receipt),'logical_batch_ids':['B001'],'doc_ids':['d0'],'completed_doc_ids':['d0'],
       'actual_token_lengths':[1],'shared_worker_identity':shared,'group_id':'G001','code':code,'input_identities':[],
       'output_identities':[identity(group/'paired_result.json'),identity(group/'paired_worker_manifest.json')]}
   gp=group/'execution_receipt.json';dump(gp,gr)
   analysis={'schema':'m005_r005_analysis_manifest_v1','model_execution_complete':True,'completed_documents':1024,'expected_documents':1024,
       'missing_doc_ids':[],'actual_doc_ids':['d'+str(i) for i in range(1024)],'expected_doc_ids':['d'+str(i) for i in range(1024)],
       'shared_worker_identity':shared,'session_gpu_receipt':identity(receipt),'session_launch_manifest':identity(launch),
       'ordered_groups':[{'attempt_path':str(group),'group_id':'G001','receipt':identity(gp)}]}
   dump(session/'analysis_manifest.json',analysis)
   _,_,binding=runtime_bindings(group,session)
   self.assertEqual(binding['group_receipt']['path'],str(gp));self.assertTrue(binding['shared_process'])
   corrupt=copy.deepcopy(terminal);corrupt['native_exit_code']=1;dump(receipt,corrupt)
   with self.assertRaisesRegex(AssertionError,'must finish'):runtime_bindings(group,session)
   dump(receipt,terminal);corrupt=copy.deepcopy(gr);corrupt['shared_worker_identity']['starttime']=999;dump(gp,corrupt)
   with self.assertRaisesRegex(AssertionError,'shared launch'):runtime_bindings(group,session)
   dump(gp,gr);source.write_text('changed')
   with self.assertRaisesRegex(AssertionError,'file identity'):runtime_bindings(group,session)

if __name__=='__main__':unittest.main(verbosity=2)
