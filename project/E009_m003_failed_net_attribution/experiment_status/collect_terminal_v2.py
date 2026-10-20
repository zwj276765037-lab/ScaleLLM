#!/usr/bin/env python3
"""Post-terminal, CPU-only closure and independent census arithmetic audit."""
import argparse,collections,csv,datetime,fcntl,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def identity(p):
    p=p.resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def rows(p):
    with p.open() as f:yield from csv.DictReader(f,delimiter='\t')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',type=Path,required=True);a=ap.parse_args();at=a.attempt.resolve()
    assert at.is_relative_to(ROOT/'project/E009_m003_failed_net_attribution/experiment_results/runs')
    target=at/'terminal_facts_v2.json';assert not target.exists(),'append-only terminal producer'
    status=json.loads((at/'status.json').read_text());assert status['execution_state'] in ('completed','failed')
    ids=dict(status['tracked_identities'])
    for role in ('leader','supervisor'):ids[str(status[role+'_pid'])]=status[role+'_start_ticks']
    present=[];live=[]
    for pid,start in ids.items():
        p=Path(f'/proc/{pid}/stat')
        try:
            fs=p.read_text().rsplit(')',1)[1].split()
            if int(fs[19])==start:
                r=dict(pid=int(pid),start_ticks=start,state=fs[0]);present.append(r)
                if fs[0]!='Z':live.append(r)
        except FileNotFoundError:pass
    with (ROOT/'project/hardware/vivado/.m002_eda.lock').open('r') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);lane_free=True;fcntl.flock(f,fcntl.LOCK_UN)
        except BlockingIOError:lane_free=False
    baseline=json.loads((at/'sources/baseline.json').read_text());mismatches=[]
    for r in baseline['identities']+baseline['production_inputs']:
        if identity(Path(r['path']))!=r:mismatches.append(r['path'])
    bindings=json.loads((at/'input_bindings.json').read_text());archives=[]
    for r in bindings['archive']:
        if identity(Path(r['path']))!=r:archives.append(r['path'])
    out=at/'evidence/native';native_counts={}
    rpt=out/'native_route_status.rpt'
    if rpt.exists():
        for line in rpt.read_text().splitlines():
            match=re.match(r'^\s*(.*?)\s*:\s*(\d+)\s*:\s*$',line)
            if match:native_counts[match.group(1).rstrip('.').strip()]=int(match.group(2))
    arithmetic={};coverage_file=out/'unknowns_and_coverage.json'
    if coverage_file.exists() and (out/'native_completed.txt').exists():
        claimed=json.loads(coverage_file.read_text());ids=set();groups=collections.defaultdict(set)
        for r in rows(out/'failed_nets.tsv'):
            assert r['canonical'] not in ids,'duplicate canonical output'
            ids.add(r['canonical']);groups[(r['driver_module'],r['source_SLR'],r['load_SLRs'] or 'NO_LOADS')].add(r['canonical'])
        sorted_groups=sorted(groups,key=lambda k:(-len(groups[k]),k))
        table=list(rows(out/'module_region_summary.tsv'))
        assert [(r['driver_module'],r['source_SLR'],r['load_SLR_set']) for r in table]==sorted_groups
        assert [int(r['unique_conflict_nets']) for r in table]==[len(groups[k]) for k in sorted_groups]
        main_union=set().union(*(groups[k] for k in sorted_groups[:20])) if groups else set()
        supplemental={r['canonical'] for r in rows(out/'net_inventory.tsv') if r['conflict']=='1' and r['seed_tags']}
        union=main_union|supplemental
        assert len(ids)==claimed['canonical_conflict_nets']==sum(len(v) for v in groups.values())
        assert len(main_union)==claimed['top20_unique_conflict_nets']
        assert len(union)==claimed['top20_plus_supplemental_union']
        arithmetic=dict(canonical_unique=len(ids),primary_disjoint_count=sum(len(v) for v in groups.values()),primary_groups=len(groups),top20_whole_group_union=len(main_union),supplemental_union=len(supplemental),combined_union=len(union),representative_deep_sample_is_not_whole_group_coverage=True,output_recomputed=True)
    facts=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=identity(at/'status.json'),native_exit_code=status['native_exit_code'],supervisor_exit_code=status['exit_code'],stop_reason=status['stop_reason'],native_natural_terminal=status['native_natural_terminal_observed'],cleanup_was_required=status['cleanup_was_required'],registered_pid_start_count=len(ids),registered_identities_still_present=present,registered_live_processes=live,eda_lane_free=lane_free,production_inputs_verified=len(baseline['production_inputs']),baseline_or_production_mismatches=mismatches,source_archive_mismatches=archives,native_route_status=native_counts,baseline_conflict_nets=547548,baseline_overlap_nodes=702396,overlap_node_complete_export='NOT_MEASURED',census_arithmetic=arithmetic,extraction_execution_success=status['exit_code']==0 and (out/'native_completed.txt').exists(),engineering_closure_verified=not live and lane_free and not mismatches and not archives and status['post_integrity_error'] is None,G1_review='PENDING_INDEPENDENT_REVIEW',producer=identity(Path(__file__)))
    target.write_text(json.dumps(facts,indent=2)+'\n');print(json.dumps(facts,indent=2))
if __name__=='__main__':main()
