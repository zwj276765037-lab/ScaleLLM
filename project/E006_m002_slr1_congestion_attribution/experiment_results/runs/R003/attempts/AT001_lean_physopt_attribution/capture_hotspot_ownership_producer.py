#!/usr/bin/env python3
"""Closed R003 CPU evidence only; never controls EDA or edits native output."""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts/AT001_lean_physopt_attribution'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R003_AT001_lean_physopt_attribution'


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


def table(path):
    with Path(path).open() as stream:
        yield from csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)


def put(path, data):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def closed_queries(stage):
    names = {
        'failure_samples': {'failure_node_device_mapping', 'failure_samples'},
        'hotspot_ownership': {'actual_tile_site_mapping', 'hotspot_union',
                              'hotspot_primitive_union_coverage'} |
                             {'hotspot_NW%03d' % i for i in range(1, 11)},
        'hotspot_connections': {'hotspot_union_connections'},
    }
    rows = [row for row in table(REPORT / 'query_receipts.tsv')
            if (row['query'] in names[stage] if stage in names else
                row['query'].startswith('native_exact_hierarchy_'))]
    expected = len(names[stage]) if stage in names else 9
    assert len(rows) == expected and all(row['native_tcl_code'] == '0' for row in rows), stage
    return rows


def native_slr(path):
    active = False
    seen = False
    headers = []
    result = {}
    with Path(path).open() as stream:
        for line, text in enumerate(stream, 1):
            if active and seen and not text.startswith('|'):
                active = False
            if not text.startswith('|'):
                continue
            cells = [v.strip() for v in text.split('|')[1:-1]]
            if cells[:4] == ['Site Type', 'SLR0', 'SLR1', 'SLR2']:
                headers.append(line)
                active = True
                seen = False
                continue
            if active and len(cells) >= 4:
                try:
                    values = [float(v.replace(',', '')) for v in cells[1:4]]
                except ValueError:
                    continue
                result[cells[0]] = dict(native_line=line, SLR0=values[0], SLR1=values[1], SLR2=values[2])
                seen = True
    assert len(headers) == 1, ('No unique aggregate SLR table', path, len(headers))
    assert 'CLB LUTs' in result and 'Block RAM Tile' in result, path
    return result


def slot_sets():
    return {key: set() for key in ['CLB_sites', 'LUT_BEL_letter_slots',
                                   'register_BELs', 'DSP48E2_sites',
                                   'RAMB36_sites', 'RAMB18_sites', 'URAM_sites']}


