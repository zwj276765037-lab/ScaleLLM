#!/usr/bin/env python3
"""One-time R005 same-scope helper repair freeze; preserves failed 558c package."""
from datetime import datetime,timezone
import json
from pathlib import Path
from directed_evidence import identity,save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent/'directed_candidate_cut'

def main():
    output=HERE/'prepared_source_manifest.json';assert not output.exists()
    base=json.loads((BASE/'prepared_source_manifest.json').read_text())
    for row in base['source_files']+base['CPU_checks']:
        assert identity(row['path'])==row,'Original 558c package changed'
    runtime=base['runtime_source_names']
    lookup={Path(row['path']).name:row for row in base['source_files']}
    for name in runtime:
        if name=='candidate_inspector.tcl':continue
        actual=identity(HERE/name);assert all(actual[key]==lookup[name][key] for key in ['bytes','sha256']),'Unexpected functional runtime change: '+name
    original=ROOT/'agent/A006/E006_exact_candidates/candidate_inspector.tcl'
    historical=original.read_text();start=historical.index('proc slr2::owner name {');end=historical.index('proc slr2::spatial loc {',start);owner=historical[start:end]
    assert (HERE/'candidate_inspector.tcl').read_text()==(BASE/'candidate_inspector.tcl').read_text().replace('proc slr2::spatial loc {',owner+'proc slr2::spatial loc {',1)
    checks=[HERE/'CPU_checks/CT001_owner_dependency.json',HERE/'CPU_checks/CT006_actual_readonly_resolve.json',HERE/'CPU_checks/CT007_final_control_membership.json']
    actual=json.loads(checks[1].read_text());assert actual['actual_all_slr2_helpers_not_stubbed'] and actual['actual_readonly_resolve_completed'] and actual['no_original_procedure_deleted']
    cpu=json.loads(checks[-1].read_text());assert all(cpu['checks'].values())
    for row in cpu['source_files']:assert identity(row['path'])==row
    own=runtime+['README.md','check_preparation_CPU.py','prepare_reuse_manifest.py','freeze_prepared_manifest.py','check_owner_dependency_CPU.py','check_readonly_resolve_mock.tcl']
    prior=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/attempts/AT001_candidate_directed_cut'
    external=dict(base['external_inputs'])
    external.update(original_558c_manifest=identity(BASE/'prepared_source_manifest.json'),
        failed_AT001_terminal_status=identity(prior/'status.json'),failed_AT001_terminal_facts=identity(prior/'terminal_facts.json'),
        original_owner_source=identity(original))
    value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CPU_PREPARED_NOT_EXECUTED',EDA_executed=False,
        exporter_protocol_complete=True,source_protocol_and_CPU_checks_complete=True,native_design_or_class_qualification=False,
        coverage_version='candidate_directed_cut_v1',source_files=[identity(HERE/name) for name in own],runtime_source_names=runtime,
        CPU_checks=[identity(path) for path in checks]+base['CPU_checks'],external_inputs=external,scope_revision=base['scope_revision'],
        repair=dict(kind='same_scope_ordinary_pure_helper_restoration',original_package=identity(BASE/'prepared_source_manifest.json'),
            failed_native_attempt_status=identity(prior/'status.json'),failed_native_attempt_facts=identity(prior/'terminal_facts.json'),
            root_cause='Original old-cut cleanup accidentally removed neighboring owner pure metadata procedure; readonly_resolve site ledger failed before native cut/class/role',
            production_or_native_API_changes=False,only_functional_runtime_change='Exact frozen R004 slr2::owner restored in new inspector',
            shared_collector_and_validator_unchanged=True,original_b59_and_E008_1d612_unchanged=True),
        launch_dependencies=['New source-bound R005 retry execution binding under same scope','All prior E006 owners including failed AT001 closed; nonblocking unique EDA lane free',
            'Same native DCP/144 production identity checks and fresh native membership/class/role/cut/timing qualification'],
        limitations=['No native class/role/directed cut result from failed AT001','CPU native mocks are not actual Vivado qualification','No candidate supported or implementation success inferred'])
    save(output,value);print(json.dumps(identity(output)))

if __name__=='__main__':main()
