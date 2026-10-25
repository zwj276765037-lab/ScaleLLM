#!/usr/bin/env python3
"""Bounded CPU tests, immutable snapshots and native evidence; no EDA/GPU."""
import argparse,datetime as dt,hashlib,json,os,platform,resource,signal,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[3]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def available():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024

def main():
 p=argparse.ArgumentParser();p.add_argument('--pattern',default='test_scalellm_mlp_gu_only.py');a=p.parse_args()
 out=BASE/('AT_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir()
 env=dict(os.environ,PYTHONPATH=str(ROOT/'project/hardware'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',HOST_GU_ONLY_EVIDENCE_DIR=str(out))
 cpus=sorted(os.sched_getaffinity(0))[:8];limit=8*1024**3;floor=64*1024**3
 command=[sys.executable,'-B','-m','unittest','discover','-s','project/hardware/tests','-p',a.pattern,'-v']
 files=[*sorted((ROOT/'project/hardware/host').glob('scalellm_mlp_gu_only*.py')),*sorted((ROOT/'project/hardware/tests').glob('test_scalellm_mlp_gu_only*.py'))]
 files += [ROOT/'project/hardware/host/scalellm_mlp_linear.py',ROOT/'project/hardware/host/scalellm_artifacts.py',ROOT/'project/hardware/host/scalellm_runtime.py',ROOT/'project/hardware/model/mlp_fixed.py',ROOT/'project/hardware/source/mlp_linear/abi_gu_only.json',ROOT/'PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md',ROOT/'project/hardware/data/mlp_silu_q16.mem',Path(__file__)]
 identities={str(x.relative_to(ROOT)):sha(x) for x in files};snap=out/'snapshots';snap.mkdir()
 for path in files:
  if path.suffix=='.py':(snap/path.name).write_bytes(path.read_bytes())
 before=available();assert before>=floor,'available memory below64GiB'
 metadata=dict(started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),root=str(ROOT),command=command,python=sys.version,platform=platform.platform(),source_sha256=identities,affinity=cpus,limits=dict(rss_bytes=limit,mem_available_floor=floor),mem_available_before=before,environment={k:env[k] for k in ['PYTHONPATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','HOST_GU_ONLY_EVIDENCE_DIR']},scope='CPU synthetic integer/runtime tests; no real32-layer model, EDA/GPU/board result')
 (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
 def setup():os.sched_setaffinity(0,cpus);resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
 started=time.monotonic();peak=0;lowest=before;stop=None
 with (out/'unittest.log').open('w') as log:
  proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=setup)
  while proc.poll() is None:
   lowest=min(lowest,available())
   try:
    status=Path(f'/proc/{proc.pid}/status').read_text().splitlines();rss=next((int(x.split()[1])*1024 for x in status if x.startswith('VmRSS:')),0);peak=max(peak,rss)
   except FileNotFoundError:pass
   if peak>limit or lowest<floor:
    stop='resource_protection';os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10);break
   time.sleep(.1)
  code=proc.wait()
 metadata.update(ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,native_exit_code=code,stop_reason=stop,peak_rss_sampled_bytes=peak,child_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,mem_available_lowest=lowest,inputs_unchanged=all(sha(ROOT/key)==value for key,value in identities.items()),outputs_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'})
 (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
 print(out);print((out/'unittest.log').read_text());return code if stop is None else 2
if __name__=='__main__':raise SystemExit(main())
