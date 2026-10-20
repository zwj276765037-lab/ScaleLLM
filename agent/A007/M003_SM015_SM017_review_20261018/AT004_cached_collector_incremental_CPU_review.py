"""Only two incremental CPU checks for the new collector/cache boundary; no EDA."""
from pathlib import Path
import ast,hashlib,json,subprocess,tempfile
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
SRC=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/place_write_replica_proof'
source=SRC/'test_cached_collector.py'
parsed=ast.parse(source.read_text());nodes=[]
for node in parsed.body:
 if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='results' for x in node.targets):break
 nodes.append(node)
ns={'__file__':str(source),'__name__':'a007_fixture_definition_only'}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
prefix=ns['prefix']
old_ports='''proc get_ports {args} {
    if {[llength [lindex $args end]]!=1} {error {primary-port query did not use one actual canonical object}}
    if {$::scenario eq "native_port_error"} {error {native primary-port failure}}
    return {}
}'''
new_ports='''proc get_ports {args} {
    set nets [lindex $args end]
    set groups {}
    foreach net $nets {lappend groups [dict get $::memberships $net]}
    set groups [lsort -unique $groups]
    if {[llength $groups]!=1} {error {mixed actual native group}}
    if {$groups eq {C}} {return primary_clock_port}
    return {}
}'''
assert prefix.count(old_ports)==1
positive=prefix.replace(old_ports,new_ports)
prelude='''
# Primary-input clock group: legitimate zero leaf drivers, one actual IN port.
dict set ::group_driver C {}
property primary_clock_port NAME primary_clock_port
property primary_clock_port DIRECTION IN
# Per-pin polarity must not be cached as a net/group property.
set special [lindex $proof_cells 1]
property $special/D IS_INVERTED 1
property $special INIT 1'b1
'''
marker='set code [catch {source $collector} message options]'
assert positive.count(marker)==1
positive=positive.replace(marker,prelude+'\n'+marker)
outputs={}
with tempfile.TemporaryDirectory(prefix='a007_cached_delta_') as td:
 td=Path(td)
 for kind,collector in [('original','query.tcl'),('cached','query_cached.tcl')]:
  p=td/kind;p.mkdir();mock=p/'mock.tcl';mock.write_text(positive)
  run=subprocess.run(['tclsh',str(mock),'positive',str(p),str(SRC/collector)],text=True,capture_output=True)
  assert run.returncode==0,(kind,run.stderr)
  raw=(p/'selected_state_and_root_pins.jsonl').read_bytes();rows=[json.loads(x) for x in raw.splitlines()]
  assert len(rows)==108
  clock_pins=[r for r in rows if r.get('kind')=='state_pin' and r.get('terminal')=='C']
  assert len(clock_pins)==12 and all(r['drivers']=='' and r['driver_cells']=='' and r['driver_refs']=='' and r['primary_ports']=='primary_clock_port' and r['primary_port_directions']=='IN' and len(r['nets'].split())==12560 for r in clock_pins)
  changed=[r for r in rows if r.get('kind')=='state_pin' and r.get('terminal')=='D' and r['IS_INVERTED']=='1'];assert len(changed)==1
  assert sum(r.get('INIT')=="1'b1" for r in rows if r.get('kind')=='cell')==1
  outputs[kind]=dict(rows=rows,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 assert outputs['original']['rows']==outputs['cached']['rows']
 # One targeted context mutation; complete old context/negative suites are reused.
 p=td/'changed_context';p.mkdir()
 ctx='''
property other_design NAME other_design
property other_design PART xcvu9p-flga2104-2L-e
set context_calls 0
rename current_design fixture_old_current_design
proc current_design {} {
 incr ::context_calls
 if {$::context_calls>=3} {return other_design}
 return fixture_design
}
rename get_designs fixture_old_get_designs
proc get_designs {} {return {design_handle other_design}}
'''
 mock=p/'mock.tcl';mock.write_text(positive.replace(marker,ctx+'\n'+marker))
 run=subprocess.run(['tclsh',str(mock),'positive',str(p),str(SRC/'query_cached.tcl')],text=True,capture_output=True)
 assert run.returncode==1 and 'M003 connectivity design context changed' in run.stderr
 assert not (p/'read_only_complete.json').exists()
result=dict(schema='A007_AT004_cached_collector_incremental_CPU_review_v1',passed=True,native_executed=False,
 cases=[dict(case='actual_original_collector_vs_cached_complete_schema_with_primary_IN_clock',rows=108,equal_row_dictionaries=True,original_bytes=outputs['original']['bytes'],cached_bytes=outputs['cached']['bytes'],original_sha256=outputs['original']['sha256'],cached_sha256=outputs['cached']['sha256'],legitimate_empty_leaf_drivers=True,nonempty_primary_IN_port_retained=True,full12560clock_members_retained=True,independent_per_pin_inversion_and_per_cell_INIT_retained=True),dict(case='design_context_changes_during_same_call',rejected=True,no_complete_marker=True)],
 owner_six_case_suite_rerun=False,large_DCP_or_snapshot_read=False,actual_native_performance_claim=False)
p=OUT/'AT004_cached_collector_incremental_CPU_review_20261020.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
