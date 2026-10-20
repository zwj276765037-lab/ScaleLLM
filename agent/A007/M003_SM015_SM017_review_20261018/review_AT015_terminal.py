from pathlib import Path
import hashlib,json,datetime,os
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
B=ROOT/'project/E011_m003_joint_routability_implementation'
E=B/'experiment_results/runs/R002/attempts/AT015_measured_native_entry_postreport_recovery/evidence'
def identity(p):
 p=Path(p);assert p.suffix!='.dcp'
 b=p.read_bytes();assert len(b)<4*1024*1024
 return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(d):
 actual=identity(d['path']);assert actual['bytes']==d['bytes'] and actual['sha256']==d['sha256'],d['path']
 return actual
t=json.loads((E/'AT015_terminal_and_source_integrity.json').read_text())
w=json.loads((E/'AT015_existing_DDR_puts_warning_attribution.json').read_text())
refs={k:check(v) for k,v in t.items() if isinstance(v,dict) and 'path'in v and k!='fresh_core_DCP'}
st=json.loads(Path(t['native_status']['path']).read_text());assert st==t['actual_status']
assert st['native_exit_code']==1 and st['stop_reason'] is None and st['owned_survivors']=={} and st['no_wall_or_quiet_stop']
started=json.loads(Path(t['started']['path']).read_text())
proc={}
for pid,ticks in {**st['tracked_PID_start_identities'],'33953':957751}.items():
 p=Path('/proc')/pid/'stat'
 if p.exists():
  text=p.read_text();now=int(text[text.rfind(')')+2:].split()[19])
 else: now=None
 proc[pid]={'expected_start_ticks':ticks,'observed_start_ticks':now,'original_identity_absent':now!=ticks}
assert all(x['original_identity_absent'] for x in proc.values())
lock=ROOT/'project/hardware/vivado/.m002_eda.lock';s=lock.stat()
lock_key=f'{os.major(s.st_dev):02x}:{os.minor(s.st_dev):02x}:{s.st_ino}'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if lock_key in l]
assert not locks
m=json.loads(Path(t['actual_frozen_manifest']['path']).read_text())
sources=[check(x) for x in m['sources']];assert len(sources)==45
rtls=[check(x) for x in started['core_RTL']]
log=Path(t['closed_native_log']['path']).read_text().splitlines()
for x in t['actual_failure_lines']:assert log[x['line']-1]==x['text']
trace=Path(t['apply_attempts']['path']).read_text()
assert trace=='attempt=1 restore_verify_only=0\nattempt=2 restore_verify_only=0\n'
report=Path(t['closed_native_log']['path']).parent
success=list(report.glob('m003_apply_success_*.json'));snapshots=list(report.glob('m003_native_*.json'))
assert not success and not snapshots
constraint=check(w['constraint_source']);src=Path(w['constraint_source']['path']).read_text()
assert src==w['source_complete_text'];active=[(i,l) for i,l in enumerate(src.splitlines(),1) if l.strip() and not l.lstrip().startswith('#')]
assert active==[(9,'puts {INFO: [M002] Clock contract: core100 / DDR UI200; no added timing exceptions or placement.}')]
historical=[]
for attempt,rec in w['native_warning_occurrences'].items():
 wanted={x['line']:x['text'] for x in rec['matching_lines']};found={}
 with Path(rec['path']).open() as f:
  for i,line in enumerate(f,1):
   if i in wanted:found[i]=line.rstrip('\n')
   if i>=max(wanted):break
 assert found==wanted
 historical.append({'attempt':attempt,'path':str(Path(rec['path']).relative_to(ROOT)),'verified_lines':list(found)})
raw=B/'experiment_results/runs/R002/attempts/AT003_fresh_selected_synthesis/evidence/AT003_terminal_and_raw_native_lineage.json'
lineage=json.loads(raw.read_text());matches=[]
def walk(obj,path=''):
 if isinstance(obj,dict):
  if obj.get('path')==w['constraint_source']['path'] and obj.get('sha256')==constraint['sha256']:matches.append(path)
  for k,v in obj.items():walk(v,path+'/'+k)
 elif isinstance(obj,list):
  for i,v in enumerate(obj):walk(v,path+'/'+str(i))
