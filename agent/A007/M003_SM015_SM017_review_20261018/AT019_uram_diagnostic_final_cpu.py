"""A007 bounded CPU fixtures for fixed db04eeb5 diagnostic; no native execution."""
from pathlib import Path
import importlib.util
import json
import unittest

ROOT=Path(__file__).resolve().parents[3]
TARGET=Path(__file__).with_name('AT019_final_diagnostic_fixture')/'test_diagnostic.py'
spec=importlib.util.spec_from_file_location('submitted_diagnostic',TARGET)
submitted=importlib.util.module_from_spec(spec)
spec.loader.exec_module(submitted)

class Independent(unittest.TestCase):
    run_diag=submitted.Diagnostic.run_diag
    def rows(self,report):
        return [json.loads(x) for x in (report/'uram_address_pins.jsonl').read_text().splitlines()]

    def test_vcc_value_comes_from_single_actual_ref(self):
        p,r=self.run_diag('rename get_property original_get_property\nproc get_property {key objects} {if {$key eq "REF_NAME" && $objects eq "gnd"} {return VCC};return [original_get_property $key $objects]}')
        self.assertEqual(p.returncode,0,p.stderr)
        row=self.rows(r)[0]
        self.assertEqual(row['driver_refs'],['VCC'])
        self.assertEqual(row['startpoints'],[])
        self.assertEqual(row['single_constant_driver'],1)
        self.assertEqual(row['constant_value_from_single_driver_ref'],1)

    def test_multiple_drivers_are_not_classified_constant(self):
        p,r=self.run_diag('rename get_pins original_get_pins\nproc get_pins {args} {if {[lsearch -exact $args -leaf] >= 0} {return {gnd/G ff/Q}};return [original_get_pins {*}$args]}')
        self.assertEqual(p.returncode,0,p.stderr)
        row=self.rows(r)[0]
        self.assertEqual(row['driver_refs'],['GND','FDCE'])
        self.assertEqual(row['drivers'],['gnd/G','ff/Q'])
        self.assertEqual(row['single_constant_driver'],0)
        self.assertIsNone(row['constant_value_from_single_driver_ref'])

    def test_all_four_native_address_families_and_mode_inventory(self):
        mutation=r"""
set m003_uram_diag::expected_pins 92
set m003_uram_diag::expected_mode_pins 2
rename get_pins original_get_pins
proc get_pins {args} {
 if {[lsearch -exact $args -leaf] >= 0} {return [original_get_pins {*}$args]}
 set cell [lindex $args end-2]
 if {[string match {*RDB_WR*} [lindex $args end]]} {return [list $cell/RDB_WR_A $cell/RDB_WR_B]}
 set pins {}
 foreach family {ADDR_A ADDR_B CAS_IN_ADDR_A CAS_IN_ADDR_B} {
  for {set bit 0} {$bit < 23} {incr bit} {lappend pins [format {%s/%s[%d]} $cell $family $bit]}
 }
 return $pins
}
"""
        p,r=self.run_diag(mutation)
        self.assertEqual(p.returncode,0,p.stderr)
        rows=self.rows(r)
        expected={f'{family}[{bit}]' for family in ['ADDR_A','ADDR_B','CAS_IN_ADDR_A','CAS_IN_ADDR_B'] for bit in range(23)}
        self.assertEqual(len(rows),184)
        for i in [0,1]:
            group=[x for x in rows if x['slice']==i]
            self.assertEqual(len(group),92)
            self.assertEqual({x['pin'] for x in group},expected)
            self.assertTrue(all(x['pin_name']==x['cell']+'/'+x['pin'] for x in group))
        modes=[json.loads(x) for x in (r/'uram_mode_pins.jsonl').read_text().splitlines()]
        self.assertEqual(len(modes),4)
        self.assertEqual(json.loads((r/'diagnostic_complete.json').read_text())['rows'],184)

    def test_out_of_range_physical_bit_rejected(self):
        p,r=self.run_diag(r'rename get_pins original_get_pins'+ '\n' + r'proc get_pins {args} {if {[lsearch -exact $args -leaf] >= 0 || [string match {*RDB_WR*} [lindex $args end]]} {return [original_get_pins {*}$args]};set cell [lindex $args end-2];return [list $cell/ADDR_A\[23\] $cell/ADDR_A\[0\]]}')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Physical address terminal differs',p.stderr)
        self.assertFalse((r/'diagnostic_complete.json').exists())

    def test_duplicate_mode_pin_rejected(self):
        p,r=self.run_diag(r'set m003_uram_diag::expected_mode_pins 2'+ '\n' + r'rename get_pins original_get_pins'+ '\n' + r'proc get_pins {args} {if {[string match {*RDB_WR*} [lindex $args end]]} {set cell [lindex $args end-2];return [list $cell/RDB_WR_A $cell/RDB_WR_A]};return [original_get_pins {*}$args]}')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Invalid bounded collection mode_pins',p.stderr)
        self.assertFalse((r/'diagnostic_complete.json').exists())


    def test_auxiliary_exact_predicate_without_extra_fanin(self):
        mutation=r"""
rename get_pins original_get_pins
proc get_pins {args} {
 if {[lindex $args end] eq {DIRECTION == IN}} {
  set cell [lindex $args end-2];set pins {}
  foreach terminal {ADDR_A[0] CAS_IN_ADDR_B[22] RDB_WR_A RDB_WR_B EN_A BWE_A[0] CLK CAS_IN_DIN_A[0] CAS_IN_RDACCESS_A CAS_IN_RDB_WR_A CAS_IN_EN_A RST_A SLEEP DIN_A[0]} {lappend pins $cell/$terminal}
  return $pins
 }
 return [original_get_pins {*}$args]
}
rename all_fanin original_all_fanin
proc all_fanin {args} {puts A007_FANIN_QUERY;return [original_all_fanin {*}$args]}
"""
        p,r=self.run_diag(mutation)
        self.assertEqual(p.returncode,0,p.stderr)
        rows=[json.loads(x) for x in (r/'uram_auxiliary_pins.jsonl').read_text().splitlines()]
        expected={'EN_A','BWE_A[0]','CLK','CAS_IN_DIN_A[0]','CAS_IN_RDACCESS_A','CAS_IN_RDB_WR_A','CAS_IN_EN_A'}
        self.assertEqual(len(rows),14)
        for i in [0,1]:
            self.assertEqual({x['pin'] for x in rows if x['slice']==i},expected)
        self.assertEqual(p.stdout.count('A007_FANIN_QUERY'),4)
        self.assertEqual(json.loads((r/'diagnostic_complete.json').read_text())['auxiliary_rows'],14)

    def test_auxiliary_nonsingleton_driver_owner_fails(self):
        mutation=r"""
rename get_pins original_get_pins
proc get_pins {args} {if {[lindex $args end] eq {DIRECTION == IN}} {set cell [lindex $args end-2];return [list $cell/EN_A]};return [original_get_pins {*}$args]}
rename get_cells original_get_cells
proc get_cells {args} {if {[lindex $args end] eq {ff/Q}} {return {ff0 ff1}};return [original_get_cells {*}$args]}
"""
        p,r=self.run_diag(mutation)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Auxiliary driver owner is not singleton',p.stderr)
        self.assertFalse((r/'diagnostic_complete.json').exists())
        self.assertTrue((r/'uram_auxiliary_pins.jsonl.partial').exists())

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(submitted),unittest.defaultTestLoader.loadTestsFromTestCase(Independent)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
