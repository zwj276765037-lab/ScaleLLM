#!/usr/bin/env python3
"""Read fixed E006 stage artifacts; no native execution or process control."""
import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution'


def identity(path):
    path = Path(path); before = path.stat(); digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def table(path):
    with path.open() as stream:
        yield from csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)


def native_slr(path):
    active = False; seen_data = False; headers = []; result = {}
    with path.open() as stream:
        for line, text in enumerate(stream, 1):
            if active and seen_data and not text.startswith('|'):
                active = False
            if not text.startswith('|'):
                continue
            cells = [v.strip() for v in text.split('|')[1:-1]]
            if cells[:4] == ['Site Type', 'SLR0', 'SLR1', 'SLR2']:
                headers.append(line); active = True; seen_data = False; continue
            if active and len(cells) >= 4:
                try:
                    values = [float(v.replace(',', '')) for v in cells[1:4]]
                except ValueError:
                    continue
                result[cells[0]] = dict(native_line=line, SLR0=values[0], SLR1=values[1], SLR2=values[2])
                seen_data = True
    assert len(headers) == 1, ('Native report has no unique SLR resource table; collection scope unresolved', path, headers)
    assert 'CLB LUTs' in result and 'Block RAM Tile' in result, path
    return result


def put(path, data):
    with path.open('x') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def slot_sets():
    return {key: set() for key in ['CLB_sites', 'LUT_slots', 'register_BELs', 'DSP48E2_sites', 'RAMB36_sites', 'RAMB18_sites', 'URAM_sites']}


