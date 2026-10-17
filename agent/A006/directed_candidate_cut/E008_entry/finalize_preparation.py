#!/usr/bin/env python3
"""Freeze new E008 directed scope source; never choose candidate or launch EDA."""
import ast
import json
from pathlib import Path
from datetime import datetime,timezone
from directed_evidence import identity,save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'agent/A006/exact_hotspot_offload'

def main():
    target=HERE/'prepared_manifest.json';assert not target.exists(),'Never overwrite new E008 package identity'
    base_manifest=json.loads((BASE/'prepared_manifest.json').read_text())
    for row in base_manifest['own_sources']+base_manifest['reused_sources']:assert identity(row['path'])==row
    for name in ['directed_exporter.tcl','directed_evidence.py']:
        assert (HERE/name).read_bytes()==(HERE.parent/name).read_bytes(),'Shared coverage collector/validator differs'
    cpu_paths=[HERE/'bounded_CPU_admission_directed_CT001.json',HERE/'bounded_CPU_admission_directed_CT005.json']
    cpus=[json.loads(path.read_text()) for path in cpu_paths]
    assert all(all(value in {True,'PASS'} for value in row['checks'].values()) for row in cpus)
    for row in cpus[-1]['source_identities']:assert identity(row['path'])==row,'Final phase CPU checked source changed'
    contract=ROOT/'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md'
    scope=ROOT/'mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md'
    reuse=dict(original_b59_manifest=identity(BASE/'prepared_manifest.json'),
               original_b59_independent_review=identity(ROOT/'agent/A007/independent_E008_source_preparation_review_b59d1126.json'),
               shared_R005_manifest=identity(HERE.parent/'prepared_source_manifest.json'),
               same_shared_collector_and_validator=True,base_contract=identity(contract),scope_revision=identity(scope),
               actual_P_projection='Same-phase RAW/S literal + actual reconciled P, pre-place native literal P; read-only links; no raw replacement',
               physical_and_policy_qualification='Original b59 gates and source recovery retained',
               EDA_executed=False,candidate_selected=None)
    save(HERE/'source_reuse_manifest.json',reuse)
    own_names=['candidate_hooks.tcl','runtime_hooks.tcl','property_alignment.tcl','implementation.tcl','evidence_adapter.py',
        'directed_exporter.tcl','directed_evidence.py','run_candidate.py','launch_detached.py','target_authority.json',
        'validate_cpu.py','check_directed_phase_CPU.py','finalize_preparation.py']
    target_authority=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'
    assert (HERE/'target_authority.json').read_bytes()==target_authority.read_bytes()
    value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CPU_PREPARED_NOT_EXECUTED',EDA_executed=False,candidate_selected=None,
        coverage_version='candidate_directed_cut_v1',own_sources=[identity(HERE/name) for name in own_names],reused_sources=base_manifest['reused_sources'],
        contract=identity(contract),scope_revision=identity(scope),selector_reference=identity(HERE/'target_authority.json'),
        original_target_authority=identity(target_authority),source_reuse_manifest=identity(HERE/'source_reuse_manifest.json'),
        CPU_checks=[identity(path) for path in cpu_paths],documentation=[identity(HERE/'README.md')],
        shared_collector=identity(HERE/'directed_exporter.tcl'),shared_validator=identity(HERE/'directed_evidence.py'),
        validation=dict(Python_AST='PASS',Tcl_info_complete='PASS',literal_membership_and_actual_P_projection_CPU='PASS',
            native_APIs='NOT_RUN',actual_pre_place_membership='NOT_RUN',native_resource_admissibility='NOT_RUN',geometry_readback='NOT_RUN',
            candidate_directed_cut='NOT_RUN',place_physopt_route='NOT_RUN'),current_EDA_unchanged=True,
        launch_dependencies=['Actual same-DCP directed candidate comparison and supported single ID/root selection',
            'All registered E006 PID/start ownership closed and nonblocking unique EDA lane free',
            'Root actual terminal/evidence/base_contract/scope_revision/preparation_manifest binding',
            'Native pre-place, 80 protections, 144 production input/175 source constraint identities and migration qualification',
            'Fresh native local-leaf/alias/class/role gates at each phase; full legal route and formal setup/hold/PW/DRC remain required'])
    save(target,value);print(json.dumps(identity(target)))

if __name__=='__main__':main()
