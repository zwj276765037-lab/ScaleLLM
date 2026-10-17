#!/usr/bin/env python3
"""Observed candidate endpoints in closed E006 scopes; never a complete P cut."""
import argparse
import csv
import importlib.util
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
from capture_stage import ROOT, ATTEMPT, REPORT, identity, table, put, closed_queries
from capture_graph_stage import refined_class

CLASSIFIER = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/audit_input_frontend_candidate.py'


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['failure_samples', 'hotspot_connections'])
    stage = parser.parse_args().stage
    receipt = [row for row in table(REPORT / 'stage_receipts.tsv') if row['stage'] == stage]
    assert len(receipt) == 1 and receipt[0]['native_tcl_code'] == '0'
    prefix = 'failure' if stage == 'failure_samples' else 'hotspot_union_canonical'
    source = REPORT / (prefix + '_net_endpoints.tsv')
    spec = importlib.util.spec_from_file_location('candidate_literal_reference', CLASSIFIER)
    selector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector)
    endpoints = ATTEMPT / (stage + '_candidate_observed_endpoints.tsv')
    net_table = ATTEMPT / (stage + '_candidate_per_canonical_net_counts.tsv')
    facts_path = ATTEMPT / (stage + '_candidate_observed_scope_facts.json')
    assert not any(path.exists() for path in [endpoints, net_table, facts_path])
    seen = {}
    nets = defaultdict(Counter)
    candidate_refs = Counter()
    candidate_cells = set()
    candidate_S_cells = set()
    candidate_DSP_sites = set()
    totals = Counter()
    categories = Counter()
    with endpoints.open('x') as out:
        fields = ['canonical_net', 'role', 'pin', 'cell', 'owner', 'detail',
                  'REF_NAME', 'LOC', 'BEL', 'SLR', 'REF_PIN_NAME',
                  'literal_group', 'selected_RAW', 'selected_S',
                  'refined_primitive_terminal_category', 'IS_CLOCK_evidence']
        writer = csv.DictWriter(out, fieldnames=fields, delimiter='\t',
                                quoting=csv.QUOTE_NONE, lineterminator='\n')
        writer.writeheader()
        for row in table(source):
            totals['raw_source_endpoint_rows'] += 1
            key = (row['canonical_net'], row['role'], row['pin'])
            signature = tuple(row.items())
            if key in seen:
                assert seen[key] == signature, ('Repeated canonical alias endpoint differs', key)
                totals['repeated_alias_endpoint_rows_suppressed'] += 1
                continue
            seen[key] = signature
            totals['unique_canonical_endpoint_rows'] += 1
            group = selector.classify(row['cell'])
            raw = bool(group and selector.selected(group))
            semantic = raw and row['REF_NAME'] not in {'GND', 'VCC'}
            role = row['role']
            assert role in {'DRIVER', 'LOAD'}
            counter = nets[row['canonical_net']]
            counter['all_' + role] += 1
            counter[('candidate_RAW_' if raw else 'outside_RAW_') + role] += 1
            counter[('candidate_S_' if semantic else 'outside_S_') + role] += 1
            if row['SLR'] not in {'SLR0', 'SLR1', 'SLR2'}:
                counter['unknown_or_unplaced_SLR_' + role] += 1
            if row['cell'].startswith('UNRESOLVED_PARENT_FROM_PIN:'):
                counter['unresolved_parent_' + role] += 1
            if raw:
                totals['unique_candidate_RAW_endpoints'] += 1
                totals['unique_candidate_S_endpoints'] += semantic
                totals['selected_constant_endpoints'] += not semantic
                candidate_refs[row['REF_NAME']] += 1
                candidate_cells.add(row['cell'])
                if semantic:
                    candidate_S_cells.add(row['cell'])
                if row['REF_NAME'].startswith('DSP') and row['LOC']:
                    candidate_DSP_sites.add(row['LOC'])
                category = refined_class(row['REF_NAME'], row['REF_PIN_NAME'])
                categories[(role, category)] += 1
                writer.writerow(dict(**row, literal_group=group, selected_RAW=1,
                                     selected_S=int(semantic),
                                     refined_primitive_terminal_category=category,
                                     IS_CLOCK_evidence='NOT_QUERIED_BY_E006'))
    columns = ['all_DRIVER', 'all_LOAD', 'candidate_RAW_DRIVER', 'candidate_RAW_LOAD',
               'candidate_S_DRIVER', 'candidate_S_LOAD', 'outside_RAW_DRIVER', 'outside_RAW_LOAD',
               'outside_S_DRIVER', 'outside_S_LOAD', 'unknown_or_unplaced_SLR_DRIVER',
               'unknown_or_unplaced_SLR_LOAD', 'unresolved_parent_DRIVER', 'unresolved_parent_LOAD']
    relevant = {name: counts for name, counts in nets.items()
                if counts['candidate_RAW_DRIVER'] or counts['candidate_RAW_LOAD']}
    with net_table.open('x') as out:
        writer = csv.DictWriter(out, fieldnames=['canonical_net', *columns],
                                delimiter='\t', quoting=csv.QUOTE_NONE, lineterminator='\n')
        writer.writeheader()
        for name, counter in sorted(relevant.items()):
            writer.writerow(dict(canonical_net=name, **{key: counter[key] for key in columns}))
    totals['observed_unique_canonical_nets'] = len(nets)
    totals['canonical_nets_with_candidate_RAW_endpoints'] = len(relevant)
    totals['candidate_RAW_cells_observed_at_endpoints'] = len(candidate_cells)
    totals['candidate_S_cells_observed_at_endpoints'] = len(candidate_S_cells)
    totals['selected_DSP_LOC_sites_observed_not_P_normalization'] = len(candidate_DSP_sites)
    producer = ATTEMPT / ('capture_' + stage + '_candidate_endpoint_producer.py')
    shutil.copy2(Path(__file__), producer)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                 phase='closed_E006_observed_candidate_endpoints', stage=stage,
                 native_closed_stage_receipt=receipt[0],
                 native_closed_query_receipts=closed_queries(stage),
                 source=identity(source), classifier=identity(CLASSIFIER),
                 graph_classification_helper=identity(Path(__file__).with_name('capture_graph_stage.py')),
                 producer=identity(producer), totals=dict(totals),
                 candidate_RAW_endpoint_REF_counts=dict(candidate_refs),
                 candidate_RAW_endpoint_primitive_categories=[dict(role=key[0], category=key[1], count=value)
                                                            for key, value in categories.most_common()],
                 selected_DSP_LOC_sites_observed=sorted(candidate_DSP_sites),
                 endpoints=identity(endpoints), per_net_counts=identity(net_table),
                 alias_handling='Deduplicated exact (canonical net, role, pin); repeated aliases must have identical full endpoint rows; suppression counted separately',
                 scope='Only complete nets selected by closed E006 failure-sample or hotspot-UNION scope, leaf IN/OUT. Observed RAW/S endpoint names are not the whole candidate cut or actual E007 physical P.',
                 missing_fields='INOUT/top ports/native IS_CLOCK/origin/macro/new E007 P membership not queried here; unknown parent/SLR counters retained',
                 native_E007_P_qualification='NOT_RUN', formal_signoff=False)
    put(facts_path, facts)
    print(json.dumps(dict(facts=identity(facts_path), totals=dict(totals)), ensure_ascii=False))


if __name__ == '__main__':
    main()
