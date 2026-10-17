#!/usr/bin/env python3
"""Adopt the live E003 worker without a wall timeout, then manage qualified route.

No frozen worker/design/contract is modified. Only the old supervisor PID is
stopped; its existing EDA lane lock stays held until that worker tree closes.
"""
from __future__ import annotations
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HW=ROOT/'project/hardware'
RESULTS=ROOT/'project/E003_m002_full_implementation/experiment_results'
HERE=Path(__file__).resolve().parent
ADDENDUM=ROOT/'mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md'
ADDENDUM_SHA='17acf92465c4e0f3256a40ff78f953bc7398b1a9a68ed53da79ae23fb8db8363'
SUPERVISION_PROFILE='m002_no_wall_continuation'
OLD_SUPERVISOR=3677862
OLD_SUPERVISOR_TICKS=917946821
LEADER=3677864
LEADER_TICKS=917946826
VIVADO=3678158
VIVADO_TICKS=917949115
CPUS=list(range(8))
ACTIVE=None
ACTIVE_PROC=None
sys.path.insert(0,str(HW/'vivado/scripts'))
import run_managed_eda as managed
import m002_execution_profile as profile


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def save(path,value):profile.save(path,value)
def fid(path):return profile.identity(path)


def procstat(pid):
    try:
        raw=(Path('/proc')/str(pid)/'stat').read_text();f=raw[raw.rindex(')')+2:].split()
        return dict(pid=pid,state=f[0],ppid=int(f[1]),pgrp=int(f[2]),start_ticks=int(f[19]),
                    cpu_ticks=int(f[11])+int(f[12]),exit_wait_status=int(f[49]))
    except FileNotFoundError:return None


def exact(pid,ticks):
    row=procstat(pid)
    if row is None or row['start_ticks']!=ticks:raise RuntimeError(f'PID identity lost: {pid}/{ticks}')
    return row


def single_signal(pid,ticks,sig):
    exact(pid,ticks);os.kill(pid,sig)


def stop_supervisor(pid,ticks,leader,leader_ticks):
    before=exact(leader,leader_ticks)
    single_signal(pid,ticks,signal.SIGSTOP)
    for _ in range(100):
        row=exact(pid,ticks)
        if row['state'] in {'T','t'}:break
        time.sleep(.01)
    else:raise RuntimeError('old supervisor did not stop')
    after=exact(leader,leader_ticks)
    if after['pgrp']!=before['pgrp'] or after['state'] in {'T','t','Z','X'}:
        raise RuntimeError('worker identity/state changed across supervisor-only stop')
    return {'before':before,'after':after,'old_supervisor_after':row}


def sample(leader,tracked):
    rows=managed.owned_processes(managed.process_table(),leader,tracked)
    for pid in rows:
        try:
            if not os.sched_getaffinity(pid).issubset(CPUS):os.sched_setaffinity(pid,CPUS)
        except ProcessLookupError:pass
    return dict(utc=utc(),rss_bytes=sum(r['rss_bytes'] for r in rows.values()),
                mem_available_bytes=managed.mem_available(),disk_free_bytes=shutil.disk_usage(HW).free,processes=rows)


def active_owned(leader,tracked):
    rows=managed.owned_processes(managed.process_table(),leader,tracked)
    return {pid:row for pid,row in rows.items() if (procstat(pid) or {}).get('state') not in {None,'Z','X'}}


def decode_wait(status):
    if os.WIFEXITED(status):return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):return -os.WTERMSIG(status)
    raise RuntimeError('worker wait status is not terminal')


