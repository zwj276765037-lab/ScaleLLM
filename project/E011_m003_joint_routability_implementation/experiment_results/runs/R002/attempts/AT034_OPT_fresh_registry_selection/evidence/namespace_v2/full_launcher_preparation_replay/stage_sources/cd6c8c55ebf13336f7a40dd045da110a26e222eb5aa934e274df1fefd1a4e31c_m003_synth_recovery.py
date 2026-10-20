#!/usr/bin/env python3
"""Qualify AT003's successful new netlists in a distinct post-report attempt."""
from pathlib import Path
import argparse, datetime, json, re, shutil
import m003_entry as entry
import m002_physical_evidence as old

ROOT=entry.ROOT
EXPERIMENT=ROOT/'project/E011_m003_joint_routability_implementation'
ORIGIN=EXPERIMENT/'experiment_results/runs/R002/attempts/AT003_fresh_selected_synthesis'
ORIGIN_REPORT=entry.HW/'vivado/reports/m003_E011_R002_AT003_fresh_synth'
RAW=ORIGIN/'evidence/AT003_terminal_and_raw_native_lineage.json'
RAW_SHA='2b43590a2e36204c6628780ba077e9e030f6e10d0f7e579430cce602d8b41e64'
SCHEMA='M003_fresh_native_synthesis_postreport_recovery_v1'
CHANGED={entry.HW/'vivado/scripts'/name for name in (
 'm003_joint_checks.tcl','m003_joint_evidence.py','m003_entry.py','create_vcu118_board.tcl',
 'build_vcu118_board.tcl','m003_physical.tcl','m002_diagnostic_common.tcl',
 'm003_stage.py','run_m003_stage.py','m003_physical_evidence.py')}
CHANGED.update((entry.MANIFEST,entry.HW/'vivado/constraints/m003_joint_locality.xdc'))
ADDITIONS={entry.HW/'vivado/scripts'/name for name in (
 'm003_native_init.py','m003_synth_recovery.py','m003_recover_synthesis.tcl',
 'm003_shared_connectivity.tcl','m003_snapshot_stream.tcl','m003_snapshot_decode.py')}
REPORTS=('utilization_post_synth.rpt','utilization_hierarchical_post_synth.rpt',
 'timing_post_synth.rpt','check_timing_post_synth.rpt','clocks_post_synth.rpt',
 'clock_interaction_post_synth.rpt','cdc_post_synth.rpt','drc_pre_impl.rpt')
RUN_ANCHORS=('native_synthesis_run_metadata.json','native_synthesis_run_qualification.json')

def save(path,value):
 old.require(not path.exists(),'recovery evidence already exists: '+str(path))
 path.write_text(json.dumps(value,indent=2)+'\n')

def validate_delta(prior,current):
 removed=set(prior)-set(current);added=set(current)-set(prior)
 old.require(not removed and added==ADDITIONS,'recovery source closure changed outside the exact declared entry helper closure')
 changed={p for p in prior if prior[p]['sha256']!=current[p]['sha256']}
 old.require(changed<=CHANGED,'recovery modified a synthesis/design source outside the entry-only repair')
 return dict(changed=sorted(map(str,changed)),added=sorted(map(str,added)))

