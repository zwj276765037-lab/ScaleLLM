#!/usr/bin/env python3
"""Prepared R005 directed candidate comparison. No queued or automatic launch."""
from pathlib import Path
import argparse
import datetime as dt
import csv
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SCRIPTS=ROOT/'project/hardware/vivado/scripts'
sys.path.insert(0,str(ROOT/'agent/A006/E006_lean_candidate'))
from run_attribution_lean import identity,freeze_check,prior_registered_identities,require_registered_closed,require,utc,save
sys.path.insert(0,str(SCRIPTS))
import run_m002_no_wall as guard
CONTRACT=ROOT/'mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md'
PARENT=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
PRIOR=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts/AT001_exact_candidate_comparison'
E006=ROOT/'project/E006_m002_slr1_congestion_attribution'


def interrupted(signum,frame):raise KeyboardInterrupt(f'signal {signum}')


def require_fresh_or_planned_attempt(attempt,report):
    require(not report.exists(),'Report already contains evidence')
    if not attempt.exists():return None
    import re
    match=re.fullmatch(r'(AT[0-9]{3})_(.+)',attempt.name)
    require(match and attempt.is_dir() and not attempt.is_symlink(),'Invalid planned attempt')
    require({p.name for p in attempt.iterdir()}=={'run.json','report.md','evidence'},'Attempt already contains runtime products')
    for name in ['run.json','report.md']:
        require((attempt/name).is_file() and not (attempt/name).is_symlink(),'Invalid planned metadata')
    require((attempt/'evidence').is_dir() and not (attempt/'evidence').is_symlink() and not any((attempt/'evidence').iterdir()),'Planned evidence is not empty')
    expected=dict(execution_state='planned',schema=1,id=match[1],experiment='E006',run='R005',title=match[2])
    require(json.loads((attempt/'run.json').read_text())==expected,'Wrong planned R005 metadata')
    require((attempt/'report.md').read_text()=='# '+match[1]+' · '+match[2]+'\n\n记录目的、实际结果、适用范围、限制及原始证据。登记不代表已执行或通过。\n','Planned report changed')
    return dict(run=identity(attempt/'run.json'),report=identity(attempt/'report.md'),evidence_empty=True)


def verify_external_inputs(expected):
    actual={key:identity(row['path']) for key,row in expected.items()}
    require(actual==expected,'External directed scope/protocol/target/evidence changed')
    return actual


def verify_preparation():
    path=HERE/'prepared_source_manifest.json'
    require(path.is_file(),'Directed source/protocol has not been admitted')
    manifest=json.loads(path.read_text())
    require(manifest.get('status')=='CPU_PREPARED_NOT_EXECUTED' and manifest.get('EDA_executed') is False,'Not an unexecuted preparation manifest')
    require(manifest.get('exporter_protocol_complete') is True,'Directed exporter protocol/source incomplete')
    for row in manifest['source_files']+manifest['CPU_checks']:
        require(identity(row['path'])==row,'Prepared source/check changed')
    verify_external_inputs(manifest['external_inputs'])
    require(manifest['scope_revision']==identity(CONTRACT),'Wrong actual scope revision')
    return manifest