def monitor(stage,attempt,report,leader,tracked,*,proc=None):
    """No elapsed/global/no-output termination branch exists here."""
    minimum_mem=managed.mem_available();minimum_disk=shutil.disk_usage(HW).free;peak=0;low_since=None
    stopped=None;native=None;terminal=None;last_error=None;start=time.monotonic()
    old_samples=attempt/'resources.jsonl'
    if old_samples.exists():
        for line in old_samples.read_text().splitlines():
            row=json.loads(line);peak=max(peak,row['rss_bytes']);minimum_mem=min(minimum_mem,row['mem_available_bytes']);minimum_disk=min(minimum_disk,row['disk_free_bytes'])
    log=attempt/'continuation_resources.jsonl'
    while True:
        try:
            observation=sample(leader,tracked);observation.update(supervision_profile=SUPERVISION_PROFILE,elapsed_since_adoption_seconds=time.monotonic()-start)
            with log.open('a') as handle:handle.write(json.dumps(observation)+'\n')
            peak=max(peak,observation['rss_bytes']);minimum_mem=min(minimum_mem,observation['mem_available_bytes']);minimum_disk=min(minimum_disk,observation['disk_free_bytes'])
            if observation['mem_available_bytes']<48*managed.GIB:low_since=low_since or time.monotonic()
            else:low_since=None
            reason=('task_tree_rss_above_192GiB' if observation['rss_bytes']>192*managed.GIB else
                'system_mem_available_below_48GiB_for_30s' if low_since is not None and time.monotonic()-low_since>=30 else
                'disk_free_below_30GiB' if observation['disk_free_bytes']<30*managed.GIB else None)
            if reason and stopped is None:
                stopped=reason;save(attempt/'continuation_resource_stop.json',dict(utc=utc(),reason=reason,sample=observation))
                managed.terminate_owned(leader,tracked)
            row=procstat(leader)
            if proc is not None:
                value=proc.poll()
                if value is not None:native=value;terminal={'source':'actual subprocess.wait/poll','returncode':value,'proc_stat':row}
            elif row and row['state']=='Z':
                native=decode_wait(row['exit_wait_status']);terminal={'source':'actual adopted worker /proc/stat zombie wait status','proc_stat':row,'returncode':native}
            elif row is None:
                raise RuntimeError('adopted worker disappeared before terminal wait status was captured')
            if native is not None and not active_owned(leader,tracked):break
            if last_error is not None:
                save(attempt/'watchdog_exception_recovered.json',dict(utc=utc(),previous=last_error));last_error=None
            time.sleep(5)
        except Exception as exc:
            # Do not restore the old timed supervisor or abandon the live child.
            # Keep retrying supervision and expose the concrete error immediately.
            last_error=f'{type(exc).__name__}: {exc}'
            print(json.dumps(dict(watchdog_exception=last_error,utc=utc(),stage=stage)),flush=True)
            try:save(attempt/'watchdog_exception.json',dict(utc=utc(),error=last_error,policy='retain same child and retry supervision; never resume old deadline'))
            except Exception:pass
            time.sleep(1)
    return dict(native_exit_code=native,stop_reason=stopped,exit_code=125 if stopped else native,
                terminal=terminal,max_tree_rss_bytes=peak,minimum_mem_available_bytes=minimum_mem,
                minimum_disk_free_bytes=minimum_disk,tracked_identities=tracked)


def close_status(stage,attempt,metadata,outcome,leader):
    survivors=sorted(managed.owned_processes(managed.process_table(),leader,outcome['tracked_identities']))
    if survivors:raise RuntimeError(f'cannot close stage with existing owned process identities: {survivors}')
    value={**metadata,**outcome,'execution_state':'completed','ended_utc':utc(),'owned_survivors':[],
           'supervisor_pid':os.getpid(),'supervision_profile':SUPERVISION_PROFILE,'timeout_seconds':None,
           'global_deadline_utc':None,'wall_clock_stop_disabled':True,'continuation_authorization':fid(ADDENDUM),
           'continuation_supervisor_source':fid(Path(__file__)),'terminal_native_scope':'physical worker exit; actual Vivado result retained in launcher_status.txt'}
    save(attempt/'status.json',value)
    print(json.dumps(dict(stage=stage,completed=True,exit_code=value['exit_code'],supervision_profile=SUPERVISION_PROFILE)),flush=True)
    return value


