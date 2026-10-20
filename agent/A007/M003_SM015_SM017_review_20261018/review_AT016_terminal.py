from pathlib import Path
import json,hashlib,datetime,re,os,subprocess
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
E=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT016_fresh_core_original_address_attribution/evidence'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<4*1024*1024;b=p.read_bytes()
 return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(d):
 a=ident(d['path']);assert a['bytes']==d['bytes'] and a['sha256']==d['sha256'],d['path'];return a
package=E/'AT016_closed_native_facts_and_terminal.json';t=json.loads(package.read_text());assert ident(package)['sha256']=='9b0e5b737967d5419d1f0ee2495bec5f0a0820451e8a8712a553dd4e1106d274'
refs={k:check(v) for k,v in t.items() if isinstance(v,dict) and 'path'in v and k!='fresh_core'}
outputs=[check(x) for x in t['closed_outputs']];report=Path(t['closed_outputs'][0]['path']).parent
s=json.loads(Path(t['status']['path']).read_text());assert s==t['actual_status']
assert s['execution_state']=='completed' and s['native_exit_code']==0 and s['stop_reason'] is None and not s['owned_survivors']
procs={}
for pid,ticks in {**s['tracked_PID_start_identities'],'38579':1122289}.items():
 p=Path('/proc')/pid/'stat'
 if p.exists():
  raw=p.read_text();actual=int(raw[raw.rfind(')')+2:].split()[19])
 else:actual=None
 procs[pid]={'expected_start_ticks':ticks,'observed_start_ticks':actual,'original_identity_absent':actual!=ticks}
assert all(x['original_identity_absent'] for x in procs.values())
lock=R/'project/hardware/vivado/.m002_eda.lock';st=lock.stat();key=f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
locks=[l for l in Path('/proc/locks').read_text().splitlines() if key in l];assert not locks
m=json.loads(Path(t['current_manifest']['path']).read_text());sources=[check(x) for x in m['sources']];assert len(sources)==45
complete=json.loads((report/'diagnostic_complete.json').read_text());assert complete['execution']=='completed' and complete['api_errors']==0
assert not list(report.glob('*.partial'))
counts=json.loads((report/'query_counts.json').read_text());assert counts['constraint_apply_requested'] is False and counts['new_synthesis_launched'] is False
progress=[json.loads(x) for x in (report/'diagnostic_progress.jsonl').read_text().splitlines()]
assert progress[-1]['event']=='diagnostic_complete'
rows={}
for name,n in [('original_address_broad',19),('local_control_luts',4)]:
 raw=[json.loads(x) for x in (report/(name+'.jsonl')).read_text().splitlines()]
 assert len(raw)==n==counts['collections'][name]['count']
 assert [x['index'] for x in raw]==list(range(n))
 expected={'NAME','REF_NAME','IS_PRIMITIVE','DONT_TOUCH'}|({'INIT'} if name=='local_control_luts' else set())
 decoded=[]
 for x in raw:
  assert set(x['fields'])==expected
  for field,v in x['fields'].items():
   assert v['status'] in {'OK','OK_EMPTY'} and (v['status']=='OK_EMPTY')==(v['value']=='')
  d={k:v['value'] for k,v in x['fields'].items()}
  assert x['object']==d['NAME'] and d['IS_PRIMITIVE']=='1';decoded.append(d)
 assert len({x['NAME'] for x in decoded})==n
 assert decoded==t['actual_native_rows'][name]
 closed=[x for x in progress if x['event']=='dump_closed' and x['collection']==name]
 assert len(closed)==1 and int(closed[0]['rows_written'])==n
 rows[name]=decoded
scope='inst/u_core/u_compute/u_attention/'
ff=[];carry=[]
for x in rows['original_address_broad']:
 if x['REF_NAME']=='FDCE':
  match=re.fullmatch(re.escape(scope)+r'meta_read_addr_r_reg\[(0|[1-9][0-9]*)\]',x['NAME']);assert match;ff.append((int(match[1]),x))
 else:assert x['REF_NAME']=='CARRY8';carry.append(x)
assert sorted(i for i,x in ff)==list(range(17))
expected_carry={scope+'meta_read_addr_r_reg[16]_i_5',scope+'meta_read_addr_r_reg[8]_i_2'}
assert {x['NAME'] for x in carry}==expected_carry
assert all(x['DONT_TOUCH']=='' for x in rows['original_address_broad'])
controls={}
for x in rows['local_control_luts']:
 match=re.fullmatch(re.escape(scope)+r'u_meta/g_m003_width_slices\.g_slice\[([01])\]\.u_addr/u_local_(ce|increment)',x['NAME']);assert match
 i,role=int(match[1]),match[2];assert (i,role) not in controls
 assert x['DONT_TOUCH']=='1' and (x['REF_NAME'],x['INIT'])==({'ce':('LUT3',"8'hFE"),'increment':('LUT2',"4'h2")}[role])
 controls[(i,role)]=x
