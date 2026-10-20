from pathlib import Path
import json,subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent
MOCK=r'''
set scenario [lindex $argv 0];set ::env(HAP_REPORT_DIR) [lindex $argv 1];set ::env(M003_RESET_LIBRARY_ONLY) 1
set props {};set netpin {};set groups {};set netdrivers {};set owners {};set cellinputs {};set group_calls 0;set leaf_calls 0
proc obj {id args} {foreach {k v} $args {dict set ::props $id $k $v}}
set rootnets {};for {set n 0} {$n<600} {incr n} {set net rn$n;lappend rootnets $net;obj $net NAME root_alias_$n CLASS net}
dict set props rn0 NAME core_rst_n
foreach n $rootnets {dict set groups $n $rootnets}
obj root_port NAME core_rst_n DIRECTION IN CLASS port;dict set netpin root_port rn0
set corecells {};set helpercells {}
foreach group {core h0 h1} {
 set net ${group}_net;obj $net NAME ${group}_clr CLASS net;dict set groups $net [list $net]
 set drv ${group}_out;set cell ${group}_lut
 obj $drv NAME $cell/O DIRECTION OUT REF_PIN_NAME O CLASS pin;dict set netpin $drv $net;dict set netdrivers $net [list $drv];dict set owners $drv $cell
 obj $cell NAME $cell REF_NAME LUT1 INIT 2'h1 CLASS cell
 set ip ${group}_in;obj $ip NAME $cell/I0 DIRECTION IN REF_PIN_NAME I0 CLASS pin;dict set netpin $ip rn0;dict set cellinputs $cell [list $ip]
 for {set b 0} {$b<17} {incr b} {
  set c ${group}_ff$b;set pin ${c}_CLR
  if {$group eq "core"} {set name [format {inst/u_core/u_compute/u_attention/meta_read_addr_r_reg[%d]} $b];lappend corecells $c} else {set slice [string index $group end];set name [format {inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice[%d].u_addr/address_r_reg[%d]} $slice $b];lappend helpercells $c}
  obj $c NAME $name REF_NAME FDCE INIT 1'b0 IS_CLR_INVERTED 0 CLASS cell
  obj $pin NAME $name/CLR REF_PIN_NAME CLR DIRECTION IN CLASS pin
  dict set cellinputs $c [list $pin];dict set netpin $pin $net
 }
}
if {$scenario eq "constant"} {dict set props core_lut REF_NAME GND;dict set cellinputs core_lut {}}
if {$scenario eq "unknown_inversion"} {dict unset props core_ff0 IS_CLR_INVERTED}
if {$scenario eq "missing_endpoint"} {set corecells [lrange $corecells 1 end]}
if {$scenario eq "duplicate_endpoint"} {set corecells [lreplace $corecells 16 16 core_ff0]}
if {$scenario eq "cycle"} {dict set netpin core_in core_net}
if {$scenario eq "multi_driver"} {dict set netdrivers core_net {core_out h0_out}}
if {$scenario eq "missing_source"} {dict set netdrivers core_net {}}
if {$scenario eq "bad_direction"} {dict set props core_out DIRECTION IN}
if {$scenario eq "bad_input_direction"} {dict set props core_in DIRECTION OUT}
if {$scenario eq "unknown_primitive"} {dict set props core_lut REF_NAME MUXF7}
if {$scenario eq "duplicate_NAME"} {dict set props rn599 NAME root_alias_1}
if {$scenario eq "depth"} {
 for {set i 0} {$i<6} {incr i} {
  set cell chain$i;set n cn$i;set d cd$i;set p cp$i
  obj $n NAME $n CLASS net;dict set groups $n [list $n];obj $d NAME $cell/O DIRECTION OUT;dict set netdrivers $n [list $d];dict set netpin $d $n;dict set owners $d $cell
  obj $cell NAME $cell REF_NAME LUT1 INIT 2'h1;obj $p NAME $cell/I0 DIRECTION IN REF_PIN_NAME I0;dict set cellinputs $cell [list $p]
  dict set netpin $p [expr {$i==5?"rn0":"cn[expr {$i+1}]"}]
 };dict set netpin core_in cn0
}
proc get_property {key objects} {set out {};foreach obj $objects {lappend out [dict get $::props $obj $key]};if {[llength $objects]==1} {return [lindex $out 0]};return $out}
proc list_property {obj} {return [dict keys [dict get $::props $obj]]}
proc get_ports {args} {
 if {[llength $args]==1} {return root_port}
 set n [lindex $args end];if {$n eq "rn0"} {return root_port};return {}
}
proc get_cells {args} {
 if {[lsearch -exact $args -hier]>=0} {if {[string first u_meta [lindex $args end]]>=0} {return $::helpercells};return $::corecells}
 return [dict get $::owners [lindex $args end]]
}
proc get_pins {args} {
 set obj [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
 if {[lsearch -exact $args -leaf]>=0} {
  incr ::leaf_calls;set n [lindex $obj 0];if {[dict exists $::netdrivers $n]} {return [dict get $::netdrivers $n]};return {}
 };return [dict get $::cellinputs $obj]
}
proc get_nets {args} {
 if {$::scenario eq "api_error"} {return -code error -errorcode {NATIVE RESET} {native reset query failed}}
 set pin [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]];set n [dict get $::netpin $pin]
 if {[lsearch -exact $args -top_net_of_hierarchical_group]>=0} {return [lindex [dict get $::groups $n] 0]}
 if {[lsearch -exact $args -segments]>=0} {incr ::group_calls;return [dict get $::groups $n]}
 return $n
}
'''
class ResetProvenance(unittest.TestCase):
 def run_spy(self,case):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'run.tcl';p.write_text(MOCK+'\nsource {'+str(HERE/'read_reset_provenance.tcl')+'}\n'+('for {set i 0} {$i<16} {incr i} {dict set m003_reset::seen_nodes seed$i 1}\n' if case=='node_bound' else '')+('set m003_reset::pins 64\n' if case=='pin_bound' else '')+r'''
if {[catch {m003_reset::run $::env(HAP_REPORT_DIR)} msg opts]} {puts stderr [dict get $opts -errorinfo];exit 1}
puts "$group_calls $leaf_calls"
''');cp=subprocess.run(['tclsh',str(p),case,td],text=True,capture_output=True);out=Path(td)/'reset_provenance.jsonl';rows=[json.loads(x) for x in out.read_text().splitlines()] if out.exists() else [];return cp,rows
 def test_exact51_600root_aliases_and4_unique_groups(self):
  cp,rows=self.run_spy('good');self.assertEqual(cp.returncode,0,cp.stderr);self.assertEqual(cp.stdout.strip(),'4 4');self.assertEqual(rows[-1],dict(kind='complete',endpoints='51',nodes='3',input_pins='3',groups='4'));root=next(z for z in rows if z['kind']=='group');self.assertEqual(root['actual_segment_count'],'600');self.assertEqual(len([z for z in rows if z['kind']=='endpoint']),51)
 def test_unknown_FF_inversion_preserved(self):
  cp,rows=self.run_spy('unknown_inversion');self.assertEqual(cp.returncode,0,cp.stderr);z=next(z for z in rows if z['kind']=='endpoint');self.assertEqual(z['IS_CLR_INVERTED'],'NOT_SUPPORTED')
 def test_constant_source_preserved(self):
  cp,rows=self.run_spy('constant');self.assertEqual(cp.returncode,0,cp.stderr);self.assertTrue(any(z.get('REF_NAME')=='GND' for z in rows if z['kind']=='node'))
 def test_errors_cycles_bounds_source_identity_and_directions_reject(self):
  for case in ['missing_endpoint','duplicate_endpoint','cycle','multi_driver','missing_source','bad_direction','bad_input_direction','unknown_primitive','duplicate_NAME','depth','node_bound','pin_bound','api_error']:
   with self.subTest(case=case):
    cp,_=self.run_spy(case);self.assertNotEqual(cp.returncode,0,cp.stderr)
    if case=='api_error':self.assertIn('native reset query failed',cp.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
