#!/usr/bin/env python3
"""Freeze E008 matching acquisition source, preserving the accepted physical flow."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from directed_evidence import identity, save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT/'agent/A006/directed_candidate_cut_system_python/E008_entry'


def main():
    output = HERE/'prepared_manifest.json'
    assert not output.exists()
    base = json.loads((BASE/'prepared_manifest.json').read_text())
    for row in base['own_sources'] + base['reused_sources']:
        assert identity(row['path']) == row
    for name in ['candidate_hooks.tcl', 'runtime_hooks.tcl', 'property_alignment.tcl', 'implementation.tcl', 'system_python.tcl', 'target_authority.json', 'launch_detached.py']:
        assert (HERE/name).read_bytes() == (BASE/name).read_bytes(), 'Physical or protection entry changed'
    for name in ['directed_exporter.tcl', 'directed_evidence.py', 'top_port_index.tcl', 'top_port_evidence.py']:
        assert (HERE/name).read_bytes() == (HERE.parent/name).read_bytes()
    cpu = HERE/'CPU_checks/CT005_index_phase/results.json'
    result = json.loads(cpu.read_text())
    assert all(result['checks'].values()) and len(result['replays']) == 32
    for row in result['sources']:
        assert identity(row['path']) == row
    acquisition = ROOT/'mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md'
    shared = HERE.parent/'prepared_source_manifest.json'
    reuse = dict(original_da34_manifest=identity(BASE/'prepared_manifest.json'), shared_R006_manifest=identity(shared),
                 base_contract=base['contract'], scope_revision=base['scope_revision'], acquisition_revision=identity(acquisition),
                 same_shared_acquisition_sources=True, EDA_executed=False, candidate_selected=None,
                 physical_qualification='Accepted da34 physical/control pipeline and global acceptance retained',
                 actual_P_projection='Same-phase original literal RAW/S plus actual native-origin P; complete index/native receipts included')
    save(HERE/'source_reuse_manifest.json', reuse)
    own = [Path(row['path']).name for row in base['own_sources']]
    own += ['top_port_index.tcl', 'top_port_evidence.py', 'check_index_phase_CPU.py', 'freeze_index_preparation.py']
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    value = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), status='CPU_PREPARED_NOT_EXECUTED', EDA_executed=False,
                 candidate_selected=None, coverage_version='candidate_directed_cut_v1', acquisition_mode='NATIVE_PORT_REVERSE_INDEX_V1',
                 acquisition_schema_version='top_port_reverse_index_v1', own_sources=[identity(HERE/name) for name in own],
                 reused_sources=base['reused_sources'], contract=base['contract'], scope_revision=base['scope_revision'],
                 acquisition_revision=identity(acquisition), selector_reference=identity(HERE/'target_authority.json'),
                 original_target_authority=base['original_target_authority'], source_reuse_manifest=identity(HERE/'source_reuse_manifest.json'),
                 CPU_checks=[identity(cpu), identity(HERE.parent/'CPU_checks/CT004_full_combination/results.json'),
                             identity(HERE.parent/'CPU_checks/CT006_system_python_entry.json')],
                 runtime_dependencies=base['runtime_dependencies'], documentation=[identity(HERE/'README.md')],
                 shared_collector=identity(HERE/'directed_exporter.tcl'), shared_validator=identity(HERE/'directed_evidence.py'),
                 validation=dict(actual_collector_phase_projection_CPU='32 passed', native_port_index='NOT_RUN',
                                 actual_pre_place_membership='NOT_RUN', migration_policy_and_resource_qualification='NOT_RUN',
                                 place_physopt_route='NOT_RUN', physical_signoff=False),
                 launch_dependencies=['Actual supported single ID/root and E006 terminal evidence', 'All E006 PID/start owners and EDA lock closed',
                                      'Actual Root base_contract/scope_revision/acquisition_revision/preparation_manifest binding',
                                      'Original native pre-place/80 protections/policy/resource/origin gates', 'Fresh per-phase complete native port-index qualification',
                                      'Complete place/physopt/route and global formal timing/CDC/reset/IO/DRC acceptance'])
    save(output, value)
    print(json.dumps(identity(output)))


if __name__ == '__main__':
    main()
