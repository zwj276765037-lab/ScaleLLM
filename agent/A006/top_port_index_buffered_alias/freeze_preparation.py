#!/usr/bin/env python3
"""Freeze a distinct same-coverage R006 acquisition package without EDA."""
from datetime import datetime, timezone
import json
from pathlib import Path
import ast
from directed_evidence import identity, save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE.parent / 'directed_candidate_cut_system_python'


def main():
    target = HERE / 'prepared_source_manifest.json'
    assert not target.exists()
    old = json.loads((BASE/'prepared_source_manifest.json').read_text())
    for row in old['source_files'] + old['CPU_checks']:
        assert identity(row['path']) == row
    names = [name for name in old['runtime_source_names'] if name != 'controlled_stop_R004.py'] + ['top_port_index.tcl', 'top_port_evidence.py']
    for name in ['candidate_inspector.tcl', 'property_alignment.tcl', 'targets.tcl', 'reuse_manifest.json', 'system_python.tcl', 'attribution_directed.tcl']:
        assert (HERE/name).read_bytes() == (BASE/name).read_bytes()
    tail = '    proc=None;tracked={};stop=None;peak=0;low_since=None'
    before, after = [(path/'run_directed_attribution.py').read_text() for path in [BASE, HERE]]
    assert before[before.index(tail):] == after[after.index(tail):]
    cpu_paths = [HERE/'CPU_checks/CT004_full_combination/results.json', HERE/'CPU_checks/CT005_control_membership.json', HERE/'CPU_checks/CT006_system_python_entry.json']
    combined, control, runtime = [json.loads(path.read_text()) for path in cpu_paths]
    assert len(combined['actual_collector_positive_cases']) == 16 and len(combined['mutation_cases']) == 16
    assert all(case['rejected'] for case in combined['mutation_cases'])
    assert all(control['checks'].values()) and all(runtime['checks'].values())
    for row in combined['sources']:
        assert identity(row['path']) == row, 'Checked source changed before freeze'
    acquisition = ROOT/'mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md'
    spec = ROOT/'agent/A007/top_port_projection_semantics_20261017/minimal_native_qualification.md'
    spec_json = spec.with_suffix('.json')
    external = dict(old['external_inputs'])
    external.update(original_b330_manifest=identity(BASE/'prepared_source_manifest.json'),
                    original_da34_manifest=identity(BASE/'E008_entry/prepared_manifest.json'),
                    acquisition_revision=identity(acquisition), native_index_specification=identity(spec),
                    native_index_machine_constraints=identity(spec_json))
    own_names = sorted(set(names + [path.name for path in HERE.glob('*.py')] + ['README.md', 'check_native_index_mock.tcl', 'check_native_index_phase_mock.tcl', 'check_timing_index_mock.tcl']))
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    value = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), status='CPU_PREPARED_NOT_EXECUTED', EDA_executed=False,
                 exporter_protocol_complete=True, source_protocol_and_CPU_checks_complete=True, native_design_or_class_qualification=False,
                 coverage_version='candidate_directed_cut_v1', acquisition_mode='NATIVE_PORT_REVERSE_INDEX_V1', acquisition_schema_version='top_port_reverse_index_v1',
                 runtime_source_names=names, source_files=[identity(HERE/name) for name in own_names],
                 CPU_checks=[identity(path) for path in cpu_paths] + old['CPU_checks'], external_inputs=external,
                 scope_revision=old['scope_revision'], acquisition_revision=identity(acquisition),
                 original_package_unchanged=identity(BASE/'prepared_source_manifest.json'),
                 control_tail='Byte-identical process/resource/post-integrity tail to b330 and original R004',
                 native_index_qualification='Complete unfiltered universe, all per-port adjacency, complete aliases, exhaustive per-port-group native reciprocity; reject incomplete stage',
                 actual_native_calls='BEGIN/END plus complete native command/result/code/options ledger; pure JOIN has no native_tcl_code',
                 launch_dependencies=['Actual source/scope/acquisition execution binding', 'Current R005 AT003 actual terminal and input/PID/start/lane closure',
                                      'All historical E006 owners closed, nonblocking single EDA lock', 'Actual system-Python preflight and fresh member/class/role/index qualification'],
                 stop_policy='No current stop permission; separately bound real new user decision required for exact current supervisor-only pidfd notice',
                 limitations=['CPU finite native mocks and actual previous member replay only', 'New native qualification and speed not measured',
                              'No selected candidate or implementation success inferred'])
    save(target, value)
    print(json.dumps(identity(target)))


if __name__ == '__main__':
    main()
