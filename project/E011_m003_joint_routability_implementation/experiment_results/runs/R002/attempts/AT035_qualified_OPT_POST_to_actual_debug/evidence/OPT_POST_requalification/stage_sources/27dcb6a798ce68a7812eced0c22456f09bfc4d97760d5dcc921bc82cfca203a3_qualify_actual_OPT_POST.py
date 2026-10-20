"""Bind current M003 native OPT producer/data, retaining original full safety gates."""
from pathlib import Path
import argparse,importlib.util,json,os,shutil,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'AT028_init_recovery'))
import native_init_recovery as r
ACTUAL=r.HW/'vivado/reports/m003_E011_R002_AT034_OPT_fresh_registry_selection'
ATTEMPT=r.ORIGIN.parent/'AT034_OPT_fresh_registry_selection'
JOB=ATTEMPT/'evidence/jobs/native_OPT_missing_POST_debug_preplace'
PACKAGE=r.HERE/'recovery_package_AT034_namespace_v2.json'

def provenance():
    value=r.verify(PACKAGE)
    status=json.loads((JOB/'status.json').read_text());closure=json.loads((ATTEMPT/'evidence/owner_terminal_and_source_closure.json').read_text())
    r.old.require(status['native_exit_code']==1 and status['stop_reason'] is None and status['owned_survivors']=={} and status['core_RTL_unchanged_during_job'] is True and closure['lock_free'] is True,'actual OPT POST origin not naturally closed')
    archive=json.loads((JOB/'source_archive.json').read_text())['bindings']
    for row in archive:r.old.verify_identity(row['original']);r.old.verify_identity(row['preserved'])
    preparation=json.loads((ACTUAL/'native_launch_preparation.json').read_text());parent=json.loads((ACTUAL/'M003_init_recovery_parent.json').read_text())
    r.old.require(preparation['package']==r.old.file_id(PACKAGE) and parent['package']==preparation['package'] and preparation['checkpoint']==parent['checkpoint']==value['checkpoint'] and parent['restored_phase']=='opt' and parent['OPT_executed'] is False,'actual same OPT checkpoint/producer package changed')
    env=preparation['environment'];r.old.require(env.get('HAP_M003_QUALIFIED_OPT_SNAPSHOT')==value['reuse_opt']['input_snapshot']['path'] and 'HAP_RECOVERY_PHASE' not in env,'actual native phase/selected branch changed')
    r.old.require(r.old.sha256(ACTUAL/'opt.dcp')==value['checkpoint']['sha256'],'actual restored OPT bytes changed')
    membership=json.loads((ACTUAL/'restored_effective_membership_pass.json').read_text());r.old.require(membership['passed'] is True and membership['selected_cells']==22850 and membership['pblocks']==28 and membership['checkpoint']==value['checkpoint'],'actual selected OPT restore not proven')
    r.zero_reapply(json.loads((ACTUAL/'restore_apply_attempts.json').read_text()))
    integrity=json.loads((ACTUAL/'integrity_opt.json').read_text())
    r.old.require(integrity['phase']=='opt' and integrity['gate_issues']==['critical_CDC: ValueError: exact OPT reset CDC requires actual chain/polarity/HostSplit/fanout diagnostic proof'] and integrity['reset_structure']['qualified'] is True and integrity['reset_structure']['issues']==[],'different native OPT failure requires separate analysis')
    r.old.require(integrity['constraints']==r.old.file_id(ACTUAL/'constraints_opt.json'),'actual effective constraints changed')
    constraints=json.loads((ACTUAL/'constraints_opt.json').read_text())
    for path,digest in constraints['hashes'].items():r.old.require(Path(path).is_file() and r.old.sha256(Path(path))==digest,'actual effective constraint source bytes changed')
    r.stage.verify_probe(ACTUAL,'opt');r.stage.lineage(r.PROJECT,r.SYNTH_REPORT,r.SYNTH_AT)
    producers=[]
    for p in [r.HERE/'recover_init.tcl',r.HERE/'native_init_recovery.py',r.HW/'vivado/scripts/m002_diagnostic_common.tcl']:
        matches=[row for row in archive if row['original']['path']==str(p)];r.old.require(len(matches)==1,'actual producer source not archived');producers+=matches
    common=(r.HW/'vivado/scripts/m002_diagnostic_common.tcl').read_text()
    r.old.require('set violations [get_cdc_violations -quiet -name $name]' in common and 'if {[llength $violations] > 64}' in common,'actual bounded CDC producer changed')
    files=[JOB/'status.json',JOB/'source_archive.json',ATTEMPT/'evidence/owner_terminal_and_source_closure.json',ACTUAL/'native_launch_preparation.json',ACTUAL/'M003_init_recovery_parent.json',ACTUAL/'restored_effective_membership_pass.json',ACTUAL/'restore_apply_attempts.json',ACTUAL/'constraints_opt.json',ACTUAL/'integrity_opt.json',ACTUAL/'cdc_changed_reset_opt.tsv',ACTUAL/'reset_graph_opt.tsv',ACTUAL/'bram_port_clocks_opt.tsv',ACTUAL/'cdc_opt.rpt']
    return dict(schema='M003_same_actual_OPT_targeted_CDC_binding_v1',source_report=str(ACTUAL),checkpoint=value['checkpoint'],package=r.old.file_id(PACKAGE),anchors=[r.old.file_id(p) for p in files],producers=producers,reports=[r.old.file_id(ACTUAL/f'cdc_changed_opt_{i}.rpt') for i in range(4)],object_counts=[668,668,768,769],object_limit=64,formal_reset_cdc_safety='OPEN',raw_UNKNOWN_retained=True,scope='current complete Critical reports only; exact original chains/polarity/fanout/8tuple/full-union retained')

