"""Offline joins of original native R004 tables; never opens an EDA process."""
from pathlib import Path
import collections
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'project/hardware/vivado/reports/m003_E011_R004_AT001_failed_route_driver_region_localization'
AT = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R004/attempts/AT001_failed_route_driver_region_localization'
OLD = ROOT / 'project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/evidence/native'


def rows(path):
    with path.open() as handle:
        yield from csv.DictReader(handle, delimiter='\t')


def table(path, header, data):
    with path.open('x', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(header)
        writer.writerows(data)


def identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4194304), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def main():
    target = AT / 'evidence/offline_attribution'
    target.mkdir(exist_ok=False)
    coverage = json.loads((OUT / 'unknowns_and_coverage.json').read_text())
    old_coverage = json.loads((OLD / 'unknowns_and_coverage.json').read_text())
    key_columns = ('driver_module', 'source_SLR', 'load_SLR_set')
    new_groups = {tuple(r[k] for k in key_columns): int(r['unique_conflict_nets'])
                  for r in rows(OUT / 'module_region_summary.tsv')}
    old_groups = {tuple(r[k] for k in key_columns): int(r['unique_conflict_nets'])
                  for r in rows(OLD / 'module_region_summary.tsv')}
    denominator = coverage['canonical_conflict_nets']
    old_denominator = old_coverage['canonical_conflict_nets']
    keys = sorted(new_groups.keys() | old_groups.keys(), key=lambda k: (-new_groups.get(k, 0), k))
    table(target / 'same_scope_E009_group_comparison.tsv',
          [*key_columns, 'old_canonical_conflicts', 'current_canonical_conflicts', 'delta',
           'old_fraction', 'current_fraction', 'physical_version_same'],
          ([*k, old_groups.get(k, 0), new_groups.get(k, 0),
            new_groups.get(k, 0) - old_groups.get(k, 0),
            old_groups.get(k, 0) / old_denominator, new_groups.get(k, 0) / denominator,
            'NO_DIFFERENT_DESIGN_AND_PLACE_ROUTE'] for k in keys))
    modules = collections.Counter()
    for key, count in new_groups.items():
        modules[key[0]] += count
    table(target / 'actual_driver_module_ranking.tsv',
          ['rank', 'driver_module', 'canonical_conflict_nets', 'fraction_of_current_canonical'],
          ([i + 1, name, count, count / denominator]
           for i, (name, count) in enumerate(modules.most_common())))
    # Route samples are actual resources. Truncated samples establish only that
    # listed SLRs were visited, never that no omitted SLR was visited.
    sample_slrs = collections.defaultdict(set)
    sample_regions = collections.defaultdict(set)
    for row in rows(OUT / 'sampled_route_nodes.tsv'):
        sample_slrs[row['canonical']].add(row['SLR'])
        sample_regions[row['canonical']].add(row['clock_region'])
    failed = {r['canonical']: r for r in rows(OUT / 'failed_nets.tsv')}
    sample_data = []
    for receipt in rows(OUT / 'route_sample_receipts.tsv'):
        name = receipt['canonical']
        net = failed.get(name, {})
        sample_data.append([name, net.get('driver_module', 'SUPPLEMENTAL_NONCONFLICT'),
                            net.get('source_SLR', 'NOT_MEASURED'), net.get('load_SLRs', 'NOT_MEASURED'),
                            receipt['node_count'], receipt['complete_node_export'],
                            receipt['region_mapping_complete'], receipt['unknown_mapping_node_count'],
                            ','.join(sorted(sample_slrs[name])),
                            ','.join(sorted(sample_regions[name])), receipt['native_code'],
                            'NO_OMITTED_REGION_EXCLUSION' if receipt['complete_node_export'] != '1'
                            else 'COMPLETE_NATIVE_GET_NODES_SET'])
    table(target / 'actual_route_sample_regions.tsv',
          ['canonical', 'driver_module', 'source_SLR', 'load_SLRs', 'native_node_count',
           'complete_node_export', 'region_mapping_complete', 'unknown_mapping_node_count',
           'observed_route_SLRs', 'observed_route_clockregions',
           'native_code', 'coverage_limit'], sample_data)
    # Full endpoint placement-to-window joins use only actual native site/TILE
    # and GRID_POINT facts. Neighbor placement percentages are not net shares.
    context = json.loads((AT / 'evidence/offline_existing_failure_context_stage_labels_v2.json').read_text())
    tiles = {r['tile']: r for r in rows(OUT / 'device_tiles.tsv')}
    import re
    windows = []
    unresolved_windows = []
    for index, window in enumerate(context['congestion_windows']):
        corners = re.findall(r'[A-Z][A-Z0-9_]*_X\d+Y\d+', window['physical_window'])
        if len(corners) != 2 or any(c not in tiles for c in corners):
            unresolved_windows.append(index)
            continue
        try:
            p, q = (tiles[c] for c in corners)
            xs = sorted((int(p['GRID_POINT_X']), int(q['GRID_POINT_X'])))
            ys = sorted((int(p['GRID_POINT_Y']), int(q['GRID_POINT_Y'])))
        except (ValueError, KeyError):
            unresolved_windows.append(index)
            continue
        windows.append((index, window, xs, ys))
    tile_windows = {}
    for name, tile in tiles.items():
        try:
            x, y = int(tile['GRID_POINT_X']), int(tile['GRID_POINT_Y'])
        except ValueError:
            continue
        matches = [index for index, _, xs, ys in windows
                   if xs[0] <= x <= xs[1] and ys[0] <= y <= ys[1]]
        if matches:
            tile_windows[name] = matches
    site_tiles = {r['site']: r['tile'] for r in rows(OUT / 'site_tiles.tsv')}
    has_site_tiles = any(k != 'NOT_MEASURED' and v and v != 'NOT_MEASURED'
                         for k, v in site_tiles.items())
    cells = {r['name']: (r['LOC'], r['REF_NAME']) for r in rows(OUT / 'cells.tsv')}
    incidence = collections.defaultdict(set)
    missing_endpoint_rows = 0
    for endpoint in rows(OUT / 'endpoints.tsv'):
        name = endpoint['canonical']
        if name not in failed:
            continue
        loc, ref = cells.get(endpoint['owner'], ('', ''))
        # Preserve the E009 DSP child-to-parent location rule.
        owner = endpoint['owner']
        while not loc and ref.startswith('DSP') and '/' in owner:
            owner = owner.rsplit('/', 1)[0]
            loc, ref = cells.get(owner, ('', ''))
        tile = site_tiles.get(loc)
        if not tile:
            missing_endpoint_rows += 1
            continue
        role = 'driver' if endpoint['DIRECTION'] == 'OUT' else 'load'
        for index in tile_windows.get(tile, []):
            incidence[index, role].add(name)
    window_rows = []
    window_modules = []
    for index, window, xs, ys in windows:
        drivers = incidence[index, 'driver']
        loads = incidence[index, 'load']
        union = drivers | loads
        window_rows.append([index, window['stage'], window['direction'],
                            window['net_resource_type'], window['physical_window'],
                            len(drivers) if has_site_tiles else 'NOT_MEASURED',
                            len(loads) if has_site_tiles else 'NOT_MEASURED',
                            len(union) if has_site_tiles else 'NOT_MEASURED',
                            len(union) / denominator if has_site_tiles else 'NOT_MEASURED',
                            'MAPPED_ENDPOINT_INCIDENCE_NONADDITIVE_LOWER_BOUND' if has_site_tiles
                            else 'NOT_MEASURED_NO_NATIVE_SITE_TILE_LINK'])
        counts = collections.Counter(failed[n]['driver_module'] for n in union)
        for module, count in counts.most_common():
            window_modules.append([index, module, count])
    table(target / 'actual_endpoint_window_incidence.tsv',
          ['window', 'report_stage', 'direction', 'resource_type', 'native_tile_window',
           'driver_inside_unique_conflicts', 'load_inside_unique_conflicts',
           'any_endpoint_inside_unique_conflicts', 'fraction_current_canonical', 'scope'], window_rows)
    table(target / 'window_actual_driver_module_incidence.tsv',
          ['window', 'driver_module', 'unique_canonical_conflicts'], window_modules)
    summary = dict(current_canonical=denominator, current_report=615840,
                   current_canonical_minus_report=denominator - 615840,
                   old_canonical=old_denominator, old_report=547548,
                   old_canonical_minus_report=old_denominator - 547548,
                   primary_module_sum=sum(modules.values()), module_groups_disjoint=True,
                   unknown_window_mappings=unresolved_windows,
                   endpoint_rows_without_actual_site_tile=missing_endpoint_rows,
                   window_incidence_additive=False, actual_route_sample_count=len(sample_data),
                   scope_limits=['endpoint location does not imply actual route containment',
                                 'sampled actual route resources are not all conflict-net routes',
                                 'no complete 797175-overlap-node mapping',
                                 'RouterInitial/PlacerFinal window composition is not final net contribution'])
    (target / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    inputs = [OUT / n for n in ('unknowns_and_coverage.json', 'module_region_summary.tsv',
                               'failed_nets.tsv', 'route_sample_receipts.tsv', 'sampled_route_nodes.tsv',
                               'device_tiles.tsv', 'site_tiles.tsv', 'cells.tsv', 'endpoints.tsv')]
    (target / 'input_identities.json').write_text(json.dumps([identity(p) for p in inputs], indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
