#!/usr/bin/env python3
"""Independent CPU reclassification of the completed primitive export."""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args(); report=args.report.resolve()
    receipts=(report/'query_receipts.tsv').read_text()
    rows=list(csv.DictReader(receipts.splitlines(),delimiter='\t'))
    close=[r for r in rows if r['query']=='complete_exclusive_ownership' and r['native_tcl_code']=='0']
    if len(close)!=1: raise SystemExit('Primitive ownership query not closed successfully exactly once.')
    rules=json.loads((OUT/'hierarchy_attribution_targets.json').read_text())['owner_rules']
    rules=sorted([(root,r['owner']) for r in rules for root in r['exact_hierarchy_roots']],key=lambda x:-len(x[0]))
    names=set(); sites=defaultdict(set); counts=Counter(); metrics=defaultdict(Counter)
    dsp_sites=defaultdict(set); slice_sites=defaultdict(set); source=report/'all_primitive_locations.tsv'
    digest=hashlib.sha256(); n=0; mismatches=[]; site_slr={}; unplaced=Counter()
    with source.open('rb') as stream:
        header=stream.readline();digest.update(header)
        expected=b'cell\tREF_NAME\tLOC\tBEL\tSLR\texclusive_owner\tdetail_hierarchy\n'
        if header!=expected:raise ValueError('Unexpected primitive export header')
        for line in stream:
            digest.update(line)
            cell,ref,loc,bel,slr,owner,detail=line.decode().rstrip('\n').split('\t')
            if cell in names: raise ValueError('Duplicate primitive: '+cell)
            names.add(cell);n+=1
            expected_owner=next((o for prefix,o in rules if cell==prefix or cell.startswith(prefix+'/')),'interconnect_other')
            if owner!=expected_owner: mismatches.append([cell,owner,expected_owner])
            key=(owner,slr); c=metrics[key]; c['unique_primitives']+=1; counts[owner,slr,ref]+=1
            if re.fullmatch(r'LUT[1-6](?:_2)?',ref):c['logic_LUT_primitives_not_native_LUT_total']+=1
            if ref.startswith(('FD','LD')):
                c['FF_latch_primitives_all_sites']+=1
                if loc.startswith('SLICE_'):c['FF_latch_primitives_at_SLICE_sites']+=1
                else:c['FF_latch_primitives_outside_SLICE_sites']+=1
            if ref.startswith(('RAMB36','FIFO36')):c['RAMB36_FIFO36_primitives']+=1;c['BRAM_36K_equivalent']+=1
            if ref.startswith(('RAMB18','FIFO18')):c['RAMB18_FIFO18_primitives']+=1;c['BRAM_36K_equivalent']+=.5
            if ref.startswith('URAM'):c['URAM_primitives']+=1
            if ref.startswith('DSP'):
                c['DSP_split_primitives_not_blocks']+=1
                if loc:dsp_sites[key].add(loc)
            if loc:
                sites[loc].add(owner)
                if loc in site_slr and site_slr[loc]!=slr:raise ValueError('Site SLR inconsistent: '+loc)
                site_slr[loc]=slr
                if loc.startswith('SLICE_'):slice_sites[key].add(loc)
            else:unplaced[owner]+=1
    for key,c in metrics.items():
        c['DSP_unique_occupied_sites']=len(dsp_sites[key])
        c['SLICE_touched_sites_nonadditive_between_owners']=len(slice_sites[key])
    native_counts={}
    with (report/'exclusive_owner_SLR_REF_counts.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            k=(row['exclusive_owner'],row['SLR'],row['primitive_REF'])
            if k in native_counts:raise ValueError('Duplicate native ref group')
            native_counts[k]=int(row['primitive_count_not_native_resource_count'])
    if dict(counts)!=native_counts:raise ValueError('Independent ref aggregation differs from native export')
    coverage=dict(line.split('\t') for line in (report/'ownership_coverage.tsv').read_text().splitlines())
    if n!=int(coverage['all_primitive_count']) or len(names)!=int(coverage['classified_unique_primitive_count']):raise ValueError('Native coverage differs')
    if len(sites)!=int(coverage['site_sets_nonadditive']):raise ValueError('Native occupied sites differs')
    if mismatches:raise ValueError('Owner prefix mismatch: '+repr(mismatches[:10]))
    native_sites={}
    with (report/'site_owner_sets.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            native_sites[row['site']]=set(row['exclusive_primitive_owners_sharing_site'].split())
    if dict(sites)!=native_sites:raise ValueError('Independent site owner sharing differs')
    result={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'closure_query':close[0], 'source':{'path':str(source.relative_to(ROOT)),'bytes':source.stat().st_size,'sha256':digest.hexdigest()},
        'unique_primitives':n,'independent_prefix_owner_mismatches':0,'independent_ref_counts_equal_native':True,
        'independent_site_owner_sets_equal_native':True,'unique_occupied_sites':len(sites),'unplaced_by_owner':dict(unplaced),
        'module_SLR_metrics':[{'owner':o,'SLR':s,**c} for (o,s),c in sorted(metrics.items())],
        'SLR1_shared_SLICE_sites':sum(p.startswith('SLICE_') and site_slr[p]=='SLR1' and len(o)>1 for p,o in sites.items()),
        'limits':['Logic LUT primitive counts can exceed native LUT resources due to physical combining.',
                  'All-site FF primitive count is not CLB Registers; SLICE-site subset is separately exposed for native comparison.',
                  'BRAM uses 36K equivalents; DSP uses unique occupied sites instead of split primitive counts.',
                  'Owner-touched SLICE sites can overlap and cannot be added as unique sites.',
                  'Global primitive ownership has closed; later native reports, hotspots and connections are independent pending stages.']}
    path=OUT/'closed_primitive_ownership_review.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(path.relative_to(ROOT)),'unique_primitives':n,
        'SLR1': [x for x in result['module_SLR_metrics'] if x['SLR']=='SLR1'],
        'SLR1_shared_SLICE_sites':result['SLR1_shared_SLICE_sites']},ensure_ascii=False))


if __name__=='__main__':main()
