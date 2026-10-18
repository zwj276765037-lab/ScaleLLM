import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,os,re
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
A=R/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
P=R/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
O=Path(__file__).resolve().parent
ids={}
def identity(path):
 p=Path(path).resolve();assert p.suffix.lower()!='.dcp'
 b=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4194304),b''):h.update(chunk)
 a=p.stat();assert (b.st_size,b.st_mtime_ns)==(a.st_size,a.st_mtime_ns)
 value=dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest());ids[str(p)]=value;return value
def verify(v):assert identity(v['path'])==v
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
 with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')

native=read(A/'native_start_verified.json');started=read(A/'started.json');inputs=read(A/'input_bindings.json')
assert identity(A/'native_start_verified.json')['sha256']=='60ab709547a73d520a46fcdf9e1807357c8adc3b135fb542d8c9b8c019406a38'
verify(native['started']);verify(native['input_bindings']);verify(native['preparation_manifest']);verify(native['producer'])
assert started['inputs']==native['input_bindings'] and native['actual_native_started']
execution=inputs['attribution']['closeout'];verify(execution)
assert execution['bytes']==19863 and execution['sha256']=='ec12f2c282f002b718aab8dbdda0f4131e8504ea83ba9f65c5ef9733ff3d593e'
binding=read(execution['path']);verify(binding['previous_execution_binding']);verify(binding['resume_authority'])
previous=read(binding['previous_execution_binding']['path'])
for key in ['selected_candidate','base_contract','scope_revision','acquisition_revision','preparation_manifest','controller_decision']:
 assert binding[key]==previous[key],key
assert binding['ordinary_retry']['same_selected_candidate'] and binding['resumed_after_PDU']['same_pre_place_DCP_restart'] and binding['resumed_after_PDU']['no_partial_place_resume']
assert binding['ordinary_retry']['previous_E008_closed'] and not binding['ordinary_retry']['previous_E008_execution_completed']
assert read(binding['resume_authority']['path'])['user_message']=='可以继续了'
assert inputs['attribution']['selected_candidate']==native['selected_candidate']==binding['selected_candidate']
assert native['preparation_manifest']==binding['preparation_manifest'] and native['preparation_manifest']['sha256']=='b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb'
old_closure_path=R/'agent/A007/E008_PDU_resume_review_20261017/AT003_stop_and_resume_input_review.json'
old_closure=read(old_closure_path);identity(old_closure_path)
assert old_closure['terminal_facts']==binding['resumed_after_PDU']['predecessor_terminal']
assert old_closure['stop_closeout']==binding['resumed_after_PDU']['predecessor_pause_closeout']
for key in ['tool_env_preflight','license_probe']:verify(binding['resumed_after_PDU'][key])
environment=read(binding['resumed_after_PDU']['tool_env_preflight']['path'])
license_probe=read(binding['resumed_after_PDU']['license_probe']['path'])
assert environment['prepared_manifest']==binding['preparation_manifest'] and environment['manifest_verify']=='PASS'
assert environment['production']==inputs['frozen_inputs']
assert license_probe['version_exit']==0 and license_probe['expected_Vivado_2025_2_build6299465']
assert license_probe['node_locked_lmdiag_exit']==0 and license_probe['node_locked_lmdiag_completed']
verify(inputs['parent']);parent=read(inputs['parent']['path'])
assert parent['checkpoint']==old_closure['checkpoint_content_identity']==environment['same_C01_parent_DCP']
assert inputs['parent']['sha256']=='9fe26a58f938265c0f8a46060264fbfc966166e93306b92412c4fff628bd7432'

# New archives independently compared with the unchanged accepted source package.
manifest=read(inputs['preparation_manifest']['path']);source_rows=manifest['own_sources']+manifest['reused_sources']
assert inputs['source_bindings']==source_rows and len(source_rows)==39
assert len(native['archived_runtime_sources'])==39
for original,archive in zip(source_rows,native['archived_runtime_sources']):
 verify(archive)
 assert Path(archive['path'])==P/'stage_sources'/Path(original['path']).name
 assert (archive['bytes'],archive['sha256'])==(original['bytes'],original['sha256'])
