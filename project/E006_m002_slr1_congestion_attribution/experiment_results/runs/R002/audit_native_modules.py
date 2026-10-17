#!/usr/bin/env python3
"""CPU extraction of CLOSED E006 module-resource stage; no EDA invocation."""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
METRICS = ['CLB', 'CLB LUTs', 'LUT as Logic', 'LUT as Memory',
           'CLB Registers', 'Block RAM Tile', 'RAMB36/FIFO', 'RAMB18',
           'URAM', 'DSPs', 'Unique Control Sets']


def identity(path):
    content = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest()}


def parse(path):
    result = {'source': identity(path), 'rows': {}}
    lines = path.read_text().splitlines()
    header = ['Site Type', 'SLR0', 'SLR1', 'SLR2', 'SLR0 %', 'SLR1 %', 'SLR2 %']
    header_lines = [n for n,line in enumerate(lines,1)
                    if [s.strip() for s in line.split('|')[1:-1]] == header]
    if len(header_lines) != 1:
        raise ValueError(f'Expected exactly one native SLR resource table, got {len(header_lines)} in {path}; report scope unresolved')
    result['single_SLR_header_line'] = header_lines[0]
    started_rows = False
    for n, line in enumerate(lines, 1):
        if 'Command' in line and 'report_utilization' in line:
            result['native_command'] = line
        if n <= header_lines[0]:
            continue
        if line.startswith('+') and started_rows:
            break
        cols = [s.strip() for s in line.split('|')[1:-1]]
        if len(cols) == 7:
            started_rows = True
        if len(cols) == 7 and cols[0] in METRICS:
            if cols[0] in result['rows']:
                raise ValueError(f'Duplicate metric {cols[0]} in {path}')
            result['rows'][cols[0]] = {'used': [float(x) for x in cols[1:4]],
                                     'util_percent': [x if x.startswith(('<','>')) else float(x) for x in cols[4:7]],
                                     'line': n, 'raw_line': line}
    for key in ['CLB LUTs', 'CLB Registers', 'Block RAM Tile', 'URAM', 'DSPs']:
        if key not in result['rows']:
            raise ValueError(f'Missing required SLR metric {key} in {path}')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--owners-first', action='store_true',
                        help='Accept each completed native owner query before later detail queries close.')
    args = parser.parse_args()
    report = args.report.resolve()
    closed = report / 'stage_module_resources_closed.txt'
    receipts_text = (report/'query_receipts.tsv').read_text()
    receipt_rows = {r['query']:r for r in csv.DictReader(receipts_text.splitlines(),delimiter='\t')}
    completed = {k for k,v in receipt_rows.items() if v['native_tcl_code']=='0'}
    native_owner_queries = {f'native_owner_{o}' for o in
        ['attention','mlp','weight_metadata','weight_loader','core_other','ddr0','ddr1','pcie','debug']}
    required = native_owner_queries | {'native_global_SLR','native_remaining_global','complete_exclusive_ownership'}
    if args.owners_first:
        if not required <= completed:
            raise SystemExit(f'Owner queries not all completed: {sorted(required-completed)}')
        closed = OUT/'native_module_owners_first_query_receipts_snapshot.tsv'
        if closed.exists():
            raise SystemExit('First owner snapshot already exists; preserve it.')
        closed.write_text(receipts_text)
    elif not closed.is_file() or 'native_tcl_code=0\n' not in closed.read_text():
        raise SystemExit('Module stage is not closed successfully; no partial result published.')
    paths = sorted(report.glob('utilization_exclusive_*_SLR.rpt'))
    if len(paths) != 10:
        raise ValueError(f'Expected 10 mutually exclusive owners, found {len(paths)}')
    owners = {p.name.removeprefix('utilization_exclusive_').removesuffix('_SLR.rpt'): parse(p)
              for p in paths}
    global_result = parse(report / 'utilization_global_SLR.rpt')
    details = {}
    for p in sorted(report.glob('utilization_total_*_SLR.rpt')):
        key = p.name.removeprefix('utilization_total_').removesuffix('_SLR.rpt')
        if f'native_detail_{key}' in completed:
            details[key] = parse(p)
    old_path = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/old_physopt_owner_baseline.json'
    old = json.loads(old_path.read_text())
    differences = {}
    for prior in old['owners']:
        key = prior['owner'].lower()
        if key not in ('attention', 'mlp'):
            continue  # DDR grouping could differ; do not compare nonidentical roots.
        differences[key] = {}
        for metric, row in prior['rows'].items():
            current = owners[key]['rows'].get(metric)
            if current:
                differences[key][metric] = {
                    'E003': [float(x) for x in row['used']],
                    'E005': current['used'],
                    'delta': [b-float(a) for a, b in zip(row['used'], current['used'])]}
    sums = {}
    for metric in ['CLB LUTs', 'CLB Registers', 'Block RAM Tile', 'URAM', 'DSPs']:
        total = [sum(o['rows'][metric]['used'][s] for o in owners.values()) for s in range(3)]
        whole = global_result['rows'][metric]['used']
        sums[metric] = {'sum_owner_native_counts': total, 'global_native_counts': whole,
                        'difference': [a-b for a, b in zip(total, whole)]}
    result = {'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'scope': 'closed current E005 physopt native E006 module attribution; CPU parsing',
              'closure': identity(closed), 'column_order': ['SLR0', 'SLR1', 'SLR2'],
              'global': global_result, 'exclusive_owners': owners, 'inclusive_details': details,
              'sum_comparison_not_forced': sums, 'old_owner_baseline': identity(old_path),
              'same_scope_attention_mlp_changes': differences,
              'limits': ['Exclusive primitive ownership is separate from native physical resource sharing.',
                         'Native LUTs can combine across hierarchies; occupied sites and control sets are nonadditive.',
                         'Block RAM Tile is 36K equivalent; RAMB18 count is half tiles, not full tiles.',
                         'Same-stage distributions are aggregates, not same-cell motion evidence.',
                         'No causal separation of RTL changes and SSI placement directive.']}
    target = OUT / ('native_module_owners_first_review.json' if args.owners_first else 'native_module_stage_review.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': identity(target), 'SLR1_owner_ranking': sorted(
        [(k, v['rows']['CLB LUTs']['used'][1], v['rows']['CLB Registers']['used'][1],
          v['rows']['Block RAM Tile']['used'][1], v['rows']['URAM']['used'][1],
          v['rows']['DSPs']['used'][1]) for k, v in owners.items()], key=lambda x: -x[1]),
          'attention_mlp_deltas': differences, 'sums': sums}, ensure_ascii=False))


if __name__ == '__main__':
    main()