def verify_origin(project):
 entry.check_sources();old.require(old.sha256(RAW)==RAW_SHA,'original failed-attempt raw lineage changed')
 raw=json.loads(RAW.read_text())
 old.require(raw['native_exit_code']==1 and raw['stop_reason'] is None and not raw['owned_survivors'] and raw['run_count']==23 and raw['consumed_count']==22,'original native/postreport states changed')
 for key in ('raw_status','native_log','source_archive'):old.verify_identity(raw[key])
 archive=json.loads(Path(raw['source_archive']['path']).read_text())['bindings']
 for row in archive:old.verify_identity(row['preserved'])
 manifest=[r for r in archive if r['original']['path']==str(entry.MANIFEST)]
 old.require(len(manifest)==1,'original source manifest missing from immutable archive')
 prior={Path(r['path']):r for r in json.loads(Path(manifest[0]['preserved']['path']).read_text())['sources']}
 current={Path(r['path']):r for r in entry.check_sources()['sources']}
 delta=validate_delta(prior,current)
 input_changes=[]
 for row in raw['build_input_checks']:
  path=Path(row['path']);digest=old.sha256(path)
  if digest!=row['sha256']:
   old.require(path in CHANGED,'original production synthesis input changed: '+str(path))
   preserved=[r for r in archive if r['original']['path']==str(path) and r['original']['sha256']==row['sha256']]
   old.require(len(preserved)==1,'changed entry input has no original byte archive')
   input_changes.append(dict(path=str(path),before_sha256=row['sha256'],after_sha256=digest,preserved=preserved[0]['preserved']))
 for row in raw['run_records']:
  old.require(Path(row['checkpoint']['path']).is_relative_to(project/'scalellm_vcu118_f05.runs'),'foreign fresh synthesis producer')
  old.verify_identity(row['checkpoint']);old.verify_identity(row['end'])
  old.require(not (Path(row['end']['path']).parent/'.vivado.error.rst').exists(),'fresh synthesis producer has an error marker')
 for row in raw['produced_consumed']:
  old.verify_identity(row['produced']);old.verify_identity(row['consumed'])
  old.require(Path(row['consumed']['path']).is_relative_to(project/'scalellm_vcu118_f05.gen') and row['produced']['sha256']==row['consumed']['sha256'],'original consumed checkpoint is not the fresh produced netlist')
 return dict(original_failed_attempt=str(ORIGIN),original_report=str(ORIGIN_REPORT),raw_lineage=old.file_id(RAW),original_native_exit_code=1,original_records_modified=False,source_delta=delta,input_changes=input_changes,raw=raw)

def prepare(project,report):
 origin=verify_origin(project)
 inherited=[]
 for name in REPORTS:
  source=ORIGIN_REPORT/name;target=report/name
  old.require(not target.exists(),'inherited report already exists');shutil.copyfile(source,target)
  old.require(old.sha256(source)==old.sha256(target),'inherited raw report copy changed')
  inherited.append(dict(original=old.file_id(source),preserved=old.file_id(target)))
 paths={Path(r['path']) for r in origin['raw']['build_input_checks']}
 paths.update(Path(r['path']) for r in entry.check_sources()['sources']);paths.add(entry.MANIFEST)
 (report/'inputs.sha256').write_text(''.join(old.sha256(p)+'  '+str(p)+'\n' for p in sorted(paths)))
 origin.pop('raw')
 value=dict(schema=SCHEMA,project=str(project),origin=origin,inherited_raw_reports=inherited,
  reports_scope='AT003 original same-RTL post_synth reports; selected native graph/apply requalified in the new attempt',
  input_manifest=old.file_id(report/'inputs.sha256'),new_source_manifest=old.file_id(entry.MANIFEST))
 save(report/'postreport_recovery_inputs.json',value);return value

def compare_identity(report):
 before=old.key_values(ORIGIN_REPORT/'build_identity.txt');after=old.key_values(report/'build_identity.txt')
 old.require(set(before)==set(after),'build identity registry/key inventory changed')
 changed=[]
 for key,value in before.items():
  if after[key]==value:continue
  old.require(key.startswith('file.') and str(entry.HW/'vivado/constraints/m003_joint_locality.xdc') in value and value.endswith(':XDC:0:1') and after[key]==value[:-len(':XDC:0:1')]+':TCL:0:1','build parameter/clock/ABI/synthesis registry changed: '+key)
  changed.append(key)
 old.require(len(changed)==1,'expected precisely one implementation-only XDC-to-TCL identity change')
 return dict(passed=True,changed_keys=changed,original=old.file_id(ORIGIN_REPORT/'build_identity.txt'),current=old.file_id(report/'build_identity.txt'))

