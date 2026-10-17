"""Independent closed-physopt/terminal audit. No EDA, tests, DCP reads or locks taken."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import re

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent
AT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT002_closed_place_physopt_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly'
ORIGINAL = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
checks = []


def identity(path, expected=None):
    path = Path(path)
    assert path.suffix != '.dcp'
    data = path.read_bytes()
    value = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if expected:
        assert value == expected, (value, expected)
    checks.append(value)
    return value


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


phase_summary_path = AT / 'physopt_readonly_closed_phase_summary.json'
identity(phase_summary_path, dict(path=str(phase_summary_path), bytes=4268,
    sha256='a3ac7dcee4f2e3b1ba3ba18ae32a89807758c4ae655e66029e40df5ba02344fc'))
summary = json.loads(phase_summary_path.read_text())
identity(summary['full_facts']['path'], summary['full_facts'])
facts = json.loads(Path(summary['full_facts']['path']).read_text())
for key in ('producer', 'input_bindings', 'result_and_options'):
    identity(facts[key]['path'], facts[key])
for row in facts['actual_archived_query_sources_unchanged'] + facts['artifacts']:
    identity(row['path'], row)
assert len(facts['artifacts']) == 61
placed_review_path = OUT / 'R006_AT002_place_supplement_review_evidence.json'
identity(placed_review_path)
placed_review = json.loads(placed_review_path.read_text())
placed_facts_path = AT / 'place_readonly_closed_phase_facts.json'
identity(placed_facts_path, dict(path=str(placed_facts_path), bytes=138834,
    sha256='e151be401b138df8618f91a78831abeb49e3c7c522b17652d591ecf3529ba574'))
placed_facts = json.loads(placed_facts_path.read_text())
# Verify reused placed products remain the exact independently audited inputs.
for row in placed_facts['artifacts']:
    identity(row['path'], row)
identical = []
for name in ('boundary_drivers.tsv', 'target_net_loads.tsv', 'target_net_position_envelopes.tsv',
             'fixed_window_occupancy.tsv', 'fixed_window_attached_connections.tsv'):
    assert (REPORT / 'physopt' / name).read_bytes() == (REPORT / 'place' / name).read_bytes()
    identical.append(name)
for i in range(48):
    name = f'fixed_window_{i}_actual_tiles.txt'
    assert (REPORT / 'physopt' / name).read_bytes() == (REPORT / 'place' / name).read_bytes()
    identical.append(name)
assert facts['per_net_loads'] == placed_facts['per_net_loads']
assert facts['load_groups'] == placed_facts['load_groups'] == summary['load_groups']
assert facts['load_groups'] == placed_review['load_groups_independently_recomputed']
assert len(facts['per_net_loads']) == 94 and facts['position_envelope_rows'] == 97
mapping = table(REPORT / 'physopt/placed_reference_site_SLR_mapping.tsv')
placed_mapping = table(REPORT / 'place/placed_reference_site_SLR_mapping.tsv')
assert len(mapping) == 56
for now, before in zip(mapping, placed_mapping):
    assert now['phase_context'] == 'physopt' and before['phase_context'] == 'place'
    assert {k:v for k,v in now.items() if k != 'phase_context'} == {k:v for k,v in before.items() if k != 'phase_context'}
hierarchy_checks = []
for suffix in ('input', 'gate', 'down', 'depth7'):
    name = f'utilization_hierarchy_{suffix}.rpt'
    current = [line for line in (REPORT / 'physopt' / name).read_text().splitlines() if line.startswith('|') and line.endswith('|')]
    previous = [line for line in (REPORT / 'place' / name).read_text().splitlines() if line.startswith('|') and line.endswith('|')]
    assert current == previous and current
    hierarchy_checks.append(dict(report=name, native_table_rows=len(current), actual_tables_equal=True,
        metadata_differences='Native dates/output paths and Design State Fully Placed versus Physopt postPlace preserved'))
for prefix in ('optimized_boundaries', 'optimized_control_sources'):
    p = ORIGINAL / f'{prefix}_physopt.tsv'
    identity(p)
    assert table(p) == table(ORIGINAL / f'{prefix}_place.tsv')
phase_rows = table(REPORT / 'phase_receipts.tsv')
assert len(phase_rows) == 2 and [r['phase'] for r in phase_rows] == ['place', 'physopt']
assert phase_rows[1] == facts['phase_receipt'] == summary['phase_receipt']
queries = table(REPORT / 'physopt/query_receipts.tsv')
assert len(queries) == 60 and all(r['native_tcl_code'] == '0' for r in queries)
assert {r['query'] for r in queries if r['query'].startswith('fixed_native_window_')} == {f'fixed_native_window_{i}' for i in range(48)}
phase_identity = dict(line.split('\t', 1) for line in (REPORT / 'physopt/identity.tsv').read_text().splitlines())
assert phase_identity == facts['phase_identity'] == summary['phase_identity']
assert phase_identity['phase'] == 'physopt' and phase_identity['checkpoint'] == str(ORIGINAL / 'physopt.dcp')
assert phase_identity['tool'] == '2025.2' and phase_identity['PART'] == 'xcvu9p-flga2104-2L-e' and phase_identity['blackboxes'] == '0'

terminal_summary_path = AT / 'readonly_terminal_summary.json'
identity(terminal_summary_path, dict(path=str(terminal_summary_path), bytes=3518,
    sha256='aa14c8430e2034774a7bd1aad9df626b7de5cde7ec5a3d571017e95cc90dfc5f'))
terminal_summary = json.loads(terminal_summary_path.read_text())
identity(terminal_summary['full_facts']['path'], terminal_summary['full_facts'])
terminal = json.loads(Path(terminal_summary['full_facts']['path']).read_text())
for key in ('status','resources_identity','freeze_manifest','input_bindings','command','started','producer','closed_log','result','phase_receipts'):
    identity(terminal[key]['path'], terminal[key])
for row in terminal['actual_archived_source_checks']:
    assert row['actual'] == row['expected']
    identity(row['actual']['path'], row['actual'])
status = json.loads(Path(terminal['status']['path']).read_text())
started = json.loads(Path(terminal['started']['path']).read_text())
bindings = json.loads(Path(terminal['input_bindings']['path']).read_text())
assert status['inputs'] == started['inputs'] == terminal['input_bindings']
assert status['native_exit_code'] == status['exit_code'] == 0 and status['execution_state'] == 'completed'
assert status['stop_reason'] is None and status['post_integrity_error'] is None
assert status['native_natural_terminal_observed'] and not status['cleanup_was_required']
assert not status['owned_before_cleanup'] and not status['owned_before_reap'] and not status['owned_survivors']
assert status['physical_commands_executed'] is False and status['checkpoint_write_executed'] is False
assert status['frozen_inputs_after'] == bindings['frozen_inputs']
identity(bindings['contract']['path'], bindings['contract'])
freeze = json.loads(Path(terminal['freeze_manifest']['path']).read_text())
assert len(freeze['files']) == terminal['production_files_checked'] == 144 and terminal['production_mismatches'] == []
assert terminal['freeze_manifest'] == bindings['frozen_inputs']['freeze']
assert terminal['new_peak_source_report_checks'] == {} and 'new_peak_source_reports' not in bindings
dcp_stat_bindings = []
for phase, row in terminal['original_checkpoint_checks'].items():
    assert row['actual'] == row['expected'] == bindings['checkpoints'][phase]
    assert Path(row['actual']['path']).stat().st_size == row['actual']['bytes']
    dcp_stat_bindings.append(dict(phase=phase, engineering_rehash=row['actual'], independently_stat_size=True, binary_read_by_A007=False))
assert facts['original_checkpoint_rehashed_unchanged'] == bindings['checkpoints']['physopt']
for phase, phase_facts in zip(phase_rows, terminal['phases']):
    assert phase == phase_facts['receipt'] and phase['native_tcl_code'] == '0'
    assert phase_facts['query_count'] == 60 and not phase_facts['native_query_failures']
    for key in ('result','result_and_options','closed_phase_facts'):
        identity(phase_facts[key]['path'], phase_facts[key])
    assert Path(phase['result_and_options_file']).read_text() == 'result {} options {-code 0 -level 0}\n'
log = Path(terminal['closed_log']['path']).read_bytes()
assert log == (REPORT / 'vivado.log').read_bytes()
assert log.startswith((OUT / 'R006_AT002_place_closed_then_physopt_open_native_prefix.txt').read_bytes())
text = log.decode()
assert text.count('E005_READONLY_PHYSICAL_SUPPLEMENT_COMPLETED') == 2
assert 'E005_READONLY_PHASE_COMPLETED place native_tcl_code=0' in text
assert 'E005_READONLY_PHASE_COMPLETED physopt native_tcl_code=0' in text
assert 'E005_READONLY_TWO_PHASE_SUPPLEMENT_COMPLETED' in text
assert 'Exiting Vivado at Fri Oct 16 22:45:05 2026' in text

resource_rows = [json.loads(line) for line in Path(terminal['resources_identity']['path']).read_text().splitlines()]
times = [datetime.fromisoformat(r['utc']) for r in resource_rows]
gaps = [(b-a).total_seconds() for a,b in zip(times,times[1:])]
peak = max(r['rss_bytes'] for r in resource_rows)
min_mem = min(r['mem_available_bytes'] for r in resource_rows)
min_disk = min(r['disk_free_bytes'] for r in resource_rows)
assert len(resource_rows) == terminal['resources']['samples'] == 422
assert peak == terminal['resources']['sampled_peak_tree_rss_bytes'] == status['max_tree_rss_bytes']
assert min_mem == terminal['resources']['minimum_mem_available_bytes'] == status['minimum_mem_available_bytes']
assert min_disk == terminal['resources']['minimum_disk_free_bytes'] == status['minimum_disk_free_bytes']
assert max(gaps) == terminal['resources']['maximum_sample_interval_seconds'] == 5.146364
assert min(gaps) > 0
assert all(row['rss_bytes'] == sum(p['rss_bytes'] for p in row['processes'].values()) for row in resource_rows)
assert all(p['nice'] == 5 for row in resource_rows for p in row['processes'].values())
assert peak < 192*2**30 and min_mem > 48*2**30 and min_disk > 30*2**30
elapsed = (datetime.fromisoformat(status['ended_utc'])-datetime.fromisoformat(status['started_utc'])).total_seconds()
assert elapsed == terminal['attempt_seconds'] == 2141.43421
current_process_checks = []
for row in terminal['process_checks']:
    assert not row['original_identity_present'] and not row['original_live']
    p = Path(f"/proc/{row['pid']}/stat")
    current = dict(pid=row['pid'], expected_start_ticks=row['expected_start_ticks'], original_identity_present=False)
    if p.exists():
        fields = p.read_text().rsplit(')',1)[1].split()
        current.update(current_start_ticks=int(fields[19]), state=fields[0], original_identity_present=int(fields[19]) == row['expected_start_ticks'])
    assert not current['original_identity_present']
    current_process_checks.append(current)
assert len(current_process_checks) == 4
lock_stat = (ROOT / 'project/hardware/vivado/.m002_eda.lock').stat()
lock_rows = [line for line in Path('/proc/locks').read_text().splitlines() if re.search(r':'+str(lock_stat.st_ino)+r'\s', line)]
old_pids = {r['pid'] for r in current_process_checks}
assert all(int(line.split()[4]) not in old_pids for line in lock_rows)
assert terminal['lane_lock_probe']['probe'] == 'exclusive_nonblocking_acquire_succeeded' and terminal['lane_lock_probe']['released_immediately']
record = dict(reviewed_utc=datetime.now(timezone.utc).isoformat(), identity_checks=checks,
    independent_physopt_native_phase_seconds=int(phase_rows[1]['ended_epoch'])-int(phase_rows[1]['started_epoch']),
    phase_receipts=phase_rows, physopt_query_count=len(queries), all_queries_zero=True,
    physopt_source_identity=phase_identity,
    byte_identical_actual_phase_tables_and_tile_lists=identical,
    actual94net_97position_80boundary_48window_data_equal_independently_reviewed_placed=True,
    native_original_physopt80boundary14upstream_match=True,
    actual56_site_mapping_equal_except_phase=True, hierarchy_native_tables=hierarchy_checks,
    load_groups=summary['load_groups'], gate_crossing_rows=placed_review['gate_crossing_rows'],
    upstream_crossing_rows=placed_review['upstream_crossing_rows'], position_spans=placed_review['position_spans'],
    hierarchy=placed_review['hierarchical_utilization'], fixed_window_priorities=placed_review['priority_fixed_windows'],
    natural_terminal=dict(native=0, supervisor=0, started=status['started_utc'], ended=status['ended_utc'],
        attempt_seconds=elapsed, native_exit_local='2026-10-16 22:45:05', stop=None, cleanup_required=False, survivors=[]),
    original_DCP_engineering_rehash_and_independent_stat=dcp_stat_bindings,
    original144_freeze=dict(manifest=terminal['freeze_manifest'], engineering_full_rehash_count=144, mismatches=[],
        A007_scope='Manifest identity, count, producer and wrapper-after receipt binding; no redundant144-file rehash'),
    resources_independently_recomputed=dict(samples=len(resource_rows), peak_RSS_GiB=peak/2**30,
        min_MemAvailable_GiB=min_mem/2**30, min_disk_GiB=min_disk/2**30, max_gap_seconds=max(gaps), all_recorded_nice_5=True),
    independent_current_original_process_checks=current_process_checks,
    engineering_terminal_lock_probe=terminal['lane_lock_probe'], current_lock_rows=lock_rows,
    lock_scope='A007 reads /proc/locks only; A006 recorded actual exclusive acquire/release at terminal. Later AT003 may own lane, no current-unlocked claim.',
    new_peak_check_scope='AT002 has no new_peak_source_reports: engineering all(empty)=true is not new peak measurement/coverage.',
    execution='AT002 both readonly phases and natural supervisor terminal independently reviewed completed',
    verdict='Actual physopt measured outputs equal placed across reviewed targets; this does not improve existing route FAIL or formal hold/CDC safety.',
    applicability='Each own original AT003 closed DCP; original logs/source/freeze preserved',
    review='A007 bounded text/hash/aggregate/proc review, reused placed proofs. New12peak/10region AT003 obligation remains pending actual outputs.')
destination = OUT / 'R006_AT002_physopt_terminal_review_evidence.json'
with destination.open('x') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2); stream.write('\n')
print(json.dumps(dict(evidence=str(destination), identity_checks=len(checks), resource=record['resources_independently_recomputed'],
    physopt_seconds=record['independent_physopt_native_phase_seconds'], natural_terminal=record['natural_terminal'],
    process_checks=current_process_checks, lock_rows=lock_rows), ensure_ascii=False, indent=2))
