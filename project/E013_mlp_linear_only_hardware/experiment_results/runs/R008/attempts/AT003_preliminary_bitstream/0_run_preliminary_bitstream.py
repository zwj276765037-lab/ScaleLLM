#!/usr/bin/env python3
"""User-prioritized engineering-validation bitstream, with open signoff limits recorded."""
import argparse,fcntl,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];HW=ROOT/'project/hardware'
sys.path.insert(0,str(HW/'vivado/scripts'))
from run_mlp_gu_board import proc_snapshot,VIVADO
from run_mlp_gu_sim import now,sha,GIB
PARENT=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl'

def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def terminal_gate(result,owned):
 rc=result.get('native_returncode')
 if type(rc) is not int or rc not in (0,1):raise ValueError('parent did not exit naturally with rc0/1')
 if result.get('stop_reason') is not None or result.get('changed_inputs')!=[]:raise ValueError('parent stopped or inputs drifted')
 if owned.get('survivors')!=[]:raise ValueError('parent still has owned survivors')
 if result.get('execution_state') not in ('completed','failed'):raise ValueError('parent is not terminal')
 if result.get('execution_state')!=('completed' if result.get('verdict')=='NATIVE_STAGE_COMPLETED' else 'failed'):raise ValueError('parent execution/verdict mismatch')
 if rc==1 and result.get('verdict')!='FAIL':raise ValueError('parent rc1/verdict mismatch')
 if rc==0 and result.get('verdict') not in ('FAIL','NATIVE_STAGE_COMPLETED'):raise ValueError('parent rc0/verdict mismatch')
 # Natural FAIL remains FAIL; this program issues no synthesis/implementation receipt.

