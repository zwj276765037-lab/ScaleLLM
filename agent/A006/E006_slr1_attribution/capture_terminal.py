#!/usr/bin/env python3
"""One-time E006 terminal audit, preserving native outcomes; no EDA control."""
import csv
import fcntl
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution'


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
    status = json.loads((ATTEMPT / 'status.json').read_text())
    assert status['execution_state'] == 'completed' and status['ended_utc'], 'No original supervisor terminal'
    output = ATTEMPT / 'terminal_facts.json'; short = ATTEMPT / 'terminal_summary.json'
    assert not output.exists() and not short.exists(), 'Never overwrite terminal evidence'
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
    stages = table(REPORT / 'stage_receipts.tsv'); queries = table(REPORT / 'query_receipts.tsv')
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
        four_stages_complete=[r['stage'] for r in stages] == ['module_resources', 'hotspot_ownership', 'failure_samples', 'hotspot_connections'],
        all_stage_codes_zero=all(r['native_tcl_code'] == '0' for r in stages), all_query_codes_zero=all(r['native_tcl_code'] == '0' for r in queries),
        production_144_unchanged=len(rows) == 144 and not mismatches, source_physopt_DCP_unchanged=checkpoint == inputs['checkpoint'],
        archived_sources_unchanged=sources == inputs['sources'], external_targets_sources_unchanged=external == inputs['external_inputs'],
        contract_unchanged=identity(inputs['contract']['path']) == inputs['contract'],
        no_post_integrity_error=status['post_integrity_error'] is None, wrapper_after_freeze_agrees=status['frozen_inputs_after'] == inputs['frozen_inputs'],
        no_physical_commands=status['physical_commands_executed'] is False, no_checkpoint_write=status['checkpoint_write_executed'] is False,
        resource_extrema_agree=peak == status['max_tree_rss_bytes'] and minimum_mem >= status['minimum_mem_available_bytes'] and minimum_disk >= status['minimum_disk_free_bytes'])
    producer = ATTEMPT / 'terminal_capture_producer.py'; shutil.copy2(Path(__file__), producer)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), engineering_execution_verified=all(checks.values()), checks=checks,
        started_utc=status['started_utc'], ended_utc=status['ended_utc'], native_exit_code=status['native_exit_code'], supervisor_exit_code=status['exit_code'], stop_reason=status['stop_reason'],
        attempt_seconds=(datetime.fromisoformat(status['ended_utc']) - datetime.fromisoformat(status['started_utc'])).total_seconds(),
        stages=stages, queries=queries, processes=processes, lane_lock_probe=lock, input_bindings=bound, status=identity(ATTEMPT / 'status.json'),
        freeze_manifest=freeze, production_files_checked=len(rows), production_mismatches=mismatches,
        source_checkpoint=checkpoint, archived_sources=sources, external_inputs=external, producer=identity(producer),
        resources=dict(samples=samples, first_sample=first, last_sample=last, sampled_peak_tree_rss_bytes=peak, minimum_mem_available_bytes=minimum_mem, minimum_disk_free_bytes=minimum_disk, maximum_sample_gap_seconds=max_gap),
        closed_native_log=identity(REPORT / 'vivado.log'), result=identity(REPORT / 'result.txt'),
        graph_scope='Original E005 physopt only, not failed route graph; failure sample names may legitimately not exist',
        endpoint_scope='Primitive leaf DIRECTION IN/OUT; excludes INOUT and top ports; NO_PRIMITIVE_DRIVER is not proof of no real driver',
        fixed_window_congestion='UNAVAILABLE; occupancy is not congestion', formal_signoff=False)
    put(output, facts)
    summary = {k: facts[k] for k in ['recorded_utc', 'engineering_execution_verified', 'checks', 'started_utc', 'ended_utc', 'native_exit_code', 'supervisor_exit_code', 'stop_reason', 'attempt_seconds', 'stages', 'production_files_checked', 'production_mismatches', 'resources', 'endpoint_scope', 'fixed_window_congestion', 'formal_signoff']}
    summary['full_facts'] = identity(output); put(short, summary)
    print(json.dumps(dict(summary=identity(short), facts=identity(output), checks=checks), ensure_ascii=False))


if __name__ == '__main__':
    main()
