"""Bounded A007 native first-apply review; no EDA or process control."""
from pathlib import Path
import datetime,hashlib,json,os
ROOT=Path(__file__).resolve().parents[3];OWN=Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT024_grouped_stream_postreport_recovery'
JOB=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT024_grouped_stream_postreport_recovery/evidence/jobs/native_postreport'
def ident(p,b=None):
 if b is None:b=p.read_bytes()
 return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
eventp=OWN/'AT024_dependency_event_001.json';event=json.loads(eventp.read_text());receiptp=REPORT/'m003_apply_success_158026_1.json';receipt=json.loads(receiptp.read_text())
expected={'kind':'native','success':'true','attempt':'1','pid':'158026','source_manifest_sha256':'16f9523c2e4968a34abdce8d8e5c126476f206ce8c0f93ceec146799c0d9cf75','overlay_sha256':'9124ea7eb710d8bbb4fe5c0c83e09f6cda1909d42e13d38bf6bae6765c9f3528'}
assert receipt==expected
assert ident(receiptp)['sha256']==event['dependencies']['stage_m003_apply_success_158026_1.json']['sha256_of_bounded_bytes']
sources={}
for relative,sha in [('project/hardware/vivado/constraints/m003_entry_manifest.json',expected['source_manifest_sha256']),('project/hardware/vivado/constraints/m003_joint_locality.xdc',expected['overlay_sha256']),('project/hardware/vivado/scripts/m003_joint_checks.tcl','604f22e3e0372e5ae8c56dbb03aa2e4f9fd9e86e936f3a611b9d0600debd9774')]:
 p=ROOT/relative;sources[relative]=ident(p);assert sources[relative]['sha256']==sha
checks=(ROOT/'project/hardware/vivado/scripts/m003_joint_checks.tcl').read_text();start=checks.index('proc m003::apply ');apply=checks[start:checks.index('\nproc ',start+1)]
assert apply.index('require_project runtime')<apply.index('set r [resolve]')<apply.index('hard_pblock m002_exact_hotspot_SLR2')<apply.index('foreach name $c01_protected')<apply.index('m003_apply_success_')
log=JOB/'launcher.log';size=log.stat().st_size;assert size<262144
with log.open('rb') as f:prefix=f.read(size)
prefixp=OWN/'AT024_first_apply_launcher_prefix.log'
with prefixp.open('xb') as f:f.write(prefix)
lines=prefix.decode(errors='replace').splitlines();markers=[{'line':i,'text':l} for i,l in enumerate(lines,1) if 'M003_OVERLAY_APPLIED' in l or 'open_run:' in l or 'REAL_CLOCK_FAMILIES' in l]
assert any('M003_OVERLAY_APPLIED' in x['text'] for x in markers)
oldprefix=(OWN/'AT024_native22_dependency_read_prefix.log').read_bytes();assert prefix.startswith(oldprefix)
tracep=REPORT/'m003_apply_attempts_158026.txt';assert tracep.stat().st_size<4096;trace=tracep.read_text();assert trace.startswith('attempt=1 restore_verify_only=0\n')
processes=[]
for pid,start in [(157933,6185410),(157934,6185432),(157935,6185621),(157954,6185625),(158026,6185635)]:
 fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();assert int(fields[19])==start and fields[0]!='Z'
 row={'pid':pid,'start_ticks':int(fields[19]),'state':fields[0],'nice':os.getpriority(os.PRIO_PROCESS,pid),'cpus':sorted(os.sched_getaffinity(pid))};assert row['nice']==5 and row['cpus']==list(range(8));processes.append(row)
keys={'HAP_M003_SCRIPTS_DIR','HAP_PROJECT_DIR','HAP_REPORT_DIR','HAP_M003_RECOVERED_SYNTHESIS','HAP_JOBS','HAP_SYNTH_JOBS'}
env={}
for item in (Path('/proc/158026/environ').read_bytes().split(b'\0')):
 if b'=' in item:
  k,v=item.split(b'=',1);key=k.decode()
  if key in keys:env[key]=v.decode()
assert env['HAP_REPORT_DIR']==str(REPORT) and env['HAP_M003_SCRIPTS_DIR']==str(ROOT/'project/hardware/vivado/scripts')
assert env['HAP_M003_RECOVERED_SYNTHESIS']=='1' and env['HAP_JOBS']=='8' and env['HAP_SYNTH_JOBS']=='1'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if '169247080' in l];assert len(locks)==1 and ' 157933 ' in locks[0]
p=JOB/'resources.jsonl'
with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));rows=f.read().splitlines()
for line in reversed(rows):
 try:resource=json.loads(line);break
 except ValueError:pass
now=datetime.datetime.now(datetime.timezone.utc);age=(now-datetime.datetime.fromisoformat(resource['utc'])).total_seconds();assert age<120
record={'utc':now.isoformat(),'execution':'completed_bounded_first_apply_review_native_continues','verdict':'accepted_first_native_Tcl_overlay_application_flow','review':'accepted_first_apply_only','applicability':'AT024 native158026/start6185635, manifest16f9523c, checks604f, overlay9124; runtime/resolve/allpblocks/C01 guard precede receipt','identities':{'event':ident(eventp),'native_receipt':ident(receiptp),'immutable_launcher_prefix':ident(prefixp,prefix),'apply_trace_observed':ident(tracep)},'native_receipt':receipt,'launcher_markers':markers,'prefix_extends_accepted22_dependency_read_prefix':True,'source_identities':sources,'owned_processes':processes,'native_environment_whitelist':env,'exact_lock':locks,'latest_resource':resource,'resource_age_seconds':age,'observed_apply_trace':trace,'pending':['Full selected snapshot and structure','Same-stage budget','Native natural terminal','Strict INIT/OPT/restore','G4 and full physical result'],'G4':False,'limits':['First Tcl apply success does not establish full open_run completion or snapshot success','No new test suite/EDA/DCP content or hash/production mutation/process control','Earlier exact_count site question independently closed by prior AT018 evidence']}
out=OWN/'AT024_first_apply_success_independent_review.json'
with out.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'receipt':ident(out),'markers':markers,'native_receipt':ident(receiptp),'resource_age_seconds':age}))
