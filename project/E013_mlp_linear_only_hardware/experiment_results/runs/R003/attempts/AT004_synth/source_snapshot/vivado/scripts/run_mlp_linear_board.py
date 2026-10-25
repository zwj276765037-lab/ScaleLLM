#!/usr/bin/env python3
"""One owned M006 board session, with stage-specific artifact provenance."""
import argparse,fcntl,hashlib,json,os,shutil,signal,subprocess,time
import xml.etree.ElementTree as ET
from pathlib import Path
from run_mlp_linear_sim import now,sha,GIB
HW=Path(__file__).resolve().parents[2];ROOT=HW.parents[1]
VIVADO='/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado'
INPUTS=HW/'vivado/manifests/mlp_linear/input_manifest.json'

def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def xpr_source_identity(project):
 """Bind source settings while allowing Vivado run-status updates."""
 root=ET.parse(project/'scalellm_vcu118_f05.xpr').getroot();selected=[]
 for node in root:
  if node.tag=='Configuration':
   for option in node:
    if option.attrib.get('Name') in {'Part','BoardPart','TargetLanguage','SimulatorLanguage','IPRepoPath','CoreContainer.Enable'}:selected.append(ET.tostring(option,encoding='unicode'))
  elif node.tag=='FileSets':
   for fileset in node:
    if fileset.attrib.get('Type') in {'DesignSrcs','Constrs','BlockSrcs'}:selected.append(ET.tostring(fileset,encoding='unicode'))
 if not selected:raise ValueError('XPR source settings could not be identified')
 return hashlib.sha256('\n'.join(selected).encode()).hexdigest()

def project_inventory(project):
 files={}
 for q in sorted(project.rglob('*')):
  if not q.is_file() or q.name=='m006_constructor_identity.json':continue
  rel=q.relative_to(project)
  if any(part.endswith(('.runs','.cache','.hw')) or part=='.Xil' for part in rel.parts):continue
  if q.suffix=='.xpr':continue
  if any(part.endswith(('.srcs','.gen','.ip_user_files')) for part in rel.parts):files[str(rel)]=sha(q)
 return dict(files=files,xpr_source_sha256=xpr_source_identity(project))

def check_project(project,inventory):
 for rel,h in inventory['files'].items():
  path=(project/rel).resolve()
  if not path.is_relative_to(project) or not path.is_file() or sha(path)!=h:raise ValueError('generated input changed: '+rel)
 if xpr_source_identity(project)!=inventory['xpr_source_sha256']:raise ValueError('XPR design configuration/filesets changed')

def check_artifacts(artifacts):
 for name,h in artifacts.items():
  path=Path(name).resolve()
  if not path.is_relative_to(HW/'vivado/reports') or not path.is_file() or sha(path)!=h:raise ValueError('native stage artifact changed or outside reports: '+name)

