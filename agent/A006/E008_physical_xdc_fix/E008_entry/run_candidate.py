#!/usr/bin/env python3
"""E008 guarded full implementation. Preparation never invokes this main.

The required E006 closeout is an engineering dependency, not new user approval.
Only Root/A007 can supply actual terminal evidence supporting the candidate.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SCRIPTS=ROOT/'project/hardware/vivado/scripts'
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'agent/A006/E006_lean_candidate'))
from run_attribution_lean import (identity,freeze_check,require_registered_closed,
                                 prior_registered_identities,require)
import evidence_adapter as adapter
e=adapter.e
sys.path.insert(0,str(SCRIPTS))
import run_m002_no_wall as guard

E008=ROOT/'project/E008_m002_exact_hotspot_offload_implementation'
E006=ROOT/'project/E006_m002_slr1_congestion_attribution'
SOURCE=adapter.SOURCE
CONTRACT=ROOT/'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md'
SCOPE_REVISION=ROOT/'mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md'
ACQUISITION=ROOT/'mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md'


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def verify_manifest(path):
    value=json.loads(path.read_text())
    require(value['EDA_executed'] is False,'Not a preparation manifest')
    for row in value['own_sources']+value['reused_sources']+value.get('CPU_checks',[])+value.get('documentation',[])+value.get('runtime_dependencies',[]):
        require(identity(row['path'])==row,f"Prepared execution source changed: {row['path']}")
    for key in ['contract','scope_revision','acquisition_revision','selector_reference','source_reuse_manifest']:
        require(identity(value[key]['path'])==value[key],f'Changed {key}')
    require(value['contract']==identity(CONTRACT),'Wrong candidate contract')
    require(value['scope_revision']==identity(SCOPE_REVISION),'Wrong candidate directed scope revision')
    require(value['acquisition_revision']==identity(ACQUISITION),'Wrong top-port acquisition revision')
    require(value.get('coverage_version')=='candidate_directed_cut_v1','Wrong prepared cut coverage')
    return value


def require_fresh_or_planned(attempt, report):
    require(not report.exists(), 'Report already contains evidence')
    if not attempt.exists(): return None
    match = re.fullmatch(r'(AT\d{3})_(.+)', attempt.name)
    require(match and attempt.is_dir() and not attempt.is_symlink(), 'Invalid planned attempt')
    require({p.name for p in attempt.iterdir()} == {'run.json', 'report.md', 'evidence'}, 'Attempt already contains runtime data')
    require((attempt/'evidence').is_dir() and not (attempt/'evidence').is_symlink() and not any((attempt/'evidence').iterdir()), 'Planned evidence directory is not empty')
    for name in ['run.json', 'report.md']:
        require((attempt/name).is_file() and not (attempt/name).is_symlink(), 'Invalid planned metadata')
    expected = dict(execution_state='planned', schema=1, id=match[1], experiment='E008', run='R001', title=match[2])
    require(json.loads((attempt/'run.json').read_text()) == expected, 'Planned metadata differs')
    require((attempt/'report.md').read_text() == '# '+match[1]+' · '+match[2]+'\n\n记录目的、实际结果、适用范围、限制及原始证据。登记不代表已执行或通过。\n', 'Planned report is not untouched')
    return dict(run=identity(attempt/'run.json'), report=identity(attempt/'report.md'), evidence_empty=True)


def attribution_dependency(closeout_path):
    closeout=json.loads(closeout_path.read_text())
    require(closeout.get('phase')=='E006_attribution_closed' and
            closeout.get('successor')=='SM012/E008' and
            closeout.get('engineering_execution_verified') is True and
            closeout.get('candidate_scope_supported') is True,
            'E006 attribution/candidate engineering dependency is not closed')
    require(bool(closeout.get('evidence')),'No actual attribution review evidence')
    require(closeout.get('scope_revision') == identity(SCOPE_REVISION), 'Wrong directed-cut scope revision binding')
    require(closeout.get('acquisition_revision') == identity(ACQUISITION), 'Wrong top-port acquisition revision binding')
    selected = closeout.get('selected_candidate', {})
    targets = json.loads((HERE/'target_authority.json').read_text())['candidates']
    require(any(selected == dict(id=t['id'], root=t['root']) for t in targets),
            'Empty or unsupported exact candidate selection')
    require(closeout.get('base_contract') == identity(CONTRACT), 'Wrong E008 selected contract binding')
    require(closeout.get('preparation_manifest') == identity(HERE/'prepared_manifest.json'), 'Wrong E008 selected source binding')
    for row in [closeout['terminal_status'],*closeout['evidence']]:
        require(identity(row['path'])==row,'Attribution closure evidence identity changed')
    registered={};closed=[]
    for started_path in sorted((E006/'experiment_results/runs').glob('R*/attempts/AT*/started.json')):
        status_path=started_path.parent/'status.json'
        require(status_path.is_file(),f'Prior E006 owner unclosed: {started_path}')
        status=json.loads(status_path.read_text());started=json.loads(started_path.read_text())
        require(status.get('execution_state')=='completed' and not status.get('owned_survivors'),
                'Prior E006 terminal retains ownership')
        ids=prior_registered_identities(status,started)
        require_registered_closed(ids)
        for pid,start in ids.items():
            require(pid not in registered or registered[pid]==start,'E006 ownership identity conflict')
            registered[pid]=start
        closed.append(identity(status_path))
    require(bool(closed) and closeout['terminal_status'] in closed,'Closed E006 terminal is not a managed actual attempt')
    return dict(closeout=identity(closeout_path),terminal_statuses=closed,closed_registered_identities=registered, selected_candidate=selected)


def prepare_runtime(attempt,report,manifest,dependency):
    # Called only under the EDA lock, after all real E006 owners have gone.
    source_command=json.loads((SOURCE/'command.json').read_text())
    lineage=source_command['synthesis'];project=Path(lineage['project'])
    synth_report=Path(lineage['manifest']['path']).parent
    synth_attempt=Path(lineage['checkpoint_manifest']['path']).parent
    require(e.synth_lineage(project,synth_report,synth_attempt)==lineage,'Synthesis identity changed')
    attempt.mkdir(parents=True, exist_ok=True);report.mkdir(parents=True)
    archive=report/'stage_sources';archive.mkdir()
    source_rows=manifest['own_sources']+manifest['reused_sources']
    # Archive all execution sources once. Native Tcl helper references are frozen
    # by stage_inputs, and Python imports retain their production module paths.
    for row in source_rows:
        src=Path(row['path']);dst=archive/src.name
        require(not dst.exists(),'Execution archive basename collision')
        shutil.copy2(src,dst)
    shutil.copy2(SOURCE/'probe_targets.tcl',report/'probe_targets.tcl')
    parent=adapter.successful_pre_place_parent(SOURCE,project,lineage,report)
    env={k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E006_','SLR2_','E005_SUPPLEMENT_'))}
    env.update(HAP_STAGE='place',HAP_PROJECT_DIR=str(project),HAP_REPORT_DIR=str(report),
        HAP_CURRENT_ATTEMPT_DIR=str(attempt),HAP_SYNTH_REPORT_DIR=str(synth_report),
        HAP_SYNTH_ATTEMPT_DIR=str(synth_attempt),HAP_EXECUTION_MODE='checkpoint_restored_commands',
        HAP_EXECUTION_PROFILE='m002_optimized_implementation',HAP_RECOVERY_PHASE='post_debug_pre_place',
        HAP_PRE_PLACE_REPORT_DIR=str(SOURCE),HAP_RECOVERY_PARENT_REPORT=str(SOURCE),
        HAP_RECOVERY_CHECKPOINT=parent['checkpoint']['path'],HAP_JOBS='8',
        SLR2_REUSED_SCRIPT_DIR=str(SCRIPTS),SLR2_ADAPTER=str(archive/'evidence_adapter.py'),
        SLR2_HOOKS=str(archive/'candidate_hooks.tcl'),
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    # The archived adapter needs an explicit original workspace, independent of
    # its changed archive depth. This is bound into the actual command receipt.
    env['SLR2_WORKSPACE_ROOT']=str(ROOT)
    env['SLR2_CANDIDATE_ID']=dependency['selected_candidate']['id']
    env['SLR2_CANDIDATE_ROOT']=dependency['selected_candidate']['root']
    files={Path(r['path']) for r in source_rows}
    files.update(Path(row['path']) for row in manifest.get('runtime_dependencies',[]))
    files.update({report/'recovery_parent.json', report/'probe_targets.tcl',CONTRACT,
                  SOURCE/'pre_place_evidence.json',SOURCE/'diagnostic_evidence.json',SCOPE_REVISION,ACQUISITION,Path(parent['checkpoint']['path'])})
    files.update(Path(r['path']) for r in lineage.values() if isinstance(r,dict) and 'path' in r)
    files.update(p for p in archive.iterdir() if p.is_file())
    files.add(Path(dependency['closeout']['path']))
    (report/'stage_inputs.sha256').write_text(''.join(f"{identity(p)['sha256']}  {p}\n" for p in sorted(files)))
    (report/'archived_sources.sha256').write_text(''.join(f"{identity(p)['sha256']}  {p}\n" for p in sorted(archive.iterdir())))
    cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
         '-source',str(archive/'implementation.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    save(report/'command.json',dict(argv=cmd,stage='place',
        environment={k:v for k,v in env.items() if k.startswith(('HAP_','SLR2_'))},
        started_utc=utc(),execution_mode='checkpoint_restored_commands',synthesis=lineage,
        managed_attempt=str(attempt),scope='new E008 exact-hotspot complete place/physopt/route; original impl_1 status preserved', selected_candidate=dependency['selected_candidate']))
    return cmd,env,lineage


def final_evidence(report,native):
    evidence=dict(native_exit_code=native,physical_signoff=False,formal_reset_cdc_IO_safety='OPEN')
    if native==0:
        for point in ('place','physopt','route'):
            phase_status=e.key_values(report/f'candidate_phase_{point}_status.txt')
            require(phase_status.get('post_code')=='0' and phase_status.get('locality_code')=='0',
                    f'{point} explicit POST/locality failure receipt')
            result=e.key_values(report/f'{point}_result.txt')
            require(result.get('completed')=='1' and result.get('diagnostic_eligible')=='1',f'{point} gate incomplete')
            require(not json.loads((report/f'integrity_{point}.json').read_text())['gate_issues'],f'{point} integrity incomplete')
            require(json.loads((report/f'candidate_compliance_{point}.json').read_text())['compliance_established'],
                    f'{point} actual locality qualification incomplete')
        evidence.update(route=e.route_counts(report/'route_status_route.rpt'),
            timing_metrics_ns=e.timing_metrics(report/'timing_route.rpt'),checkpoint=identity(report/'route.dcp'))
        evidence['timing_verdict']=e.timing_verdict(evidence['timing_metrics_ns'])
        require(evidence['route']['complete'],'Native success did not produce complete legal route')
        evidence['execution_state']='completed'
    else:
        evidence.update(execution_state='failed',
            failed_route_artifacts=[identity(p) for p in sorted(report.glob('route_failed*')) if p.is_file()])
    save(report/'E008_physical_evidence.json',evidence)
    return evidence


def interrupted(signum,frame):raise KeyboardInterrupt(f'signal {signum}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--e006-closeout',type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve()
    require(attempt.parent==E008/'experiment_results/runs/R001/attempts' and attempt.name.startswith('AT'),
            'Wrong E008 physical batch')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_'),
            'Wrong E008 report root')
    planned = require_fresh_or_planned(attempt, report)
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    # Fail immediately if E006 is active. No queued job or automatic result bypass.
    lock=(ROOT/'project/hardware/vivado/.m002_eda.lock').open('r')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    dependency=attribution_dependency(args.e006_closeout.resolve())
    manifest=verify_manifest(HERE/'prepared_manifest.json')
    for path in (E008/'experiment_results/runs/R001/attempts').glob('AT*/started.json'):
        status=json.loads((path.parent/'status.json').read_text())
        require(status.get('execution_state')=='completed' and not status.get('owned_survivors'),'Prior E008 unclosed')
        require_registered_closed(prior_registered_identities(status,json.loads(path.read_text())))
    frozen=freeze_check()
    require(guard.mem_available()>=48*guard.GIB and shutil.disk_usage(ROOT).free>=30*guard.GIB,'Resource reserve unavailable')
    try:cmd,env,lineage=prepare_runtime(attempt,report,manifest,dependency)
    except Exception as exc:
        if attempt.is_dir():save(attempt/'status.json',dict(stage='full_slr2_implementation',
            execution_state='completed',native_exit_code=None,exit_code=1,stop_reason='prelaunch_CPU_admission_failed',
            owned_survivors=[],EDA_started=False,error=f'{type(exc).__name__}: {exc}',ended_utc=utc()))
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        raise
    bindings=dict(preparation_manifest=identity(HERE/'prepared_manifest.json'),
        planned_management_scaffold=planned,
        source_bindings=manifest['own_sources']+manifest['reused_sources'],
        attribution=dependency,frozen_inputs=frozen,parent=identity(report/'recovery_parent.json'),
        stage_inputs=identity(report/'stage_inputs.sha256'),contract=identity(CONTRACT),scope_revision=identity(SCOPE_REVISION))
    save(attempt/'input_bindings.json',bindings)
    metadata=dict(stage='full_slr2_implementation',started_utc=utc(),supervisor_pid=os.getpid(),
        supervisor_start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        argv=cmd,report=str(report),project=lineage['project'],cpu_affinity=list(range(8)),nice=5,max_threads=8,
        timeout_seconds=None,no_output_timeout_seconds=None,wall_clock_stop_disabled=True,
        rss_limit_bytes=192*guard.GIB,mem_available_floor_bytes=48*guard.GIB,mem_low_grace_seconds=30,
        disk_free_floor_bytes=30*guard.GIB,inputs=identity(attempt/'input_bindings.json'))
    save(attempt/'command.json',metadata)
    proc=None;tracked={};stop=None;peak=0;low_since=None;begin=time.monotonic()
    min_mem=guard.mem_available();min_disk=shutil.disk_usage(ROOT).free
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        with (attempt/'launcher.log').open('x') as log,(attempt/'resources.jsonl').open('x',buffering=1) as resources:
            proc=subprocess.Popen(cmd,cwd=report,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            metadata.update(leader_pid=proc.pid,process_group=proc.pid)
            sample=guard.process_table().get(proc.pid)
            if sample:metadata['leader_start_ticks']=sample['start_ticks']
            save(attempt/'started.json',metadata)
            print(json.dumps(dict(started=True,supervisor_pid=os.getpid(),leader_pid=proc.pid,attempt=str(attempt))),flush=True)
            while True:
                owned=guard.owned_processes(guard.process_table(),proc.pid,tracked)
                for pid in owned:
                    try:
                        if not os.sched_getaffinity(pid).issubset(range(8)):os.sched_setaffinity(pid,set(range(8)))
                    except ProcessLookupError:pass
                rss=sum(r['rss_bytes'] for r in owned.values());mem=guard.mem_available();disk=shutil.disk_usage(ROOT).free
                peak=max(peak,rss);min_mem=min(min_mem,mem);min_disk=min(min_disk,disk)
                resources.write(json.dumps(dict(utc=utc(),elapsed_seconds=time.monotonic()-begin,rss_bytes=rss,
                    mem_available_bytes=mem,disk_free_bytes=disk,processes=owned))+'\n')
                low_since=(low_since if low_since is not None else time.monotonic()) if mem<48*guard.GIB else None
                if rss>192*guard.GIB:stop='task_tree_rss_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since>=30:stop='MemAvailable_below_48GiB_30s'
                elif disk<30*guard.GIB:stop='disk_free_below_30GiB'
                if proc.poll() is not None or stop:break
                time.sleep(5)
    except BaseException as exc:stop=f'{type(exc).__name__}:{exc}'
    finally:
        natural=proc is not None and proc.poll() is not None
        before_cleanup=guard.owned_processes(guard.process_table(),proc.pid,tracked) if proc else {}
        cleanup=bool(proc and (stop is not None or not natural or before_cleanup))
        if cleanup:
            stop=stop or 'unexpected_owned_processes_after_native_terminal'
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        else:native,before,remain=(proc.wait(),[],[]) if proc else (None,[],[])
        while remain:
            stop=stop or 'owned_cleanup_incomplete'
            save(attempt/'cleanup_pending.json',dict(owned_survivors=remain,lane_lock_held=True,observed_utc=utc()))
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        rc=native if stop is None and native is not None else 125
        error=None;after=None
        try:
            after=freeze_check();verify_manifest(HERE/'prepared_manifest.json')
            require(identity(HERE/'prepared_manifest.json')==bindings['preparation_manifest'],'Prepared manifest changed')
            require(identity(args.e006_closeout.resolve())==dependency['closeout'],'Attribution closeout changed')
            closeout=json.loads(args.e006_closeout.resolve().read_text())
            for row in dependency['terminal_statuses']+[closeout['terminal_status'],*closeout['evidence']]:
                require(identity(row['path'])==row,'Referenced E006 closeout/terminal evidence changed')
            require(identity(report/'stage_inputs.sha256')==bindings['stage_inputs'],'Bound stage manifest itself changed')
            e.input_manifest(report/'stage_inputs.sha256')
            require(e.synth_lineage(Path(lineage['project']),Path(env['HAP_SYNTH_REPORT_DIR']),Path(env['HAP_SYNTH_ATTEMPT_DIR']))==lineage,
                    'Synthesis identity changed during new experiment')
            final_evidence(report,native)
        except Exception as exc:error=f'{type(exc).__name__}: {exc}';rc=rc or 1
        if (report/'vivado.log').is_file():shutil.copy2(report/'vivado.log',report/'implementation_run.log')
        save(attempt/'status.json',dict(**metadata,ended_utc=utc(),execution_state='completed',
            native_exit_code=native,exit_code=rc,stop_reason=stop,tracked_identities=tracked,
            owned_before_reap=before,owned_survivors=remain,native_natural_terminal_observed=natural,
            cleanup_was_required=cleanup,owned_before_cleanup=before_cleanup,
            max_tree_rss_bytes=peak,minimum_mem_available_bytes=min_mem,minimum_disk_free_bytes=min_disk,
            post_integrity_error=error,frozen_inputs_after=after,physical_signoff=False))
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        print(json.dumps(dict(completed=True,exit_code=rc,native_exit_code=native,stop_reason=stop)),flush=True)
    return rc


if __name__=='__main__':raise SystemExit(main())
