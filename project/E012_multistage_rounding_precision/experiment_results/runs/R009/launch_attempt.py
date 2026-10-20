"""Launch one authorized R009 attempt and a read-only pidfd observer."""
import argparse,os,json,subprocess,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--runner',required=True);a=p.parse_args()
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');R=Path(__file__).resolve().parent;out=R/'attempts'/a.attempt;script=ROOT/'project/software/0_Software/rounding_precision/experiment/rounding_optimization'/a.runner
assert json.loads((out/'cpu_qualification.json').read_text())['passed']
for launch in (R/'attempts').glob('*/actual_launch.json'):
 old=json.loads(launch.read_text());proc=Path(f"/proc/{old['pid']}/stat")
 if proc.exists() and proc.read_text().split()[21]==old['startticks']:raise RuntimeError('prior owned worker still alive')
cmd=[sys.executable,'-B',str(script),'--output-dir',str(out),'--model-dir','/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct','--documents',str(ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT001_clean_document_manifest/documents_dev.jsonl')]
env=os.environ.copy()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='1'
env.update(CUDA_VISIBLE_DEVICES='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DEACTIVATE_ASYNC_LOAD='1',PYTHONDONTWRITEBYTECODE='1')
with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:worker=subprocess.Popen(cmd,env=env,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
row=dict(pid=worker.pid,pgid=os.getpgid(worker.pid),startticks=Path(f'/proc/{worker.pid}/stat').read_text().split()[21],launched_at=datetime.now(timezone.utc).isoformat(),command=cmd,cuda_visible_devices=env['CUDA_VISIBLE_DEVICES'],cpu_threads=1,launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Authorized R009 true lastlayer output precision; GPU conformance before one model assembly')
(out/'actual_launch.json').write_text(json.dumps(row,indent=2)+'\n')
observer=(ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/observe_lifecycle_v2.py').read_text();(out/'observe_lifecycle.py').write_text(observer)
with (out/'lifecycle_stdout.log').open('x') as stdout,(out/'lifecycle_stderr.log').open('x') as stderr:ob=subprocess.Popen([sys.executable,'-B',str(out/'observe_lifecycle.py')],stdout=stdout,stderr=stderr,start_new_session=True)
print(json.dumps(dict(**row,observer_pid=ob.pid)),flush=True)
report=dict(execution_state='running',current_task='R009 repaired legal-shift reconstruction; GPU conformance then fixed six-arm dev36',stage='Actual new-version GPU worker launch, model assembly not yet started',blocker=None,next_step='Pass rawcode/width/reference qualification, then one model assembly and216forwards',runtime_id=f'collaboration:/root/rounding_optimization_runner; worker_pid:{worker.pid}; observer_pid:{ob.pid}',thread_id=None,resource='GPU0 exact UUID; CPU1/RSS8GiB/GPU24GiB/2400s/512MiB; prior failed workers ended')
(out/'agent_running_report.json').write_text(json.dumps(report,indent=2)+'\n')
