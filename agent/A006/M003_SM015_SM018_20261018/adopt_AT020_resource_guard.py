"""Restore resource/lock protection of EXISTING AT020; never launch an EDA.

The original launcher is a foreign child after its supervisor disappeared.
This guard cannot reap it or invent its native return code. Original job
started/resources/status and frozen inputs remain untouched.
"""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,shutil,signal,sys,time
ROOT=Path(__file__).resolve().parents[3]
HW=ROOT/'project/hardware';GIB=1024**3
sys.path.insert(0,str(HW/'vivado/scripts'))
import run_managed_eda as owned
EXPECTED={86002:3111217,86005:3111300,86024:3111303,86095:3111314}
LEADER=86002
HELPER_SHA='ef3cc774f30764a4b7f40eca073e4cf8f69a9704f860b0c813bfa88c2bc37839'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def fid(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def row(pid):
 try:
  raw=Path(f'/proc/{pid}/stat').read_text();f=raw[raw.rfind(')')+2:].split()
  return dict(start_ticks=int(f[19]),state=f[0],exit_code_raw=int(f[49]) if len(f)>49 else None)
 except (FileNotFoundError,ProcessLookupError):return None
def verify_initial(table):
 for pid,start in EXPECTED.items():
  if table.get(pid,{}).get('start_ticks')!=start:raise RuntimeError(f'Owned PID/start mismatch: {pid}')
  if table[pid]['pgrp']!=LEADER:raise RuntimeError(f'Owned process group mismatch: {pid}')
def resource_reason(rss,available,disk,low_since,now):
 if rss>192*GIB:return 'owned_tree_RSS_above_192GiB'
 if available<48*GIB and low_since is not None and now-low_since>=30:return 'MemAvailable_below_48GiB_for_30s'
 if disk<30*GIB:return 'disk_free_below_30GiB'
 return None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve()
 attempt=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics'
 if not out.is_relative_to(attempt/'evidence') or out.exists():raise ValueError('New AT020 evidence directory required')
 helper=HW/'vivado/scripts/run_managed_eda.py'
 if fid(helper)['sha256']!=HELPER_SHA:raise RuntimeError('Owned helper identity changed')
 if Path('/proc/86001').exists():raise RuntimeError('Original supervisor identity must be audited before adoption')
 verify_initial(owned.process_table())
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 lockpath=HW/'vivado/.m002_eda.lock';lock=lockpath.open('a+')
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Recheck after acquiring the sole lane; acquire does not launch/mutate EDA.
 verify_initial(owned.process_table());out.mkdir()
 tracked=dict(EXPECTED);maxrss=0;low_since=None;stop_reason=None;error_count=0;exit_observations={}
 def event(kind,**kw):
  with (out/'events.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),event=kind,**kw))+'\n')
 def signum(signum,frame):
  # Guard lifecycle signals never become authority to terminate normal EDA.
  event('guard_signal_recorded_native_not_signalled',signum=signum)
 for sig in (signal.SIGHUP,signal.SIGTERM,signal.SIGINT):signal.signal(sig,signum)
 lockstat=lockpath.stat();started=dict(schema='M003_existing_AT020_adopted_resource_guard_v1',started_utc=utc(),guard_pid=os.getpid(),guard_start_ticks=row(os.getpid())['start_ticks'],guard_pgrp=os.getpgrp(),guard_session=os.getsid(0),original_supervisor_pid=86001,original_supervisor_missing=True,original_native_exit_code=None,original_session74874_unavailable=True,original_job_status_created=False,existing_leader=LEADER,existing_PID_start_identities=EXPECTED,cpu_affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),rss_limit_bytes=192*GIB,mem_available_floor_bytes=48*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB,no_wall_or_quiet_stop=True,EDA_spawned=False,normal_native_signalled=False,lock=dict(path=str(lockpath),device=lockstat.st_dev,inode=lockstat.st_ino,held_by_guard=True),source=fid(Path(__file__)),ownership_helper=fid(helper),scope='Adopt existing exact PID/start tree and restore sole lock/resource protection only. Cannot reap foreign launcher or reconstruct missing original supervisor/native exit.')
 owned.write_json(out/'started.json',started)
 with (out/'resources.jsonl').open('x',buffering=1) as samples:
  while True:
   try:
    table=owned.process_table()
    # Existing tracked identities remain protected even after launcher exit.
    if LEADER in table and table[LEADER]['start_ticks']!=EXPECTED[LEADER]:
     rows={pid:r for pid,r in table.items() if tracked.get(pid)==r['start_ticks']}
     if rows:raise RuntimeError('Leader PID reused while tracked tree exists')
    else:rows=owned.owned_processes(table,LEADER,tracked)
    for pid,r in rows.items():
     actual=row(pid)
     if actual and actual['start_ticks']==r['start_ticks'] and actual['state']=='Z':exit_observations[str(pid)]=dict(observed_utc=utc(),**actual)
     try:
      if not os.sched_getaffinity(pid).issubset(set(range(8))):os.sched_setaffinity(pid,set(range(8)))
      if os.getpriority(os.PRIO_PROCESS,pid)<5:os.setpriority(os.PRIO_PROCESS,pid,5)
     except ProcessLookupError:pass
    rss=sum(r['rss_bytes'] for r in rows.values());maxrss=max(maxrss,rss)
    available=owned.mem_available();disk=shutil.disk_usage(HW).free;now=time.monotonic()
    low_since=(low_since if low_since is not None else now) if available<48*GIB else None
    sample=dict(utc=utc(),guard_pid=os.getpid(),rss_bytes=rss,mem_available_bytes=available,disk_free_bytes=disk,processes=rows,lock_held=True,original_supervisor_missing=True)
    samples.write(json.dumps(sample)+'\n');owned.write_json(out/'heartbeat.json',sample)
    reason=resource_reason(rss,available,disk,low_since,now)
    if reason and stop_reason is None:
     # Only the already-authorized measured resource thresholds permit stop.
     stop_reason=reason;event('measured_resource_protection_trigger',reason=reason,sample=sample)
     owned.terminate_owned(LEADER,tracked)
    if not rows:break
    time.sleep(1)
   except BaseException as exc:
    error_count+=1
    try:
     event('guard_monitor_error_native_not_signalled',error_type=type(exc).__name__,error=str(exc),error_count=error_count)
     owned.write_json(out/'monitor_error.json',dict(utc=utc(),error_type=type(exc).__name__,error=str(exc),error_count=error_count,lock_held=True,native_not_signalled=True))
    except BaseException:pass
    # Retain lane and keep trying; an observer must alert owner to this file.
    time.sleep(1)
 status=dict(schema=started['schema'],execution_state='owned_tree_drained' if not stop_reason else 'resource_protection_stopped_owned_tree',ended_utc=utc(),original_native_exit_code=None,native_exit_code_observable_by_this_guard=False,foreign_process_exit_raw_observations=exit_observations,stop_reason=stop_reason,owned_survivors={},tracked_PID_start_identities=tracked,max_RSS_bytes_since_adoption=maxrss,monitor_error_count=error_count,original_job_status_created=False,EDA_spawned=False,no_wall_or_quiet_stop=True)
 owned.write_json(out/'status.json',status)
 fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
 owned.write_json(out/'lock_released.json',dict(utc=utc(),guard_pid=os.getpid(),lock_released=True,reason='all tracked owned identities drained'))
 return 0
if __name__=='__main__':sys.exit(main())
