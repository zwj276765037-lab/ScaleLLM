"""Real original G4 launcher -> exact successful place -> complete POST/physopt/route."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HW = ROOT / 'project/hardware'
sys.path.insert(0, str(HW / 'vivado/scripts'))
sys.path.insert(0, str(HERE.parent / 'AT028_init_recovery'))
import run_m003_stage as original
import native_init_recovery as literal
import state_equivalence as proof

SOURCES = [HERE / name for name in ['continue_successful_place.py', 'continue_successful_place.tcl',
           'runtime_state_collector.tcl', 'runtime_qualify.py', 'state_equivalence.py',
           'qualify_placed_sources.py', 'query.tcl', 'query_cached.tcl', 'targets.tcl']]
SOURCES.append(HERE.parent / 'AT028_init_recovery/native_init_recovery.py')

class Prepared(Exception):
    pass

def verify(path):
    package = json.loads(path.read_text())
    assert package['schema'] == 'M003_successful_place_full_POST_fixed_physopt_route_v1'
    for row in package['bindings']:
        assert proof.identity(row['path']) == row, ('continuation input changed', row['path'])
    assert {row['path'] for row in package['sources']} == {str(path) for path in SOURCES}
    for row in package['sources']:
        assert proof.identity(row['path']) == row
    literal.entry.check_sources()
    qualification = json.loads(Path(package['qualified_place_structure']['path']).read_text())
    assert qualification['passed'] is True and qualification['errors'] == [] and qualification['phase'] == 'place'
    assert qualification['original_full_function_evaluation_retained'] is True
    assert qualification['no_alias_expansion_or_source_renaming'] is True
    assert qualification['explicit_adapter'] == proof.identity(HERE / 'qualify_placed_sources.py')
    state = qualification['physical_state_equivalence']
    actual = proof.prove(Path(state['raw_native_source']['path']), Path(state['actual_snapshot']['path']),
                         Path(state['query_package']['path']))
    assert actual == state and actual['identity_bindings_verified'] is True
    assert actual['checkpoint'] == package['checkpoint']
    for row in package['inherited_place_files']:
        assert proof.identity(row['path']) == row
    command = Path(package['successful_place_command']['path']).read_text()
    assert 'native_tcl_code=0' in command and 'command=place_design -directive SSI_SpreadSLLs' in command
    parent = json.loads(Path(package['original_terminal']['path']).read_text())
    assert parent['native_exit_code'] == 1 and parent['stop_reason'] is None and parent['owned_survivors'] == {}
    assert package['fixed_commands'] == ['phys_opt_design -directive Default', 'route_design -directive Default']
    return package

class Boundary:
    def __init__(self, package_path, prepare_only):
        self.path, self.prepare_only = package_path, prepare_only

    def run(self, command, *, cwd, env):
        package = verify(self.path)
        report = Path(env['HAP_REPORT_DIR'])
        pre = Path(env['HAP_PRE_PLACE_REPORT_DIR'])
        assert env['HAP_STAGE'] == 'implement' and env['HAP_EXECUTION_MODE'] == 'checkpoint_restored_commands'
        expected = [original.VIVADO, '-mode', 'batch', '-notrace', '-source',
                    str(HW / 'vivado/scripts/m003_physical.tcl'), '-log', str(report / 'vivado.log'),
                    '-journal', str(report / 'vivado.jou')]
        assert command == expected and cwd == HW / 'vivado'
        preplace = json.loads((pre / 'M003_preplace_package.json').read_text())
        assert env['HAP_RECOVERY_CHECKPOINT'] == preplace['checkpoint']['path']
        inherited = []
        for row in package['inherited_place_files']:
            source = Path(row['path'])
            target = report / source.name
            assert not target.exists()
            shutil.copyfile(source, target)
            assert proof.identity(target)['sha256'] == row['sha256']
            inherited.append(dict(original=row, inherited=proof.identity(target), native_origin='R003/AT001'))
        literal.archive_extra(report, [*SOURCES, self.path,
                              *[Path(row['path']) for row in package['inherited_place_files']],
                              Path(package['qualified_place_structure']['path'])])
        literal.save(report / 'inherited_successful_place_provenance.json', dict(
            actual_new_place_executed=False, inherited_checkpoint=package['checkpoint'],
            successful_native_command=package['successful_place_command'],
            original_outer_native1_preserved=package['original_terminal'],
            inherited_prefix_reports_and_snapshot=inherited,
            accepted_current_structure=package['qualified_place_structure'],
            full_original_unfinished_POST_suffix_still_required=True))
        original_command = list(command)
        command[5] = str(HERE / 'continue_successful_place.tcl')
        env = {**env, 'HAP_RECOVERY_CHECKPOINT': package['checkpoint']['path'],
               'HAP_M003_CONTINUE_PLACE_PACKAGE': str(self.path)}
        literal.save(report / 'successful_place_continuation_native_boundary.json', dict(
            completed=True, prepare_only=self.prepare_only, native_executed=False,
            actual_original_G4_gate=proof.identity(pre / 'A007_G4_no_blocker.json'),
            actual_original_preplace=proof.identity(pre / 'M003_preplace_package.json'),
            package=proof.identity(self.path), actual_place_checkpoint=package['checkpoint'],
            original_command=original_command, adapted_command=command, changed_native_arguments=[5],
            original_G4_and_source_review_guards_executed=True,
            place_not_reexecuted=True, every_new_stage_requires_fresh_state_query=True,
            source_archive=proof.identity(report / 'source_archive.json'),
            stage_inputs=proof.identity(report / 'stage_inputs.sha256')))
        if self.prepare_only:
            raise Prepared()
        return subprocess.run(command, cwd=cwd, env=env)

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--archive-source', action='append', default=[])
    parser.add_argument('--prepare-only', action='store_true')
    args, rest = parser.parse_known_args()
    verify(args.package)
    expected = {row['path'] for row in literal.entry.check_sources()['sources']} | {str(path) for path in SOURCES}
    assert set(args.archive_source) == expected and len(args.archive_source) == len(expected)
    assert rest.count('--stage') == 1 and rest[rest.index('--stage') + 1] == 'implement'
    original.subprocess = Boundary(args.package.resolve(), args.prepare_only)
    saved = sys.argv
    sys.argv = [str(HW / 'vivado/scripts/run_m003_stage.py'), *rest]
    try:
        try:
            return original.main()
        except Prepared:
            print(json.dumps(dict(prepared=True, actual_original_G4_checked=True,
                                  native_executed=False, runtime_sources=len(expected))))
            return 0
    finally:
        sys.argv = saved

if __name__ == '__main__':
    raise SystemExit(main())