def check_run_metadata(records,run_records):
 expected={r['run']:str(Path(r['checkpoint']['path']).parent) for r in run_records}
 old.require(len(expected)==23 and len(records)==23,'recovered native run inventory must be23')
 names=[r.get('NAME') for r in records]
 old.require(len(set(names))==23 and set(names)==set(expected),'recovered native run names missing, duplicate or foreign')
 stale=[]
 for row in records:
  name=row['NAME'];status=row.get('STATUS','');refresh=str(row.get('NEEDS_REFRESH','')).lower()
  old.require(row.get('DIRECTORY')==expected[name] and row.get('PROGRESS')=='100%','recovered native run incomplete or foreign directory: '+name)
  complete='Complete' in status and refresh in ('0','false','no')
  metadata_stale=status=='Out-of-date' and refresh in ('1','true','yes')
  old.require(complete or metadata_stale,'recovered native run status is not completed or attributed metadata stale: '+name)
  if metadata_stale:stale.append(name)
 return sorted(stale)

def admit_runs(project,report,synth_report=None,synth_attempt=None):
 origin=verify_origin(project)
 if synth_report is None:
  old.require(synth_attempt is None,'partial recovered synthesis lineage')
  compare_identity(report)
 else:
  old.require(synth_attempt is not None,'missing recovered synthesis attempt')
  package=json.loads((synth_attempt/'M003_frozen_synthesis.json').read_text())
  old.require(package['schema']==SCHEMA,'stale exception is only for explicit recovered synthesis')
  lineage(project,synth_report,synth_attempt,package)
  old.require(old.sha256(report/'effective_build_identity.txt')==old.sha256(synth_report/'build_identity.txt'),'recovered physical build identity changed')
 metadata=report/RUN_ANCHORS[0]
 stale=check_run_metadata(json.loads(metadata.read_text()),origin['raw']['run_records'])
 value=dict(schema='M003_original_native_run_content_qualification_v1',passed=True,
  project=str(project),source_manifest=old.file_id(entry.MANIFEST),raw_lineage=old.file_id(RAW),
  native_metadata=old.file_id(metadata),actual_stale_runs=stale,
  native_status_modified=False,new_synthesis_launched=False,
  qualification='Original AT003 native23 completed producers/22 consumed DCPs and all production synthesis inputs remain exact; real metadata stale retained',
  synth_package=old.file_id(synth_attempt/'M003_frozen_synthesis.json') if synth_attempt else None)
 save(report/RUN_ANCHORS[1],value);return value

def verify_run_receipt(project,report,origin):
 path=report/RUN_ANCHORS[1];row=json.loads(path.read_text());metadata=report/RUN_ANCHORS[0]
 old.require(row['schema']=='M003_original_native_run_content_qualification_v1' and row['passed'] is True and row['project']==str(project) and row['native_status_modified'] is False and row['new_synthesis_launched'] is False,'recovered native run receipt changed')
 old.require(row['source_manifest']==old.file_id(entry.MANIFEST) and row['raw_lineage']==old.file_id(RAW) and row['native_metadata']==old.file_id(metadata),'recovered native run receipt source binding changed')
 old.require(row['actual_stale_runs']==check_run_metadata(json.loads(metadata.read_text()),origin['raw']['run_records']),'recovered native run metadata changed')
 return old.file_id(path)

