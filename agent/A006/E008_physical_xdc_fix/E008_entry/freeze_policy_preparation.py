#!/usr/bin/env python3
"""Freeze only the actual RLOC_ORIGIN policy compatibility delta; never launch EDA."""
import ast
from datetime import datetime,timezone
import json
from pathlib import Path
from directed_evidence import identity
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'agent/A006/E008_top_port_index_logging_fix/E008_entry'


def write(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    target=HERE/'prepared_manifest.json';assert not target.exists()
    original=BASE/'prepared_manifest.json';base=json.loads(original.read_text())
    for row in base['own_sources']+base['reused_sources']+base['CPU_checks']+base['runtime_dependencies']+base['documentation']:
        assert identity(row['path'])==row
    for row in base['own_sources']:
        name=Path(row['path']).name
        if name!='runtime_hooks.tcl':assert (HERE/name).read_bytes()==Path(row['path']).read_bytes(),name
    cpu=HERE/'CPU_checks/CT001_native_policy_schema/results.json';result=json.loads(cpu.read_text())
    assert all(result['checks'].values()) and len(result['cases'])==26 and all(row['passed'] for row in result['cases'])
    for key in ['source','baseline','fixture','producer']:assert identity(result[key]['path'])==result[key]
    for row in result['cases']:
        assert all(identity(item['path'])==item for item in row['artifacts'])
    failure=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT001_C01_slr2_offload_full_implementation'
    facts=json.loads((failure/'terminal_facts.json').read_text());assert facts['closure_verified'] is True
    assert facts['native_exit_code']==1 and facts['supervisor_exit_code']==1 and facts['stop_reason'] is None
    rule=ROOT/'agent/A007/E008_R001_AT001_actual_stage_review_20261017/RLOC_ORIGIN_schema_failure_and_minimal_rule.json'
    policy_rule=json.loads(rule.read_text());assert policy_rule['minimal_rule']['only_allowed_schema_exception']=='RLOC_ORIGIN'
    reuse=dict(original_consumed_preparation=identity(original),original_unchanged_reuse_record=base['source_reuse_manifest'],
        actual_failed_attempt_terminal=identity(failure/'terminal_facts.json'),actual_native_failure=identity(Path(facts['status']['path'])),
        independent_actual_rule=identity(rule),delta='Only native policy schema compatibility; no RTL/physical variable/selector/index/logging/global gate changes',
        reuse_scope='Previously accepted unchanged physical/coverage/logging CPU tests reused; affected actual runtime policy/constrain wrapper checked by26 focused cases',EDA_executed=False)
    write(HERE/'source_reuse_manifest.json',reuse)
    own=[HERE/Path(row['path']).name for row in base['own_sources']]+[HERE/'check_policy_schema_CPU.py',Path(__file__).resolve()]
    for path in own:
        if path.suffix=='.py':ast.parse(path.read_text(),filename=str(path))
    value=dict(base)
    value.update(recorded_utc=datetime.now(timezone.utc).isoformat(),own_sources=[identity(path) for path in own],
        selector_reference=identity(HERE/'target_authority.json'),source_reuse_manifest=identity(HERE/'source_reuse_manifest.json'),
        CPU_checks=base['CPU_checks']+[identity(cpu)],documentation=[identity(HERE/'README.md')],
        shared_collector=identity(HERE/'directed_exporter.tcl'),shared_validator=identity(HERE/'directed_evidence.py'),
        original_preparation=identity(original),
        validation=dict(actual_collector_phase_projection_CPU='Accepted unchanged collector32-case proof reused, not rerun',
            affected_native_policy_CPU='26 actual resource/policy/constrain-wrapper cases passed',
            native_policy_compatibility='NOT_RUN_IN_NEW_NATIVE_ATTEMPT',native_port_index='NOT_RUN_IN_NEW_NATIVE_ATTEMPT',
            actual_pre_place_membership='NOT_RUN_IN_NEW_NATIVE_ATTEMPT',place_physopt_route='NOT_RUN',physical_signoff=False),
        native_policy_schema_repair=dict(actual_rule=identity(rule),only_schema_exception='RLOC_ORIGIN',
            unsupported='Explicit object-bound unsupported state plus actual native0 empty scalar result required; errors/nonempty reject',
            supported='Actual value preserved, nonempty relative-macro conflict remains',
            preservation='Original wrapper/ancestors/macros/Pblocks unchanged; support status and native values included in exact before/after snapshots',
            cache='Only immediately preceding actual per-object resource census before any design mutation; ancestors and after schemas freshly queried'))
    write(target,value);print(json.dumps(identity(target)))


if __name__=='__main__':main()