def slots_add(slots, row, types):
    loc = row['LOC']; bel = row['BEL']; kind = types.get(loc, 'UNKNOWN')
    if kind in ['SLICEL', 'SLICEM']:
        slots['CLB_sites'].add(loc)
        match = re.search(r'\.([A-H])[56]LUT$', bel)
        if match:
            slots['LUT_slots'].add((loc, match.group(1)))
        if re.search(r'\.[A-H]FF2?$', bel):
            slots['register_BELs'].add((loc, bel))
    if kind == 'DSP48E2': slots['DSP48E2_sites'].add(loc)
    if kind == 'RAMB36': slots['RAMB36_sites'].add(loc)
    if kind in ['RAMB180', 'RAMB181', 'RAMB18', 'RAMBFIFO18']: slots['RAMB18_sites'].add(loc)
    if kind == 'URAM288': slots['URAM_sites'].add(loc)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['module_resources', 'hotspot_ownership']); stage = parser.parse_args().stage
    selected = [r for r in table(REPORT / 'stage_receipts.tsv') if r['stage'] == stage]
    assert len(selected) == 1, 'Stage has no unique closed receipt'
    receipt = selected[0]
    started = json.loads((ATTEMPT / 'started.json').read_text()); bound = identity(ATTEMPT / 'input_bindings.json'); assert bound == started['inputs']
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    sources = [identity(r['path']) for r in bindings['sources']]; assert sources == bindings['sources']
    phase_identity = dict(line.split('\t', 1) for line in (REPORT / 'identity.tsv').read_text().splitlines())
    assert phase_identity['checkpoint'] == bindings['checkpoint']['path'] and phase_identity['PART'] == 'xcvu9p-flga2104-2L-e' and phase_identity['blackboxes'] == '0'
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), stage=stage, native_closed_stage_receipt=receipt,
        native_stage_zero=receipt['native_tcl_code'] == '0', input_bindings=bound, actual_archived_sources_unchanged=sources,
        phase_identity=phase_identity, stage_closed_marker=identity(REPORT / ('stage_' + stage + '_closed.txt')),
        final_native_supervisor_freeze_DCP_PID_lock='PENDING_OR_SEPARATELY_VERIFIED_AT_TRUE_TERMINAL',
        resource_semantics='Primitive ownership is exclusive. Native hierarchy totals and shared physical sites/LUT slots are not assumed additive. DSP split primitive rows are not DSP block counts.',
        endpoint_scope='Selected complete nets; primitive leaf DIRECTION IN/OUT only. INOUT and top ports are not enumerated; NO_PRIMITIVE_DRIVER is not proof of no real driver.',
        pin_category_scope='Conservative primitive terminal categories; OTHER includes unclassified control spellings, can be refined from actual REF_NAME/REF_PIN_NAME without changing source graph.',
        fixed_window_congestion='UNAVAILABLE; resource occupation is not congestion', formal_signoff=False)
    if stage == 'module_resources':
        paths = sorted(REPORT.glob('utilization_exclusive_*_SLR.rpt')) + sorted(REPORT.glob('utilization_total_*_SLR.rpt')) + [REPORT / 'utilization_global_SLR.rpt']
        resources = {p.name: native_slr(p) for p in paths}
        primitive = defaultdict(Counter)
        for row in table(REPORT / 'exclusive_owner_SLR_REF_counts.tsv'):
            primitive[row['exclusive_owner']][row['SLR']] += int(row['primitive_count_not_native_resource_count'])
        coverage = dict(line.split('\t', 1) for line in (REPORT / 'ownership_coverage.tsv').read_text().splitlines())
        assert sum(sum(v.values()) for v in primitive.values()) == int(coverage['all_primitive_count']) == int(coverage['classified_unique_primitive_count'])
        facts.update(native_resource_tables=resources, exclusive_primitive_owner_SLR_counts=primitive, ownership_coverage=coverage,
            native_target_resolution=list(table(REPORT / 'native_target_resolution.tsv')))
        files = paths + [REPORT / n for n in ['all_primitive_locations.tsv', 'exclusive_owner_SLR_REF_counts.tsv', 'site_owner_sets.tsv', 'ownership_coverage.tsv', 'native_target_resolution.tsv']]
        summary = dict(stage=stage, native_stage_zero=facts['native_stage_zero'], ownership_coverage=coverage,
            exclusive_owner_SLR_native_metrics={name: {metric: value for metric, value in metrics.items() if metric in ['CLB LUTs', 'CLB Registers', 'CLB', 'Block RAM Tile', 'RAMB36/FIFO', 'RAMB18', 'URAM', 'DSPs']} for name, metrics in resources.items() if name.startswith('utilization_exclusive_')})
    else:
        types = {r['site']: r['SITE_TYPE'] for r in table(REPORT / 'site_owner_sets.tsv')}
        groups = {}; validations = {}; files = []
        for path in sorted(REPORT.glob('hotspot_*_cells.tsv')):
            region = path.name[len('hotspot_'):-len('_cells.tsv')]
            per_owner = defaultdict(slot_sets); all_slots = slot_sets(); ref_counts = defaultdict(Counter); count = 0; details = Counter()
            for row in table(path):
                count += 1; owner = row['exclusive_owner']; ref_counts[owner][row['REF_NAME']] += 1; details[(owner, row['detail_hierarchy'])] += 1
                slots_add(all_slots, row, types); slots_add(per_owner[owner], row, types)
            native_path = REPORT / ('utilization_hotspot_' + region + '_SLR.rpt'); native = native_slr(native_path)
            derived = {key: len(value) for key, value in all_slots.items()}; derived['BRAM_tile_equivalent_from_occupied_sites'] = derived['RAMB36_sites'] + derived['RAMB18_sites'] / 2
            expected = {metric: sum(row[s] for s in ['SLR0', 'SLR1', 'SLR2']) for metric, row in native.items()}
            validations[region] = {'LUT_slots_equal_native_CLB_LUTs': derived['LUT_slots'] == expected['CLB LUTs'], 'register_BELs_equal_native_CLB_Registers': derived['register_BELs'] == expected['CLB Registers'], 'DSP_sites_equal_native_DSPs': derived['DSP48E2_sites'] == expected['DSPs'], 'BRAM_sites_equal_native_tiles': derived['BRAM_tile_equivalent_from_occupied_sites'] == expected['Block RAM Tile'], 'URAM_sites_equal_native_URAM': derived['URAM_sites'] == expected['URAM']}
            groups[region] = dict(unique_primitive_cells=count, native_resource_table=native, derived_unique_physical_slots=derived,
                owners={owner: dict(primitive_REF_counts=ref_counts[owner], primitive_count=sum(ref_counts[owner].values()), occupied_sites_or_BEL_slots={k: len(v) for k, v in slots.items()}) for owner, slots in per_owner.items()},
                detail_hierarchy_primitive_counts=[dict(owner=k[0], detail=k[1], primitive_count=v) for k, v in details.most_common()],
                owner_slot_sharing={key: sum(len(value[key]) for value in per_owner.values()) - len(all_slots[key]) for key in all_slots})
            files += [path, native_path]
        assert set(groups) == {'UNION'} | {'NW%03d' % i for i in range(1, 11)}, 'Incomplete hotspot scopes'
        facts.update(hotspot_scopes=groups, derived_physical_slot_validation_against_native=validations,
            derived_metric_limits='Per-owner counts are occupied physical sites/BEL slots touched by that owner, not additive exclusive allocation. Only mappings that match the native all-owner region metric are validated; false comparisons remain unqualified.')
        files.append(REPORT / 'hotspot_scope.tsv')
        summary = dict(stage=stage, native_stage_zero=facts['native_stage_zero'], UNION=groups['UNION'], derived_physical_slot_validation_against_native=validations)
        # Keep the first delivery short; full hierarchy ranking remains in full facts.
        summary['UNION'] = {k: v for k, v in groups['UNION'].items() if k != 'detail_hierarchy_primitive_counts'}
    producer = ATTEMPT / ('capture_' + stage + '_producer.py'); shutil.copy2(Path(__file__), producer)
    facts['producer'] = identity(producer); facts['artifacts'] = [identity(p) for p in files]
    full = ATTEMPT / (stage + '_closed_stage_facts.json'); put(full, facts)
    summary.update(recorded_utc=facts['recorded_utc'], full_facts=identity(full), stage_receipt=receipt, endpoint_scope=facts['endpoint_scope'], fixed_window_congestion=facts['fixed_window_congestion'], formal_signoff=False)
    short = ATTEMPT / (stage + '_closed_stage_summary.json'); put(short, summary)
    print(json.dumps(dict(summary=identity(short), facts=identity(full)), ensure_ascii=False))


if __name__ == '__main__':
    main()
