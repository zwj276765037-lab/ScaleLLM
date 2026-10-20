#!/usr/bin/env python3
"""Single owned M003 tool lane, PID/start tracking and resources, no wall/quiet stop."""
from __future__ import annotations
import argparse,datetime,fcntl,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
import run_managed_eda as owned

HW=Path(__file__).resolve().parents[2]
ROOT=HW.parent.parent
EXPERIMENT=ROOT/'project/E011_m003_joint_routability_implementation'
G2=ROOT/'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md'
G2_SHA='4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709'
GIB=1024**3
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--attempt',type=Path,required=True)
 ap.add_argument('--job',required=True)
 ap.add_argument('--report',type=Path,required=True)
 ap.add_argument('command',nargs=argparse.REMAINDER)
 a=ap.parse_args();attempt=a.attempt.resolve();report=a.report.resolve()
 cmd=a.command[1:] if a.command[:1]==['--'] else a.command
 if not cmd or not a.job.replace('_','').isalnum():raise ValueError('Command/job missing or invalid')
 if not attempt.is_relative_to(EXPERIMENT/'experiment_results/runs') or not attempt.is_dir():raise ValueError('Registered E011 attempt required')
 if not report.is_relative_to(HW/'vivado/reports') or report.exists():raise ValueError('New M003 report required')
 assert identity(G2)['sha256']==G2_SHA,'G2 binding changed'
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 if owned.mem_available()<48*GIB or shutil.disk_usage(HW).free<30*GIB:raise RuntimeError('Resource reserve unavailable')
 lock=(HW/'vivado/.m002_eda.lock').open('a+')
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 job=attempt/'evidence'/'jobs'/a.job
 job.mkdir(parents=True,exist_ok=False)
 env={**os.environ,'HAP_JOBS':'8','HAP_SYNTH_JOBS':'1','HAP_XSIM_TIMEOUT_SECONDS':'0','HAP_NICE_INCREMENT':'0','HAP_REPORT_DIR':str(report),'HAP_XSIM_REPORT_DIR':str(report),'HAP_CURRENT_ATTEMPT_DIR':str(attempt),'OMP_NUM_THREADS':'8','OPENBLAS_NUM_THREADS':'1','HAP_M003_ACTIVE':'1'}
 for k in ('HAP_EXECUTION_PROFILE','HAP_EXECUTION_MODE','HAP_BD_VALIDATE_ONLY'):env.pop(k,None)
 core_files=[HW/'rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv',HW/'rtl/attention/hap_weight_meta_resident.sv',HW/'rtl/attention/hap_attention_board_cohort16_core.sv']
 inputs=[identity(p) for p in core_files]
 meta=dict(started_utc=utc(),command=cmd,cwd=str(HW),attempt=str(attempt),job=a.job,report=str(report),G2=identity(G2),core_RTL=inputs,supervisor=identity(Path(__file__)),ownership_helpers=identity(HW/'vivado/scripts/run_managed_eda.py'),cpu_affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),timeout_seconds=None,no_output_timeout_seconds=None,rss_limit_bytes=192*GIB,mem_available_floor_bytes=48*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB)
 owned.write_json(job/'command.json',meta)
 tracked={};stop_reason=None;proc=None;native=None;max_rss=0;low_since=None
 def on_signal(signum,frame):raise KeyboardInterrupt(f'Explicit supervisor signal {signum}')
 signal.signal(signal.SIGTERM,on_signal);signal.signal(signal.SIGINT,on_signal)
 try:
  with (job/'launcher.log').open('w') as log,(job/'resources.jsonl').open('w',buffering=1) as samples:
   proc=subprocess.Popen(cmd,cwd=HW,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   table=owned.process_table();pidrow=table.get(proc.pid,{})
   meta.update(supervisor_pid=os.getpid(),leader_pid=proc.pid,leader_start_ticks=pidrow.get('start_ticks'))
   owned.write_json(job/'started.json',meta)
   print(json.dumps({'started':True,'job':a.job,'pid':proc.pid,'start_ticks':pidrow.get('start_ticks'),'supervisor':os.getpid(),'evidence':str(job),'report':str(report)}),flush=True)
   while True:
    rows=owned.owned_processes(owned.process_table(),proc.pid,tracked)
    for pid in rows:
     try:
      if not os.sched_getaffinity(pid).issubset(set(range(8))):os.sched_setaffinity(pid,set(range(8)))
      if os.getpriority(os.PRIO_PROCESS,pid)<5:os.setpriority(os.PRIO_PROCESS,pid,5)
     except ProcessLookupError:pass
    rss=sum(r['rss_bytes'] for r in rows.values());max_rss=max(max_rss,rss)
    available=owned.mem_available();disk=shutil.disk_usage(HW).free
    samples.write(json.dumps(dict(utc=utc(),rss_bytes=rss,mem_available_bytes=available,disk_free_bytes=disk,processes=rows))+'\n')
    low_since=(low_since or time.monotonic()) if available<48*GIB else None
    if rss>192*GIB:stop_reason='owned_tree_RSS_above_192GiB'
    elif low_since is not None and time.monotonic()-low_since>=30:stop_reason='MemAvailable_below_48GiB_for_30s'
    elif disk<30*GIB:stop_reason='disk_free_below_30GiB'
    if stop_reason:
     native,_,_=owned.terminate_and_reap(proc,tracked);break
    if proc.poll() is not None:
     native=proc.wait()
     # A native launcher can exit before an owned child. Keep the lane and
     # original resource monitoring until all PID/start identities drain.
     if not owned.owned_processes(owned.process_table(),proc.pid,tracked):break
    time.sleep(1)
 except BaseException as exc:
  stop_reason=f'explicit_interrupt_or_supervisor_error:{type(exc).__name__}:{exc}'
  if proc is not None:native,_,_=owned.terminate_and_reap(proc,tracked)
 finally:
  remaining=owned.owned_processes(owned.process_table(),proc.pid,tracked) if proc is not None else {}
  while remaining:
   # Never release the EDA lock merely because the leader has returned.
   owned.write_json(job/'ownership_drain.json',dict(observed_utc=utc(),leader_exit=native,remaining=remaining,lock_held=True))
   time.sleep(1)
   remaining=owned.owned_processes(owned.process_table(),proc.pid,tracked)
  integrity=[identity(Path(e['path']))==e for e in inputs]
  status=dict(execution_state='completed' if native==0 and not stop_reason and not remaining and all(integrity) else 'failed',ended_utc=utc(),native_exit_code=native,stop_reason=stop_reason,owned_survivors=remaining,tracked_PID_start_identities=tracked,core_RTL_unchanged_during_job=all(integrity),max_RSS_bytes=max_rss,no_wall_or_quiet_stop=True)
  owned.write_json(job/'status.json',status)
  fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
  print(json.dumps(status),flush=True)
 return 0 if status['execution_state']=='completed' else 1
if __name__=='__main__':sys.exit(main())
