#!/usr/bin/env python3
"""One-time E006 terminal audit, preserving native outcomes; no EDA control."""
import csv
import argparse
import fcntl
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts/AT001_candidate_directed_cut'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R006_AT001_candidate_directed_cut'


def identity(path):
    path = Path(path); before = path.stat(); h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    after = path.stat(); assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())


def put(path, data):
    with path.open('x') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))


def main():
    global ATTEMPT,REPORT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.attempt:ATTEMPT=args.attempt.resolve()
    if args.report:REPORT=args.report.resolve()
    assert ATTEMPT.parent==ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts'
    assert REPORT.parent==ROOT/'project/hardware/vivado/reports' and REPORT.name.startswith('m002_E006_R006_')
    import os
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    status = json.loads((ATTEMPT / 'status.json').read_text())
    assert status['execution_state'] == 'completed' and status['ended_utc'], 'No original supervisor terminal'
    output = ATTEMPT / 'terminal_facts.json'; short = ATTEMPT / 'terminal_summary.json'
    assert not any(p.exists() for p in [output, short, ATTEMPT/'terminal_capture_producer.py']), 'Never overwrite terminal evidence or producer'
    started = json.loads((ATTEMPT / 'started.json').read_text()); bound = identity(ATTEMPT / 'input_bindings.json')
    assert bound == status['inputs'] == started['inputs']
    inputs = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    ids = {int(pid): int(tick) for pid, tick in status['tracked_identities'].items()}; ids[status['supervisor_pid']] = status['supervisor_start_ticks']
    processes = []
    for pid, tick in sorted(ids.items()):
        row = dict(pid=pid, expected_start_ticks=tick, original_identity_present=False, original_live=False)
        try:
            f = Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()
            row.update(current_start_ticks=int(f[19]), state=f[0]); row['original_identity_present'] = row['current_start_ticks'] == tick; row['original_live'] = row['original_identity_present'] and row['state'] != 'Z'
        except FileNotFoundError:
            pass
        processes.append(row)
    assert not any(p['original_live'] for p in processes), 'Original owner still live; wait without control'
    lock = dict(path=str(ROOT / 'project/hardware/vivado/.m002_eda.lock'))
    with Path(lock['path']).open('r') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB); lock.update(probe='exclusive_nonblocking_acquire_succeeded', released_immediately=True); fcntl.flock(stream, fcntl.LOCK_UN)
        except BlockingIOError:
            lock['probe'] = 'held_by_owner_not_identified_by_this_probe'
    freeze = inputs['frozen_inputs']['freeze']; assert identity(freeze['path']) == freeze
    rows = json.loads(Path(freeze['path']).read_text())['files']
    mismatches = []
    for row in rows:
        actual = identity(row['path'])
        if actual != row: mismatches.append(dict(expected=row, actual=actual))
    checkpoint = identity(inputs['checkpoint']['path'])
    sources = [identity(r['path']) for r in inputs['sources']]
    external = {key: identity(row['path']) for key, row in inputs['external_inputs'].items()}
    reused = {key: identity(row['path']) for key, row in inputs['reused_closed_inputs'].items()}
    authorization = identity(inputs['replacement_authorization']['path'])
    stages = table(REPORT / 'stage_receipts.tsv'); queries = table(REPORT / 'query_receipts.tsv')
    expected_queries = ['open_checkpoint', 'identity', 'topology',
        'candidate_C01_membership_qualification', 'candidate_C02_membership_qualification', 'candidate_disjointness',
        'candidate_C01_directed_cut', 'candidate_C01_bounded_timing',
        'candidate_C02_directed_cut', 'candidate_C02_bounded_timing']
    if (REPORT/'native_system_python_preflight.json').is_file():expected_queries.insert(0,'system_python_runtime_preflight')
    expected_runtime=json.loads(Path(inputs['preparation_manifest']['path']).read_text())['runtime_source_names']
    samples = 0; peak = 0; minimum_mem = None; minimum_disk = None; first = None; last = None; max_gap = 0.0
    for line in (ATTEMPT / 'resources.jsonl').read_text().splitlines():
        row = json.loads(line)
        if first is None: first = row['utc']
        if last: max_gap = max(max_gap, (datetime.fromisoformat(row['utc']) - datetime.fromisoformat(last)).total_seconds())
        last = row['utc']; samples += 1; peak = max(peak, row['rss_bytes'])
        minimum_mem = min(minimum_mem, row['mem_available_bytes']) if minimum_mem is not None else row['mem_available_bytes']
        minimum_disk = min(minimum_disk, row['disk_free_bytes']) if minimum_disk is not None else row['disk_free_bytes']
    checks = dict(native_zero=status['native_exit_code'] == 0, supervisor_zero=status['exit_code'] == 0,
        natural_terminal=status['native_natural_terminal_observed'], no_stop=status['stop_reason'] is None,
        no_cleanup=not status['cleanup_was_required'], no_survivors=status['owned_survivors'] == [], no_original_live=not any(p['original_live'] for p in processes),
        lane_released=lock['probe'] == 'exclusive_nonblocking_acquire_succeeded',
        six_stages_complete=[r['stage'] for r in stages] == ['candidate_C01_membership_qualification', 'candidate_C02_membership_qualification', 'candidate_C01_directed_cut', 'candidate_C01_bounded_timing', 'candidate_C02_directed_cut', 'candidate_C02_bounded_timing'],
        complete_expected_query_order=[r['query'] for r in queries] == expected_queries,
        all_stage_codes_zero=all(r['native_tcl_code'] == '0' for r in stages), all_query_codes_zero=all(r['native_tcl_code'] == '0' for r in queries),
        production_144_unchanged=len(rows) == 144 and not mismatches, source_physopt_DCP_unchanged=checkpoint == inputs['checkpoint'],
        archived_runtime_sources_unchanged=len(sources) == len(expected_runtime) and {Path(row['path']).name for row in sources} == set(expected_runtime) and sources == inputs['sources'], all_bound_external_targets_sources_unchanged=bool(external) and external == inputs['external_inputs'],
        all_bound_reused_closed_inputs_unchanged=bool(reused) and reused == inputs['reused_closed_inputs'], replacement_authorization_unchanged=authorization == inputs['replacement_authorization'],
        contract_unchanged=identity(inputs['contract']['path']) == inputs['contract'],
        resource_helper_unchanged=identity(inputs['resource_helper']['path']) == inputs['resource_helper'],
        no_post_integrity_error=status['post_integrity_error'] is None, wrapper_after_freeze_agrees=status['frozen_inputs_after'] == inputs['frozen_inputs'],
        no_physical_commands=status['physical_commands_executed'] is False, no_checkpoint_write=status['checkpoint_write_executed'] is False,
        resource_extrema_agree=peak == status['max_tree_rss_bytes'] and minimum_mem >= status['minimum_mem_available_bytes'] and minimum_disk >= status['minimum_disk_free_bytes'])
    producer = ATTEMPT / 'terminal_capture_producer.py'; shutil.copy2(Path(__file__), producer)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), engineering_execution_verified=all(checks.values()), checks=checks,
        started_utc=status['started_utc'], ended_utc=status['ended_utc'], native_exit_code=status['native_exit_code'], supervisor_exit_code=status['exit_code'], stop_reason=status['stop_reason'],
        attempt_seconds=(datetime.fromisoformat(status['ended_utc']) - datetime.fromisoformat(status['started_utc'])).total_seconds(),
        stages=stages, queries=queries, bound_external_input_count=len(external), bound_reused_input_count=len(reused), processes=processes, lane_lock_probe=lock, input_bindings=bound, status=identity(ATTEMPT / 'status.json'),
        freeze_manifest=freeze, production_files_checked=len(rows), production_mismatches=mismatches,
        source_checkpoint=checkpoint, prior_R004_actual_closure=inputs['prior_R004_closure'], preparation_manifest=inputs['preparation_manifest'], archived_sources=sources, external_inputs=external, reused_closed_inputs=reused, replacement_authorization=authorization, producer=identity(producer),
        resources=dict(samples=samples, first_sample=first, last_sample=last, sampled_peak_tree_rss_bytes=peak, minimum_mem_available_bytes=minimum_mem, minimum_disk_free_bytes=minimum_disk, maximum_sample_gap_seconds=max_gap),
        closed_native_log=identity(REPORT / 'vivado.log') if (REPORT / 'vivado.log').is_file() else None,
        result=identity(REPORT / 'result.txt') if (REPORT / 'result.txt').is_file() else None,
        graph_scope='Original E005 physopt only, not failed route graph; failure sample names may legitimately not exist',
        coverage_version='candidate_directed_cut_v1',
        endpoint_scope='Candidate-directed complete local leaf and aliases with native class/role-qualified external-driver reduction, all top ports, declared full fallback and bounded timing. External peer ordinary leaf loads NOT_ENUMERATED on qualified reduced nets; full-net fanout NOT_MEASURED. Old hotspot UNION full endpoint recovery NOT_IN_SCOPE and old unfinished evidence preserved. Native resources explicitly reused from R004. No candidate support inferred.',
        fixed_window_congestion='UNAVAILABLE; occupancy is not congestion', formal_signoff=False)
    put(output, facts)
    summary = {k: facts[k] for k in ['recorded_utc', 'engineering_execution_verified', 'checks', 'started_utc', 'ended_utc', 'native_exit_code', 'supervisor_exit_code', 'stop_reason', 'attempt_seconds', 'stages', 'production_files_checked', 'production_mismatches', 'resources', 'endpoint_scope', 'fixed_window_congestion', 'formal_signoff']}
    summary['full_facts'] = identity(output); put(short, summary)
    print(json.dumps(dict(summary=identity(short), facts=identity(output), checks=checks), ensure_ascii=False))


if __name__ == '__main__':
    main()
