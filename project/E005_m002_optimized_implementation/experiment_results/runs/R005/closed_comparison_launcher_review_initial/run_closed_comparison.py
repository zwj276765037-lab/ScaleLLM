#!/usr/bin/env python3
"""One supervised read-only native session, after the authorized route terminates."""
from pathlib import Path
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'project/hardware/vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import run_m002_no_wall as guard
import m002_physical_evidence as evidence

CONTRACT = ROOT/'mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md'
FREEZE = ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'
PARENT = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
RUNS = ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs'
DCPS = {'place': '32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2',
        'physopt': '766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d'}


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()


def require(value, message):
    if not value: raise ValueError(message)


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(4*1024*1024), b''): digest.update(data)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def save(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2)+'\n');tmp.replace(path)


def freeze_check():
    require(identity(FREEZE)['sha256'] == 'a5643a9e8adb13d6e76f3e78b2dfb6804b9b8ac193f7006f5ceff1b0c4f5a26f', 'changed freeze')
    rows = json.loads(FREEZE.read_text())['files']
    require(len(rows) == 144, 'wrong production freeze size')
    for row in rows: require(identity(row['path']) == row, f"Changed production input: {row['path']}")
    return dict(freeze=identity(FREEZE), verified_files=len(rows), unchanged=True)


def closed_status(path, stage, success=False):
    status = json.loads(path.read_text())
    require(status['stage'] == stage and status['execution_state'] == 'completed' and
            status['stop_reason'] is None and not status['owned_survivors'], 'unclosed/abnormally stopped physical stage')
    require(status['native_exit_code'] in ({0} if success else {0,1}) and
            status['exit_code'] in ({0} if success else {0,1}) and
            status['exit_code'] >= status['native_exit_code'], 'unqualified terminal status')
    return status


def tcl(value):
    require(not any(c in str(value) for c in '{}\r\n'), 'unsupported Tcl path')
    return '{'+str(value)+'}'


