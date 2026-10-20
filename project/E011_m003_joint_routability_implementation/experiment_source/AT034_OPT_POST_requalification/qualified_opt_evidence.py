"""Strictly OPT-only inherited admission; debug must produce its own complete facts."""
from pathlib import Path
import argparse,json,os,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import qualify_actual_OPT_POST as q
r=q.r
SOURCES=[HERE/name for name in ('run_qualified_opt_debug.py','qualified_opt_debug.tcl','qualified_opt_evidence.py','qualify_actual_OPT_POST.py')]
def verify(package):
    value=json.loads(package.read_text());r.old.require(value['schema']=='M003_qualified_actual_OPT_to_debug_v1','foreign phase-qualified continuation package')
    for row in [value['recovery_package'],value['qualified_OPT_POST'],*value['sources']]:r.old.verify_identity(row)
    r.old.require({row['path'] for row in value['sources']}=={str(p) for p in SOURCES},'missing/hidden continuation source')
    recovered=r.verify(Path(value['recovery_package']['path']));receipt=json.loads(Path(value['qualified_OPT_POST']['path']).read_text())
    r.old.require(receipt['schema']=='M003_actual_AT034_OPT_POST_requalified_v1' and receipt['completed'] is True and receipt['new_EDA'] is False and receipt['OPT_executed'] is False and receipt['snapshot_recollected'] is False and receipt['checkpoint']==recovered['checkpoint'] and receipt['recovery_package']==value['recovery_package'],'actual qualified OPT stage/checkpoint mismatch')
    for row in [receipt['binding'],receipt['qualifier'],receipt['source_archive'],receipt['stage_inputs'],*receipt['outputs']]:r.old.verify_identity(row)
    q.provenance()
    integrity=next(row for row in receipt['outputs'] if Path(row['path']).name=='integrity_opt.json');facts=json.loads(Path(integrity['path']).read_text())
    r.old.require(facts['gate_issues']==[] and facts['reset_structure']['qualified'] is True and facts['reset_fanout_observation']['qualified'] is True and facts['cdc_classification']['new_critical']==0,'full actual OPT qualification not valid')
    return value,receipt

def restored(package,report,*,offline_replay=False):
    value,receipt=verify(package)
    r.old.require(report==Path(os.environ['HAP_REPORT_DIR']).resolve() and Path(os.environ['HAP_CURRENT_ATTEMPT_DIR']).is_relative_to(r.ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs'),'current native report/owner context absent')
    r.old.require(os.environ.get('HAP_EXECUTION_MODE')=='checkpoint_restored_commands' and os.environ.get('HAP_M003_QUALIFIED_OPT_SNAPSHOT')==str(q.ACTUAL/'m003_native_opt.json').replace('m003_E011_R002_AT034_OPT_fresh_registry_selection','m003_E011_R002_AT031_verified_restore_parser_to_OPT'),'different actual native stage/snapshot')
    membership=json.loads((report/'restored_effective_membership_pass.json').read_text());r.old.require(membership['passed'] is True and membership['selected_cells']==22850 and membership['pblocks']==28 and membership['checkpoint']==receipt['checkpoint'],'current native restored membership changed')
    r.zero_reapply(json.loads((report/'restore_apply_attempts.json').read_text()))
    metadata,hashes=r.old.hash_registry('opt',report);constraints=json.loads((report/'constraints_opt.json').read_text())
    r.old.require(metadata==constraints['metadata'] and all(constraints['hashes'].get(path)==digest for path,digest in hashes.items()),'current native candidate metadata/source bytes differ from qualified OPT')
    r.old.require((report/'embedded_xdc_registry_opt.tsv').is_file(),'current actual embedded constraint observation missing')
    admission=dict(zip(*(iter((report/'admission_opt.txt').read_text().split()),)*2));r.old.require(admission['diagnostic_eligible']=='0' and admission['debug_materialization_eligible']=='1','inherited OPT cannot admit placement')
    r.save(report/'qualified_OPT_restore_binding.json',dict(passed=True,offline_replay=offline_replay,native_observation_origin='actual_AT034_copied_data_replay' if offline_replay else 'current_owned_native_restore',phase='same_untransformed_OPT_before_actual_debug',qualified_OPT_POST=value['qualified_OPT_POST'],current_membership=r.old.file_id(report/'restored_effective_membership_pass.json'),current_registry=r.old.file_id(report/'xdc_registry_opt_hashed.tsv'),current_embedded_registry=r.old.file_id(report/'embedded_xdc_registry_opt.tsv'),current_zeroapply=r.old.file_id(report/'restore_apply_attempts.json'),checkpoint=receipt['checkpoint'],OPT_POST_not_reexecuted=True,actual_debug_all_original_POST_still_required=True,formal_reset_cdc_safety='OPEN',G4=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dependency-package',type=Path,required=True);p.add_argument('--report',type=Path);p.add_argument('--offline-replay',action='store_true');a=p.parse_args()
    if a.report:restored(a.dependency_package.resolve(),a.report.resolve(),offline_replay=a.offline_replay)
    else:verify(a.dependency_package.resolve())
