#!/usr/bin/env python3
"""Capture fixed, naturally closed read-only phase outputs; no EDA/control."""
import argparse
import csv
import hashlib
import json
import shutil
import tkinter
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs'
ATTEMPT = BASE / 'R006/attempts/AT002_closed_place_physopt_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly'
TCL = tkinter.Tcl()


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


def rows(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))


def tlist(value):
    return list(TCL.splitlist(value))


def counts(value):
    terms = tlist(value)
    assert len(terms) % 2 == 0, value
    return {terms[n]: int(terms[n + 1]) for n in range(0, len(terms), 2)}


def save_new(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['place', 'physopt'])
    args = parser.parse_args()
    phase = args.phase
    output = REPORT / phase
    receipts = rows(REPORT / 'phase_receipts.tsv')
    phase_rows = [r for r in receipts if r['phase'] == phase]
    assert len(phase_rows) == 1, 'Phase has no unique natural completion receipt'
    phase_receipt = phase_rows[0]
    assert phase_receipt['native_tcl_code'] == '0', phase_receipt
    queries = rows(output / 'query_receipts.tsv')
    assert len({r['query'] for r in queries}) == len(queries)
    assert all(r['native_tcl_code'] == '0' for r in queries), 'Native query failure retained; inspect raw output'
    result = (output / 'result.txt').read_text()
    assert 'failed_queries=\n' in result
    assert 'checkpoint_mutated=false' in result and 'physical_commands_executed=false' in result
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    actual_identity = dict(line.split('\t', 1) for line in (output / 'identity.tsv').read_text().splitlines())
    assert actual_identity['checkpoint'] == bindings['checkpoints'][phase]['path']
    assert actual_identity['phase'] == phase and actual_identity['tool'] == '2025.2'
    assert actual_identity['PART'] == 'xcvu9p-flga2104-2L-e' and actual_identity['blackboxes'] == '0'
    source_checks = []
    for expected in bindings['sources']:
        actual = identity(expected['path'])
        assert actual == expected, ('Archived query source changed', actual)
        source_checks.append(actual)
    checkpoint = identity(actual_identity['checkpoint'])
    assert checkpoint == bindings['checkpoints'][phase], 'Original source checkpoint drift'
    boundary = rows(output / 'boundary_drivers.tsv')
    assert Counter(r['scope'] for r in boundary) == {'input': 48, 'gate': 16, 'down': 16}
    assert len({r['cell'] for r in boundary}) == 80
    assert all(r['REF_NAME'] == ('LUT6' if r['scope'] == 'input' else 'LUT1') for r in boundary)
    assert all(r['SLR'] in ['SLR0', 'SLR1', 'SLR2'] for r in boundary)
    mapping = rows(output / 'placed_reference_site_SLR_mapping.tsv')
    assert len(mapping) == len({r['placed_reference_LOC'] for r in mapping}) == 56
    assert all(r['placed_reference_LOC'] == r['actual_site_NAME'] and r['device_SLR'] in ['SLR0', 'SLR1', 'SLR2'] and r['phase_context'] == phase for r in mapping)
    loads = rows(output / 'target_net_loads.tsv')
    assert len(loads) == len({r['net'] for r in loads}) == 94
    envelopes = rows(output / 'target_net_position_envelopes.tsv')
    by_net = defaultdict(list)
    for row in envelopes:
        by_net[row['net']].append(row)
    groups = defaultdict(lambda: dict(nets=0, leaf_load_pins=0, unique_load_cells_summed_per_net=0, cross_SLR_leaf_load_pins=0, load_SLR_pin_counts=Counter(), driver_SLR_counts=Counter(), driver_REF_counts=Counter()))
    detailed = []
    for row in loads:
        roles = tlist(row['roles'])
        boundary_roles = [r for r in roles if r.startswith('boundary:')]
        assert len(boundary_roles) <= 1
        group = boundary_roles[0].split(':', 2)[1] if boundary_roles else 'upstream'
        n = int(row['leaf_load_pin_count']); unique = int(row['unique_load_cell_count'])
        slrs = counts(row['load_SLR_pin_counts'])
        assert set(slrs) <= {'SLR0', 'SLR1', 'SLR2'}
        assert sum(slrs.values()) == sum(counts(row['load_REF_pin_counts']).values()) == sum(counts(row['load_terminal_counts']).values()) == n
        assert sum(counts(row['load_REF_unique_cell_counts']).values()) == unique
        assert row['source_resolution'] == 'SINGLE_PLACED_DRIVER'
        drivers = tlist(row['driver_SLRs']); refs = tlist(row['driver_REF_NAMEs'])
        assert len(drivers) == len(refs) == 1
        cross = int(row['source_relative_cross_SLR_pin_count'])
        assert cross == n - slrs.get(drivers[0], 0)
        assert {e['SLR']: int(e['leaf_load_pins']) for e in by_net[row['net']]} == slrs
        assert all(int(e['SLICE_pins']) + int(e['nonSLICE_or_unplaced_pins']) == int(e['leaf_load_pins']) for e in by_net[row['net']])
        if group != 'upstream':
            assert n == unique == {'input': 256, 'gate': 384, 'down': 512}[group]
            assert counts(row['load_terminal_counts']) == {'CE': n}
        g = groups[group]; g['nets'] += 1; g['leaf_load_pins'] += n; g['unique_load_cells_summed_per_net'] += unique; g['cross_SLR_leaf_load_pins'] += cross
        g['load_SLR_pin_counts'].update(slrs); g['driver_SLR_counts'].update(drivers); g['driver_REF_counts'].update(refs)
        detailed.append(dict(net=row['net'], group=group, driver_cells=tlist(row['driver_cells']), driver_REF=refs[0], driver_LOCs=tlist(row['driver_LOCs']), driver_SLR=drivers[0], leaf_load_pins=n, unique_load_cells=unique, cross_SLR_leaf_load_pins=cross, load_SLR_pin_counts=slrs, load_REF_pin_counts=counts(row['load_REF_pin_counts']), load_terminal_counts=counts(row['load_terminal_counts']), position_envelopes=by_net[row['net']]))
    assert {key: val['nets'] for key, val in groups.items()} == {'input': 48, 'gate': 16, 'down': 16, 'upstream': 14}
    windows = rows(output / 'fixed_window_occupancy.tsv')
    connections = rows(output / 'fixed_window_attached_connections.tsv')
    assert len(windows) == len(connections) == 48
    assert {r['reference_row'] for r in windows} == {str(i) for i in range(48)}
    assert all(r['current_fixed_congestion_metric'] == 'UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API' for r in windows)
    for window in windows:
        assert sum(counts(window['site_TYPE_capacity']).values()) == sum(counts(window['SLR_site_counts']).values()) == int(window['site_count'])
        assert sum(counts(window['primitive_REF_counts']).values()) == int(window['primitive_count'])
        assert len((output / ('fixed_window_' + window['reference_row'] + '_actual_tiles.txt')).read_text().splitlines()) == int(window['tile_count'])
        assert all(value <= counts(window['site_TYPE_capacity'])[key] for key, value in counts(window['occupied_site_TYPE_counts']).items())
    artifacts = [identity(p) for p in sorted(output.iterdir()) if p.is_file()]
    disposition = identity(Path(phase_receipt['result_and_options_file']))
    producer_archive = ATTEMPT / ('capture_' + phase + '_phase_producer.py')
    shutil.copy2(Path(__file__), producer_archive)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), phase=phase, phase_receipt=phase_receipt,
        native_phase_and_queries_passed=True, query_count=len(queries), failed_queries=[], phase_identity=actual_identity,
        original_checkpoint_rehashed_unchanged=checkpoint, input_bindings=identity(ATTEMPT / 'input_bindings.json'),
        actual_archived_query_sources_unchanged=source_checks, result_and_options=disposition, artifacts=artifacts,
        producer=identity(producer_archive), boundary_driver_count=80, boundary_REF_counts=dict(Counter(r['REF_NAME'] for r in boundary)),
        actual_device_mapped_original_placed_sites=56, original_placed_mapping_scope='Original placed LOCs mapped through same-part actual device topology; never substituted current driver LOCs',
        load_groups=groups, per_net_loads=detailed, position_envelope_rows=len(envelopes), fixed_native_windows=48,
        fixed_window_congestion='UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API',
        fixed_window_scope='Actual device GRID/tile/site/SLR resource occupation and attached hierarchical net segments; overlapping windows are not summed and occupancy is not congestion',
        session_terminal='PENDING_SEPARATE_NATIVE_SUPERVISOR_AND_FULL_FREEZE_PROCESS_LOCK_VERIFICATION',
        physical_commands_executed=False, checkpoint_write_executed=False, formal_signoff=False)
    full = ATTEMPT / (phase + '_readonly_closed_phase_facts.json'); save_new(full, facts)
    summary = {k: facts[k] for k in ['recorded_utc', 'phase', 'phase_receipt', 'query_count', 'failed_queries', 'phase_identity', 'original_checkpoint_rehashed_unchanged', 'input_bindings', 'producer', 'boundary_driver_count', 'boundary_REF_counts', 'actual_device_mapped_original_placed_sites', 'load_groups', 'position_envelope_rows', 'fixed_native_windows', 'fixed_window_congestion', 'fixed_window_scope', 'session_terminal', 'formal_signoff']}
    summary['full_facts'] = identity(full)
    short = ATTEMPT / (phase + '_readonly_closed_phase_summary.json'); save_new(short, summary)
    print(json.dumps(dict(summary=identity(short), full_facts=identity(full), phase=phase, groups=groups), ensure_ascii=False))


if __name__ == '__main__':
    main()
