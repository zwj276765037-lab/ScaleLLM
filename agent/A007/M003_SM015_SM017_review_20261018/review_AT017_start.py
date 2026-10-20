from pathlib import Path
import json,hashlib,datetime,os
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
BASE=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts'
E=BASE/'AT017_original_address_entry_postreport_recovery/evidence'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<4*1024*1024;b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['bytes']==x['bytes'] and a['sha256']==x['sha256'],x['path'];return a
activation=E/'actual_native_activation.json';a=json.loads(activation.read_text());assert ident(activation)['sha256']=='03e2fc6a7d411dcb7ee98d732edae44891ae8ce5981566d5f0b9acb443f2a58b'
refs={k:check(v) for k,v in a.items() if isinstance(v,dict) and 'path'in v}
s=json.loads(Path(a['started']['path']).read_text());m=json.loads(Path(a['manifest']['path']).read_text());assert len(m['sources'])==45
assert s['supervisor_pid']==42759 and s['leader_pid']==42760 and s['leader_start_ticks']==1270550
assert s['cpu_affinity']==list(range(8)) and s['nice']==5 and s['timeout_seconds'] is None and s['no_output_timeout_seconds'] is None
assert s['rss_limit_bytes']==192*1024**3 and s['mem_available_floor_bytes']==48*1024**3 and s['mem_low_grace_seconds']==30 and s['disk_floor_bytes']==30*1024**3
managed={x['path']:x for x in m['sources']};managed[s['G2']['path']]=s['G2'];managed[a['manifest']['path']]=a['manifest'];assert len(managed)==47
archive=json.loads(Path(a['archive']['path']).read_text());assert len(archive['bindings'])==191
prior=BASE/'AT015_measured_native_entry_postreport_recovery/evidence/jobs/native_postreport/source_archive.json';old=json.loads(prior.read_text());oldmap={x['original']['path']:x['original'] for x in old['bindings']}
verified=[];metadata=[];seen=set()
for row in archive['bindings']:
 original,preserved=row['original'],row['preserved'];p=original['path'];assert p not in seen;seen.add(p)
 assert original['bytes']==preserved['bytes'] and original['sha256']==preserved['sha256']
 assert Path(preserved['path']).stat().st_size==preserved['bytes']
 if p in managed:
  assert original==managed[p];verified.append({'original':check(original),'preserved':check(preserved)})
 else:
  assert original==oldmap[p];metadata.append({'path':p,'bytes':original['bytes'],'sha256':original['sha256'],'preserved':str(Path(preserved['path']).relative_to(R))})
assert set(managed).issubset(seen) and len(verified)==47 and len(metadata)==144
inputs=json.loads(Path(a['postreport_recovery_inputs']['path']).read_text());lineage=json.loads(Path(a['original_AT003_lineage']['path']).read_text())
assert lineage['native_exit_code']==1 and lineage['run_count']==23 and lineage['consumed_count']==22
assert inputs['origin']['original_native_exit_code']==1 and inputs['origin']['original_records_modified'] is False and inputs['origin']['raw_lineage']==a['original_AT003_lineage']
assert inputs['new_source_manifest']==a['manifest']
prior_inputs=R/'project/hardware/vivado/reports/m003_E011_R002_AT015_measured_native_entry_postreport_recovery/postreport_recovery_inputs.json'
previous=json.loads(prior_inputs.read_text())
assert inputs['origin']['source_delta']==previous['origin']['source_delta']
oldchanges={x['path']:x for x in previous['origin']['input_changes']}
newchanges={x['path']:x for x in inputs['origin']['input_changes']}
assert set(oldchanges)==set(newchanges)
changed_after=[]
for path,row in newchanges.items():
 assert path in managed
 assert row['before_sha256']==oldchanges[path]['before_sha256'] and row['preserved']==oldchanges[path]['preserved']
 check(row['preserved'])
 assert ident(path)['sha256']==row['after_sha256']
 if row['after_sha256']!=oldchanges[path]['after_sha256']:changed_after.append(path)
assert set(changed_after).issubset({a['manifest']['path'],a['checks']['path']}) and a['manifest']['path'] in changed_after
inherit=inputs['inherited_raw_reports'];assert len(inherit)==8
for row in inherit:
 assert row['original']['bytes']==row['preserved']['bytes'] and row['original']['sha256']==row['preserved']['sha256']
 assert Path(row['preserved']['path']).stat().st_size==row['preserved']['bytes']
processes=[];queue=[42759];seen=set()
while queue:
 pid=queue.pop(0)
 if pid in seen:continue
 seen.add(pid);p=Path('/proc')/str(pid);raw=(p/'stat').read_text();parts=raw[raw.rfind(')')+2:].split()
 x={'pid':pid,'ppid':int(parts[1]),'comm':raw[raw.find('(')+1:raw.rfind(')')],'start_ticks':int(parts[19]),'nice':int(parts[16]),'cpu_affinity':sorted(os.sched_getaffinity(pid))}
 assert x['nice']==5 and x['cpu_affinity']==list(range(8));processes.append(x)
 queue.extend(int(y) for y in (p/'task'/str(pid)/'children').read_text().split())