def parent_identity(anchor_path):
 result=json.loads((PARENT/'result.json').read_text());owned=json.loads((PARENT/'owned_processes.json').read_text());terminal_gate(result,owned)
 if result['native_returncode']!=0 or result['verdict']!='NATIVE_STAGE_COMPLETED':raise ValueError('preliminary bitstream requires the successful routed parent')
 q=result['quality']['assessment']
 if any(q[k]['status']!='PASS' for k in ['route','netlist','clocks','gu_structure']) or q['timing']['setup']['status']!='PASS' or q['timing']['hold']['status']!='PASS':raise ValueError('routed parent lacks route/synchronous STA/native identity')
 if anchor_path.parent!=PARENT or anchor_path.name!='routed_checkpoint_observation.json':raise ValueError('only original R008 native checkpoint observations are accepted')
 a=json.loads(anchor_path.read_text());launch=json.loads((PARENT/'launch.json').read_text())
 dcp=Path(a['dcp']).resolve();report=Path(launch['report']).resolve()
 if report!=HW/'vivado/reports/m006_gu_AT001_impl' or dcp.parent!=report or dcp.name!='routed.dcp':raise ValueError('DCP outside original R008 report')
 if a['input_manifest_sha256']!=launch['input_manifest_sha256'] or sha(PARENT/'input_manifest.json')!=launch['input_manifest_sha256']:raise ValueError('parent input identity mismatch')
 if sha(dcp)!=a['dcp_sha256']:raise ValueError('native checkpoint changed since original export observation')
 log=report/'console.log';prefix=log.read_bytes()[:a['native_log_prefix_bytes']]
 if hashlib.sha256(prefix).hexdigest()!=a['native_log_prefix_sha256'] or f"The checkpoint '{dcp}' has been generated.".encode() not in prefix:raise ValueError('native checkpoint historical export anchor changed')
 manifest=json.loads((PARENT/'input_manifest.json').read_text())
 for rel,h in manifest['files'].items():
  f=(HW/rel).resolve()
  if not f.is_relative_to(HW) or not f.is_file() or sha(f)!=h:raise ValueError('parent production input changed: '+rel)
 return dict(parent=str(PARENT),parent_result_sha256=sha(PARENT/'result.json'),parent_result=result,parent_owned_sha256=sha(PARENT/'owned_processes.json'),anchor=str(anchor_path),anchor_sha256=sha(anchor_path),dcp=str(dcp),dcp_sha256=a['dcp_sha256'],phase=a['phase'],input_manifest_sha256=launch['input_manifest_sha256'],native_log_sha256=sha(log),preliminary_bitstream_no_parent_quality_promotion=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('attempt');ap.add_argument('--anchor',type=Path,required=True);args=ap.parse_args()
 if not args.attempt or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.attempt):raise ValueError('invalid attempt')
 lock=(HW/'vivado/.m006_linear_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 anchor=args.anchor.resolve();identity=parent_identity(anchor)
 here=Path(__file__).resolve().parent;script=here/'write_preliminary_bitstream.tcl';prep=here/'cpu_preparation.json';cancellation=PARENT.parent/'AT002_terminal_bus_skew_query/priority_cancellation_receipt.json'
 prepared=json.loads(prep.read_text())
 if sha(script)!=prepared['script_sha256']:raise ValueError('prepared bitstream script changed')
 if identity['dcp_sha256']!='cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4':raise ValueError('unexpected original routed checkpoint')
 c=json.loads(cancellation.read_text())
 if c.get('reason')!='USER_PRIORITIZED_PRELIMINARY_BITSTREAM' or c.get('owned_survivors')!=[] or not c.get('lock_released'):raise ValueError('prior optional query not safely closed')
 report=HW/'vivado/reports'/('m006_gu_'+args.attempt);report.mkdir(exist_ok=False)
 evidence=PARENT.parent/args.attempt;evidence.mkdir(exist_ok=False);(evidence/'native_reports').symlink_to(report,target_is_directory=True)
 sources=[Path(__file__).resolve(),script,prep,cancellation,HW/'vivado/scripts/run_mlp_gu_board.py',HW/'vivado/scripts/run_mlp_gu_sim.py']
 hashes={str(f):sha(f) for f in sources}
 for i,f in enumerate(sources):shutil.copy2(f,evidence/(str(i)+'_'+f.name))
 write_json(evidence/'parent_identity.json',identity);write_json(evidence/'source_hashes.json',hashes)
 cpus=sorted(os.sched_getaffinity(0))[:32]
 command=[VIVADO,'-mode','batch','-notrace','-source',str(script),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',identity['dcp'],str(report/'native_output')]
 env={**os.environ,'OMP_NUM_THREADS':'8'}
 launch=dict(started=now(),command=command,cwd=str(HW/'vivado'),profile='board_preliminary_bitstream',cpus=cpus,nice_increment=5,rss_limit_bytes=192*GIB,mem_available_floor_bytes=64*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB,max_threads=8,wall_timeout=None,silence_timeout=None,parent_identity=identity)
 def setup():os.sched_setaffinity(0,cpus);os.nice(5)
 owned={};peak=0;stop=None;low_since=None
 def discover():
  rows=proc_snapshot();live={pid for pid,birth in owned.items() if pid in rows and rows[pid]['birth']==birth}
  live|={pid for pid,row in rows.items() if row['sid']==session and int(row['birth'])>=birth_min}
  while True:
   extra={pid for pid,row in rows.items() if row['ppid'] in live}
   if extra<=live:break
   live|=extra
  for pid in live:owned.setdefault(pid,rows[pid]['birth'])
  live={pid for pid in live if rows[pid]['birth']==owned[pid]}
  return live,sum(rows[pid]['rss'] for pid in live)
 with (report/'console.log').open('w') as log:
  p=subprocess.Popen(command,cwd=HW/'vivado',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=setup);session=p.pid
  birth=Path('/proc',str(p.pid),'stat').read_text().rpartition(')')[2].split()[19];birth_min=int(birth);owned[p.pid]=birth
  launch.update(pid=p.pid,session=session,root_birth=birth,actual_affinity=sorted(os.sched_getaffinity(p.pid)));write_json(evidence/'launch.json',launch)
  if launch['actual_affinity']!=cpus:raise RuntimeError('native CPU affinity mismatch')
  while True:
   live,rss=discover();peak=max(peak,rss)
   if p.poll() is not None and not live:break
   mem=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'));low_since=(low_since or time.monotonic()) if mem<64*GIB else None
   disk=os.statvfs(report)
   if rss>192*GIB or disk.f_bavail*disk.f_frsize<30*GIB or (low_since and time.monotonic()-low_since>=30):
    stop='resource_protection';deadline=time.monotonic()+30
    while live:
     sig=signal.SIGTERM if time.monotonic()<deadline else signal.SIGKILL
     for pid in live:
      try:os.kill(pid,sig)
      except ProcessLookupError:pass
     time.sleep(.5);live,_=discover()
    break
   time.sleep(2)
  rc=p.wait()
 survivors,_=discover();write_json(evidence/'owned_processes.json',dict(pids=owned,survivors=sorted(survivors),session=session))
 changed=[n for n,h in hashes.items() if not Path(n).is_file() or sha(Path(n))!=h]
 try:
  if parent_identity(anchor)!=identity:changed.append('parent_identity_revalidation')
 except Exception as ex:changed.append('parent_identity_revalidation:'+repr(ex))
 completed=rc==0 and stop is None and not survivors and not changed and 'NATIVE_GU_PRELIMINARY_BITSTREAM_COMPLETED' in (report/'console.log').read_text(errors='replace')
 bit=report/'native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit'
 completed=completed and bit.is_file() and bit.stat().st_size>0
 tool_version=subprocess.run([VIVADO,'-version'],capture_output=True,text=True,check=True);(report/'tool_version.txt').write_text(tool_version.stdout+tool_version.stderr)
 artifacts={str(f):sha(f) for f in sorted(report.rglob('*')) if f.is_file()}
 result=dict(ended=now(),native_returncode=rc,stop_reason=stop,peak_tree_rss_bytes=peak,changed_inputs=changed,execution_state='completed' if completed else 'failed',verdict='PRELIMINARY_BITSTREAM_GENERATED_SIGNOFF_OPEN' if completed else 'FAIL',parent_verdict_unchanged=identity['parent_result']['verdict'],artifacts=artifacts)
 write_json(evidence/'result.json',result)
 if completed:
  manifest=dict(scope='ENGINEERING_VALIDATION_PRELIMINARY_NOT_FOR_BOARD_DOWNLOAD',bitstream=dict(path=str(bit),bytes=bit.stat().st_size,sha256=sha(bit)),native=dict(result_path=str(evidence/'result.json'),result_sha256=sha(evidence/'result.json'),returncode=rc,stop=stop,survivors=sorted(survivors)),parent_routed=identity,tool_version=str(report/'tool_version.txt'),source_hashes=hashes,limitations=['User three-domain clock_groups masks intended Max-DPO; design section12 correction remains pending.','External reset input/output signoff remains open.','No FPGA programming, board download, GPU or model accuracy execution authorized by this file generation.'],native_checks='Normal write_bitstream checks; no severity downgrade or DRC bypass; original parent quality FAIL retained.')
  write_json(evidence/'bitstream_manifest.json',manifest);write_json(report/'bitstream_manifest.json',manifest)
 print(json.dumps(dict(verdict=result['verdict'],native_returncode=rc,stop=stop,changed_inputs=changed,peak_tree_rss_bytes=peak,bitstream=str(bit) if completed else None)));return 0 if completed else 1
if __name__=='__main__':raise SystemExit(main())
