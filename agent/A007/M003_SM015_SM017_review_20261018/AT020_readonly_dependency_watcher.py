"""Live A007 dependency observer: bounded metadata reads only, no EDA/control.
This process emits an event; the active A007 agent performs the required actual
collaboration.followup_task. A file or this script alone does not send a message.
"""
import datetime,hashlib,json,os,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parents[3];OWN=pathlib.Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT020_fresh_core_state_source_semantics'
JOB=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics/evidence/jobs/native_state_sources'
WATCH={
 'clock_final':REPORT/'uram_clock_sources.jsonl',
 'diagnostic_complete':REPORT/'diagnostic_complete.json',
 'diagnostic_error':REPORT/'diagnostic_error_info.txt',
 'native_status':JOB/'status.json',
}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(p):
 try:
  st=p.stat();out={'path':str(p.relative_to(ROOT)),'exists':True,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns}
  # Never read the large clock table here. Small evidence is bounded128KiB.
  if p!=WATCH['clock_final']:
   with p.open('rb') as f:b=f.read(131073)
   out['read_truncated']=len(b)>131072;b=b[:131072];out['bounded_sha256']=hashlib.sha256(b).hexdigest()
   if p.suffix=='.json':
    try:out['json']=json.loads(b)
    except (ValueError,UnicodeDecodeError) as e:out['parse_error']=str(e)
   else:out['text']=b.decode(errors='replace')
  return out
 except FileNotFoundError:return {'path':str(p.relative_to(ROOT)),'exists':False}
def snapshot():return {k:identity(p) for k,p in WATCH.items()}
def publish(name,value):
 p=OWN/name
 with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
 return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
stat=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
start={'schema':'A007_AT020_live_readonly_watcher_start_v1','utc':utc(),'pid':os.getpid(),'start_ticks':int(stat[19]),'nice':os.getpriority(os.PRIO_PROCESS,0),'cpus':sorted(os.sched_getaffinity(0)),'cwd':os.getcwd(),'script':str(pathlib.Path(__file__).resolve()),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'interval_seconds':30,'per_small_file_read_limit_bytes':131072,'no_partial_table_reads':True,'no_process_control_or_EDA_lock':True,'watch':snapshot(),'event_delivery':'Watcher emits only. Active A007 must call collaboration.followup_task to wake A006; no claim that file writes notify.'}
rec=publish('AT020_readonly_watcher_start.json',start);print(json.dumps({'event':'watcher_started','identity':rec,'pid':start['pid'],'start_ticks':start['start_ticks']}),flush=True)
# An already-present dependency is also immediately actionable.
while True:
 state=snapshot();changed=[k for k,v in state.items() if v['exists']]
 if changed:
  event={'schema':'A007_AT020_dependency_change_v1','observed_utc':utc(),'watcher_pid':os.getpid(),'watcher_start_ticks':start['start_ticks'],'triggers':changed,'dependencies':state,'owner_action':'A007 must immediately call actual collaboration.followup_task to A006 for owner closure; A006 retains session/process/lock/production ownership.','G4':False}
  rec=publish('AT020_dependency_change_event.json',event);print(json.dumps({'event':'dependency_changed','receipt':rec,'observed_utc':event['observed_utc'],'triggers':changed}),flush=True);break
 time.sleep(30)