def requalify(target):
    r.old.require(not target.exists(),'new offline derivation directory required')
    binding=provenance()
    # Existing low-level per-run checker retains the exact original command,
    # tool/design/device/Optimized headers, counts, complete tuples and union8.
    auxiliary=r.old.auxiliary_cdc_limits(ACTUAL/'cdc_changed_reset_opt.tsv',_e005_binding=binding)
    r.old.require(auxiliary['coverage']=='coverage_limited' and auxiliary['critical_rows']==8,'current complete Critical report coverage not proven')
    target.mkdir();r.stage.prepare_sources(target,r.SYNTH_REPORT)
    names=['opt_result.txt','opt_command_result.txt','utilization_opt.rpt','timing_opt.rpt','drc_opt.rpt','check_timing_opt.rpt','clocks_opt.rpt','cdc_opt.rpt','clock_interaction_opt.rpt','exceptions_opt.rpt','pulse_width_opt.rpt','bus_skew_opt.rpt','debug_opt.tsv','debug_proof_opt.txt','blackboxes_opt.tsv','reset_cdc_and_io_probe_opt.tsv','xpm_invalid_endpoint_probe_opt.tsv','head_wave_local_opt.tsv','m003_stream_opt_cells.jsonl','m003_native_opt.json','m003_qualification_opt.json','constraints_opt.json']
    inputs=[ACTUAL/name for name in names]+[HERE/'qualify_actual_OPT_POST.py',PACKAGE]+[Path(row['path']) for row in binding['anchors']+binding['reports']]
    r.archive_extra(target,inputs)
    for name in names:shutil.copyfile(ACTUAL/name,target/name);r.old.require(r.old.sha256(target/name)==r.old.sha256(ACTUAL/name),'inherited native OPT evidence changed')
    q=json.loads((target/'m003_qualification_opt.json').read_text());r.old.require(q['passed'] is True and q['snapshot_sha256']==r.old.sha256(target/'m003_native_opt.json'),'selected structure qualification missing')
    r.stage.prepare_probe(target,'opt',r.SYNTH_REPORT,r.PROJECT)
    spec=importlib.util.spec_from_file_location('membership',r.HERE.parent/'AT028_offline_pblock_membership_check.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    membership=module.check(target/'m003_stream_opt_cells.jsonl',r.HW/'vivado/constraints/m003_joint_locality_spec.json');r.old.require(membership['passed'] is True,'actual C01/M2 pools not preserved');r.save(target/'effective_pblock_membership_opt.json',membership)
    r.save(target/'M003_current_targeted_CDC_binding.json',binding)
    original_aux=r.old.auxiliary_cdc_limits;original_constraints=r.base.constraint_chain;original_structure=r.base.reset_structure;original_fanout=r.base.reset_fanout;previous=os.environ.copy()
    def current_aux(path,**kw):
        r.old.require(path.resolve()==ACTUAL/'cdc_changed_reset_opt.tsv' and not kw,'foreign auxiliary source or double binding')
        return original_aux(path,_e005_binding=binding)
    def inherited_constraints(point,report):
        r.old.require(point=='opt' and report==target and r.old.sha256(report/'constraints_opt.json')==r.old.sha256(ACTUAL/'constraints_opt.json'),'different effective native constraint observation')
        return json.loads((report/'constraints_opt.json').read_text())
    def actual_structure(path):return original_structure(ACTUAL/'reset_graph_opt.tsv')
    def actual_fanout(path,clock_path):return original_fanout(ACTUAL/'cdc_changed_reset_opt.tsv',ACTUAL/'bram_port_clocks_opt.tsv')
    os.environ.update(HAP_PROJECT_DIR=str(r.PROJECT),HAP_SYNTH_REPORT_DIR=str(r.SYNTH_REPORT),HAP_SYNTH_ATTEMPT_DIR=str(r.SYNTH_AT),HAP_EXECUTION_MODE='checkpoint_restored_commands')
    r.old.auxiliary_cdc_limits=current_aux;r.base.constraint_chain=inherited_constraints;r.base.reset_structure=actual_structure;r.base.reset_fanout=actual_fanout
    try:r.base.hook_batch('opt',target)
    finally:
        r.old.auxiliary_cdc_limits=original_aux;r.base.constraint_chain=original_constraints;r.base.reset_structure=original_structure;r.base.reset_fanout=original_fanout;os.environ.clear();os.environ.update(previous)
    admission=dict(zip(*(iter((target/'admission_opt.txt').read_text().split()),)*2))
    r.old.require(admission['diagnostic_eligible']=='0' and admission['debug_materialization_eligible']=='1','OPT must authorize only actual debug, not placement')
    bb=r.old.key_values(target/'opt_result.txt')['blackboxes'];(target/'opt_result.txt').write_text('completed=1\ndiagnostic_eligible=0\ndebug_materialization_eligible=1\nphase=opt\nblackboxes='+bb+'\nclock_coverage='+admission['clock_coverage']+'\nevidence_origin=actual_AT034_OPT_POST_offline_current_provenance_requalification\nphysical_signoff=false\n')
    outputs=[p for p in target.iterdir() if p.is_file() and p.name not in {'source_archive.json','stage_inputs.sha256'}]
    result=dict(schema='M003_actual_AT034_OPT_POST_requalified_v1',completed=True,new_EDA=False,OPT_executed=False,snapshot_recollected=False,source_report=str(ACTUAL),original_outer_native_exit_code=1,actual_OPT_native_tcl_code=0,checkpoint=binding['checkpoint'],recovery_package=r.old.file_id(PACKAGE),binding=r.old.file_id(target/'M003_current_targeted_CDC_binding.json'),qualifier=r.old.file_id(Path(__file__)),outputs=[r.old.artifact_id(p) for p in outputs],source_archive=r.old.file_id(target/'source_archive.json'),stage_inputs=r.old.file_id(target/'stage_inputs.sha256'),actual_debug_and_preplace_still_required=True,formal_reset_cdc_safety='OPEN')
    r.save(target/'offline_OPT_POST_requalification.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);a=p.parse_args();x=requalify(a.target.resolve());print(json.dumps(dict(completed=x['completed'],new_EDA=False,actual_debug_still_required=True)))
