from pathlib import Path
import datetime,hashlib,json,os
ROOT=Path.cwd();OWN=ROOT/'agent/A007/M003_SM015_SM017_review_20261018';A=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT027_reset_semantics_postreport_recovery';J=A/'evidence/jobs/native_postreport';OLD=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/jobs/native_postreport';APP=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair/reset_semantics_application_evidence'
def load(p):return json.loads(Path(p).read_text())
def ident(p):
 p=Path(p);assert p.suffix!='.dcp' and p.stat().st_size<4*2**20;b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def check(r):
 d=ident(r['path']);assert (d['bytes'],d['sha256'])==(r['bytes'],r['sha256']);return d
act=load(A/'evidence/actual_native_activation.json');started=load(J/'started.json');arc=load(J/'source_archive.json');prior=load(OLD/'source_archive.json');manifest=load(ROOT/'project/hardware/vivado/constraints/m003_entry_manifest.json');regr=load(APP/'applied_regression_receipt.json');candidate=load(OWN/'reset_semantic_candidate_v2_independent_review.json')
assert len(arc['bindings'])==len(prior['bindings'])==194;old={x['original']['path']:x for x in prior['bindings']};now={x['original']['path']:x for x in arc['bindings']};assert set(old)==set(now)
small_paths={x['path'] for x in manifest['sources']}|{started['G2']['path'],str(ROOT/'project/hardware/vivado/constraints/m003_entry_manifest.json')};assert len(small_paths)==50
small=[];metadata=[];changed=[]
for path,b in now.items():
 before=old[path]
 if b['original']!=before['original']:changed.append(dict(before=before['original'],after=b['original']))
 if path in small_paths:
  small.append(dict(original=check(b['original']),preserved=check(b['preserved'])))
 else:
  assert b['original']==before['original']
  assert Path(path).stat().st_size==b['original']['bytes']
  assert Path(b['preserved']['path']).stat().st_size==b['preserved']['bytes']==b['original']['bytes']
  assert b['preserved']['sha256']==b['original']['sha256']
  metadata.append(dict(original=b['original'],archive=b['preserved'],verification='Current+archive stat and exact original SHA descriptor equality to accepted AT025 input; not rehashed or DCP-read by A007'))
assert len(metadata)==144
expected_changed={str(ROOT/'project/hardware/vivado/scripts'/n) for n in ['m003_joint_checks.tcl','m003_joint_evidence.py','m003_snapshot_stream.tcl']}|{str(ROOT/'project/hardware/vivado/constraints/m003_entry_manifest.json')};assert {x['after']['path'] for x in changed}==expected_changed
assert check(act['runtime_manifest'])['sha256']=='42dafce33f4727734dcf169b285a3decfcfa18d78d10f9a36463b4bea7c904d5'
for label,name in [('checks','m003_joint_checks.tcl'),('evidence','m003_joint_evidence.py'),('stream','m003_snapshot_stream.tcl')]:assert ident(ROOT/'project/hardware/vivado/scripts'/name)['sha256']==candidate['candidates'][label]['sha256']
receipts=[check(act[k]) for k in ['started','source_archive','runtime_manifest','candidate_independent_review','applied_regression']]
for section in ['formal_qualification','formal_native_entry']:
 receipts.extend([check(regr[section][k]) for k in ['actual_log','result']]);assert load(regr[section]['result']['path'])['exit_code']==0
assert 'Ran 33 tests in 7.967s' in Path(regr['formal_native_entry']['actual_log']['path']).read_text();assert 'Ran 95 tests in 39.432s' in Path(regr['formal_qualification']['actual_log']['path']).read_text()
receipts.extend([check(regr[k]) for k in ['first_failed_native_entry','fixture_source','final_application','depth_recheck','constant_recheck','runtime_manifest']])
assert regr['fixture_source']['sha256']=='ba1a6ff44e2bdbe29d98c3988c7d16c2a8dc748084658dea7a38644b2334b193'
processes=[]
for row in [act['supervisor']]+act['processes']+[dict(pid=379620,start_ticks=8592315)]:
 pid=row['pid'];p=Path('/proc')/str(pid);fields=(p/'stat').read_text().rsplit(')',1)[1].split();current=dict(pid=pid,start_ticks=int(fields[19]),state=fields[0],ppid=int(fields[1]),cpus=sorted(os.sched_getaffinity(pid)),nice=os.getpriority(os.PRIO_PROCESS,pid),command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode())
 assert current['start_ticks']==row['start_ticks'] and current['state']!='Z' and current['cpus']==list(range(8)) and current['nice']==5;processes.append(current)
