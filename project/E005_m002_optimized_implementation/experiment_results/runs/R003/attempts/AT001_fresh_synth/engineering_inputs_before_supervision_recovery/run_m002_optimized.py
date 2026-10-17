#!/usr/bin/env python3
"""E005 single EDA lane, explicit authorization and resource guards, no wall limit."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import m002_execution_profile as policy
import run_m002_no_wall as guard

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['preflight','xsim','create','synth','place','route'])
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--synth-report', type=Path)
    parser.add_argument('--synth-attempt', type=Path)
    parser.add_argument('--place-report', type=Path)
    parser.add_argument('--command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    attempt, report = args.attempt.resolve(), args.report.resolve()
    project = (args.project or ROOT/'vivado/project/m002_E005_preflight').resolve()
    auth = policy.authorization(ROOT.parent.parent, args.stage, attempt, report, policy.OPTIMIZED_PROFILE)
    policy.check(not attempt.exists() and not report.exists(), 'attempt/report already used')
    policy.check(report.is_relative_to(ROOT/'vivado/reports') and project.is_relative_to(ROOT/'vivado/project'), 'foreign project/report')
    policy.check(args.stage != 'create' or not project.exists(), 'fresh project already exists')
    if args.stage in {'place','route'}:
        policy.check(args.synth_report and args.synth_attempt and args.project, 'physical stage needs actual synthesis identity')
    if args.stage == 'route':
        policy.check(args.place_report, 'route needs successful new place/physopt parent')
    policy.check(not args.command or args.stage in {'preflight','xsim'}, 'custom command restricted to preflight/xsim')
    policy.check(args.stage not in {'preflight','xsim'} or args.command, 'preflight/xsim command missing')
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    policy.check(guard.mem_available() >= 48*guard.GIB and shutil.disk_usage(ROOT).free >= 30*guard.GIB, 'resource reserve unavailable')
    lock = (ROOT/'vivado/.m002_eda.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Closed attempts are not inferred from an idle terminal or elapsed time.
    for prior in (ROOT.parent/'E005_m002_optimized_implementation/experiment_results/runs').glob('R*/attempts/AT*/started.json'):
        ended = prior.parent/'status.json'
        policy.check(ended.is_file(), f'unclosed E005 attempt: {prior.parent}')
        state = json.loads(ended.read_text())
        policy.check(not state.get('owned_survivors'), f'owned E005 survivors: {prior.parent}')
    attempt.mkdir(parents=True)
    env = {k:v for k,v in os.environ.items() if not k.startswith('HAP_')}
    env.update(HAP_JOBS='8', HAP_SYNTH_JOBS='1', HAP_NICE_INCREMENT='0',
               HAP_PROJECT_DIR=str(project), HAP_REPORT_DIR=str(report),
               HAP_CURRENT_ATTEMPT_DIR=str(attempt), HAP_EXECUTION_PROFILE=policy.OPTIMIZED_PROFILE,
               HAP_SUPERVISION_PROFILE=policy.OPTIMIZED_PROFILE, HAP_XSIM_TIMEOUT_SECONDS='0',
               HAP_XSIM_REPORT_DIR=str(report), OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='1')
    for name, value in [('HAP_SYNTH_REPORT_DIR',args.synth_report),('HAP_SYNTH_ATTEMPT_DIR',args.synth_attempt),('HAP_PLACE_REPORT_DIR',args.place_report)]:
        if value: env[name] = str(value.resolve())
    if args.command:
        cmd = args.command
    elif args.stage in {'place','route'}:
        cmd = [sys.executable,str(ROOT/'vivado/scripts/run_m002_physical_stage.py'),args.stage]
    else:
        cmd = [str(ROOT/'vivado/scripts/run_vcu118_board.sh'),args.stage]
    if args.stage == 'preflight': report.mkdir(parents=True)
    policy.save(attempt/'execution_authorization.json',auth)
    command_inputs = [policy.identity(Path(p).resolve()) for p in cmd if Path(p).is_file()]
    metadata = dict(stage=args.stage, argv=cmd, cwd=str(ROOT), project=str(project), report=str(report),
        execution_profile=policy.OPTIMIZED_PROFILE, authorization=policy.identity(attempt/'execution_authorization.json'),
        supervisor=policy.identity(Path(__file__)), contract=auth['contract'], command_inputs=command_inputs,
        environment={k:v for k,v in env.items() if k.startswith('HAP_')},
        cpu_affinity=list(range(8)), nice=5, timeout_seconds=None, no_output_timeout_seconds=None,
        wall_clock_stop_disabled=True, global_deadline_utc=None, rss_limit_bytes=192*guard.GIB,
        mem_available_floor_bytes=48*guard.GIB, mem_low_grace_seconds=30,
        disk_free_floor_bytes=30*guard.GIB, started_utc=guard.utc())
    policy.save(attempt/'command.json',metadata)
    proc = None; tracked = {}; stopped = None; peak = 0; low_since = None
    minimum_mem = guard.mem_available(); minimum_disk = shutil.disk_usage(ROOT).free
    begin = time.monotonic()
    def interrupted(signum, frame): raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGINT,interrupted); signal.signal(signal.SIGTERM,interrupted)
    try:
        with (attempt/'launcher.log').open('w') as log, (attempt/'resources.jsonl').open('w',buffering=1) as resources:
            proc = subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            metadata.update(supervisor_pid=os.getpid(),leader_pid=proc.pid,process_group=proc.pid)
            policy.save(attempt/'started.json',metadata)
            print(json.dumps(dict(started=True,stage=args.stage,supervisor_pid=os.getpid(),leader_pid=proc.pid,attempt=str(attempt))),flush=True)
            while True:
                rows = guard.owned_processes(guard.process_table(),proc.pid,tracked)
                for pid in rows:
                    try:
                        if not os.sched_getaffinity(pid).issubset(range(8)): os.sched_setaffinity(pid,set(range(8)))
                    except ProcessLookupError: pass
                rss = sum(x['rss_bytes'] for x in rows.values())
                mem = guard.mem_available(); disk = shutil.disk_usage(ROOT).free
                peak=max(peak,rss);minimum_mem=min(minimum_mem,mem);minimum_disk=min(minimum_disk,disk)
                resources.write(json.dumps(dict(utc=guard.utc(),elapsed_seconds=time.monotonic()-begin,rss_bytes=rss,
                    mem_available_bytes=mem,disk_free_bytes=disk,processes=rows))+'\n')
                low_since = (low_since if low_since is not None else time.monotonic()) if mem < 48*guard.GIB else None
                if rss > 192*guard.GIB: stopped='task_tree_rss_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since >= 30: stopped='MemAvailable_below_48GiB_30s'
                elif disk < 30*guard.GIB: stopped='disk_free_below_30GiB'
                if proc.poll() is not None or stopped: break
                time.sleep(5)
    except BaseException as exc: stopped=f'{type(exc).__name__}:{exc}'
    finally:
        native,before,remaining = guard.terminate_and_reap(proc,tracked) if proc else (None,[],[])
        rc = native if stopped is None and native is not None else 125
        policy.save(attempt/'status.json',dict(**metadata,execution_state='completed',ended_utc=guard.utc(),
            native_exit_code=native,exit_code=rc,stop_reason=stopped,max_tree_rss_bytes=peak,
            minimum_mem_available_bytes=minimum_mem,minimum_disk_free_bytes=minimum_disk,
            tracked_identities=tracked,owned_before_reap=before,owned_survivors=remaining))
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        print(json.dumps(dict(completed=True,stage=args.stage,exit_code=rc,stop_reason=stopped,survivors=remaining)),flush=True)
    return rc


if __name__ == '__main__': raise SystemExit(main())
