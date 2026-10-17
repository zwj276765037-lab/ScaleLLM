#!/usr/bin/env python3
"""Freeze the same bounded alias-logging repair for an R006 retry and E008."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from directed_evidence import identity, save

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT/'agent/A006/directed_candidate_top_port_index'
PHYSICAL = ROOT/'agent/A006/E008_top_port_index_logging_fix/E008_entry'


def main():
    assert not (HERE/'prepared_source_manifest.json').exists()
    assert not (PHYSICAL/'prepared_manifest.json').exists()
    base = json.loads((BASE/'prepared_source_manifest.json').read_text())
    old_physical = json.loads((BASE/'E008_entry/prepared_manifest.json').read_text())
    for row in base['source_files'] + base['CPU_checks'] + old_physical['own_sources'] + old_physical['reused_sources']:
        assert identity(row['path']) == row
    changed = {'directed_exporter.tcl','run_directed_attribution.py','README.md','controlled_stop_R005.py'}
    for row in base['source_files']:
        if Path(row['path']).name not in changed:
            assert (HERE/Path(row['path']).name).read_bytes() == Path(row['path']).read_bytes()
    for row in old_physical['own_sources']:
        if Path(row['path']).name != 'directed_exporter.tcl':
            assert (PHYSICAL/Path(row['path']).name).read_bytes() == Path(row['path']).read_bytes()
    assert (HERE/'directed_exporter.tcl').read_bytes() == (PHYSICAL/'directed_exporter.tcl').read_bytes()
    mark = '    proc=None;tracked={};stop=None;peak=0;low_since=None'
    before, after = [(directory/'run_directed_attribution.py').read_text() for directory in [BASE,HERE]]
    assert before[before.index(mark):] == after[after.index(mark):]
    cpu = PHYSICAL/'CPU_checks/CT003_dual_logging/results.json'
    tested = json.loads(cpu.read_text())
    assert all(tested['checks'].values()) and len(tested['actual_cases']) == 6
    assert identity(tested['R006_shared_collector']['path']) == tested['R006_shared_collector']
    for row in tested['source_identities']:
        assert identity(row['path']) == row
    for directory in [HERE,PHYSICAL]:
        for path in directory.glob('*.py'):
            ast.parse(path.read_text(), filename=str(path))
    external = dict(base['external_inputs'])
    external.update(original_1425_preparation=identity(BASE/'prepared_source_manifest.json'),
                    original_dcc64_E008_preparation=identity(BASE/'E008_entry/prepared_manifest.json'))
    own = [Path(row['path']).name for row in base['source_files'] if Path(row['path']).name != 'controlled_stop_R005.py']
    own += ['controlled_stop_R006.py','freeze_buffered_preparation.py']
    repair = dict(kind='buffered_alias_observation_only', exact_redirected_event_sites=6,
                  preserved='All native queries/cache/coverage/index qualification/direction/timing; all actual ALIAS events and top-port native BEGIN/END',
                  lifecycle='EXCL per-point full-buffer sidecar; final close on mapping success/error; original native error code/options retained if logging also fails',
                  active_R006_unchanged=True, performance='New native speed not measured')
    retry = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), status='CPU_PREPARED_NOT_EXECUTED', EDA_executed=False,
                 exporter_protocol_complete=True, source_protocol_and_CPU_checks_complete=True, native_design_or_class_qualification=False,
                 coverage_version=base['coverage_version'], acquisition_mode=base['acquisition_mode'], acquisition_schema_version=base['acquisition_schema_version'],
                 runtime_source_names=base['runtime_source_names'], source_files=[identity(HERE/name) for name in own],
                 CPU_checks=base['CPU_checks']+[identity(cpu)], external_inputs=external, scope_revision=base['scope_revision'],
                 acquisition_revision=base['acquisition_revision'], repair=repair, original_preparation=identity(BASE/'prepared_source_manifest.json'),
                 native_index_qualification='Same complete native universe/adjacency/aliases/exhaustive reciprocity and fail-closed gates',
                 launch_dependencies=['Actual retry source/scope/acquisition binding','Actual current R006 AT002 and all previous E006 terminal/input/PID/start/lane closure'],
                 stop_permission='NOT_GRANTED_BY_PREPARATION; exact new user decision and current supervisor1377029/start931801943 required',
                 limitations=['Focused finite-graph normal/error logging lifecycle only; prior unchanged qualifications reused',
                              'No new native qualification, speed, candidate selection or physical success inferred'])
    save(HERE/'prepared_source_manifest.json', retry)
    reuse = dict(original_dcc64_manifest=identity(BASE/'E008_entry/prepared_manifest.json'),
                 buffered_R006_preparation=identity(HERE/'prepared_source_manifest.json'),
                 same_buffered_collector=True, base_contract=old_physical['contract'], scope_revision=old_physical['scope_revision'],
                 acquisition_revision=old_physical['acquisition_revision'], logging_repair=repair,
                 all_physical_policies_constraints_origin_and_acceptance_unchanged=True,
                 EDA_executed=False, candidate_selected=None)
    save(PHYSICAL/'source_reuse_manifest.json', reuse)
    physical = dict(old_physical)
    physical.update(recorded_utc=datetime.now(timezone.utc).isoformat(),
                    own_sources=[identity(PHYSICAL/Path(row['path']).name) for row in old_physical['own_sources']]+[identity(PHYSICAL/'check_logging_repair_CPU.py')],
                    source_reuse_manifest=identity(PHYSICAL/'source_reuse_manifest.json'),
                    selector_reference=identity(PHYSICAL/'target_authority.json'),
                    CPU_checks=old_physical['CPU_checks']+[identity(cpu)],
                    documentation=[identity(PHYSICAL/'README.md')],
                    shared_collector=identity(PHYSICAL/'directed_exporter.tcl'),
                    shared_validator=identity(PHYSICAL/'directed_evidence.py'),
                    original_preparation=identity(BASE/'E008_entry/prepared_manifest.json'), logging_repair=repair)
    save(PHYSICAL/'prepared_manifest.json', physical)
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), new_EDA_executed=False,
                  R006_prepared_manifest=identity(HERE/'prepared_source_manifest.json'),
                  E008_prepared_manifest=identity(PHYSICAL/'prepared_manifest.json'),
                  focused_actual_CPU=identity(cpu), stop_helper=identity(HERE/'controlled_stop_R006.py'))
    save(HERE/'paired_preparation_identity.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
