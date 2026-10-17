#!/usr/bin/env python3
"""Prepared lean E006 read-only alternative; never controls or edits original AT001."""
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

CONTRACT = ROOT/'mission/M002_ddr_separation_and_timing_recovery/slr1_attribution_contract_2026-10-16.md'
EXPECTED_CONTRACT_SHA='cf53ff562b1894620ab0d6cc4398e17718cf815b32b8d2d8fd491adb17754263'
FREEZE = ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'
PARENT = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
RUNS = ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs'
DCPS = {'place': '32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2',
        'physopt': '766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d'}
LEGACY_CPU_RECEIPTS = {
    'AT007_supervision_recovery_cpu': (
        'c242d3517622c92d48e74b9e5560a4d25f7249ed3f2308d7986a051422123cbe',
        '4307348d3f841b933e54f6a6d1e2ff922a821c59c4a0c6f9080e192b289e72bd',
        'CPU only; no EDA'),
    'AT008_supervision_recovery_cpu_cwd': (
        '2981985181dc65ebc5ffb70807930e3d6d3f1f0d83ebfca1f590c02a8c16f569',
        '8d9afcdd3e5c2cffa718f5c6bd226fe5f5058393639408d7e5d937603c2f8763',
        'CPU only; no EDA; same regression scope with corrected package cwd'),
}


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


def still_live(identities):
    result = []
    for pid, start in identities.items():
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            if int(fields[19]) == start and fields[0] != 'Z':
                result.append(dict(pid=int(pid),start_ticks=start,state=fields[0]))
        except FileNotFoundError: pass
    return result




def prior_registered_identities(status, original, extra=None):
    registered = {}
    def add(pid, start):
        pid = str(pid)
        require(pid.isdigit() and int(pid) > 0 and type(start) is int and start > 0,
                'Invalid recorded process identity')
        require(pid not in registered or registered[pid] == start, 'Conflicting recorded process identity')
        registered[pid] = start
    for pid, start in status.get('tracked_identities', {}).items(): add(pid, start)
    for record in (status, original):
        for role in ('leader', 'supervisor'):
            if record.get(role+'_pid') is not None and record.get(role+'_start_ticks') is not None:
                add(record[role+'_pid'], record[role+'_start_ticks'])
    for pid, start in (extra or {}).items(): add(pid, start)
    return registered


def require_registered_closed(registered):
    require(bool(registered), 'No recorded prior ownership identity')
    live = still_live(registered)
    require(not live, f'Registered prior owned process remains live: {live}')
    return live








def verify_external_inputs(expected):
    actual={key:identity(row['path']) for key,row in expected.items()}
    require(actual == expected,'external source/target changed')
    return actual


