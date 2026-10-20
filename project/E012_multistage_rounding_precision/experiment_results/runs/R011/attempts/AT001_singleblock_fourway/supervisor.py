"""R011 singleblock diagnostic owner: actual launch identity and wait/reaped receipt."""
from pathlib import Path
import subprocess,os,json,time,datetime,hashlib
AT=Path(__file__).resolve().parent
ROOT=AT.parents[5]
PY='/home/user/anaconda3/envs/zhouwenjun/bin/python'
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,x):
    p=AT/name;t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');os.replace(t,p)
command=[PY,'-B',str(ROOT/'software/0_Software/rounding_precision/experiment/rounding_optimization/r011_run_diagnostic.py'),'--output-dir',str(AT),'--model-dir','/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct']
# Resolve project root explicitly: avoid any path-parent interpretation drift.
project_root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');command[2]=str(project_root/'project/software/0_Software/rounding_precision/experiment/rounding_optimization/r011_run_diagnostic.py')
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=GPU,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
start=now();t=time.monotonic()
with (AT/'worker_stdout.log').open('xb') as stdout,(AT/'worker_stderr.log').open('xb') as stderr:
    worker=subprocess.Popen(command,env=env,cwd=project_root,stdout=stdout,stderr=stderr,start_new_session=True)
    startticks=Path('/proc',str(worker.pid),'stat').read_text().split()[21]
    write('actual_launch.json',dict(pid=worker.pid,pgid=os.getpgid(worker.pid),startticks=startticks,supervisor_pid=os.getpid(),launched_at=start,command=command,cuda_visible_devices=GPU,cpu_threads=1,supervisor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    code=worker.wait()
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True).splitlines()
own=[x for x in apps if len(x.split(','))>=2 and x.split(',')[1].strip()==str(worker.pid)]
write('external_wait_receipt.json',dict(execution_state='completed' if code==0 else 'failed',native_exit_code=code,wait_returncode=code,child_reaped=True,actual_parent_waitpid=True,worker_pid=worker.pid,worker_startticks=startticks,supervisor_pid=os.getpid(),started_at=start,ended_at=now(),wall_seconds=time.monotonic()-t,worker_proc_absent=not Path('/proc',str(worker.pid)).exists(),gpu_owned_process_rows=own))
