from pathlib import Path
import subprocess,os,json,time,datetime,resource,hashlib
HERE=Path(__file__).resolve().parent;script=HERE/'render_and_verify.py';sha=hashlib.sha256(script.read_bytes()).hexdigest();started=datetime.datetime.now(datetime.timezone.utc).isoformat();begin=time.monotonic()
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(HERE/'mpl_cache'),PYTHONDONTWRITEBYTECODE='1');command=['/home/user/anaconda3/envs/zhouwenjun/bin/python','-B',str(script)]
with (HERE/'render_stdout.log').open('xb') as o,(HERE/'render_stderr.log').open('xb') as e:
 p=subprocess.Popen(command,env=env,stdout=o,stderr=e);(HERE/'actual_launch.json').write_text(json.dumps(dict(driver_pid=os.getpid(),child_pid=p.pid,command=command,started_at=started,cuda_visible_devices='',cpu_threads=1,source_sha256=sha),indent=2)+'\n');code=p.wait()
r=dict(execution_state='completed' if code==0 else 'failed',native_exit_code=code,child_reaped=True,child_pid=p.pid,started_at=started,ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-begin,child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,source_unchanged=hashlib.sha256(script.read_bytes()).hexdigest()==sha,GPU_or_model_used=False)
(HERE/'execution_receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);raise SystemExit(code)