def proc_snapshot():
 rows={}
 for path in Path('/proc').glob('[0-9]*/stat'):
  try:
   f=path.read_text().rpartition(')')[2].split()
   if f[0]=='Z':continue
   rss=next((int(line.split()[1])*1024 for line in (path.parent/'status').read_text().splitlines() if line.startswith('VmRSS:')),0)
   rows[int(path.parent.name)]=dict(ppid=int(f[1]),pgid=int(f[2]),sid=int(f[3]),birth=f[19],rss=rss)
  except (OSError,ValueError,IndexError):pass
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['create','synth','impl']);ap.add_argument('attempt');ap.add_argument('--project',type=Path);ap.add_argument('--synth-dcp',type=Path);a=ap.parse_args()
 subprocess.run(['/usr/bin/python3',str(HW/'vivado/scripts/m006_entry.py'),'check'],check=True)
 freeze_sha=sha(INPUTS)
 lock=(HW/'vivado/.m006_linear_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 report=HW/'vivado/reports'/('m006_linear_'+a.attempt);report.mkdir(parents=True,exist_ok=False)
 project=(a.project or HW/'vivado/project'/('m006_linear_'+a.attempt)).resolve()
 if not project.is_relative_to(HW/'vivado/project'):raise ValueError('project outside new root')
 batch='R004' if a.stage=='impl' else 'R003'
 evidence=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs'/batch/'attempts'/a.attempt;evidence.mkdir(parents=True,exist_ok=False)
 (evidence/'native_reports').symlink_to(report,target_is_directory=True)
 cpus=sorted(os.sched_getaffinity(0))[:32]
 env={**os.environ,'HAP_PROJECT_DIR':str(project),'HAP_REPORT_DIR':str(report),'HAP_JOBS':'8','HAP_STAGE':a.stage,'HAP_BOARD_CORE_CLK_MHZ':'100.0','HAP_BOARD_DDR_UI_CLK_HZ':'200000000','HAP_BD_VALIDATE_ONLY':'0','OMP_NUM_THREADS':'8'}
 constructor_path=project/'m006_constructor_identity.json'
 if a.stage!='create':
  constructor=json.loads(constructor_path.read_text())
  if constructor.get('scope')!='validated_bd_generated_ip_wrapper' or constructor['project']!=str(project) or constructor['input_manifest_sha256']!=freeze_sha:raise ValueError('full constructor identity mismatch')
  if json.loads((Path(constructor['constructor_evidence'])/'result.json').read_text())['verdict']!='NATIVE_STAGE_COMPLETED':raise ValueError('constructor attempt did not succeed')
  check_artifacts(constructor['artifacts']);write_json(evidence/'constructor_identity.json',constructor)
  if a.stage=='synth':check_project(project,constructor['inventory'])
 if a.stage=='impl':
  if a.synth_dcp is None:raise ValueError('impl requires --synth-dcp')
  dcp=a.synth_dcp.resolve()
  if not dcp.is_relative_to(HW/'vivado/reports') or not dcp.is_file():raise ValueError('DCP must exist in new-root reports')
  receipt=json.loads((dcp.parent/'m006_synth_identity.json').read_text())
  if receipt.get('verdict')!='NATIVE_STAGE_COMPLETED' or receipt['project']!=str(project) or receipt['input_manifest_sha256']!=freeze_sha or receipt['constructor_sha256']!=sha(constructor_path) or receipt['dcp']!=str(dcp) or receipt['dcp_sha256']!=sha(dcp):raise ValueError('DCP is not the successful matching M006 synthesis artifact')
  if json.loads((Path(receipt['synth_evidence'])/'result.json').read_text())['verdict']!='NATIVE_STAGE_COMPLETED':raise ValueError('synthesis attempt did not succeed')
  check_artifacts(receipt['artifacts']);check_project(project,receipt['inventory']);write_json(evidence/'synth_identity.json',receipt);env['HAP_SYNTH_DCP']=str(dcp)
 elif a.synth_dcp is not None:raise ValueError('--synth-dcp only applies to impl')
 if a.stage!='create':write_json(evidence/'project_inputs.json',project_inventory(project))
 script=HW/'vivado/scripts'/('create_mlp_linear_board.tcl' if a.stage=='create' else 'build_mlp_linear_board.tcl')
 cmd=[VIVADO,'-mode','batch','-notrace','-source',str(script),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
 version=subprocess.run([VIVADO,'-version'],capture_output=True,text=True,check=True);(report/'tool_version.txt').write_text(version.stdout+version.stderr)
 identity=json.loads(INPUTS.read_text());write_json(evidence/'input_manifest.json',identity)
 for rel,h in identity['files'].items():
  src=HW/rel;dst=evidence/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  if sha(dst)!=h:raise ValueError('input changed while snapshotting: '+rel)
 meta=dict(input_manifest_sha256=freeze_sha,stage=a.stage,started=now(),command=cmd,cwd=str(HW/'vivado'),project=str(project),report=str(report),profile='board',cpus=cpus,nice_increment=5,rss_limit_bytes=192*GIB,mem_available_floor_bytes=64*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB,max_threads=8,synth_jobs=4,wall_timeout=None,silence_timeout=None,bd_validate_only=0)
 if a.stage=='impl':meta['synth_dcp']=dict(path=str(dcp),sha256=sha(dcp))
 def setup():os.sched_setaffinity(0,cpus);os.nice(5)
 peak=0;low_since=None;stop=None;owned={}
 def discover():
  rows=proc_snapshot();live={pid for pid,birth in owned.items() if pid in rows and rows[pid]['birth']==birth}
  # Session identity finds children even after the original root exits.
  live|={pid for pid,row in rows.items() if row['sid']==session and int(row['birth'])>=minimum_birth}
  while True:
   extra={pid for pid,row in rows.items() if row['ppid'] in live}
   if extra<=live:break
   live|=extra
  for pid in live:owned.setdefault(pid,rows[pid]['birth'])
  live={pid for pid in live if rows[pid]['birth']==owned[pid]}
  return live,sum(rows[pid]['rss'] for pid in live)
 with (report/'console.log').open('w') as log:
  p=subprocess.Popen(cmd,cwd=HW/'vivado',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=setup)
  session=p.pid
  f=Path('/proc',str(p.pid),'stat').read_text().rpartition(')')[2].split();minimum_birth=int(f[19]);owned[p.pid]=f[19]
  meta.update(pid=p.pid,session=session,root_birth=f[19],actual_affinity=sorted(os.sched_getaffinity(p.pid)));write_json(evidence/'launch.json',meta)
  if meta['actual_affinity']!=cpus:raise RuntimeError('CPU affinity setup mismatch')
  while True:
   live,rss=discover();peak=max(peak,rss)
   if p.poll() is not None and not live:break
   mem=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
   low_since=(low_since or time.monotonic()) if mem<64*GIB else None
   disk=os.statvfs(report);free=disk.f_bavail*disk.f_frsize
   if rss>192*GIB or free<30*GIB or (low_since and time.monotonic()-low_since>=30):
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
 changed=[rel for rel,h in identity['files'].items() if not (HW/rel).is_file() or sha(HW/rel)!=h]
 if sha(INPUTS)!=freeze_sha:changed.append('selected_input_manifest.json')
 if a.stage=='impl' and sha(dcp)!=meta['synth_dcp']['sha256']:changed.append('selected_synth_dcp')
 success=rc==0 and stop is None and not changed and not survivors
 result=dict(ended=now(),native_returncode=rc,stop_reason=stop,peak_tree_rss_bytes=peak,changed_inputs=changed,execution_state='completed' if success else 'failed',verdict='NATIVE_STAGE_COMPLETED' if success else 'FAIL')
 if success:
  try:
   inventory=project_inventory(project);write_json(evidence/'project_outputs.json',inventory)
   required=['production_shape.json','elaboration_identity.txt','compile_order_sources.rpt','compile_order_constraints.rpt','constructor_summary.txt'] if a.stage=='create' else ['stage_quality.json','utilization_hierarchical.rpt','timing_summary.rpt','clock_interaction.rpt','cdc.rpt','drc.rpt']
   for name in required:
    if not (report/name).is_file() or not (report/name).stat().st_size:raise ValueError('required native artifact missing/empty: '+name)
   artifacts={str(path):sha(path) for path in sorted(report.rglob('*')) if path.is_file()}
   if a.stage!='create':
    quality=json.loads((report/'stage_quality.json').read_text());write_json(evidence/'stage_quality.json',quality)
    result['quality']=dict(path=str(report/'stage_quality.json'),sha256=artifacts[str(report/'stage_quality.json')],assessment=quality,scope='native-stage quality evidence; independent acceptance required')
   if a.stage=='create':
    if not list(project.glob('*.gen/sources_1/bd/*/hdl/*_wrapper.v')):raise ValueError('full constructor did not produce wrapper')
    receipt=dict(scope='validated_bd_generated_ip_wrapper',project=str(project),input_manifest_sha256=freeze_sha,constructor_evidence=str(evidence),constructor_report=str(report),inventory=inventory,artifacts=artifacts)
   if a.stage=='synth':
    synthesized=report/'synthesized.dcp'
    receipt=dict(verdict='NATIVE_STAGE_COMPLETED',project=str(project),input_manifest_sha256=freeze_sha,constructor_sha256=sha(constructor_path),synth_evidence=str(evidence),dcp=str(synthesized),dcp_sha256=sha(synthesized),inventory=inventory,artifacts=artifacts)
  except Exception as ex:
   success=False;result.update(execution_state='failed',verdict='FAIL',artifact_validation_error=repr(ex))
 # A receipt is issued only after the final qualified native-stage result.
 write_json(evidence/'result.json',result)
 if success and a.stage=='create':write_json(constructor_path,receipt)
 if success and a.stage=='synth':
  write_json(report/'m006_synth_identity.json',receipt);write_json(evidence/'synth_identity.json',receipt)
 for src in project.glob('*.runs/*/runme.log'):
  dst=evidence/'run_logs'/src.parent.name/'runme.log';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 write_json(evidence/'result.json',result);print(json.dumps(result));return 0 if success else 1
if __name__=='__main__':raise SystemExit(main())