def main():
    global ACTIVE,ACTIVE_PROC
    if fid(ADDENDUM)['sha256']!=ADDENDUM_SHA:raise RuntimeError('continuation authorization identity changed')
    os.sched_setaffinity(0,CPUS);os.setpriority(os.PRIO_PROCESS,0,5)
    place_attempt=HERE.parent;place_report=HW/'vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt'
    for archived in (place_report/"stage_sources").iterdir():
        live=HW/"vivado/scripts"/archived.name
        if live.exists() and fid(live)["sha256"]!=fid(archived)["sha256"]:
            raise RuntimeError("frozen production source changed: "+str(live))
    metadata=json.loads((place_attempt/'started.json').read_text())
    if (place_attempt/'status.json').exists():raise RuntimeError('original stage already closed; do not adopt')
    before=dict(supervisor=exact(OLD_SUPERVISOR,OLD_SUPERVISOR_TICKS),worker=exact(LEADER,LEADER_TICKS),vivado=exact(VIVADO,VIVADO_TICKS))
    tracked={}
    for line in (place_attempt/'resources.jsonl').read_text().splitlines():
        tracked.update({int(pid):row['start_ticks'] for pid,row in json.loads(line)['processes'].items()})
    def external_signal(signum,frame):
        notice=dict(utc=utc(),signal=signum,policy='retain supervision; no implicit timed child cancellation')
        save(HERE/'external_signal.json',notice);print(json.dumps(notice),flush=True)
    signal.signal(signal.SIGTERM,external_signal);signal.signal(signal.SIGINT,external_signal)
    ready=dict(utc=utc(),watchdog=procstat(os.getpid()),source=fid(Path(__file__)),authorization=fid(ADDENDUM),
               supervision_profile=SUPERVISION_PROFILE,wall_clock_stop_disabled=True,timeout_seconds=None,
               original_started=fid(place_attempt/'started.json'),original_command=fid(place_attempt/'command.json'),
               original_budget=fid(place_attempt/'effective_budget.json'),before=before,first_resource_sample=sample(LEADER,tracked))
    save(HERE/'adoption_ready.json',ready)
    ACTIVE=('place',place_attempt,place_report,LEADER,tracked)
    proof=stop_supervisor(OLD_SUPERVISOR,OLD_SUPERVISOR_TICKS,LEADER,LEADER_TICKS)
    proof.update(utc=utc(),vivado_after=exact(VIVADO,VIVADO_TICKS),watchdog=procstat(os.getpid()),
        old_deadline_effective=False,old_supervisor_policy='stopped; never resumed; only single PID ended after live child tree closes',
        authorization=fid(ADDENDUM),supervision_profile=SUPERVISION_PROFILE,lane='original stopped supervisor retains exclusive flock')
    if proof['vivado_after']['state'] in {'T','t','Z','X'}:raise RuntimeError('Vivado not live across supervisor-only stop')
    save(HERE/'handoff_effective.json',proof)
    save(place_report/'runtime_supervision_override.json',dict(handoff=fid(HERE/'handoff_effective.json'),authorization=fid(ADDENDUM),timeout_seconds=None,global_deadline_utc=None,wall_clock_stop_disabled=True,supervision_profile=SUPERVISION_PROFILE))
    print(json.dumps(dict(handoff_effective=True,utc=utc(),watchdog_pid=os.getpid(),old_supervisor_state=proof['old_supervisor_after']['state'],worker_pid=LEADER,vivado_pid=VIVADO,wall_clock_stop_disabled=True)),flush=True)
    outcome=monitor('place',place_attempt,place_report,LEADER,tracked)
    # No active child remains now. SIGKILL only the stopped original supervisor:
    # Python finally cannot run; no signal is sent to the child process group.
    save(HERE/'worker_terminal_before_old_supervisor_release.json',dict(utc=utc(),outcome=outcome,active_owned=active_owned(LEADER,tracked),old_supervisor=exact(OLD_SUPERVISOR,OLD_SUPERVISOR_TICKS)))
    single_signal(OLD_SUPERVISOR,OLD_SUPERVISOR_TICKS,signal.SIGKILL)
    lane=(HW/'vivado/.m002_eda.lock').open('a+')
    fcntl.flock(lane,fcntl.LOCK_EX)  # never launch route without real lane ownership
    while managed.owned_processes(managed.process_table(),LEADER,tracked):time.sleep(.1)
    release=dict(utc=utc(),old_supervisor_after=procstat(OLD_SUPERVISOR),owned_after_release=[],new_lane_holder=procstat(os.getpid()),old_manager_exit_scope='administrative stopped-supervisor replacement, not native EDA failure/success')
    save(HERE/'old_supervisor_released.json',release)
    metadata.update(original_timeout_seconds=metadata['timeout_seconds'],original_supervisor_pid=OLD_SUPERVISOR,original_supervisor_release=fid(HERE/'old_supervisor_released.json'))
    place_status=close_status('place',place_attempt,metadata,outcome,LEADER)
    if place_status['exit_code']:return place_status['exit_code']
    # The unchanged physical worker independently validates native successful
    # physopt, complete POST, exact parent and new current supervisor status.
    route_attempt=RESULTS/'runs/R003/attempts/AT001_full_route';route_report=HW/'vivado/reports/m002_E003_R003_AT001_full_route'
    if route_attempt.exists() or route_report.exists():raise RuntimeError('route attempt/report already used')
    route_attempt.mkdir(parents=True)
    env={**os.environ,**metadata['environment'],'HAP_STAGE':'route','HAP_CURRENT_ATTEMPT_DIR':str(route_attempt),
         'HAP_REPORT_DIR':str(route_report),'HAP_PLACE_REPORT_DIR':str(place_report),
         'HAP_EXECUTION_PROFILE':profile.PROFILE,'OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'1'}
    for key in ('HAP_INIT_REPORT_DIR','HAP_OPT_REPORT_DIR','HAP_PRE_PLACE_REPORT_DIR'):env.pop(key,None)
    auth=profile.authorization(ROOT,'route',route_attempt,route_report);save(route_attempt/'execution_authorization.json',auth)
    cmd=['python3',str(HW/'vivado/scripts/run_m002_physical_stage.py'),'route']
    route_metadata={**metadata,'stage':'route','argv':cmd,'cwd':str(HW),'report':str(route_report),
        'environment':{k:v for k,v in env.items() if k.startswith('HAP_')},'started_utc':utc(),
        'execution_profile':profile.PROFILE,'supervision_profile':SUPERVISION_PROFILE,'timeout_seconds':None,
        'budget':{'fixed_wall_stops':'cancelled by user continuation instruction'},'continuation_authorization':fid(ADDENDUM),
        'authorization':fid(route_attempt/'execution_authorization.json'),'parent_place_status':fid(place_attempt/'status.json'),
        'continuation_supervisor_source':fid(Path(__file__))}
    for key in ('leader_pid','process_group','original_supervisor_pid','original_timeout_seconds','original_supervisor_release'):route_metadata.pop(key,None)
    save(route_attempt/'command.json',route_metadata)
    def prepare():os.setsid();os.sched_setaffinity(0,CPUS);os.setpriority(os.PRIO_PROCESS,0,5)
    with (route_attempt/'launcher.log').open('w') as log:
        proc=subprocess.Popen(cmd,cwd=HW,env=env,stdout=log,stderr=subprocess.STDOUT,preexec_fn=prepare)
        ACTIVE=('route',route_attempt,route_report,proc.pid,{})
        ACTIVE_PROC=proc
        route_metadata.update(supervisor_pid=os.getpid(),leader_pid=proc.pid,process_group=proc.pid)
        save(route_attempt/'started.json',route_metadata)
        print(json.dumps(dict(route_worker_started=True,pid=proc.pid,utc=utc(),wall_clock_stop_disabled=True)),flush=True)
        route_outcome=monitor(*ACTIVE,proc=proc)
        proc.wait()
        route_status=close_status('route',route_attempt,route_metadata,route_outcome,proc.pid)
    save(HERE/'continuation_chain_status.json',dict(execution_state='completed',ended_utc=utc(),place_status=fid(place_attempt/'status.json'),route_status=fid(route_attempt/'status.json'),exit_code=route_status['exit_code'],scope='actual worker exits; route evidence must independently prove all native and POST/full-routing requirements'))
    return route_status['exit_code']


if __name__=='__main__':
    try:
        result=main()
    except Exception as exc:
        error=dict(utc=utc(),error=f'{type(exc).__name__}: {exc}',policy='no old deadline resumed; retain resource-only supervision of any active same child')
        print(json.dumps(error),flush=True)
        try:save(HERE/'watchdog_main_exception.json',error)
        except Exception:pass
        if ACTIVE is not None and active_owned(ACTIVE[3],ACTIVE[4]):
            outcome=monitor(*ACTIVE,proc=ACTIVE_PROC)
            save(HERE/'emergency_resource_supervision_terminal.json',dict(utc=utc(),outcome=outcome,scope='native child finished after watchdog control exception; no completion or route inferred'))
        raise SystemExit(125)
    raise SystemExit(result)
