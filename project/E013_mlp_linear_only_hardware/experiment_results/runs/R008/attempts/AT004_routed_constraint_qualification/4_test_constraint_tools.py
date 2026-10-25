#!/usr/bin/env python3
"""CPU source/patch checks. No Vivado/native object behavior is claimed."""
from pathlib import Path
import importlib.util,json,tempfile,zipfile,tkinter,ast
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('constraint_tools',HERE/'constraint_tools.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
tests=[]
def reject(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('expected rejection')
root=HERE.parents[4]
native=root/'project/hardware/vivado/reports/m006_gu_AT001_impl/timing_summary.rpt'
metrics=m.metrics(native);assert metrics['wns_ns']==.002 and metrics['setup_failing_endpoints']==0 and metrics['whs_ns']==.010;tests.append('actual_native_twelve_metrics')
assert m.assert_timing(native)['status']=='PASS';tests.append('native_active_aggregate_acceptance')
identity={'clock_groups':{'pcie':['core_clk','xdma_clk'],'ddr0':['d0_clk'],'ddr1':['d1_clk']},'target_D':{'ddr0':[f'a/dest_hsdata_ff_reg[{i}]/D' for i in range(68)],'ddr1':[f'g/dest_hsdata_ff_reg[{i}]/D' for i in range(70)]}}
body=m.replacement(identity)
assert body.count('set_false_path ')==6 and body.count('set_clock_groups ')==1 and body.count('NAME != ')==138 and '-reset_path' not in body;tests.append('exact_138_and_six_directed_exceptions')
assert body.count('get_cells -quiet -hierarchical -filter {IS_PRIMITIVE == 1}')==2 and body.count('IS_CLOCK == 0')==2 and body.count('DIRECTION == OUT || DIRECTION == INOUT')==4;tests.append('all_primitive_nonclock_input_and_output_capture_superset')
assert body.count(m.CAPTURE_PREDICATE)==2 and 'REF_PIN_NAME =~ CE*' in m.CAPTURE_PREDICATE and 'DIRECTION == INOUT' in m.CAPTURE_PREDICATE;tests.append('explicit_gating_ce_and_inout_inclusion')
for name,alter in [('clock_overlap',lambda x:x['clock_groups']['ddr0'].append('core_clk')),('missing_endpoint',lambda x:x['target_D']['ddr0'].pop()),('duplicate_endpoint',lambda x:x['target_D']['ddr1'].__setitem__(0,x['target_D']['ddr0'][0])),('nonD',lambda x:x['target_D']['ddr1'].__setitem__(0,'bad/Q'))]:
 x=json.loads(json.dumps(identity));alter(x);reject(lambda:m.replacement(x));tests.append('reject_'+name)
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);a=d/'a.xdc';b=d/'b.xdc';c=d/'c.xdc';b.write_text(body);prefix='# vendor before\nset_false_path -through [get_pins {vendor/D}]\n';suffix='\n# vendor after\nset_max_delay -datapath_only 10 -to [get_pins {vendor/D}]\n';a.write_text(prefix+m.USER_GROUP+suffix);r=m.patch(a,b,c);assert c.read_text()==prefix+body.rstrip('\n')+suffix and r['other_original_bytes_preserved'];tests.append('patch_preserves_all_vendor_bytes')
 a.write_text(prefix+suffix);reject(lambda:m.patch(a,b,c));tests.append('reject_missing_user_group')
 a.write_text(m.USER_GROUP+'\n'+m.USER_GROUP+'\n');reject(lambda:m.patch(a,b,c));tests.append('reject_duplicate_user_group')
 timing=d/'timing.rpt'
 for words in ['-.001 0 0 100 .010 0 0 100 0 0 0 100','.002 0 1 100 .010 0 0 100 0 0 0 100','nan 0 0 100 .010 0 0 100 0 0 0 100']:
  timing.write_text('WNS(ns) TNS Failing Endpoints\n'+words+'\n');reject(lambda:m.assert_timing(timing))
 tests.append('reject_negative_failing_or_nonfinite_aggregate')
 z=d/'physical.dcp'
 with zipfile.ZipFile(z,'w') as f:
  for suffix in m.PHYSICAL_SUFFIXES:f.writestr('design'+suffix,b'fixed_'+suffix.encode())
  f.writestr('design.sta',b'timing intentionally separate')
 r=m.checkpoint_members(z);assert len(r)==6 and 'design.sta' not in r;tests.append('physical_six_members_exclude_timing')
 for bad in ['bad{pin','bad\\pin','bad\npin']:reject(lambda:m.tcl_list([bad]))
 tests.append('reject_tcl_injection_names')
t=tkinter.Tcl();script=(HERE/'qualify_routed_constraints.tcl').read_text();assert t.call('info','complete',script)==1;t.eval(script[:script.rfind('\ncq_main\n')]);tests.append('tcl_complete_and_proc_definition')
assert 'set predicate {'+m.CAPTURE_PREDICATE+'}' in script;tests.append('native_proof_and_replacement_identical_predicate')
for value in ['a[2]/D','quote"slash\\tab\tline\n','simple']:
 assert json.loads(t.call('cq_quote',value))==value
assert json.loads(t.call('cq_json_array',t.call('list','a[2]/D','b')))==['a[2]/D','b'];tests.append('tcl_json_roundtrip')
ast.parse((HERE/'run_constraint_qualification.py').read_text());tests.append('runner_python_ast')
output={'scope':'CPU_HELPER_AND_SYNTAX_ONLY_NATIVE_NOT_RUN','tests':tests,'count':len(tests),'actual_parent_metrics':metrics,'source_sha256':m.digest(HERE/'constraint_tools.py'),'tcl_sha256':m.digest(HERE/'qualify_routed_constraints.tcl'),'test_sha256':m.digest(Path(__file__)),'runner_sha256':m.digest(HERE/'run_constraint_qualification.py')}
(HERE/'cpu_helper_check.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