assert 'm003_recover_synthesis.tcl' in next(x for x in processes if x['pid']==378139)['command']
allowed={'HAP_M003_ACTIVE','HAP_REPORT_DIR','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','PYTHONDONTWRITEBYTECODE'}
env={x.split('=',1)[0]:x.split('=',1)[1] for x in Path('/proc/378139/environ').read_bytes().decode().split('\0') if '=' in x and x.split('=',1)[0] in allowed};assert env['HAP_M003_ACTIVE']=='1' and env['HAP_REPORT_DIR']==started['report']
locks=[x for x in Path('/proc/locks').read_text().splitlines() if x.split()[5].split(':')[-1]=='169247080'];assert len(locks)==1 and locks[0].split()[4]=='377993'
p=J/'resources.jsonl'
with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));tail=f.read()
res=next(json.loads(x) for x in reversed(tail.splitlines()) if x.startswith(b'{') and x.endswith(b'}'));age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(res['utc'])).total_seconds();assert age<30 and res['rss_bytes']<192*2**30 and res['mem_available_bytes']>48*2**30 and res['disk_free_bytes']>30*2**30
assert started['timeout_seconds'] is None and started['no_output_timeout_seconds'] is None;assert [started[k] for k in ['rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes']]==[192*2**30,48*2**30,30,30*2**30]
watcher=load(OWN/'AT027_readonly_watcher_start.json');watcher.update(own_exec_session=19318,actual_proc_verified=True,script=str(OWN/'AT027_readonly_dependency_watcher.py'),no_EDA_process_control_lock=True,retired=False,delivery='Active A007 must immediately followup_task A006 on dependencies then review and message Root; observer only emits files/stdout')
with (OWN/'AT027_readonly_watcher_actual_identity.json').open('x') as f:json.dump(watcher,f,ensure_ascii=False,indent=2);f.write('\n')
report=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution='AT027 actual native recovery running; A007 active bounded independent observation',verdict='Actual startup, frozen3-source semantic candidate,48-source closure and corrected33-entry PASS accepted; no fulltop new reset/G4 result yet',applicability='AT027 manifest42dafce3, original source design, same postreport recovery, no RTL/resynthesis',review='Independent194 binding classification,100 small original/archive hashes,144 exact prior descriptors+stat,6process identities/env/lock/protection and actual observer verified',archive=ident(J/'source_archive.json'),prior_archive=ident(OLD/'source_archive.json'),actual_activation=ident(A/'evidence/actual_native_activation.json'),small50_original_archive_checks=small,other144_metadata=metadata,changed_exactly3_sources_plus_manifest=changed,processes=processes,native_env_whitelist=env,locks=locks,resource=res,resource_age_seconds=age,protections={k:started[k] for k in ('timeout_seconds','no_output_timeout_seconds','rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes')},receipts=receipts,tests=dict(actual33_seconds=7.967,fixture_source_accepted='Only4 isolated early-source/reset stubs; inverse exact old SHA',reused95_original_seconds=39.432,reuse_rationale='Final correction confined to native helper and collector, fixture paths AST unchanged; actual prior95 reused, not rerun',original_failure_preserved=True,A007_reran_old_suite=False),observer=watcher,early_reset_obligation='Actual trace reset_provenance_complete must trigger bounded native51 table review, not full qualification success',G4=False,no_DCP_content_or_whole_snapshot_read=True)
p=OWN/'AT027_actual_start_and_final_application_independent_review.json'
with p.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
statefile=ROOT/'agent/A007/state.json';s=load(statefile);s.update(execution_state='running',current_task='AT027新全图复位语义资格/实际阶段只读独审',stage='实际启动/最终48源/33入口PASS独审通过；早期51原生表待',reported_at=report['observed_utc'],latest_review=str(p.relative_to(ROOT)),review_execution='AT027_active_readonly_native_reset_and_full_qualification_watch',current_turn_state='active_readonly_observation',next_step='轮询自有session19318；实际early51/其他依赖/异常/终态立即followup A006后有界独审',watcher=watcher);statefile.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
status=ROOT/'agent/A007/status.md';old=status.read_text();status.write_text('# A007：AT027真实启动与最终语义候选应用独审通过\n\nexecution_state: running\nreview_execution: AT027_active_readonly_native_reset_and_full_qualification_watch\n\n[实际启动独审](M003_SM015_SM017_review_20261018/AT027_actual_start_and_final_application_independent_review.json)：194绑定=50小源原/档逐hash+144既审descriptor/原档stat；最终48manifest42dafce3、精确3源变更、6实际PID/start/CPU0–7/nice5、native白名单env、377993独锁与保护/新鲜资源核实。受影响33实际PASS7.967s，旧95实际39.432s按fixture路径未变复用不重跑，首次入口失败保留。\n\n候选py7f8a7186/Tclf5dc49c6/stream71e2524b已独审，DAG最长深度与原生常量pin两个新反例闭合。observer379620/start8592315/自有session19318已真实运行并核/proc，15s只读，新增early reset_provenance_complete触发；依赖由活跃A007实际followup A006后审。新全图实际51复位表/完整资格/预算/G4仍待；当前不是物理或时序通过。\n\n## 历史阶段（保留）\n\n'+old)
print(json.dumps(dict(review=ident(p),observer=ident(OWN/'AT027_readonly_watcher_actual_identity.json'),small_pairs=len(small),metadata_pairs=len(metadata),processes=len(processes))))
