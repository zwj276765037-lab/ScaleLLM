#!/usr/bin/env python3
"""Closed cut/timing facts and candidate-involved pair model; no EDA control."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import sys
import tkinter
from capture_membership_resources import ATTEMPT, REPORT, identity, table, save, HOTSPOT

SEMANTIC_SOURCE = Path(__file__).resolve().parents[1]/'E006_exact_candidates/candidate_evidence.py'
sys.path.insert(0, str(SEMANTIC_SOURCE.parent))
from candidate_evidence import category

SLRS = {'SLR0', 'SLR1', 'SLR2'}


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    parser = argparse.ArgumentParser()
    parser.add_argument('point', choices=['C01', 'C02'])
    parser.add_argument('--timing', action='store_true')
    args = parser.parse_args(); point = args.point
    stage = f'candidate_{point}_' + ('bounded_timing' if args.timing else 'complete_cut')
    assert not any((ATTEMPT/name).exists() for name in [f'{stage}_closed_facts.json', f'{stage}_closed_summary.json', f'capture_{stage}_producer.py']), 'Never overwrite a captured stage or its producer'
    receipt = [r for r in table(REPORT / 'stage_receipts.tsv') if r['stage'] == stage]
    assert len(receipt) == 1, 'Actual native stage has not closed'
    facts = dict(point=point, stage=stage, observed_utc=datetime.now(timezone.utc).isoformat(),
                 native_stage_receipt=receipt[0], native_stage_zero=receipt[0]['native_tcl_code'] == '0',
                 candidate_supported='NOT_ASSESSED', formal_signoff=False)
    files = [REPORT / f'stage_{stage}_closed.txt']
    if not facts['native_stage_zero']:
        tcl = tkinter.Tcl()
        outer = tcl.splitlist(receipt[0]['failed_queries']); assert len(outer) == 1
        files += [REPORT / f'error_{q}.txt' for q in tcl.splitlist(outer[0])]
        facts['execution'] = 'closed_native_stage_failed; partial cut/timing not promoted'
    elif args.timing:
        files += [REPORT / f'candidate_scoped_timing_{point}.tsv', REPORT / f'candidate_scoped_timing_{point}_coverage.txt',
                  REPORT / f'candidate_timing_queries_{point}.tcllist', REPORT / f'candidate_boundary_timing_scope_{point}.tsv']
        timing = list(table(files[1])); scope = list(table(files[-1])); groups = defaultdict(list)
        for row in timing:
            groups[(row['direction'], row['delay_type'])].append(row)
        facts['timing_groups'] = [dict(direction=k[0], delay_type=k[1], rows=v) for k, v in sorted(groups.items())]
        facts['exact_query_endpoint_count_by_direction'] = dict(Counter(r['cut_direction'] for r in scope))
        facts['timing_limits'] = 'max/min cap16 per direction; current physopt graph only, no full-cut TNS or hypothetical timing'
        files += sorted(REPORT.glob(f'candidate_cut_timing_{point}_*.rpt'))
    else:
        files += [REPORT / f'candidate_{key}_{point}.tsv' for key in ['nets', 'segments', 'endpoints', 'pins']]
        summary_path = REPORT / f'candidate_cut_summary_{point}.json'
        summary = json.loads(summary_path.read_text()); assert summary['native_cut_consistency_verified'] is True
        nets = {r['canonical_net']: r for r in table(files[1])}
        endpoints = defaultdict(list)
        for row in table(files[3]): endpoints[row['canonical_net']].append(row)
        assert set(endpoints) == set(nets)
        aliases = {r['segment']: r['canonical_net'] for r in table(files[2])}
        bindings = json.loads((ATTEMPT/'input_bindings.json').read_text())
        sample_path = Path(bindings['reused_closed_inputs']['R003_AT001_failure_exact_net_resolution.tsv']['path'])
        sample_intersections = []
        for sample in table(sample_path):
            name = sample['exact_requested_net_name']; canonical = aliases.get(name)
            records = endpoints[canonical] if canonical else []
            semantic_inside = lambda r: r['inside_S'] == '1' or r['inside_P'] == '1'
            sample_intersections.append(dict(sample_id=sample['sample_id'], exact_requested_net_name=name,
                original_resolution=sample['status'], selected_cut_canonical_net=canonical,
                candidate_leaf_or_top_drivers=sum(r['role']=='DRIVER' and semantic_inside(r) for r in records),
                candidate_leaf_or_top_loads=sum(r['role']=='LOAD' and semantic_inside(r) for r in records),
                total_leaf_or_top_drivers=sum(r['role']=='DRIVER' for r in records),
                total_leaf_or_top_loads=sum(r['role']=='LOAD' for r in records),
                candidate_endpoint_directions=dict(Counter(r['DIRECTION'] for r in records if semantic_inside(r)))))
        hotspot = {r['cell'] for r in table(HOTSPOT)}
        totals = Counter(); semantic_pairs = defaultdict(Counter); pairs = []; unresolved = []; hotspot_net_count = 0
        for name, native in nets.items():
            rows = endpoints[name]; drivers = [r for r in rows if r['role'] == 'DRIVER']; loads = [r for r in rows if r['role'] == 'LOAD']
            selected = lambda r: r['inside_P'] == '1'
            hotspot_loads = sum(r['raw_cell'] in hotspot for r in loads)
            hotspot_net_count += hotspot_loads > 0
            if native['resolution'] != 'SINGLE_DRIVER' or len(drivers) != 1:
                unresolved.append(dict(canonical_net=name, resolution=native['resolution'], drivers=len(drivers),
                                       leaf_or_top_loads=len(loads), candidate_P_endpoint_count=sum(selected(r) for r in rows)))
                continue
            driver = drivers[0]
            semantic_category, semantics_unknown = category(native['actual_clocks'], {r['pin_class'] for r in rows})
            for load in loads:
                if not (selected(driver) or selected(load)):
                    totals['unrelated_outside_to_outside_load_pairs_excluded'] += 1
                    continue
                relation = 'INTERNAL' if selected(driver) and selected(load) else 'EGRESS' if selected(driver) else 'INGRESS'
                current_known = driver['SLR'] in SLRS and load['SLR'] in SLRS
                ds = 'SLR2' if selected(driver) else driver['SLR']
                ls = 'SLR2' if selected(load) else load['SLR']
                modeled_known = ds in SLRS and ls in SLRS
                cur = int(driver['SLR'] != load['SLR']) if current_known else None
                modeled = int(ds != ls) if modeled_known else None
                totals[relation + '_candidate_involved_load_pairs'] += 1
                totals['current_known_pairs'] += current_known
                totals['current_known_cross_SLR_load_pairs'] += cur or 0
                totals['modeled_known_pairs'] += modeled_known
                totals['modeled_known_cross_SLR_load_pairs'] += modeled or 0
                comparable = current_known and modeled_known
                totals['directly_comparable_pairs'] += comparable
                if comparable:
                    totals['comparable_current_cross_SLR_load_pairs'] += cur
                    totals['comparable_modeled_cross_SLR_load_pairs'] += modeled
                local = semantic_pairs[(relation, semantic_category)]
                local['candidate_involved_load_pairs'] += 1
                local['current_known_pairs'] += current_known;local['current_cross_SLR_load_pairs'] += cur or 0
                local['modeled_known_pairs'] += modeled_known;local['modeled_cross_SLR_load_pairs'] += modeled or 0
                local['directly_comparable_pairs'] += comparable
                local['unknown_semantics_pairs'] += semantics_unknown
                if comparable:
                    local['comparable_current_cross_SLR_load_pairs'] += cur
                    local['comparable_modeled_cross_SLR_load_pairs'] += modeled
                pairs.append(dict(canonical_net=name, relation=relation,
                                  driver=driver['NAME'], driver_kind=driver['kind'], driver_current_SLR=driver['SLR'],
                                  driver_modeled_SLR=ds, load=load['NAME'], load_kind=load['kind'],
                                  load_current_SLR=load['SLR'], load_modeled_SLR=ls, current_cross_SLR=cur,
                                  hypothetical_cross_SLR=modeled, directly_comparable=comparable,
                                  native_clock_and_REF_semantic_category=semantic_category,
                                  load_pin_class=load['pin_class'], load_in_hotspot=load['raw_cell'] in hotspot))
        facts.update(native_cut_summary=summary, candidate_involved_pair_totals=dict(totals),
                     candidate_involved_pair_totals_by_direction_and_semantics=[dict(relation=k[0], category=k[1], **dict(v)) for k,v in sorted(semantic_pairs.items())],
                     original_failed_sample_net_intersections=sample_intersections,
                     candidate_involved_current_and_hypothetical_load_pairs=pairs,
                     unresolved_single_driver_pair_models=unresolved,
                     attached_canonical_nets_with_any_hotspot_load=hotspot_net_count,
                     crossing_model='Only resolved single-driver net load pairs involving selected P. Hypothetical model puts all P in SLR2 and holds every outside endpoint fixed. Internal P pairs remain visible. Top/unknown current positions stay unknown; unresolved/INOUT/multidriver nets are separate. Counts are load pairs, never SLL, physical placement feasibility, timing, traffic or candidate support.')
        files += [summary_path, HOTSPOT, sample_path]
    producer = ATTEMPT / f'capture_{stage}_producer.py'; shutil.copy2(Path(__file__), producer)
    facts.update(artifacts=[identity(p) for p in files], producer=identity(producer), semantic_classifier=identity(SEMANTIC_SOURCE),
                 table_and_identity_helper=identity(Path(__file__).with_name('capture_membership_resources.py')))
    full = ATTEMPT / f'{stage}_closed_facts.json'; save(full, facts)
    short = {k: v for k, v in facts.items() if k not in {'candidate_involved_current_and_hypothetical_load_pairs', 'native_cut_summary', 'timing_groups'}}
    if 'native_cut_summary' in facts:
        short['native_cut_summary'] = {k: facts['native_cut_summary'][k] for k in ['canonical_nets', 'endpoints', 'boundary_counts', 'driver_resolution_counts', 'cut_directions', 'exclusive_cut_categories']}
    short['full_facts'] = identity(full)
    target = ATTEMPT / f'{stage}_closed_summary.json'; save(target, short)
    print(dict(facts=identity(full), summary=identity(target), native_stage_zero=facts['native_stage_zero']))


if __name__ == '__main__':
    main()