def native_finish(project,report):
 origin=verify_origin(project);old.input_manifest(report/'inputs.sha256');compare_identity(report);applied=entry.check_apply(report)
 runs=verify_run_receipt(project,report,origin)
 for name in ('m003_qualification_synth.json','m003_same_stage_budget.json'):
  old.require(json.loads((report/name).read_text())['passed'],'recovered selected native structure/budget did not pass')
 value=dict(schema=SCHEMA,native_selected_postreport_completed=True,new_synthesis_launched=False,
  original_failed_attempt=str(ORIGIN),original_native_exit_code=1,actual_overlay_apply=applied,native_run_qualification=runs,
  created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 save(report/'M003_postreport_qualification_complete.json',value);return value

def freeze(project,report,attempt,job):
 origin=verify_origin(project);status=attempt/'evidence/jobs'/job/'status.json';state=json.loads(status.read_text())
 old.require(state['native_exit_code']==0 and not state['stop_reason'] and not state['owned_survivors'],'new postreport qualification did not close natively')
 launch=json.loads((report/'launcher_status.json').read_text());old.require(launch['stage']=='recover-synth' and launch['native_exit_code']==0 and launch['project']==str(project),'new native recovery launcher mismatch')
 complete=json.loads((report/'M003_postreport_qualification_complete.json').read_text());old.require(complete['native_selected_postreport_completed'] and complete['original_native_exit_code']==1 and complete['new_synthesis_launched'] is False,'recovery may not invent a fresh synthesis attempt success')
 pairs=origin['raw']['produced_consumed'];expected={(r['cell'],r['consumed']['path'],r['consumed']['sha256']) for r in pairs};current=set()
 for line in (report/'vivado.log').read_text(errors='replace').splitlines():
  match=re.search(r"Reading design checkpoint '([^']+)' for cell '([^']+)'",line)
  if match:current.add((match[2],match[1],old.sha256(Path(match[1]))))
 old.require(current==expected and len(current)==22,'new selected graph did not actually load all22 fresh produced dependencies')
 entry.check_apply(report);compare_identity(report);verify_run_receipt(project,report,origin);inputs=old.input_manifest(report/'inputs.sha256')
 for name in ('m003_qualification_synth.json','m003_same_stage_budget.json'):old.require(json.loads((report/name).read_text())['passed'],'new selected graph or same-stage budget failed')
 anchors=[old.file_id(report/n) for n in ('inputs.sha256','build_identity.txt','postreport_recovery_inputs.json','M003_postreport_qualification_complete.json','m003_qualification_synth.json','m003_same_stage_budget.json','launcher_status.json',*RUN_ANCHORS)]+[old.file_id(status),old.file_id(entry.MANIFEST)]
 package=dict(schema=SCHEMA,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),project=str(project),report=str(report),attempt=str(attempt),job=job,G2_sha256=entry.G2,input_count=len(inputs),anchors=anchors,origin={k:v for k,v in origin.items() if k!='raw'},run_records=origin['raw']['run_records'],produced_consumed=pairs,current_native_consumed_count=len(current),source_log=old.file_id(report/'vivado.log'))
 save(attempt/'M003_frozen_synthesis.json',package);return package

def lineage(project,report,attempt,package):
 old.require(package['project']==str(project) and package['report']==str(report) and package['attempt']==str(attempt) and package['G2_sha256']==entry.G2,'recovered synthesis package identity changed')
 origin=verify_origin(project)
 old.require(package['run_records']==origin['raw']['run_records'] and package['produced_consumed']==origin['raw']['produced_consumed'] and package['origin']=={k:v for k,v in origin.items() if k!='raw'} and package['current_native_consumed_count']==22,'recovered native producer/consumer/original failure provenance changed')
 status=attempt/'evidence/jobs'/package['job']/'status.json';state=json.loads(status.read_text())
 old.require(state['native_exit_code']==0 and not state['stop_reason'] and not state['owned_survivors'],'recovered native qualification status changed')
 verify_run_receipt(project,report,origin)
 expected=[old.file_id(report/n) for n in ('inputs.sha256','build_identity.txt','postreport_recovery_inputs.json','M003_postreport_qualification_complete.json','m003_qualification_synth.json','m003_same_stage_budget.json','launcher_status.json',*RUN_ANCHORS)]+[old.file_id(status),old.file_id(entry.MANIFEST)]
 old.require(package['anchors']==expected,'recovered qualification anchor inventory changed')
 for row in package['anchors']:old.verify_identity(row)
 old.verify_identity(package['source_log']);old.input_manifest(report/'inputs.sha256')
 return dict(schema=SCHEMA,project=str(project),report=str(report),attempt=str(attempt),package=old.file_id(attempt/'M003_frozen_synthesis.json'),G2_sha256=entry.G2,input_count=package['input_count'],original_native_exit_code=1,new_postreport_native_exit_code=0)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['compare-identity','native-finish','admit-runs']);parser.add_argument('--project',type=Path);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--synth-report',type=Path);parser.add_argument('--synth-attempt',type=Path);a=parser.parse_args()
 if a.action=='compare-identity':value=compare_identity(a.report)
 elif a.action=='admit-runs':value=admit_runs(a.project,a.report,a.synth_report,a.synth_attempt)
 else:value=native_finish(a.project,a.report)
 print(json.dumps(value))
