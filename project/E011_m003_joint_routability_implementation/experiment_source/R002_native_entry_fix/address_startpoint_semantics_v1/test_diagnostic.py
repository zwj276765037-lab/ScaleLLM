"""CPU fixtures preserve raw C/port sources and separately prove Q membership."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

TCL = Path(__file__).with_name('read_state_sources.tcl').resolve()
BASE = r'''
set ::env(M003_STATE_SOURCE_LIBRARY_ONLY) 1
source {%s}
set m003_state_diag::expected_helpers_per_slice 1
set m003_state_diag::expected_memories 2
set ff0 {inst/u_core/u_compute/u_attention/u_meta/g_slice[0].u_addr/address_r_reg[0]}
set ff1 {inst/u_core/u_compute/u_attention/u_meta/g_slice[1].u_addr/address_r_reg[0]}
set ram0 {inst/u_core/u_compute/u_attention/u_meta/g_slice[0].mem0}
set ram1 {inst/u_core/u_compute/u_attention/u_meta/g_slice[1].mem1}
proc get_cells {args} {
 if {[lsearch -exact $args -hier]>=0} {if {[string match {*address_r_reg*} [lindex $args end]]} {return [list $::ff0 $::ff1]};return [list $::ram0 $::ram1]}
 return [list [file dirname [lindex $args end]]]
}
proc get_pins {args} {
 if {[lsearch -exact $args -leaf]>=0} {return {}}
 set owner [lindex [lindex $args end-2] 0];set filter [lindex $args end]
 foreach terminal {D Q CLK} {if {[string match "*==*\"$terminal\"*" $filter] || $filter eq "REF_PIN_NAME == $terminal"} {return [list $owner/$terminal]}}
 error "Unexpected pins query $args"
}
proc get_property {key objects} {
 switch -- $key {
  NAME {return $objects}
  CLASS {if {$objects eq {clk}} {return port};return pin}
  REF_NAME {if {[string match *mem* $objects]} {return URAM288};return FDCE}
  DIRECTION {return IN}
  default {error "Unexpected property $key"}
 }
}
proc all_fanin {args} {
 set cell [file dirname [lindex $args end]]
 if {[lsearch -exact $args -only_cells]>=0} {return [list $cell]}
 if {[lsearch -exact $args -startpoints_only]>=0} {return [list $cell/C clk]}
 return [list $cell/C $cell/Q $cell/D clk]
}
proc get_nets {args} {return clock_net}
proc get_ports {args} {return clk}
'''


class StateSources(unittest.TestCase):
    def run_diag(self, mutation=''):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = Path(tmp.name)
        code = BASE % TCL + mutation + '\nif {[catch {m003_state_diag::run {' + str(report) + '}} msg]} {puts stderr $msg;exit 1}\n'
        result = subprocess.run(['tclsh'], input=code, text=True, capture_output=True)
        return result, report

    def test_raw_clock_startpoint_is_retained_and_Q_evidence_separate(self):
        result, report = self.run_diag()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(x) for x in (report / 'helper_D_sources.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row['raw_startpoints'], [row['cell'] + '/C', 'clk'])
        self.assertEqual(row['own_Q_in_full_fanin'], 1)
        self.assertEqual(row['actual_source_owner_facts'][0]['owner_Q_in_full_fanin'], ['1'])
        self.assertEqual(row['actual_source_owner_facts'][0]['owner_Q_pins'], [row['cell'] + '/Q'])
        self.assertEqual(row['actual_source_owner_facts'][1]['owner_names'], [])
        clocks = [json.loads(x) for x in (report / 'uram_clock_sources.jsonl').read_text().splitlines()]
        self.assertEqual(clocks[0]['leaf_drivers'], [])
        self.assertEqual(clocks[0]['primary_ports'], ['clk'])
        self.assertEqual(clocks[0]['primary_port_directions'], ['IN'])
        done = json.loads((report / 'diagnostic_complete.json').read_text())
        self.assertEqual((done['helper_D_rows'], done['URAM_clock_rows']), (2, 2))
        self.assertFalse(done['raw_values_rewritten'])
        self.assertFalse(done['G4'])

    def test_missing_Q_is_false_not_manufactured_from_C_name(self):
        mutation = r'''
rename all_fanin original_all_fanin
proc all_fanin {args} {
 if {[lsearch -exact $args -startpoints_only]>=0} {return [original_all_fanin {*}$args]}
 set cell [file dirname [lindex $args end]];return [list $cell/C $cell/D clk]
}
'''
        result, report = self.run_diag(mutation)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads((report / 'helper_D_sources.jsonl').read_text().splitlines()[0])
        self.assertEqual(row['own_Q_in_full_fanin'], 0)
        self.assertEqual(row['actual_source_owner_facts'][0]['owner_Q_in_full_fanin'], ['0'])

    def test_native_API_error_preserves_partial_without_success(self):
        result, report = self.run_diag('proc all_fanin {args} {error {forced native failure}}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('forced native failure', result.stderr)
        self.assertTrue((report / 'helper_D_sources.jsonl.partial').exists())
        self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_wrong_identity_duplicate_and_empty_collection_rejected(self):
        for mutation in ['proc get_cells {args} {return {}}', 'proc get_cells {args} {return {same same}}', 'set m003_state_diag::expected_helpers_per_slice 2']:
            with self.subTest(mutation=mutation):
                result, report = self.run_diag(mutation)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_missing_required_pin_is_not_accepted(self):
        result, report = self.run_diag('proc get_pins {args} {return {}}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Non-singleton required pin', result.stderr)
        self.assertFalse((report / 'diagnostic_complete.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
