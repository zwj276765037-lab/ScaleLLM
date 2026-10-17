#!/usr/bin/env python3
"""Capture naturally closed AT003 new-peak device-region measurements."""
import argparse
import csv
import hashlib
import json
import shutil
import tkinter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT003_new_peak_windows_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT003_new_peak_windows_readonly'
TCL = tkinter.Tcl()


def identity(path):
    path = Path(path)
    before = path.stat(); digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))


def counts(value):
    words = TCL.splitlist(value); assert len(words) % 2 == 0
    return {words[i]: int(words[i + 1]) for i in range(0, len(words), 2)}


def put(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['place', 'physopt']); phase = parser.parse_args().phase
    output = REPORT / phase
    receipts = [r for r in table(REPORT / 'phase_receipts.tsv') if r['phase'] == phase]
    assert len(receipts) == 1 and receipts[0]['native_tcl_code'] == '0', 'No naturally closed successful phase'
    queries = table(output / 'query_receipts.tsv')
    assert len(queries) == len({r['query'] for r in queries}) == 15
    assert all(r['native_tcl_code'] == '0' for r in queries)
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    manifest = json.loads((ATTEMPT / 'sources/new_worst_targets_manifest.json').read_text())
    spec = manifest['phases'][phase]
    actual_identity = dict(line.split('\t', 1) for line in (output / 'identity.tsv').read_text().splitlines())
    assert actual_identity['phase'] == phase and actual_identity['checkpoint'] == bindings['checkpoints'][phase]['path']
    assert actual_identity['tool'] == '2025.2' and actual_identity['PART'] == 'xcvu9p-flga2104-2L-e' and actual_identity['blackboxes'] == '0'
    checkpoint = identity(actual_identity['checkpoint']); assert checkpoint == bindings['checkpoints'][phase]
    sources = [identity(r['path']) for r in bindings['sources']]; assert sources == bindings['sources']
    source_report = identity(spec['source_report']['path']); assert source_report == spec['source_report'] == bindings['new_peak_source_reports'][phase]
    declared = table(output / 'source_report_identity.tsv')
    assert declared == [dict(source_report_path=source_report['path'], bytes=str(source_report['bytes']), sha256=source_report['sha256'])]
    source_rows = table(output / 'source_congestion_rows.tsv')
    expected_rows = [dict(native_line=str(r['native_line']), direction=r['direction'], type=r['type'], reported_level=str(r['level']), native_endpoint_1=r['endpoints'][0], native_endpoint_2=r['endpoints'][1], selected_peak=str(int(r['selected_peak'])), region_id=r['region_id']) for r in spec['source_rows']]
    assert source_rows == expected_rows and len(source_rows) == 48
    peaks = [r for r in source_rows if r['selected_peak'] == '1']; assert len(peaks) == 12
    measurements = table(output / 'new_peak_region_occupancy.tsv')
    attached = table(output / 'new_peak_region_attached_connections.tsv')
    regions = {r['region_id']: r for r in spec['unique_regions']}
    assert len(measurements) == len(attached) == len(regions) == 10
    assert {r['region_id'] for r in measurements} == {r['region_id'] for r in attached} == set(regions)
    connection_map = {r['region_id']: r for r in attached}
    converted = []
    for row in measurements:
        key = row['region_id']; expected = regions[key]
        assert [row['native_endpoint_1'], row['native_endpoint_2']] == expected['endpoints']
        assert row['current_fixed_congestion_metric'] == 'UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API'
        tiles = (output / ('new_peak_' + key + '_actual_tiles.txt')).read_text().splitlines()
        assert len(tiles) == len(set(tiles)) == int(row['tile_count']) > 0
        assert set(expected['endpoints']) <= set(tiles)
        capacity = counts(row['site_TYPE_capacity']); occupied = counts(row['occupied_site_TYPE_counts']); refs = counts(row['primitive_REF_counts']); slrs = counts(row['SLR_site_counts'])
        assert sum(capacity.values()) == sum(slrs.values()) == int(row['site_count'])
        assert sum(refs.values()) == int(row['primitive_count'])
        assert all(value <= capacity[key] for key, value in occupied.items())
        assert set(slrs) <= {'SLR0', 'SLR1', 'SLR2'}
        connection = connection_map[key]
        assert connection['scope'] == 'attached_segments_only_not_boundary_crossings_or_congestion'
        bounds = [int(row[k]) for k in ['actual_GRID_POINT_Xmin', 'actual_GRID_POINT_Ymin', 'actual_GRID_POINT_Xmax', 'actual_GRID_POINT_Ymax']]
        assert bounds[0] <= bounds[2] and bounds[1] <= bounds[3]
        converted.append(dict(region_id=key, native_endpoints=expected['endpoints'], actual_GRID_bounds=bounds,
            tile_count=len(tiles), site_count=int(row['site_count']), primitive_count=int(row['primitive_count']),
            site_TYPE_capacity=capacity, occupied_site_TYPE_counts=occupied, primitive_REF_counts=refs, SLR_site_counts=slrs,
            primitive_input_leaf_pins=int(connection['primitive_input_leaf_pins']), primitive_output_leaf_pins=int(connection['primitive_output_leaf_pins']),
            attached_hierarchical_net_segments=int(connection['attached_hierarchical_net_segments']),
            selected_source_rows=[r for r in peaks if r['region_id'] == key], actual_tiles=identity(output / ('new_peak_' + key + '_actual_tiles.txt'))))
    result = (output / 'result.txt').read_text(); assert 'failed_queries=\n' in result
    producer = ATTEMPT / ('capture_' + phase + '_new_peak_producer.py'); shutil.copy2(Path(__file__), producer)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), phase=phase, phase_receipt=receipts[0], query_count=15,
        all_query_codes_zero=True, phase_identity=actual_identity, original_checkpoint_rehashed_unchanged=checkpoint,
        actual_archived_sources_unchanged=sources, input_bindings=identity(ATTEMPT / 'input_bindings.json'),
        source_report=source_report, independent_targets=manifest['independent_targets'], retained_source_rows=source_rows,
        selected_peak_rows=12, unique_regions=10, region_measurements=converted,
        fixed_window_congestion='UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API',
        measurement_scope='12 original Placer Final direction/type peak rows mapped to10 actual device regions; full48 report rows retained; current occupations and attached segments are not congestion or boundary crossings; overlapping regions not summed',
        physical_commands_executed=False, checkpoint_write_executed=False, formal_signoff=False,
        session_terminal='PENDING_SEPARATE_NATIVE_SUPERVISOR_AND_FULL_FREEZE_PROCESS_LOCK_VERIFICATION',
        result_and_options=identity(Path(receipts[0]['result_and_options_file'])), producer=identity(producer),
        artifacts=[identity(p) for p in sorted(output.iterdir()) if p.is_file()])
    full = ATTEMPT / (phase + '_readonly_closed_phase_facts.json'); put(full, facts)
    summary = {k: facts[k] for k in ['recorded_utc', 'phase', 'phase_receipt', 'query_count', 'all_query_codes_zero', 'phase_identity', 'original_checkpoint_rehashed_unchanged', 'source_report', 'independent_targets', 'selected_peak_rows', 'unique_regions', 'fixed_window_congestion', 'measurement_scope', 'session_terminal', 'formal_signoff']}
    summary['per_region_SLR_sites'] = {r['region_id']: r['SLR_site_counts'] for r in converted}
    summary['full_facts'] = identity(full)
    short = ATTEMPT / (phase + '_readonly_closed_phase_summary.json'); put(short, summary)
    print(json.dumps(dict(summary=identity(short), full_facts=identity(full), phase=phase), ensure_ascii=False))


if __name__ == '__main__':
    main()
