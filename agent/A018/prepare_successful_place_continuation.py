"""Freeze actual place/proof lineage and the complete fixed continuation candidate."""
from pathlib import Path
import json
import sys

root = Path.cwd()
exp = root / 'project/E011_m003_joint_routability_implementation'
here = exp / 'experiment_source/place_write_replica_proof'
sys.path.insert(0, str(here))
import continue_successful_place as continuation

report = root / 'project/hardware/vivado/reports/m003_E011_R003_AT001_fixed_complete_physical'
origin = exp / 'experiment_results/runs/R003/attempts/AT001_fixed_complete_physical'
proof_attempt = exp / 'experiment_results/runs/R003/attempts/AT004_cached_place_write_replica_proof'
evidence = proof_attempt / 'evidence'
qualification = evidence / 'actual_complete_place_structure_requalified.json'
negative = json.loads((evidence / 'actual_full_CLI_negative_receipt.json').read_text())
assert negative['passed'] is True and len(negative['cases']) == 8
assert all(row['exit_code'] == 1 and row['rejected'] is True for row in negative['cases'])
assert sum(row['full_original_validator_reached'] for row in negative['cases']) == 3
status = json.loads((evidence / 'jobs/native_bounded_place_write_replica_query/status.json').read_text())
assert status['native_exit_code'] == 0 and status['stop_reason'] is None and status['owned_survivors'] == {}
inherited = [path for path in sorted(report.iterdir()) if path.is_file() and 'place' in path.name
             and path.name != 'm003_qualification_place.json' and '_error_info' not in path.name]
assert report / 'place.dcp' in inherited and report / 'm003_native_place.json' in inherited
preplace = root / 'project/hardware/vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug'
package = dict(schema='M003_successful_place_full_POST_fixed_physopt_route_v1',
               checkpoint=continuation.proof.identity(report / 'place.dcp'),
               qualified_place_structure=continuation.proof.identity(qualification),
               successful_place_command=continuation.proof.identity(report / 'place_command_result.txt'),
               original_terminal=continuation.proof.identity(origin / 'evidence/jobs/native_fixed_complete_physical/status.json'),
               selection_package=continuation.proof.identity(here / 'query_package_AT004_cached.json'),
               inherited_place_files=[continuation.proof.identity(path) for path in inherited],
               sources=[continuation.proof.identity(path) for path in continuation.SOURCES],
               fixed_commands=['phys_opt_design -directive Default', 'route_design -directive Default'],
               no_place_reexecution=True, no_old_failed_qualification_overwrite=True,
               every_new_stage_requires_actual_current_state_query=True,
               formal_safety_and_final_timing='OPEN')
paths = set(continuation.SOURCES + inherited + [qualification,
    evidence / 'actual_same_state_equivalence.json', evidence / 'actual_full_CLI_negative_receipt.json',
    evidence / 'owner_terminal_and_source_closure.json', evidence / 'jobs/native_bounded_place_write_replica_query/status.json',
    here / 'query_package_AT004_cached.json',
    root / 'project/hardware/vivado/reports/m003_E011_R003_AT004_cached_place_write_replica_proof/selected_state_and_root_pins.jsonl',
    report / 'm003_qualification_place.json',
    Path(package['original_terminal']['path']), origin / 'evidence/owner_terminal_and_source_closure.json',
    preplace / 'M003_preplace_package.json', preplace / 'A007_G4_no_blocker.json',
    continuation.literal.entry.MANIFEST])
package['bindings'] = [continuation.proof.identity(path) for path in sorted(paths)]
package_path = here / 'place_continuation_package.json'
continuation.literal.save(package_path, package)
continuation.verify(package_path)
sources = sorted({row['path'] for row in continuation.literal.entry.check_sources()['sources']} |
                 {str(path) for path in continuation.SOURCES})
assert len(sources) == 58
at = exp / 'experiment_results/runs/R003/attempts/AT005_successful_place_POST_physopt_route'
native_report = root / 'project/hardware/vivado/reports/m003_E011_R003_AT005_successful_place_POST_physopt_route'
assert not native_report.exists()
inner = [sys.executable, str(here / 'continue_successful_place.py'), '--package', str(package_path)]
for source in sources:
    inner += ['--archive-source', source]
inner += ['--stage', 'implement', '--project', str(root / 'project/hardware/vivado/project/scalellm_m003_E011_R002_AT002'),
          '--synth-report', str(root / 'project/hardware/vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery'),
          '--synth-attempt', str(exp / 'experiment_results/runs/R002/attempts/AT027_reset_semantics_postreport_recovery'),
          '--preplace-report', str(preplace)]
owned = [sys.executable, str(continuation.HW / 'vivado/scripts/run_m003_owned.py'),
         '--attempt', str(at), '--job', 'native_successful_place_POST_physopt_route',
         '--report', str(native_report), '--', *inner]
registration = dict(execution_state='planned', owner='A018',
    scope='Actual original G4 -> restore exact successful AT001 place.dcp with zeroapply/full structure -> inherit completed place prefix reports -> all original unfinished place POST -> fixed physopt Default/route Default, with actual fresh 12FF state proof every new phase; no new place',
    command=owned, code_identity=continuation.proof.identity(package_path), input_identity=package['checkpoint'],
    evidence=[str(path.relative_to(root)) for path in [qualification, evidence / 'actual_full_CLI_negative_receipt.json',
              here / 'place_continuation_CPU_preservation.log', here / 'runtime_collector_CPU_integration.log']])
continuation.literal.save(here / 'AT005_registration.json', registration)
print(json.dumps(dict(candidate_ready=True, runtime_sources=58, inherited_place_files=len(inherited),
                      package=continuation.proof.identity(package_path), actual_EDA_started=False)))
