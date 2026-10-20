import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent
source=out/'source_snapshot.py'
cmd=['taskset','-c','18,19','/home/user/anaconda3/envs/zhouwenjun/bin/python','-B',str(out/'library_check_entry.py')]
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',LD_LIBRARY_PATH='/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/nvml_local_recovery_20261018/cuda_lib')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
record={'schema':'scalellm_gpu1_repair_launch_v1','started_at':now(),'launcher_pid':os.getpid(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'argv':cmd,'environment_overrides':{k:env[k] for k in ['CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','LD_LIBRARY_PATH']},'execution_state':'starting'}
with (out/'stdout.log').open('w') as log:
 proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT);record.update(worker_pid=proc.pid,execution_state='running');(out/'launch.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
 rc=proc.wait()
record.update(execution_state='completed' if rc==0 else 'failed',exit_code=rc,ended_at=now(),stop_reason=None);(out/'terminal.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True);sys.exit(rc)
