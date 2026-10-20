from pathlib import Path
import datetime,json,os,shutil,subprocess,sys
root=Path.cwd();exp=root/'project/E011_m003_joint_routability_implementation';here=exp/'experiment_source/AT028_init_recovery';sys.path.insert(0,str(here));import native_init_recovery as r
at=exp/'experiment_results/runs/R002/attempts/AT034_OPT_fresh_registry_selection';ev=at/'evidence';package=here/'recovery_package_AT034.json';value=r.verify(package)
replay=ev/'actual_OPT_snapshot_projection_CLI_replay';replay.mkdir();parent=r.HW/'vivado/reports/m003_E011_R002_AT031_verified_restore_parser_to_OPT'
snapshot=json.loads((parent/'m003_native_opt.json').read_text())
records=[dict(kind='cell',NAME=row['NAME'],PBLOCKS=row['PBLOCKS']) for row in snapshot['cells'] if row['role']!='core_address']+[dict(row,kind='pblock') for row in snapshot['pblocks']]
(replay/'restored_effective_membership.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in records))
shutil.copyfile(parent/'restore_apply_attempts.json',replay/'restore_apply_attempts.json')
env={**os.environ,'HAP_M003_INIT_RECOVERY_PACKAGE':str(package)}
cmd=[sys.executable,str(here/'native_init_recovery.py'),'restore-proof','opt',str(replay)]
with (ev/'actual_OPT_snapshot_projection_CLI_replay.log').open('x') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
archive=sorted({row['path'] for row in value['sources']}|{row['path'] for row in r.entry.check_sources()['sources']})
launch=[sys.executable,str(here/'launch.py'),'--package',str(package)]
for path in archive:launch+=['--archive-source',path]
with (ev/'launch_check_only.log').open('x') as f:subprocess.run(launch+['--check-only'],stdout=f,stderr=subprocess.STDOUT,check=True)
staging=ev/'full_launcher_preparation_replay'
with (ev/'full_launcher_preparation_replay.log').open('x') as f:subprocess.run(launch+['--prepare-only'],env={**env,'HAP_REPORT_DIR':str(staging),'HAP_M003_ACTIVE':'1'},stdout=f,stderr=subprocess.STDOUT,check=True)
prepared=json.loads((staging/'native_launch_preparation.json').read_text());assert prepared['completed'] is True and prepared['native_executed'] is False and prepared['exact_native_call_boundary'] is True
# Real-data negative: explicitly reinsert the immutable old parent into inherited
# artifacts. The exact same preparation must reject EXCL, preserving its bytes.
mutated=json.loads(package.read_text());old_parent=parent/'M003_init_recovery_parent.json';mutated['reuse_opt']['artifacts'].append(r.old.file_id(old_parent))
negative_package=ev/'negative_old_parent_selection_package.json';r.save(negative_package,mutated)
negative_launch=[*launch];negative_launch[negative_launch.index('--package')+1]=str(negative_package)
negative_stage=ev/'negative_old_parent_selection_replay'
with (ev/'negative_old_parent_selection_replay.log').open('x') as f:negative=subprocess.run(negative_launch+['--prepare-only'],env={**env,'HAP_REPORT_DIR':str(negative_stage),'HAP_M003_ACTIVE':'1'},stdout=f,stderr=subprocess.STDOUT)
assert negative.returncode==1 and 'FileExistsError' in (ev/'negative_old_parent_selection_replay.log').read_text()
assert r.old.sha256(negative_stage/'M003_init_recovery_parent.json')==r.old.sha256(old_parent) and not (negative_stage/'native_launch_preparation.json').exists()
r.save(ev/'old_new_parent_selection_regression.json',dict(positive_full_boundary=r.old.file_id(staging/'native_launch_preparation.json'),negative_old_parent_rejected=True,negative_exit_code=negative.returncode,old_parent_bytes_preserved=True,native_executed=False,EXCL_retained=True,negative_log=r.old.file_id(ev/'negative_old_parent_selection_replay.log')))
# Execute the exact original restored-registry Tcl function on actual files.
# Native queries alone are empty stubs: this is a filesystem-preparation test,
# not native constraint evidence or an EDA run.
registry_receipts=[]
for kind in ['fresh_selection_positive','existing_opt_registry_negative']:
    dest=ev/kind;dest.mkdir();shutil.copyfile(parent/'xdc_registry_project.tsv',dest/'xdc_registry_project.tsv')
    if kind.endswith('negative'):shutil.copyfile(parent/'xdc_registry_opt.tsv',dest/'xdc_registry_opt.tsv')
    tcl='set ::env(HAP_REPORT_DIR) {'+str(dest)+'}\nset ::env(HAP_EXECUTION_MODE) checkpoint_restored_commands\nsource {'+str(r.HW/'vivado/scripts/m002_diagnostic_common.tcl')+'}\n'
    tcl+='proc m002_registered_constraints {} {return {}}\nproc m002_debug_source_ips {} {return {}}\nproc report_compile_order {args} {return {offline_filesystem_test_only}}\n'
    tcl+='if {[catch {m002_dump_xdc opt} msg]} {puts stderr $msg;exit 1}\nputs {original_Tcl_EXCL_copy_completed}\n'
    check=subprocess.run(['tclsh'],input=tcl,text=True,capture_output=True)
    (dest/'stdout.log').write_text(check.stdout);(dest/'stderr.log').write_text(check.stderr)
    if kind.endswith('positive'):assert check.returncode==0 and r.old.sha256(dest/'xdc_registry_opt.tsv')==r.old.sha256(dest/'xdc_registry_project.tsv')
    else:assert check.returncode==1 and 'file already exists' in check.stderr and r.old.sha256(dest/'xdc_registry_opt.tsv')==r.old.sha256(parent/'xdc_registry_opt.tsv')
    registry_receipts.append(dict(kind=kind,exit_code=check.returncode,exact_original_Tcl=True,native_queries_stubbed=True,native_execution=False,stderr=r.old.artifact_id(dest/'stderr.log')))
r.save(ev/'original_Tcl_registry_selection_regression.json',dict(completed=True,results=registry_receipts,runtime_code_unchanged=True,excluded_fresh_registry_count=1,actual_native_registry_still_required=True))
regression=here/'affected_regression_AT033.log';assert 'Ran 17 tests' in regression.read_text() and regression.read_text().rstrip().endswith('OK')
receipt=dict(registry_selection_regression=r.old.file_id(ev/'original_Tcl_registry_selection_regression.json'),full_launcher_preparation=r.old.file_id(staging/'native_launch_preparation.json'),old_new_parent_regression=r.old.file_id(ev/'old_new_parent_selection_regression.json'),observed_utc=r.stage.now(),completed=True,new_EDA=False,qualification=r.old.file_id(ev/'actual_OPT_full_CLI_final_qualification.json'),
 regression=r.old.file_id(regression),test_methods=17,semantic_suite_reused_no_runtime_code_change=True,real_actual_reset_endpoint_count=51,canonical_cell_literals_decoded=17,
 membership_CLI_replay=r.old.file_id(replay/'restored_effective_membership_pass.json'),
 membership_replay_origin='projection of actual complete native OPT snapshot, not a new native restore; actual INIT restore replay correctly rejected 1 optimized-away C01 busy_INST_0 cell; new native same-OPT restore still required',
 package=r.old.file_id(package),launch_check_only=r.old.file_id(ev/'launch_check_only.log'),missing_POST_and_actual_debug_not_simulated=True,
 original_core48_unchanged=True,actual_OPT_native_tcl_code=0,AT031_outer_native_exit_code=1)
r.save(ev/'offline_actual_OPT_and_adapter_final_receipt.json',receipt)
report=r.HW/'vivado/reports/m003_E011_R002_AT034_OPT_fresh_registry_selection';job='native_OPT_missing_POST_debug_preplace'
owned=[sys.executable,str(r.HW/'vivado/scripts/run_m003_owned.py'),'--attempt',str(at),'--job',job,'--report',str(report),'--',*launch]
run=dict(schema=1,id='AT034',experiment='E011',run='R002',title='OPT_fresh_registry_selection',execution_state='planned',owner='A018',
 scope='Strict width1 binary cell flag normalization; full actual OPT CLI pass and affected real-data negatives before same opt.dcp restore; complete missing native POST, actual debug, strict preplace; no place.',
 command=owned,code_identity='Unchanged frozen core48 plus4 explicit experiment adapters; all original full reset functions/source/structure guards retained',input_identity=value['checkpoint'],evidence=[str(p.relative_to(root)) for p in [package,ev/'offline_actual_OPT_and_adapter_final_receipt.json',ev/'actual_OPT_full_CLI_final_qualification.json',regression]])
r.save(at/'run.json',run)
r.save(ev/'prepared_owned_command.json',dict(command=owned,report=str(report),job=job,offline_final_receipt=r.old.file_id(ev/'offline_actual_OPT_and_adapter_final_receipt.json')))
print(json.dumps(dict(offline_final_receipt=True,native_restore_pending=True,attempt='AT034',runtime_sources=len(archive),actual_OPT_checkpoint=value['checkpoint'])))
