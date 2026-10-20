"""A007 bounded AT025 startup identity review; large inputs stat only."""
from pathlib import Path
import datetime,hashlib,json,os
ROOT=Path(__file__).resolve().parents[3];OWN=Path(__file__).resolve().parent
RUNS=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts'
ATT=RUNS/'AT025_boundary_sources_postreport_recovery';JOB=ATT/'evidence/jobs/native_postreport'
PREV=RUNS/'AT024_grouped_stream_postreport_recovery/evidence/jobs/native_postreport'
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT025_boundary_sources_postreport_recovery'
FIX=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair'
def ident(p):
 b=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
started=json.loads((JOB/'started.json').read_text());activation=json.loads((ATT/'evidence/actual_native_activation.json').read_text());delivery=json.loads((FIX/'repair_application_receipt.json').read_text())
assert ident(FIX/'repair_application_receipt.json')['sha256']=='4673c9198fe5f38e6e01e41278355b54b8480e0e56e7884cb24c2458bb08e11c'
manifestp=ROOT/'project/hardware/vivado/constraints/m003_entry_manifest.json';assert ident(manifestp)['sha256']=='dab87062fdb295c0c0dd4639cb8144b9fc05c58a5caae78b8c6bdfcbbbfd173c';manifest=json.loads(manifestp.read_text());assert len(manifest['sources'])==48
rows=json.loads((JOB/'source_archive.json').read_text())['bindings'];prevrows=json.loads((PREV/'source_archive.json').read_text())['bindings'];assert len(rows)==194
prev={r['original']['path']:r for r in prevrows};selected={r['path']:r for r in manifest['sources']};selected[str(manifestp)]=dict(path=str(manifestp),bytes=manifestp.stat().st_size,sha256=ident(manifestp)['sha256']);selected[started['G2']['path']]=started['G2']
small=[];metadata=[]
for row in rows:
 original=row['original'];preserved=row['preserved'];path=original['path']
 assert original['bytes']==preserved['bytes'] and original['sha256']==preserved['sha256']
 assert Path(path).stat().st_size==original['bytes'] and Path(preserved['path']).stat().st_size==preserved['bytes']
 if path in selected:
  expect=selected[path];a=ident(Path(path));b=ident(Path(preserved['path']));assert a['sha256']==b['sha256']==expect['sha256'] and a['bytes']==b['bytes']==expect['bytes'];small.append({'original':a,'preserved':b})
 else:
  assert original==prev[path]['original'];metadata.append({'path':path,'bytes':original['bytes'],'metadata_equal_accepted_AT024':True,'original_and_archive_size_checked':True,'contents_not_read':True})
assert len(small)==50 and len(metadata)==144
oldmanifest=json.loads(Path(prev[str(manifestp)]['preserved']['path']).read_text());old={r['path']:r for r in oldmanifest['sources']};new={r['path']:r for r in manifest['sources']};assert old.keys()==new.keys();changed=[p for p in new if old[p]!=new[p]]
assert {Path(p).name for p in changed}=={'m003_joint_checks.tcl','m003_shared_connectivity.tcl'}
for key,want in [('timeout_seconds',None),('no_output_timeout_seconds',None),('rss_limit_bytes',206158430208),('mem_available_floor_bytes',51539607552),('mem_low_grace_seconds',30),('disk_floor_bytes',32212254720)]:assert started[key]==want
assert started['cpu_affinity']==list(range(8)) and started['nice']==5
expected={274416:7666717,274417:7666738,274442:7666927,274461:7666932,274532:7666943};processes=[]
for pid,start in expected.items():
 fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();row={'pid':pid,'start_ticks':int(fields[19]),'state':fields[0],'ppid':int(fields[1]),'pgrp':int(fields[2]),'session':int(fields[3]),'nice':os.getpriority(os.PRIO_PROCESS,pid),'cpus':sorted(os.sched_getaffinity(pid))};assert row['start_ticks']==start and row['state']!='Z' and row['nice']==5 and row['cpus']==list(range(8));processes.append(row)
keys={'HAP_M003_SCRIPTS_DIR','HAP_PROJECT_DIR','HAP_REPORT_DIR','HAP_M003_RECOVERED_SYNTHESIS','HAP_JOBS','HAP_SYNTH_JOBS'};env={}
for item in Path('/proc/274532/environ').read_bytes().split(b'\0'):
 if b'=' in item:
  k,v=item.split(b'=',1)
  if k.decode() in keys:env[k.decode()]=v.decode()
