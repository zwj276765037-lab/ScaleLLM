#!/usr/bin/env python3
"""A007 independently replay non-DCP terminal evidence and read-only owner state."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('DCP content access forbidden')
sys.addaudithook(guard)
import csv,hashlib,json,os,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
checks={}
def identity(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';a=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    z=p.stat();assert (a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns)
    v=dict(path=str(p),bytes=z.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):assert identity(v['path'])==v
def read(p):identity(p);return json.loads(Path(p).read_text())
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def rows(p):
    identity(p)
    with Path(p).open() as f:return list(csv.DictReader(f,delimiter='\t'))
facts=read(AT/'terminal_facts.json');assert identity(AT/'terminal_facts.json')['sha256']=='3475d4df05fff44410f0c99d19ca7087ba43ee330d39e9227491de195c846f7c'
summary=read(AT/'terminal_summary.json');verify(summary['facts']);assert {k:v for k,v in summary.items() if k!='facts'}=={k:facts[k] for k in summary if k!='facts'}
assert facts['closure_verified'] and len(facts['checks'])==14 and all(facts['checks'].values())
assert facts['engineering_execution_verified'] is False
for k in ['status','input_bindings','preparation_manifest','base_contract','scope_revision','stage_manifest','physical_evidence_identity','producer']:verify(facts[k])
status=read(facts['status']['path']);inputs=read(facts['input_bindings']['path']);started=read(AT/'started.json')
assert started['inputs']==status['inputs']==facts['input_bindings']
assert status['native_exit_code']==status['exit_code']==facts['native_exit_code']==facts['supervisor_exit_code']==1
assert status['owned_survivors']==[] and status['native_natural_terminal_observed'] and status['stop_reason'] is None and not status['cleanup_was_required']
assert status['frozen_inputs_after']==inputs['frozen_inputs'] and status['post_integrity_error'] is None
verify(inputs['frozen_inputs']['freeze']);freeze=read(inputs['frozen_inputs']['freeze']['path'])
assert len(freeze['files'])==144
for row in freeze['files']:verify(row)
verify(inputs['preparation_manifest']);manifest=read(inputs['preparation_manifest']['path'])
source_counts={}
for key in ['own_sources','reused_sources','CPU_checks','documentation']:
    source_counts[key]=len(manifest.get(key,[]))
    for row in manifest.get(key,[]):verify(row)
assert len(inputs['source_bindings'])==39
for row in inputs['source_bindings']:verify(row)
verify(inputs['contract']);verify(inputs['scope_revision']);assert facts['base_contract']==inputs['contract'] and facts['scope_revision']==inputs['scope_revision']
attr=inputs['attribution'];verify(attr['closeout']);closeout=read(attr['closeout']['path'])
for row in [*attr['terminal_statuses'],closeout['terminal_status'],*closeout['evidence']]:verify(row)
assert facts['selected_candidate']==attr['selected_candidate']
stage_entries=[];dcp_manifest=[]
for line in Path(facts['stage_manifest']['path']).read_text().splitlines():
    sha,p=line.split(None,1);p=Path(p.strip());assert re.fullmatch('[0-9a-f]{64}',sha)
    if p.suffix.lower()=='.dcp':dcp_manifest.append(dict(path=str(p),sha256=sha,bytes=p.stat().st_size));continue
    actual=identity(p);assert actual['sha256']==sha;stage_entries.append(actual)
assert len(dcp_manifest)==1 and facts['stage_manifest']==inputs['stage_inputs']

# Bind engineering independent DCP hashes; never read DCP content as reviewer.
failed=read(AT/'failed_route_terminal_facts.json');assert identity(AT/'failed_route_terminal_facts.json')['sha256']=='cf03a19dbcc734b845575cf3d24e084f98e0cae99c338b04e1f4e1ea3d8aa122'
failed_summary=read(AT/'failed_route_terminal_summary.json');verify(failed_summary['facts'])
assert {k:v for k,v in failed_summary.items() if k!='facts'}=={k:failed[k] for k in failed_summary if k!='facts'}
verify(failed['production_144_and_full_closure']);verify(failed['observer_closure']);verify(failed['producer']);verify(inputs['parent'])
parent=read(inputs['parent']['path']);assert parent['checkpoint']==failed['parent_checkpoint_independently_unchanged']==dcp_manifest[0]
assert Path(parent['checkpoint']['path']).stat().st_size==parent['checkpoint']['bytes']==396068466
assert parent['checkpoint']['sha256']=='8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f'
physical=read(facts['physical_evidence_identity']['path']);assert physical==facts['physical_evidence']
assert failed['failed_diagnostic_artifacts_all_independently_hashed']==physical['failed_route_artifacts']
for row in failed['failed_diagnostic_artifacts_all_independently_hashed']:
    if row['path'].endswith('.dcp'):
        assert Path(row['path']).stat().st_size==row['bytes']==765705446 and row==failed['failed_checkpoint']
        assert row['sha256']=='51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21'
    else:verify(row)
producer=Path(failed['producer']['path']).read_text()
assert "parent = identity(parent_record['checkpoint']['path'])" in producer and "failed_artifacts = [identity(row['path']) for row in physical['failed_route_artifacts']]" in producer
archives=failed['archived_sources'];assert len(archives)==failed['archived_sources_count']==39
for row in archives:verify(row)
assert {r['path'] for r in archives}=={str(p) for p in (RPT/'stage_sources').iterdir() if p.is_file()}
archive_manifest=RPT/'archived_sources.sha256';identity(archive_manifest)
assert {p.strip():sha for sha,p in (line.split(None,1) for line in archive_manifest.read_text().splitlines())}=={r['path']:r['sha256'] for r in archives}
assert failed['original_source_bindings_count']==39 and failed['original_source_bindings_all_unchanged']
for row in failed['artifact_identities']:verify(row)

# Replay complete resource samples, independent of truncated observer terminal delivery.
resourcepath=AT/'resources.jsonl';resourceid=identity(resourcepath)
samples=[json.loads(line) for line in resourcepath.read_text().splitlines()]
times=[datetime.fromisoformat(r['utc']) for r in samples]
assert all(a<=b for a,b in zip(times,times[1:]))
resources=dict(samples=len(samples),first=samples[0]['utc'],last=samples[-1]['utc'],peak_tree_RSS_bytes=max(r['rss_bytes'] for r in samples),minimum_MemAvailable_bytes=min(r['mem_available_bytes'] for r in samples),minimum_disk_free_bytes=min(r['disk_free_bytes'] for r in samples),maximum_sample_gap_seconds=max((b-a).total_seconds() for a,b in zip(times,times[1:])))
assert resources==facts['resources']==summary['resources'] and len(samples)==8499
assert resources['peak_tree_RSS_bytes']==status['max_tree_rss_bytes']<status['rss_limit_bytes']
assert resources['minimum_MemAvailable_bytes']==status['minimum_mem_available_bytes']>status['mem_available_floor_bytes']
assert resources['minimum_disk_free_bytes']==status['minimum_disk_free_bytes']>status['disk_free_floor_bytes']
assert datetime.fromisoformat(status['started_utc'])<=times[0]<=times[-1]<datetime.fromisoformat(status['ended_utc'])

# Read-only proc/stat and proc/locks inspection: no signals, flock or lock-file open.
registered={int(pid):tick for pid,tick in status['tracked_identities'].items()}
for role in ['supervisor','leader']:registered[started[role+'_pid']]=started[role+'_start_ticks']
assert len(registered)==19 and {r['pid']:r['expected_start_ticks'] for r in facts['processes']}==registered
now_processes=[]
for pid,tick in sorted(registered.items()):
    v=dict(pid=pid,expected_start_ticks=tick,original_identity_live=False)
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();v.update(current_start_ticks=int(fields[19]),state=fields[0]);v['original_identity_live']=int(fields[19])==tick and fields[0]!='Z'
    except FileNotFoundError:pass
    now_processes.append(v)
assert not any(r['original_identity_live'] for r in now_processes)
lockpath=Path(facts['lane_lock_probe']['path']);stat=lockpath.stat();matching_locks=[]
for line in Path('/proc/locks').read_text().splitlines():
    for dev_major,dev_minor,inode in re.findall(r'([0-9a-fA-F]+):([0-9a-fA-F]+):(\d+)',line):
        if (int(dev_major,16),int(dev_minor,16),int(inode))==(os.major(stat.st_dev),os.minor(stat.st_dev),stat.st_ino):matching_locks.append(line)
assert not matching_locks and facts['lane_lock_probe']['free'] is True

observer=read(AT/'observer_terminal_facts.json');assert identity(AT/'observer_terminal_facts.json')['sha256']=='38dc8a69d07b760876c26992002c5e6d208d43a7766276a962e5b1504d02b4d9'
receipt_id=observer['actual_tool_receipts'];receiptpath=ROOT/receipt_id['path'];rid=identity(receiptpath)
assert {k:rid[k] for k in ['bytes','sha256']}=={k:receipt_id[k] for k in ['bytes','sha256']}
receipts=read(receiptpath);deliveries=receipts['actual_observer_tool_closures'];assert len(deliveries)==2
assert {r['session_id'] for r in deliveries}=={42865,73883}
assert all(r['tool_exit_code']==0 and not r['running_session_returned'] for r in deliveries)
assert observer['both_observers_exit0'] and observer['observer_processes_absent'] and observer['exact_observer_script_argv_processes_live']==[]
resource_observer=next(r for r in deliveries if r['observer']=='resource_observer')
auto_observer=next(r for r in deliveries if r['observer']=='automatic_index_phase_capture')
terminal=resource_observer['last_parsed_observation']['terminal']
assert terminal==dict(ended_utc=status['ended_utc'],exit_code=1,native_exit_code=1,stop_reason=None,owned_survivors=[])
assert resource_observer['last_parsed_observation']['utc']==resources['last']
assert auto_observer['last_parsed_observation']['supervisor_terminal'] is True and auto_observer['last_parsed_observation']['observed_utc']=='2026-10-17T21:18:34.992595+00:00'

# Cross-check engineer failed metrics against the independently completed native review.
native=read(OUT/'route_failed_native_terminal_review.json');assert identity(OUT/'route_failed_native_terminal_review.json')['sha256']=='f388b6510d3627aa9addbc4ef503a9ec3bc18be9ae4f8c67eb9ab22c747de0ca'
assert failed['failure_graph_global_timing']==native['diagnostic_timing']['current'] and failed['failed_graph_candidate_compliance']==native['candidate_compliance']
assert failed['final_native_failure_counts']=={k:native['current_native'][k] for k in ['node_overlaps','congestion_failed_signals']}
assert failed['failure_capture_receipts']==native['native_capture_receipts']
assert failed['native_route_original_failure_utc']==native['time_boundaries']['native_error_caught_utc']
native_excerpt=Path(failed['native_failure_excerpt']['path']);verify(failed['native_failure_excerpt']);log=(RPT/'vivado.log').read_text().splitlines()
assert native_excerpt.read_text()=='\n'.join(log[failed['native_excerpt_first_line']-1:failed['native_excerpt_last_line']])+'\n'
duration=re.search(r'elapsed = (\d+):(\d+):(\d+)',log[failed['native_excerpt_last_line']-1]);assert sum(int(v)*m for v,m in zip(duration.groups(),[3600,60,1]))==failed['native_route_reported_elapsed_seconds']==13872
timingrows=rows(RPT/'candidate_scoped_timing_route_failed.tsv');groups={}
for direction in ['INGRESS','EGRESS']:
    for delay in ['max','min']:
        rs=[r for r in timingrows if r['direction']==direction and r['delay_type']==delay];assert len(rs)==16
        groups[direction+'_'+delay]=dict(paths=16,worst_slack_ns=min(float(r['SLACK']) for r in rs),queried_LOAD_pins=int(rs[0]['queried_boundary_pins']))
assert groups==failed['failed_graph_bounded_through_LOAD_timing']
recomputed=dict(no_survivors=not status['owned_survivors'],no_original_live=not any(r['original_identity_live'] for r in now_processes),lane_released=not matching_locks and facts['lane_lock_probe']['free'],production_144_unchanged=True,wrapper_after_freeze_agrees=status['frozen_inputs_after']==inputs['frozen_inputs'],preparation_manifest_unchanged=True,all_bound_source_CPU_and_docs_unchanged=True,stage_manifest_unchanged=True,stage_manifest_all_actual_input_hashes_match=True,source_contract_unchanged=True,scope_revision_unchanged=True,attribution_selection_evidence_unchanged=True,no_post_integrity_error=status['post_integrity_error'] is None,resource_extrema_agree=True)
assert recomputed==facts['checks']
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='TERMINAL_INPUT_PROCESS_RESOURCE_AND_OBSERVER_CLOSURE_REVIEW_COMPLETED',verdict='ACCEPT_14_CLOSURE_CHECKS_WITH_EXPLICIT_ENGINEERING_DCP_HASH_AND_LOCK_PROBE_ATTRIBUTION; LEGAL_ROUTING_FAIL_AND_FORMAL_SAFETY_OPEN_RETAINED',applicability='AT004 natural failed attempt closure only; no implementation success, new run or global acceptance',review='INDEPENDENT_TERMINAL_CLOSURE_COMPLETE',terminal_facts=identity(AT/'terminal_facts.json'),terminal_summary=identity(AT/'terminal_summary.json'),failed_diagnostic_facts=identity(AT/'failed_route_terminal_facts.json'),failed_diagnostic_summary=identity(AT/'failed_route_terminal_summary.json'),accepted_native_failure_review=identity(OUT/'route_failed_native_terminal_review.json'),recomputed_closure_checks=recomputed,production_input_files_rehashed=144,preparation_source_counts=source_counts,original_source_bindings_rehashed=39,stage_manifest_non_DCP_files_rehashed=len(stage_entries),stage_manifest_DCP_metadata_and_binding=dcp_manifest,archived_stage_sources_rehashed=39,parent_DCP=dict(identity=parent['checkpoint'],content_hash_attribution='A006 capture_failed_route_terminal_producer.py independently rehashed; A007 verifies metadata size/bindings only'),failed_DCP=dict(identity=failed['failed_checkpoint'],content_hash_attribution='A006 independent terminal rehash agrees with runtime evidence; A007 verifies metadata size/bindings only'),resources=resources,resource_history=resourceid,resources_GiB=dict(peak_RSS=resources['peak_tree_RSS_bytes']/2**30,minimum_MemAvailable=resources['minimum_MemAvailable_bytes']/2**30,minimum_disk_free=resources['minimum_disk_free_bytes']/2**30),current_original_owner_identity_readonly_checks=now_processes,lock_closure=dict(engineering_nonblocking_exclusive_probe=facts['lane_lock_probe'],reviewer_readonly_inode=dict(device_major=os.major(stat.st_dev),device_minor=os.minor(stat.st_dev),inode=stat.st_ino),reviewer_proc_locks_matching_rows=matching_locks,no_lock_acquire_release_by_reviewer=True),observer_facts=identity(AT/'observer_terminal_facts.json'),observer_tool_receipts=rid,observer_receipt_scope='Actual exit0/session-drain receipts archived by A006; terminal fields cross-checked against raw supervisor/resource history. Truncated historical delivery not treated as complete resource trace. A007 did not re-drain sessions.',engineering_execution_verified_false_explanation='Producer combines closure with native_zero/supervisor_zero/three_success_phases; false correctly records lack of successful implementation, not missing verification of natural failure.',native_reported_route_seconds=13872,epoch_boundary_elapsed_seconds=13871,elapsed_scope='Native displayed hh:mm:ss versus integer recorded boundary epochs differ by1s; neither includes1152s diagnostic captures or later failed-route locality.',bounded_failure_table_crosscheck=groups,bounded_table_review_limit='Recomputed64 archived TSV row counts/slack minima, not replay of every native path/query or full cut coverage.',limits=['Natural native1/supervisor1 is a completed failed attempt. Fourteen closure checks and observer exit0 do not establish a legal route, successful global POST, final bus-skew coverage or formal safety.','DCP content identities are explicitly engineering-attributed, not independently hashed/read by A007.','The exact recorded19 original PID-start identities are absent; no process or lock control was performed.','Prior place/physopt reviews remain accepted without re-running them; prior full-route coverage gaps remain OPEN.','No EDA/retry/newAT, production/engineering edits, copied raw-evidence replacement or background-monitoring claim.'],all_identity_checks=list(checks.values()),audit_program=identity(__file__))
dest=OUT/'route_failed_terminal_closure_review.json';save(dest,out)
human=OUT/'route_failed_terminal_closure_review.md'
with human.open('x') as f:f.write('''# AT004 自然失败后的收尾独立审核

execution：终态输入、原进程、资源与观察器证据审核完成。verdict：接受 14 项收尾检查；合法布线仍 FAIL、正式安全仍 OPEN。applicability：仅 AT004 已结束尝试的闭合，不是实现成功或新的运行授权。

独立重新核对 144 个生产输入、39 个原来源绑定、39 个实际 stage_sources 归档、准备包/CPU 检查/文档、合同/范围补充和候选归因证据，身份一致。stage_inputs 的所有非 DCP 文件重新 hash；父 DCP 与失败 DCP 只由 A007 检查元数据大小和绑定。两份 DCP 的完整内容 hash 已由 A006 独立终态 collector 复算，分别吻合 396,068,466 字节/8451b2a8… 和 765,705,446 字节/51679d9a…；不会表述为 A007 读过或 hash 过 DCP。

8,499 条完整 resources.jsonl 样本独立复算与 status/terminal facts 一致：峰值 RSS 35,757,166,592 字节，最低 MemAvailable 490,982,973,440 字节，最低磁盘余量 411,805,528,064 字节；最大采样间隔 11.721124 秒。全程样本符合既有资源保护阈值。19 个原 PID-start 身份通过只读 /proc 再核均不存活；工程独占非阻塞锁探测显示 lane 已释放，审核另以 /proc/locks 核对该 inode 无持锁条目，未申请/释放锁或发送信号。

两个观察器 session 42865、73883 的工程归档真实工具回执均 exit0，未返回 running session；终态字段与监督 status 相符，自动捕获器最后于 21:18:34.992595Z 观察到 supervisor_terminal=true。历史缓冲输出截断不影响完整资源样本复算，也不当作完整资源历史。资源观察器最后一条 utc 是资源采样时间，不冒充观察器退出时间。

工程失败详细包 cf03a19d… 的最终失败计数、全局时序、当前 C01 compliance、五项采证回执和原生日志片段均与 A007 已完成的终态审核一致；64 条有界时序 TSV 的组数和最差 slack 也已复算，仅作为失败图有界诊断。native 日志显示 route elapsed 13,872 秒；整数边界 epoch 差 13,871 秒，1 秒舍入/取点差异保留，两者均不同于包含后续采证和 locality 的监督总时长。

engineering_execution_verified=false 正确表示原生/监督非零且没有完整成功 route 阶段，并非未核实这次自然失败。没有成功 route POST、最终 bus-skew 全覆盖或正式 reset/CDC/IO 安全结论；收尾通过不能替代这些验收。未启动 EDA、新 AT 或 implementation。

证据、完整身份和核查边界见 [JSON 审核记录](route_failed_terminal_closure_review.json)；物理失败结论见 [终态审核](route_failed_native_terminal_review.md)。
''')
print(json.dumps(dict(review=identity(dest),human=identity(human),recomputed_checks=recomputed,stage_manifest_non_DCP_files=len(stage_entries),resources=resources),ensure_ascii=False))
