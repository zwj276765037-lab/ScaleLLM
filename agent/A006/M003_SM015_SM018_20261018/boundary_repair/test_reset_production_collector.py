from pathlib import Path
import importlib.util,json,subprocess,tempfile,unittest
W=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('prior_reset_spy',W/'test_reset_provenance.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
source=(W/'m003_joint_checks.reset_semantics.tcl.proposed').read_text();LIB=source[source.index('namespace eval m003_reset'):source.index('proc m003::snapshot_body')]
class ProductionCollector(unittest.TestCase):
 def run_spy(self,case='good',twice=False):
  with tempfile.TemporaryDirectory() as td:
   script=Path(td)/'run.tcl';out=Path(td)/'records.jsonl'
   script.write_text(M.MOCK+'\nsource {'+str(W/'frozen_shared_connectivity.tcl')+'}\n'+LIB+r'''
namespace eval m003 {}
set output [open [file join $::env(HAP_REPORT_DIR) records.jsonl] w]
proc m003::stream_row {section row} {
 if {$section ne "reset_provenance"} {error {wrong stream section}}
 set fields {};dict for {k v} $row {lappend fields "[m003_conn::quote $k]:[m003_conn::quote $v]"};puts $::output "\{[join $fields ,]\}"
}
set checks 0
proc m003_conn::check {token} {incr ::checks;if {$token ne "actual_call_token"} {error expired}}
rename get_nets original_mock_get_nets
proc get_nets {args} {
 if {[lsearch -exact $args -of_objects]<0} {incr ::group_calls;return [dict get $::groups [lindex $args end]]}
 return [original_mock_get_nets {*}$args]
}
obj root_out NAME independent_reset_driver/O DIRECTION OUT CLASS pin
dict set netpin root_out rn0;dict set netdrivers rn0 root_out
set r [dict create core_address {} addresses [dict create 0 {} 1 {}]]
for {set b 0} {$b<17} {incr b} {dict set r core_address $b core_ff$b;dict set r addresses 0 $b h0_ff$b;dict set r addresses 1 $b h1_ff$b}
if {[catch {
m003_reset::run $r rn0 actual_call_token
'''+('m003_reset::run $r rn0 actual_call_token\n' if twice else '')+r'''
} msg opts]} {close $output;foreach var {object_groups groups seen_nodes visiting heights root} {if {[set ::m003_reset::$var] ne {}} {puts stderr LEAKED_AFTER_ERROR;exit 2}};puts stderr [dict get $opts -errorinfo];exit 1}
close $output
if {$m003_reset::object_groups ne {} || $m003_reset::groups ne {} || $m003_reset::seen_nodes ne {}} {error {actual handles leaked beyond one call}}
puts "$group_calls $leaf_calls $checks"
''');cp=subprocess.run(['tclsh',str(script),case,td],capture_output=True,text=True);rows=[json.loads(l) for l in out.read_text().splitlines()] if out.exists() else [];return cp,rows
 def test_actual_native_source_and_same_call_group_cost(self):
  cp,rows=self.run_spy();self.assertEqual(cp.returncode,0,cp.stderr);self.assertEqual(cp.stdout.strip(),'5 5 2');self.assertEqual(rows[-1]['endpoints'],'51');root=next(r for r in rows if r['kind']=='root');self.assertEqual(root['actual_source'],'independent_reset_driver/O');self.assertEqual(root['direction'],'OUT')
 def test_next_call_collects_fresh_handles_and_source_groups(self):
  cp,rows=self.run_spy(twice=True);self.assertEqual(cp.returncode,0,cp.stderr);self.assertEqual(cp.stdout.strip(),'10 10 4');self.assertEqual(sum(r['kind']=='endpoint' for r in rows),102)
 def test_cycles_and_wrong_actual_source_direction_still_reject(self):
  for case in ['cycle','multi_driver','bad_direction','bad_input_direction','duplicate_NAME','depth','api_error']:
   with self.subTest(case=case):
    cp,_=self.run_spy(case);self.assertEqual(cp.returncode,1,cp.stderr);self.assertNotIn('LEAKED_AFTER_ERROR',cp.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
