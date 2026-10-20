#!/usr/bin/env python3
"""CPU evidence audit; does not import CUDA libraries."""
import argparse,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('attempt',type=Path);a=p.parse_args();d=a.attempt.resolve();status=json.loads((d/'status.json').read_text());launch=json.loads((d/'launch.json').read_text());terminal=json.loads((d/'terminal.json').read_text());errors=[];summaries=[]
 assert status['execution_state'] in ['completed','failed']
 assert terminal['exit_code']==0 and status['execution_state']=='completed'
 assert sha(d/'source_snapshot.py')==status['source_sha256']==launch['source_sha256']
 assert status['gpu_uuid_actual']=='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533' and status['cpu_affinity']==[18,19]
 assert len(status['allocations'])==80 and sum(r['size_bytes']for r in status['allocations'])==20*(1<<30)
 assert all(r==0 for r in status['allocation_free_return_codes']) and status['context_destroy_return_code']==0 and status['lock_released_at']
 for t in status['tests']:
  assert len(t['reads'])==160
  failed={};transitions=[]
  for r in t['reads']:
   if r['repeat']==1:transitions.append(r['changed_bytes_from_previous_read'])
   if not r['changed_bytes']:continue
   f=d/r['raw_diff_file'];assert sha(f)==r['raw_diff_sha256']
   with np.load(f,allow_pickle=False) as raw:coords=raw['byte_offsets'];expected=raw['expected'];observed=raw['observed'];xor=raw['xor']
   assert r['raw_diff_coordinates_complete'] and len(coords)==r['changed_bytes'] and np.all(coords[1:]>coords[:-1])
   label=t['pattern'];value=int(label,16) if label!='ramp' else None
   truth=np.full(coords.shape,value,dtype=np.uint8) if value is not None else ((coords+17*r['allocation_index'])%256).astype(np.uint8)
   assert np.array_equal(truth,expected) and np.array_equal(xor,np.bitwise_xor(expected,observed)) and np.all(xor!=0)
   vals,counts=np.unique(xor,return_counts=True);assert {str(int(v)):int(c)for v,c in zip(vals,counts)}==r['xor_histogram']
   pages=d/(f.stem.removesuffix('_diff')+'_pages.npz')
   with np.load(pages,allow_pickle=False)as pg:page=pg['page_offset'];pc=pg['changed_byte_counts']
   ep,ec=np.unique(coords//4096,return_counts=True);assert np.array_equal(page,ep)and np.array_equal(pc,ec)
   failed.setdefault(r['allocation_index'],[]).append({'repeat':r['repeat'],'changed_bytes':r['changed_bytes'],'even_byte_offsets':int(np.count_nonzero(coords%2==0)),'odd_byte_offsets':int(np.count_nonzero(coords%2==1)),'observed_ff_count':int(np.count_nonzero(observed==255)),'set_bit_bytes':int(np.count_nonzero(np.bitwise_and(np.bitwise_not(expected),observed))),'cleared_bit_bytes':int(np.count_nonzero(np.bitwise_and(expected,np.bitwise_not(observed)))),'first_byte_offset':int(coords[0]),'last_byte_offset':int(coords[-1]),'raw_diff_sha256':sha(f)})
  summary={'test_id':t['test_id'],'route':t['route'],'pattern':t['pattern'],'read_count':len(t['reads']),'failing_reads':sum(r['changed_bytes']>0 for r in t['reads']),'failing_allocations':sorted(failed),'changed_bytes_total_including_repeats':sum(r['changed_bytes']for r in t['reads']),'changed_bytes_first_read_only':sum(r['changed_bytes']for r in t['reads']if r['repeat']==0),'repeat_read_transition_changed_bytes':sum(transitions),'failures':failed}
  assert summary['changed_bytes_total_including_repeats']==t['changed_bytes'];summaries.append(summary)
 assert len(summaries)==2
 assert all(c['passed'] for c in status['gpu_observer']['self_tests']) and len(status['gpu_observer']['self_tests'])==2
 receipt=json.loads((d/'compile_receipt.json').read_text())
 assert sha(d/'observer.cubin')==receipt['cubin_sha256']==status['gpu_observer']['compiled_cubin_sha256']
 assert sha(d/'observer.cu')==receipt['kernel_source_sha256']==status['gpu_observer']['kernel_source_sha256']
 assert len(status['allocation_free_return_codes'])==82
 for t in status['tests']:
  for r in t['reads']:
   obs=r['gpu_internal_observer']; assert obs['small_result_reads_equal']
   if obs['mismatch_byte_count']:
    assert 0<=obs['first_mismatch_byte_offset']<r['size_bytes'] and obs['first_observed_byte']!=int(t['pattern'],16)
   assert r['gpu_cpu_mismatch_counts_equal']==(obs['mismatch_byte_count']==r['changed_bytes'])
 result={'schema':'scalellm_gpu_internal_observer_evidence_audit_v1','attempt':d.name,'created_at':datetime.now(timezone.utc).isoformat(),'analyzer_sha256':sha(__file__),'cpu_affinity':sorted(os.sched_getaffinity(0)),'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'status_sha256':sha(d/'status.json'),'launch_sha256':sha(d/'launch.json'),'terminal_sha256':sha(d/'terminal.json'),'execution_state':'completed','raw_cuda_test_count':len(summaries),'reads_total':sum(x['read_count']for x in summaries),'failing_reads_total':sum(x['failing_reads']for x in summaries),'byte_for_byte_diff_records_recomputed':sum(x['failing_reads']for x in summaries),'source_identity_and_resource_cleanup_verified':True,'tests':summaries,'review':'engineering self-audit only; independent reviewer pending'}
 result['native_observer_controls_passed']=True
 result['gpu_observer_self_tests']=status['gpu_observer']['self_tests']
 result['gpu_internal_failing_reads']=sum(r['gpu_internal_observer']['mismatch_byte_count']>0 for t in status['tests'] for r in t['reads'])
 result['gpu_cpu_count_mismatching_reads']=sum(not r['gpu_cpu_mismatch_counts_equal'] for t in status['tests']for r in t['reads'])
 result['gpu_cpu_results']=[{'test':t['test_id'],'gpu_first_read_mismatch_bytes':sum(r['gpu_internal_observer']['mismatch_byte_count']for r in t['reads']if r['repeat']==0),'cpu_first_read_mismatch_bytes':sum(r['changed_bytes']for r in t['reads']if r['repeat']==0),'gpu_failing_allocations':sorted({r['allocation_index']for r in t['reads']if r['gpu_internal_observer']['mismatch_byte_count']>0}),'cpu_failing_allocations':sorted({r['allocation_index']for r in t['reads']if r['changed_bytes']>0})}for t in status['tests']]
 output=d/'audit.json';output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='tests'}))
if __name__=='__main__':main()
