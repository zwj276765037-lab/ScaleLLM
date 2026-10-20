"""R009 CPU postprocessing waits for actual GPU worker release; no CUDA use."""
import os,json,subprocess,sys,time,hashlib,signal
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');HERE=Path(__file__).resolve().parent;INPUT=HERE.parent/'AT003_true_exit_precision_dev36';S=ROOT/'project/software/0_Software/rounding_precision/experiment/rounding_optimization'
def now():return datetime.now(timezone.utc).isoformat()
def write(name,obj):
 p=HERE/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2)+'\n');os.replace(t,p)
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
started=now();begin=time.monotonic();commands=[]
try:
 sources=[S/'r009_analyze_lastlayer.py',S/'r009_head_witness.py',Path(__file__).resolve()];snap=HERE/'source_snapshot';snap.mkdir(exist_ok=True)
 for p in sources:(snap/p.name).write_bytes(p.read_bytes())
 write('manifest.json',dict(schema='r009_cpu_postprocess_v1',started_at=started,driver_pid=os.getpid(),source=[ident(p) for p in sources],input_attempt=str(INPUT),gpu_visible_devices='',fixed_head_witness_plan=dict(document_indices=[0,4,35],positions='0,T//2,T-1',all7pairs=True),scope='CPU-only independent raw evidence verification and fixed full-vocab head witnesses afterGPUrelease; source/ordinal plan frozen whileGPUmodelassembling',limits=dict(cpu_threads=1,rss_gib=8,wall_seconds_per_command=300)))
 for _ in range(2400):
  if (INPUT/'result.json').exists() and (INPUT/'external_lifecycle_receipt_v2.json').exists():break
  if (INPUT/'execution_receipt.json').exists() and json.loads((INPUT/'execution_receipt.json').read_text())['execution_state']=='failed':raise RuntimeError('GPU attempt failed')
  time.sleep(1)
 else:raise TimeoutError('GPU completion/external lifecycle evidence absent')
 receipt=json.loads((INPUT/'external_lifecycle_receipt_v2.json').read_text());assert receipt['proc_entry_absent'] and not receipt['gpu_owned_process_present']
 env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='';env['PYTHONDONTWRITEBYTECODE']='1'
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='1'
 import psutil
 for name,script,output in [('analysis',S/'r009_analyze_lastlayer.py',HERE/'analysis'),('head_witness',S/'r009_head_witness.py',HERE/'head_witness')]:
  cmd=[sys.executable,'-B',str(script),'--input',str(INPUT),'--output',str(output)];start=now();t=time.monotonic();peak=0;stop=None
  with (HERE/f'{name}_stdout.log').open('x') as stdout,(HERE/f'{name}_stderr.log').open('x') as stderr:proc=subprocess.Popen(cmd,env=env,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
  while proc.poll() is None:
   try:peak=max(peak,psutil.Process(proc.pid).memory_info().rss)
   except psutil.NoSuchProcess:pass
   if time.monotonic()-t>300 or peak>8*(1<<30):stop='CPUresource/time bound';os.killpg(proc.pid,signal.SIGTERM);break
   time.sleep(.5)
  native=proc.wait();r=dict(name=name,command=cmd,pid=proc.pid,started_at=start,ended_at=now(),native_exit_code=native,child_reaped=True,max_sampled_rss_bytes=peak,wall_seconds=time.monotonic()-t,stop_reason=stop);commands.append(r);write(f'{name}_receipt.json',r)
  if native or stop:raise RuntimeError(f'{name} failed')
 write('execution_receipt.json',dict(execution_state='completed',native_exit_code=0,started_at=started,ended_at=now(),wall_seconds=time.monotonic()-begin,commands=commands,source_unchanged=all(ident(p)['sha256']==ident(snap/p.name)['sha256'] for p in sources)));print(json.dumps(dict(state='completed',commands=commands)),flush=True)
except BaseException as e:
 write('execution_receipt.json',dict(execution_state='failed',native_exit_code=1,started_at=started,ended_at=now(),wall_seconds=time.monotonic()-begin,error=str(e),commands=commands));raise
