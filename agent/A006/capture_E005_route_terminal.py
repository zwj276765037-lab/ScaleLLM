#!/usr/bin/env python3
"""One-time read-only terminal observation; does not validate physical signoff."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R004/attempts/AT004_default_route'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'
FREEZE = ROOT / 'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'


def identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def put(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    status_path = ATTEMPT / 'status.json'
    if not status_path.is_file():
        raise SystemExit('NOT_RUN: original route has no supervisor terminal status')
    status = json.loads(status_path.read_text())
    if status.get('execution_state') != 'completed':
        raise SystemExit('NOT_RUN: original supervisor is not terminal')
    output = ATTEMPT / 'route_terminal_observation_facts.json'
    summary_path = ATTEMPT / 'route_terminal_observation_summary.json'
    if output.exists() or summary_path.exists():
        raise SystemExit('Evidence already exists; do not overwrite')
    launch_path = ROOT / 'agent/A006/detached_R004_AT004_default_route.json'
    launch = json.loads(launch_path.read_text())
    tracked = {int(pid): int(start) for pid, start in status.get('tracked_identities', {}).items()}
    tracked[611388] = 925368939
    tracked[611402] = 925369067
    tracked[611607] = 925370167
    process_observations = []
    for pid, start in sorted(tracked.items()):
        row = dict(pid=pid, expected_start_ticks=start, original_identity_present=False, original_live=False)
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            row.update(current_start_ticks=int(fields[19]), state=fields[0])
            row['original_identity_present'] = row['current_start_ticks'] == start
            row['original_live'] = row['original_identity_present'] and row['state'] != 'Z'
        except FileNotFoundError:
            pass
        process_observations.append(row)
    live = [row for row in process_observations if row['original_live']]
    lock = dict(path=str(ROOT / 'project/hardware/vivado/.m002_eda.lock'), probe='SKIPPED_original_owned_identity_live')
    if not live:
        with Path(lock['path']).open('r') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock.update(probe='exclusive_nonblocking_acquire_succeeded', released_immediately=True)
                fcntl.flock(stream, fcntl.LOCK_UN)
            except BlockingIOError:
                lock.update(probe='held_by_an_owner_not_identified_by_this_probe')
    receipt = REPORT / 'route_command_result.txt'
    native = dict(line.split('=', 1) for line in receipt.read_text().splitlines() if '=' in line) if receipt.exists() else None
    if native and native.get('started_epoch') and native.get('ended_epoch'):
        native['duration_seconds_including_failure_capture_if_any'] = int(native['ended_epoch']) - int(native['started_epoch'])
    log_path = REPORT / 'vivado.log'
    log_bytes = log_path.read_bytes()
    frozen_log = ATTEMPT / 'closed_native_route_log.txt'
    with frozen_log.open('xb') as stream:
        stream.write(log_bytes)
    producer = ATTEMPT / 'route_terminal_observer_producer.py'
    with producer.open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    phase = None
    observations = []
    for number, line in enumerate(log_bytes.decode(errors='replace').splitlines(), 1):
        if line.startswith('Phase ') and '| Checksum:' not in line:
            phase = line
        if re.search(r'Number of (?:Nodes with overlaps|Node Overlaps|Failed Nets|Unrouted Nets|Partially Routed Nets)\s*=|\[Route 35-(?:2|17|162|416|447|448|581)\]|route_design (?:failed|completed)|M002_FAILED_ROUTE', line):
            observations.append(dict(native_line=number, native_phase=phase, raw=line))
    resources = ATTEMPT / 'resources.jsonl'
    samples = 0
    peak = 0
    min_mem = None
    min_disk = None
    first_sample = None
    last_sample = None
    max_interval = 0
    max_interval_bounds = None
    for line in resources.read_text().splitlines():
        row = json.loads(line)
        observed = datetime.fromisoformat(row['utc'])
        if first_sample is None:
            first_sample = row['utc']
        if last_sample is not None:
            interval = (observed - datetime.fromisoformat(last_sample)).total_seconds()
            if interval > max_interval:
                max_interval = interval
                max_interval_bounds = [last_sample, row['utc']]
        last_sample = row['utc']
        samples += 1
        peak = max(peak, row['rss_bytes'])
        min_mem = min(min_mem, row['mem_available_bytes']) if min_mem is not None else row['mem_available_bytes']
        min_disk = min(min_disk, row['disk_free_bytes']) if min_disk is not None else row['disk_free_bytes']
    freeze_identity = identity(FREEZE)
    freeze_identity_matches = freeze_identity['sha256'] == 'a5643a9e8adb13d6e76f3e78b2dfb6804b9b8ac193f7006f5ceff1b0c4f5a26f'
    freeze_rows = json.loads(FREEZE.read_text())['files']
    mismatches = []
    for row in freeze_rows:
        actual = identity(Path(row['path']))
        if actual != row:
            mismatches.append(dict(expected=row, actual=actual))
    names = ['route.dcp', 'route_status_route.rpt', 'timing_route.rpt', 'drc_route.rpt',
             'check_timing_route.rpt', 'clocks_route.rpt', 'cdc_route.rpt', 'reset_graph_route.tsv',
             'integrity_route.json', 'route_result.txt', 'admission_route.txt', 'diagnostic_evidence.json',
             'implementation_checkpoint.sha256', 'route_failed_original_error.tcllist',
             'route_failed_capture_receipts.tsv', 'route_failed.dcp', 'route_failed_status.rpt',
             'route_failed_timing.rpt', 'route_failed_congestion.rpt', 'route_failed_drc.rpt',
             'failed_route_artifacts.json', 'launcher_status.txt', 'evidence_error.txt',
             'command.json', 'stage_inputs.sha256', 'archived_sources.sha256']
    artifacts = {name: dict(present=(REPORT / name).is_file(),
                           identity=identity(REPORT / name) if (REPORT / name).is_file() else None)
                 for name in names}
    now = datetime.now(timezone.utc).isoformat()
    value = dict(observed_utc=now, producer=identity(producer), supervisor_status=identity(status_path),
                 detached_launch=identity(launch_path), original_supervisor_launch=launch.get('supervisor_pid'),
                 execution={key: status.get(key) for key in ['started_utc', 'ended_utc', 'native_exit_code',
                            'exit_code', 'stop_reason', 'owned_survivors', 'wall_clock_stop_disabled']},
                 native_route_receipt=identity(receipt) if receipt.exists() else None, native_route=native,
                 native_log=identity(log_path), retained_closed_log=identity(frozen_log), last_native_phase=phase,
                 native_phase_count_error_observations=observations, artifacts=artifacts,
                 registered_process_observations=process_observations, original_owned_live=live, lane_lock=lock,
                 resources_recomputed=dict(samples=samples, sampled_peak_tree_rss_bytes=peak,
                      minimum_mem_available_bytes=min_mem, minimum_disk_free_bytes=min_disk,
                      first_sample_utc=first_sample, last_sample_utc=last_sample,
                      max_sample_interval_seconds=max_interval, max_interval_bounds_utc=max_interval_bounds),
                 frozen_inputs=dict(manifest=freeze_identity, manifest_identity_matches=freeze_identity_matches,
                                    entries=len(freeze_rows), expected_entries=144, mismatches=mismatches),
                 interpretation='Observation only. Native command, supervisor, diagnostic capture and successful POST are distinct. Failed DCP/reports do not qualify a successful route parent. Formal timing/reset/CDC/board signoff evaluated separately.')
    put(output, value)
    summary = dict(observed_utc=now, full_facts=identity(output), execution=value['execution'],
                   native_route=native, last_native_phase=phase, original_owned_live=live, lane_lock=lock,
                   unchanged_frozen_inputs=144 if freeze_identity_matches and len(freeze_rows) == 144 and not mismatches else False,
                   artifacts_present={name: row['present'] for name, row in artifacts.items()},
                   resources_GiB={key: round(number / 2**30, 4) for key, number in
                       [('peak_rss', peak), ('minimum_mem_available', min_mem), ('minimum_disk_free', min_disk)]},
                   terminal_observation_only=True, formal_safety='OPEN')
    put(summary_path, summary)
    print(json.dumps(dict(summary=identity(summary_path), full_facts=identity(output),
                          execution=value['execution'], native_route=native), indent=2))


if __name__ == '__main__':
    main()
