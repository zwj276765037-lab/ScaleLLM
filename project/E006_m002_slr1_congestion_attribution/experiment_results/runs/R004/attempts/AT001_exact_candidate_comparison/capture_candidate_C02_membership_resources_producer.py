#!/usr/bin/env python3
"""Read only closed R004 member/resource stages; no EDA or process control."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts/AT001_exact_candidate_comparison'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R004_AT001_exact_candidate_comparison'
TARGETS = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'
HOTSPOT = ROOT / 'project/hardware/vivado/reports/m002_E006_R003_AT001_lean_physopt_attribution/hotspot_UNION_cells.tsv'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'agent/A006/E006_lean_capture'))
from capture_stage import native_slr


def identity(path):
    path = Path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def table(path):
    # Some readonly_resolve rows used an unquoted literal TAB as join's argument.
    # Tcl discards that argument whitespace, leaving join's default single space.
    # Preserve every empty field; accept only exact fixed cardinality, no guessing.
    # Header strings were quoted and remain genuine TAB-separated columns.
    with Path(path).open() as stream:
        header = stream.readline().rstrip('\n').split('\t')
        for number, raw in enumerate(stream, 2):
            raw = raw.rstrip('\n')
            values = raw.split('\t')
            if len(values) == 1 and len(header) > 1 and Path(path).name.startswith((
                    'candidate_membership_', 'candidate_physical_members_', 'candidate_site_members_')):
                values = raw.split(' ')
            assert len(values) == len(header), ('Unrecoverable native row cardinality', str(path), number, len(header), len(values))
            yield dict(zip(header, values))


def save(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def unique(path, key='NAME'):
    records = list(table(path))
    values = {row[key]: row for row in records}
    assert len(records) == len(values), ('Duplicate rows', path)
    return values


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    parser = argparse.ArgumentParser()
    parser.add_argument('point', choices=['C01', 'C02'])
    point = parser.parse_args().point
    stage = f'candidate_{point}_membership_resources'
    receipts = [row for row in table(REPORT / 'stage_receipts.tsv') if row['stage'] == stage]
    assert len(receipts) == 1, 'Actual native stage has not uniquely closed'
    query_names = {f'candidate_{point}_membership', f'candidate_{point}_exact_native_resources'}
    queries = [row for row in table(REPORT / 'query_receipts.tsv') if row['query'] in query_names]
    assert len(queries) == 2
    target = next(row for row in json.loads(TARGETS.read_text())['candidates'] if row['id'] == point)
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    assert identity(ATTEMPT / 'input_bindings.json') == json.loads((ATTEMPT / 'started.json').read_text())['inputs']
    assert [identity(row['path']) for row in bindings['sources']] == bindings['sources']
    facts = dict(observed_utc=datetime.now(timezone.utc).isoformat(), point=point, stage=stage,
                 target=target, native_closed_stage_receipt=receipts[0], native_closed_query_receipts=queries,
                 native_stage_zero=receipts[0]['native_tcl_code'] == '0',
                 input_bindings=identity(ATTEMPT / 'input_bindings.json'), archived_sources_unchanged=bindings['sources'],
                 target_authority=identity(TARGETS), actual_DCP_mutation=False,
                 full_cut='PENDING_OR_SEPARATELY_VERIFIED', candidate_supported='NOT_ASSESSED',
                 formal_signoff=False, final_input_PID_lane_resource_closure='PENDING_ACTUAL_TERMINAL')
    files = [REPORT / f'stage_{stage}_closed.txt']
    if not facts['native_stage_zero']:
        files += [REPORT / f'error_{row["query"]}.txt' for row in queries if row['native_tcl_code'] != '0']
        facts['artifacts'] = [identity(path) for path in files]
        facts['execution'] = 'closed_native_stage_failed; partial member files are not promoted to complete evidence'
    else:
        assert all(row['native_tcl_code'] == '0' for row in queries)
        paths = {key: REPORT / f'candidate_{key}_{point}.tsv' for key in ['RAW', 'S', 'P', 'membership', 'physical_members', 'site_members', 'property_support']}
        raw = unique(paths['RAW'])
        semantic = unique(paths['S'])
        physical = unique(paths['P'])
        members = unique(paths['membership'])
        parent_rows = unique(paths['physical_members'])
        assert set(members) == set(raw) and set(parent_rows) == set(physical)
        assert set(semantic) == {name for name, row in raw.items() if row['REF_NAME'] not in {'GND', 'VCC'}}
        assert all(name.startswith(target['primitive_literal_prefix']) for name in raw)
        normalized = {}
        for name, row in members.items():
            assert row['selected_RAW'] == '1' and row['selected_S'] == str(int(name in semantic))
            assert row['REF_NAME'] == raw[name]['REF_NAME'] and row['mapping_reason'] == 'ACTUAL_NATIVE_MAPPING'
            parent = row['physical_parent']
            if name in semantic:
                assert row['selected_P'] == '1' and parent in physical
                assert parent_rows[parent]['REF_NAME'] == row['physical_REF']
                if row['REF_NAME'].startswith('DSP') and row['REF_NAME'] != 'DSP48E2':
                    assert row['physical_REF'] == 'DSP48E2' and name.startswith(parent + '/')
                normalized[parent] = row['physical_REF']
        assert normalized == {name: row['REF_NAME'] for name, row in physical.items()}
        policies = ['IS_LOC_FIXED', 'IS_BEL_FIXED', 'USER_SLR_ASSIGNMENT', 'RLOC', 'RLOC_ORIGIN',
                    'MACRO_NAME', 'DONT_TOUCH', 'ORIG_CELL_NAME', 'ORIG_REF_NAME', 'actual_PBLOCKS']
        assert all(set(policies).issubset(row) for row in parent_rows.values())
        p_sites = {row['LOC'] for row in parent_rows.values() if row['LOC']}
        site_rows = list(table(paths['site_members']))
        assert len({row['NAME'] for row in site_rows}) == len(site_rows)
        observed = defaultdict(list)
        unknown_site_rows = []
        for row in site_rows:
            if row['LOC'] in p_sites:
                observed[row['LOC']].append(row)
            else:
                unknown_site_rows.append(row)
            assert row['selected_P'] == str(int(row['physical_parent'] in physical))
        assert p_sites <= set(observed), 'Some actual P touched sites have no primitive-member export'
        site_summary = defaultdict(Counter)
        for site in sorted(p_sites):
            rows = observed[site]
            slrs = {row['SLR'] for row in rows}
            assert len(slrs) == 1
            slr = next(iter(slrs))
            family = 'CLB' if site.startswith('SLICE_') else site.split('_X', 1)[0]
            label = ('unknown_mapping' if any(row['mapping_reason'] != 'ACTUAL_NATIVE_MAPPING' for row in rows) else
                     'shared_with_outside_P' if any(row['selected_P'] == '0' for row in rows) else 'currently_only_candidate_P')
            site_summary[(slr, family)]['touched_sites'] += 1
            site_summary[(slr, family)][label] += 1
        hotspot = {row['cell'] for row in table(HOTSPOT)}
        raw_hotspot = set(raw) & hotspot
        s_hotspot = set(semantic) & hotspot
        p_hotspot = {members[name]['physical_parent'] for name in s_hotspot}
        native_report = REPORT / f'utilization_candidate_{point}_SLR.rpt'
        native = native_slr(native_report)
        anomalies = []
        for name, row in parent_rows.items():
            reasons = []
            if row['IS_LOC_FIXED'] in {'1', 'true', 'TRUE'} and row['SLR'] != 'SLR2': reasons.append('FIXED_LOC_CURRENTLY_OUTSIDE_SLR2')
            if row['IS_BEL_FIXED'] in {'1', 'true', 'TRUE'}: reasons.append('EXISTING_FIXED_BEL_REQUIRES_QUALIFICATION')
            if row['USER_SLR_ASSIGNMENT'] and row['USER_SLR_ASSIGNMENT'] != 'SLR2': reasons.append('EXISTING_USER_SLR_ASSIGNMENT_NOT_SLR2')
            if any(row[key] for key in ['RLOC', 'RLOC_ORIGIN', 'MACRO_NAME']): reasons.append('RELATIVE_MACRO_POLICY_REQUIRES_NATIVE_PARTNER_PROOF')
            if row['actual_PBLOCKS']: reasons.append('EXISTING_PBLOCK_REQUIRES_RANGE_COMPATIBILITY')
            if reasons: anomalies.append(dict(NAME=name, REF_NAME=row['REF_NAME'], LOC=row['LOC'], SLR=row['SLR'], reasons=reasons, policy={key: row[key] for key in policies}))
        facts.update(execution='closed_member_resources_CPU_consistency_verified', RAW=len(raw), S=len(semantic), P=len(physical),
                     native_export_format_correction='membership/physical_members/site_members headers use TAB but source unquoted-literal-TAB join emits single SPACE; all rows independently required exact header cardinality with empty fields preserved. Raw files unchanged. No split-on-whitespace or field guessing.',
                     RAW_REF_counts=dict(Counter(row['REF_NAME'] for row in raw.values())),
                     P_REF_counts=dict(Counter(row['REF_NAME'] for row in parent_rows.values())),
                     RAW_actual_SLR_counts=dict(Counter(row['SLR'] for row in members.values())),
                     S_actual_SLR_counts=dict(Counter(members[name]['SLR'] for name in semantic)),
                     P_actual_SLR_counts=dict(Counter(row['SLR'] for row in parent_rows.values())),
                     native_exact_hierarchy_SLR_resources=native,
                     P_touched_shared_exclusive_sites=[dict(SLR=key[0], site_family=key[1], **dict(value)) for key, value in sorted(site_summary.items())],
                     P_unplaced_rows=[row for row in parent_rows.values() if not row['LOC']],
                     site_member_rows_outside_known_P_LOCs=unknown_site_rows,
                     hotspot_intersection=dict(RAW_primitive_NAMES=len(raw_hotspot), S_primitive_NAMES=len(s_hotspot),
                                               normalized_P_parents_of_hotspot_S_members=len(p_hotspot),
                                               P_direct_NAME_matches_in_primitive_export=len(set(physical) & hotspot)),
                     P_policy_anomalies=anomalies,
                     policy_limits='Actual P-parent values and native property-support samples retained. Empty optional values do not prove full inherited/ancestor/macro compatibility; live E008 pre-place qualification remains required.',
                     site_limits='Current selected-site primitive membership only; shared sites are not additive allocation, currently-only-candidate sites are not guaranteed released or packable in SLR2. No native LUT or SLL inferred from rows/sites.',
                     hotspot_export=identity(HOTSPOT), physical_normalization_and_literal_membership_consistent=True)
        files += list(paths.values()) + [native_report, REPORT / f'candidate_existing_pblocks_{point}.tcllist',
                                       REPORT / f'candidate_unresolved_mapping_{point}.tcllist', REPORT / f'candidate_membership_{point}_closed.txt']
        facts['artifacts'] = [identity(path) for path in files]
    producer = ATTEMPT / f'capture_{stage}_producer.py'
    shutil.copy2(Path(__file__), producer)
    facts['producer'] = identity(producer)
    facts['native_table_parser'] = identity(ROOT / 'agent/A006/E006_lean_capture/capture_stage.py')
    full = ATTEMPT / f'{stage}_closed_facts.json'
    save(full, facts)
    summary = {key: facts[key] for key in ['observed_utc', 'point', 'stage', 'native_closed_stage_receipt',
                                          'native_closed_query_receipts', 'native_stage_zero', 'candidate_supported', 'formal_signoff']}
    if facts['native_stage_zero']:
        for key in ['RAW', 'S', 'P', 'RAW_actual_SLR_counts', 'P_actual_SLR_counts', 'P_REF_counts',
                    'native_exact_hierarchy_SLR_resources', 'P_touched_shared_exclusive_sites', 'hotspot_intersection']:
            summary[key] = facts[key]
        summary['P_policy_anomaly_count'] = len(facts['P_policy_anomalies'])
        summary['P_unplaced_count'] = len(facts['P_unplaced_rows'])
    summary['full_facts'] = identity(full)
    short = ATTEMPT / f'{stage}_closed_summary.json'
    save(short, summary)
    print(json.dumps(dict(facts=identity(full), summary=identity(short), native_stage_zero=facts['native_stage_zero']), ensure_ascii=False))


if __name__ == '__main__':
    main()