assert env['HAP_REPORT_DIR']==str(REPORT) and env['HAP_M003_SCRIPTS_DIR']==str(ROOT/'project/hardware/vivado/scripts') and env['HAP_PROJECT_DIR']==str(ROOT/'project/hardware/vivado/project/scalellm_m003_E011_R002_AT002') and env['HAP_JOBS']=='8' and env['HAP_SYNTH_JOBS']=='1' and env['HAP_M003_RECOVERED_SYNTHESIS']=='1'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if '169247080' in l];assert len(locks)==1 and ' 274416 ' in locks[0]
p=JOB/'resources.jsonl'
with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));lines=f.read().splitlines()
for l in reversed(lines):
 try:resource=json.loads(l);break
 except ValueError:pass
now=datetime.datetime.now(datetime.timezone.utc);age=(now-datetime.datetime.fromisoformat(resource['utc'])).total_seconds();assert age<120 and not resource.get('monitor_error')
watch=json.loads((OWN/'AT025_readonly_watcher_start.json').read_text());pid=watch['pid'];fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();assert pid==277146 and int(fields[19])==7683120 and sorted(os.sched_getaffinity(pid))==list(range(8)) and os.getpriority(os.PRIO_PROCESS,pid)==5
watchrec={'utc':now.isoformat(),'pid':pid,'start_ticks':int(fields[19]),'own_exec_session':99907,'cpus':'0-7','nice':5,'actual_proc_verified':True,'script':str(OWN/'AT025_readonly_dependency_watcher.py'),'interval_seconds':15,'no_EDA_process_control_lock':True}
wp=OWN/'AT025_readonly_watcher_actual_identity.json'
with wp.open('x') as f:json.dump(watchrec,f,indent=2);f.write('\n')
for key in ('source','log'):
 e=delivery['affected_tests'][key];p=Path(e['path']);assert ident(p)['bytes']==e['bytes'] and ident(p)['sha256']==e['sha256']
log=Path(delivery['affected_tests']['log']['path']).read_text();assert 'Ran 7 tests in 0.896s' in log and log.rstrip().endswith('OK')
record={'utc':now.isoformat(),'execution':'AT025_running_startup_review_completed','verdict':'actual_start_and_frozen_input_closure_accepted','review':'accepted_startup_only_not_G4','applicability':'AT025 manifestdab87062/checks8d3aa4c/shared59c22aed; no new synthesis or RTL change','identities':{'activation':ident(ATT/'evidence/actual_native_activation.json'),'started':ident(JOB/'started.json'),'archive':ident(JOB/'source_archive.json'),'repair_delivery':ident(FIX/'repair_application_receipt.json'),'current_manifest':ident(manifestp)},'50_small_source_original_preserved_pairs':small,'144_large_input_metadata_and_sizes':metadata,'exact_runtime_changed_paths':changed,'owned_processes':processes,'native_environment_whitelist':env,'exact_lock_lines':locks,'resource_limits':{k:started[k] for k in ('timeout_seconds','no_output_timeout_seconds','rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes')},'latest_resource':resource,'resource_age_seconds':age,'actual_watcher':watchrec,'owner_affected_tests_verified':{'functions':7,'actual_log_seconds':0.896,'unchanged128_and_AT023_not_repeated':True},'static_review':['Independent scalar anchors cover6nonclock plusclock, before row walk','Actual source objects preserved same-call; leaf actual DIRECTION OUT and exclusive primary IN retained','Exact same-call actual net object membership before source bind; new distinct endpoint; decoder and80protection unchanged','Three previously reviewed serializer wrappers applied; write boundary now usesactual net helper'],'pending_defense_and_actual_acceptance':['Current boundary_names does not explicitly reject short NAME vector or emptyNAME; no observed native partial result yet','Do not hot edit or stop AT025; offline hardened candidate and CPU examples separate','At actual snapshot completion require each6tag source_selected segment_count equals complete nonempty unique NAME list, plus actual scalar anchor membership; clock by its complete same-call group witness','Missing/mismatched actual evidence requires ordinary next repair; static defense omission alone is not current native failure'],'G4':False}
out=OWN/'AT025_actual_start_independent_review.json'
with out.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'receipt':ident(out),'watcher_identity':ident(wp),'small_pairs':len(small),'metadata_only':len(metadata),'runtime_delta':[Path(p).name for p in changed],'resource_age_seconds':age}))
