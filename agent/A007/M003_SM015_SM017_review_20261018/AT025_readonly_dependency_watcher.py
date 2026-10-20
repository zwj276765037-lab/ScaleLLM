"""Read-only bounded observer; active A007 sends actual collaboration messages."""
import datetime,hashlib,json,os,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parents[3];OWN=pathlib.Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT025_boundary_sources_postreport_recovery'
JOB=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/jobs/native_postreport'
SUPERVISOR=(274416,7666717);LOCK_INODE='169247080'
WATCH={'snapshot_final':REPORT/'m003_native_synth.json','snapshot_trace':REPORT/'m003_connection_synth_trace.jsonl','qualification':REPORT/'m003_qualification_synth.json','same_stage_budget':REPORT/'m003_same_stage_budget.json','postreport_complete':REPORT/'M003_postreport_qualification_complete.json','native_status':JOB/'status.json'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read_small(p,limit=131072):
 try:
  st=p.stat()
  if p.name=='m003_native_synth.json':return {'path':str(p.relative_to(ROOT)),'bytes':st.st_size,'stat_only':True}
  with p.open('rb') as f:b=f.read(limit+1)
  v={'path':str(p.relative_to(ROOT)),'bytes':st.st_size,'truncated':len(b)>limit,'sha256_of_bounded_bytes':hashlib.sha256(b[:limit]).hexdigest()}
  if p.suffix=='.json':
   try:v['json']=json.loads(b[:limit])
   except (ValueError,UnicodeDecodeError) as e:v['parse_error']=str(e)
  else:v['text']=b[:limit].decode(errors='replace')
  return v
 except FileNotFoundError:return None
def process(pid,start):
 try:
  v=(pathlib.Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'start_ticks':int(v[19]),'state':v[0],'matches':int(v[19])==start and v[0]!='Z'}
 except FileNotFoundError:return {'pid':pid,'matches':False,'absent':True}
def resource():
 p=JOB/'resources.jsonl'
 try:
  with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));lines=f.read().splitlines()
  # Writer may be in the middle of its last line; use latest complete JSON.
  for line in reversed(lines):
   try:
    v=json.loads(line);v['age_seconds']=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(v['utc'])).total_seconds();return v
   except (ValueError,UnicodeDecodeError):pass
  return {'error':'no complete bounded resource line'}
 except FileNotFoundError:return {'error':'resource file absent'}
def publish(name,value):
 p=OWN/name
 with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
 return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
stat=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
start={'utc':utc(),'pid':os.getpid(),'start_ticks':int(stat[19]),'nice':os.getpriority(os.PRIO_PROCESS,0),'cpus':sorted(os.sched_getaffinity(0)),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'interval_seconds':15,'read_limit_bytes':131072,'no_partial_table_scan':True,'no_process_control_or_lock_acquisition':True,'message_delivery':'File/event emission only; active A007 must followup_task A006.'}
print(json.dumps({'event':'watcher_started','identity':publish('AT025_readonly_watcher_start.json',start),'pid':start['pid'],'start_ticks':start['start_ticks']}),flush=True)
seen=set();index=0
while True:
 dynamic=dict(WATCH)
 for pattern in ('m003_apply_success_*.json','m003_snapshot_synth_*_error_info.txt'):
  for p in REPORT.glob(pattern):dynamic['stage_'+p.name]=p
 deps={k:read_small(p) for k,p in dynamic.items()};sup=process(*SUPERVISOR);res=resource();locks=[l for l in pathlib.Path('/proc/locks').read_text().splitlines() if LOCK_INODE in l]
 trace=deps.get('snapshot_trace')
 if trace and trace.get('text'):
  parsed=[]
  for line in trace['text'].splitlines():
   try:parsed.append(json.loads(line))
   except ValueError:pass
  selected=[r for r in parsed if r.get('event')=='boundary_source_selected']
  if {r.get('tag') for r in selected}=={'S','L','R','reset','read_enable','write_enable'}:deps['all_six_control_source_counts']={'rows':selected,'scope':'actual selection counts only; final NAME completeness still pending'}
  clock=[r for r in parsed if r.get('event')=='boundary_clock_source']
  if clock:deps['independent_clock_source_boundary']={'rows':clock}

 triggers=[k for k,v in deps.items() if v is not None and k not in seen]
 terminal=deps['native_status'] is not None
 if not terminal:
  if not sup['matches']:triggers.append('supervisor_missing_or_mismatched')
  if not(len(locks)==1 and ' 274416 ' in locks[0]):triggers.append('exact_supervisor_lock_absent_or_changed')
  if res.get('error') or res.get('age_seconds',999)>120:triggers.append('resource_heartbeat_missing_or_stale')
  if res.get('monitor_error') or res.get('monitor_error_count',0):triggers.append('monitor_error')
 if triggers:
  index+=1;event={'utc':utc(),'triggers':triggers,'dependencies':deps,'supervisor':sup,'lock_lines':locks,'resources':res,'G4':False,'required_delivery':'Active A007 immediately followup_task A006; sole owner retains control.'}
  print(json.dumps({'event':'dependency_changed','triggers':triggers,'receipt':publish(f'AT025_dependency_event_{index:03d}.json',event)}),flush=True)
  seen.update(k for k,v in deps.items() if v is not None)
  if terminal or any(k.startswith(('supervisor_','exact_','resource_','monitor_')) for k in triggers):break
 time.sleep(15)
