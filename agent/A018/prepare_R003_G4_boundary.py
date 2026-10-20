from pathlib import Path
import json,os,subprocess,sys
root=Path.cwd();exp=root/'project/E011_m003_joint_routability_implementation';at=exp/'experiment_results/runs/R003/attempts/AT001_fixed_complete_physical';ev=at/'evidence';run=json.loads((at/'run.json').read_text());args=run['command'];report=root/'project/hardware/vivado/reports/m003_E011_R003_AT001_G4_boundary_preparation'
assert not report.exists();env={**os.environ,'HAP_REPORT_DIR':str(report),'HAP_M003_ACTIVE':'1','HAP_CURRENT_ATTEMPT_DIR':str(at)}
with (ev/'pre_G4_exact_launcher_preparation.log').open('x') as f:proc=subprocess.run(args+['--prepare-only'],env=env,stdout=f,stderr=subprocess.STDOUT)
text=(ev/'pre_G4_exact_launcher_preparation.log').read_text();gate=root/'project/hardware/vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug/A007_G4_no_blocker.json'
sys.path.insert(0,str(exp/'experiment_source/physical_literal_adapter'));import physical_literal_adapter as a
if proc.returncode==0:
 boundary=report/'physical_adapter_native_boundary.json';value=json.loads(boundary.read_text());assert value['prepare_only'] is True and value['native_executed'] is False;state='actual_G4_passed_full_preparation_no_native';actual_gate=a.literal.old.file_id(gate);native_boundary=a.literal.old.file_id(boundary)
else:
 assert proc.returncode==1 and 'FileNotFoundError' in text and str(gate) in text and not (report/'physical_adapter_native_boundary.json').exists(),text[-3000:]
 state='original_actual_G4_gate_missing_rejected_before_native';actual_gate=None;native_boundary=None
assert not (report/'vivado.log').exists() and not (report/'launcher_status.json').exists()
receipt=dict(observed_utc=a.literal.stage.now(),completed=True,new_EDA=False,preparation_state=state,exit_code=proc.returncode,actual_G4_gate=actual_gate,native_boundary=native_boundary,original_launcher_unchanged=a.literal.old.file_id(a.HW/'vivado/scripts/run_m003_stage.py'),frozen_physical_v2_package=a.literal.old.file_id(exp/'experiment_source/physical_literal_adapter/dependency_package_v2.json'),report=str(report),source_archive=a.literal.old.file_id(report/'source_archive.json'),stage_inputs=a.literal.old.file_id(report/'stage_inputs.sha256'),no_dummy_gate_created=True,no_native_process_invoked=True,log=a.literal.old.file_id(ev/'pre_G4_exact_launcher_preparation.log'))
a.literal.save(ev/'pre_G4_exact_launcher_preparation_receipt.json',receipt);print(json.dumps(dict(completed=True,state=state,new_EDA=False)))
