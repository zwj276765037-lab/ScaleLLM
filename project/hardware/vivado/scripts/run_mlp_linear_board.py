#!/usr/bin/env python3
"""One owned M006 board session, with stage-specific artifact provenance."""
import argparse,difflib,fcntl,hashlib,json,os,re,shutil,signal,subprocess,time
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

def validate_qualification_origin(path,freeze_sha):
 """One explicit recovery of AT004's identity-probe failure, never any FAIL."""
 path=path.resolve();scope=ROOT/'project/E013_mlp_linear_only_hardware/experiment_source/dcp_qualification'
 if not path.is_relative_to(scope):raise ValueError('qualification record outside its evidence scope')
 record=json.loads(path.read_text());origin_path=Path(record['origin_record']).resolve()
 if not origin_path.is_relative_to(scope) or sha(origin_path)!=record['origin_record_sha256']:raise ValueError('qualification origin record changed')
 origin=json.loads(origin_path.read_text());parent=Path(origin['origin_evidence']).resolve()
 expected=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT004_synth'
 if origin.get('schema')!=1 or origin.get('scope')!='AT004_identity_probe_requalification' or parent!=expected:raise ValueError('only the explicit AT004 identity-probe recovery is supported')
 for name,h in {**origin['evidence_hashes'],**origin['native_synth_log_hashes']}.items():
  source=Path(name).resolve()
  if not source.is_relative_to(parent) or sha(source)!=h:raise ValueError('origin evidence changed: '+name)
 check_artifacts(origin['artifact_hashes'])
 result=json.loads((parent/'result.json').read_text())
 if result.get('verdict')!='FAIL' or result.get('native_returncode')!=1 or result.get('stop_reason') is not None or result.get('changed_inputs'):raise ValueError('origin is not the preserved diagnostic-probe failure')
 if json.loads((parent/'owned_processes.json').read_text()).get('survivors'):raise ValueError('origin left owned processes')
 logs=origin['native_synth_log_hashes']
 if len(logs)!=23 or any('synth_design completed successfully' not in Path(n).read_text(errors='replace') for n in logs):raise ValueError('22 OOC plus top successful native synthesis logs required')
 report=Path(origin['origin_report']);quality=json.loads((report/'stage_quality.json').read_text())
 if quality['process']['status']!='NATIVE_STAGE_COMPLETED' or quality['netlist']['attention_cells']!=0 or quality['netlist']['shared_kernel_cells']!=0 or quality['netlist']['blackbox_cells']!=1:raise ValueError('origin failure is outside the documented probe mismatch')
 if 'blackboxes.cell=dbg_hub ref=dbg_hub_CV' not in (report/'netlist_identity.txt').read_text() or 'M006 required native netlist/clock identity failed' not in (report/'vivado.log').read_text():raise ValueError('origin probe failure evidence missing')
 old_manifest=parent/'input_manifest.json'
 if sha(old_manifest)!=origin['parent_input_manifest_sha256']:raise ValueError('origin input manifest changed')
 old=json.loads(old_manifest.read_text());current=json.loads(INPUTS.read_text())
 if {k:v for k,v in old.items() if k!='files'}!={k:v for k,v in current.items() if k!='files'} or old['files'].keys()!=current['files'].keys():raise ValueError('production shape/source graph/baseline/dependency membership changed')
 changes={r:dict(parent_sha256=h,current_sha256=current['files'][r]) for r,h in old['files'].items() if h!=current['files'][r]}
 constraints={'vivado/constraints/ddr_timing_recovery.xdc','vivado/constraints/mlp_linear_physical.xdc'}
 drivers={'vivado/scripts/run_mlp_linear_board.py','vivado/scripts/build_mlp_linear_board.tcl'}
 if set(changes)!=constraints|drivers or record.get('changes')!=changes or record.get('current_input_manifest_sha256')!=freeze_sha:raise ValueError('qualification changes differ from the exact four-file patch')
 for rel,h in old['files'].items():
  if sha(parent/'source_snapshot'/rel)!=h:raise ValueError('origin source snapshot changed: '+rel)
 for rel in constraints:
  lines=(parent/'source_snapshot'/rel).read_bytes().splitlines(keepends=True)
  diagnostic=[line for line in lines if re.fullmatch(rb'puts \{[^{}\r\n]*\}\r?\n?',line)]
  if len(diagnostic)!=1 or (HW/rel).read_bytes()!=b''.join(l for l in lines if l not in diagnostic):raise ValueError('effective constraint changed: '+rel)
 for rel in drivers:
  patch=scope/record['patches'][rel]['path']
  if not patch.resolve().is_relative_to(scope) or sha(patch)!=record['patches'][rel]['sha256']:raise ValueError('driver patch evidence changed')
  exact=''.join(difflib.unified_diff((parent/'source_snapshot'/rel).read_text().splitlines(True),(HW/rel).read_text().splitlines(True),fromfile='parent/'+rel,tofile='current/'+rel))
  if patch.read_text()!=exact:raise ValueError('driver differs from exact recorded patch: '+rel)
 project=Path(origin['project']).resolve()
 if not project.is_relative_to(HW/'vivado/project') or sha(project/'m006_constructor_identity.json')!=origin['constructor_sha256']:raise ValueError('constructor provenance changed')
 check_project(project,json.loads((parent/'post_failure_generated_inventory.json').read_text()))
 dcp=Path(origin['dcp']).resolve()
 if not dcp.is_relative_to(report) or sha(dcp)!=origin['dcp_sha256']:raise ValueError('origin synthesized DCP changed')
 for key,count in [('pre_opt_no_clock_pins',530),('pre_opt_unconstrained_endpoints',554)]:
  if len(origin[key])!=count or any('/u_ddr_cal_top/u_ddr_cal/' not in p or not p.startswith('scalellm_vcu118_f05_bd_i/ddr4_') for p in origin[key]):raise ValueError('debug target set changed or broadened')
 return dict(record=str(path),record_sha256=sha(path),origin_record=str(origin_path),origin_record_sha256=sha(origin_path),origin=origin,verified_changes=changes,scope='same_DCP_native_identity_requalification_original_FAIL_preserved')

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
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['create','synth','qualify','impl']);ap.add_argument('attempt');ap.add_argument('--project',type=Path);ap.add_argument('--synth-dcp',type=Path);ap.add_argument('--qualification-origin',type=Path);a=ap.parse_args()
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
 qualification=None;constructor_freeze=freeze_sha
 if a.stage=='qualify':
  if a.qualification_origin is None or a.synth_dcp is None:raise ValueError('qualify requires --qualification-origin and --synth-dcp')
  qualification=validate_qualification_origin(a.qualification_origin,freeze_sha);origin=qualification['origin']
  if origin['project']!=str(project) or str(a.synth_dcp.resolve())!=origin['dcp']:raise ValueError('qualification project/DCP differ from recorded native origin')
  constructor_freeze=origin['parent_input_manifest_sha256']
 elif a.qualification_origin is not None:raise ValueError('--qualification-origin only applies to qualify')
 if a.stage=='impl':
  if a.synth_dcp is None:raise ValueError('impl requires --synth-dcp')
  early_receipt=json.loads((a.synth_dcp.resolve().parent/'m006_synth_identity.json').read_text())
  constructor_freeze=early_receipt.get('constructor_input_manifest_sha256',freeze_sha)
  if constructor_freeze!=freeze_sha and early_receipt.get('scope')!='qualified_existing_synthesis_dcp':raise ValueError('constructor/source transition lacks successful native qualification')
 if a.stage!='create':
  constructor=json.loads(constructor_path.read_text())
  if constructor.get('scope')!='validated_bd_generated_ip_wrapper' or constructor['project']!=str(project) or constructor['input_manifest_sha256']!=constructor_freeze:raise ValueError('full constructor identity mismatch')
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
 elif a.stage=='qualify':
  dcp=report/'synthesized.dcp';shutil.copy2(a.synth_dcp,dcp)
  if sha(dcp)!=origin['dcp_sha256']:raise ValueError('qualification DCP copy changed')
  source_report=Path(origin['origin_report'])
  for name in ['utilization_hierarchical.rpt','timing_summary.rpt','clock_interaction.rpt','cdc.rpt','drc.rpt','check_timing.rpt','drc_native_objects.txt']:
   shutil.copy2(source_report/name,report/name)
   if sha(report/name)!=origin['artifact_hashes'][str(source_report/name)]:raise ValueError('reused report changed: '+name)
  shutil.copy2(source_report/'stage_quality.json',report/'inherited_stage_quality.json')
  write_json(report/'qualification_origin.json',origin);write_json(report/'qualification_validation.json',qualification)
  transition=json.loads(a.qualification_origin.read_text())
  for rel,patch in transition['patches'].items():shutil.copy2(a.qualification_origin.parent/patch['path'],report/(Path(rel).name+'.qualification.patch'))
  shutil.copy2(a.qualification_origin,report/'qualification_transition.json')
  env.update(HAP_SYNTH_DCP=str(dcp),HAP_PARENT_QUALITY=str(report/'inherited_stage_quality.json'))
  write_json(report/'driver_diagnostics.json',dict(recovery='M002 core100/UI200; no added timing exceptions or placement',linear='M006 linear hierarchy; no unverified placement or timing exception',scope='Literal diagnostic messages moved out of XDC; exact deletion validated'))
 elif a.synth_dcp is not None:raise ValueError('--synth-dcp only applies to impl/qualify')
 if a.stage=='impl':
  debug_targets=receipt.get('qualification_origin')
  if not debug_targets or sha(Path(debug_targets['path']))!=debug_targets['sha256']:raise ValueError('post-opt debug target provenance missing or changed')
  env['HAP_DEBUG_TARGETS']=debug_targets['path']
 if a.stage!='create':write_json(evidence/'project_inputs.json',project_inventory(project))
 script=HW/'vivado/scripts'/('create_mlp_linear_board.tcl' if a.stage=='create' else 'build_mlp_linear_board.tcl')
 cmd=[VIVADO,'-mode','batch','-notrace','-source',str(script),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
 version=subprocess.run([VIVADO,'-version'],capture_output=True,text=True,check=True);(report/'tool_version.txt').write_text(version.stdout+version.stderr)
 identity=json.loads(INPUTS.read_text());write_json(evidence/'input_manifest.json',identity)
 for rel,h in identity['files'].items():
  src=HW/rel;dst=evidence/'source_snapshot'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  if sha(dst)!=h:raise ValueError('input changed while snapshotting: '+rel)
 meta=dict(input_manifest_sha256=freeze_sha,stage=a.stage,started=now(),command=cmd,cwd=str(HW/'vivado'),project=str(project),report=str(report),profile='board',cpus=cpus,nice_increment=5,rss_limit_bytes=192*GIB,mem_available_floor_bytes=64*GIB,mem_low_grace_seconds=30,disk_floor_bytes=30*GIB,max_threads=8,synth_jobs=4,wall_timeout=None,silence_timeout=None,bd_validate_only=0)
 if a.stage in {'impl','qualify'}:meta['synth_dcp']=dict(path=str(dcp),sha256=sha(dcp))
 if qualification is not None:meta['qualification_origin']=qualification
 if a.stage=='impl':meta['synth_receipt_sha256']=sha(dcp.parent/'m006_synth_identity.json')
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
 if a.stage in {'impl','qualify'} and sha(dcp)!=meta['synth_dcp']['sha256']:changed.append('selected_synth_dcp')
 if qualification is not None and sha(a.qualification_origin)!=qualification['record_sha256']:changed.append('selected_qualification_transition')
 if a.stage=='impl' and sha(dcp.parent/'m006_synth_identity.json')!=meta['synth_receipt_sha256']:changed.append('selected_synth_receipt')
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
   if a.stage in {'synth','qualify'}:
    synthesized=report/'synthesized.dcp'
    receipt=dict(verdict='NATIVE_STAGE_COMPLETED',scope='qualified_existing_synthesis_dcp' if a.stage=='qualify' else 'native_synthesis',project=str(project),input_manifest_sha256=freeze_sha,constructor_input_manifest_sha256=constructor_freeze,constructor_sha256=sha(constructor_path),synth_evidence=str(evidence),dcp=str(synthesized),dcp_sha256=sha(synthesized),inventory=inventory,artifacts=artifacts)
    if a.stage=='qualify':receipt['qualification_origin']=dict(path=str(report/'qualification_origin.json'),sha256=sha(report/'qualification_origin.json'),validation=qualification)
  except Exception as ex:
   success=False;result.update(execution_state='failed',verdict='FAIL',artifact_validation_error=repr(ex))
 # A receipt is issued only after the final qualified native-stage result.
 write_json(evidence/'result.json',result)
 if success and a.stage=='create':write_json(constructor_path,receipt)
 if success and a.stage in {'synth','qualify'}:
  write_json(report/'m006_synth_identity.json',receipt);write_json(evidence/'synth_identity.json',receipt)
 for src in project.glob('*.runs/*/runme.log'):
  dst=evidence/'run_logs'/src.parent.name/'runme.log';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 write_json(evidence/'result.json',result);print(json.dumps(result));return 0 if success else 1
if __name__=='__main__':raise SystemExit(main())
