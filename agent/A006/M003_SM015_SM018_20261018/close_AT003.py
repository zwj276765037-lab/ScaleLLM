from pathlib import Path
import json,hashlib,datetime,re,fcntl,os
R=Path('.').resolve();E=R/'project/E011_m003_joint_routability_implementation';A=E/'experiment_results/runs/R002/attempts/AT003_fresh_selected_synthesis';J=A/'evidence/jobs/fresh_synth';P=R/'project/hardware/vivado/project/scalellm_m003_E011_R002_AT002';D=R/'project/hardware/vivado/reports/m003_E011_R002_AT003_fresh_synth'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def fid(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def save(p,x):assert not p.exists(),p;p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=json.loads((J/'status.json').read_text());b=json.loads((J/'started.json').read_text());assert s['native_exit_code']==1 and s['stop_reason'] is None and not s['owned_survivors']
archive=json.loads((J/'source_archive.json').read_text())['bindings'];checks=[]
for x in archive:
 row=dict(path=x['original']['path'],original_matches=sha(Path(x['original']['path']))==x['original']['sha256'],preserved_matches=sha(Path(x['preserved']['path']))==x['preserved']['sha256']);checks.append(row)
assert all(x['original_matches'] and x['preserved_matches'] for x in checks)
inputs=[]
for line in (D/'inputs.sha256').read_text().splitlines():
 digest,path=line.split('  ',1);p=Path(path);inputs.append(dict(path=path,sha256=digest,current_matches=sha(p)==digest))
assert all(x['current_matches'] for x in inputs)
runs=[];produced={}
for directory in sorted((P/'scalellm_vcu118_f05.runs').glob('*synth_1')):
 cp=directory/('scalellm_vcu118_f05_bd_wrapper.dcp' if directory.name=='synth_1' else directory.name.removesuffix('_synth_1')+'.dcp');end=directory/'.vivado.end.rst';assert cp.is_file() and end.is_file() and not(directory/'.vivado.error.rst').exists();id=fid(cp);produced[cp.name]=id;runs.append(dict(run=directory.name,checkpoint=id,end=fid(end)))
pairs=[]
for i,line in enumerate((D/'vivado.log').read_text(errors='replace').splitlines(),1):
 m=re.search(r"Reading design checkpoint '([^']+)' for cell '([^']+)'",line)
 if m:
  cp=Path(m[1]);id=fid(cp);src=produced[cp.name];assert id['sha256']==src['sha256'];pairs.append(dict(produced=src,consumed=id,cell=m[2],line=i))
assert len(runs)==23 and len(pairs)==22
lock=(R/'project/hardware/vivado/.m002_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
x=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution_state='failed',native_exit_code=1,stop_reason=None,owned_survivors={},single_EDA_lock_available=True,core_RTL_unchanged=s['core_RTL_unchanged_during_job'],source_archive_count=len(checks),source_checks=checks,build_input_count=len(inputs),build_input_checks=inputs,run_count=len(runs),consumed_count=len(pairs),run_records=runs,produced_consumed=pairs,raw_status=fid(J/'status.json'),native_log=fid(D/'vivado.log'),source_archive=fid(J/'source_archive.json'),scope='Native synthesis23 produced/22 consumed succeeded; outer selected post-report qualification failed. Not qualified synthesis/G4.',failures=['XDC custom Tcl file/info/source/::m003::apply rejected Designutils20-1307; effective overlay not established','payload selector admitted parent_count_r_reg[0]; strict resolver failed naturally'])
p=A/'evidence/AT003_terminal_and_raw_native_lineage.json';save(p,x)
r=json.loads((E/'experiment_source/R002_AT003_running_registration.json').read_text());r.update(execution_state='failed',finished_at=s['ended_utc'],exit_status=1,scope=x['scope']+' '+str(x['failures']),evidence=[str(p.relative_to(R)),str((J/'status.json').relative_to(R)),str((J/'started.json').relative_to(R)),str((J/'source_archive.json').relative_to(R))]);save(E/'experiment_source/R002_AT003_terminal_registration.json',r)
print(json.dumps(dict(receipt=fid(p),source_archive_count=len(checks),build_input_count=len(inputs),runs=len(runs),consumed=len(pairs),max_RSS_GiB=s['max_RSS_bytes']/2**30),ensure_ascii=False))
