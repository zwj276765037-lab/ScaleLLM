"""Retain original implement launcher and G4 checks; adapt one qualifier call only."""
from pathlib import Path
import argparse,json,os,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
HW=ROOT/'project/hardware'
sys.path.insert(0,str(HW/'vivado/scripts'))
sys.path.insert(0,str(HERE.parent/'AT028_init_recovery'))
import run_m003_stage as native
import native_init_recovery as literal
SOURCES=[Path(__file__),HERE/'physical_literal_adapter.tcl',HERE.parent/'AT028_init_recovery/native_init_recovery.py']
class PreparedBoundary(Exception): pass

def dependency_package(output):
    value=dict(schema='M003_physical_cell_literal_adapter_v1',created_utc=literal.stage.now(),
        frozen_source_manifest=literal.old.file_id(literal.entry.MANIFEST),
        original_launcher=literal.old.file_id(HW/'vivado/scripts/run_m003_stage.py'),
        original_physical=literal.old.file_id(HW/'vivado/scripts/m003_physical.tcl'),
        sources=[literal.old.file_id(p) for p in SOURCES],
        contract='original actual A007 package/source-review guards and all fixed commands unchanged; single width1 binary cell decoder only')
    literal.save(output,value); return value

def verify(package):
    value=json.loads(package.read_text())
    literal.old.require(value['schema']=='M003_physical_cell_literal_adapter_v1','foreign physical adapter package')
    for row in [value['frozen_source_manifest'],value['original_launcher'],value['original_physical'],*value['sources']]:literal.old.verify_identity(row)
    literal.entry.check_sources()
    literal.old.require({x['path'] for x in value['sources']}=={str(p) for p in SOURCES},'hidden or missing physical adapter dependency')
    return value

class NativeBoundary:
    def __init__(self,package,prepare_only): self.package=package;self.prepare_only=prepare_only
    def run(self,command,*,cwd,env):
        # The unmodified original launcher reaches this only after real G4 checks.
        value=verify(self.package);report=Path(env['HAP_REPORT_DIR']);pre=Path(env['HAP_PRE_PLACE_REPORT_DIR'])
        literal.old.require(env['HAP_STAGE']=='implement' and env['HAP_EXECUTION_MODE']=='checkpoint_restored_commands','original implement mode changed')
        expected=[native.VIVADO,'-mode','batch','-notrace','-source',str(HW/'vivado/scripts/m003_physical.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
        literal.old.require(command==expected and cwd==HW/'vivado','original native invocation changed')
        pkg=json.loads((pre/'M003_preplace_package.json').read_text())
        literal.old.require(env['HAP_RECOVERY_CHECKPOINT']==pkg['checkpoint']['path'],'original selected checkpoint changed')
        literal.archive_extra(report,SOURCES+[self.package])
        rows=json.loads((report/'source_archive.json').read_text());manifest=literal.old.manifest_records(report/'stage_inputs.sha256')
        for row in rows:
            literal.old.verify_identity(row['original']);literal.old.verify_identity(row['preserved'])
            literal.old.require(manifest[Path(row['original']['path'])]==row['original']['sha256'],'physical adapter archive changed')
        literal.old.require(len(rows)==len(manifest),'physical source archive coverage differs')
        gate=json.loads((pre/'A007_G4_no_blocker.json').read_text())
        adapted=list(command);adapted[5]=str(HERE/'physical_literal_adapter.tcl')
        literal.save(report/'physical_adapter_native_boundary.json',dict(completed=True,native_executed=False,prepare_only=self.prepare_only,
            original_launcher=value['original_launcher'],dependency_package=literal.old.file_id(self.package),
            preplace=literal.old.file_id(pre/'M003_preplace_package.json'),actual_G4_gate=literal.old.file_id(pre/'A007_G4_no_blocker.json'),
            actual_source_review=gate['source_review'],checkpoint=pkg['checkpoint'],original_command=command,adapted_command=adapted,
            changed_native_arguments=[5],all_original_G4_checks_retained=True,source_archive=literal.old.file_id(report/'source_archive.json'),
            stage_inputs=literal.old.file_id(report/'stage_inputs.sha256'),archive_bindings=len(rows),no_bitstream=True))
        if self.prepare_only: raise PreparedBoundary()
        return subprocess.run(adapted,cwd=cwd,env=env)

def main():
    p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--dependency-package',type=Path,required=True)
    p.add_argument('--archive-source',action='append',default=[]);p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--make-package',action='store_true');args,rest=p.parse_known_args()
    if args.make_package:dependency_package(args.dependency_package.resolve());print('{"prepared":true,"new_EDA":false}');return 0
    value=verify(args.dependency_package.resolve())
    expected={row['path'] for row in literal.entry.check_sources()['sources']}|{str(p) for p in SOURCES}
    literal.old.require(set(args.archive_source)==expected and len(args.archive_source)==len(expected),'complete core48+3 physical dependency archive required')
    literal.old.require(rest.count('--stage')==1 and rest[rest.index('--stage')+1]=='implement','only fixed original implement is authorized')
    native.subprocess=NativeBoundary(args.dependency_package.resolve(),args.prepare_only)
    original=sys.argv;sys.argv=[str(HW/'vivado/scripts/run_m003_stage.py'),*rest]
    try:
        try:return native.main()
        except PreparedBoundary:
            print('{"prepared":true,"native_executed":false,"actual_G4_checked":true,"exact_original_native_boundary":true}');return 0
    finally:sys.argv=original
if __name__=='__main__':sys.exit(main())
