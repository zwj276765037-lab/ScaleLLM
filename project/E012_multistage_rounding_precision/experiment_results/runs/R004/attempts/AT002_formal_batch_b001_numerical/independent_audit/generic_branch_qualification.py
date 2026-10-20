import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import json,hashlib,tempfile,subprocess,sys
from pathlib import Path
root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
source=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical'
script=root/'project/software/0_Software/rounding_precision/experiment/audit_formal_numerical.py'
work=Path(tempfile.mkdtemp(prefix='A014_generic_synthetic_fixture_'))
def load(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d))
def ident(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
reports=[]
for mode in ['no_audit_absent','no_audit_empty_manifest','thin_three_layers','bad_non_audit_final']:
 target=work/mode;target.mkdir()
 for p in source.iterdir():
  if p.name not in ['independent_audit','aggregate_v1','overview_v1','overview_v2','node_witnesses','paired_worker_manifest.json','tensor_metrics.jsonl','dynamic_metadata.jsonl','node_witness_policy.json','paired_result.json','documents']:(target/p.name).symlink_to(p,target_is_directory=p.is_dir())
 manifest=load(source/'paired_worker_manifest.json');plan=load(Path(manifest['document_source']['path']));storage=load(Path(manifest['formal_storage_source']['path']));result=load(source/'paired_result.json')
 thin=mode=='thin_three_layers';audit=manifest['audit_document_ids'][0]
 if thin:
  for rec in storage['records']:
   if rec['doc_id']==audit:rec['raw_hidden_layers']=[0,15,31]
  (target/'node_witnesses').symlink_to(source/'node_witnesses',target_is_directory=True)
 else:
  manifest['audit_document_ids']=[]
  for b in plan['batches']:
   if b['batch_id'] in result['formal_batch_ids']:b['audit_doc_ids']=[]
  if mode=='no_audit_empty_manifest':
   (target/'node_witnesses').mkdir();write(target/'node_witnesses/manifest.json',{'audit_doc_ids':[],'records':[]})
 write(target/'fixture_plan.json',plan);manifest['document_source']=ident(target/'fixture_plan.json');storage['input_plan']=manifest['document_source']
 write(target/'fixture_storage.json',storage);manifest['formal_storage_source']=ident(target/'fixture_storage.json');write(target/'paired_worker_manifest.json',manifest);write(target/'paired_result.json',result)
 for name in ['tensor_metrics.jsonl','dynamic_metadata.jsonl']:
  rows=[json.loads(l) for l in (source/name).open() if l.strip()]
  for r in rows:
   if name=='tensor_metrics.jsonl' and (not thin or r['layer'] not in [0,15,31]):r['output_artifact']=None
   if name=='dynamic_metadata.jsonl' and not thin:r['artifact']=None
  (target/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
 write(target/'node_witness_policy.json',{'audit_doc_ids':[audit] if thin else [],'collection_enabled':thin})
 if mode=='bad_non_audit_final':
  (target/'documents').mkdir()
  for d in (source/'documents').iterdir():
   if d.name!='doc0000':(target/'documents'/d.name).symlink_to(d,target_is_directory=True);continue
   dst=target/'documents'/d.name;dst.mkdir()
   for p in d.iterdir():
    if p.name!='final_norm_comparison.json':(dst/p.name).symlink_to(p,target_is_directory=p.is_dir())
   final=load(d/'final_norm_comparison.json');final['metrics']['current_vs_reference']['relative_l2_percent']+=1;write(dst/'final_norm_comparison.json',final)
 else:(target/'documents').symlink_to(source/'documents',target_is_directory=True)
 cp=subprocess.run([sys.executable,'-B',str(script),'--attempt',str(target),'--output',str(target/'audit_result.json')],capture_output=True,text=True,timeout=45)
 expect=mode!='bad_non_audit_final';assert (cp.returncode==0)==expect,(mode,cp.returncode,cp.stderr)
 if not expect:assert 'final aggregate formula relative_l2_percent' in cp.stderr,cp.stderr
 report={'case':mode,'fixture_only':True,'expected_accept':expect,'exit_code':cp.returncode,'stdout':cp.stdout,'stderr_tail':cp.stderr[-1000:]};reports.append(report);print(json.dumps(report),flush=True)
write(work/'qualification_results.json',{'fixture_only':True,'source_attempt':str(source),'auditor':ident(script),'cases':reports})
print('QUALIFICATION_REPORT='+str(work/'qualification_results.json'))
