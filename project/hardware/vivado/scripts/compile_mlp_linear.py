#!/usr/bin/env python3
import argparse,hashlib,json,os,subprocess,datetime
from pathlib import Path
from m006_entry import closure,selected_hdl,HW
BIN='/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/xvlog'
def main():
 a=argparse.ArgumentParser();a.add_argument('attempt');o=a.parse_args()
 out=HW.parents[1]/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts'/o.attempt;out.mkdir(parents=True,exist_ok=False)
 files=closure();sources=[str(p) for p in selected_hdl()]
 identity={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(out/'inputs.json').write_text(json.dumps(identity,indent=2)+'\n')
 cmd=[BIN,'-sv','-L','xpm','-L','unisims_ver','-d','HAP_BOARD_V5','-d','HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core',*sources]
 def setup():os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:8]);os.nice(5)
 with (out/'xvlog.log').open('w') as log:r=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT,preexec_fn=setup)
 (out/'result.json').write_text(json.dumps(dict(native_returncode=r.returncode,command=cmd,scope='syntax analysis only; not elaboration or functional simulation',changed_inputs=[p for p,h in identity.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]),indent=2)+'\n')
 print('xvlog returncode',r.returncode,out);return r.returncode
if __name__=='__main__':raise SystemExit(main())
