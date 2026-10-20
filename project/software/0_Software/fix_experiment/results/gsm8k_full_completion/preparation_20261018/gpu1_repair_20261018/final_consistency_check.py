from pathlib import Path
from datetime import datetime,timezone
import fcntl,hashlib,json,os
root=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for name in ['AT001','AT002','AT003']:
 p=root/name;s=json.loads((p/'status.json').read_text());l=json.loads((p/'launch.json').read_text());t=json.loads((p/'terminal.json').read_text());a=json.loads((p/'audit.json').read_text());lib=json.loads((p/'actual_cuda_library.json').read_text())
 assert s['execution_state']==t['execution_state']=='completed' and t['exit_code']==0 and t['stop_reason']is None
 assert s['pid']==l['worker_pid']==t['worker_pid'] and not Path(f"/proc/{s['pid']}").exists()
 assert s['source_sha256']==sha(p/'source_snapshot.py')==l['source_sha256']==t['source_sha256']
 assert a['status_sha256']==sha(p/'status.json') and a['launch_sha256']==sha(p/'launch.json') and a['terminal_sha256']==sha(p/'terminal.json')
 assert s['gpu_uuid_actual']=='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533' and s['cpu_affinity']==[18,19]
 assert s['allocated_bytes']==20*(1<<30) and len(s['allocations'])==80 and len({r['ptr']for r in s['allocations']})==80
 assert min(s['gpu_memory_after_allocations']['free_bytes'],s['gpu_memory_before_free']['free_bytes'])>=8*(1<<30)
 assert s['host_available_start_bytes']>=80*(1<<30) and s['host_available_end_bytes']>=80*(1<<30)
 assert all(c==0 for c in s['allocation_free_return_codes']) and s['context_destroy_return_code']==0 and s['lock_released_at']
 assert datetime.fromisoformat(s['cleanup_completed_at'])<=datetime.fromisoformat(t['ended_at'])
 expected='dcdf334aeb177c95b3385b797c9b871d03a287895713c6d107f79096b0985aa9'if name=='AT001'else'3a3cf81c03a39008b3da4320bbc2cc8194dcfe91e8eef7c05dfc46febe2d1aac'
 assert len(lib['mapped_libraries'])==1 and lib['mapped_libraries'][0]['sha256']==expected and sha(lib['mapped_libraries'][0]['path'])==expected and '580.159.03'in lib['kernel_driver_version']
 if name!='AT001':assert lib['actual_identity_verified']
 if name=='AT003':
  controls=s['gpu_observer']['self_tests'];assert len(controls)==2
  for ctrl in controls:
   assert ctrl['passed']and ctrl['clean']['small_result_words']==[0,2**64-1,0,0,2**64-1]
   e=[1,12345,1,0,255]if ctrl['expected_byte']==0 else[1,12345,0,1,0]
   assert ctrl['injected']['small_result_words']==e
  for test in s['tests']:
   for r in test['reads']:
    g=r['gpu_internal_observer'];assert g['small_result_reads_equal']and g['mismatch_byte_count']==r['changed_bytes']
    assert g['set_bit_byte_count']==r.get('set_bit_bytes',0)and g['cleared_bit_byte_count']==r.get('cleared_bit_bytes',0)
    if r['changed_bytes']:assert g['first_mismatch_byte_offset']==r['first_32_byte_offsets'][0]and g['first_observed_byte']==r['first_32_observed'][0]
 rows.append({'attempt':name,'pid':s['pid'],'worker_absent':True,'source_sha256':s['source_sha256'],'status_sha256':sha(p/'status.json'),'audit_sha256':sha(p/'audit.json'),'mapped_cuda_library_sha256':expected,'patterns':len(s['tests']),'whole_chunk_reads':sum(len(x['reads'])for x in s['tests']),'resource_cleanup_verified':True})
lockpath=Path(json.loads((root/'AT003/status.json').read_text())['lock_path'])
with lockpath.open('r+')as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
record={'schema':'scalellm_gpu1_repair_final_consistency_v1','created_at':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(__file__),'CPU_only':True,'cpu_affinity':sorted(os.sched_getaffinity(0)),'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'attempts':rows,'AT003_gpu_cpu_count_direction_first_coordinate_value_all_equal':True,'gpu1_resource_flock_available':True,'execution_state':'completed','production_repair_verified':False,'causal_boundary':'GPU-visible byte corruption persists with matched libcuda. Pure H2D-only and pure full-buffer D2H-only explanations excluded by device fill and native observer controls. Physical device/controller/kernel-driver root cause unresolved; maintenance required for further repair attempts.','independent_review':'separately owned, not certified by self-audit'}
(root/'final_consistency_check.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
