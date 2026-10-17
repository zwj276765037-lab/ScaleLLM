#!/usr/bin/env python3
"""One-time capture of actual R005 native closed stages; no EDA/process control."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent/A006/directed_candidate_cut'))
from directed_evidence import identity,save,rows,require
ATTEMPT=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/attempts/AT001_candidate_directed_cut'
REPORT=ROOT/'project/hardware/vivado/reports/m002_E006_R005_AT001_candidate_directed_cut'
PHASES={'membership':'membership_qualification','cut':'directed_cut','timing':'bounded_timing'}


def main():
    global ATTEMPT,REPORT
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('point',choices=['C01','C02']);parser.add_argument('phase',choices=PHASES)
    parser.add_argument('--attempt',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.attempt:ATTEMPT=args.attempt.resolve()
    if args.report:REPORT=args.report.resolve()
    require(ATTEMPT.parent==ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/attempts','Wrong R005 attempt')
    require(REPORT.parent==ROOT/'project/hardware/vivado/reports' and REPORT.name.startswith('m002_E006_R005_'),'Wrong R005 report')
    point=args.point;phase=args.phase;stage='candidate_'+point+'_'+PHASES[phase]
    output=ATTEMPT/(stage+'_closed_facts.json');summary=ATTEMPT/(stage+'_closed_summary.json');producer=ATTEMPT/('capture_'+stage+'_producer.py')
    require(not any(p.exists() for p in [output,summary,producer]),'Never overwrite captured stage evidence or producer')
    receipts=[row for row in rows(REPORT/'stage_receipts.tsv') if row['stage']==stage]
    require(len(receipts)==1,'Actual native stage has not uniquely closed')
    native=receipts[0]
    # Older failed attempts retained multiline native tracebacks in result.
    # Parse only an exact known query record start; full result stays in its
    # original Tcl error artifact. New entries escape TSV control characters.
    queries=[]
    with (REPORT/'query_receipts.tsv').open() as stream:
        next(stream)
        for line in stream:
            fields=line.rstrip('\n').split('\t',4)
            if len(fields)==5 and fields[0]==stage and fields[1] in {'0','1'} and fields[2].isdigit() and fields[3].isdigit():
                queries.append(dict(zip(['query','native_tcl_code','started_epoch','ended_epoch','result_first_physical_line'],fields)))
    require(len(queries)==1 and queries[0]['native_tcl_code']==native['native_tcl_code'],'Actual query/stage closure differs')
    bound=identity(ATTEMPT/'input_bindings.json');started=json.loads((ATTEMPT/'started.json').read_text());require(bound==started['inputs'],'Started input bindings changed')
    inputs=json.loads((ATTEMPT/'input_bindings.json').read_text())
    source_ids=[identity(row['path']) for row in inputs['sources']];require(source_ids==inputs['sources'],'Fixed archived source changed')
    reuse={key:identity(row['path']) for key,row in inputs['reused_closed_inputs'].items()};require(reuse==inputs['reused_closed_inputs'],'Closed reused input changed')
    require(identity(inputs['preparation_manifest']['path'])==inputs['preparation_manifest'],'Prepared manifest changed')
    zero=native['native_tcl_code']=='0';value=None;files=[]
    if zero:
        if phase=='membership':
            path=REPORT/f'candidate_membership_qualification_{point}.json';value=json.loads(path.read_text());files.append(path)
            require(value['actual_same_DCP_membership_qualified'] is True,'Actual native member qualification not closed')
            for tag in ['RAW','S','P']:require(identity(value['current'][tag]['artifact']['path'])==value['current'][tag]['artifact'],'Fresh member ledger changed')
            for tag in ['membership','physical_members','site_members']:require(identity(value['current'][tag]['path'])==value['current'][tag],'Fresh policy/site ledger changed')
        elif phase=='cut':
            path=REPORT/f'candidate_cut_summary_{point}.json';value=json.loads(path.read_text());files.append(path)
            require(value['coverage_version']=='candidate_directed_cut_v1' and value['directed_boundary_complete'] is True and value['candidate_leaf_coverage_complete'] is True,'Fresh directed cut not qualified')
            for row in list(value['artifacts'].values())+[value[key] for key in ['schema','local_scope','native_role_queries','native_closed_marker','validator']]:
                require(identity(row['path'])==row,'Closed directed raw ledger changed')
        else:
            path=REPORT/f'candidate_timing_validation_{point}.json';value=json.loads(path.read_text());files.append(path)
            require(value['coverage_version']=='candidate_directed_cut_v1' and value['complete_directional_query_sets'] is True,'Native bounded timing qualification not closed')
            for row in value['artifacts']:require(identity(row['path'])==row,'Closed timing raw input changed')
            files.extend(p for p in REPORT.glob(f'candidate_cut_timing_{point}_*.rpt') if p.is_file())
    else:
        error=REPORT/('error_'+stage+'.txt')
        if error.is_file():files.append(error)
        # Partial data remains in place; failure never receives qualified summary.
        files.extend(p for p in REPORT.glob('candidate_*_'+point+'.*') if p.is_file())
    stage_marker=REPORT/('stage_'+stage+'_closed.txt');files.append(stage_marker)
    shutil.copy2(Path(__file__),producer)
    facts=dict(observed_utc=datetime.now(timezone.utc).isoformat(),point=point,stage=stage,
        coverage_version='candidate_directed_cut_v1',native_closed_stage_receipt=native,native_closed_query_receipt=queries[0],native_stage_zero=zero,
        execution='closed_native_stage_with_CPU_consistency' if zero else 'closed_native_query_failure_unqualified',
        native_result=value,input_bindings=bound,prepared_source_manifest=inputs['preparation_manifest'],archived_sources_unchanged=source_ids,
        reused_closed_input_identities=reuse,current_R004_prior_closure=inputs['prior_R004_closure'],
        source_DCP=inputs['checkpoint'],resource_reports='Explicit R004 reuse, not freshly queried in R005',
        candidate_supported='NOT_ASSESSED',physical_implementation='NOT_RUN_IN_THIS_DIAGNOSTIC',formal_signoff=False,
        final_input_PID_lane_resource_closure='PENDING_ACTUAL_SUPERVISOR_TERMINAL',
        artifacts=[identity(p) for p in files],producer=identity(producer))
    save(output,facts)
    short={key:facts[key] for key in ['observed_utc','point','stage','coverage_version','native_stage_zero','execution','candidate_supported','formal_signoff','final_input_PID_lane_resource_closure']}
    if value is not None:
        if phase=='membership':short['current']={tag:value['current'][tag]['count'] for tag in ['RAW','S','P']}
        elif phase=='cut':
            short['directed_cut']={key:value[key] for key in ['canonical_nets','actual_candidate_native_leaf_pins','retained_endpoint_rows','scope_modes','boundary_directions','candidate_involved_driver_load_pairs','candidate_boundary_driver_load_pairs','pair_scope','unknown_top_or_unplaced_pair_positions','timing_scope_rows']}
            short['original_failure_sample_alias_relation']=value['original_failure_sample_alias_relation']
        else:short['native_timing']={key:value[key] for key in ['complete_directional_query_sets','native_query_count','max_paths','nworst','full_cut_TNS']}
    short['full_facts']=identity(output);save(summary,short)
    print(json.dumps(dict(facts=identity(output),summary=identity(summary),native_stage_zero=zero)))

if __name__=='__main__':main()
