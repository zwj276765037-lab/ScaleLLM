from pathlib import Path
import subprocess,os,json,time,datetime,hashlib
AT=Path(__file__).resolve().parent;PY='/home/user/anaconda3/envs/zhouwenjun/bin/python';root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(n,x):
 p=AT/n;t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');os.replace(t,p)
m=json.loads((AT/'manifest.json').read_text());env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
cmd=[PY,'-B',m['source'][0]['path'],'--attempt',m['input_attempt'],'--output',str(AT/'analysis')];start=now();t=time.monotonic()
with (AT/'stdout.log').open('xb') as o,(AT/'stderr.log').open('xb') as e:
 p=subprocess.Popen(cmd,env=env,cwd=root,stdout=o,stderr=e);write('actual_launch.json',dict(driver_pid=os.getpid(),pid=p.pid,startticks=Path('/proc',str(p.pid),'stat').read_text().split()[21],started_at=start,command=cmd));code=p.wait()
unchanged=all(hashlib.sha256(Path(d['path']).read_bytes()).hexdigest()==d['sha256'] for d in m['source'])
write('execution_receipt.json',dict(execution_state='completed' if code==0 else 'failed',native_exit_code=code,child_reaped=True,source_unchanged=unchanged,started_at=start,ended_at=now(),wall_seconds=time.monotonic()-t,child_pid=p.pid))
print(json.dumps(dict(native_exit_code=code,child_reaped=True,source_unchanged=unchanged)),flush=True)
raise SystemExit(code)
