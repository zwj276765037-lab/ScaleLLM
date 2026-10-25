#!/usr/bin/env python3
"""CPU source/patch checks. No Vivado/native object behavior is claimed."""
from pathlib import Path
import importlib.util,json,tempfile,zipfile,tkinter,ast
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('constraint_tools',HERE/'constraint_tools.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec=importlib.util.spec_from_file_location('constraint_replay_identity',HERE/'constraint_replay_identity.py');replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
spec=importlib.util.spec_from_file_location('capture_role_classifier',HERE/'capture_role_classifier.py');roles=importlib.util.module_from_spec(spec);spec.loader.exec_module(roles)
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
 before=d/'before.xdc';after=d/'after.xdc'
 before.write_text('# Command Used: original.xdc\ncurrent_instance block0\nset_false_path -to [get_pins {ff/D}]\ncurrent_instance -quiet\nset_clock_uncertainty .05 [get_clocks c]\n')
 after.write_text('# Command Used: replay.xdc\n# Constraints from file: aggregate.xdc\ncurrent_instance -quiet\ncurrent_instance block0\nset_false_path -to [get_pins {ff/D}]\ncurrent_instance -quiet\ncurrent_instance -quiet\nset_clock_uncertainty .05 [get_clocks c]\n')
 assert replay.compare(before,after)['constraint_commands']==2;tests.append('replay_ignores_tool_comments_and_redundant_scope_switches')
 original=after.read_text()
 for name,changed in [('scope',original.replace('block0','block1')),('constraint',original.replace('.05','.06')),('deletion',original.replace('set_false_path -to [get_pins {ff/D}]\n','')),('final_scope',original+'current_instance other\n')]:
  after.write_text(changed);reject(lambda:replay.compare(before,after));tests.append('reject_replay_'+name+'_drift')
 before.write_text('set_clock_uncertainty .05 [get_clocks c]\nset_clock_uncertainty .06 [get_clocks c]\n');after.write_text('set_clock_uncertainty .06 [get_clocks c]\nset_clock_uncertainty .05 [get_clocks c]\n');reject(lambda:replay.compare(before,after));tests.append('reject_replay_constraint_reordering')
 exported=root/'project/hardware/vivado/reports/m006_gu_AT004_routed_constraint_qualification/native_output/original_timing_all.xdc'
 assert replay.compare(exported,exported)['constraint_commands']>100;tests.append('actual_native_export_scope_parser_selfcheck')
t=tkinter.Tcl();script=(HERE/'qualify_routed_constraints.tcl').read_text();probe=(HERE/'capture_role_probe.tcl').read_text();assert t.call('info','complete',script)==1 and t.call('info','complete',probe)==1;t.eval(script[:script.rfind('\nsource [file join')]);t.eval(probe);tests.append('tcl_complete_and_proc_definition')
assert t.call('cq_base_predicate')==m.CAPTURE_PREDICATE;tests.append('native_proof_and_replacement_identical_predicate')
assert '!(' not in t.call('cq_missing_predicate') and '!=' in t.call('cq_missing_predicate') and '!~' in t.call('cq_missing_predicate')
for direction in ['IN','OUT','INOUT']:
 for clock in [0,1]:
  for pin in ['D','C','CE','CE0']:
   positive=(direction=='IN' and (clock==0 or pin.startswith('CE'))) or direction=='INOUT'
   negative=direction!='INOUT' and (direction!='IN' or (clock!=0 and not pin.startswith('CE')))
   assert positive!=negative
tests.append('explicit_DeMorgan_complement_truth_table_and_supported_operators')
for pins in identity['target_D'].values():
 assert t.call('cq_exclusions',t.call('list',*pins))==m.exclusion_predicate(pins)
tests.append('native_and_python_identical_fast_scope_guard_with_exact_name_exclusions')
extra=['clock_valued_data_reg/D','enable_reg/CLKEN'];assert t.call('cq_full_predicate',t.call('list',*extra))==m.full_capture_predicate(extra);tests.append('native_and_python_identical_extra_capture_predicate')
fact={'owner_ref':'FDRE','ref_pin':'D','direction':'IN','library_direction':'IN','library_is_clock':'0','library_is_data':'1','is_clock':'1','native_clock_member':False,'native_output_member':False,'pin_clocks':[],'library_pin_count':1,'categories':['data']}
assert roles.decide(fact,{'FDRE'})[0]=='ADD_EXACT_CAPTURE';tests.append('clock_valued_known_data_is_explicitly_added')
f={**fact,'ref_pin':'C','library_is_clock':'1','library_is_data':'0','native_clock_member':True,'pin_clocks':['clock']};assert roles.decide(f,{'FDRE'})[0]=='EXCLUDE_PROVEN_NONCAPTURE';tests.append('pure_clock_requires_bound_primitive_library_and_actual_role')
f={**fact,'ref_pin':'Q','direction':'OUT','library_direction':'OUT','is_clock':'0','native_output_member':True};assert roles.decide(f,{'FDRE'})[0]=='EXCLUDE_PROVEN_NONCAPTURE';tests.append('pure_launch_output_requires_bound_primitive_and_library_direction')
for f in [{**fact,'library_pin_count':0},{**fact,'library_is_clock':'1'},{**fact,'owner_ref':'UNKNOWN','library_is_clock':'__UNAVAILABLE__'},{**fact,'ref_pin':'C','library_is_clock':'1','library_is_data':'1','native_clock_member':True}]:
 assert roles.decide(f,{'FDRE'})[0]=='UNKNOWN'
tests.append('unknown_missing_conflicting_and_dual_roles_rejected')
baseline=root/'project/hardware/vivado/reports/m006_gu_AT004_routed_constraint_qualification/native_output/original_same_clock_paths.txt';assert len(t.splitlist(t.call('cq_load_reused_sync',str(baseline))))==100;tests.append('actual_closed_AT004_same_clock_baseline_parse')
for value in ['a[2]/D','quote"slash\\tab\tline\n','simple']:
 assert json.loads(t.call('cq_quote',value))==value
assert json.loads(t.call('cq_json_array',t.call('list','a[2]/D','b')))==['a[2]/D','b'];tests.append('tcl_json_roundtrip')
ast.parse((HERE/'run_constraint_qualification.py').read_text());tests.append('runner_python_ast')
output={'scope':'CPU_HELPER_AND_SYNTAX_ONLY_NATIVE_NOT_RUN','tests':tests,'count':len(tests),'actual_parent_metrics':metrics,'source_sha256':m.digest(HERE/'constraint_tools.py'),'replay_comparator_sha256':m.digest(HERE/'constraint_replay_identity.py'),'probe_sha256':m.digest(HERE/'capture_role_probe.tcl'),'classifier_sha256':m.digest(HERE/'capture_role_classifier.py'),'role_models_sha256':m.digest(HERE/'role_model_sources.json'),'native_export_parser_sample_sha256':m.digest(exported),'tcl_sha256':m.digest(HERE/'qualify_routed_constraints.tcl'),'test_sha256':m.digest(Path(__file__)),'runner_sha256':m.digest(HERE/'run_constraint_qualification.py')}
(HERE/'cpu_helper_check.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
