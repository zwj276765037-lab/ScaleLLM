"""Use the frozen complete recovery launcher; inherit qualified OPT, execute real debug."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import qualified_opt_evidence as e
r=e.r
sys.path.insert(0,str(r.HERE));import launch as native
class PreparedBoundary(Exception):pass
class Boundary:
    def __init__(self,package,prepare_only):self.package=package;self.prepare_only=prepare_only
    def run(self,command,*,cwd,env):
        value,receipt=e.verify(self.package);report=Path(env['HAP_REPORT_DIR'])
        expected=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace','-source',str(r.HERE/'recover_init.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
        r.old.require(command==expected and cwd==r.HW/'vivado' and env.get('HAP_M003_QUALIFIED_OPT_SNAPSHOT')==r.verify(Path(value['recovery_package']['path']))['reuse_opt']['input_snapshot']['path'],'original same-OPT native boundary changed')
        history=report/'prior_preparation_state';history.mkdir()
        prior=[]
        for name in ['native_launch_preparation.json','source_archive.json','stage_inputs.sha256']:
            original=r.old.file_id(report/name);shutil.copyfile(report/name,history/name);prior.append(dict(original=original,preserved=r.old.file_id(history/name)))
        paths=e.SOURCES+[self.package,Path(value['qualified_OPT_POST']['path'])]+[Path(row['path']) for row in receipt['outputs']]+[Path(receipt[k]['path']) for k in ['source_archive','stage_inputs']]
        r.archive_extra(report,paths)
        copies=[]
        for row in receipt['outputs']:
            target=report/Path(row['path']).name
            if target.exists() and r.old.sha256(target)!=row['sha256']:r.old.require(target.name=='opt_result.txt','unexpected derived-input overwrite')
            shutil.copyfile(row['path'],target);r.old.require(r.old.sha256(target)==row['sha256'],'qualified OPT output changed');copies.append(dict(source=row,target=r.old.artifact_id(target)))
        r.save(report/'OPT_POST_qualified_evidence_origin.json',dict(original_native_attempt='AT034',actual_native_OPT_attempt='AT031',original_outer_native_exit_code=1,native_OPT_tcl_code=0,OPT_POST_reexecuted=False,qualified_receipt=value['qualified_OPT_POST'],copies=copies,prior_preparation_state=prior,formal_reset_cdc_safety='OPEN',actual_debug_and_own_POST_required=True))
        original_command=list(command);command[5]=str(HERE/'qualified_opt_debug.tcl');env={**env,'HAP_QUALIFIED_OPT_DEPENDENCY_PACKAGE':str(self.package)}
        archive=json.loads((report/'source_archive.json').read_text());manifest=r.old.manifest_records(report/'stage_inputs.sha256')
        for row in archive:r.old.verify_identity(row['original']);r.old.verify_identity(row['preserved']);r.old.require(manifest[Path(row['original']['path'])]==row['original']['sha256'],'continuation source archive mismatch')
        r.old.require(len(archive)==len(manifest),'continuation dependency coverage mismatch')
        r.save(report/'qualified_OPT_debug_native_boundary.json',dict(completed=True,native_executed=False,prepare_only=self.prepare_only,original_command=original_command,actual_command=command,dependency_package=r.old.file_id(self.package),qualified_OPT_POST=value['qualified_OPT_POST'],source_archive=r.old.file_id(report/'source_archive.json'),stage_inputs=r.old.file_id(report/'stage_inputs.sha256'),archive_bindings=len(archive),original_native_preparation_preserved=prior,OPT_identity_applicable_only_before_actual_debug=True,actual_debug_must_collect_own_snapshot_graph_CDC_fanout_and_all_original_guards=True))
        if self.prepare_only:raise PreparedBoundary()
        return subprocess.run(command,cwd=cwd,env=env)
def main():
    p=argparse.ArgumentParser();p.add_argument('--dependency-package',type=Path,required=True);p.add_argument('--archive-source',action='append',default=[]);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    value,receipt=e.verify(a.dependency_package.resolve());base=r.verify(Path(value['recovery_package']['path']))
    original_sources={row['path'] for row in base['sources']}|{row['path'] for row in r.entry.check_sources()['sources']};expected=original_sources|{str(path) for path in e.SOURCES}
    r.old.require(set(a.archive_source)==expected and len(a.archive_source)==len(expected),'complete core48+4 recovery+4 continuation source archive required')
    argv=[str(r.HERE/'launch.py'),'--package',value['recovery_package']['path']]
    for path in sorted(original_sources):argv+=['--archive-source',path]
    native.subprocess=Boundary(a.dependency_package.resolve(),a.prepare_only);old_argv=sys.argv;sys.argv=argv
    try:
        try:return native.main()
        except PreparedBoundary:print('{"prepared":true,"new_EDA":false,"exact_actual_debug_boundary":true}');return 0
    finally:sys.argv=old_argv
if __name__=='__main__':sys.exit(main())