assert next(x for x in processes if x['pid']==42760)['start_ticks']==1270550
argv=(Path('/proc/42760/cmdline').read_bytes().rstrip(b'\0').split(b'\0'));assert [x.decode() for x in argv]==s['command']
lock=R/'project/hardware/vivado/.m002_eda.lock';st=lock.stat();key=f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if key in l];assert len(locks)==1 and ' 42759 ' in locks[0]
report=Path(s['report']);lp=report/'vivado.log';assert lp.stat().st_size<256*1024;log=lp.read_text();tail=log.splitlines()[-5:]
assert 'Reading design checkpoint' in log
e={'schema':'A007_AT017_actual_start_independent_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'activation':ident(activation),'references':refs,'actual47source_archive_content_pairs':verified,'144input_metadata_only':metadata,'original_lineage_counts':{'produced':23,'consumed':22,'original_outer_native_exit_code':1},'prepare_binding':{'original_lineage_identity_exact':True,'current_manifest_identity_exact':True,'recorded_original_input_adapter_changes':inputs['origin']['input_changes'],'adapter_delta_since_AT015':changed_after,'approved_entry_source_delta_metadata_matches_prior_AT015':True,'inherited8reports_identity_metadata_equal':True},'processes':processes,'exact_leader_command_verified':True,'lock':{'device_inode_key':key,'matching_proc_locks':locks,'method':'read-only stat+/proc/locks,no acquisition'},'live_log':{'path':str(lp.relative_to(R)),'observed_bytes':len(log.encode()),'tail':tail,'closed':False},'read_scope':'47 source/G2/manifest original and archive contents independently hashed; other144input contents and DCP contents NOT read or hashed; original immutable lineage JSON metadata compared.','current22read_completion':'Not checked in startup scope; awaits separate closed-prefix/native evidence'}
ep=O/'AT017_actual_start_independent_evidence.json';ep.write_text(json.dumps(e,indent=2)+'\n')
review={'schema':'A007_AT017_actual_start_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','AT017':'actually_started_native_recover_synth','started_utc':s['started_utc'],'native_terminal':'not observed'},'verdict':{'startup_source_archive_binding_resource_ownership':'accepted','current22native_dependency_read_completion':'not established by this startup review','actual_overlay_apply_or_selected_graph':'pending','G4':False,'place_admission':False},'applicability':{'checks_sha256':a['checks']['sha256'],'manifest_sha256':a['manifest']['sha256'],'actual_source_review_sha256':a['independent_actual_source_review']['sha256'],'original_lineage_sha256':a['original_AT003_lineage']['sha256']},'review':{'activation':ident(activation),'evidence':ident(ep),'archives':'191metadata pairs agree;47managedsource/G2/manifest original+preserved contents verified; remaining144original inputmetadata equal acceptedAT015 inventory, archived sizes agree, no content reread.','lineage_prepare':'Actual prepare admits same originalAT00323producers/22consumed;originalnative1 preserved;144 data-inputmetadata unchanged. Original-build adapter deltas retained and changed after-hashes limited to approved currentmanifest/checks; newmanifest exact. This is not proof that currentnative has readall22.','resources':'All observed owned processes CPU0–7/nice5; originalleader1270550 matches;supervisor42759 holds exactEDAflock.192GiB RSS/48GiB available30s/disk30GiB limits and no wall/quiet timeout retained.','process_identities':processes,'native_observation':'Live log shows actual dependencyread underway;log still open,not final result.'},'next':'A006 normal native execution continues. Send actual22readprefix/metadata, overlayapply/currentgraph or failure/terminal as separate increments. StrictG4 requires actual fullINIT/OPT/debug/preplace review.','limits':['No EDA,DCPcontents/hash,productionedit,process/lockcontrol by A007.','OriginalAT003outer1 remains; no new synthesis claimed.','Point-in-time startup observation is not background monitoring or global mission completion.']}
p=O/'AT017_actual_start_review.json';p.write_text(json.dumps(review,indent=2)+'\n');print(json.dumps({'review':ident(p),'evidence':ident(ep),'processes':processes,'archive_metadata_count':191,'archive_content_pair_count':47},indent=2))
statep=R/'agent/A007/state.json';state=json.loads(statep.read_text());state.update({'reported_at':review['reviewed_utc'],'stage':'AT017实际启动/191归档/47内容与原23/22准备绑定独立通过','next_step':'等实际22读取/原生apply与图或终态里程碑直接续审；G4另审','latest_review':str(p.relative_to(R)),'review_execution':'completed_AT017_start','current_turn_state':'waiting_for_actual_native_milestone','delivery':'AT017 startup review prepared; real delivery follows'});statep.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：AT017实际启动独立审核通过\n\nexecution_state: running\nreview_execution: completed_AT017_start\n\n[启动审核](M003_SM015_SM017_review_20261018/AT017_actual_start_review.json)：11:31:39Z新recover-synth真实启动，checks083/manifest5b，191归档metadata和47源/G2/manifest原件+归档内容核验通过；其余144旧输入metadata与AT015一致，未重复读大内容。原23产22用prepare绑定成立、AT003原native1保持；当前22原生读取完成尚待单独证据。\n\n归属PID/start、CPU0–7/nice5和监督42759精确锁持有已核。A006正常原生继续，实际apply/图/预算及G4未通过；A007无EDA、DCP内容/哈希、生产修改或进程/锁控制。下一里程碑由A006直接followup续审。\n\n## 历史阶段（保留）\n\n'+status.read_text())
