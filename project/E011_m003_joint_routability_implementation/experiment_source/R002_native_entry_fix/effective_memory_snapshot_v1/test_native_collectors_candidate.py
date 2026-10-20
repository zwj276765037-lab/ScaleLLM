from pathlib import Path
import json,subprocess,unittest
BASE=Path(__file__).resolve().parent
SOURCE=(BASE/'m003_joint_checks.tcl.proposed').read_text()
PROCS='namespace eval m003 {}\n'+SOURCE[SOURCE.index('proc m003::exact_count'):SOURCE.index('proc m003::require_synthesis_runs')]+SOURCE[SOURCE.index('proc m003::jq'):SOURCE.index('proc m003::cell_row')]
class NativeCollectors(unittest.TestCase):
 def run_tcl(self,body):
  p=subprocess.run(['tclsh'],input='if {[catch {\n'+PROCS+'\n'+body+'\n} message options]} {puts stderr [dict get $options -errorinfo];exit 1}\n',capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr);return p.stdout.strip()
 def helper(self,mutation=''):
  return self.run_tcl(r'''
set objects [dict create dp [dict create NAME root/helper/D] qp [dict create NAME root/helper/Q] raw [dict create NAME root/helper/C CLASS pin] rst [dict create NAME core_rst_n CLASS port] owner [dict create NAME root/helper REF_NAME FDCE]]
proc get_property {property ids} {
 if {![llength $ids]} {error {fixture refuses empty property query}}
 set values {};foreach id $ids {lappend values [dict get $::objects $id $property]}
 # Vivado scalar NAME is a scalar string, not a one-element quoted list.
 if {[llength $values]==1} {return [lindex $values 0]};return $values
}
proc get_pins {args} {set terminal [lindex $args end];if {$terminal eq "REF_PIN_NAME == D"} {return dp};if {$terminal eq "REF_PIN_NAME == Q"} {return qp};error {unexpected pin query}}
proc get_cells {args} {if {[lindex $args end] ne "raw"} {error {wrong actual owner query}};return owner}
proc all_fanin {args} {
 if {[info exists ::native_error]} {return -code error -errorcode {NATIVE FANIN} {actual API failure}}
 if {[lsearch -exact $args -only_cells]>=0} {return owner}
 if {[lsearch -exact $args -startpoints_only]>=0} {return {raw rst}}
 if {[info exists ::omit_q]} {return {raw rst}}
 return {raw qp rst}
}
'''+mutation+r'''
set code [catch {m003::address_state_evidence helper} value options]
if {$code} {puts "$code|$value|[dict get $options -errorcode]"} else {puts [m003::jobject $value]}
''')
 def test_raw_C_and_actual_owner_Q_separate_and_primary_port_retained(self):
  r=json.loads(self.helper());self.assertEqual(r['D_startpoints'],'root/helper/C core_rst_n');f=json.loads(r['D_source_facts']);self.assertEqual(f[0]['owner_Q_pins'],'root/helper/Q');self.assertEqual(f[0]['owner_Q_in_full_fanin'],'1');self.assertEqual(f[1]['class'],'port');self.assertEqual(f[1]['owner_names'],'');self.assertEqual(r['D_startpoint_cells'],'root/helper')
 def test_absent_actual_Q_records_zero_not_inferred(self):
  r=json.loads(self.helper('set omit_q 1\n'));self.assertEqual(json.loads(r['D_source_facts'])[0]['owner_Q_in_full_fanin'],'0')
 def test_native_helper_error_not_swallowed(self):self.assertEqual(self.helper('set native_error 1\n'),'1|actual API failure|NATIVE FANIN')
 def memory(self,terminal,mode):
  body='set terminal {'+terminal+'}\nset mode '+mode+'\n'+r'''
set port_calls 0
proc get_property {property ids} {
 if {![llength $ids]} {error {empty property call}}
 switch -- $property {
  REF_PIN_NAME {return $::terminal}
  NAME {switch -- $ids {pin {return root/uram/$::terminal} driver {return constant/G} owner {return constant} port {return core_clk} net {return core_clk} default {error {unexpected NAME}}}}
  REF_NAME {return GND}
  DIRECTION {return IN}
 };error {unexpected property}
}
proc get_nets {args} {
 if {$::mode eq "error"} {return -code error -errorcode {NATIVE NET} {native net failure}}
 if {$::mode eq "unconnected"} {return {}}
 return net
}
proc get_pins {args} {if {[lindex $args end] eq "DIRECTION == OUT"} {if {$::mode eq "port"} {return {}};return driver};error {unexpected pin call}}
proc get_cells {args} {return owner}
proc get_ports {args} {incr ::port_calls;return port}
proc all_fanin {args} {if {$::mode eq "unconnected"} {return pin};return {}}
set code [catch {m003::memory_pin_row 0 root/uram pin} value options]
if {$code} {puts "$code|$value|[dict get $options -errorcode]"} else {dict set value port_calls $port_calls;puts [m003::jobject $value]}
'''
  return self.run_tcl(body)
 def test_empty_startpoint_GND_raw_preserved(self):
  r=json.loads(self.memory('ADDR_A[22]','constant'));self.assertEqual(r['startpoints'],'');self.assertEqual(r['driver_refs'],'GND');self.assertEqual(r['driver_cells'],'constant')
 def test_unselected_unconnected_address_self_raw_preserved(self):
  r=json.loads(self.memory('ADDR_A[0]','unconnected'));self.assertEqual(r['nets'],'');self.assertEqual(r['drivers'],'');self.assertEqual(r['startpoints'],'root/uram/ADDR_A[0]')
 def test_primary_input_query_only_if_leaf_driver_absent(self):
  port=json.loads(self.memory('CLK','port'));self.assertEqual(port['primary_ports'],'core_clk');self.assertEqual(port['primary_port_directions'],'IN');self.assertEqual(port['port_calls'],'1')
  leaf=json.loads(self.memory('CLK','constant'));self.assertEqual(leaf['primary_ports'],'');self.assertEqual(leaf['port_calls'],'0')
 def test_nonempty_native_memory_error_propagates(self):self.assertEqual(self.memory('ADDR_A[0]','error'),'1|native net failure|NATIVE NET')
if __name__=='__main__':unittest.main(verbosity=2)
