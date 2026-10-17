#!/usr/bin/env python3
"""Freeze CPU-prepared E008 source identities; no EDA or candidate selection."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SCRIPTS=ROOT/'project/hardware/vivado/scripts'


def identity(path):
    path=Path(path).resolve();return dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    assert not (HERE/'prepared_manifest.json').exists(), 'Admitted source identity is immutable; preserve before a new revision'
    previous=HERE.parent/'slr2_input_locality'
    def body(path,name):
        return ast.dump(next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
    assert body(HERE/'evidence_adapter.py','successful_pre_place_parent')==body(previous/'evidence_adapter.py','successful_pre_place_parent')
    reuse=dict(E007_reviewed_source_only=identity(previous/'prepared_manifest.json'),
        E007_source_parent_adapter=identity(previous/'evidence_adapter.py'),
        E007_successful_parent_adapter_AST_unchanged=True,
        E006_R004_frozen_source_manifest=identity(HERE.parent/'E006_exact_candidates/prepared_source_manifest.json'),
        E006_R004_query_source=identity(HERE.parent/'E006_exact_candidates/candidate_inspector.tcl'),
        current_E006_runtime_source_mutated=False,
        narrow_changes=['exact literal root and generic RAW/S/P', 'actual P-parent and ancestor policy/admissibility',
            'explicit TAB writers', 'generic memory-aware evidence and native resources', 'single selected actual closure binding',
            'pre-place and each-stage complete cut and exact bounded directional timing', 'alias deduplication and actual origin mapping'])
    (HERE/'source_reuse_manifest.json').write_text(json.dumps(reuse,ensure_ascii=False,indent=2)+'\n')
    for path in HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    for path in HERE.glob('*.tcl'):
        result=subprocess.run(['tclsh'],input='set h [open {'+str(path)+'} r]\nputs [info complete [read $h]]\nclose $h\n',text=True,capture_output=True,check=True)
        assert result.stdout.strip()=='1'
    reused=sorted(set(SCRIPTS.glob('*.py'))|{SCRIPTS/name for name in (
        'm002_resume_physical.tcl','m002_diagnostic_common.tcl','m002_optimized_structure.tcl','m002_route_failure_capture.tcl')}|{HERE.parent/'E006_lean_candidate/run_attribution_lean.py'})
    own=sorted(set(HERE.glob('*.py'))|set(HERE.glob('*.tcl'))|{HERE/'target_authority.json'})
    contract=ROOT/'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md'
    assert identity(contract)['sha256']=='1a9253d3d5acd9988f497410bbd132383dcddaad36f02456bccc293a55457e8f'
    original_target=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'
    assert original_target.read_bytes()==(HERE/'target_authority.json').read_bytes()
    manifest=dict(status='CPU_PREPARED_NOT_EXECUTED',EDA_executed=False,candidate_selected=None,
        own_sources=[identity(p) for p in own],reused_sources=[identity(p) for p in reused],contract=identity(contract),
        selector_reference=identity(HERE/'target_authority.json'),source_reuse_manifest=identity(HERE/'source_reuse_manifest.json'),
        CPU_checks=[identity(HERE/'bounded_CPU_admission_CT003.json')],documentation=[identity(HERE/'README.md')],
        original_target_authority=identity(original_target),
        validation=dict(Python_AST='PASS',Tcl_info_complete='PASS',native_APIs='NOT_RUN',actual_pre_place_membership='NOT_RUN',
                        native_resource_admissibility='NOT_RUN',geometry_readback='NOT_RUN',complete_cut='NOT_RUN'),
        current_EDA_unchanged=True,launch_dependencies=['actual closed and independently supported single C01/C02 selection from E006',
        'all prior registered PID/start closed and single EDA lock free', 'Root actual contract/source/selection/terminal/evidence binding',
        'actual E008 pre-place qualification, 144 frozen input and 175 constraint source identity checks'])
    (HERE/'prepared_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(manifest=identity(HERE/'prepared_manifest.json'),own_sources=len(own),reused_sources=len(reused),native_executed=False)))


if __name__=='__main__':main()
