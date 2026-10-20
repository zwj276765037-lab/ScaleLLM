from pathlib import Path
import datetime,json,os,shutil,subprocess,sys
root=Path.cwd();exp=root/'project/E011_m003_joint_routability_implementation';here=exp/'experiment_source/AT028_init_recovery';sys.path.insert(0,str(here));import native_init_recovery as r
at=exp/'experiment_results/runs/R002/attempts/AT032_cell_literal_OPT_POST_recovery';ev=at/'evidence';package=here/'recovery_package_AT032.json';value=r.verify(package)
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
regression=here/'affected_regression_AT032.log';assert 'Ran 17 tests' in regression.read_text() and regression.read_text().rstrip().endswith('OK')
receipt=dict(observed_utc=r.stage.now(),completed=True,new_EDA=False,qualification=r.old.file_id(ev/'actual_OPT_full_CLI_final_qualification.json'),
 regression=r.old.file_id(regression),test_methods=17,real_actual_reset_endpoint_count=51,canonical_cell_literals_decoded=17,
 membership_CLI_replay=r.old.file_id(replay/'restored_effective_membership_pass.json'),
 membership_replay_origin='projection of actual complete native OPT snapshot, not a new native restore; actual INIT restore replay correctly rejected 1 optimized-away C01 busy_INST_0 cell; new native same-OPT restore still required',
 package=r.old.file_id(package),launch_check_only=r.old.file_id(ev/'launch_check_only.log'),missing_POST_and_actual_debug_not_simulated=True,
 original_core48_unchanged=True,actual_OPT_native_tcl_code=0,AT031_outer_native_exit_code=1)
r.save(ev/'offline_actual_OPT_and_adapter_final_receipt.json',receipt)
report=r.HW/'vivado/reports/m003_E011_R002_AT032_cell_literal_OPT_POST_recovery';job='native_OPT_missing_POST_debug_preplace'
owned=[sys.executable,str(r.HW/'vivado/scripts/run_m003_owned.py'),'--attempt',str(at),'--job',job,'--report',str(report),'--',*launch]
run=dict(schema=1,id='AT032',experiment='E011',run='R002',title='cell_literal_OPT_POST_recovery',execution_state='planned',owner='A018',
 scope='Strict width1 binary cell flag normalization; full actual OPT CLI pass and affected real-data negatives before same opt.dcp restore; complete missing native POST, actual debug, strict preplace; no place.',
 command=owned,code_identity='Unchanged frozen core48 plus4 explicit experiment adapters; all original full reset functions/source/structure guards retained',input_identity=value['checkpoint'],evidence=[str(p.relative_to(root)) for p in [package,ev/'offline_actual_OPT_and_adapter_final_receipt.json',ev/'actual_OPT_full_CLI_final_qualification.json',regression]])
r.save(at/'run.json',run)
r.save(ev/'prepared_owned_command.json',dict(command=owned,report=str(report),job=job,offline_final_receipt=r.old.file_id(ev/'offline_actual_OPT_and_adapter_final_receipt.json')))
print(json.dumps(dict(offline_final_receipt=True,native_restore_pending=True,attempt='AT032',runtime_sources=len(archive),actual_OPT_checkpoint=value['checkpoint'])))
