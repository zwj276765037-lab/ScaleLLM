"""Affected actual-object source proofs. CPU API semantics, not native EDA proof."""
from pathlib import Path
import importlib.util,json,subprocess,sys,tempfile,unittest
R=Path(__file__).resolve().parents[4];S=R/'project/hardware/vivado/scripts';HERE=Path(__file__).resolve().parent
OLD=R/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/grouped_connectivity_v1'
sys.path.insert(0,str(OLD));sys.path.insert(1,str(S))
sp=importlib.util.spec_from_file_location('existing_clock_spy',OLD/'test_grouped_clock.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
CHECK=(S/'m003_joint_checks.tcl').read_text();HELPERS=CHECK[CHECK.index('proc m003::boundary_net'):CHECK.index('proc m003::snapshot_body')]
ONE=CHECK[CHECK.index('proc m003::one'):CHECK.index('proc m003::yes')]
PROP=CHECK[CHECK.index('proc m003::collection_property'):CHECK.index('proc m003::memory_startpoint_names')]
PREFIX=r'''
namespace eval m003 {};namespace eval m003_conn {}
proc m003_conn::event {args} {}
proc m003_conn::bounded_objects {objects label} {if {[llength $objects]>131072} {error bound};return $objects}
set anchor core/engine_soft_clear;set query_count 0
set props [dict create n0 [dict create NAME $anchor CLASS net]]
proc get_property {key objects} {
 if {$::case eq "getter_error" && $key eq "NAME" && [llength $objects]>1} {return -code error -errorcode {NATIVE REALERROR} {actual NAME failed}}
 set result {};foreach o $objects {lappend result [dict get $::props $o $key]};return $result
}
proc get_nets {args} {
 incr ::query_count
 if {[lsearch -exact $args -of_objects]>=0} {error {net input to -of_objects is forbidden}}
 if {[lsearch -exact $args -segments]<0} {
  if {$::case eq "missing"} {return {}}
  if {$::case eq "duplicate"} {return {n0 n0}}
  if {$::case eq "wrong_name"} {dict set ::props n0 NAME wrong}
  if {$::case eq "wrong_class"} {dict set ::props n0 CLASS pin}
  return n0
 }
 if {[lindex $args end] ne "n0"} {error {expansion did not consume actual selected object}}
 if {$::case eq "segments_error"} {return -code error -errorcode {NATIVE REALERROR} {actual segment failed}}
 set result {};for {set i 0} {$i<600} {incr i} {lappend result n$i;dict set ::props n$i NAME [expr {$i?"alias_$i":$::anchor}];dict set ::props n$i CLASS net}
 if {$::case eq "omit_actual"} {return [lrange $result 1 end]}
 if {$::case eq "duplicate_object"} {return [concat $result n0]}
 if {$::case eq "duplicate_name"} {dict set ::props n599 NAME alias_1}
 if {$::case eq "bad_segment_class"} {dict set ::props n599 CLASS cell}
 return $result
}
'''
def tcl(script):
 p=subprocess.run(['tclsh'],input='if {[catch {\n'+script+'\n} msg opts]} {puts stderr [dict get $opts -errorinfo];exit 1}\n',text=True,capture_output=True)
 return p
class BoundaryRepair(unittest.TestCase):
 def test_complete_600_aliases_from_actual_anchor(self):
  p=tcl('set case good\n'+PREFIX+ONE+PROP+HELPERS+r'''
set net [m003::boundary_net $anchor];set names [m003::boundary_names S $net]
if {[llength $names]!=600 || [lindex $names 0] ne $anchor || [lindex $names end] ne "alias_599"} {error {full actual alias evidence differs}}
puts PASS
''');self.assertEqual(p.returncode,0,p.stderr);self.assertIn('PASS',p.stdout)
 def test_missing_misidentified_forged_and_native_errors_reject(self):
  for case in ['missing','duplicate','wrong_name','wrong_class','omit_actual','duplicate_object','duplicate_name','bad_segment_class','segments_error','getter_error']:
   with self.subTest(case=case):
    p=tcl('set case '+case+'\n'+PREFIX+ONE+PROP+HELPERS+'\nset net [m003::boundary_net $anchor];m003::boundary_names S $net\n');self.assertNotEqual(p.returncode,0)
    if case.endswith('error'):self.assertIn('actual',p.stderr)
 def test_literal_anchors_forbid_positional_wildcards(self):
  for name in ['core/bus[0]','core/s*','core/s?']:
   p=tcl('set case good\n'+PREFIX+ONE+PROP+HELPERS+'\nm003::boundary_net {'+name+'}\n');self.assertNotEqual(p.returncode,0)
 def clock(self,scenario,tail=''):
  mock=M.MOCK.split('set ::env(M003_GROUPED_CLOCK_LIBRARY_ONLY)')[0]
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'mock.tcl';p.write_text(mock+'\nsource {'+str(S/'m003_shared_connectivity.tcl')+'}\ndict set pinmap driver n0;dict set pinmap port n0;dict set props driver DIRECTION OUT\n'+r'''
set token [m003_conn::begin unit]
for {set i 0} {$i<80} {incr i} {m003_conn::bind $token p$i}
foreach gid [m003_conn::group_ids $token] {m003_conn::source $token $gid 1}
'''+tail+r'''
set b [m003_conn::bind_source_net $token n0]
if {[dict get $b pin] ni {core_clk clkbuf/O}} {error {source witness was not actual upstream object}}
set stats [m003_conn::finish $token]
foreach key {segments canonical drivers ports} {if {[dict get $stats counters $key calls]!=1} {error {heavy group API repeated}}}
if {[dict get $stats endpoints]!=81 || [dict get $stats groups]!=1} {error {missing distinct source witness}}
puts PASS
''');return subprocess.run(['tclsh',str(p),scenario,td,str(OLD)],text=True,capture_output=True)
 def test_clock_native_leaf_and_primary_source_reuse_exact_group(self):
  for case in ['leaf','one']:
   p=self.clock(case);self.assertEqual(p.returncode,0,p.stderr);self.assertIn('PASS',p.stdout)
 def test_clock_foreign_context_duplicate_and_nonexclusive_sources_reject(self):
  for case,tail in [('leaf','dict set props driver DIRECTION IN\n'),('leaf','dict set props n0 CLASS pin\n'),('leaf','dict set objects_dummy unused yes\nset token stale\n'),('leaf','m003_conn::bind_source_net $token n0\n'),('dual',''),('bad_direction','')]:
   p=self.clock(case,tail);self.assertNotEqual(p.returncode,0,p.stderr)
 def test_all_7_anchors_precede_large_row_walk_and_match_native_partials(self):
  body=CHECK[CHECK.index('proc m003::snapshot_body'):CHECK.index('# Preserve the native Tcl stack')]
  firstrow=body.index('dict for {bit cell}');self.assertLess(body.index('set control_clock_net'),firstrow);self.assertLess(body.index('dict set control_sources $tag'),firstrow)
  core='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention';meta=core+'/u_meta';report=R/'project/hardware/vivado/reports/m003_E011_R002_AT024_grouped_stream_postreport_recovery'
  expected={'S':core+'/engine_soft_clear','L':core+'/input_load_start','R':meta+'/rsp_fire','reset':core+'/core_rst_n','read_enable':meta+'/rd_fire','write_enable':core+'/meta_wr_valid','clock':core+'/core_clk'}
  observed=set()
  for stem in ['helper_pins','memory_pins']:
   with (report/f'm003_stream_synth_{stem}.jsonl.partial').open() as f:
    for line in f:observed.update(json.loads(line).get('nets','').split())
  observed.update(json.loads((report/'m003_connection_synth_groups.jsonl.partial').read_text().splitlines()[0])['nets'])
  self.assertTrue(set(expected.values())<=observed)
  for tag,name in expected.items():self.assertIn(name.replace(core,'${core_meta_scope}').replace('${core_meta_scope}/u_meta','${meta_scope}'),body)
  self.assertNotIn('get_pins -quiet ${meta_scope}/meta_wr_valid',body)
 def test_modified_tcl_syntax(self):
  for name in ['m003_joint_checks.tcl','m003_shared_connectivity.tcl']:
   p=tcl('set h [open {'+str(S/name)+'} r];set value [read $h];close $h\nif {![info complete $value]} {error {incomplete Tcl}}');self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
