"""A007 new bridge-only CPU tests; no EDA, no original suite rerun."""
from pathlib import Path
import ast,contextlib,copy,hashlib,importlib.util,io,json,os,subprocess,sys,tempfile
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HERE=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/place_write_replica_proof'
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
def identity(p):
 p=Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
# Extract only the prior mock API definitions; skip every previous test case.
source=HERE/'test_cached_collector.py';tree=ast.parse(source.read_text());selected=[]
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='results' for t in node.targets):break
 selected.append(node)
ns={'__file__':str(source),'__name__':'A007_CPU_mock_definitions_only'}
exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),ns)
prefix=ns['prefix'];needle='set code [catch {source $collector} message options]';assert prefix.count(needle)==1
with tempfile.TemporaryDirectory(dir=OUT,prefix='AT005_CPU_increment_') as directory:
 report=Path(directory);checkpoints={}
 for phase in ['physopt','route']:
  p=report/(phase+'.dcp');p.write_text('CPU fixture identity only; not a native DCP: '+phase+'\n');checkpoints[phase]=p
 replacement='\n'.join([
 'set code [catch {',
 ' source {'+str(ROOT/'project/hardware/vivado/scripts/m003_joint_checks.tcl')+'}',
 ' source {'+str(HERE/'runtime_state_collector.tcl')+'}',
 ' m003_collect_actual_write_states physopt $out',
 ' foreach cell $proof_cells {property $cell INIT 1\'b1}',
 ' property clock_object PERIOD 20.000',
 ' m003_collect_actual_write_states route $out',
 '} message options]'])
 script=report/'CPU_runtime_phase_test.tcl';script.write_text(prefix.replace(needle,replacement))
 run=subprocess.run(['tclsh',str(script),'positive',str(report),str(HERE/'query_cached.tcl')],text=True,capture_output=True)
 assert run.returncode==0 and not run.stderr,(run.returncode,run.stderr)
 phases=[]
 for phase in ['physopt','route']:
  rows=[json.loads(s) for s in (report/f'state_{phase}_actual.jsonl').read_text().splitlines()]
  assert len(rows)==108
  counts={kind:sum(r['kind']==kind for r in rows) for kind in ['cell','parent','state_pin','state_clock','memory_root_pin']}
  assert counts=={'cell':12,'parent':12,'state_pin':48,'state_clock':12,'memory_root_pin':24}
  context=json.loads((report/f'state_{phase}_native_context.json').read_text())
  assert context['phase']==phase and context['checkpoint']==str(checkpoints[phase])
  assert all(r['INIT']==("1'b0" if phase=='physopt' else "1'b1") for r in rows if r['kind']=='cell')
  assert all(float(r['PERIOD'])==(10 if phase=='physopt' else 20) for r in rows if r['kind']=='state_clock')
  trace=[json.loads(s) for s in (report/f'state_{phase}_API_trace.jsonl').read_text().splitlines()]
  assert trace[0]['phase']==phase+'_write_state' and trace[-1]['endpoints']=='72' and trace[-1]['groups']=='15'
  calls=[r for r in trace if r['event']=='api_begin']
  assert {api:sum(r['api']==api for r in calls) for api in ['segments','drivers','ports','canonical']}==dict(segments=15,drivers=15,ports=15,canonical=15)
  phases.append(dict(phase=phase,coverage=counts,groups=15,endpoints=72,checkpoint_binding=True,token=trace[0]['token'],fresh_actual_scalar_properties=True))
 assert phases[0]['token']!=phases[1]['token']
 assert not(report/'vivado.log').exists()
