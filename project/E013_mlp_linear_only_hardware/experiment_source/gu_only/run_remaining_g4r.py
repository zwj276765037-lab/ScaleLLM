#!/usr/bin/env python3
"""A022's serial queue; waits for AT019, then runs exactly three G4R checks."""
from pathlib import Path
import fcntl,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[4];HW=ROOT/'project/hardware';BASE=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R006'
def main():
 out=BASE/'preparation/remaining_g4r_queue';out.mkdir(exist_ok=False)
 (out/'script.sha256').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()+'\n')
 parent=BASE/'attempts/AT019_production_integration/result.json'
 while not parent.is_file():time.sleep(1)
 if json.loads(parent.read_text())['verdict']!='PASS':
  (out/'result.json').write_text(json.dumps(dict(verdict='STOPPED_DEPENDENCY_FAILURE',dependency=str(parent)),indent=2)+'\n');return 1
 # Result creation can precede the parent's final Python cleanup by milliseconds.
 with (HW/'vivado/.m006_linear_eda.lock').open('a+') as lock:
  while True:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:time.sleep(.2)
  fcntl.flock(lock,fcntl.LOCK_UN)
 base=['python3',str(HW/'vivado/scripts/run_mlp_gu_sim.py')]
 tasks=[('AT023_csr','hap_mlp_gu_axil_control_tb','tb/hap_mlp_gu_axil_control_tb.sv','vivado/manifests/mlp_gu_only/csr.list',False),('AT024_metadata_fault','hap_attention_mlp_gu_metadata_fault_tb','tb/hap_attention_mlp_gu_metadata_fault_tb.sv','vivado/manifests/mlp_gu_only/metadata_fault.list',True),('AT025_production_shape','hap_attention_mlp_gu_production_shape_tb','tb/hap_attention_mlp_gu_production_shape_tb.sv','vivado/manifests/mlp_gu_only/production_shape.list',True)]
 results=[]
 for attempt,top,tb,manifest,production in tasks:
  command=base+[top,tb,manifest,attempt]
  if production:command+=['--define','HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core']
  if attempt=='AT024_metadata_fault':
   for name in ['generate_integration_gold.py','all_values.json','gold_words.bin','gold_rows.svtext','manifest.json','generation.log']:
    command+=['--support-input','project/E013_mlp_linear_only_hardware/experiment_results/host_reference/integration_gold/'+name]
  with (out/(attempt+'.log')).open('w') as log:r=subprocess.run(command,cwd=HW,stdout=log,stderr=subprocess.STDOUT)
  results.append(dict(attempt=attempt,command=command,native_runner_returncode=r.returncode))
  (out/'steps.json').write_text(json.dumps(results,indent=2)+'\n')
  if r.returncode:
   (out/'result.json').write_text(json.dumps(dict(verdict='STOPPED_CHECK_FAILURE',steps=results),indent=2)+'\n');return 1
 (out/'result.json').write_text(json.dumps(dict(verdict='THREE_CHECKS_COMPLETED',steps=results),indent=2)+'\n');return 0
if __name__=='__main__':raise SystemExit(main())
