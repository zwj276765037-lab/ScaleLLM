from pathlib import Path
import ast,datetime,hashlib,importlib.util,io,json,os,shutil,subprocess,unittest
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
B=R/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/original_address_selector_v1'
tree=O/'original_address_candidate_cpu_tree'
for d in ['vivado/scripts','vivado/constraints']:(tree/d).mkdir(parents=True,exist_ok=True)
shutil.copyfile(B/'m003_joint_checks.tcl.proposed',tree/'vivado/scripts/m003_joint_checks.tcl')
for f in ['vivado/scripts/m003_system_python.tcl','vivado/constraints/m003_joint_locality_data.tcl']:shutil.copyfile(R/'project/hardware'/f,tree/f)
os.sched_setaffinity(0,set(range(8)));os.nice(5)
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ.pop('HAP_M003_SCRIPTS_DIR',None)
tmp=O/'original_address_selector_cpu_tmp';tmp.mkdir(exist_ok=True);os.environ['TMPDIR']=str(tmp)
def ident(p):
 b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
jobs=[]
def unittest_job(name,suite):
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 p=O/(name+'.log');p.write_text(log.getvalue());jobs.append({'name':name,'started_utc':start,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':result.testsRun,'success':result.wasSuccessful(),'log':ident(p)})
spec=importlib.util.spec_from_file_location('candidate_engineer_tests',B/'test_selector.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
unittest_job('original_address_candidate_engineer6_independent_rerun',unittest.defaultTestLoader.loadTestsFromTestCase(m.Address))
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
p=subprocess.run(['/usr/bin/python3',str(O/'test_original_address_selector_independent.py')],capture_output=True,text=True,cwd=R/'project/hardware',env=dict(os.environ))
log=O/'original_address_candidate_independent6.log';log.write_text(p.stdout+p.stderr);jobs.append({'name':'independent_six_candidate_tests','started_utc':start,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':6,'success':p.returncode==0,'exit_code':p.returncode,'log':ident(log)})
before=ast.parse((R/'project/hardware/tests/test_m003_native_entry_repair.py').read_text())
after=ast.parse((B/'test_m003_native_entry_repair.py.proposed').read_text())
added=[x for x in after.body if isinstance(x,ast.ClassDef) and x.name=='OriginalAddressSelection'];assert len(added)==1
remaining=ast.Module(body=[x for x in after.body if x not in added],type_ignores=[]);assert ast.dump(before,include_attributes=False)==ast.dump(remaining,include_attributes=False)
ns={'Path':Path,'unittest':unittest,'subprocess':subprocess,'HW':tree}
exec(compile(ast.fix_missing_locations(ast.Module(body=added,type_ignores=[])),'proposed_tests_class','exec'),ns)
unittest_job('original_address_candidate_proposed3_independent_rerun',unittest.defaultTestLoader.loadTestsFromTestCase(ns['OriginalAddressSelection']))
receipt={'schema':'A007_original_address_selector_CPU_v1','candidate':ident(B/'m003_joint_checks.tcl.proposed'),'isolated_candidate':ident(tree/'vivado/scripts/m003_joint_checks.tcl'),'jobs':jobs,'all_passed':all(x['success'] for x in jobs),'existing_production_regression_AST_unchanged':True,'independent_source':ident(O/'test_original_address_selector_independent.py'),'bounded_native_reads':'OnlyAT016 small19candidate facts; combined fullAT014 replay accepted from engineering original source/log and prior native reviews, not redundantly rescanned here','cpu_affinity':sorted(os.sched_getaffinity(0)),'nice':os.getpriority(os.PRIO_PROCESS,0),'no_EDA':True}
p=O/'original_address_selector_independent_cpu_receipt.json';p.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));assert receipt['all_passed']
