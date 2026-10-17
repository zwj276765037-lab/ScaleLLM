#!/usr/bin/env python3
"""Reduce immutable native E004 diagnostics to small, scoped analysis tables."""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
AT = HERE / 'attempts/AT001_readonly_physopt_diagnostics'


def rows(name):
    with (AT / name).open() as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def fid(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def native_util(path):
    result = {}
    for line in path.read_text().splitlines():
        parts = [s.strip() for s in line.split('|')[1:-1]]
        if len(parts) < 2 or parts[0] in result:
            continue
        if re.fullmatch(r'\d+(?:\.\d+)?', parts[1]):
            result[parts[0]] = float(parts[1]) if '.' in parts[1] else int(parts[1])
    return result


def native_slr(path):
    text = path.read_text()
    marker = '1.3 SLR CLB Logic and Dedicated Block Utilization\n'
    section = text.rsplit(marker, 1)[1].split('1.4 SLR IO Utilization', 1)[0]
    result = {}
    for line in section.splitlines():
        parts = [s.strip() for s in line.split('|')[1:-1]]
        if len(parts) != 7 or parts[0] in result:
            continue
        if all(re.fullmatch(r'\d+(?:\.\d+)?', s) for s in parts[1:4]):
            result[parts[0]] = {f'SLR{i}': float(s) if '.' in s else int(s)
                                for i, s in enumerate(parts[1:4])}
    return result


def main():
    result = dict(derived_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  source_attempt=str(AT.resolve()),
                  limits=[
                      'Successful physopt checkpoint placement only; not the failed-route state.',
                      'Hierarchy site sets overlap and must not be added across scopes.',
                      'Mapped physical BEL histogram is compared with native adjusted utilization before interpretation.',
                      'Primitive counts, LUT slots, occupied sites, BEL loads and FF utilization are separate quantities.',
                  ])
    result['query_receipts'] = rows('query_receipts.tsv')
    result['utilization_by_scope'] = {
        p.stem.removeprefix('utilization_'): native_util(p)
        for p in sorted(AT.glob('utilization_*.rpt'))
        if not p.name.startswith(('utilization_SLR_', 'utilization_hierarchy_'))}
    result['native_utilization_by_scope_SLR'] = {
        p.stem.removeprefix('utilization_SLR_'): native_slr(p)
        for p in sorted(AT.glob('utilization_SLR_*.rpt'))}
    prim = rows('module_primitive_counts.tsv')
    grouped = defaultdict(lambda: defaultdict(Counter))
    for row in prim:
        grouped[row['scope']][row['slr']][row['REF_NAME']] += int(row['primitive_count'])
    result['primitives_by_scope_SLR'] = grouped
    sites = rows('module_used_sites.tsv')
    grouped_sites = defaultdict(lambda: defaultdict(Counter))
    for row in sites:
        grouped_sites[row['scope']][row['slr']][row['site_type']] += int(row['distinct_occupied_sites'])
    result['sites_by_scope_SLR'] = grouped_sites
    packing_file = ('global_CLB_BEL_packing_hist_recovered.tsv'
                    if (AT / 'global_CLB_BEL_packing_hist_recovered.tsv').exists()
                    else 'global_CLB_BEL_packing_hist.tsv')
    packing = rows(packing_file)
    global_pack = Counter()
    slr_pack = defaultdict(Counter)
    for row in packing:
        n = int(row['occupied_CLB_sites'])
        l = int(row['physical_LUT_slots_with_mapped_cells'])
        f = int(row['FF_BELs_with_mapped_cells'])
        for out in (global_pack, slr_pack[row['slr']]):
            out['occupied_sites'] += n
            out['mapped_LUT_slots'] += n * l
            out['mapped_FF_BELs'] += n * f
            out['sites_no_mapped_LUT'] += n if l == 0 else 0
            out['sites_no_mapped_FF'] += n if f == 0 else 0
            out['sites_LUT_le2'] += n if l <= 2 else 0
            out['sites_LUT_le4'] += n if l <= 4 else 0
            out['sites_FF_le4'] += n if f <= 4 else 0
            out['sites_FF_le8'] += n if f <= 8 else 0
    result['raw_BEL_histogram_aggregation_requires_validity'] = global_pack
    result['raw_BEL_histogram_by_SLR_requires_validity'] = slr_pack
    result['packing_crosscheck'] = dict(
        native_baseline_CLB_sites=146472,
        native_baseline_LUT_slots=814935,
        native_baseline_CLB_registers=1019698,
        mapped_minus_native_sites=global_pack['occupied_sites'] - 146472,
        mapped_minus_native_LUT=global_pack['mapped_LUT_slots'] - 814935,
        mapped_minus_native_FF=global_pack['mapped_FF_BELs'] - 1019698)
    result['packing_validity'] = dict(
        source_file=packing_file,
        site_count_valid=global_pack['occupied_sites'] == 146472,
        LUT_FF_slot_histogram_valid=(global_pack['mapped_LUT_slots'] == 814935
                                     and global_pack['mapped_FF_BELs'] == 1019698),
        interpretation=('Use slot histogram only if independently reconciled with native utilization. '
                        'The original frozen query returned all-zero slot counts because the BEL '
                        'matching assumed unqualified literal names; nonempty unexpected BEL format '
                        'must not be interpreted as empty LUT/FF slots. No new checkpoint is opened.'))
    nets = rows('target_net_fanout.tsv')
    for row in nets:
        row['load_SLR_cell_counts_parsed'] = {
            k: int(v) for k, v in re.findall(r'(SLR\d+|UNKNOWN)\s+(\d+)', row['load_SLR_cell_counts'])}
    result['target_nets'] = nets
    result['hierarchy_properties'] = rows('hierarchy_properties.tsv')
    result['source_files'] = [fid(p) for p in sorted(AT.iterdir())
                              if p.is_file() and p.suffix in {'.rpt', '.tsv', '.txt'}
                              and p.name != 'launcher.log']
    out = HERE / 'physical_diagnostic_summary.json'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(output=str(out), packing_validity=result['packing_validity'],
                          crosscheck=result['packing_crosscheck'],
                          scopes=list(result['utilization_by_scope']),
                          target_net_count=len(nets)), indent=2))


if __name__ == '__main__':
    main()
