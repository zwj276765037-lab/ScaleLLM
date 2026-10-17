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
import m002_synthesis_recovery as synth_recovery

CONTRACT = ROOT/'mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md'
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


def prior_terminal_kind(status, original, status_path, started_path):
    """Qualify terminal receipt fields without rewriting its original verdict/schema."""
    require(isinstance(status.get('ended_utc'), str) and bool(status['ended_utc']),
            f'Missing prior terminal time: {status_path}')
    require(type(status.get('exit_code')) is int and type(status.get('native_exit_code')) is int,
            f'Missing prior actual exit codes: {status_path}')
    require(status.get('owned_survivors') == [], f'Prior owned survivors: {status_path}')
    require(status.get('started_utc') == original.get('started_utc') and bool(status.get('started_utc')),
            f'Inconsistent prior start: {status_path}')
    start = dt.datetime.fromisoformat(status['started_utc'])
    end = dt.datetime.fromisoformat(status['ended_utc'])
    require(start.tzinfo is not None and end.tzinfo is not None and end >= start,
            f'Invalid prior terminal interval: {status_path}')
    state = status.get('execution_state')
    if state in {'completed', 'failed'}:
        return 'explicit_terminal_' + state
    # Only these two immutable CPU-only receipts predate execution_state. Do not
    # turn absent/UNKNOWN state into a generic EDA or synthesis recovery bypass.
    name = status_path.parent.name
    binding = LEGACY_CPU_RECEIPTS.get(name)
    require('execution_state' not in status and binding is not None and
            status_path.parent.parent == RUNS/'R002/attempts' and
            identity(status_path)['sha256'] == binding[0] and
            identity(started_path)['sha256'] == binding[1],
            f'Unclosed/unknown prior execution state: {status_path}')
    require(status.get('stage') == original.get('stage') == 'preflight' and
            status.get('execution_profile') == original.get('execution_profile') == 'm002_optimized_implementation' and
            status.get('scope') == original.get('scope') == binding[2] and
            status.get('argv') == original.get('argv') and status.get('cwd') == original.get('cwd') and
            status.get('stop_reason') is None and status.get('inputs_unchanged') is True and
            type(original.get('leader_pid')) is int and type(original.get('leader_start_ticks')) is int,
            f'Unqualified legacy CPU receipt: {status_path}')
    return 'explicit_closed_legacy_CPU_receipt_missing_state_field'


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


def prior_attempts_closed():
    checked = []
    for started in sorted(RUNS.glob('R*/attempts/AT*/started.json')):
        original = json.loads(started.read_text())
        ended = started.parent/'status.json'
        if not ended.is_file() and (started.parent/synth_recovery.RECEIPT).is_file():
            synth_recovery.validate_recovery(Path(original['project']),Path(original['report']),started.parent)
            checked.append(dict(started=identity(started),closure='qualified_original_synthesis_recovery_gap_preserved'))
            continue
        require(ended.is_file(),f'Unclosed prior E005 attempt: {started.parent}')
        status = json.loads(ended.read_text())
        closure_kind = prior_terminal_kind(status, original, ended, started)
        extra = {}
        supervisor_receipt = ROOT/'agent/A006'/('detached_'+started.parent.parent.parent.name+'_'+started.parent.name+'.json')
        if status.get('supervisor_pid') and status.get('supervisor_start_ticks'):
            extra[str(status['supervisor_pid'])] = status['supervisor_start_ticks']
        receipt_identity = None
        if supervisor_receipt.is_file():
            launch = json.loads(supervisor_receipt.read_text())
            if launch.get('supervisor_pid') == status.get('supervisor_pid') and launch.get('supervisor_proc_identity'):
                extra[str(launch['supervisor_pid'])] = launch['supervisor_proc_identity']['start_ticks']
                receipt_identity = identity(supervisor_receipt)
        registered = prior_registered_identities(status, original, extra)
        live = require_registered_closed(registered)
        checked.append(dict(status=identity(ended),started=identity(started),closure_kind=closure_kind,
            original_execution_state=status.get('execution_state'),original_exit_code=status['exit_code'],
            registered_identities=registered,registered_owned_live=live,supervisor_launch_receipt=receipt_identity))
    return checked


def tcl(value):
    require(not any(c in str(value) for c in '{}\r\n'), 'unsupported Tcl path')
    return '{'+str(value)+'}'


