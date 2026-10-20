#!/usr/bin/env python3
"""SM015 actual engineering start and frozen design/source binding; no EDA."""
import datetime,hashlib,json,os,shutil
from pathlib import Path
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HERE=Path(__file__).resolve().parent
AT=HERE.parent/'experiment_results/runs/R001/attempts/AT001_selected_RTL_and_functional_integration'
DESIGN=ROOT/'agent/A006/M003_SM014_design_20261018'
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
 out=AT/'actual_engineering_start.json';assert not out.exists()
 manifest=DESIGN/'design_delivery_manifest.json'
 assert ident(manifest)['sha256']=='6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b'
 frozen=json.loads(manifest.read_text());verified=[]
 for e in frozen['files']:
  a=ident(Path(e['path']));assert a==e;verified.append(a)
 baseline=json.loads((DESIGN/'design_input_identities.json').read_text())['production_inputs']
 for e in baseline:assert ident(Path(e['path']))==e
 originals=HERE/'prechange_RTL';originals.mkdir()
 paths=['rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv','rtl/attention/hap_weight_meta_resident.sv','rtl/attention/hap_attention_board_cohort16_core.sv']
 copies=[]
 for rel in paths:
  src=ROOT/'project/hardware'/rel;dst=originals/src.name;shutil.copyfile(src,dst);copies.append(dict(original=ident(src),preserved=ident(dst)))
 result=dict(started_utc=started_utc,observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),role='engineering',task='/root/m002_build_verify',experiment='E011',run='R001',attempt='AT001',execution_state='running',stage='SM015/SM016 selected version actual source preparation started',G2_decision=ident(ROOT/'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md'),design_manifest=ident(manifest),frozen_files_verified=len(verified),frozen_bytes_verified=sum(r['bytes'] for r in verified),production_inputs_before_change_verified=len(baseline),selected=['C-M2','C-A3','C-P1'],prechange_RTL=copies,process=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]),affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),threads=1),actual_model='UNVERIFIED',new_EDA=False,protected_other_work='M004/E010 and all others retained; no descendants',producer=ident(Path(__file__)))
 out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='prechange_RTL'},indent=2))
if __name__=='__main__':main()
