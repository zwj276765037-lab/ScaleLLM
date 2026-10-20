from pathlib import Path
import json,hashlib,datetime,os
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
E=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT016_fresh_core_original_address_attribution/evidence'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<16*1024*1024;b=p.read_bytes()
 return {'path':(str(p.relative_to(R)) if p.is_relative_to(R) else str(p)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(d):
 a=ident(d['path']);assert a['bytes']==d['bytes'] and a['sha256']==d['sha256'],d['path'];return a
a=json.loads((E/'actual_native_activation.json').read_text())
assert ident(E/'actual_native_activation.json')['sha256']=='3f52fadc850ee3f5b131c33dbca9a887fd24753edcc428af3c600b9b6763f908'
refs={k:check(v) for k,v in a.items() if isinstance(v,dict) and 'path'in v}
s=json.loads(Path(a['started']['path']).read_text());assert s['supervisor_pid']==38579 and s['leader_pid']==38580 and s['leader_start_ticks']==1122304
assert s['cpu_affinity']==list(range(8)) and s['nice']==5 and s['timeout_seconds'] is None and s['no_output_timeout_seconds'] is None
assert s['rss_limit_bytes']==192*1024**3 and s['mem_available_floor_bytes']==48*1024**3 and s['mem_low_grace_seconds']==30 and s['disk_floor_bytes']==30*1024**3
archive=json.loads(Path(a['source_archive']['path']).read_text());pairs=[]
for x in archive['bindings']:
 original=check(x['original']);preserved=check(x['preserved']);assert original['bytes']==preserved['bytes'] and original['sha256']==preserved['sha256'];pairs.append({'original':original,'preserved':preserved})
assert len(pairs)==12
b=json.loads(Path(a['original_core_consumption_binding']['path']).read_text());package=json.loads(Path(a['diagnostic_package']['path']).read_text())
assert b['diagnostic_package']==a['diagnostic_package'] and b['independent_review']==a['review']
assert b['core_original_produced_checkpoint']==package['fresh_core']
assert b['previous_terminal']==package['previous_terminal'] and b['entry_manifest']==package['entry_manifest'] and b['raw_original_lineage']==package['original_raw_lineage']
for key in ['diagnostic_package','independent_review','previous_terminal','entry_manifest','raw_original_lineage','core_original_native_completion']:check(b[key])
processes=[];queue=[s['supervisor_pid']];seen=set()
while queue:
 pid=queue.pop(0)
 if pid in seen:continue
 seen.add(pid);p=Path('/proc')/str(pid);raw=(p/'stat').read_text();parts=raw[raw.rfind(')')+2:].split()
 info={'pid':pid,'comm':raw[raw.find('(')+1:raw.rfind(')')],'ppid':int(parts[1]),'start_ticks':int(parts[19]),'nice':int(parts[16]),'cpu_affinity':sorted(os.sched_getaffinity(pid))}
 assert info['nice']==5 and info['cpu_affinity']==list(range(8))
 env=(p/'environ').read_bytes().split(b'\0')
 info['library_switch_absent']=not any(v.startswith(b'M003_ORIGINAL_ADDRESS_LIBRARY_ONLY=') for v in env)
 assert info['library_switch_absent']
 processes.append(info);queue += [int(x) for x in (p/'task'/str(pid)/'children').read_text().split()]
leader=[x for x in processes if x['pid']==38580];assert len(leader)==1 and leader[0]['start_ticks']==1122304
lock=R/'project/hardware/vivado/.m002_eda.lock';st=lock.stat();key=f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if key in l];assert len(locks)==1 and ' 38579 ' in locks[0] and 'FLOCK' in locks[0]
report=Path(s['report']);log=(report/'vivado.log').read_text();expected='Command: open_checkpoint '+package['fresh_core']['path'];assert expected in log
e={'schema':'A007_AT016_actual_start_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'activation':ident(E/'actual_native_activation.json'),'references':refs,'archive_pairs':pairs,'processes':processes,'lock':{'device_inode_key':key,'matching_proc_locks':locks,'method':'read-only stat and /proc/locks; no acquisition'},'live_native_log_excerpt':{'path':str((report/'vivado.log').relative_to(R)),'observed_bytes':len(log.encode()),'exact_original_core_open_command':expected,'tail':log.splitlines()[-5:],'closed':False},'DCP_read_or_hash':False,'provenance':'DCP identity compared from engineer consumption binding and reviewed package, not independently read'}
ep=O/'AT016_actual_start_independent_evidence.json';ep.write_text(json.dumps(e,indent=2)+'\n')
review={'schema':'A007_AT016_actual_start_review_v1','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','AT016':'actually_started_readonly_diagnostic','started_utc':s['started_utc'],'native_terminal':'not observed'},'verdict':{'actual_entry_identity_and_ownership':'accepted','native_candidate_names_or_counts':'not yet available','method_efficacy':'unassessed','G4':False,'place_admission':False},'applicability':{'package_sha256':a['diagnostic_package']['sha256'],'entry_review_sha256':a['review']['sha256'],'manifest_sha256':package['entry_manifest']['sha256'],'fresh_core_sha256_as_recorded_by_engineer':package['fresh_core']['sha256']},'review':{'activation':ident(E/'actual_native_activation.json'),'evidence':ident(ep),'archive_pairs_verified':12,'live_process_count':len(processes),'live_process_identities':processes,'library_only_switch':'independently absent in each observed owned process','EDA_lock':'exact inode exclusively held by supervisor38579','resources':'All observed owned processes CPU0–7/nice5; supervisor configured192GiB RSS/48GiB available30s/disk30GiB; no normal wall or quiet timeout','native_action':'Actual open_checkpoint command names exact original fresh core; no candidate count/role conclusion yet'},'next':'A006 continue normal read-only job. Send closed candidate/control collections and native terminal for review, then evidence-based narrow repair and explicit replay provenance. No new ordinary user approval.','limits':['No EDA, DCP contents/hash, source edit, signal or lock acquisition by A007.','Live process/log observation is point-in-time and not continuous monitoring.','AT015 failure and original raw evidence preserved; no G4 qualification implied.']}
p=O/'AT016_actual_start_review.json';p.write_text(json.dumps(review,indent=2)+'\n');print(json.dumps({'review':ident(p),'evidence':ident(ep),'processes':processes},indent=2))
statep=R/'agent/A007/state.json';state=json.loads(statep.read_text());state.update({'reported_at':e['observed_utc'],'stage':'AT016实际启动/12归档/原core绑定/归属资源独立通过','next_step':'等待A006闭合原地址及控制LUT原生集合/自然终态消息后直接续审；G4另审','latest_review':str(p.relative_to(R)),'review_execution':'completed_AT016_start','current_turn_state':'waiting_for_native_evidence'});statep.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：AT016实际启动独立审核通过\n\nexecution_state: running\nreview_execution: completed_AT016_start\n\n[启动审核](M003_SM015_SM017_review_20261018/AT016_actual_start_review.json)：11:06:56Z已按精确6e56包/6ff审核实际打开原e51核心；12归档对、全部观察归属PID/start/CPU0–7/nice5及测试开关缺席、监督38579精确锁持有均核实。原地址候选/控制LUT闭合集合与自然终态待送，角色修复及G4尚未通过。\n\nA006唯一EDA owner正常继续；A007仅自身审核，无DCP内容/哈希、生产改动或进程/锁控制。实际下一阶段由A006直接followup续审，不声称后台监控。\n\n## 历史阶段（保留）\n\n'+status.read_text())