assert len(list((P/'stage_sources').iterdir()))==39
assert native['production_files_checked']==144 and native['production_inputs_unchanged']
assert old_closure['verified_production_files']==144
# Reuse same-turn independent 144-current-file verification; no redundant functional or source tests.
freeze=read(inputs['frozen_inputs']['freeze']['path'])
prior_ids={x['path']:x for x in old_closure['identities']}
assert len(freeze['files'])==144 and all(prior_ids[v['path']]==v for v in freeze['files'])
assert all(prior_ids[v['path']]==v for v in source_rows)
verify(inputs['stage_inputs']);assert native['stage_inputs']==inputs['stage_inputs']
stage_lines=(P/'stage_inputs.sha256').read_text().splitlines()
stage_new=[];stage_reused=0;dcps=[]
for line in stage_lines:
 sha,path=line.split('  ',1)
 if Path(path).suffix.lower()=='.dcp':dcps.append(dict(path=path,sha256=sha));continue
 if path in prior_ids and prior_ids[path]['sha256']==sha:stage_reused+=1
 else:
  actual=identity(path);assert actual['sha256']==sha;stage_new.append(actual)
assert len(dcps)==1 and dcps[0]['path']==parent['checkpoint']['path'] and dcps[0]['sha256']==parent['checkpoint']['sha256']

old_started=read(R/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/started.json')
resource_keys=['cpu_affinity','nice','max_threads','timeout_seconds','no_output_timeout_seconds','wall_clock_stop_disabled','rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_free_floor_bytes']
assert all(started[k]==old_started[k] for k in resource_keys)
assert started['cpu_affinity']==list(range(8)) and started['nice']==5 and started['max_threads']==8
observations=[]
for row in native['actual_native_process_tree']:
 pid=row['pid'];proc=Path('/proc')/str(pid)
 fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
 assert int(fields[19])==row['start_ticks'] and fields[0]!='Z' and int(fields[16])==5
 affinity=sorted(os.sched_getaffinity(pid));assert affinity==list(range(8))
 command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
 assert command==row['cmdline'] and str(A if pid==started['supervisor_pid'] else P) in command
 observations.append(dict(pid=pid,start_ticks=int(fields[19]),state=fields[0],nice=int(fields[16]),affinity=affinity,ppid=int(fields[1]),pgrp=int(fields[2]),cmdline=command))
assert {x['pid'] for x in observations}=={14547,14590,14609,14680}
assert native['unique_project_native']==[14680] and any(x['pid']==14680 and '/bin/unwrapped/lnx64.o/vivado' in x['cmdline'] for x in observations)
lock=R/'project/hardware/vivado/.m002_eda.lock';inode=str(lock.stat().st_ino)
lockrows=[s for s in Path('/proc/locks').read_text().splitlines() if len(s.split())>5 and s.split()[5].split(':')[-1]==inode]
assert len(lockrows)==1 and lockrows[0].split()[1:5]==['FLOCK','ADVISORY','WRITE',str(started['supervisor_pid'])]

with (P/'vivado.log').open('rb') as f:prefix=f.read(256*1024)
snapshot=O/'native_start_log_observed_prefix.txt'
with snapshot.open('xb') as f:f.write(prefix)
text=prefix.decode(errors='replace')
assert '# Vivado v2025.2 (64-bit)' in text and '# SW Build 6299465 ' in text and '# Process ID         : 14680' in text
rows=[dict(line=i,text=s) for i,s in enumerate(text.splitlines(),1) if any(x in s for x in ['Command: open_checkpoint','Obtained license','license for feature','Command: place_design'])]
latest=None
with (A/'resources.jsonl').open() as f:
 for line in f:
  try:latest=json.loads(line)
  except json.JSONDecodeError:pass
assert latest and latest['rss_bytes']<started['rss_limit_bytes'] and latest['mem_available_bytes']>started['mem_available_floor_bytes'] and latest['disk_free_bytes']>started['disk_free_floor_bytes']
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='ACTUAL_NEW_AT004_NATIVE_RUNNING',verdict='ACCEPT_START_IDENTITY_AND_RESOURCE_BINDING_DELTA',applicability='AT004 C01 resume startup only; actual pre-place and physical results pending',review='A007 independent bounded startup delta',
 native_start_record=identity(A/'native_start_verified.json'),started=identity(A/'started.json'),actual_started_utc=started['started_utc'],
 selected_candidate=binding['selected_candidate'],execution_binding=execution,resume_authority=binding['resume_authority'],accepted_package=native['preparation_manifest'],
 prior_AT003_closure_review=identity(old_closure_path),unchanged_candidate_contracts_and_controller_decision=True,
 new_archived_runtime_sources_verified=39,production144_same_turn_independent_verification_reused=True,
 stage_inputs=dict(artifact=inputs['stage_inputs'],new_identity_checks=len(stage_new),reused_same_turn_identity_checks=stage_reused,DCP_metadata_only=dcps),
 parent_record=inputs['parent'],checkpoint_content_identity=parent['checkpoint'],DCP_identity_attribution='A006 actual post-reboot hash bound by preflight/parent; A007 no DCP content read/hash',
 process_observations=observations,read_only_proc_lock_rows=lockrows,engineering_unique_project_native=native['unique_project_native'],
 unique_scope_provenance='A006 producer inspected: exact unwrapped vivado executable plus workspace path; no A007 whole-process scan or lock probe',
 resource_profile={k:started[k] for k in resource_keys},resource_sample={k:latest[k] for k in ['utc','rss_bytes','mem_available_bytes','disk_free_bytes']},
 log_prefix=identity(snapshot),log_selected_rows=rows,license_preflight=license_probe,
 formal_signoff=False,limits=['Native startup only, no pre-place/place/physopt/route completion inferred.','lmstat nonserver diagnostics not equivalent to actual Implementation feature checkout; native stage must obtain required license.','No repeated26/9CPU tests or AT003 cut/timing/POST audit; accepted same-version evidence reused within scope.','No DCP access, EDA invocation, process signal, lock acquisition, production edits or new approval gate.'],
 identities=list(ids.values()),audit_program=identity(__file__))
