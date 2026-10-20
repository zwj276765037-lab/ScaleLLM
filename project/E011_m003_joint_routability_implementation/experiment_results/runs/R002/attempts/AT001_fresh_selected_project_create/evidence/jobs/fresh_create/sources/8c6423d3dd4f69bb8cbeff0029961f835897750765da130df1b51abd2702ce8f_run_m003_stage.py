#!/usr/bin/env python3
"""Native command launcher; outer run_m003_owned.py retains the single tool lane."""
from pathlib import Path
import argparse,json,os,subprocess,sys
import m003_entry as entry
import m003_stage as stage
import m002_physical_evidence as old
HW=Path(__file__).resolve().parents[2]
VIVADO='/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado'
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['create','synth','qualify','implement'],required=True);p.add_argument('--project',type=Path,required=True);p.add_argument('--synth-report',type=Path);p.add_argument('--synth-attempt',type=Path);p.add_argument('--preplace-report',type=Path);a=p.parse_args()
 entry.check_sources();report=Path(os.environ['HAP_REPORT_DIR']);project=a.project.resolve();old.require(project.is_relative_to(HW/'vivado/project') and report.is_relative_to(HW/'vivado/reports') and not report.exists(),'new selected project/report required')
 env={**os.environ,'HAP_PROJECT_DIR':str(project),'HAP_STAGE':a.stage,'HAP_BOARD_CORE_CLK_MHZ':'100.0','HAP_BOARD_DDR_UI_CLK_HZ':'200000000','HAP_M003_ACTIVE':'1','HAP_JOBS':'8','HAP_SYNTH_JOBS':'1'}
 if a.stage in ('create','synth'):
  cmd=[str(HW/'vivado/scripts/run_vcu118_board.sh'),a.stage]
 else:
  old.require(a.synth_report is not None and a.synth_attempt is not None,'new synthesis qualification lineage required')
  stage.lineage(project,a.synth_report,a.synth_attempt)
  report.mkdir();stage.prepare_sources(report,a.synth_report)
  env.update(HAP_SYNTH_REPORT_DIR=str(a.synth_report),HAP_SYNTH_ATTEMPT_DIR=str(a.synth_attempt),HAP_EXECUTION_MODE='m003_explicit_commands')
  if a.stage=='implement':
   old.require(a.preplace_report is not None,'qualified preplace required')
   pkg=json.loads((a.preplace_report/'M003_preplace_package.json').read_text())
   old.require(pkg['schema']=='M003_preplace_v1' and pkg['G2_sha256']==entry.G2,'selected preplace package changed')
   for key in ('checkpoint','pre_place','constraints','source_manifest','stage_inputs','source_archive','selection'):old.verify_identity(pkg[key])
   gate=json.loads((a.preplace_report/'A007_G4_no_blocker.json').read_text())
   old.require(gate.get('no_blocker') is True and gate.get('package_sha256')==old.sha256(a.preplace_report/'M003_preplace_package.json'),'A007 selected G4 no-blocker binding missing')
   review=gate.get('source_review',{});old.verify_identity(review)
   review_path=Path(review['path']);old.require(review_path.is_relative_to(HW.parent.parent/'agent/A007'),'independent G4 review must be from A007 owned evidence')
   verdict=json.loads(review_path.read_text());old.require(verdict.get('no_blocker') is True and verdict.get('package_sha256')==gate['package_sha256'],'independent G4 review does not admit actual package')
   env.update(HAP_PRE_PLACE_REPORT_DIR=str(a.preplace_report),HAP_RECOVERY_CHECKPOINT=pkg['checkpoint']['path'],HAP_EXECUTION_MODE='checkpoint_restored_commands')
  cmd=[VIVADO,'-mode','batch','-notrace','-source',str(HW/'vivado/scripts/m003_physical.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
 started=stage.now();r=subprocess.run(cmd,cwd=HW/'vivado',env=env)
 if a.stage in ('qualify','implement'):stage.save(report/'launcher_status.json',dict(stage=a.stage,project=str(project),started_utc=started,ended_utc=stage.now(),native_exit_code=r.returncode,command=cmd,bitstream=None))
 return r.returncode
if __name__=='__main__':sys.exit(main())