def interrupted(signum, frame): raise KeyboardInterrupt(f'signal {signum}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve()
    authorization_path=args.authorization.resolve()
    authorization=json.loads(authorization_path.read_text())
    require(authorization.get('execution_authorized') is True,'No actual replacement execution authorization')
    require(authorization.get('decision') == 'allow_readonly_lean_replacement','Wrong replacement decision')
    approval_evidence=authorization['decision_evidence']
    require(identity(approval_evidence['path']) == approval_evidence,'Replacement decision evidence identity changed')
    batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts'
    require(attempt.parent==batch and attempt.name.startswith('AT'),'wrong E006 batch')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R001_'),'wrong E006 report root')
    require(not attempt.exists() and not report.exists(),'attempt/report already used')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    lock=(ROOT/'project/hardware/vivado/.m002_eda.lock').open('r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    require(identity(CONTRACT)['sha256']==EXPECTED_CONTRACT_SHA,'changed E006 contract')
    prior=RUNS/'R006/attempts/AT003_new_peak_windows_readonly'
    prior_status=closed_status(prior/'status.json','readonly_physical_comparison',True)
    require(json.loads((prior/'readonly_terminal_facts.json').read_text())['engineering_execution_verified'],'prior closeout unverified')
    prior_ids=prior_registered_identities(prior_status,json.loads((prior/'started.json').read_text()));require_registered_closed(prior_ids)
    source_dir=Path(__file__).resolve().parent
    reuse=json.loads((source_dir/'reuse_manifest.json').read_text())
    original=Path(reuse['original_attempt'])
    original_status=json.loads((original/'status.json').read_text())
    require(authorization['prior_terminal_status'] == identity(original/'status.json'),'Original terminal is not the authorized closed status')
    require(original_status['execution_state']=='completed' and not original_status['owned_survivors'],'Original attempt not closed')
    if original_status['stop_reason'] is not None:
        require(authorization.get('approval_kind') == 'user_explicit_controlled_stop','Original non-natural stop lacks explicit user decision')
    else:
        require(original_status['native_natural_terminal_observed'],'Original terminal not naturally observed')
    for p in sorted(batch.glob('AT*/started.json')):
        ended=p.parent/'status.json';require(ended.exists(),'prior E006 attempt unclosed')
        status=json.loads(ended.read_text())
        require(status['execution_state']=='completed' and not status['owned_survivors'],'prior E006 owner not closed')
        require(status['stop_reason'] is None or p.parent==original,'Unrelated prior E006 stop is not authorized')
        require_registered_closed(prior_registered_identities(status,json.loads(p.read_text())))
    reused_inputs=reuse['artifacts']
    require(all(identity(row['path'])==row for row in reused_inputs.values()),'Reused closed input changed')
    import csv
    with (Path(reuse['original_report'])/'query_receipts.tsv').open() as stream:
        observed={row['query']:row for row in csv.DictReader(stream,delimiter='\t')}
    require(all(observed.get(row['query'])==row and row['native_tcl_code']=='0' for row in reuse['required_closed_query_receipts']),'Reused query did not close unchanged')
    checkpoint=identity(PARENT/'physopt.dcp');require(checkpoint['sha256']==DCPS['physopt'],'changed source physopt DCP')
    checkpoints={'physopt':checkpoint}
    before_freeze=freeze_check();source_dir=Path(__file__).resolve().parent
    target_manifest=json.loads((source_dir/'targets_manifest.json').read_text())
    require(identity(target_manifest['targets_tcl']['path'])==target_manifest['targets_tcl'],'changed compiled query targets')
    external_inputs=target_manifest['external_inputs']
    require(all(identity(row['path'])==row for row in external_inputs.values()),'changed query target/source input')
    require(guard.mem_available()>=48*guard.GIB and shutil.disk_usage(ROOT).free>=30*guard.GIB,'resource reserve unavailable')
    attempt.mkdir(parents=True);report.mkdir(parents=True);archive=attempt/'sources';archive.mkdir()
    names=['attribution_lean.tcl','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]
    for name in names:shutil.copy2(source_dir/name,archive/name)
    source_bindings=[identity(p) for p in sorted(archive.iterdir())]
    inputs=dict(contract=identity(CONTRACT),checkpoint=checkpoint,checkpoints=checkpoints,
        closed_physopt_status=identity(RUNS/'R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/status.json'),
        prior_readonly_status=identity(prior/'status.json'),prior_readonly_terminal=identity(prior/'readonly_terminal_facts.json'),
        prior_registered_identities=prior_ids,external_inputs=external_inputs,reused_closed_inputs=reused_inputs,replacement_authorization=identity(authorization_path),original_attempt_terminal=identity(original/'status.json'),
        frozen_inputs=before_freeze,sources=source_bindings,resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save(attempt/'input_bindings.json',inputs)
    cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
        '-source',str(archive/'attribution_lean.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    env={k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_SUPPLEMENT_','E006_'))}
    env.update(E006_DCP=str(checkpoint['path']),E006_OUT=str(report),E006_TARGETS=str(archive/'targets.tcl'),
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    supervisor_start=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    metadata=dict(stage='readonly_slr1_attribution_lean',started_utc=utc(),supervisor_pid=os.getpid(),supervisor_start_ticks=supervisor_start,
        argv=cmd,cwd=str(report),report=str(report),project=str(ROOT/'project/hardware/vivado/project/m002_E005_R002_AT006_fresh'),
        cpu_affinity=list(range(8)),nice=5,max_threads=8,timeout_seconds=None,no_output_timeout_seconds=None,
        wall_clock_stop_disabled=True,rss_limit_bytes=192*guard.GIB,mem_available_floor_bytes=48*guard.GIB,
        mem_low_grace_seconds=30,disk_free_floor_bytes=30*guard.GIB,inputs=identity(attempt/'input_bindings.json'),
        environment={k:v for k,v in env.items() if k.startswith('E006_')})
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
        natural_terminal = proc is not None and proc.poll() is not None
        before_cleanup = guard.owned_processes(guard.process_table(),proc.pid,tracked) if proc else {}
        cleanup_required = bool(proc and (stop is not None or not natural_terminal or before_cleanup))
        if cleanup_required:
            if stop is None: stop='unexpected_owned_processes_after_native_terminal'
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        else:
            native,before,remain=(proc.wait(),[],[]) if proc else (None,[],[])
        # A live survivor keeps the lane occupied; never release it as a success.
        while remain:
            stop=stop or 'owned_process_cleanup_incomplete'
            observation=dict(observed_utc=utc(),execution_state='cleanup_pending',owned_survivors=remain,
                native_exit_code=native,stop_reason=stop,lane_lock_held=True)
            with (attempt/'cleanup_history.jsonl').open('a') as stream: stream.write(json.dumps(observation)+'\n')
            save(attempt/'cleanup_pending.json',observation)
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        rc=native if stop is None and native is not None else 125
        post_error=None
        try:
            after_freeze=freeze_check()
            require({p:identity(row['path']) for p,row in checkpoints.items()} == checkpoints,'source checkpoint changed')
            require([identity(row['path']) for row in source_bindings] == source_bindings,'archived query changed')
            verify_external_inputs(external_inputs)
            require({p:identity(row['path']) for p,row in reused_inputs.items()} == reused_inputs,'reused closed input changed')
            require(identity(authorization_path)==inputs['replacement_authorization'],'replacement authorization changed')
        except Exception as exc:
            after_freeze=None;post_error=f'{type(exc).__name__}: {exc}';rc=rc or 1
        status=dict(**metadata,ended_utc=utc(),execution_state='completed',native_exit_code=native,exit_code=rc,
            stop_reason=stop,max_tree_rss_bytes=peak,minimum_mem_available_bytes=min_mem,minimum_disk_free_bytes=min_disk,
            tracked_identities=tracked,owned_before_reap=before,owned_survivors=remain,
            native_natural_terminal_observed=natural_terminal,cleanup_was_required=cleanup_required,
            owned_before_cleanup=before_cleanup,
            post_integrity_error=post_error,frozen_inputs_after=after_freeze,physical_commands_executed=False,checkpoint_write_executed=False)
        save(attempt/'status.json',status)
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        print(json.dumps(dict(completed=True,exit_code=rc,native_exit_code=native,stop_reason=stop,survivors=remain)),flush=True)
    return rc


if __name__ == '__main__': raise SystemExit(main())
