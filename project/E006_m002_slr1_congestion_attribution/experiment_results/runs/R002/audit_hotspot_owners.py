#!/usr/bin/env python3
"""Stream closed native hotspot primitive tables. Resource units stay explicit."""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def identity(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': h.hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    report = args.report.resolve()
    closed = report/'stage_hotspot_ownership_closed.txt'
    if not closed.is_file() or 'native_tcl_code=0\n' not in closed.read_text():
        raise SystemExit('Hotspot stage is not closed successfully; no partial results published.')
    results = {}
    accumulated = set()
    for scope in [f'NW{i:03d}' for i in range(1,11)]+['UNION']:
        path = report/f'hotspot_{scope}_cells.tsv'
        owners = defaultdict(Counter)
        details = defaultdict(Counter)
        owner_sites = defaultdict(set)
        dsp_sites = defaultdict(set)
        owners_by_site = defaultdict(set)
        names = set()
        slrs = Counter()
        with path.open() as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            for row in reader:
                name, owner, detail, ref, loc, slr = (row[x] for x in
                    ['cell','exclusive_owner','detail_hierarchy','REF_NAME','LOC','SLR'])
                if name in names:
                    raise ValueError(f'Duplicate primitive in {scope}: {name}')
                names.add(name)
                slrs[slr] += 1
                metrics = Counter({'unique_primitives':1})
                if re.fullmatch(r'LUT[1-6](?:_2)?', ref):
                    metrics['logic_LUT_primitives_not_native_LUT_total'] = 1
                if ref.startswith(('FD','LD')):
                    metrics['FF_latch_primitives'] = 1
                if ref.startswith(('RAMB36','FIFO36')):
                    metrics['RAMB36_FIFO36_primitives'] = 1
                    metrics['BRAM_36K_equivalent_from_primitives'] = 1
                if ref.startswith(('RAMB18','FIFO18')):
                    metrics['RAMB18_FIFO18_primitives'] = 1
                    metrics['BRAM_36K_equivalent_from_primitives'] = .5
                if ref.startswith('URAM'):
                    metrics['URAM_primitives'] = 1
                if ref.startswith('DSP'):
                    metrics['DSP_split_primitives_not_blocks'] = 1
                    if loc:
                        dsp_sites[owner].add(loc)
                if ref.startswith(('RAMD','RAMS','RAM32','RAM64','RAM128','RAM256','RAM512','SRL')):
                    metrics['distributed_memory_shift_primitives_not_LUT_equivalent'] = 1
                owners[owner].update(metrics)
                details[(owner,detail)].update(metrics)
                if loc:
                    owners_by_site[loc].add(owner)
                if loc.startswith('SLICE_'):
                    owner_sites[owner].add(loc)
        for owner, metrics in owners.items():
            metrics['touched_SLICE_sites_nonadditive_between_owners'] = len(owner_sites[owner])
            metrics['occupied_DSP_sites_not_split_primitive_count'] = len(dsp_sites[owner])
        if scope != 'UNION':
            accumulated.update(names)
        elif accumulated != names:
            raise ValueError(f'Native UNION differs from exact set union: {len(accumulated-names)}, {len(names-accumulated)}')
        results[scope] = {'source':identity(path),'unique_primitives':len(names),
                         'SLR_primitive_counts':dict(slrs),
                         'unique_occupied_SLICE_sites':sum(s.startswith('SLICE_') for s in owners_by_site),
                         'shared_SLICE_sites_multiple_owners':sum(s.startswith('SLICE_') and len(o)>1 for s,o in owners_by_site.items()),
                         'exclusive_primitive_owners':dict(owners),
                         'top_details_by_FF_plus_logic_LUT':sorted(
                             [{'owner':o,'hierarchy':d,'counts':dict(c)} for (o,d),c in details.items()],
                             key=lambda r:-(r['counts'].get('FF_latch_primitives',0)+r['counts'].get('logic_LUT_primitives_not_native_LUT_total',0)))[:20]}
    payload = {'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
               'closure':identity(closed), 'actual_exact_region_union_equal':True,
               'regions':results,
               'limits':['All ten actual NW regions overlap; use UNION for combined counts.',
                         'Primitive counts are not native LUT resource totals; DSP count uses unique occupied sites.',
                         'Module-touched SLICE sites overlap; shared sites retained and not summed as total.',
                         'BRAM_36K_equivalent_from_primitives counts a RAMB18 as 0.5, not a whole site.',
                         'These are original physopt placed resources, not failed-route occupancy or causal proof.',
                         'Fixed-window congestion remains UNAVAILABLE.']}
    target=OUT/'native_hotspot_stage_review.json'
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':identity(target),'UNION':results['UNION']},ensure_ascii=False))


if __name__=='__main__':
    main()
