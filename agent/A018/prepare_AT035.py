from pathlib import Path
import json,os,shutil,subprocess,sys
root=Path.cwd();here=root/'project/E011_m003_joint_routability_implementation/experiment_source/AT034_OPT_POST_requalification';sys.path.insert(0,str(here));import qualified_opt_evidence as e
r=e.r;at=r.ORIGIN.parent/'AT035_qualified_OPT_POST_to_actual_debug';ev=at/'evidence';package=here/'qualified_OPT_debug_dependency_package.json';value,qualified=e.verify(package)
for log,needle in [('current_binding_regression.log','Ran 4 tests'),('debug_continuation_regression.log','Ran 2 tests')]:
    text=(here/log).read_text();assert needle in text and text.rstrip().endswith('OK')
base=r.verify(Path(value['recovery_package']['path']));sources=sorted({row['path'] for row in base['sources']}|{row['path'] for row in r.entry.check_sources()['sources']}|{str(path) for path in e.SOURCES});assert len(sources)==56
launch=[sys.executable,str(here/'run_qualified_opt_debug.py'),'--dependency-package',str(package)]
for path in sources:launch+=['--archive-source',path]
staging=ev/'full_qualified_debug_launcher_preparation';env={**os.environ,'HAP_REPORT_DIR':str(staging),'HAP_M003_ACTIVE':'1','HAP_CURRENT_ATTEMPT_DIR':str(at)}
with (ev/'full_qualified_debug_launcher_preparation.log').open('x') as f:subprocess.run(launch+['--prepare-only'],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
boundary=json.loads((staging/'qualified_OPT_debug_native_boundary.json').read_text());assert boundary['completed'] is True and boundary['native_executed'] is False
# Exhaust remaining exclusive/absent families: OPT reuse never includes debug
# data; every full native debug/POST/preplace output has a fresh namespace.
newnames=['m003_candidate_registration.json','native_synthesis_run_metadata.json','restored_effective_membership_pass.json','xdc_registry_opt.tsv','embedded_xdc_registry_opt.tsv','qualified_OPT_restore_binding.json','drc_OPT_restore_live.rpt','debug_materialization_condition.txt','debug_materialization_command_result.txt','debug_materialized.dcp','debug_materialized_result.txt','xdc_registry_debug_materialized.tsv','actual_xdc_reads_debug_materialized.json','constraints_debug_materialized.json','effective_pblock_membership_debug_materialized.json','probe_targets_debug_materialized.json','probe_targets_debug_materialized.tcl','m003_qualification_debug_materialized.json','m003_native_debug_materialized.json','m003_stream_debug_materialized_*.jsonl','m003_connection_debug_materialized_*.jsonl','reset_graph_debug_materialized.tsv','cdc_changed_reset_debug_materialized.tsv','bram_port_clocks_debug_materialized.tsv','integrity_debug_materialized.json','admission_debug_materialized.txt','pre_place_evidence.json','M003_preplace_package.json']
assert all(not list(staging.glob(name)) for name in newnames)
# Replay only real AT034 restore observations on separate, labelled CPU fixtures.
# No new native observation or phase success is fabricated.
replays=[]
for mutation in ['positive','wrong_scope','nonzero_apply','wrong_membership','missing_embedded']:
    target=ev/('current_OPT_restore_'+mutation);target.mkdir()
    inherited_names=['restored_effective_membership_pass.json','restore_apply_attempts.json','xdc_registry_opt.tsv','embedded_xdc_registry_opt.tsv']
    for name in inherited_names:shutil.copyfile(e.q.ACTUAL/name,target/name)
    for name in ['constraints_opt.json','admission_opt.txt']:shutil.copyfile(staging/name,target/name)
    origin=dict(native_observation_origin='AT034 real same-OPT restore copied for CPU replay',new_native_observation=False,inputs=[r.old.artifact_id(e.q.ACTUAL/name) for name in inherited_names]);r.save(target/'offline_actual_restore_origin.json',origin)
    if mutation=='wrong_scope':
        p=target/'xdc_registry_opt.tsv';lines=p.read_text().splitlines();changed=[]
        for line in lines:
            fields=line.split('\t')
            if fields[0]==str(r.OVERLAY):fields[6]='foreign_scope';line='\t'.join(fields)
            changed.append(line)
        p.write_text('\n'.join(changed)+'\n')
    if mutation=='nonzero_apply':(target/'restore_apply_attempts.json').write_text(json.dumps(dict(before='0',after='1',delta='1')))
    if mutation=='wrong_membership':
        p=target/'restored_effective_membership_pass.json';x=json.loads(p.read_text());x['selected_cells']=22851;p.write_text(json.dumps(x))
    if mutation=='missing_embedded':(target/'embedded_xdc_registry_opt.tsv').unlink()
    args=[sys.executable,str(here/'qualified_opt_evidence.py'),'--dependency-package',str(package),'--report',str(target),'--offline-replay']
    with (target/'CLI.log').open('x') as f:result=subprocess.run(args,env={**env,'HAP_REPORT_DIR':str(target),'HAP_EXECUTION_MODE':'checkpoint_restored_commands','HAP_M003_QUALIFIED_OPT_SNAPSHOT':base['reuse_opt']['input_snapshot']['path']},stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==(0 if mutation=='positive' else 1),(mutation,(target/'CLI.log').read_text())
    if mutation=='positive':assert json.loads((target/'qualified_OPT_restore_binding.json').read_text())['offline_replay'] is True
    else:assert not (target/'qualified_OPT_restore_binding.json').exists()
    replays.append(dict(mutation=mutation,exit_code=result.returncode,new_native_observation=False,log=r.old.file_id(target/'CLI.log')))
receipt=dict(completed=True,new_EDA=False,dependency_package=r.old.file_id(package),qualified_actual_OPT_POST=value['qualified_OPT_POST'],full_launcher_boundary=r.old.file_id(staging/'qualified_OPT_debug_native_boundary.json'),fresh_native_output_targets=newnames,all_fresh_targets_absent=True,actual_AT034_restore_CPU_replays=replays,source_tests=[r.old.file_id(here/name) for name in ['current_binding_regression.log','debug_continuation_regression.log']],runtime_sources=56,actual_debug_still_required=True,OPT_or_full_POST_reexecuted=False,formal_reset_cdc_safety='OPEN')
r.save(ev/'complete_actual_OPT_to_debug_prelaunch_receipt.json',receipt)
report=r.HW/'vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug';job='native_qualified_OPT_to_actual_debug_preplace';owned=[sys.executable,str(r.HW/'vivado/scripts/run_m003_owned.py'),'--attempt',str(at),'--job',job,'--report',str(report),'--',*launch]
run=dict(schema=1,id='AT035',experiment='E011',run='R002',title='qualified_OPT_POST_to_actual_debug',execution_state='planned',owner='A018',scope='Strictly same actual OPT restored constraints/zeroapply; inherit full original OPT admission qualified on real AT034 data; actual native conditional debug and complete fresh debug POST/preplace, no repeated OPT/OPT snapshot/OPT POST',command=owned,code_identity='core48+4 unchanged recovery sources+4 explicit OPT-only continuation sources; actual debug suffix unchanged; current-stage debug evidence mandatory',input_identity=qualified['checkpoint'],evidence=[str(path.relative_to(root)) for path in [package,ev/'complete_actual_OPT_to_debug_prelaunch_receipt.json',Path(value['qualified_OPT_POST']['path'])]])
r.save(at/'run.json',run);r.save(ev/'prepared_owned_command.json',dict(command=owned,report=str(report),job=job,prelaunch_receipt=r.old.file_id(ev/'complete_actual_OPT_to_debug_prelaunch_receipt.json')));print(json.dumps(dict(ready=True,runtime_sources=56,actual_debug_not_yet_started=True,namespace_targets=len(newnames),restore_replay_exit_codes=[row['exit_code'] for row in replays])))