def interrupted(signum, frame): raise KeyboardInterrupt(f'signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--route-attempt', type=Path, required=True)
    args = parser.parse_args()
    attempt, report, route = [p.resolve() for p in (args.attempt,args.report,args.route_attempt)]
    require(attempt.parent == RUNS/'R006/attempts' and attempt.name.startswith('AT'), 'wrong supplement batch')
    require(report.parent == ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E005_R006_'), 'wrong report root')
    require(route.parent == RUNS/'R004/attempts', 'foreign route attempt')
    require(not attempt.exists() and not report.exists(), 'attempt/report already used')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    lock = (ROOT/'project/hardware/vivado/.m002_eda.lock').open('r')
    fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(identity(CONTRACT)['sha256'] == '0de96ef2e741f3fb18005af5d4fed2137b4a15a71915f2d490bbb6d7e1e529f6','changed contract')
    route_status = closed_status(route/'status.json','route')
    parent = json.loads((PARENT/'diagnostic_evidence.json').read_text())
    closed_status(Path(parent['managed_attempt'])/'status.json','place',True)
    project = Path(parent['project'])
    accepted = evidence.parent_place(PARENT/'diagnostic_evidence.json',project,parent['synthesis'])
    route_command = json.loads((Path(route_status['report'])/'command.json').read_text())
    require(route_command['stage'] == 'route' and route_command['managed_attempt'] == str(route) and
            route_command['environment']['HAP_PLACE_REPORT_DIR'] == str(PARENT) and
            route_command['synthesis'] == parent['synthesis'], 'route has different parent')
    checkpoints = {phase:identity(PARENT/(phase+'.dcp')) for phase in DCPS}
    for phase, row in checkpoints.items(): require(row['sha256'] == DCPS[phase], 'changed closed phase DCP')
    require(accepted['checkpoint'] == checkpoints['physopt'], 'wrong admitted physopt DCP')
    before_freeze = freeze_check()
    require(guard.mem_available() >= 48*guard.GIB and shutil.disk_usage(ROOT).free >= 30*guard.GIB,'resource reserve unavailable')
    attempt.mkdir(parents=True);report.mkdir(parents=True)
    archive = attempt/'sources';archive.mkdir()
    source_dir = Path(__file__).resolve().parent
    names = ['readonly_two_phase_driver.tcl','readonly_physical_supplement.tcl','targets.tcl',Path(__file__).name]
    for name in names: shutil.copy2(source_dir/name,archive/name)
    jobs = 'set jobs [list '+ ' '.join('[list '+tcl(p)+' '+tcl(checkpoints[p]['path'])+' '+tcl(report/p)+']' for p in ('place','physopt'))+']\n'
    (archive/'jobs.tcl').write_text(jobs)
    source_bindings = [identity(p) for p in sorted(archive.iterdir())]
    inputs = dict(contract=identity(CONTRACT), checkpoints=checkpoints,
        parent=identity(PARENT/'diagnostic_evidence.json'), parent_status=identity(Path(parent['managed_attempt'])/'status.json'),
        parent_integrity=parent['integrity'], parent_constraints=parent['constraints'],
        phase_integrities={p:identity(PARENT/('integrity_'+p+'.json')) for p in DCPS},
        phase_commands={p:identity(PARENT/(p+'_command_result.txt')) for p in DCPS},
        route_status=identity(route/'status.json'), route_command=identity(Path(route_status['report'])/'command.json'),
        placed_reference=identity(RUNS/'R005/AT003_placed_driver_sites_for_device_mapping.json'),
        frozen_inputs=before_freeze, sources=source_bindings, resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save(attempt/'input_bindings.json',inputs)
    cmd = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
           '-source',str(archive/'readonly_two_phase_driver.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    env = {k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_SUPPLEMENT_'))}
    env.update(E005_SUPPLEMENT_JOBS=str(archive/'jobs.tcl'), E005_SUPPLEMENT_CORE=str(archive/'readonly_physical_supplement.tcl'),
        E005_SUPPLEMENT_TARGETS=str(archive/'targets.tcl'),E005_SUPPLEMENT_MASTER_OUT=str(report),
        PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    metadata = dict(stage='readonly_physical_comparison',started_utc=utc(),supervisor_pid=os.getpid(),argv=cmd,
        cwd=str(report),report=str(report),project=str(project),cpu_affinity=list(range(8)),nice=5,max_threads=8,
        timeout_seconds=None,no_output_timeout_seconds=None,wall_clock_stop_disabled=True,
        rss_limit_bytes=192*guard.GIB,mem_available_floor_bytes=48*guard.GIB,mem_low_grace_seconds=30,
        disk_free_floor_bytes=30*guard.GIB,inputs=identity(attempt/'input_bindings.json'),
        environment={k:v for k,v in env.items() if k.startswith('E005_SUPPLEMENT_')})
    save(attempt/'command.json',metadata)
    proc=None;tracked={};stop=None;peak=0;low_since=None
    min_mem=guard.mem_available();min_disk=shutil.disk_usage(ROOT).free;begin=time.monotonic()
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        with (attempt/'launcher.log').open('x') as log,(attempt/'resources.jsonl').open('x',buffering=1) as resources:
            proc=subprocess.Popen(cmd,cwd=report,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            metadata.update(leader_pid=proc.pid,process_group=proc.pid)
            save(attempt/'started.json',metadata)
            print(json.dumps(dict(started=True,supervisor_pid=os.getpid(),leader_pid=proc.pid,attempt=str(attempt))),flush=True)
            while True:
                rows=guard.owned_processes(guard.process_table(),proc.pid,tracked)
                for pid in rows:
                    try:
                        if not os.sched_getaffinity(pid).issubset(range(8)): os.sched_setaffinity(pid,set(range(8)))
                    except ProcessLookupError: pass
                rss=sum(r['rss_bytes'] for r in rows.values());mem=guard.mem_available();disk=shutil.disk_usage(ROOT).free
                peak=max(peak,rss);min_mem=min(min_mem,mem);min_disk=min(min_disk,disk)
                resources.write(json.dumps(dict(utc=utc(),elapsed_seconds=time.monotonic()-begin,rss_bytes=rss,
                    mem_available_bytes=mem,disk_free_bytes=disk,processes=rows))+'\n')
                low_since=(low_since if low_since is not None else time.monotonic()) if mem < 48*guard.GIB else None
                if rss > 192*guard.GIB: stop='task_tree_rss_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since >= 30: stop='MemAvailable_below_48GiB_30s'
                elif disk < 30*guard.GIB: stop='disk_free_below_30GiB'
                if proc.poll() is not None or stop: break
                time.sleep(5)
    except BaseException as exc: stop=f'{type(exc).__name__}:{exc}'
    finally:
        native,before,remain=guard.terminate_and_reap(proc,tracked) if proc else (None,[],[])
        rc=native if stop is None and native is not None else 125
        post_error=None
        try:
            after_freeze=freeze_check()
            require({p:identity(row['path']) for p,row in checkpoints.items()} == checkpoints,'source checkpoint changed')
            require([identity(row['path']) for row in source_bindings] == source_bindings,'archived query changed')
        except Exception as exc:
            after_freeze=None;post_error=f'{type(exc).__name__}: {exc}';rc=rc or 1
        status=dict(**metadata,ended_utc=utc(),execution_state='completed',native_exit_code=native,exit_code=rc,
            stop_reason=stop,max_tree_rss_bytes=peak,minimum_mem_available_bytes=min_mem,minimum_disk_free_bytes=min_disk,
            tracked_identities=tracked,owned_before_reap=before,owned_survivors=remain,
            post_integrity_error=post_error,frozen_inputs_after=after_freeze,physical_commands_executed=False,checkpoint_write_executed=False)
        save(attempt/'status.json',status)
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        print(json.dumps(dict(completed=True,exit_code=rc,native_exit_code=native,stop_reason=stop,survivors=remain)),flush=True)
    return rc


if __name__ == '__main__': raise SystemExit(main())
