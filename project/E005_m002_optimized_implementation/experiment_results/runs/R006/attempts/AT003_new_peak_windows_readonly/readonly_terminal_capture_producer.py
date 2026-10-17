#!/usr/bin/env python3
"""One-time read-only R006 terminal verification; never controls EDA."""
import csv
import argparse
import fcntl
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT002_closed_place_physopt_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly'


def identity(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def put(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))


def main():
    global ATTEMPT, REPORT
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-name', choices=['AT002_closed_place_physopt_readonly', 'AT003_new_peak_windows_readonly'], default='AT002_closed_place_physopt_readonly')
    selected = parser.parse_args().attempt_name
    ATTEMPT = ATTEMPT.parent / selected
    REPORT = REPORT.parent / ('m002_E005_R006_' + selected)
    status_path = ATTEMPT / 'status.json'
    assert status_path.is_file(), 'No supervisor natural terminal yet'
    status = json.loads(status_path.read_text())
    assert status['execution_state'] == 'completed' and status.get('ended_utc'), 'No true terminal'
    output = ATTEMPT / 'readonly_terminal_facts.json'
    summary_path = ATTEMPT / 'readonly_terminal_summary.json'
    assert not output.exists() and not summary_path.exists(), 'Do not overwrite terminal evidence'
    started = json.loads((ATTEMPT / 'started.json').read_text())
    tracked = {int(pid): int(ticks) for pid, ticks in status['tracked_identities'].items()}
    tracked[started['supervisor_pid']] = started['supervisor_start_ticks']
    process_checks = []
    for pid, ticks in sorted(tracked.items()):
        row = dict(pid=pid, expected_start_ticks=ticks, original_identity_present=False, original_live=False)
        try:
            fields = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
            row.update(current_start_ticks=int(fields[19]), state=fields[0])
            row['original_identity_present'] = row['current_start_ticks'] == ticks
            row['original_live'] = row['original_identity_present'] and row['state'] != 'Z'
        except FileNotFoundError:
            pass
        process_checks.append(row)
    assert not any(row['original_live'] for row in process_checks), 'Original process still live; wait without control'
    lock = dict(path=str(ROOT / 'project/hardware/vivado/.m002_eda.lock'))
    with Path(lock['path']).open('r') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock.update(probe='exclusive_nonblocking_acquire_succeeded', released_immediately=True)
            fcntl.flock(stream, fcntl.LOCK_UN)
        except BlockingIOError:
            lock.update(probe='held_by_an_owner_not_identified_by_this_probe')
    input_identity = identity(ATTEMPT / 'input_bindings.json')
    assert input_identity == started['inputs'] == status['inputs'], 'Original bound input manifest drift'
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    freeze_expected = bindings['frozen_inputs']['freeze']
    freeze_actual = identity(freeze_expected['path'])
    assert freeze_actual == freeze_expected, 'Freeze manifest drift'
    frozen_files = json.loads(Path(freeze_actual['path']).read_text())['files']
    freeze_mismatches = []
    for expected in frozen_files:
        try:
            actual = identity(expected['path'])
        except (FileNotFoundError, AssertionError) as exc:
            actual = dict(error=str(exc))
        if actual != expected:
            freeze_mismatches.append(dict(expected=expected, actual=actual))
    source_checks = [dict(expected=row, actual=identity(row['path'])) for row in bindings['sources']]
    checkpoint_checks = {phase: dict(expected=row, actual=identity(row['path'])) for phase, row in bindings['checkpoints'].items()}
    new_peak_report_checks = {phase: dict(expected=row, actual=identity(row['path'])) for phase, row in bindings.get('new_peak_source_reports', {}).items()}
    new_peak_target_check = None
    target_manifest = ATTEMPT / 'sources/new_worst_targets_manifest.json'
    if target_manifest.exists():
        expected_target = json.loads(target_manifest.read_text())['independent_targets']
        new_peak_target_check = dict(expected=expected_target, actual=identity(expected_target['path']))
    phases = table(REPORT / 'phase_receipts.tsv')
    assert [r['phase'] for r in phases] == ['place', 'physopt'], 'Wrong phase coverage/order'
    phase_checks = []
    for receipt in phases:
        phase = receipt['phase']
        queries = table(REPORT / phase / 'query_receipts.tsv')
        phase_checks.append(dict(phase=phase, receipt=receipt, query_count=len(queries),
            native_query_failures=[r for r in queries if r['native_tcl_code'] != '0'],
            result=identity(REPORT / phase / 'result.txt'), result_text=(REPORT / phase / 'result.txt').read_text(),
            result_and_options=identity(receipt['result_and_options_file']),
            result_and_options_text=Path(receipt['result_and_options_file']).read_text(),
            closed_phase_facts=identity(ATTEMPT / (phase + '_readonly_closed_phase_facts.json')) if (ATTEMPT / (phase + '_readonly_closed_phase_facts.json')).exists() else None))
    resources_path = ATTEMPT / 'resources.jsonl'
    samples = 0; peak = 0; min_mem = None; min_disk = None; first = None; last = None; max_gap = 0.0; max_gap_bounds = None
    for line in resources_path.read_text().splitlines():
        row = json.loads(line)
        if first is None:
            first = row['utc']
        if last:
            gap = (datetime.fromisoformat(row['utc']) - datetime.fromisoformat(last)).total_seconds()
            if gap > max_gap:
                max_gap = gap; max_gap_bounds = [last, row['utc']]
        last = row['utc']; samples += 1
        peak = max(peak, row['rss_bytes'])
        min_mem = min(min_mem, row['mem_available_bytes']) if min_mem is not None else row['mem_available_bytes']
        min_disk = min(min_disk, row['disk_free_bytes']) if min_disk is not None else row['disk_free_bytes']
    resource_facts = dict(samples=samples, first_sample=first, last_sample=last, maximum_sample_interval_seconds=max_gap,
        maximum_interval_bounds=max_gap_bounds, sampled_peak_tree_rss_bytes=peak,
        minimum_mem_available_bytes=min_mem, minimum_disk_free_bytes=min_disk,
        recorded_supervisor_extrema_agree=peak == status['max_tree_rss_bytes'] and min_mem >= status['minimum_mem_available_bytes'] and min_disk >= status['minimum_disk_free_bytes'])
    producer = ATTEMPT / 'readonly_terminal_capture_producer.py'
    shutil.copy2(Path(__file__), producer)
    closed_log = ATTEMPT / 'closed_readonly_native_log.txt'
    with closed_log.open('xb') as stream:
        stream.write((REPORT / 'vivado.log').read_bytes())
    checks = dict(native_exit_zero=status['native_exit_code'] == 0, supervisor_exit_zero=status['exit_code'] == 0,
        natural_terminal=status['native_natural_terminal_observed'], no_stop=status['stop_reason'] is None,
        no_cleanup_required=not status['cleanup_was_required'], no_owned_survivors=status['owned_survivors'] == [],
        no_original_live=not any(r['original_live'] for r in process_checks), lane_released=lock['probe'] == 'exclusive_nonblocking_acquire_succeeded',
        all_phases_query_zero=all(r['receipt']['native_tcl_code'] == '0' and not r['native_query_failures'] for r in phase_checks),
        original_checkpoints_unchanged=all(r['actual'] == r['expected'] for r in checkpoint_checks.values()),
        archived_sources_unchanged=all(r['actual'] == r['expected'] for r in source_checks),
        new_peak_source_reports_unchanged=all(r['actual'] == r['expected'] for r in new_peak_report_checks.values()),
        new_peak_independent_target_unchanged=new_peak_target_check is None or new_peak_target_check['actual'] == new_peak_target_check['expected'],
        original_input_binding_unchanged=input_identity == started['inputs'] == status['inputs'],
        contract_unchanged=identity(bindings['contract']['path']) == bindings['contract'],
        production_144_unchanged=len(frozen_files) == 144 and not freeze_mismatches,
        no_post_integrity_error=status['post_integrity_error'] is None,
        wrapper_after_freeze_agrees=status['frozen_inputs_after'] == bindings['frozen_inputs'],
        no_physical_commands=status['physical_commands_executed'] is False,
        no_checkpoint_write=status['checkpoint_write_executed'] is False,
        resource_extrema_agree=resource_facts['recorded_supervisor_extrema_agree'])
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), execution='naturally closed readonly two-phase comparison',
        checks=checks, engineering_execution_verified=all(checks.values()), status=identity(status_path),
        native_exit_code=status['native_exit_code'], supervisor_exit_code=status['exit_code'], stop_reason=status['stop_reason'],
        started_utc=status['started_utc'], ended_utc=status['ended_utc'],
        attempt_seconds=(datetime.fromisoformat(status['ended_utc']) - datetime.fromisoformat(status['started_utc'])).total_seconds(),
        phases=phase_checks, resources=resource_facts, resources_identity=identity(resources_path),
        process_checks=process_checks, lane_lock_probe=lock, freeze_manifest=freeze_actual,
        production_files_checked=len(frozen_files), production_mismatches=freeze_mismatches,
        original_checkpoint_checks=checkpoint_checks, actual_archived_source_checks=source_checks,
        new_peak_source_report_checks=new_peak_report_checks,
        new_peak_independent_target_check=new_peak_target_check,
        new_peak_check_applicability='ACTUAL_TWO_SOURCE_REPORTS_AND_INDEPENDENT_TARGET' if new_peak_report_checks else 'NOT_APPLICABLE_NO_NEW_PEAK_INPUTS; empty checks do not imply new peak measurement',
        input_bindings=input_identity, command=identity(ATTEMPT / 'command.json'),
        started=identity(ATTEMPT / 'started.json'), producer=identity(producer), closed_log=identity(closed_log),
        result=identity(REPORT / 'result.txt'), result_text=(REPORT / 'result.txt').read_text(),
        phase_receipts=identity(REPORT / 'phase_receipts.tsv'), physical_commands_executed=False, checkpoint_write_executed=False,
        fixed_window_congestion='UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API; occupancy is not congestion',
        route_legality='Prior R004/AT004 FAIL remains; read-only measurement cannot create successful route', formal_signoff=False)
    put(output, facts)
    summary = {key: facts[key] for key in ['recorded_utc', 'engineering_execution_verified', 'checks', 'native_exit_code', 'supervisor_exit_code', 'stop_reason', 'started_utc', 'ended_utc', 'attempt_seconds', 'resources', 'production_files_checked', 'production_mismatches', 'input_bindings', 'fixed_window_congestion', 'route_legality', 'formal_signoff']}
    summary['full_facts'] = identity(output)
    summary['phase_results'] = [dict(phase=r['phase'], native_tcl_code=int(r['receipt']['native_tcl_code']), query_count=r['query_count'], failures=r['native_query_failures'], closed_phase_facts=r['closed_phase_facts']) for r in phase_checks]
    put(summary_path, summary)
    print(json.dumps(dict(summary=identity(summary_path), full_facts=identity(output), checks=checks), ensure_ascii=False))


if __name__ == '__main__':
    main()
