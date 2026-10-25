#!/usr/bin/env python3
"""Owned, bounded-resource XSim execution with immutable per-attempt evidence."""
import argparse,datetime,fcntl,hashlib,json,os,re,signal,subprocess,time
from pathlib import Path
HW=Path(__file__).resolve().parents[2]
ROOT=HW.parents[1]
E=ROOT/'project/E013_mlp_linear_only_hardware'
BIN=Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin')
GIB=1024**3

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(pid):
 rows={}
 for p in Path('/proc').glob('[0-9]*/status'):
  try:
   a=dict(x.split(':',1) for x in p.read_text().splitlines() if ':' in x)
   rows[int(p.parent.name)]=(int(a['PPid']),int(a.get('VmRSS','0 kB').split()[0])*1024)
  except (OSError,ValueError,KeyError):pass
 ids={pid}
 while True:
  nxt=ids|{k for k,v in rows.items() if v[0] in ids}
  if nxt==ids:break
  ids=nxt
 return ids,sum(rows.get(k,(0,0))[1] for k in ids)

def main():
 a=argparse.ArgumentParser();a.add_argument('top');a.add_argument('tb');a.add_argument('manifest');a.add_argument('attempt');a.add_argument('--define',action='append',default=[]);o=a.parse_args()
 if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',o.top):raise ValueError('top')
 out=E/'experiment_results/runs/R001/attempts'/o.attempt
 out.mkdir(parents=True,exist_ok=False)
 lock=(HW/'vivado/.m006_linear_eda.lock').open('a+')
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 inputs={Path(__file__).resolve()};sources=[]
 def add_list(p):
  p=p.resolve();assert p.is_relative_to(HW) and p.is_file();inputs.add(p)
  for line in p.read_text().splitlines():
   line=line.split('#',1)[0].strip()
   if not line:continue
   q=(HW/line).resolve();assert q.is_relative_to(HW) and q.is_file()
   if q.suffix=='.list':add_list(q)
   else:
    inputs.add(q)
    if q.suffix in ['.sv','.v'] and q not in sources:sources.append(q)
 add_list(HW/o.manifest)
 tb=(HW/o.tb).resolve();assert tb.is_relative_to(HW) and tb.is_file();inputs.add(tb)
 glbl=(BIN/'../data/verilog/src/glbl.v').resolve();inputs.add(glbl)
 # ROMs are runtime inputs. Symlink only current hardware data, never old root.
 (out/'data').symlink_to(HW/'data',target_is_directory=True)
 for p in (HW/'data').glob('*.mem'):inputs.add(p)
 identity={str(p):sha(p) for p in sorted(inputs)}
 (out/'inputs.json').write_text(json.dumps(identity,indent=2)+'\n')
 cpus=sorted(os.sched_getaffinity(0))[:8]
 (out/'resource_contract.json').write_text(json.dumps(dict(cpus=cpus,nice_increment=5,rss_limit=96*GIB,mem_available_floor=64*GIB,mem_low_grace_seconds=30,wall_timeout=None,silence_timeout=None),indent=2)+'\n')
 env={**os.environ,'OMP_NUM_THREADS':'8'}
 results=[]
 def run(name,cmd):
  start=now();low_since=None;peak=0;stop=None
  def setup():os.sched_setaffinity(0,cpus);os.nice(5)
  with (out/(name+'.log')).open('w') as log:
   proc=subprocess.Popen(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=setup)
   (out/'active.json').write_text(json.dumps(dict(phase=name,pid=proc.pid,started=start,argv=cmd),indent=2)+'\n')
   while proc.poll() is None:
    ids,rss=tree(proc.pid);peak=max(peak,rss)
    mem={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')}
    low=mem['MemAvailable']<64*GIB
    low_since=(low_since or time.monotonic()) if low else None
    disk=os.statvfs(out);free=disk.f_bavail*disk.f_frsize
    if rss>96*GIB or free<30*GIB or (low_since and time.monotonic()-low_since>=30):
     stop='resource_protection';os.killpg(proc.pid,signal.SIGTERM)
     try:proc.wait(30)
     except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL)
     break
    time.sleep(.5)
   rc=proc.wait()
  result=dict(phase=name,argv=cmd,started=start,ended=now(),native_returncode=rc,peak_tree_rss_bytes=peak,stop_reason=stop)
  results.append(result);(out/'steps.json').write_text(json.dumps(results,indent=2)+'\n')
  if rc:raise RuntimeError(f'{name} native returncode {rc}')
 try:
  for name in ['xvlog','xelab','xsim']:run(name+'_version',[str(BIN/name),'-version'])
  run('xvlog',[str(BIN/'xvlog'),'-sv','-L','xpm','-L','unisims_ver',*[x for d in o.define for x in ['-d',d]],*[str(p) for p in sources],str(tb),str(glbl)])
  run('xelab',[str(BIN/'xelab'),'-mt','8','-L','xpm','-L','unisims_ver',o.top,'glbl','-s',o.top+'_sim'])
  run('xsim',[str(BIN/'xsim'),o.top+'_sim','-runall'])
  logs='\n'.join((out/(n+'.log')).read_text() for n in ['xvlog','xelab','xsim'])
  assert not re.search(r'\b(ERROR|FATAL|FAIL)\b|\$error',logs,re.I),'error in native log'
  assert (out/'xsim.log').read_text().splitlines().count('HARDWARE_AGENT_SIM_PASS')==1,'missing unique pass'
  assert all(sha(Path(p))==h for p,h in identity.items()),'inputs changed during run'
  verdict='PASS'
 except Exception as ex:
  verdict='FAIL';(out/'exception.txt').write_text(repr(ex)+'\n')
 (out/'result.json').write_text(json.dumps(dict(verdict=verdict,ended=now(),steps=results),indent=2)+'\n')
 print(verdict,out)
 return 0 if verdict=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