def actual_prior_closure(authorization):
    row=authorization['prior_terminal_status'];require(identity(row['path'])==row and Path(row['path'])==PRIOR/'status.json','Wrong actual R004 terminal')
    status=json.loads(Path(row['path']).read_text());started=json.loads((PRIOR/'started.json').read_text())
    require(status.get('execution_state')=='completed' and not status.get('owned_survivors'),'R004 has not actually closed')
    require_registered_closed(prior_registered_identities(status,started))
    facts_row=authorization['prior_terminal_facts'];require(identity(facts_row['path'])==facts_row,'Prior terminal audit changed')
    facts=json.loads(Path(facts_row['path']).read_text());require(facts['status']==row,'Prior audit does not bind actual terminal')
    closure_checks=['no_survivors','no_original_live','lane_released','production_144_unchanged','source_physopt_DCP_unchanged',
        'archived_8_sources_unchanged','all_bound_external_targets_sources_unchanged','all_bound_reused_closed_inputs_unchanged',
        'replacement_authorization_unchanged','contract_unchanged','resource_helper_unchanged','no_post_integrity_error',
        'wrapper_after_freeze_agrees','no_physical_commands','no_checkpoint_write','resource_extrema_agree']
    require(all(facts['checks'].get(key) is True for key in closure_checks),'Prior R004 ownership/integrity closure is incomplete')
    if status['stop_reason'] is None:
        require(status['native_natural_terminal_observed'],'R004 natural terminal not observed')
    else:
        stop_row=authorization.get('controlled_stop_evidence')
        require(stop_row and identity(stop_row['path'])==stop_row,'A new explicit R004 user stop exception is required')
        stop=json.loads(Path(stop_row['path']).read_text())
        require(stop.get('approval_kind')=='user_explicit_controlled_stop' and stop.get('authorized_stop_attempt')==str(PRIOR),
                'This stop is not explicitly authorized for the current R004 attempt')
    # All real previous E006 owners must have gone, including historical R001.
    for path in sorted((E006/'experiment_results/runs').glob('R*/attempts/AT*/started.json')):
        terminal=path.parent/'status.json';require(terminal.is_file(),'A previous E006 owner is unclosed')
        ended=json.loads(terminal.read_text());require(ended.get('execution_state')=='completed' and not ended.get('owned_survivors'),'Prior E006 owns processes')
        require_registered_closed(prior_registered_identities(ended,json.loads(path.read_text())))
    return dict(status=row,facts=facts_row)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve();authorization_path=args.authorization.resolve()
    require(attempt.parent==E006/'experiment_results/runs/R005/attempts','Wrong R005 attempt root')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R005_'),'Wrong R005 report root')
    planned_scaffold=require_fresh_or_planned_attempt(attempt,report)
    manifest=verify_preparation()
    authorization=json.loads(authorization_path.read_text())
    require(authorization.get('execution_authorized') is True and authorization.get('decision')=='readonly_two_candidate_directed_cut','No actual R005 directed execution binding')
    require(authorization.get('scope_revision')==identity(CONTRACT),'Execution binding does not adopt actual scope revision')
    require(authorization.get('prepared_source_manifest')==identity(HERE/'prepared_source_manifest.json'),'Wrong actual source binding')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    # Nonblocking: never queue behind or control R004.
    lock=(ROOT/'project/hardware/vivado/.m002_eda.lock').open('r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    prior_closure=actual_prior_closure(authorization)
    before_freeze=freeze_check();checkpoint=identity(PARENT/'physopt.dcp')
    require(checkpoint['sha256']=='766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d','Wrong source physopt graph')
    checkpoints={'physopt':checkpoint}
    reuse=json.loads((HERE/'reuse_manifest.json').read_text());reused_inputs=reuse['artifacts']
    verify_external_inputs(reused_inputs)
    external_inputs=dict(manifest['external_inputs'])
    for key,row in authorization.items():
        if isinstance(row,dict) and {'path','bytes','sha256'}.issubset(row):external_inputs['execution_binding_'+key]=row
    verify_external_inputs(external_inputs)
    require(guard.mem_available()>=48*guard.GIB and shutil.disk_usage(ROOT).free>=30*guard.GIB,'Resource reserve unavailable')
    planned_scaffold=require_fresh_or_planned_attempt(attempt,report)
    attempt.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True);archive=attempt/'sources';archive.mkdir()
    for name in manifest['runtime_source_names']:shutil.copy2(HERE/name,archive/name)
    source_bindings=[identity(p) for p in sorted(archive.iterdir())]
    inputs=dict(contract=identity(CONTRACT),checkpoint=checkpoint,checkpoints=checkpoints,planned_management_scaffold=planned_scaffold,
        prior_R004_closure=prior_closure,external_inputs=external_inputs,reused_closed_inputs=reused_inputs,
        replacement_authorization=identity(authorization_path),preparation_manifest=identity(HERE/'prepared_source_manifest.json'),
        frozen_inputs=before_freeze,sources=source_bindings,resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save(attempt/'input_bindings.json',inputs)
    cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
        '-source',str(archive/'attribution_directed.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    env={k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_SUPPLEMENT_','E006_','DIRECTED_'))}
    env.update(E006_DCP=str(checkpoint['path']),E006_OUT=str(report),E006_TARGETS=str(archive/'targets.tcl'),
        E006_CANDIDATE_ADAPTER=str(archive/'directed_evidence.py'),DIRECTED_REUSE=str(archive/'reuse_manifest.json'),
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    supervisor_start=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    metadata=dict(stage='readonly_candidate_directed_cut',started_utc=utc(),supervisor_pid=os.getpid(),supervisor_start_ticks=supervisor_start,
        argv=cmd,cwd=str(report),report=str(report),project=str(ROOT/'project/hardware/vivado/project/m002_E005_R002_AT006_fresh'),
        cpu_affinity=list(range(8)),nice=5,max_threads=8,timeout_seconds=None,no_output_timeout_seconds=None,
        wall_clock_stop_disabled=True,rss_limit_bytes=192*guard.GIB,mem_available_floor_bytes=48*guard.GIB,
        mem_low_grace_seconds=30,disk_free_floor_bytes=30*guard.GIB,inputs=identity(attempt/'input_bindings.json'),
        environment={k:v for k,v in env.items() if k.startswith(('E006_','DIRECTED_'))})
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
