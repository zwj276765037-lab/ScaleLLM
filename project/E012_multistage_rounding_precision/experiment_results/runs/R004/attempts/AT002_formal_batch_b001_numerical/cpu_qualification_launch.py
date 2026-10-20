from pathlib import Path
from types import SimpleNamespace
import sys
root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
here=root/'project/software/0_Software/rounding_precision/experiment'
sys.path.insert(0,str(here))
from run_numerical_fidelity import cpu_supervise
from run_paired_numerical_model import code_identities
attempt=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical'
script=here/'run_paired_numerical_model.py'
sys.argv=[str(script),'--cpu-check','--model-dir','/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct',
    '--formal-batch-plan',str(attempt.parent/'AT001_frozen_formal_input_plan/formal_batch_plan.json'),
    '--formal-storage-plan',str(attempt/'preflight_storage/formal_storage_plan.json'),
    '--batch-ids','B001','--tokens','128','--raw-audit-layers','0,15,31',
    '--witness-max-doc-mib','64','--witness-max-at-mib','96','--output-dir',str(attempt/'cpu_check')]
raise SystemExit(cpu_supervise(SimpleNamespace(output_dir=attempt/'cpu_check',wall_seconds=300),script,'formal_entry',
                              [Path(row['path']) for row in code_identities()]))