walk(lineage);assert matches
e={'schema':'A007_AT015_independent_terminal_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'terminal_package':identity(E/'AT015_terminal_and_source_integrity.json'),'warning_package':identity(E/'AT015_existing_DDR_puts_warning_attribution.json'),'verified_references':refs,'native_status':st,'tracked_processes':proc,'lock':{'path':str(lock.relative_to(ROOT)),'device_inode_key':lock_key,'matching_proc_locks':locks,'method':'stat and /proc/locks read only; no acquisition'},'all45_source_identities':sources,'three_RTL':rtls,'source_bytes_hashed':sum(x['bytes'] for x in sources),'raw_failure_lines':t['actual_failure_lines'],'stack_lines':[{ 'line':i,'text':log[i-1]} for i in range(336,354)],'apply_trace':trace,'success_receipts':[],'native_selected_snapshots':[],'DDR_warning':{'source':constraint,'only_active_source_command':active,'historical_exact_line_checks':historical,'original_lineage':identity(raw),'matching_original_input_records':matches},'DCP_content_or_hash_read':False,'session_drained':'A006 report; no reviewer session polling','fresh_core_integrity':'A006 hash authority retained; reviewer does not independently hash/read DCP'}
p=OUT/'AT015_terminal_independent_evidence.json';p.write_text(json.dumps(e,indent=2,ensure_ascii=False)+'\n')
review={'schema':'A007_AT015_natural_failure_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','native_attempt':'failed_naturally','native_exit_code':1,'ended_utc':st['ended_utc'],'stop_reason':None,'owned_survivors':{},'original_six_processes_and_supervisor':'identities absent','EDA_lock':'no /proc/locks holder for exact inode at observation'},'verdict':{'terminal_integrity':'accepted','entry_failure':'M003 original core address role unresolved','payload_and_CE':'current source resolve lines139–149 necessarily completed before failing original-address loop lines150–153; limited control-flow reachability evidence only','unknown':'Exact offending original-address candidate NAME/REF is not yet known; no guessed selector repair','method_efficacy':'unassessed; entry failure does not refute M2/A3','G4':False,'place_admission':False},'applicability':{'checks_sha256':t['source_checks']['sha256'],'manifest_sha256':t['actual_frozen_manifest']['sha256'],'sources_verified':45,'three_RTL_and_G2':'unchanged','fresh_core_DCP':'A006-provided unchanged e51adf501ead; reviewer did not read or hash DCP'},'review':{'decision':'Accept natural terminal and source preservation; continue authorized narrowly scoped read-only native attribution and ordinary entry repair','required_next':'Preserve all original-address candidates and constraints; complete source qualification, actual apply/restore/current graph and strict INIT/OPT/debug/preplace before G4','evidence':identity(p),'terminal_package':identity(E/'AT015_terminal_and_source_integrity.json')},'DDR_warning':{'attribution':'accepted narrowly: unchanged f096a53a line9 contains only informational puts; exact same Designutils20-1307 observed AT003, AT012 and AT015','original_input_match':matches,'source_adds_constraints':False,'distinction':'Separate from M003 overlay file/info/source/apply issue; no blanket warnings/safety clearance','chronology':'Attribution recorded while AT015 live; closed_log=false and running description there are historical. Terminal package and closed log now supersede that state.'},'limits':['No successful apply receipt or native selected snapshot; trace has two failed attempts.','No independent native object naming inference for original address yet.','No EDA, production edit, DCP contents/hash, process control or lock acquisition performed.','TOP01 -2.896ns and report/canonical delta22049 remain OPEN.']}
p=OUT/'AT015_natural_failure_review.json';p.write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'review':identity(p),'evidence':identity(OUT/'AT015_terminal_independent_evidence.json'),'source_count':len(sources),'source_bytes':e['source_bytes_hashed'],'all_original_processes_gone':True,'lock_holder_count':len(locks),'DDR_original_matches':matches},indent=2))