def new_peak_target_check(source_dir):
    manifest = json.loads((source_dir/'new_worst_targets_manifest.json').read_text())
    require(identity(manifest['targets_tcl']['path']) == manifest['targets_tcl'], 'changed new peak Tcl targets')
    require(identity(manifest['independent_targets']['path']) == manifest['independent_targets'], 'changed independent peak targets')
    independent = json.loads(Path(manifest['independent_targets']['path']).read_text())
    require(set(manifest['phases']) == set(DCPS), 'wrong new peak phases')
    source_reports = {}
    for phase, spec in manifest['phases'].items():
        report = spec['source_report']
        require(Path(report['path']) == PARENT/('congestion_'+phase+'.rpt') and identity(report['path']) == report,
                'changed or foreign new peak source report')
        rows = spec['source_rows']; regions = spec['unique_regions']
        peaks = [r for r in rows if r['selected_peak']]
        require(len(rows) == 48 and len({r['native_line'] for r in rows}) == 48 and len(peaks) == spec['peak_rows'] == 12,
                'wrong new peak report-row selection')
        require(len(regions) == len({r['region_id'] for r in regions}) == len({tuple(r['endpoints']) for r in regions}) == 10,
                'wrong new peak unique-region selection')
        region_map = {r['region_id']: r['endpoints'] for r in regions}
        require({(r['direction'], r['type']) for r in peaks} == {(d,t) for d in ['North','South','East','West'] for t in ['Global','Long','Short']},
                'incomplete new peak direction/type coverage')
        require(all(r['level'] == max(x['level'] for x in rows if (x['direction'],x['type']) == (r['direction'],r['type'])) == 6 and
                    region_map.get(r['region_id']) == r['endpoints'] for r in peaks), 'wrong new peak maximum/region association')
        reference = next(r for r in independent['phases'] if r['phase'] == phase)
        require(reference['source_report_identity'] == report and
                [(r['native_line'],r['source_row_index'],r['direction'],r['type'],r['level'],r['endpoints'][0],r['endpoints'][1],r['region_id']) for r in peaks] ==
                [(r['native_line'],r['source_row_index'],r['direction'],r['type'],r['level'],r['first_tile'],r['last_tile'],r['unique_region_id']) for r in reference['selected_rows']],
                'new peak targets differ from independent exact source rows')
        source_reports[phase] = report
    return source_reports


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
    prior_closure = prior_attempts_closed()
    route_status = closed_status(route/'status.json','route')
    parent = json.loads((PARENT/'diagnostic_evidence.json').read_text())
    closed_status(Path(parent['managed_attempt'])/'status.json','place',True)
    project = Path(parent['project'])
    accepted = evidence.parent_place(PARENT/'diagnostic_evidence.json',project,parent['synthesis'])
    route_command = json.loads((Path(route_status['report'])/'command.json').read_text())
    require(route_command['stage'] == 'route' and route_command['managed_attempt'] == str(route) and
            route_command['environment']['HAP_PLACE_REPORT_DIR'] == str(PARENT) and
            route_command['synthesis'] == parent['synthesis'], 'route has different parent')
    route_receipt_path = Path(route_status['report'])/'route_command_result.txt'
    route_receipt = evidence.key_values(route_receipt_path)
    require(route_receipt.get('phase') == 'route' and route_receipt.get('command') == 'route_design -directive Default' and
            route_receipt.get('native_tcl_code') in {'0','1'} and
            int(route_receipt['ended_epoch']) >= int(route_receipt['started_epoch']) > 0,
            'Actual Default route command has no qualified natural terminal receipt')
    checkpoints = {phase:identity(PARENT/(phase+'.dcp')) for phase in DCPS}
    for phase, row in checkpoints.items(): require(row['sha256'] == DCPS[phase], 'changed closed phase DCP')
    require(accepted['checkpoint'] == checkpoints['physopt'], 'wrong admitted physopt DCP')
    before_freeze = freeze_check()
    source_dir = Path(__file__).resolve().parent
    new_peak_sources = new_peak_target_check(source_dir)
    require(guard.mem_available() >= 48*guard.GIB and shutil.disk_usage(ROOT).free >= 30*guard.GIB,'resource reserve unavailable')
    attempt.mkdir(parents=True);report.mkdir(parents=True)
    archive = attempt/'sources';archive.mkdir()
    source_dir = Path(__file__).resolve().parent
    names = ['readonly_two_phase_driver.tcl','readonly_physical_supplement.tcl','targets.tcl','new_worst_targets_manifest.json',Path(__file__).name]
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
        actual_route_receipt=identity(route_receipt_path), prior_attempt_closures=prior_closure,
        placed_reference=identity(RUNS/'R005/AT003_placed_driver_sites_for_device_mapping.json'),
        frozen_inputs=before_freeze, sources=source_bindings, new_peak_source_reports=new_peak_sources,
        resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save(attempt/'input_bindings.json',inputs)
    cmd = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
           '-source',str(archive/'readonly_two_phase_driver.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    env = {k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_SUPPLEMENT_'))}
    env.update(E005_SUPPLEMENT_JOBS=str(archive/'jobs.tcl'), E005_SUPPLEMENT_CORE=str(archive/'readonly_physical_supplement.tcl'),
        E005_SUPPLEMENT_TARGETS=str(archive/'targets.tcl'),E005_SUPPLEMENT_MASTER_OUT=str(report),
        PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    supervisor_start = int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    metadata = dict(stage='readonly_physical_comparison',started_utc=utc(),supervisor_pid=os.getpid(),supervisor_start_ticks=supervisor_start,argv=cmd,
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
            require({p:identity(row['path']) for p,row in new_peak_sources.items()} == new_peak_sources,'new peak source report changed')
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