# Test only the Python bridge. The original qualifier is a named stub here;
# this is no native proof or rerun of the already accepted full qualifier.
sys.path.insert(0,str(HERE));spec=importlib.util.spec_from_file_location('A007_runtime_bridge',HERE/'runtime_qualify.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original_qualify=module.qualifier.qualify;old_argv=sys.argv[:];old_env=os.environ.get('HAP_M003_CONTINUE_PLACE_PACKAGE');calls=[]
def fake_qualify(snapshot,spec,raw,package,output):
 q=json.loads(package.read_text());calls.append(dict(snapshot=str(snapshot),raw=str(raw),package=q,output=str(output)))
 return dict(passed=case!='qualification_returns_false',errors=[] if case!='qualification_returns_false' else ['CPU specific semantic rejection'])
module.qualifier.qualify=fake_qualify
bridge=[]
try:
 for phase,case in [('restore','positive'),('place','positive'),('physopt','positive'),('route','positive'),('physopt','wrong_context_phase'),('route','wrong_context_checkpoint'),('physopt','wrong_snapshot_phase'),('route','missing_actual_state_rows'),('physopt','qualification_returns_false')]:
  with tempfile.TemporaryDirectory(dir=OUT,prefix='AT005_CPU_bridge_') as directory:
   r=Path(directory);parent=r/'original_place.dcp';parent.write_text('CPU fixture only original place')
   current=parent if phase in ['restore','place'] else r/(phase+'.dcp')
   if current!=parent:current.write_text('CPU fixture only current '+phase)
   oldpkg=r/'selection.json';oldpkg.write_text(json.dumps(dict(bindings=[],selection_cells=['CPU_fixture_only'],checkpoint=identity(parent))))
   p=r/'continuation.json';p.write_text(json.dumps(dict(bindings=[],checkpoint=identity(parent),selection_package=identity(oldpkg))))
   snapshot=r/f'm003_native_{phase}.json';snapshot.write_text(json.dumps(dict(meta=dict(phase='place' if case=='wrong_snapshot_phase' else phase))))
   raw=r/f'state_{phase}_actual.jsonl'
   if case!='missing_actual_state_rows':raw.write_text('{"CPU_fixture_only":true}\n')
   context=r/f'state_{phase}_native_context.json';context.write_text(json.dumps(dict(phase='place' if case=='wrong_context_phase' else phase,new_state_query='true',selected_cells='12',selected_root_pins='24',checkpoint=str(parent if case=='wrong_context_checkpoint' else current),design='CPU_fixture_only')))
   os.environ['HAP_M003_CONTINUE_PLACE_PACKAGE']=str(p)
   sys.argv=[str(HERE/'runtime_qualify.py'),'--snapshot',str(snapshot),'--spec',str(r/'CPU_spec_unused.json'),'--output',str(r/'CPU_qualification_output.json'),'--phase',phase,'--report',str(r)]
   before=len(calls);caught=None;rc=None
   try:
    with contextlib.redirect_stdout(io.StringIO()):rc=module.main()
   except (AssertionError,FileNotFoundError) as e:caught=type(e).__name__
   if case in ['positive','qualification_returns_false']:
    assert caught is None and rc==(0 if case=='positive' else 1) and len(calls)==before+1
    c=calls[-1];q=c['package']
    assert q['checkpoint']==identity(current) and q['actual_native_phase']==phase and q['fresh_state_source']==identity(raw) and q['original_place_checkpoint']==identity(parent)
    assert set(x['path'] for x in q['bindings'])=={str(p),str(snapshot),str(context),str(current)}
    assert c['raw']==str(raw) and c['snapshot']==str(snapshot)
   else:assert caught and len(calls)==before
   bridge.append(dict(phase=phase,case=case,expected_outcome_verified=True,qualifier_called=len(calls)==before+1,exit_code=rc,exception=caught,stub_qualifier_only=True))
finally:
 module.qualifier.qualify=original_qualify;sys.argv=old_argv
 if old_env is None:os.environ.pop('HAP_M003_CONTINUE_PLACE_PACKAGE',None)
 else:os.environ['HAP_M003_CONTINUE_PLACE_PACKAGE']=old_env
result=dict(passed=True,CPU_fixture_only=True,native_executed=False,old_whole_suites_rerun=False,actual_evidence_not_replaced=True,collector_new_phase_cases=phases,runtime_bridge_cases=bridge,scope='Incremental physopt/route fresh collector and four-phase Python dispatch/binding/rejection only; qualified body itself uses previously reviewed real proof.',sources={p.name:identity(p) for p in [HERE/'runtime_state_collector.tcl',HERE/'runtime_qualify.py',source]})
p=OUT/'AT005_incremental_bridge_CPU_review_20261020.json'
with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(passed=True,evidence=str(p.relative_to(ROOT)),sha256=identity(p)['sha256'],collector_cases=len(phases),bridge_cases=len(bridge))))
