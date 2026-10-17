"""Bounded terminal/combined-coverage audit, without EDA, DCP reads or lock mutation."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import re

parser = argparse.ArgumentParser()
parser.add_argument('summary_bytes', type=int)
parser.add_argument('summary_sha256')
args = parser.parse_args()
ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent
AT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT003_new_peak_windows_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT003_new_peak_windows_readonly'
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
    with path.open() as stream: return list(csv.DictReader(stream, delimiter='\t'))


summary_path = AT / 'readonly_terminal_summary.json'
identity(summary_path, dict(path=str(summary_path), bytes=args.summary_bytes, sha256=args.summary_sha256))
summary = json.loads(summary_path.read_text())
identity(summary['full_facts']['path'], summary['full_facts'])
terminal = json.loads(Path(summary['full_facts']['path']).read_text())
for key in ('status','resources_identity','freeze_manifest','input_bindings','command','started','producer','closed_log','result','phase_receipts'):
    identity(terminal[key]['path'], terminal[key])
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
dcp_bindings = []
for phase, pair in terminal['original_checkpoint_checks'].items():
    assert pair['actual'] == pair['expected'] == bindings['checkpoints'][phase]
    assert Path(pair['actual']['path']).stat().st_size == pair['actual']['bytes']
    dcp_bindings.append(dict(phase=phase,engineering_rehash=pair['actual'],independently_stat_size=True,binary_read_by_A007=False))
for pair in terminal['actual_archived_source_checks']:
    assert pair['actual'] == pair['expected']
    identity(pair['actual']['path'], pair['actual'])
assert len(terminal['actual_archived_source_checks']) == 6
assert set(terminal['new_peak_source_report_checks']) == {'place','physopt'}
for phase, pair in terminal['new_peak_source_report_checks'].items():
    assert pair['actual'] == pair['expected'] == bindings['new_peak_source_reports'][phase]
    identity(pair['actual']['path'], pair['actual'])
phase_rows = table(REPORT / 'phase_receipts.tsv')
assert [r['phase'] for r in phase_rows] == ['place','physopt']
reviews = {}
for phase, row in zip(('place','physopt'), phase_rows):
    review_path = OUT / f'R006_AT003_{phase}_new_peak_review_evidence.json'
    identity(review_path); review = json.loads(review_path.read_text()); reviews[phase] = review
    assert review['native_phase_receipt'] == row and row['native_tcl_code'] == '0'
    assert review['all48_source_rows_match_native_manifest'] and review['exact12peak_10NW_independent_mapping_match']
    assert len(review['actual_region_measurements']) == 10 and review['query_count'] == 15 and review['all_queries_zero']
    queries = table(REPORT / phase / 'query_receipts.tsv')
    assert len(queries) == 15 and all(r['native_tcl_code'] == '0' for r in queries)
    phase_fact = next(p for p in terminal['phases'] if p['phase'] == phase)
    assert phase_fact['receipt'] == row and phase_fact['query_count'] == 15 and not phase_fact['native_query_failures']
    for key in ('result','result_and_options','closed_phase_facts'):
        identity(phase_fact[key]['path'], phase_fact[key])
    assert Path(row['result_and_options_file']).read_text() == 'result {} options {-code 0 -level 0}\n'
# Equality is checked on actual files from both independent DCP reads.
comparison = []
for name in ['source_congestion_rows.tsv','source_report_identity.tsv','new_peak_region_occupancy.tsv',
             'new_peak_region_attached_connections.tsv'] + [f'new_peak_NW{i:03}_actual_tiles.txt' for i in range(1,11)]:
    equality = (REPORT / 'place' / name).read_bytes() == (REPORT / 'physopt' / name).read_bytes()
    comparison.append(dict(name=name, bytes_equal=equality))
    if name != 'source_report_identity.tsv': assert equality
assert reviews['place']['compact_regions'] == reviews['physopt']['compact_regions']
log = Path(terminal['closed_log']['path']).read_bytes()
assert log == (REPORT / 'vivado.log').read_bytes()
for phase in ('place','physopt'):
    assert log.startswith((OUT / f'R006_AT003_{phase}_closed_native_prefix.txt').read_bytes())
text = log.decode()
assert text.count('E005_READONLY_NEW_PEAK_SUPPLEMENT_COMPLETED') == 2
assert text.count('E005_READONLY_PHASE_COMPLETED') == 2 and 'E005_READONLY_TWO_PHASE_SUPPLEMENT_COMPLETED' in text
native_exit_lines = [line for line in text.splitlines() if 'Exiting Vivado' in line]
assert len(native_exit_lines) == 1
resources = [json.loads(line) for line in Path(terminal['resources_identity']['path']).read_text().splitlines()]
times = [datetime.fromisoformat(r['utc']) for r in resources]
gaps = [(b-a).total_seconds() for a,b in zip(times,times[1:])]
peak = max(r['rss_bytes'] for r in resources)
min_mem = min(r['mem_available_bytes'] for r in resources)
min_disk = min(r['disk_free_bytes'] for r in resources)
assert len(resources) == terminal['resources']['samples']
assert peak == terminal['resources']['sampled_peak_tree_rss_bytes'] == status['max_tree_rss_bytes']
assert min_mem == terminal['resources']['minimum_mem_available_bytes'] == status['minimum_mem_available_bytes']
assert min_disk == terminal['resources']['minimum_disk_free_bytes'] == status['minimum_disk_free_bytes']
assert max(gaps) == terminal['resources']['maximum_sample_interval_seconds'] and min(gaps) > 0
assert all(r['rss_bytes'] == sum(p['rss_bytes'] for p in r['processes'].values()) for r in resources)
assert all(p['nice'] == 5 for r in resources for p in r['processes'].values())
assert peak < 192*2**30 and min_mem > 48*2**30 and min_disk > 30*2**30
elapsed = (datetime.fromisoformat(status['ended_utc'])-datetime.fromisoformat(status['started_utc'])).total_seconds()
assert elapsed == terminal['attempt_seconds']
process_checks = []
for row in terminal['process_checks']:
    assert not row['original_identity_present'] and not row['original_live']
    p = Path(f"/proc/{row['pid']}/stat")
    value = dict(pid=row['pid'],expected_start_ticks=row['expected_start_ticks'],original_identity_present=False)
    if p.exists():
        fields = p.read_text().rsplit(')',1)[1].split()
        value.update(current_start_ticks=int(fields[19]),state=fields[0],original_identity_present=int(fields[19]) == row['expected_start_ticks'])
    assert not value['original_identity_present']; process_checks.append(value)
assert len(process_checks) == 4
lock_stat = (ROOT / 'project/hardware/vivado/.m002_eda.lock').stat()
lock_rows = [line for line in Path('/proc/locks').read_text().splitlines() if re.search(r':'+str(lock_stat.st_ino)+r'\s',line)]
assert all(int(line.split()[4]) not in {r['pid'] for r in process_checks} for line in lock_rows)
assert terminal['lane_lock_probe']['probe'] == 'exclusive_nonblocking_acquire_succeeded' and terminal['lane_lock_probe']['released_immediately']
record = dict(reviewed_utc=datetime.now(timezone.utc).isoformat(), identity_checks=checks,
    phase_receipts=phase_rows, two_phases_actually_measured=True, actual_phase_file_comparison=comparison,
    actual_region_resources_and_connections_equal=True,
    coverage='Each own closed placed/physopt DCP: all48 native rows retained,12direction/type peaks mapped to10unique NW regions;36nonpeak rows not separately mapped;routeINT hotspots excluded',
    region_compact=reviews['physopt']['compact_regions'], new_peak_mapping_obligation='completed_for_controller_accepted12peak_10region_subset',
    fixed_congestion='UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API, not a query failure or implicit zero',
    natural_terminal=dict(native=0,supervisor=0,started=status['started_utc'],ended=status['ended_utc'],attempt_seconds=elapsed,
        native_exit_line=native_exit_lines[0],stop=None,cleanup_required=False,survivors=[]),
    original_DCP_engineering_rehash_and_independent_stat=dcp_bindings,
    production144_freeze=dict(manifest=terminal['freeze_manifest'],engineering_full_rehash_count=144,mismatches=[],
        A007_scope='manifest/count/producer/wrapper-after binding, no redundant144-file rehash'),
    resources_independently_recomputed=dict(samples=len(resources),peak_RSS_GiB=peak/2**30,min_MemAvailable_GiB=min_mem/2**30,
        min_disk_GiB=min_disk/2**30,max_gap_seconds=max(gaps),all_recorded_nice_5=True),
    independent_current_process_checks=process_checks,engineering_terminal_lock_probe=terminal['lane_lock_probe'],current_lock_rows=lock_rows,
    execution='Actual two-phase supplement and natural terminal independently reviewed completed',
    verdict='Remaining accepted physical-comparison coverage gap closed; full implementation goal remains FAIL and individual RTL/SSI causality inconclusive',
    applicability='Exact own closed original AT003 phase DCPs; frozen inputs preserved; bounded peak subset only',
    review='A007 independent bounded text/hash/resource/proc audit; no EDA, tests, DCP reads, production edit, process or lock control')
destination = OUT / 'R006_AT003_terminal_coverage_review_evidence.json'
with destination.open('x') as stream: json.dump(record,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps(dict(evidence=str(destination),identity_checks=len(checks),phase_receipts=phase_rows,
    natural_terminal=record['natural_terminal'],resources=record['resources_independently_recomputed'],
    process_checks=process_checks,lock_rows=lock_rows),ensure_ascii=False,indent=2))
