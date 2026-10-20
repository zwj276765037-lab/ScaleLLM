"""CPU cost qualification from old immutable48-document metrics; no model/GPU."""
from __future__ import annotations
import argparse
from collections import Counter
import cProfile
import copy
import io
import json
from pathlib import Path
import pstats
import sys
import time
from run_numerical_fidelity import summarize_documents,CELL_FIELDS,identity,write_json,timestamp,cpu_supervise

FIELDS=['relative_l2_percent','normalized_signed_bias_percent','signal_rms','absolute_rmse','absolute_max']


def without_bootstrap(cells):
    result=copy.deepcopy(cells)
    for cell in result:
        for field in FIELDS:cell[field].pop('bootstrap95',None)
    return result


def worker(args):
    here=Path(__file__).parent
    source=identity(here/'run_numerical_fidelity.py')
    before=[];cost=[];profile_input=None
    for raw,summary in [('tensor_metrics.jsonl','document_summary.json'),('local_tensor_metrics.jsonl','local_document_summary.json'),('FINAL','final_norm_document_summary.json')]:
        paths=sorted((args.attempt/'documents').glob('doc*/final_norm_comparison.json')) if raw=='FINAL' else [args.attempt/raw]
        before += [identity(path) for path in paths]+[identity(args.attempt/summary)]
        rows=[]
        for path in paths:
            if raw=='FINAL':rows.append(json.loads(path.read_text()))
            else:rows.extend(json.loads(line) for line in path.read_text().splitlines())
        old=json.loads((args.attempt/summary).read_text());begin=time.perf_counter()
        measured=summarize_documents(rows,bootstrap_replicates=0);seconds=time.perf_counter()-begin
        assert measured['document_metrics']==old['document_metrics'],'per-document metric changed'
        assert without_bootstrap(measured['cells'])==without_bootstrap(old['cells']),'point quantiles changed'
        assert measured['element_counts']==old['element_counts'],'count changed'
        counts=Counter(tuple(row.get(field) for field in CELL_FIELDS)+(series,) for row in rows for series in row['metrics'])
        eligible=sum(count>=20 for count in counts.values())
        cost.append(dict(input=raw,rows=len(rows),documents=measured['document_count'],cells=len(counts),
                         bootstrap_eligible_cells=eligible,legacy_quantile_draw_calls=eligible*len(FIELDS)*2000,
                         no_bootstrap_seconds=seconds,all_document_metrics_equal=True,all_point_quantiles_equal=True,all_counts_equal=True))
        if raw=='local_tensor_metrics.jsonl':
            profile_input=[row for row in rows if row['layer']==0 and row['node']=='linear' and row['op']=='q_proj' and row['domain']=='web']
    profiler=cProfile.Profile();begin=time.perf_counter();profiler.enable()
    one=summarize_documents(profile_input);profiler.disable();one_seconds=time.perf_counter()-begin
    stream=io.StringIO();pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(25)
    (args.output_dir/'one_cell_profile.txt').write_text(stream.getvalue())
    profiler.dump_stats(str(args.output_dir/'one_cell_profile.pstats'))
    assert len(profile_input)==24 and len(one['cells'])==1
    for spec in [source,*before]:assert identity(spec['path'])==spec,'input/source changed'
    result=dict(schema='m005_extended_summary_cost_v1',recorded_at=timestamp(),attempt=identity(args.attempt/'paired_result.json'),
        source=source,input_identities=before,qualification=cost,
        profile=dict(real_documents=24,cells=1,replicates=2000,metrics=5,bootstrap_draw_quantile_calls=10000,
                     seconds=one_seconds,extrapolation='per-cell profile has instrumentation overhead; not a full default48doc rerun'),
        root_cause='N>=20 activates2000 document bootstrap replicates for each of5 metrics in every cell;48doc web24 qualifies,16doc web8 does not',
        numerical_boundary='bootstrap0 preserves per-document energies/ratios/counts and point quantiles exactly; batch bootstrap CIs omitted explicitly, formal final inference remains separate',
        proposal='GPU worker writes raw per-document/position metrics and coverage only; final collection performs predeclared document statistics once offline',
        command=sys.argv,no_gpu=True,no_model=True)
    write_json(args.output_dir/'summary_cost.json',result)
    print(json.dumps(dict(no_bootstrap_seconds=sum(row['no_bootstrap_seconds'] for row in cost),one_cell_seconds=one_seconds,
        total_legacy_bootstrap_draws=sum(row['legacy_quantile_draw_calls'] for row in cost),point_metrics_unchanged=True)))
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attempt',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--wall-seconds',type=int,default=300);p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    return worker(args) if args.worker else cpu_supervise(args,__file__,'summary_cost',[Path(__file__).parent/'run_numerical_fidelity.py'])


if __name__=='__main__':raise SystemExit(main())
