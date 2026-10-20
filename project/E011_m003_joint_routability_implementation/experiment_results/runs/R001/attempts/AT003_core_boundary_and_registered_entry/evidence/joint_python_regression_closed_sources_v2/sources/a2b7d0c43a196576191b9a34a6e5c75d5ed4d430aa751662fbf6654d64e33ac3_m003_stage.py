#!/usr/bin/env python3
"""M003 selected-version source, fresh synthesis, stage and checkpoint lineage."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys
import m003_entry as entry
import m002_physical_evidence as old
HW=Path(__file__).resolve().parents[2]
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def freeze_synth(project,report,attempt,job):
 entry.check_sources();status=json.loads((attempt/'evidence/jobs'/job/'status.json').read_text())
 old.require(status['native_exit_code']==0 and not status['stop_reason'] and not status['owned_survivors'],'new M003 synthesis did not close natively')
 old.status_id(report/'launcher_status.txt','synth',project);inputs=old.input_manifest(report/'inputs.sha256')
 old.identity(report/'build_identity.txt') if hasattr(old,'identity') else None
 runs=[];produced={};log=report/'vivado.log';text=log.read_text(errors='replace')
 for directory in sorted((project/'scalellm_vcu118_f05.runs').glob('*synth_1')):
  name=directory.name
  if name!='synth_1' and not name.startswith('scalellm_vcu118_f05_bd_'):continue
  cp=directory/('scalellm_vcu118_f05_bd_wrapper.dcp' if name=='synth_1' else name.removesuffix('_synth_1')+'.dcp')
  end=directory/'.vivado.end.rst';old.require(cp.is_file() and end.is_file() and not(directory/'.vivado.error.rst').exists(),'actual new synth run not complete')
  runs.append(dict(run=name,checkpoint=old.file_id(cp),end_receipt=old.file_id(end)));old.require(cp.name not in produced,'duplicate produced DCP');produced[cp.name]=cp
 consumed=[]
 for number,line in enumerate(text.splitlines(),1):
  m=re.search(r"Reading design checkpoint '([^']+)' for cell '([^']+)'",line)
  if m:consumed.append(dict(line=number,path=m[1],cell=m[2]))
 old.require(len(runs)==23 and len(consumed)==22,'actual fixed board synth graph must be23/22')
 pairs=[]
 for row in consumed:
  p=Path(row['path']);source=produced[p.name]
  old.require(p.is_relative_to(project/'scalellm_vcu118_f05.gen') and old.sha256(p)==old.sha256(source),'consumed checkpoint does not equal fresh produced OOC')
  pairs.append(dict(produced=old.file_id(source),consumed=old.file_id(p),cell=row['cell'],line=row['line']))
 for name in ['m003_qualification_synth.json','m003_same_stage_budget.json']:
  old.require(json.loads((report/name).read_text())['passed'],'selected synth structure/budget failure')
 files=[report/n for n in ['inputs.sha256','build_identity.txt','fresh_synth_complete.txt','board_evidence.json','m003_qualification_synth.json','m003_same_stage_budget.json']]+[attempt/'evidence/jobs'/job/'status.json',entry.MANIFEST]
 package=dict(schema='M003_fresh_synthesis_v1',created_utc=now(),project=str(project),report=str(report),attempt=str(attempt),job=job,G2_sha256=entry.G2,input_count=len(inputs),anchors=[old.file_id(p) for p in files],run_records=runs,produced_consumed=pairs,source_log=old.file_id(log))
 target=attempt/'M003_frozen_synthesis.json';old.require(not target.exists(),'new synth package already frozen');save(target,package);return package

def lineage(project,report,attempt):
 entry.check_sources();p=attempt/'M003_frozen_synthesis.json';x=json.loads(p.read_text())
 old.require(x['schema']=='M003_fresh_synthesis_v1' and x['project']==str(project) and x['report']==str(report) and x['G2_sha256']==entry.G2,'new M003 synth package identity mismatch')
 for r in x['anchors']:old.verify_identity(r)
 # Verify actual native produced/consumed DCP identity records; no old-DCP reuse.
 for r in x['run_records']:
  old.verify_identity(r['checkpoint']);old.verify_identity(r['end_receipt'])
 for r in x['produced_consumed']:old.verify_identity(r['produced']);old.verify_identity(r['consumed'])
 old.input_manifest(report/'inputs.sha256')
 return dict(schema=x['schema'],project=str(project),report=str(report),attempt=str(attempt),package=old.file_id(p),G2_sha256=entry.G2,input_count=x['input_count'])

def prepare_sources(report,synth=None):
 entry.check_sources();paths={Path(e['path']) for e in entry.check_sources()['sources']}
 paths.update(Path(__file__).parent.glob('m003_*'));paths.update(Path(__file__).parent.glob('m002_*.tcl'))
 paths.update([Path(__file__).parent/'m002_physical_evidence.py',Path(__file__).parent/'m002_synthesis_recovery.py',Path(__file__).parent/'m002_fresh_project_opt_recovery.py',Path(__file__).parent/'m002_execution_profile.py',Path(__file__).parent/'emit_current_board_evidence.py',entry.MANIFEST])
 if synth:paths.update(old.input_manifest(synth/'inputs.sha256'))
 archive=report/'stage_sources';archive.mkdir();lines=[];bound=[]
 for p in sorted(paths):
  ident=old.file_id(p);q=archive/(ident['sha256']+'_'+p.name);shutil.copyfile(p,q);old.require(old.sha256(q)==ident['sha256'],'archive changed');lines.append(ident['sha256']+'  '+str(p)+'\n');bound.append(dict(original=ident,preserved=old.file_id(q)))
 (report/'stage_inputs.sha256').write_text(''.join(lines));save(report/'source_archive.json',bound)

def preplace(report):
 x=old.pre_place_evidence(report,create=True)
 old.require(json.loads((report/'m003_qualification_debug_materialized.json').read_text())['passed'],'M003 preplace selected structure failed')
 save(report/'M003_preplace_package.json',dict(schema='M003_preplace_v1',checkpoint=old.file_id(report/'debug_materialized.dcp'),pre_place=old.file_id(report/'pre_place_evidence.json'),constraints=old.file_id(report/'constraints_debug_materialized.json'),source_manifest=old.file_id(entry.MANIFEST),selection=old.file_id(report/'m003_qualification_debug_materialized.json'),G2_sha256=entry.G2,physical_signoff=False))
 return x

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze-synth','lineage','preplace']);p.add_argument('--project',type=Path);p.add_argument('--report',type=Path,required=True);p.add_argument('--attempt',type=Path);p.add_argument('--job',default='fresh_synth');a=p.parse_args()
 if a.action=='freeze-synth':x=freeze_synth(a.project,a.report,a.attempt,a.job)
 elif a.action=='lineage':x=lineage(a.project,a.report,a.attempt)
 else:x=preplace(a.report)
 print(json.dumps(x))
if __name__=='__main__':main()
