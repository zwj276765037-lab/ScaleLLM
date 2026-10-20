#!/usr/bin/env python3
"""CPU-only actual process/log/lock startup receipt; never controls native EDA."""
import argparse,datetime,fcntl,hashlib,json,os,re
from pathlib import Path

def ident(p):
 return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def process(pid):
 try:
  parts=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
  return dict(pid=int(pid),start_ticks=int(parts[19]),state=parts[0],ppid=int(parts[1]),pgrp=int(parts[2]),nice=int(parts[16]),affinity=sorted(os.sched_getaffinity(int(pid))),exe=os.readlink(f'/proc/{pid}/exe'))
 except FileNotFoundError:return None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',type=Path,required=True);at=ap.parse_args().attempt.resolve()
 root=next(p for p in at.parents if (p/'.research-agent/project.json').is_file())
 assert not (at/'native_start_observed.json').exists(),'Append-only observed startup'
 assert not (at/'status.json').exists(),'Native terminal already exists'
 started=json.loads((at/'started.json').read_text())
 lines=(at/'evidence/native/vivado.log').read_text().splitlines()
 matches=[re.match(r'^SM013 (\S+) OPEN_CHECKPOINT_BEGIN$',s) for s in lines];matches=[m for m in matches if m]
 assert len(matches)==1,'Native OPEN_CHECKPOINT_BEGIN absent/nonunique'
 resources=json.loads((at/'resources.jsonl').read_text().splitlines()[-1]);native=[]
 for pid in resources['processes']:
  pr=process(pid)
  if pr and pr['exe'].endswith('/vivado'):native.append(pr)
 assert len(native)==1,native
 procs=[process(started['supervisor_pid']),process(started['leader_pid']),native[0]]
 assert procs[0]['start_ticks']==started['supervisor_start_ticks'] and procs[1]['start_ticks']==started['leader_start_ticks']
 for p in procs:assert p['state']!='Z' and p['nice']==5 and p['affinity']==list(range(8)),p
 lockpath=root/'project/hardware/vivado/.m002_eda.lock';stat=lockpath.stat()
 locks=[line for line in Path('/proc/locks').read_text().splitlines() if ' FLOCK ' in line and line.split()[4]==str(started['supervisor_pid']) and line.split()[5].endswith(':'+str(stat.st_ino))]
 assert len(locks)==1,locks
 with lockpath.open('r') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:busy=True
  else:fcntl.flock(f,fcntl.LOCK_UN);busy=False
 assert busy,'EDA lock unexpectedly free'
 value=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),native_start_utc=matches[0].group(1),native_pid=native[0]['pid'],processes=procs,unique_eda_lock_busy=busy,native_supervisor_lock_records=locks,latest_resources={k:v for k,v in resources.items()},prepared_manifest_sha256=json.loads((at/'independent_prelaunch_accepted.json').read_text())['prepared_manifest']['sha256'],input_bindings=ident(at/'input_bindings.json'),scope='SM013 same R001 AT003 singleton scalar property fix; unchanged full census and endpoint query, full native alias qualification/G1 pending',producer=ident(Path(__file__)))
 with (at/'native_start_observed.json').open('x') as f:f.write(json.dumps(value,indent=2)+'\n')
 print(json.dumps(value,indent=2))
if __name__=='__main__':main()