def slots_add(slots, row, types):
    loc = row['LOC']
    bel = row['BEL']
    kind = types.get(loc, 'UNKNOWN')
    assert kind != 'UNKNOWN', ('Selected cell missing actual site mapping', row)
    if kind in ['SLICEL', 'SLICEM']:
        slots['CLB_sites'].add(loc)
        match = re.search(r'\.([A-H])[56]LUT$', bel)
        if match:
            slots['LUT_BEL_letter_slots'].add((loc, match.group(1)))
        if re.search(r'\.[A-H]FF2?$', bel):
            slots['register_BELs'].add((loc, bel))
    if kind == 'DSP48E2': slots['DSP48E2_sites'].add(loc)
    if kind == 'RAMB36': slots['RAMB36_sites'].add(loc)
    if kind in ['RAMB180', 'RAMB181', 'RAMB18', 'RAMBFIFO18']: slots['RAMB18_sites'].add(loc)
    if kind == 'URAM288': slots['URAM_sites'].add(loc)


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['hotspot_ownership', 'exact_hierarchy_resources'])
    stage = parser.parse_args().stage
    receipts = [row for row in table(REPORT / 'stage_receipts.tsv') if row['stage'] == stage]
    assert len(receipts) == 1 and receipts[0]['native_tcl_code'] == '0', 'No successful unique closed stage'
    receipt = receipts[0]
    binding = identity(ATTEMPT / 'input_bindings.json')
    assert binding == json.loads((ATTEMPT / 'started.json').read_text())['inputs']
    inputs = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    assert [identity(row['path']) for row in inputs['sources']] == inputs['sources']
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), stage=stage,
                 native_stage_zero=True, native_closed_stage_receipt=receipt,
                 native_closed_query_receipts=closed_queries(stage),
                 input_bindings=binding, actual_archived_sources_unchanged=inputs['sources'],
                 stage_closed_marker=identity(REPORT / ('stage_' + stage + '_closed.txt')),
                 final_native_supervisor_freeze_DCP_PID_lock='PENDING_OR_SEPARATELY_VERIFIED_AT_TRUE_TERMINAL',
                 fixed_window_congestion='UNAVAILABLE; occupation is not congestion', formal_signoff=False)
    files = []
    if stage == 'hotspot_ownership':
        mapping = list(table(REPORT / 'actual_hotspot_site_tile_SLR.tsv'))
        sites = {row['site']: row for row in mapping}
        assert len(sites) == len(mapping)
        types = {site: row['SITE_TYPE'] for site, row in sites.items()}
        groups = {}
        region_union = set()
        all_cells = set()
        for path in sorted(REPORT.glob('hotspot_*_cells.tsv')):
            scope = path.name[len('hotspot_'):-len('_cells.tsv')]
            selected = set()
            owners = defaultdict(slot_sets)
            slots = slot_sets()
            refs = defaultdict(Counter)
            slrs = Counter()
            details = Counter()
            for row in table(path):
                assert row['cell'] not in selected, (scope, row['cell'])
                selected.add(row['cell'])
                assert row['SLR'] == sites[row['LOC']]['actual_device_SLR'], row
                owner = row['exclusive_owner']
                refs[owner][row['REF_NAME']] += 1
                details[(owner, row['detail_hierarchy'])] += 1
                slrs[row['SLR']] += 1
                slots_add(slots, row, types)
                slots_add(owners[owner], row, types)
            if scope == 'UNION':
                all_cells = selected
            else:
                region_union.update(selected)
            groups[scope] = dict(unique_primitive_cells=len(selected), primitive_SLR_counts=dict(slrs),
                                 occupied_sites_or_BEL_slots={key: len(value) for key, value in slots.items()},
                                 owners={owner: dict(primitive_REF_counts=dict(refs[owner]),
                                                     primitive_count=sum(refs[owner].values()),
                                                     occupied_sites_or_BEL_slots={key: len(value) for key, value in values.items()})
                                         for owner, values in owners.items()},
                                 owner_slot_overlap_not_additive={key: sum(len(value[key]) for value in owners.values()) - len(slots[key]) for key in slots},
                                 detail_hierarchy_primitive_counts=[dict(owner=key[0], detail=key[1], primitive_count=value) for key, value in details.most_common()])
            files.append(path)
        assert set(groups) == {'UNION'} | {'NW%03d' % i for i in range(1, 11)}
        assert all_cells == region_union, 'Exact region union differs from exported UNION'
        declared = {row['scope']: int(row['unique_primitive_cells']) for row in table(REPORT / 'hotspot_scope.tsv')}
        assert declared == {scope: row['unique_primitive_cells'] for scope, row in groups.items()}
        limits = (REPORT / 'hotspot_native_resource_limits.txt').read_text()
        assert 'native_hotspot_resource_utilization=NOT_QUERIED' in limits
        facts.update(hotspot_scopes=groups, unique_actual_sites=len(sites), exact_region_cell_union_verified=True,
                     native_hotspot_resource_utilization='NOT_QUERIED',
                     metric_limits='Primitive/site/BEL-letter occupation only. LUT primitive rows or occupied BEL-letter slots are not a native LUT utilization report. DSP split primitive rows are not DSP blocks. Per-owner physical sites/BEL slots overlap and region totals must not be added.')
        files += [REPORT / name for name in ['actual_hotspot_site_tile_SLR.tsv', 'hotspot_scope.tsv', 'hotspot_native_resource_limits.txt']]
        summary_data = {scope: {key: value for key, value in row.items() if key != 'detail_hierarchy_primitive_counts'} for scope, row in groups.items()}
    else:
        scope_rows = list(table(REPORT / 'lean_exact_hierarchy_scope.tsv'))
        assert len(scope_rows) == 9
        resources = []
        for row in scope_rows:
            assert row['scope'] == 'inclusive_exact_hierarchy_not_exclusive_primitive_remainder'
            path = REPORT / row['report_name']
            resources.append(dict(**row, native_SLR_resources=native_slr(path), report=identity(path)))
            files.append(path)
        facts.update(exact_hierarchy_resources=resources,
                     scope_limits='Inclusive exact single hierarchy reports. Overlapping/ancestor totals and exclusive primitive remainder counts are not additive or interchangeable.')
        files.append(REPORT / 'lean_exact_hierarchy_scope.tsv')
        summary_data = resources
    producer = ATTEMPT / ('capture_' + stage + '_producer.py')
    shutil.copy2(Path(__file__), producer)
    facts['producer'] = identity(producer)
    facts['artifacts'] = [identity(path) for path in files]
    full = ATTEMPT / (stage + '_closed_stage_facts.json')
    put(full, facts)
    summary = dict(recorded_utc=facts['recorded_utc'], stage=stage, native_stage_zero=True,
                   native_closed_stage_receipt=receipt, full_facts=identity(full),
                   scope_data=summary_data, native_hotspot_resource_utilization='NOT_QUERIED',
                   fixed_window_congestion=facts['fixed_window_congestion'], formal_signoff=False)
    short = ATTEMPT / (stage + '_closed_stage_summary.json')
    put(short, summary)
    print(json.dumps(dict(summary=identity(short), facts=identity(full)), ensure_ascii=False))


if __name__ == '__main__':
    main()