save(O/'start_delta_review.json',result)
md='''# AT004 PDU恢复启动独立增量审核

execution：真实新AT原生运行；verdict：启动身份与资源绑定接受；applicability：仅AT004/C01恢复启动；review：完成。

实际started为2026-10-17 09:23:05.136988Z。supervisor14547/69484、leader14590/70772、loader14609/70775、native14680/70786四身份独立核实，全部CPU0–7/nice5；只读`/proc/locks`确认项目锁由监督器持有。max8及192GiB/48GiB30s/30GiB、正常无墙钟/无输出强停保持。

新execution binding `ec12f2c2…`精确关联用户恢复、已闭合AT003和既有C01选择；b9dc包与39份新归档源全量身份一致。144生产输入复用同轮独立实测核验。父记录字节与AT003相同，父DCP仍8451b2…，未继承中途placement。DCP内容身份由工程实算，审核未读取或哈希DCP。

Vivado2025.2/build6299465真实native已确认；许可预检保留node-locked诊断口径，实际阶段仍须工具checkout。未重复已审26/9测试、cut/timing或完整POST。新AT当前pre-place及place/physopt/route结果尚待各自真实闭合。

证据见`start_delta_review.json`；无新审批门，A006按原合同连续执行。
'''
with (O/'start_delta_review.md').open('x') as f:f.write(md)
print(json.dumps(dict(review=identity(O/'start_delta_review.json'),human=identity(O/'start_delta_review.md'),actual_started_utc=started['started_utc'],processes=[dict(pid=x['pid'],start_ticks=x['start_ticks']) for x in observations]),ensure_ascii=False))
