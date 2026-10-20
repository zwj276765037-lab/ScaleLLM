"""Prepare the frozen full physical launcher through its genuine G4 boundary."""
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path.cwd()
exp = root / 'project/E011_m003_joint_routability_implementation'
at = exp / 'experiment_results/runs/R003/attempts/AT001_fixed_complete_physical'
ev = at / 'evidence'
run = json.loads((at / 'run.json').read_text())
inner = run['command']
assert Path(inner[1]).name == 'physical_literal_adapter.py'
sys.path.insert(0, str(exp / 'experiment_source/physical_literal_adapter'))
import physical_literal_adapter as adapter

pre = root / 'project/hardware/vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug'
gate = pre / 'A007_G4_no_blocker.json'
assert gate.is_file(), 'Real independent A007 G4 must exist before this preparation'
package = exp / 'experiment_source/physical_literal_adapter/dependency_package_v2.json'
adapter.verify(package)
report = root / 'project/hardware/vivado/reports/m003_E011_R003_AT001_actual_G4_full_preparation'
assert not report.exists()
env = {**os.environ, 'HAP_REPORT_DIR': str(report), 'HAP_M003_ACTIVE': '1',
       'HAP_CURRENT_ATTEMPT_DIR': str(at)}
with (ev / 'actual_G4_full_launcher_preparation.log').open('x') as stream:
    subprocess.run(inner + ['--prepare-only'], env=env, stdout=stream,
                   stderr=subprocess.STDOUT, check=True)
boundary_path = report / 'physical_adapter_native_boundary.json'
boundary = json.loads(boundary_path.read_text())
assert boundary['completed'] is True and boundary['prepare_only'] is True
assert boundary['native_executed'] is False
assert boundary['all_original_G4_checks_retained'] is True
assert boundary['changed_native_arguments'] == [5]
assert boundary['actual_G4_gate'] == adapter.literal.old.file_id(gate)
assert boundary['preplace'] == adapter.literal.old.file_id(pre / 'M003_preplace_package.json')
for name in ['vivado.log', 'launcher_status.json', 'placed.dcp', 'physopt.dcp', 'routed.dcp']:
    assert not (report / name).exists()

receipt = dict(completed=True, observed_utc=adapter.literal.stage.now(), new_EDA=False,
               actual_G4_checked_by_unmodified_launcher=True,
               preparation_state='actual_G4_passed_full_preparation_no_native',
               native_boundary=adapter.literal.old.file_id(boundary_path),
               actual_G4_gate=adapter.literal.old.file_id(gate),
               actual_source_review=boundary['actual_source_review'],
               preplace=boundary['preplace'], checkpoint=boundary['checkpoint'],
               source_archive=boundary['source_archive'], stage_inputs=boundary['stage_inputs'],
               archive_bindings=boundary['archive_bindings'],
               frozen_physical_v2_package=adapter.literal.old.file_id(package),
               runtime_sources=51, no_dummy_gate_created=True,
               no_native_process_invoked=True,
               log=adapter.literal.old.file_id(ev / 'actual_G4_full_launcher_preparation.log'))
adapter.literal.save(ev / 'actual_G4_full_launcher_preparation_receipt.json', receipt)

actual_report = root / 'project/hardware/vivado/reports/m003_E011_R003_AT001_fixed_complete_physical'
assert not actual_report.exists()
job = 'native_fixed_complete_physical'
owned = [sys.executable, str(adapter.HW / 'vivado/scripts/run_m003_owned.py'),
         '--attempt', str(at), '--job', job, '--report', str(actual_report), '--', *inner]
adapter.literal.save(ev / 'planned_inner_run_before_owned_wrapper.json', run)
run['command'] = owned
run.setdefault('evidence', []).append(str((ev / 'actual_G4_full_launcher_preparation_receipt.json').relative_to(root)))
(at / 'run.json').write_text(json.dumps(run, indent=2) + '\n')
adapter.literal.save(ev / 'prepared_owned_command.json', dict(
    command=owned, report=str(actual_report), job=job,
    actual_G4_gate=receipt['actual_G4_gate'],
    prelaunch_receipt=adapter.literal.old.file_id(ev / 'actual_G4_full_launcher_preparation_receipt.json')))
print(json.dumps(dict(ready=True, new_EDA=False, actual_G4_checked=True,
                      runtime_sources=51, archive_bindings=boundary['archive_bindings'])))
