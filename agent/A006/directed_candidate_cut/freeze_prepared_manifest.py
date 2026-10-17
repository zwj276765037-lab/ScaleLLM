#!/usr/bin/env python3
"""Freeze the CPU-checked R005 package; does not grant or execute EDA/stop."""
from datetime import datetime,timezone
import json
from pathlib import Path
from directed_evidence import identity,save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUNTIME=['attribution_directed.tcl','candidate_inspector.tcl','directed_exporter.tcl','property_alignment.tcl',
         'targets.tcl','directed_evidence.py','reuse_manifest.json','run_directed_attribution.py',
         'launch_detached.py','controlled_stop_R004.py']

def main():
    path=HERE/'prepared_source_manifest.json';assert not path.exists(),'Never overwrite prepared source manifest'
    review=ROOT/'agent/A007/directed_source_review_20261017'
    tested=json.loads((review/'round3_source_identities.json').read_text())
    for row in tested:
        actual=identity(row['source']);assert all(actual[key]==row[key] for key in ['bytes','sha256']),'Final collector/adapter differs from actual independently tested source'
    results=json.loads((review/'round3_adapter_results.json').read_text());assert len(results)==28 and all(row['returncode']==0 for row in results)
    mutation_result=json.loads((review/'adapter_mutations_round3/results.json').read_text());assert mutation_result['parser_brackets_multiword_empty_pass'] is True
    mutations=[row for row in mutation_result['cases'] if row['expected_accept'] is False];assert len(mutations)==9 and all(row['actual_accept'] is False and row['returncode']!=0 for row in mutations)
    cpu=HERE/'CPU_checks/CT003_final_control_membership.json';check=json.loads(cpu.read_text());assert all(check['checks'].values())
    # CT002 must bind every directly executed/imported current package source it checked.
    for row in check['source_files']:assert identity(row['path'])==row,'CPU-checked source changed'
    sources=RUNTIME+['README.md','check_preparation_CPU.py','prepare_reuse_manifest.py','freeze_prepared_manifest.py']
    external={
        'scope_revision':ROOT/'mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md',
        'independent_exporter_specification':ROOT/'agent/A007/directed_candidate_cut_scope_review_20261017.md',
        'independent_finite_graph_CPU_model':ROOT/'agent/A007/directed_cut_scope_model_check_20261017.json',
        'prior_fixed_R004_runner':ROOT/'agent/A006/E006_exact_candidates/run_attribution_lean.py',
        'imported_identity_freeze_PID_helpers':ROOT/'agent/A006/E006_lean_candidate/run_attribution_lean.py',
        'resource_process_guard':ROOT/'project/hardware/vivado/scripts/run_m002_no_wall.py',
        'imported_guard_profile':ROOT/'project/hardware/vivado/scripts/m002_execution_profile.py',
        'production_freeze_manifest':ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json',
        'R004_target_authority':ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json',
        'R004_terminal_capture_producer':ROOT/'agent/A006/E006_exact_candidates_capture/capture_terminal.py'}
    checks=[cpu,review/'round3_source_identities.json',review/'round3_adapter_results.json',review/'adapter_mutations_round3/results.json',
            review/'check_native_mock_round3.tcl',review/'check_adapter_contract.py']
    # Select actual existing independent script identity; the result files identify their source snapshots.
    checks=[p for p in checks if p.is_file()]
    source_hashes={p:identity(HERE/p) for p in sources}
    result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CPU_PREPARED_NOT_EXECUTED',
                EDA_executed=False,native_design_or_class_qualification=False,source_protocol_and_CPU_checks_complete=True,
                exporter_protocol_complete=True,coverage_version='candidate_directed_cut_v1',
                source_files=list(source_hashes.values()),runtime_source_names=RUNTIME,CPU_checks=[identity(p) for p in checks],
                external_inputs={key:identity(p) for key,p in external.items()},scope_revision=identity(external['scope_revision']),
                source_guard_tail='Byte-identical actual R004 native process/resource/post-integrity tail',
                E008_preparation='SEPARATE_WIP_NOT_INCLUDED_OR_EXECUTABLE_BY_THIS_MANIFEST',
                no_stop_authorization_created=True,no_stop_signal_sent=True,no_automatic_launch_or_queue=True,
                original_R004_sources_and_E008_b59='UNCHANGED',
                admission_checks=dict(independent_actual_collector_cases=17,independent_closed_cut_cases=14,
                    independent_cut_and_scoped_timing_CLI_passes=28,independent_ledger_command_mutations_rejected=len(mutations),
                    both_actual_closed_member_resource_fixture_ledgers_match=True),
                next_native_requirements=['New R004 user stop exception or natural terminal and actual PID/start/144-input/DCP/source/lane closure',
                    'Actual source-bound R005 attempt/report/execution binding',
                    'Fresh native class, leaf/alias/role, directed cut and bounded timing qualification on actual unchanged DCP'],
                limitations=['CPU native mocks and graph models are not Vivado API qualification or measured speedup',
                    'No candidate selected or supported by this manifest','Full implementation, legal routing and formal timing still pending'])
    save(path,result);print(json.dumps(identity(path)))

if __name__=='__main__':main()
