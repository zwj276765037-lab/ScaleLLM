"""CPU fixtures for bounded raw native-address evidence, never EDA."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

TCL = Path(__file__).with_name('read_uram_address.tcl').resolve()
BASE = r'''
set ::env(M003_URAM_ADDRESS_LIBRARY_ONLY) 1
source {%s}
set m003_uram_diag::expected_per_slice 1
set m003_uram_diag::expected_pins 2
set m003_uram_diag::expected_mode_pins 0
proc list_property {cell} {return {SELF_ADDR_A CASCADE_ORDER_A IS_RDB_WR_A_INVERTED IS_EN_A_INVERTED USE_EXT_CE}}
proc get_cells {args} {
 if {[lsearch -exact $args -hier] >= 0} {return {inst/u_core/u_compute/u_attention/u_meta/g_slice[0]/mem inst/u_core/u_compute/u_attention/u_meta/g_slice[1]/mem}}
 if {[lindex $args end] eq "gnd/G"} {return gnd}
 return ff
}
proc get_pins {args} {
 if {[string match {*RDB_WR*} [lindex $args end]]} {return {}}
 if {[lsearch -exact $args -leaf] >= 0} {
  if {[string match {*ADDR_A\[22\]*} [lindex $args end-2]]} {return gnd/G}
  return ff/Q
 }
 set cell [lindex $args end-2]
 return [list $cell/ADDR_A\[22\] $cell/ADDR_A\[0\]]
}
proc get_nets {args} {return [list [lindex $args end]]}
proc get_property {key objects} {
 if {$key eq "NAME"} {return $objects}
 if {$key eq "REF_NAME"} {if {$objects eq "gnd"} {return GND};if {$objects eq "ff"} {return FDCE};return URAM288}
 if {$key eq "REF_PIN_NAME"} {return [file tail $objects]}
 if {$key eq "SELF_ADDR_A"} {return 0}
 if {$key eq "CASCADE_ORDER_A"} {return NONE}
 if {$key in {IS_RDB_WR_A_INVERTED IS_EN_A_INVERTED USE_EXT_CE}} {return 1}
 error "Unexpected property $key"
}
proc all_fanin {args} {if {[string match {*ADDR_A\[22\]*} [lindex $args end]]} {return {}};return ff/Q}
'''


class Diagnostic(unittest.TestCase):
    def run_diag(self, mutation=''):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        report = Path(tmp.name)
        code = BASE % TCL + mutation + '\nif {[catch {m003_uram_diag::run {' + str(report) + '}} msg]} {puts stderr $msg;exit 1}\n'
        p = subprocess.run(['tclsh'], input=code, text=True, capture_output=True)
        return p, report

    def test_complete_raw_constant_and_dynamic_rows(self):
        p, report = self.run_diag()
        self.assertEqual(p.returncode, 0, p.stderr)
        done = json.loads((report / 'diagnostic_complete.json').read_text())
        self.assertEqual((done['cells'], done['rows']), (2, 4))
        self.assertEqual(done['zero_startpoint_rows'], 2)
        self.assertEqual(done['zero_startpoint_single_constant_driver_rows'], 2)
        self.assertEqual(done['nonempty_startpoint_rows'], 2)
        self.assertFalse(done['constraint_apply_requested'])
        self.assertFalse(done['new_synthesis_launched'])
        self.assertFalse(done['G4'])
        rows = [json.loads(x) for x in (report / 'uram_address_pins.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['startpoints'], [])
        self.assertEqual(rows[0]['driver_refs'], ['GND'])
        self.assertEqual(rows[1]['startpoints'], ['ff/Q'])
        self.assertFalse(list(report.glob('*.partial')))
        progress = [json.loads(x) for x in (report / 'diagnostic_progress.jsonl').read_text().splitlines()]
        self.assertEqual(progress[-1]['event'], 'diagnostic_complete')

    def test_unknown_empty_is_data_not_assumed_constant(self):
        p, report = self.run_diag('rename get_pins original_get_pins\nproc get_pins {args} {if {[lsearch -exact $args -leaf] >= 0} {return {}};return [original_get_pins {*}$args]}')
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(x) for x in (report / 'uram_address_pins.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['drivers'], [])
        self.assertEqual(rows[0]['single_constant_driver'], 0)
        self.assertEqual(json.loads((report / 'diagnostic_complete.json').read_text())['zero_startpoint_single_constant_driver_rows'], 0)

    def test_mode_cascade_and_current_config_exported(self):
        mutation = r'''
set m003_uram_diag::expected_pins 4
set m003_uram_diag::expected_mode_pins 2
rename get_pins original_get_pins
proc get_pins {args} {
 if {[lsearch -exact $args -leaf] >= 0} {return [original_get_pins {*}$args]}
 set cell [lindex $args end-2]
 if {[string match {*RDB_WR*} [lindex $args end]]} {return [list $cell/RDB_WR_A $cell/RDB_WR_B]}
 return [list $cell/ADDR_A\[22\] $cell/ADDR_A\[0\] $cell/CAS_IN_ADDR_A\[22\] $cell/CAS_IN_ADDR_A\[0\]]
}
'''
        p, report = self.run_diag(mutation)
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(x) for x in (report / 'uram_address_pins.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[2]['pin'], 'CAS_IN_ADDR_A[22]')
        self.assertEqual(rows[2]['constant_value_from_single_driver_ref'], 0)
        modes = [json.loads(x) for x in (report / 'uram_mode_pins.jsonl').read_text().splitlines()]
        self.assertEqual(len(modes), 4)
        self.assertEqual([x['pin'] for x in modes[:2]], ['RDB_WR_A', 'RDB_WR_B'])
        configs = [json.loads(x) for x in (report / 'uram_configs.jsonl').read_text().splitlines()]
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0]['SELF_ADDR_A'], '0')
        self.assertEqual(configs[0]['CASCADE_ORDER_A'], 'NONE')
        self.assertEqual(configs[0]['IS_RDB_WR_A_INVERTED'], '1')
        self.assertEqual(configs[0]['IS_EN_A_INVERTED'], '1')
        self.assertEqual(configs[0]['USE_EXT_CE'], '1')

    def test_api_failure_keeps_partial_without_completion(self):
        p, report = self.run_diag('proc all_fanin {args} {error {forced native failure}}')
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((report / 'diagnostic_complete.json').exists())
        self.assertTrue((report / 'uram_address_pins.jsonl.partial').exists())
        self.assertIn('forced native failure', p.stderr)

    def test_auxiliary_empty_directdriver_error_and_bound(self):
        mutation = r'''
rename get_pins original_get_pins
proc get_pins {args} {
 if {[lindex $args end] eq {DIRECTION == IN}} {set cell [lindex $args end-2];return [list $cell/CAS_IN_EN_A $cell/EN_A]}
 return [original_get_pins {*}$args]
}
rename get_nets original_get_nets
proc get_nets {args} {if {[string match */CAS_IN_EN_A [lindex $args end]]} {return {}};return [original_get_nets {*}$args]}
'''
        p, report = self.run_diag(mutation)
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(x) for x in (report / 'uram_auxiliary_pins.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['pin'], 'CAS_IN_EN_A')
        self.assertEqual(rows[0]['nets'], [])
        self.assertEqual(rows[0]['drivers'], [])
        self.assertEqual(rows[1]['drivers'], ['ff/Q'])
        self.assertEqual(json.loads((report / 'diagnostic_complete.json').read_text())['auxiliary_rows'], 4)
        p, report = self.run_diag(mutation + '\nset m003_uram_diag::max_auxiliary_pins 1')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Auxiliary input bound exceeded', p.stderr)
        self.assertFalse((report / 'diagnostic_complete.json').exists())
        p, report = self.run_diag(mutation + r'''
rename get_property original_get_property
proc get_property {key objects} {if {$key eq {REF_NAME} && $objects eq {ff}} {error {forced directdriver error}};return [original_get_property $key $objects]}
''')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('forced directdriver error', p.stderr)
        self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_empty_duplicate_or_overbound_cell_collection_rejected(self):
        for mutation in ['proc get_cells {args} {return {}}', 'proc get_cells {args} {return {same same}}', 'set m003_uram_diag::max_collection 1']:
            with self.subTest(mutation=mutation):
                p, report = self.run_diag(mutation)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_cell_scope_and_slice_identity_rejected(self):
        p, report = self.run_diag('proc get_cells {args} {return {foreign0 foreign1}}')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('identity differs', p.stderr)
        self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_unconnected_net_is_raw_data_and_wrong_pin_count_rejected(self):
        p, report = self.run_diag('proc get_nets {args} {return {}}\nrename get_pins original_get_pins\nproc get_pins {args} {if {[lsearch -exact $args -leaf] >= 0 && [lindex $args end-2] eq {}} {error {empty native collection}};return [original_get_pins {*}$args]}')
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(x) for x in (report / 'uram_address_pins.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['nets'], [])
        self.assertEqual(rows[0]['single_constant_driver'], 0)
        for mutation in ['set m003_uram_diag::expected_pins 3']:
            with self.subTest(mutation=mutation):
                p, report = self.run_diag(mutation)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse((report / 'diagnostic_complete.json').exists())

    def test_quote_and_array_roundtrip_without_native(self):
        code = 'set ::env(M003_URAM_ADDRESS_LIBRARY_ONLY) 1\nsource {' + str(TCL) + '}\nputs [m003_uram_diag::array [list {a"b} {c\\d} {ADDR_A[22]} "x\\ny"]]\n'
        p = subprocess.run(['tclsh'], input=code, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), ['a"b', 'c\\d', 'ADDR_A[22]', 'x\ny'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
