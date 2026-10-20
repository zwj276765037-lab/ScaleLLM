from pathlib import Path
import subprocess,json,datetime,os,hashlib,sys
ROOT=Path(__file__).resolve().parents[3];HW=ROOT/'project/hardware';AT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R001/attempts/AT003_core_boundary_and_registered_entry'
OUT=AT/'evidence/joint_python_regression_correct_path';OUT.mkdir(exist_ok=False)
modules=['test_attention_cohort16_integration_contract','test_attention_two_wave_reuse_contract','test_v5_schedule_contract','test_v5_gate_up_gather_contract','test_mlp_fixed','test_scalellm_reference','test_vcu118_builder_sources','test_vcu118_builder_rom_staging','test_m002_full_implementation','test_m002_optimized_implementation','test_m002_physical_diagnostic','test_m002_pre_place_recovery','test_m002_fresh_project_opt_recovery','test_m003_joint_qualification']
paths=[HW/'tests'/(m+'.py') for m in modules]+list((HW/'model').glob('*.py'))
manifest=HW/'vivado/constraints/m003_entry_manifest.json';selection=json.loads(manifest.read_text());paths+=[Path(e['path']) for e in selection['sources']]+[manifest,Path(__file__),Path(__file__).parent/'protocol.md']
archive=OUT/'sources';archive.mkdir();bindings=[]
for p in sorted(set(paths)):
 sha=hashlib.sha256(p.read_bytes()).hexdigest();target=archive/(sha+'_'+p.name);target.write_bytes(p.read_bytes());bindings.append(dict(path=str(p),sha256=sha,preserved=str(target)))
os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
cmd=['python3','-m','unittest','-v']+['tests.'+m for m in modules];started=datetime.datetime.now(datetime.timezone.utc).isoformat();env={**os.environ,'PYTHONPATH':str(HW/'tests')+':'+str(HW)}
r=subprocess.run(cmd,cwd=HW,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(OUT/'native.log').write_text(r.stdout)
unchanged=all(hashlib.sha256(Path(e['path']).read_bytes()).hexdigest()==e['sha256'] for e in bindings)
(OUT/'receipt.json').write_text(json.dumps(dict(command=cmd,environment={'PYTHONPATH':env['PYTHONPATH']},started_utc=started,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=r.returncode,source_bindings=bindings,source_unchanged=unchanged,native_EDA=False,scope='same selected version bounded models/algorithm/build/qualification fixtures; not timing or complete board command'),indent=2)+'\n');print(r.stdout[-6000:]);print('EXIT',r.returncode,'SOURCES_UNCHANGED',unchanged)
sys.exit(r.returncode if unchanged else 1)
