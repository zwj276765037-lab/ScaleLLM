import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
A=R/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation'
P=R/'project/hardware/vivado/reports/m002_E008_R001_AT003_C01_physical_xdc_fix_full_implementation'
O=Path(__file__).resolve().parent
ids={}
def identity(p):
 p=Path(p).resolve();assert p.suffix.lower()!='.dcp'
 b=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for v in iter(lambda:f.read(4194304),b''):h.update(v)
 a=p.stat();assert (b.st_size,b.st_mtime_ns)==(a.st_size,a.st_mtime_ns)
 v=dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest());ids[str(p)]=v;return v
def read(p):return json.loads(Path(p).read_text())
def verify(v):assert identity(v['path'])==v
facts=read(A/'terminal_facts.json');summary=read(A/'terminal_summary.json');status=read(A/'status.json');close=read(A/'user_PDU_stop_closeout_20261017.json')
assert identity(A/'terminal_facts.json')['sha256']=='ed000baf22e8e16cd48dbe5f1c950bdb7dfd4c0988cf459dffb2534ca7a5a798'
for value in close['artifacts']:verify(value)
verify(close['authority'])
assert facts['checks']==summary['checks']==close['all_14_terminal_closure_checks'] and len(facts['checks'])==14 and all(facts['checks'].values())
assert status['native_exit_code']==facts['native_exit_code']==summary['native_exit_code']==-15
assert status['exit_code']==facts['supervisor_exit_code']==summary['supervisor_exit_code']==125
assert status['stop_reason']=='KeyboardInterrupt:signal 15' and status['owned_survivors']==[]
assert close['classification']=='USER_REQUESTED_PDU_SHUTDOWN_PAUSE' and close['method_verdict']=='unassessed'
assert not facts['engineering_execution_verified'] and not facts['formal_signoff'] and not facts['closed_phases']
assert status['cleanup_was_required'] and not status['native_natural_terminal_observed'] and not status['post_integrity_error']
assert read(A/'user_PDU_supervisor_signal_sent_20261017.json')==close['actual_signal_sent']
assert datetime.fromisoformat(close['actual_signal_sent']['sent_utc'])<datetime.fromisoformat(status['ended_utc'])
assert close['current_E008_DCPs']==[] and list(P.glob('*.dcp'))==[]
for name in ['place_command_result.txt','physopt_command_result.txt','route_command_result.txt']:assert not (P/name).exists()
verify(facts['preparation_manifest']);assert facts['preparation_manifest']['sha256']=='b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb'
for key in ['status','input_bindings','base_contract','scope_revision','stage_manifest','physical_evidence_identity','producer']:verify(facts[key])
binding=read(A/'input_bindings.json');verify(binding['parent'])
assert read(binding['parent']['path'])['checkpoint']==close['same_C01_restart_checkpoint']
verify(binding['frozen_inputs']['freeze']);freeze=read(binding['frozen_inputs']['freeze']['path'])
assert len(freeze['files'])==144 and status['frozen_inputs_after']==binding['frozen_inputs']
for v in freeze['files']:verify(v)
for v in binding['source_bindings']:
 verify(v);archive=identity(P/'stage_sources'/Path(v['path']).name)
 assert (archive['bytes'],archive['sha256'])==(v['bytes'],v['sha256'])
stage_checked=[];stage_DCP_metadata_only=[]
for line in (P/'stage_inputs.sha256').read_text().splitlines():
 sha,path=line.split('  ',1)
 if Path(path).suffix.lower()=='.dcp':stage_DCP_metadata_only.append(dict(path=path,sha256=sha));continue
 value=identity(path);assert value['sha256']==sha;stage_checked.append(value)
resources=[json.loads(x) for x in (A/'resources.jsonl').read_text().splitlines()]
values=dict(samples=len(resources),first=resources[0]['utc'],last=resources[-1]['utc'],peak_tree_RSS_bytes=max(x['rss_bytes'] for x in resources),minimum_MemAvailable_bytes=min(x['mem_available_bytes'] for x in resources),minimum_disk_free_bytes=min(x['disk_free_bytes'] for x in resources),maximum_sample_gap_seconds=max((datetime.fromisoformat(b['utc'])-datetime.fromisoformat(a['utc'])).total_seconds() for a,b in zip(resources,resources[1:])))
assert values==facts['resources']
assert values['peak_tree_RSS_bytes']==status['max_tree_rss_bytes'] and values['minimum_MemAvailable_bytes']==status['minimum_mem_available_bytes'] and values['minimum_disk_free_bytes']==status['minimum_disk_free_bytes']
processes=[]
for v in facts['processes']:
 path=Path('/proc')/str(v['pid'])/'stat'
 try:fields=path.read_text().rsplit(')',1)[1].split(); current=int(fields[19]);state=fields[0]
 except FileNotFoundError:current=None;state='ABSENT'
 same=current==v['expected_start_ticks'];assert not same
 processes.append(dict(**v,current_start_ticks=current,current_state=state,independent_original_identity_absent=True))
lock=Path(facts['lane_lock_probe']['path']);ino=str(lock.stat().st_ino)
lockrows=[x for x in Path('/proc/locks').read_text().splitlines() if len(x.split())>5 and x.split()[5].split(':')[-1]==ino]
assert not any(str(p['pid']) in x.split() for p in facts['processes'] for x in lockrows)
resume=R/'.research-agent/decision_inputs/E008_user_PDU_resume_20261017.json';new=read(resume)
assert new['user_message']=='可以继续了' and new['authorization_active'] and new['selected_candidate']=='C01'
assert new['prepared_manifest_sha256']==facts['preparation_manifest']['sha256'] and new['selected_root']==facts['selected_candidate']['root']
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='COMPLETED',verdict='ACCEPT_PRIOR_USER_STOP_CLOSURE_AND_UNCHANGED_RESTART_INPUTS',applicability='AT003 closed stop only, plus resume authorization; no new AT/native started claim',review='A007 independent bounded review',resume_authority=identity(resume),terminal_facts=identity(A/'terminal_facts.json'),stop_closeout=identity(A/'user_PDU_stop_closeout_20261017.json'),native_exit_code=-15,supervisor_exit_code=125,terminal_reason='explicit user PDU maintenance stop; method unassessed',closure_checks=facts['checks'],resources_recomputed=values,old_processes=processes,current_lock_rows=lockrows,current_lock_observation_scope='Read-only /proc/locks, original owner absent; historic lock release probe attributed to A006; no acquisition/probe by A007',verified_production_files=144,verified_source_bindings=len(binding['source_bindings']),verified_non_DCP_stage_inputs=len(stage_checked),DCP_metadata_only=stage_DCP_metadata_only,checkpoint_content_identity=close['same_C01_restart_checkpoint'],reviewer_DCP_access=False,new_E008_DCPs=[],old_place_physopt_route_completed=False,identities=list(ids.values()),prior_stage_reviews_reused_without_full_replay=[identity(R/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_directed_cut_timing_review.json'),identity(R/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/restored_pre_place_global_review.json')],observer_exits='A006 recorded actual tool-session exit0 for65187/12141; historical receipts retained, not reobserved by A007',audit_program=identity(__file__))
p=O/'AT003_stop_and_resume_input_review.json'
with p.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(dict(review=identity(p),old_process_count=len(processes),production=144,source_count=len(binding['source_bindings']),non_DCP_stage=len(stage_checked),DCP_metadata_count=len(stage_DCP_metadata_only))))
