#!/usr/bin/env python3
"""Audit one naturally closed native hotspot query, without waiting for the stage."""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import json
from pathlib import Path
import re

from audit_hotspot_owners import OUT, identity
from audit_native_modules import parse
from audit_input_frontend_candidate import classify, selected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', required=True, type=Path)
    ap.add_argument('--scope', required=True, choices=[f'NW{i:03d}' for i in range(1,11)]+['UNION'])
    ap.add_argument('--native-not-queried-source', type=Path,
                    help='Actual archived lean Tcl source bound by its attempt input_bindings.json; explicitly primitive-only scope')
    args = ap.parse_args()
    report = args.report.resolve()
    scope = args.scope
    query = 'hotspot_union' if scope == 'UNION' else 'hotspot_' + scope
    receipts = list(csv.DictReader((report/'query_receipts.tsv').open(), delimiter='\t'))
    rows = [r for r in receipts if r['query'] == query]
    if len(rows) != 1 or rows[0]['native_tcl_code'] != '0':
        raise SystemExit(f'{query} has not closed exactly once with native code0; no partial publication.')
    cell_path = report/f'hotspot_{scope}_cells.tsv'
    native_path = report/f'utilization_hotspot_{scope}_SLR.rpt'
    omitted_source = None
    if args.native_not_queried_source:
        source = args.native_not_queried_source.resolve()
        binding = source.parent.parent/'input_bindings.json'
        bound = json.loads(binding.read_text())
        matches = [r for r in bound['sources'] if Path(r['path']).resolve() == source]
        ident = identity(source)
        if len(matches) != 1 or matches[0]['bytes'] != ident['bytes'] or matches[0]['sha256'] != ident['sha256']:
            raise SystemExit('Lean omission source is not exactly bound to the actual attempt.')
        if 'native_hotspot_resource_utilization=NOT_QUERIED' not in source.read_text():
            raise SystemExit('Actual archived source does not explicitly declare native hotspot utilization omission.')
        if native_path.exists():
            raise SystemExit('A native hotspot report exists despite requested primitive-only mode; resolve scope first.')
        omitted_source = dict(source=ident,input_binding=identity(binding))
    if not native_path.is_file() and omitted_source is None:
        raise SystemExit('Closed query is missing its native report; do not publish.')
    owners, details = defaultdict(Counter), defaultdict(Counter)
    owner_sites, dsp_sites = defaultdict(set), defaultdict(set)
    site_owners = defaultdict(set)
    names, slrs = set(), Counter()
    candidate = Counter()
    candidate_sites, candidate_dsp = set(), set()
    with cell_path.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            name,owner,detail,ref,loc,slr = (row[x] for x in ['cell','exclusive_owner','detail_hierarchy','REF_NAME','LOC','SLR'])
            if name in names:
                raise ValueError(f'Duplicate primitive: {name}')
            names.add(name)
            slrs[slr] += 1
            m = Counter(unique_primitives=1)
            if re.fullmatch(r'LUT[1-6](?:_2)?', ref):
                m['logic_LUT_primitives_not_native_LUT_total'] = 1
            if ref.startswith(('FD','LD')):
                m['FF_latch_primitives_all_sites'] = 1
                if loc.startswith('SLICE_'):
                    m['CLB_FF_latch_primitives'] = 1
            if ref.startswith(('RAMB36','FIFO36')):
                m['BRAM_36K_equivalent'] = 1
            if ref.startswith(('RAMB18','FIFO18')):
                m['BRAM_36K_equivalent'] = .5
            if ref.startswith('URAM'):
                m['URAM_primitives'] = 1
            if ref.startswith('DSP') and loc:
                dsp_sites[owner].add(loc)
            if loc:
                site_owners[loc].add(owner)
            if loc.startswith('SLICE_'):
                owner_sites[owner].add(loc)
            owners[owner].update(m)
            details[(owner,detail)].update(m)
            group = classify(name)
            if group and selected(group):
                candidate.update(m)
                if loc.startswith('SLICE_'):
                    candidate_sites.add(loc)
                if ref.startswith('DSP') and loc:
                    candidate_dsp.add(loc)
    for owner,m in owners.items():
        m['touched_SLICE_sites_nonadditive'] = len(owner_sites[owner])
        m['unique_DSP_sites'] = len(dsp_sites[owner])
    candidate['touched_SLICE_sites_nonadditive'] = len(candidate_sites)
    candidate['unique_DSP_sites'] = len(candidate_dsp)
    header_lines = []
    for n,line in enumerate(native_path.read_text().splitlines() if native_path.exists() else [],1):
        cols = [x.strip() for x in line.split('|')[1:-1]]
        if cols == ['Site Type','SLR0','SLR1','SLR2','SLR0 %','SLR1 %','SLR2 %']:
            header_lines.append(n)
    native = {'source':identity(native_path) if native_path.exists() else None,'SLR_table_header_lines':header_lines,
              'scope_verdict':'unresolved until one aggregate table and matching primitive-derived resources are verified'}
    if omitted_source:
        native.update(scope_verdict='NOT_QUERIED: actual archived lean source explicitly omits native hotspot utilization; all reported resource values below are primitive/site-derived',omission_provenance=omitted_source)
    if len(header_lines) == 1:
        try:
            native['parsed_single_SLR_table'] = parse(native_path)
            # Never infer native LUT totals from primitive counts. FF/BRAM/DSP
            # comparisons below are meaningful only if this is the aggregate.
            exp = Counter()
            for m in owners.values():
                exp.update({k:m.get(k,0) for k in ['CLB_FF_latch_primitives','BRAM_36K_equivalent','URAM_primitives','unique_DSP_sites']})
            checks = {}
            for native_key,cpu_key in [('CLB Registers','CLB_FF_latch_primitives'),('Block RAM Tile','BRAM_36K_equivalent'),('URAM','URAM_primitives'),('DSPs','unique_DSP_sites')]:
                got = sum(native['parsed_single_SLR_table']['rows'][native_key]['used'])
                checks[native_key] = dict(native_total=got,CPU_total=exp[cpu_key],equal=got==exp[cpu_key])
            native['aggregate_resource_checks'] = checks
            native['scope_verdict'] = ('single SLR table agrees with all primitive-derived FF/BRAM/URAM/DSP totals' if all(x['equal'] for x in checks.values()) else 'single SLR table has a resource discrepancy; aggregate scope unresolved')
        except (ValueError,KeyError) as exc:
            native['parser_issue'] = str(exc)
    result = dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
      execution='one closed region CPU audit completed; complete stage may still run',
      verdict='resource attribution only, not congestion/causal proof',
      applicability='E005 original physopt actual device tile membership from native query',
      review='prepared for controller; no user acceptance implied',scope=scope,
      closed_query=rows[0],cells_source=identity(cell_path),native_report=native,
      CPU_audit_sources=[identity(Path(__file__).resolve()), identity(OUT/'audit_native_modules.py'),identity(OUT/'audit_hotspot_owners.py'),identity(OUT/'audit_input_frontend_candidate.py')],
      unique_primitives=len(names),SLR_primitive_counts=dict(slrs),
      unique_occupied_SLICE_sites=sum(s.startswith('SLICE_') for s in site_owners),
      shared_SLICE_sites_multiple_owners=sum(s.startswith('SLICE_') and len(o)>1 for s,o in site_owners.items()),
      exclusive_primitive_owners=dict(owners),
      selected_input_preprocessing_candidate_in_this_region=dict(candidate),
      top_details_by_FF_plus_raw_LUT=sorted([dict(owner=o,hierarchy=d,counts=dict(c)) for (o,d),c in details.items()],key=lambda r:-(r['counts'].get('CLB_FF_latch_primitives',0)+r['counts'].get('logic_LUT_primitives_not_native_LUT_total',0)))[:20],
      limits=['Regions overlap; do not sum regional counts. Full UNION set equality is deferred to the complete-stage audit.',
        'Native code0 closes the files but does not prove the report -cells scope. Multiple SLR tables are not treated as one total.',
        'Primitive LUTs differ from native LUT resources; DSP uses unique physical LOC; touched sites overlap.',
        'Fixed-window congestion is UNAVAILABLE; physical occupancy is not a congestion metric.',
        'Candidate membership here is a literal NAME subset, not a proof that moving it fixes this hotspot.'])
    target = OUT/f'native_hotspot_{scope}_partial_review.json'
    if target.exists():
        raise SystemExit('Prior partial review exists; preserve it and use an explicitly versioned follow-up.')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=identity(target),scope=scope,unique_primitives=len(names),native_scope=native['scope_verdict'],owners=dict(owners),candidate=dict(candidate)),ensure_ascii=False))


if __name__ == '__main__':
    main()
