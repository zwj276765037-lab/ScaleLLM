"""Independent new-peak region audit from fixed text; no EDA or DCP reads."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['place', 'physopt'])
parser.add_argument('summary_bytes', type=int)
parser.add_argument('summary_sha256')
args = parser.parse_args()
ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent
AT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT003_new_peak_windows_readonly'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT003_new_peak_windows_readonly'
P = REPORT / args.phase
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


def counts(value):
    words = value.split()
    assert len(words) % 2 == 0
    result = {words[i]: int(words[i+1]) for i in range(0,len(words),2)}
    assert len(result)*2 == len(words)
    return result


summary_path = AT / f'{args.phase}_readonly_closed_phase_summary.json'
identity(summary_path, dict(path=str(summary_path), bytes=args.summary_bytes, sha256=args.summary_sha256))
summary = json.loads(summary_path.read_text())
identity(summary['full_facts']['path'], summary['full_facts'])
facts = json.loads(Path(summary['full_facts']['path']).read_text())
for key in ('input_bindings', 'source_report', 'independent_targets', 'result_and_options', 'producer'):
    identity(facts[key]['path'], facts[key])
for row in facts['actual_archived_sources_unchanged'] + facts['artifacts']:
    identity(row['path'], row)
assert len(facts['artifacts']) == 17
bindings = json.loads(Path(facts['input_bindings']['path']).read_text())
old_bindings_path = AT.parent / 'AT002_closed_place_physopt_readonly/input_bindings.json'
identity(old_bindings_path)
old_bindings = json.loads(old_bindings_path.read_text())
parent_fields = ['contract','checkpoints','parent','parent_status','parent_integrity','parent_constraints',
    'phase_integrities','phase_commands','route_status','route_command','actual_route_receipt',
    'placed_reference','frozen_inputs','resource_helper']
assert all(bindings[key] == old_bindings[key] for key in parent_fields)
fixed = ROOT / 'agent/A006/new_worst_window_supplement/fixed_preparation_v2'
fixed_manifest = json.loads((fixed / 'manifest.json').read_text())
expected_sources = {Path(row['path']).name: row for row in fixed_manifest['fixed_sources']}
for row in bindings['sources']:
    if Path(row['path']).name == 'jobs.tcl': continue
    expected = expected_sources[Path(row['path']).name]
    assert (row['bytes'], row['sha256']) == (expected['bytes'], expected['sha256'])
assert bindings['sources'] == facts['actual_archived_sources_unchanged']
manifest = json.loads((AT / 'sources/new_worst_targets_manifest.json').read_text())
independent = json.loads(Path(facts['independent_targets']['path']).read_text())
spec = manifest['phases'][args.phase]
reference = next(p for p in independent['phases'] if p['phase'] == args.phase)
assert facts['source_report'] == spec['source_report'] == reference['source_report_identity'] == bindings['new_peak_source_reports'][args.phase]
source_rows = table(P / 'source_congestion_rows.tsv')
assert source_rows == facts['retained_source_rows']
assert source_rows == [dict(native_line=str(r['native_line']), direction=r['direction'], type=r['type'],
    reported_level=str(r['level']), native_endpoint_1=r['endpoints'][0], native_endpoint_2=r['endpoints'][1],
    selected_peak=str(int(r['selected_peak'])), region_id=r['region_id']) for r in spec['source_rows']]
assert len(source_rows) == 48
native_lines = Path(facts['source_report']['path']).read_text().splitlines()
for row in source_rows:
    cells = [v.strip() for v in native_lines[int(row['native_line'])-1].split('|')[1:-1]]
    assert cells[:4] == [row['direction'], row['type'], row['reported_level'],
        '('+row['native_endpoint_1']+','+row['native_endpoint_2']+')']
selected = [r for r in source_rows if r['selected_peak'] == '1']
assert len(selected) == 12
assert [(int(r['native_line']),r['direction'],r['type'],int(r['reported_level']),r['native_endpoint_1'],r['native_endpoint_2'],r['region_id']) for r in selected] == [
    (r['native_line'],r['direction'],r['type'],r['level'],r['first_tile'],r['last_tile'],r['unique_region_id']) for r in reference['selected_rows']]
assert len({(r['direction'], r['type']) for r in selected}) == 12
declaration = table(P / 'source_report_identity.tsv')
assert declaration == [dict(source_report_path=facts['source_report']['path'], bytes=str(facts['source_report']['bytes']), sha256=facts['source_report']['sha256'])]
raw_regions = table(P / 'new_peak_region_occupancy.tsv')
connections = table(P / 'new_peak_region_attached_connections.tsv')
assert len(raw_regions) == len(connections) == 10
conn_map = {r['region_id']:r for r in connections}
expected_regions = {r['region_id']: r['endpoints'] for r in spec['unique_regions']}
assert set(conn_map) == {r['region_id'] for r in raw_regions} == set(expected_regions)
converted, compact, tile_sets = [], [], {}
for row in raw_regions:
    rid = row['region_id']; endpoints = expected_regions[rid]
    assert [row['native_endpoint_1'], row['native_endpoint_2']] == endpoints
    bounds = [int(row[k]) for k in ('actual_GRID_POINT_Xmin','actual_GRID_POINT_Ymin','actual_GRID_POINT_Xmax','actual_GRID_POINT_Ymax')]
    tiles_path = P / f'new_peak_{rid}_actual_tiles.txt'
    tiles = tiles_path.read_text().splitlines(); tile_set = set(tiles); tile_sets[rid] = tile_set
    assert len(tiles) == len(tile_set) == int(row['tile_count'])
    assert set(endpoints) <= tile_set
    assert (bounds[2]-bounds[0]+1)*(bounds[3]-bounds[1]+1) == len(tiles)
    capacity, used, refs, slrs = [counts(row[k]) for k in ('site_TYPE_capacity','occupied_site_TYPE_counts','primitive_REF_counts','SLR_site_counts')]
    assert sum(capacity.values()) == sum(slrs.values()) == int(row['site_count'])
    assert sum(refs.values()) == int(row['primitive_count'])
    assert all(0 <= v <= capacity[k] for k,v in used.items())
    assert set(slrs) == {'SLR1'}
    assert used['SLICEL'] == capacity['SLICEL'] and used['SLICEM'] == capacity['SLICEM']
    conn = conn_map[rid]
    assert conn['scope'] == 'attached_segments_only_not_boundary_crossings_or_congestion'
    assert row['current_fixed_congestion_metric'] == 'UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API'
    tile_identity = next(r for r in facts['artifacts'] if r['path'] == str(tiles_path))
    converted.append(dict(region_id=rid, native_endpoints=endpoints, actual_GRID_bounds=bounds,
        tile_count=len(tiles), site_count=int(row['site_count']), primitive_count=int(row['primitive_count']),
        site_TYPE_capacity=capacity, occupied_site_TYPE_counts=used, primitive_REF_counts=refs, SLR_site_counts=slrs,
        primitive_input_leaf_pins=int(conn['primitive_input_leaf_pins']), primitive_output_leaf_pins=int(conn['primitive_output_leaf_pins']),
        attached_hierarchical_net_segments=int(conn['attached_hierarchical_net_segments']),
        selected_source_rows=[r for r in selected if r['region_id'] == rid], actual_tiles=tile_identity))
    compact.append(dict(region_id=rid, peak_rows=[r['direction']+'/'+r['type'] for r in selected if r['region_id'] == rid],
        actual_GRID_bounds=bounds, tile_count=len(tiles), site_count=int(row['site_count']), SLR='SLR1',
        occupied_SLICE_sites=used['SLICEL']+used['SLICEM'], capacity_SLICE_sites=capacity['SLICEL']+capacity['SLICEM'],
        RAMB36_used_capacity=[used.get('RAMB36',0),capacity.get('RAMB36',0)],
        URAM288_used_capacity=[used.get('URAM288',0),capacity.get('URAM288',0)],
        DSP48E2_used_capacity=[used.get('DSP48E2',0),capacity.get('DSP48E2',0)],
        attached_hierarchical_net_segments=int(conn['attached_hierarchical_net_segments'])))
assert converted == facts['region_measurements']
assert summary['per_region_SLR_sites'] == {r['region_id']:r['SLR_site_counts'] for r in converted}
queries = table(P / 'query_receipts.tsv')
assert len(queries) == 15 and all(r['native_tcl_code'] == '0' for r in queries)
assert {r['query'] for r in queries} == {'open_checkpoint','identity','topology','target_scope','new_peak_native_regions'} | {f'region_NW{i:03}' for i in range(1,11)}
phase_receipt = next(r for r in table(REPORT / 'phase_receipts.tsv') if r['phase'] == args.phase)
assert phase_receipt == facts['phase_receipt'] == summary['phase_receipt'] and phase_receipt['native_tcl_code'] == '0'
assert Path(facts['result_and_options']['path']).read_text() == 'result {} options {-code 0 -level 0}\n'
actual_identity = dict(line.split('\t',1) for line in (P / 'identity.tsv').read_text().splitlines())
assert actual_identity == facts['phase_identity'] == summary['phase_identity']
assert actual_identity['phase'] == args.phase and actual_identity['checkpoint'] == bindings['checkpoints'][args.phase]['path']
assert actual_identity['tool'] == '2025.2' and actual_identity['PART'] == 'xcvu9p-flga2104-2L-e' and actual_identity['blackboxes'] == '0'
dcp = facts['original_checkpoint_rehashed_unchanged']
assert dcp == bindings['checkpoints'][args.phase] and Path(dcp['path']).stat().st_size == dcp['bytes']
start_path = AT / 'native_readonly_started_observation.json'
identity(start_path, dict(path=str(start_path),bytes=5760,sha256='cdcd65dc2fca53c4d728448d5a9a8c0e01151fb25fcdb853e449c8764b18c1be'))
start = json.loads(start_path.read_text())
for key in ('started','input_bindings','native_log_prefix'):
    identity(start[key]['path'], start[key])
assert start['input_bindings'] == facts['input_bindings']
assert start['actual_archived_sources_unchanged'] == bindings['sources']
assert all(p['nice'] == 5 and p['affinity'] == list(range(8)) and p['actual_start_ticks'] == p['expected_start_ticks'] for p in [start['supervisor']]+start['owned_processes'])
log = (REPORT / 'vivado.log').read_bytes()
assert log.startswith(Path(start['native_log_prefix']['path']).read_bytes())
assert f'E005_READONLY_PHASE_COMPLETED {args.phase} native_tcl_code=0'.encode() in log
assert ('Command: open_checkpoint '+dcp['path']).encode() in log
snapshot = OUT / f'R006_AT003_{args.phase}_closed_native_prefix.txt'
with snapshot.open('xb') as stream: stream.write(log)
identity(snapshot)
pair_intersections = [dict(a=a,b=b,shared_tiles=len(tile_sets[a]&tile_sets[b])) for a in tile_sets for b in tile_sets if a < b]
assert all(p['shared_tiles'] > 0 for p in pair_intersections)
record = dict(reviewed_utc=datetime.now(timezone.utc).isoformat(), phase=args.phase, identity_checks=checks,
    source_scope='12 maximum-level direction/type rows mapped to10 unique regions, all48 original native rows retained',
    all48_source_rows_match_native_manifest=True, exact12peak_10NW_independent_mapping_match=True,
    actual_region_measurements=converted, compact_regions=compact,
    actual_tile_lists_unique_count_endpoints_match=True, GRID_rectangle_cardinality_matches=True,
    capacity_occupied_primitive_and_SLR_histograms_reconciled=True,
    tile_overlap=dict(unique_union_tiles=len(set().union(*tile_sets.values())), all45_pairs_overlap=True, pair_intersections=pair_intersections),
    native_phase_receipt=phase_receipt, native_phase_seconds=int(phase_receipt['ended_epoch'])-int(phase_receipt['started_epoch']),
    query_count=15, all_queries_zero=True, original_checkpoint_engineering_rehash_and_independent_stat=dcp,
    parent_binding_fields_unchanged_from_AT002=parent_fields, archived_sources_match_static_fixed_V2=True,
    startup_observation_bound=True, native_prefix=str(snapshot),
    limits=['SLICE occupied means distinct sites with at least one mapped primitive, not100%LUT/FF/BEL capacity.',
        'Every region site maps to SLR1; not a claim that all route failures or design cells are in SLR1.',
        '10 regions overlap; no per-region capacity/primitive/connection sum is a whole-device total.',
        'Primitive REF counts include DSP subprimitives; BRAM alternative site modes are not additive blocks.',
        'Input/output primitive pins include enumerated primitive pins; not dynamic traffic or cross-boundary nets.',
        'Attached hierarchical net segments are not global logical-net, SLL or boundary-crossing counts.',
        'Reported native Level6 selected the windows; current fixed-window congestion remains UNAVAILABLE.',
        '36 nonpeak rows retained without separate-region measurement claims; route-stage INT windows not included.'],
    execution='This native phase and bounded independent review completed; full session terminal separate',
    verdict='Targeted new peak mapping supported for this own closed DCP; measured dense SLR1 locations do not establish sole causal source of route failure',
    review='Independent native TSV/hash/aggregate checks; no EDA/test/DCP read, process control or production edit')
destination = OUT / f'R006_AT003_{args.phase}_new_peak_review_evidence.json'
with destination.open('x') as stream: json.dump(record,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps(dict(evidence=str(destination), identity_checks=len(checks), phase_seconds=record['native_phase_seconds'],
    compact_regions=compact, unique_union_tiles=record['tile_overlap']['unique_union_tiles']),ensure_ascii=False,indent=2))
