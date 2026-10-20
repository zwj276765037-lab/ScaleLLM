from pathlib import Path
import subprocess,os,json,time,datetime,resource,hashlib
HERE=Path(__file__).resolve().parent
start=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic();source=HERE/'analyze_branches.py';expected=json.loads((HERE/'source_freeze.json').read_text())['script']['sha256']
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',MPLCONFIGDIR=str(HERE/'mpl_cache'),PYTHONDONTWRITEBYTECODE='1')
cmd=['/home/user/anaconda3/envs/zhouwenjun/bin/python','-B',str(source)]
with (HERE/'stdout.log').open('xb') as o,(HERE/'stderr.log').open('xb') as e:
 p=subprocess.Popen(cmd,env=env,stdout=o,stderr=e);(HERE/'actual_launch.json').write_text(json.dumps(dict(driver_pid=os.getpid(),child_pid=p.pid,started_at=start,command=cmd,cuda_visible_devices='',cpu_threads=1),indent=2)+'\n');code=p.wait()
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
r=dict(native_exit_code=code,child_reaped=True,started_at=start,ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_seconds=time.monotonic()-t,source_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==expected,child_peak_rss_bytes=usage.ru_maxrss*1024,cuda_or_model_used=False,child_pid=p.pid)
(HERE/'execution_receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);raise SystemExit(code)
