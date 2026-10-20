"""Affected JSON field paths only; no native runtime or source mutation."""
from pathlib import Path
import json,subprocess,unittest
HERE=Path(__file__).resolve().parent
CURRENT=(HERE/'m003_joint_checks.tcl').read_text()
PENDING=(HERE/'m003_joint_checks.serialization_fields_pending.tcl.proposed').read_text()
def script(source,scope,api_error=False):
 helpers=source[source.index('proc m003::jq'):source.index('proc m003::write_jarray')]+source[source.index('proc m003::collection_property'):source.index('proc m003::memory_startpoint_names')]
 body=source[source.index('proc m003::snapshot_body'):source.index('# Preserve the native Tcl stack')]
 setup=r'''
namespace eval m003 {variable groups {};variable spec_path unused;variable scripts unused;variable parent_scope parent;variable core_meta_scope core/meta;variable meta_scope selected_meta;variable regions {}}
namespace eval m003_conn {}
proc m003::require_project {args} {}
proc m003::stream_begin {args} {}
proc m003_conn::begin {args} {return unit_token}
proc m003::clock_group {args} {return proven_clock_group}
proc m003_conn::bind {token pin} {return [dict create group proven_clock_group pin $pin]}
proc m003::cell_row {cell role extra} {return $extra}
proc m003::address_state_evidence {cell} {return {}}
proc m003::exact_count {objects n label} {if {[llength $objects]!=$n} {error count}}
proc m003::resolve {} {
 set r [dict create core_address {} payload [dict create head {} tail {}] addresses [dict create 0 {} 1 {}] helpers [dict create 0 {} 1 {}] memory [dict create 0 {} 1 {}] c01 {} meta_all {}]
 if {$::scope eq "core"} {dict set r core_address 0 core0}
 if {$::scope eq "address"} {dict set r addresses 0 0 helper0}
 return $r
}
proc m003::stream_row {section row} {set ::captured $row;error CAPTURE}
proc m003::pin_net {cell terminal} {return opaque_native_$terminal}
proc get_property {property objects} {
 if {$property eq "NAME" && [string match opaque_native_* $objects]} {
  if {$::api_error && ($::error_target eq {} || $objects eq $::error_target)} {return -code error -errorcode {NATIVE JSONFIELD} {actual NAME getter failed}}
  set values {};for {set i 0} {$i<600} {incr i} {lappend values actual_name_${objects}_$i};return $values
 }
 return $objects
}
proc get_pins {args} {return actual_pin}
proc get_nets {args} {return opaque_native_boundary}
proc get_pblocks {args} {return {}}
proc get_slrs {args} {return actual_slr}
proc get_sites {args} {return actual_site}
proc get_cells {args} {upvar 1 control_sources cs;set ::captured $cs;error CAPTURE}
'''
 return setup+helpers+body+'\nset scope '+scope+'\nset api_error '+str(int(bool(api_error)))+'\nset error_target {'+('opaque_native_'+api_error if isinstance(api_error,str) else '')+'}\n'+r'''
set code [catch {m003::snapshot_body synth unused} message options]
if {$code==1 && $message eq "CAPTURE"} {puts [m003::jobject $::captured]} else {puts "$code|$message|[dict get $options -errorcode]"}
'''
def run(source,scope,error=False):
 r=subprocess.run(['tclsh'],input='if {[catch {\n'+script(source,scope,error)+'\n} msg opts]} {puts stderr [dict get $opts -errorinfo];exit 1}\n',text=True,capture_output=True)
 if r.returncode:raise AssertionError(r.stderr)
 return r.stdout.strip()
class SerializationFields(unittest.TestCase):
 def test_all_four_actual_snapshot_field_paths_use_complete_NAME_values(self):
  for scope,fields in [('core',['CLR_nets']),('address',['CE_nets','CLR_nets']),('control',['write_enable'])]:
   with self.subTest(scope=scope):
    old=json.loads(run(CURRENT,scope));new=json.loads(run(PENDING,scope))
    for field in fields:
     expected=[f'actual_name_opaque_native_{"CE" if field=="CE_nets" else "meta_wr_valid" if field=="write_enable" else "CLR"}_{i}' for i in range(600)]
     self.assertEqual(new[field].split(),expected);self.assertTrue(old[field].startswith('opaque_native_'));self.assertEqual(len(old[field].split()),1)
 def test_native_NAME_getter_error_is_not_swallowed_on_any_field_path(self):
  for scope,target in [('core','CLR'),('address','CE'),('address','CLR'),('control','meta_wr_valid')]:
   with self.subTest(scope=scope,target=target):self.assertEqual(run(PENDING,scope,target),'1|actual NAME getter failed|NATIVE JSONFIELD')
if __name__=='__main__':unittest.main(verbosity=2)
