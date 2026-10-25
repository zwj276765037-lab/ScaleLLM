#!/usr/bin/env python3
"""Independent routed-copy constraint qualification; preserves the delivered bitstream."""
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
 return dict(parent=str(PARENT),parent_result_sha256=sha(PARENT/'result.json'),parent_result=result,parent_owned_sha256=sha(PARENT/'owned_processes.json'),anchor=str(anchor_path),anchor_sha256=sha(anchor_path),dcp=str(dcp),dcp_sha256=a['dcp_sha256'],phase=a['phase'],input_manifest_sha256=launch['input_manifest_sha256'],native_log_sha256=sha(log),constraint_qualification_no_parent_quality_promotion=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('attempt');ap.add_argument('--anchor',type=Path,required=True);args=ap.parse_args()
 if not args.attempt or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.attempt):raise ValueError('invalid attempt')
 lock=(HW/'vivado/.m006_linear_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 anchor=args.anchor.resolve();identity=parent_identity(anchor)
 here=Path(__file__).resolve().parent;script=here/'qualify_routed_constraints.tcl';helper=here/'constraint_tools.py';prep=here/'cpu_preparation.json';bit_receipt=PARENT.parent/'AT003_preliminary_bitstream/delivery_receipt.json'
 prepared=json.loads(prep.read_text())
 if sha(script)!=prepared['script_sha256'] or sha(helper)!=prepared['helper_sha256'] or sha(here/'constraint_replay_identity.py')!=prepared['replay_comparator_sha256']:raise ValueError('prepared qualification sources changed')
 for name,key in [('capture_role_probe.tcl','probe_sha256'),('capture_role_classifier.py','classifier_sha256'),('role_model_sources.json','role_models_sha256')]:
  if sha(here/name)!=prepared[key]:raise ValueError('prepared role classification source changed: '+name)
 if identity['dcp_sha256']!='cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4':raise ValueError('unexpected original routed checkpoint')
 b=json.loads(bit_receipt.read_text())
 if b.get('scope')!='PRELIMINARY_BITSTREAM_DELIVERY_SIGNOFF_OPEN' or not b.get('zero_survivors') or not b.get('lock_released') or sha(Path(b['bitstream']['path']))!=b['bitstream']['sha256']:raise ValueError('preliminary bitstream delivery must precede qualification')
 bit_result=bit_receipt.parent/'result.json';bit_manifest=bit_receipt.parent/'bitstream_manifest.json';bit_owned=bit_receipt.parent/'owned_processes.json'
 if sha(bit_result)!=b['native_result_sha256'] or sha(bit_manifest)!=b['manifest_sha256'] or sha(bit_owned)!=b['owned_processes_sha256']:raise ValueError('delivered bitstream native receipt chain changed')
 br=json.loads(bit_result.read_text())
 if br['native_returncode']!=0 or br['stop_reason'] is not None or br['changed_inputs']!=[] or br['verdict']!='PRELIMINARY_BITSTREAM_GENERATED_SIGNOFF_OPEN' or json.loads(bit_owned.read_text())['survivors']!=[]:raise ValueError('bitstream did not finish cleanly')
 identity['delivered_bitstream']=b['bitstream'];identity['bitstream_delivery_receipt_sha256']=sha(bit_receipt)
 baseline=PARENT.parent/'AT004_routed_constraint_qualification';baseline_result=baseline/'result.json';baseline_launch=baseline/'launch.json';baseline_owned=baseline/'owned_processes.json';baseline_sources=baseline/'source_hashes.json'
 br0=json.loads(baseline_result.read_text());bl0=json.loads(baseline_launch.read_text());bo0=json.loads(baseline_owned.read_text())
 if br0['native_returncode']!=1 or br0['stop_reason'] is not None or br0['changed_inputs']!=[] or br0['verdict']!='FAIL' or bo0['survivors']!=[]:raise ValueError('unexpected AT004 original-baseline boundary')
 if bl0['parent_identity']['dcp_sha256']!=identity['dcp_sha256']:raise ValueError('AT004 baseline DCP mismatch')
 old_report=HW/'vivado/reports/m006_gu_AT004_routed_constraint_qualification';baseline_clock=old_report/'native_output/original_clock_identity.txt';baseline_sync=old_report/'native_output/original_same_clock_paths.txt';baseline_log=old_report/'console.log'
 if 'capture category omitted by complement predicate: ddr0 data' not in baseline_log.read_text() or 'CQ_STAGE ZERO_DIFFERENCE_REPLAY_STARTED' in baseline_log.read_text():raise ValueError('AT004 did not stop at the known pre-mutation inclusion gate')
 old_hashes=json.loads(baseline_sources.read_text());old_script=ROOT/'project/E013_mlp_linear_only_hardware/experiment_source/gu_only/cdc_constraint_qualification/qualify_routed_constraints.tcl'
 if old_hashes.get(str(old_script))!='98d0054bb5c63a1022bea54b6c0e84069389029a2d8ad1580213456422b52c29':raise ValueError('unknown AT004 baseline source')
 for f in [baseline_clock,baseline_sync]:
  if br0['artifacts'].get(str(f))!=sha(f):raise ValueError('closed AT004 baseline artifact changed')
 if len(baseline_clock.read_text().splitlines())!=50 or len(baseline_sync.read_text().splitlines())!=100:raise ValueError('incomplete original same-clock baseline')
 identity['reused_original_baseline']=dict(scope='ONLY_CLOSED_ORIGINAL_CLOCK_AND_SAME_CLOCK_EXTREMA_NO_FAILED_QUALIFICATION_INHERITED',failed_attempt=str(baseline),result_sha256=sha(baseline_result),clock_sha256=sha(baseline_clock),sync_sha256=sha(baseline_sync),unchanged_routed_dcp_sha256=identity['dcp_sha256'])
 report=HW/'vivado/reports'/('m006_gu_'+args.attempt);report.mkdir(exist_ok=False)
 evidence=PARENT.parent/args.attempt;evidence.mkdir(exist_ok=False);(evidence/'native_reports').symlink_to(report,target_is_directory=True)
 sources=[Path(__file__).resolve(),script,helper,here/'constraint_replay_identity.py',here/'capture_role_probe.tcl',here/'capture_role_classifier.py',here/'role_model_sources.json',prep,here/'test_constraint_tools.py',here/'cpu_helper_check.json',here/'cpu_execution.json',here/'cpu_stdout.log',bit_receipt,bit_result,bit_manifest,bit_owned,baseline_result,baseline_launch,baseline_owned,baseline_sources,baseline_clock,baseline_sync,baseline_log,HW/'vivado/scripts/run_mlp_gu_board.py',HW/'vivado/scripts/run_mlp_gu_sim.py']
 sources += [Path(row['path']) for row in json.loads((here/'role_model_sources.json').read_text())['models'].values()]
 hashes={str(f):sha(f) for f in sources}
 for i,f in enumerate(sources):shutil.copy2(f,evidence/(str(i)+'_'+f.name))
 write_json(evidence/'parent_identity.json',identity);write_json(evidence/'source_hashes.json',hashes)
 cpus=sorted(os.sched_getaffinity(0))[:32]
 command=[VIVADO,'-mode','batch','-notrace','-source',str(script),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',identity['dcp'],str(report/'native_output'),sys.executable,str(helper),str(HW/'vivado/reports/m006_gu_AT001_impl/timing_summary.rpt'),str(baseline_clock),str(baseline_sync)]
 env={**os.environ,'OMP_NUM_THREADS':'8'}
 launch=dict(started=now(),command=command,cwd=str(HW/'vivado'),profile='board_same_routed_constraint_qualification',cpus=cpus,nice_increment=5,rss_limit_bytes=192*GIB,mem_available_floor_bytes=64*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB,max_threads=8,wall_timeout=None,silence_timeout=None,parent_identity=identity)
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
  checked=parent_identity(anchor)
  if any(checked[k]!=identity[k] for k in checked):changed.append('parent_identity_revalidation')
  if sha(Path(b['bitstream']['path']))!=b['bitstream']['sha256']:changed.append('delivered_bitstream_changed')
 except Exception as ex:changed.append('parent_identity_revalidation:'+repr(ex))
 completed=rc==0 and stop is None and not survivors and not changed and 'NATIVE_GU_ROUTED_CONSTRAINT_QUALIFICATION_COMPLETED' in (report/'console.log').read_text(errors='replace')
 qualified=report/'native_output/corrected_routed.dcp'
 completed=completed and qualified.is_file() and qualified.stat().st_size>0
 physical=None
 if completed:
  comparison=subprocess.run([sys.executable,str(helper),'compare-physical',identity['dcp'],str(qualified)],capture_output=True,text=True)
  (report/'physical_identity_comparison.json').write_text(comparison.stdout or json.dumps(dict(status='FAIL',native_stderr=comparison.stderr)))
  completed=completed and comparison.returncode==0
  if comparison.returncode==0:physical=json.loads(comparison.stdout)
 tool_version=subprocess.run([VIVADO,'-version'],capture_output=True,text=True,check=True);(report/'tool_version.txt').write_text(tool_version.stdout+tool_version.stderr)
 artifacts={str(f):sha(f) for f in sorted(report.rglob('*')) if f.is_file()}
 result=dict(ended=now(),native_returncode=rc,stop_reason=stop,peak_tree_rss_bytes=peak,changed_inputs=changed,execution_state='completed' if completed else 'failed',verdict='SAME_ROUTED_CONSTRAINT_QUALIFIED_EXTERNAL_RESET_OPEN' if completed else 'FAIL',parent_verdict_unchanged=identity['parent_result']['verdict'],artifacts=artifacts)
 write_json(evidence/'result.json',result)
 if completed:
  manifest=dict(scope='SAME_ROUTED_COPY_CONSTRAINT_QUALIFICATION_EXTERNAL_RESET_OPEN',qualified_checkpoint=dict(path=str(qualified),bytes=qualified.stat().st_size,sha256=sha(qualified)),delivered_bitstream_unchanged=b['bitstream'],physical_identity=physical,native=dict(result_path=str(evidence/'result.json'),result_sha256=sha(evidence/'result.json'),returncode=rc,stop=stop,survivors=sorted(survivors)),parent_routed=identity,tool_version=str(report/'tool_version.txt'),source_hashes=hashes,limitations=['External reset input/output signoff remains open.','Only the four specified handshake scopes and exact138 dynamic D absolute-delay bounds are qualified; no claim for all other asynchronous cuts.','No FPGA programming, board download, GPU or model accuracy execution.'],native_checks='No synthesis/optimization/placement/routing/bitstream regeneration; original parent quality FAIL retained.')
  write_json(evidence/'constraint_qualification_manifest.json',manifest);write_json(report/'constraint_qualification_manifest.json',manifest)
 print(json.dumps(dict(verdict=result['verdict'],native_returncode=rc,stop=stop,changed_inputs=changed,peak_tree_rss_bytes=peak,qualified_checkpoint=str(qualified) if completed else None)));return 0 if completed else 1
if __name__=='__main__':raise SystemExit(main())
