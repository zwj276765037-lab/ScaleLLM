#!/usr/bin/env python3
"""Capture naturally closed owner queries without waiting for the whole stage.

CPU only. No Vivado API, process control, live native-source edit or checkpoint write.
"""
import argparse
import json
import shutil
from datetime import datetime, timezone

from capture_stage import ROOT, ATTEMPT, REPORT, identity, table, native_slr, put


OWNERS = ['attention', 'mlp', 'weight_metadata', 'weight_loader', 'core_other',
          'ddr0', 'ddr1', 'pcie', 'debug', 'interconnect_other']
METRICS = ['CLB', 'CLB LUTs', 'CLB Registers', 'Block RAM Tile', 'RAMB36/FIFO',
           'RAMB18', 'URAM', 'DSPs', 'Unique Control Sets']


def query_name(owner):
    return 'native_remaining_global' if owner == 'interconnect_other' else 'native_owner_' + owner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', help='Unique immutable milestone label, e.g. batch001')
    args = parser.parse_args()
    assert args.batch.isalnum(), 'Use only alphanumeric milestone labels'
    prefix = 'closed_owner_' + args.batch
    assert not (ATTEMPT / (prefix + '_facts.json')).exists()
    rows = list(table(REPORT / 'query_receipts.tsv'))
    unique = {}
    for row in rows:
        assert row['query'] not in unique, row
        unique[row['query']] = row
    assert unique['complete_exclusive_ownership']['native_tcl_code'] == '0'
    assert unique['native_global_SLR']['native_tcl_code'] == '0'
    completed = [o for o in OWNERS if query_name(o) in unique]
    assert completed, 'No naturally completed owner reports'
    receipts = [unique[k] for k in ['complete_exclusive_ownership', 'native_global_SLR']]
    receipts += [unique[query_name(o)] for o in completed]
    assert all(r['native_tcl_code'] == '0' for r in receipts), receipts

    started = json.loads((ATTEMPT / 'started.json').read_text())
    bound = identity(ATTEMPT / 'input_bindings.json')
    assert bound == started['inputs']
    bindings = json.loads((ATTEMPT / 'input_bindings.json').read_text())
    assert [identity(p['path']) for p in bindings['sources']] == bindings['sources']
    assert identity(bindings['contract']['path']) == bindings['contract']
    review_path = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/closed_primitive_ownership_review.json'
    review = json.loads(review_path.read_text())
    assert review['independent_prefix_owner_mismatches'] == 0
    assert review['independent_ref_counts_equal_native'] is True
    assert review['independent_site_owner_sets_equal_native'] is True
    primitive = {(r['owner'], r['SLR']): r for r in review['module_SLR_metrics']}

    files = [REPORT / 'utilization_global_SLR.rpt']
    resource = {'global': native_slr(files[0])}
    checks = {}
    mapping = {'CLB': 'SLICE_touched_sites_nonadditive_between_owners',
               'CLB Registers': 'FF_latch_primitives_at_SLICE_sites',
               'Block RAM Tile': 'BRAM_36K_equivalent',
               'URAM': 'URAM_primitives', 'DSPs': 'DSP_unique_occupied_sites'}
    for owner in completed:
        path = REPORT / ('utilization_exclusive_' + owner + '_SLR.rpt')
        assert unique[query_name(owner)]['result'] == str(path)
        files.append(path)
        resource[owner] = native_slr(path)
        checks[owner] = {}
        for metric, independent in mapping.items():
            checks[owner][metric] = {}
            for slr in ['SLR0', 'SLR1', 'SLR2']:
                native = resource[owner][metric][slr]
                actual = primitive.get((owner, slr), {}).get(independent, 0)
                checks[owner][metric][slr] = dict(native=native,
                    independent_primitive_or_site=actual, equal=native == actual)
    selected = {owner: {m: v for m, v in data.items() if m in METRICS}
                for owner, data in resource.items()}
    producer = ATTEMPT / (prefix + '_producer.py')
    shutil.copy2(__file__, producer)
    facts = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
        milestone=prefix, status='PARTIAL_CLOSED_QUERIES_NATIVE_RUN_CONTINUES',
        closed_query_receipts_snapshot=receipts, input_bindings=bound,
        archived_native_sources_unchanged=bindings['sources'],
        contract_unchanged=bindings['contract'],
        primitive_independent_review=identity(review_path),
        completed_owner_queries=completed,
        pending_owner_queries=[o for o in OWNERS if o not in completed],
        native_resource_tables=resource,
        independent_primitive_site_checks=checks,
        all_comparisons_equal=all(c['equal'] for owner in checks.values()
            for metric in owner.values() for c in metric.values()),
        artifacts=[identity(p) for p in files], producer=identity(producer),
        limits=[
            'Milestone is based only on naturally closed native queries; module stage and full native/supervisor terminal may remain pending.',
            'Native resource tables and primitive counts are separate metrics. Raw logic LUT primitive rows are not native CLB LUTs.',
            'Native CLB Registers use SLICE-site FF/latch subset; all-site counts contain DDR PHY non-CLB FFs.',
            'Per-owner occupied CLB sites, physical LUT slots, and control sets can overlap between owners and must not be summed as unique global allocation.',
            'BRAM uses 36K equivalents; DSP uses actual occupied DSP sites rather than split primitive rows.',
            'DCP/144 input/PID/FLOCK/resource final closure is separately verified at actual native terminal.',
            'No congestion API, causal optimization validation, legal routed timing, CDC or board signoff is implied.'])
    path = ATTEMPT / (prefix + '_facts.json')
    put(path, facts)
    short = dict(recorded_utc=facts['recorded_utc'], full_facts=identity(path),
        status=facts['status'], completed_owner_queries=completed,
        pending_owner_queries=facts['pending_owner_queries'],
        native_resource_metrics=selected,
        independent_primitive_site_checks_all_equal=facts['all_comparisons_equal'],
        limits=facts['limits'])
    summary = ATTEMPT / (prefix + '_summary.json')
    put(summary, short)
    print(json.dumps(dict(summary=identity(summary), facts=identity(path),
        closed_owners=completed, all_comparisons_equal=facts['all_comparisons_equal']), ensure_ascii=False))


if __name__ == '__main__':
    main()
