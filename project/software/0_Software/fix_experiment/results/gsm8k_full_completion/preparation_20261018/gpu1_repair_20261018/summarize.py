from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
root=Path(__file__).resolve().parent
now=datetime.now(timezone.utc).isoformat();attempts=[]
for name in ['AT001','AT002','AT003']:
 p=root/name
 if not(p/'status.json').exists():attempts.append({'attempt':name,'execution_state':'prepared_not_launched'});continue
 s=json.loads((p/'status.json').read_text());lib=json.loads((p/'actual_cuda_library.json').read_text())if(p/'actual_cuda_library.json').exists()else None
 row={'attempt':name,'execution_state':s['execution_state'],'stage':s['stage'],'pid':s['pid'],'started_at':s['started_at'],'ended_at':s.get('ended_at'),'source_sha256':s['source_sha256'],'status_sha256':hashlib.sha256((p/'status.json').read_bytes()).hexdigest(),'library':lib['mapped_libraries']if lib else None,'verdict':s.get('verdict'),'gpu_uuid_actual':s.get('gpu_uuid_actual'),'cpu_affinity':s['cpu_affinity'],'cleanup_completed_at':s.get('cleanup_completed_at'),'tests':[]}
 for t in s['tests']:
  first=[r for r in t['reads']if r['repeat']==0]
  x={'test_id':t['test_id'],'complete':bool(t.get('ended_at')),'whole_chunk_reads':len(t['reads']),'bad_bytes_first_read_only':sum(r['changed_bytes']for r in first),'failing_allocations':sorted({r['allocation_index']for r in t['reads']if r['changed_bytes']}),'set_bit_bytes_first_read':sum(r.get('set_bit_bytes',0)for r in first),'cleared_bit_bytes_first_read':sum(r.get('cleared_bit_bytes',0)for r in first),'changed_bytes_between_repeated_reads':sum(r.get('changed_bytes_from_previous_read',0)for r in t['reads'])}
  if first and 'gpu_internal_observer'in first[0]:x.update(gpu_internal_bad_bytes_first_read=sum(r['gpu_internal_observer']['mismatch_byte_count']for r in first),gpu_internal_failing_allocations=sorted({r['allocation_index']for r in t['reads']if r['gpu_internal_observer']['mismatch_byte_count']}),gpu_cpu_count_disagreeing_reads=sum(not r['gpu_cpu_mismatch_counts_equal']for r in t['reads']))
  row['tests'].append(x)
 if 'gpu_observer'in s:row['native_observer_self_tests_passed']=all(t['passed']for t in s['gpu_observer']['self_tests'])and len(s['gpu_observer']['self_tests'])==2
 attempts.append(row)
comparison={'schema':'scalellm_gpu1_repair_comparison_v1','updated_at':now,'owner':'A012 /root/gpu1_repair','attempts':attempts,'counting_convention':'Bad byte counts use first read only per allocation and pattern, never add duplicate read count. Repeat-read changes are separate. Different patterns are separate observations, not a single union of bad physical cells.','scope':'Raw GPU1 synthetic byte integrity only; no model/production qualification. CUDA virtual pointers are not fixed physical pages.'};(root/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
lines=['# GPU1 repair investigation — results','',f'Updated {now}. Engineering self-audit evidence; independent review separately owned.','',comparison['counting_convention'],'']
for a in attempts:
 lines.extend([f"## {a['attempt']}",'',f"execution_state: {a['execution_state']}." ,''])
 if not a.get('tests'):continue
 lines.extend(['| Pattern | Complete reads | Wrong bytes, first read | Failed allocations | Set / clear bytes | Repeated-read changes |','| --- | ---: | ---: | --- | ---: | ---: |'])
 for t in a['tests']:lines.append(f"| {t['test_id']} | {t['whole_chunk_reads']} | {t['bad_bytes_first_read_only']} | {','.join(map(str,t['failing_allocations'])) or 'none'} | {t['set_bit_bytes_first_read']} / {t['cleared_bit_bytes_first_read']} | {t['changed_bytes_between_repeated_reads']} |")
 lines.extend(['',f"Evidence: [{a['attempt']} raw status](../{a['attempt']}/status.json), [launch](../{a['attempt']}/launch.json), [actual CUDA library](../{a['attempt']}/actual_cuda_library.json)." ,''])
 if a['attempt']=='AT003':lines.extend(['GPU-internal observer controls passed: '+str(a.get('native_observer_self_tests_passed'))+'.',json.dumps([t for t in a['tests']if'gpu_internal_bad_bytes_first_read'in t]),''])
lines.extend(['Current causal boundary: raw CUDA errors do not require model loading or inference. A matching user-space CUDA library alone has not removed the observed errors. Device memset errors exclude an H2D-only explanation. AT003 completed validated native GPU observer controls and all320GPU/CPU count, direction, first coordinate and value comparisons match. GPU-internal reads see212992wrong bytes on device00 and0onff, excluding a pure full-buffer D2H-only explanation for those faults. Physical DRAM/controller/kernel-driver causes remain distinct.','', 'No production repair release. No reset, reboot, system driver install or GPU0 experiment run by A012. Maintenance steps are reviewable in [maintenance_candidate.md](../maintenance_candidate.md).'])
(root/'experiment_results/summary.md').write_text('\n'.join(lines)+'\n')
active=next((a for a in reversed(attempts)if a['execution_state']=='running'),None)
if active:
 state='running';task=active['attempt'];stage=active['stage'];nextstep='Complete current finite sequence naturally; conditionally run prepared native observer if matched-library comparison fails.'
else:
 state='completed'if all(a['execution_state']=='completed'for a in attempts)else 'between_attempts';task='GPU1 finite diagnostic evidence';stage='terminal audit / integration';nextstep='Publish evidence, independent review, controller maintenance decision; no further scans or production qualification.'
status=['# GPU1 repair investigation — status','',f'Updated {now}; owner A012 /root/gpu1_repair.','',f'- execution_state: {state}; current task: {task}; stage: {stage}.','- verdict: GPU-visible byte preservation failed with system and matching libcuda; no verified repair. AT003 rules out pure full-buffer D2H-only faults for the observed byte errors.','- applicability: GPU1 raw synthetic byte integrity, CPU18,19, 20GiB data allocation; no model load.','- review: engineering self-audit per attempt, independent review pending.','- repair_state: blocked_on_maintenance_decision. Last inventory shows Xorg on both GPUs; reset/display-service/system changes require separate controller handling and fresh eligibility checks; none executed here.',f'- next step: {nextstep}','', 'Original GPU1 flock and per-step ≥8GiB GPU free / ≥80GiB host available checks retained. Read actual [comparison](../comparison.json), each launch/terminal/status and actual-library receipt for version boundaries.']
(root/'experiment_status/summary.md').write_text('\n'.join(status)+'\n');print(json.dumps({'updated_at':now,'execution_state':state,'current_task':task,'attempts':[{'attempt':a['attempt'],'execution_state':a['execution_state'],'readbacks':sum(t['whole_chunk_reads']for t in a.get('tests',[]))}for a in attempts]}))
