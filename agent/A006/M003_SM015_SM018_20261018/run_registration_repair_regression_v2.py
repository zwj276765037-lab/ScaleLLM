from pathlib import Path
import json,os,subprocess,hashlib,datetime,shutil,sys
R=Path('.').resolve();H=R/'project/hardware';E=R/'project/E011_m003_joint_routability_implementation';P=E/'experiment_source/R002_native_entry_fix/v2/qualified_regression_v2';P.mkdir();(P/'sources').mkdir()
mods=['tests.test_m003_joint_qualification','tests.test_m003_native_entry_repair']
files={Path(x['path']) for x in json.loads((H/'vivado/constraints/m003_entry_manifest.json').read_text())['sources']};files.add(H/'vivado/constraints/m003_entry_manifest.json');files.update(H/(m.replace('.','/')+'.py') for m in mods);files.add(E/'experiment_results/runs/R002/attempts/AT007_native_tcl_and_complete_init_prefix_probe/evidence/native_init_driver_preserved/type_probe.tcl')
def fid(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
rows=[]
for f in sorted(files):
 x=fid(f);q=P/'sources'/(x['sha256']+'_'+f.name);shutil.copyfile(f,q);rows.append(dict(original=x,preserved=fid(q)))
cmd=[sys.executable,'-m','unittest','-v',*mods];start=datetime.datetime.now(datetime.timezone.utc).isoformat();env={**os.environ,'PYTHONPATH':str(H)+':'+str(H/'tests'),'OMP_NUM_THREADS':'8','OPENBLAS_NUM_THREADS':'1'}
with (P/'unittest.log').open('w') as log:p=subprocess.run(cmd,cwd=H,env=env,stdout=log,stderr=subprocess.STDOUT)
unchanged=all(fid(Path(x['original']['path']))==x['original'] for x in rows)
x=dict(command=cmd,cwd=str(H),started_utc=start,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=p.returncode,source_unchanged=unchanged,bindings=rows,scope='Affected entry/builder/safety tests plus native repair name-selection/apply/INIT/constraint-read/source-delta tests; no native G4 substitute')
(P/'receipt.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(dict(receipt=fid(P/'receipt.json'),exit_code=p.returncode,source_unchanged=unchanged,tail=(P/'unittest.log').read_text().splitlines()[-18:])));sys.exit(0 if p.returncode==0 and unchanged else 1)
