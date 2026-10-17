#!/usr/bin/env python3
"""Read a naturally closed E008 physical stage; never launch/control EDA."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'project/hardware/vivado/scripts'))
import m002_physical_evidence as e
sys.path.insert(0, str(ROOT/'agent/A006/E006_lean_capture'))
from capture_stage import native_slr


def identity(path):
    path=Path(path).resolve();before=path.stat();digest=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(4*1024*1024), b''):digest.update(data)
    after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(path=str(path),bytes=after.st_size,sha256=digest.hexdigest())


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--stage',choices=['place','physopt','route'],required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve();point=args.stage
    assert attempt.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts'
    assert report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_')
    target=attempt/f'{point}_closed_stage_facts.json';producer=attempt/f'capture_{point}_producer.py'
    assert not target.exists() and not producer.exists(), 'Never overwrite stage facts or producer'
    receipt=report/f'candidate_phase_{point}_status.txt';closed=e.key_values(receipt)
    assert all(key in closed for key in ['post_code','locality_code','started_epoch','ended_epoch']), 'No actual closed phase receipt'
    bindings=attempt/'input_bindings.json';binding_id=identity(bindings);started=json.loads((attempt/'started.json').read_text())
    assert binding_id==started['inputs']
    bound=json.loads(bindings.read_text());selected=bound['attribution']['selected_candidate']
    assert identity(bound['preparation_manifest']['path'])==bound['preparation_manifest']
    native_zero=closed['post_code']=='0' and closed['locality_code']=='0'
    facts=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage=point,selected_candidate=selected,
               actual_closed_phase_receipt=closed,native_stage_qualification_zero=native_zero,
               input_bindings=binding_id,original_E005_baseline_scope='same place or physopt phase only; old failed route is not complete routed timing',
               legal_routed_timing_signoff=False,formal_reset_CDC_IO_safety='OPEN',final_input_PID_lane_closure='PENDING_ACTUAL_TERMINAL')
    files=[receipt,report/f'candidate_phase_{point}_receipt.tcllist']
    if not native_zero:
        facts['execution']='Closed native POST/locality failure; partial artifacts are not promoted to a qualified phase'
        files += [p for p in [report/f'{point}_command_result.txt',report/f'{point}_result.txt',report/f'integrity_{point}.json'] if p.is_file()]
    else:
        result=e.key_values(report/f'{point}_result.txt');integrity=json.loads((report/f'integrity_{point}.json').read_text())
        compliance=json.loads((report/f'candidate_compliance_{point}.json').read_text())
        assert result.get('completed')=='1' and result.get('diagnostic_eligible')=='1'
        assert not integrity['gate_issues'] and compliance['compliance_established'] is True
        cut=json.loads((report/f'candidate_cut_summary_{point}.json').read_text())
        scoped=json.loads((report/f'candidate_timing_validation_{point}.json').read_text())
        assert cut['coverage_version']==scoped['coverage_version']=='candidate_directed_cut_v1'
        assert cut['directed_boundary_complete'] is True and cut['candidate_leaf_coverage_complete'] is True
        assert scoped['complete_directional_query_sets'] is True
        timing=e.timing_metrics(report/f'timing_{point}.rpt');resources=e.utilization_metrics(report/f'utilization_{point}.rpt')
        slrs=native_slr(report/f'utilization_slr_{point}.rpt')
        baseline={}
        if point in {'place','physopt'}:
            old_timing=e.timing_metrics(BASELINE/f'timing_{point}.rpt')
            old_resources=e.utilization_metrics(BASELINE/f'utilization_{point}.rpt')
            baseline=dict(timing=old_timing,resources=old_resources,SLR_resources=native_slr(BASELINE/f'utilization_slr_{point}.rpt'),
                timing_delta={k:timing[k]-old_timing[k] for k in timing},
                resource_used_delta={k:resources[k]['used']-old_resources[k]['used'] for k in resources},
                original_artifacts=[identity(BASELINE/f'{name}_{point}.rpt') for name in ['timing','utilization','utilization_slr']])
        facts.update(execution='closed_qualified_physical_stage',timing_metrics_ns_and_endpoint_counts=timing,
                     timing_summary_verdict=e.timing_verdict(timing),device_resources=resources,SLR_resources=slrs,
                     actual_candidate_compliance=compliance,same_phase_E005_comparison=baseline,
                     candidate_cut_coverage_version=cut['coverage_version'],
                     candidate_directed_scope={key:cut[key] for key in ['scope_modes','boundary_directions','actual_candidate_native_leaf_pins','retained_endpoint_rows','candidate_boundary_driver_load_pairs','pair_scope','unknown_top_or_unplaced_pair_positions']},
                     full_net_endpoint_coverage='NOT_CLAIMED_ON_QUALIFIED_REDUCED_NETS',
                     complete_external_fanout='NOT_MEASURED',
                     actual_bounded_timing_validation=scoped,
                     exact_candidate_native_resources=native_slr(report/f'utilization_candidate_{point}_SLR.rpt'),
                     native_POST_result=result,integrity_gate_issues=integrity['gate_issues'],
                     limits='Exact hierarchy resources do not include unproven copies outside that hierarchy. Reconciled actual-P objects are separately checked. Current site sharing is not guaranteed released capacity; bounded timing is not full-cut TNS or board safety.')
        files += [report/f'{name}_{point}.rpt' for name in ['timing','utilization','utilization_slr']]
        files += [report/f'{point}_result.txt',report/f'integrity_{point}.json',report/f'candidate_compliance_{point}.json',
                  report/f'candidate_reconciliation_{point}.json',report/f'candidate_membership_{point}.json',
                  report/f'candidate_cut_summary_{point}.json',report/f'candidate_timing_validation_{point}.json',report/f'utilization_candidate_{point}_SLR.rpt',
                  report/f'candidate_scoped_timing_{point}_coverage.txt',report/f'candidate_timing_queries_{point}.tcllist']
        if point=='route':
            facts['route_counts']=e.route_counts(report/'route_status_route.rpt')
            files.append(report/'route_status_route.rpt')
    shutil.copy2(Path(__file__),producer)
    facts.update(artifacts=[identity(p) for p in files],producer=identity(producer),
                 metric_parser=identity(ROOT/'project/hardware/vivado/scripts/m002_physical_evidence.py'),
                 SLR_parser=identity(ROOT/'agent/A006/E006_lean_capture/capture_stage.py'))
    target=attempt/f'{point}_closed_stage_facts.json'
    with target.open('x') as stream:stream.write(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(identity(target)))


if __name__=='__main__':main()
