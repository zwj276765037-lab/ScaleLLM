"""Read-only provisional same-input comparison; no global completion claim."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import argparse,json,hashlib,time
from collections import Counter
from pathlib import Path
import numpy as np


def require(test,label):
 if not test:raise AssertionError(label)

def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while block:=f.read(8<<20):h.update(block)
 return h.hexdigest()
def identity(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def rows(path):
 with Path(path).open() as f:return [json.loads(line) for line in f if line.strip()]
def cleaned(row,drop=('output_artifact','artifact')):return {k:v for k,v in row.items() if k not in drop}

def main():
 p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();start=time.monotonic()
 require(not a.output.exists(),'new comparison record only')
 old,new,session=(v.resolve() for v in (a.old,a.new,a.session));receipt_path=new/'execution_receipt.json';receipt=read(receipt_path);receipt_sha=sha(receipt_path)
 require(receipt['execution_state']=='completed' and receipt['source_unchanged'] and receipt['coverage_complete'],'completed group segment required')
 require(receipt['runtime_kind']=='segment_of_shared_gpu_worker' and Path(receipt['session_path']).resolve()==session,'canonical shared group')
 launch=read(session/'session_launch_manifest.json');require(receipt['shared_worker_identity']==launch['shared_worker_identity'],'actual shared process identity')
 require(sha(receipt['session_launch_identity']['path'])==receipt['session_launch_identity']['sha256'],'group launch identity')
 old_terminal=read(old/'gpu_receipt.json');require(old_terminal['execution_state']=='completed' and old_terminal['native_exit_code']==0 and old_terminal['source_unchanged'],'qualified historical baseline')
 om,nm=read(old/'paired_worker_manifest.json'),read(new/'paired_worker_manifest.json');old_ids=[x['doc_id'] for x in om['selected_documents']];ids=[x['doc_id'] for x in nm['selected_documents']]
 require(len(ids)==16 and ids==receipt['doc_ids'] and set(ids)<=set(old_ids),'same frozen16 documents')
 expected_index={doc:i for i,doc in enumerate(old_ids)};new_index={doc:i for i,doc in enumerate(ids)}
 require([old_ids[i] for i in sorted(expected_index[x] for x in ids)]==ids,'baseline relative document order')
 sources_old={r['path']:r['sha256'] for r in om['code']};sources_new={r['path']:r['sha256'] for r in nm['code']}
 for r in launch['source_identity']:require(sha(r['path'])==r['sha256'],'frozen source changed '+r['path'])
 overlap=sorted(set(sources_old)&set(sources_new));source_changes=[path for path in overlap if sources_old[path]!=sources_new[path]]
 old_loader=read(old/'stream_loader_validation.json');new_loader=read(session/'stream_loader_validation.json')
 require(old_loader['consumed_base_model_identity_sha256']==new_loader['consumed_base_model_identity_sha256'],'same consumed model parameters')
 old_attach,new_attach=read(old/'v5_attach_metadata.json'),read(new/'v5_attach_metadata.json')
 require(old_attach['lm_head']=='Identity; never loaded/called' and new_attach['lm_head']=='Identity facade; separate shared FP32 output head measured after both arms','explicit separate added head measurement description')
 require({k:v for k,v in old_attach.items() if k!='lm_head'}=={k:v for k,v in new_attach.items() if k!='lm_head'},'same attached core numerical configuration')
 evidence=[identity(receipt_path),identity(session/'session_launch_manifest.json'),identity(old/'gpu_receipt.json'),identity(old/'paired_worker_manifest.json'),identity(new/'paired_worker_manifest.json')]
 mismatches=[];counts=Counter();docs={doc:Counter() for doc in ids}
 def compare(x,y,kind,doc,coord):
  counts[kind+'_compared']+=1;docs[doc][kind+'_compared']+=1
  if x!=y:
   counts[kind+'_mismatch']+=1;docs[doc][kind+'_mismatch']+=1
   if len(mismatches)<30:mismatches.append({'kind':kind,'doc_id':doc,'coordinate':coord})
 for filename,kind,key,n in [('tensor_metrics.jsonl','hidden',lambda r:(r['layer'],r['node'],r['op']),32),('local_tensor_metrics.jsonl','local',lambda r:(r['layer'],r['node'],r['op']),384),('dynamic_metadata.jsonl','dynamic',lambda r:(r['arm'],r['layer'],r['function'],r['ordinal']),384)]:
  maps=[]
  for base in (old,new):
   data={}
   for row in rows(base/filename):
    if row['doc_id'] not in docs:continue
    coord=(row['doc_id'],*key(row));require(coord not in data,'duplicate coordinate');data[coord]=row
   require(Counter(c[0] for c in data)==Counter({d:n for d in ids}),'full coordinate coverage '+kind);maps.append(data);evidence.append(identity(base/filename))
  require(maps[0].keys()==maps[1].keys(),'same complete '+kind+' coordinates')
  for coord,row in maps[0].items():
   other=maps[1][coord];compare(cleaned(row),cleaned(other),kind,coord[0],coord[1:])
   if kind=='dynamic':counts['dynamic_field_hashes_compared']+=len(row['identity'])
 for doc in ids:
  od=old/'documents'/f'doc{expected_index[doc]:04d}';nd=new/'documents'/f'doc{new_index[doc]:04d}'
  for name,kind in [('input_identity.json','input'),('final_norm_comparison.json','final_norm'),('audit_current.json','current_counters'),('audit_reference.json','reference_counters')]:
   compare(cleaned(read(od/name)),cleaned(read(nd/name)),kind,doc,name);evidence.extend([identity(od/name),identity(nd/name)])
  d_old,d_new=read(od/'document_result.json'),read(nd/'document_result.json')
  keep=('doc_id','tokens','audited','dynamic_events','dynamic_changed_elements','coverage','final_norm_relative_l2_percent')
  compare({k:d_old[k] for k in keep},{k:d_new[k] for k in keep},'document_core_summary',doc,[]) 
  for op in sorted(od.glob('*.npz')):
   np=nd/op.name;require(np.exists(),'same saved raw artifact coverage '+op.name)
   with __import__('numpy').load(op,allow_pickle=False) as left,__import__('numpy').load(np,allow_pickle=False) as right:
    require(set(left.files)==set(right.files),'same raw array keys')
    for key in left.files:
     x,y=left[key],right[key]
     compare({'shape':x.shape,'dtype':str(x.dtype),'bytes':hashlib.sha256(x.tobytes()).hexdigest()},
             {'shape':y.shape,'dtype':str(y.dtype),'bytes':hashlib.sha256(y.tobytes()).hexdigest()},'raw_array',doc,[op.name,key])
   evidence.extend([identity(op),identity(np)])
 def witnesses(base):
  wm=read(base/'node_witnesses/manifest.json');out={}
  for r in wm['records']:
   if r['doc_id'] in docs:
    key=(r['doc_id'],r['layer'],r['node'],r['op_name'],r['call_ordinal']);require(key not in out,'duplicate witness');out[key]=r
  return out
 wl,wr=witnesses(old),witnesses(new);require(wl.keys()==wr.keys(),'same preselected witness coverage')
 for key,record in wl.items():
  other=wr[key];compare(record['status'],other['status'],'witness_status',key[0],key[1:])
  if record['status']=='saved':
   compare(record['arrays'],other['arrays'],'witness_arrays',key[0],key[1:])
   for base,r in ((old,record),(new,other)):require(sha(base/'node_witnesses'/r['path'])==r['sha256'],'authentic saved witness identity')
 require(sha(receipt_path)==receipt_sha,'group receipt unchanged during review')
 for e in evidence:require(sha(e['path'])==e['sha256'],'evidence unchanged during review')
 bad=sum(v for k,v in counts.items() if k.endswith('_mismatch'))
 report={'schema':'m005_r005_provisional_same_core_trajectory_v1','execution_state':'completed','scope':'provisional completed group only; global session may still be running; does not replace final67audits/analysis',
  'old_attempt':str(old),'new_group':str(new),'global_session':str(session),'shared_worker_identity':receipt['shared_worker_identity'],'doc_ids':ids,'documents':16,
  'same_consumed_weights':True,'same_core_attach_configuration':True,'declared_measurement_extension':{'old_lm_head':old_attach['lm_head'],'new_lm_head':new_attach['lm_head']},'shared_source_count':len(overlap),'changed_shared_sources':source_changes,'counts':dict(counts),'mismatch_records_first30':mismatches,
  'exact_core_observables_equal':bad==0,'per_document':[{ 'doc_id':d,**dict(docs[d])} for d in ids],
  'interpretation':'Core metric JSON values, complete dynamic array SHA identities and available raw arrays are compared exactly. Equal aggregates alone do not prove all unsaved hidden values equal.',
  'no_global_completion_claim':True,'precision_verdict':'not_evaluated','seconds':time.monotonic()-start,'source':identity(__file__),'evidence':evidence}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({k:report[k] for k in ['execution_state','documents','counts','changed_shared_sources','exact_core_observables_equal','seconds']}))

if __name__=='__main__':main()
