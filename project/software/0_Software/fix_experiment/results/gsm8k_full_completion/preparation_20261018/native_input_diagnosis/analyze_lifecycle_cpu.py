#!/usr/bin/env python3
"""Recompute target-only AT009/AT010 evidence from persisted CPU tensors."""
import fcntl,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import torch
root=Path(__file__).resolve().parent
experiment=root.parents[3]
project=experiment.parents[3]
def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sha(t):return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
def load(p):return torch.load(p,map_location='cpu',weights_only=True)
def compare(a,b):
 difference=a.view(torch.int16)!=b.view(torch.int16)
 return {'exact':not bool(difference.any()),'changed_elements':int(difference.sum()),
         'max_abs_difference':float((a.float()-b.float()).abs().max()),
         'finite':bool(torch.isfinite(a).all() and torch.isfinite(b).all())}
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU-only analysis needs empty CUDA_VISIBLE_DEVICES')
if set(os.sched_getaffinity(0))!={18,19}:raise RuntimeError('requires CPU18,19')
report={'schema':'scalellm_layer25_allocation_diagnosis_AT008_AT010_v1',
        'created_at':datetime.now(timezone.utc).isoformat(),'source_sha256':sha_file(Path(__file__)),
        'execution_state':'completed','verdict':'GPU1 original model parameter allocation does not preserve checkpoint bytes; cause unresolved',
        'applicability':'Llama3.1-8B BF16 native eager, train:0000, exact layer25.up_proj only, assigned two cards',
        'formal_rows_validated':0,'attempts':[],'frozen_sources':[]}
for attempt in ['AT009','AT010']:
 p=root/attempt;d=json.loads((p/'diagnosis.json').read_text())
 original=load(p/'checkpoint_weight.pt')
 previous=None;trajectory=[];violations=[]
 for item in d['snapshots']:
  tensor=load(p/item['file']['path'])
  if sha_file(p/item['file']['path'])!=item['file']['sha256']:violations.append(item['label']+':file_sha')
  if sha(tensor)!=item['cpu']['sha256']:violations.append(item['label']+':tensor_sha')
  c=compare(original,tensor)
  if c['changed_elements']!=item['changed_elements']:violations.append(item['label']+':changed_elements')
  row={'label':item['label'],'group':item['group'],'gpu':item['gpu'],'sha256':sha(tensor),'checkpoint_comparison':c}
  if item['group']=='model_weight':
   if previous is not None:
    row['previous_comparison']=compare(previous,tensor)
    mask=previous.view(torch.int16)!=tensor.view(torch.int16)
    coords=mask.nonzero();a=(previous.view(torch.int16)[mask].int()&65535);b=(tensor.view(torch.int16)[mask].int()&65535)
    row['transition_bit_changes']={'set_bit_elements':int(((b&~a)!=0).sum()),'cleared_bit_elements':int(((a&~b)!=0).sum())}
    if coords.shape[0]:
     name=item['label']+'_transition_diff.pt'
     torch.save({'coordinates':coords,'previous_bf16_words':a,'current_bf16_words':b},p/name)
     row['transition_raw']={'path':name,'sha256':sha_file(p/name)}
     row['first_16_transition_coordinates']=coords[:16].tolist()
   previous=tensor
  trajectory.append(row)
 native={}
 for field in ['input','output','logits']:
  left=load(p/f'native_0_{field}.pt');right=load(p/f'native_1_{field}.pt')
  native[field]=compare(left,right)
  native[field]['first_sha256']=sha(left);native[field]['second_sha256']=sha(right)
 # Source and process cleanup checks do not depend on accelerator driver/NVML.
 with Path(d['lock']).open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);available=True;fcntl.flock(lock,fcntl.LOCK_UN)
 entry={'attempt':attempt,'state':d['state'],'pid':d['pid'],'started_at':d['started_at'],'ended_at':d['ended_at'],
        'gpu_uuid_actual':d['gpu_uuid_actual'],'cpu_affinity':d['cpu_affinity'],'source_sha256':d['source_sha256'],
        'source_snapshot_matches':sha_file(p/'source_snapshot.py')==d['source_sha256'],
        'checkpoint_sha256':sha(original),'trajectory':trajectory,'native_repeats':native,
        'recompute_discrepancies':violations,'pid_absent':not Path('/proc/'+str(d['pid'])).exists(),
        'lock_available':available,'hook_inventory':d['pre_diagnostic_hook_inventory']}
 report['attempts'].append(entry)
frozen=experiment/'results/gsm8k_full_completion/R002_gsm8k_native_cache_v2/frozen_sources'
for p in sorted(frozen.rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(frozen);live=project/rel
 report['frozen_sources'].append({'path':str(rel),'sha256':sha_file(p),'live_sha256':sha_file(live) if live.exists() else None,'unchanged':live.exists() and sha_file(live)==sha_file(p)})
report['all_frozen_sources_unchanged']=all(r['unchanged'] for r in report['frozen_sources'])
report['cuda_initialized']=torch.cuda.is_initialized()
report['interpretation']=[
 'AT008 native input identical while GPU weight content hashes changed; 18 isolated GEMMs using final stable weight all exact despite reused/fresh outputs.',
 'AT009 GPU1 original parameter differs from checkpoint immediately after original loader returns; pure blocking snapshot sequence changes content before any native generate; version stays0.',
 'AT009 target native outputs equal after target weight stabilizes but final logits differ, so layer25 alone is not a complete attribution of all remaining raw-logits differences.',
 'AT010 GPU0 same original loader/script/checkpoint/prompt has exact checkpoint identity at all17 snapshots and exact two native logits.',
 'Independent newly allocated correct target weight roundtrips exact on both cards. Evidence distinguishes original model allocation from separate allocation; it does not prove a general device hardware diagnosis.',
 'No threshold, backend, driver or production source change validated. Minimal next action is retain matrix stop and obtain targeted allocation/weight-identity diagnosis or a controller-approved guarded relocation experiment before repair.']
report['limitations']=['Only one layer and one prompt measured; no all-model-weight scan, formal GSM8K or hardware health qualification.',
 'AT008 native1/native2 share pre-weight SHA but output differs, so per-call pre-SHA alone does not establish immutable operands through GEMM.',
 'Full model production qualification remains unsatisfied; GPU0 diagnosis is not a replacement for fixed-GPU R002 formal qualification.']
(root/'analysis_AT008_AT010.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'attempts':[{'attempt':r['attempt'],'native_repeats':r['native_repeats'],'recompute_discrepancies':r['recompute_discrepancies'],'lock_available':r['lock_available']} for r in report['attempts']],
                  'all_frozen_sources_unchanged':report['all_frozen_sources_unchanged'],'cuda_initialized':report['cuda_initialized']},indent=2))