assert set(controls)=={(0,'ce'),(0,'increment'),(1,'ce'),(1,'increment')}
checks=R/'project/hardware/vivado/scripts/m003_joint_checks.tcl'
source=checks.read_text();begin=source.index('    set original_address [dict create]');end=source.index('    set meta [primitive_scope',begin);block=source[begin:end]
assert 'original core address role unresolved' in block
os.sched_setaffinity(0,set(range(8)));os.nice(5)
tests=[]
for label,native,expect in [('all_19_actual_candidates',rows['original_address_broad'],1),('17_measured_state_FFs_only',[x for i,x in ff],0)]:
 names=' '.join('{'+x['NAME']+'}' for x in native)
 code='set core_meta_scope {'+scope.rstrip('/')+'}\nset names {'+names+'}\nproc get_cells {args} {return $::names}\nproc get_property {key cell} {if {$key ne "NAME"} {error "unexpected key"};return $cell}\nif {[catch {\n'+block+'\n} msg]} {puts $msg;exit 1}\nputs "COUNT=[dict size $original_address]"\n'
 result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True,cwd=R/'project/hardware');assert result.returncode==expect
 if expect:assert result.stdout.strip()=='M003 original core address role unresolved'
 else:assert result.stdout.strip()=='COUNT=17'
 tests.append({'case':label,'native_input_name_count':len(native),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
log=(report/'vivado.log').read_text();assert 'M003_FRESH_CORE_ORIGINAL_ADDRESS_ATTRIBUTION_COMPLETED' in log
e={'schema':'A007_AT016_closed_native_independent_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'terminal_package':ident(package),'verified_small_references':refs,'closed_outputs':outputs,'native_status':s,'original_processes':procs,'lock':{'device_inode_key':key,'matching_proc_locks':locks,'method':'read-only inode and /proc/locks, no acquisition'},'all45_sources':sources,'source_bytes_hashed':sum(x['bytes'] for x in sources),'completion_original_parsed':complete,'query_counts_original_parsed':counts,'progress_original_parsed':progress,'actual_rows_independently_decoded':rows,'state_bits':sorted(i for i,x in ff),'CARRY8_non_state_objects':sorted(expected_carry),'current_production_checks':ident(checks),'old_production_address_block_Tcl_replay':tests,'replay_scope':'Exact old original-address block with measured candidate names; get_cells/get_property mocked, no EDA. Isolates naming predicate failure, not full native graph qualification.','DCP_contents_or_hash_read':False,'fresh_core_integrity_authority':'Engineer original consumption binding/terminal hash; identity matched as metadata only','session_drain_authority':'A006 reported actual exec session drain; no reviewer process control'}
ep=O/'AT016_closed_native_independent_evidence.json';ep.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n')
review={'schema':'A007_AT016_native_facts_terminal_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','AT016':'naturally_completed','native_exit_code':0,'ended_utc':s['ended_utc'],'stop_reason':None,'owned_survivors':{},'original_processes':'4 tracked plus supervisor absent','EDA_lock':'no holder of exact inode at observation'},'verdict':{'native_candidate_and_control_evidence':'accepted','failure_attribution':'Old broad original-address query includes17 FDCE states and2 CARRY8 neighbors. The old resolver requires every candidate name end in packed-bit bracket, so these measured CARRY8 suffixes trigger the exact error. Tcl replay of unchanged old block rejects all19 and accepts measured17 states.','actual_state':'17 unique direct-child meta_read_addr_r_reg[0..16] FDCE; DONT_TOUCH values empty, retained without reinterpretation','controls':'Each of2 slices has protected LUT3 CE INIT8hFE and LUT2 increment INIT4h2, all measured directly','method_efficacy':'unassessed; diagnosis supports narrow role-selector correction, not M2/A3 outcome','G4':False,'place_admission':False},'applicability':{'checks_sha256':ident(checks)['sha256'],'manifest_sha256':t['current_manifest']['sha256'],'all45_sources':'independently hashed, unchanged','three_RTL_and_G2':'unchanged','core':'same original e51 checkpoint per A006 hash/binding; no reviewer DCP read'},'review':{'decision':'Accept native attribution and natural terminal; proceed with evidence-based narrow strict17-state selector candidate under existing authority','terminal_package':ident(package),'independent_evidence':ident(ep),'raw_completion':'Original140B artifact is directly valid JSON;0 API errors; counts19+4 and closed rows/progress agree; no partial output','required_candidate_properties':['Exact scope and canonical bit0..16 coverage, uniqueness and approved state REF validation.','Do not silently drop unknown or malformed/replicated FF candidates; preserve broad candidate rejection.','Any non-state exclusions need explicit measured role/ref identity basis; no unqualified blanket skip of all non-FF objects.','Native/synthetic/control-flow-derived replay fields kept separate, particularly CE INIT and C01 membership.'],'next':'Review narrow candidate/delta and positive-negative CPU tests, then actual source/manifest and native apply/restore/current graph plus strict G4.'},'limits':['This read-only run did not apply constraints or produce selected graph qualification.','Control truth tables are measured INIT values only; actual pin connectivity/protocol/feedback still require formal graph checks.','TOP01 -2.896ns and report/canonical difference22049 remain OPEN.','No EDA, production edit, DCP content/hash, process or lock control by A007.']}
p=O/'AT016_native_facts_and_terminal_review.json';p.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'review':ident(p),'evidence':ident(ep),'native_counts':{'original_address_broad':19,'state_FDCE':17,'non_state_CARRY8':2,'local_controls':4},'replays':tests},indent=2))
