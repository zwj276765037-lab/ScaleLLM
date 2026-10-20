"""Differential CPU execution of old/new Tcl reads and unchanged native guards."""
from pathlib import Path
import json
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SCRIPT = ROOT / 'project/hardware/vivado/scripts/m003_joint_checks.tcl'
FIXTURE = r'''
proc reset {} {
    set ::schemas [dict create a {NAME REF_NAME LOC BEL IS_LOC_FIXED IS_BEL_FIXED RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH ORIG_CELL_NAME ORIG_REF_NAME USER_SLR_ASSIGNMENT} b {NAME REF_NAME LOC IS_LOC_FIXED IS_BEL_FIXED MACRO_NAME RLOC RLOC_ORIGIN}]
    set ::values [dict create a [dict create NAME a REF_NAME FDRE LOC {} BEL {} IS_LOC_FIXED 0 IS_BEL_FIXED 0 RLOC {} RLOC_ORIGIN {} MACRO_NAME {} DONT_TOUCH {} ORIG_CELL_NAME {} ORIG_REF_NAME FDRE USER_SLR_ASSIGNMENT {}] b [dict create NAME b REF_NAME FDRE LOC {} IS_LOC_FIXED 0 IS_BEL_FIXED 0 RLOC {} RLOC_ORIGIN {} MACRO_NAME {}]]
    set ::enumerations [dict create];set ::gets [dict create];set ::writes {};set ::existing {};set ::pb_exists 0;set ::other_soft 0
    set ::m003::ancestor_pblocks [dict create]
    unset -nocomplain ::list_error ::get_error
}
proc list_property {object} {
    dict incr ::enumerations $object
    if {[info exists ::list_error] && $object eq $::list_error} {error {mock support API error}}
    if {$object eq {other}} {return {IS_SOFT}}
    return [dict get $::schemas $object]
}
proc get_property {args} {
    lassign [lrange $args end-1 end] key object
    dict incr ::gets $object/$key
    if {[info exists ::get_error] && "$object/$key" eq $::get_error} {error {mock get API error}}
    if {$object eq {other} && $key eq {IS_SOFT}} {return $::other_soft}
    if {$key eq {NAME} && $object in {SLR2 X3Y4}} {return $object}
    if {$key eq {NAME} && $object eq {}} {return {}}
    return [dict get $::values $object $key]
}
proc get_pblocks {args} {
    if {[lsearch -exact $args -of_objects]>=0} {return $::existing}
    return [expr {$::pb_exists ? {target} : {}}]
}
proc create_pblock {name} {lappend ::writes [list create $name];set ::pb_exists 1}
proc set_property {args} {lappend ::writes [linsert $args 0 set]}
proc resize_pblock {args} {lappend ::writes [linsert $args 0 resize]}
proc add_cells_to_pblock {args} {lappend ::writes [linsert $args 0 add]}
proc get_sites {args} {return [lindex $args end]}
proc get_slrs {args} {return SLR2}
proc get_clock_regions {args} {return X3Y4}
'''


class PropertyReadingTests(unittest.TestCase):
    def execute(self, mutation='', operation='hard', second_call=''):
        code = f'source {{{SCRIPT}}}\n' + FIXTURE
        call = 'm003::hard_pblock target SLICE_X0Y0 {a b}' if operation == 'hard' else 'm003::cell_row a payload [dict create role extra bit 9]'
        code += f'reset\n{mutation}\nset old_rc [catch {{{call}}} old_value]\nset old_writes $::writes\nset old_gets $::gets\n'
        code += f'source {{{HERE / "property_reading.tcl"}}}\nreset\n{mutation}\nset new_rc [catch {{{call}}} new_value]\n'
        code += r'''
if {$old_rc!=$new_rc || $old_value ne $new_value || $old_writes ne $::writes || $old_gets ne $::gets} {
    error "Differential mismatch: rc=$old_rc/$new_rc result=$old_value/$new_value writes=$old_writes/$::writes gets=$old_gets/$::gets"
}
if {$new_rc && [llength $::writes]} {error {Mutation before failed qualification}}
puts "rc=$new_rc"
puts "result=$new_value"
puts "enumerations=$::enumerations"
puts "gets=$::gets"
puts "writes=$::writes"
'''
        code += second_call
        wrapped = 'if {[catch {\n' + code + '\n} message]} {puts stderr $message;exit 1}\n'
        run = subprocess.run(['tclsh'], input=wrapped, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout

    def test_hard_pblock_per_cell_once_with_distinct_support_schemas(self):
        out = self.execute()
        self.assertIn('rc=0\n', out)
        self.assertIn('enumerations=a 1 b 1', out)
        self.assertNotIn('a/LOC', out)
        self.assertNotIn('b/LOC', out)
        self.assertIn('add target {a b}', out)

    def test_fixed_loc_is_only_read_when_fixed_and_stays_qualified(self):
        out = self.execute('dict set ::values a IS_LOC_FIXED 1\ndict set ::values a LOC SLICE_X0Y0')
        self.assertIn('rc=0\n', out)
        self.assertIn('a/LOC 1', out)
        self.assertNotIn('b/LOC', out)

    def test_guard_rejections_and_early_errors_make_no_native_writes(self):
        cases = [
            'dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] IS_LOC_FIXED]',
            'dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] IS_BEL_FIXED]',
            'dict set ::values a MACRO_NAME macro0',
            'dict set ::values a RLOC X0Y0',
            'dict set ::values a RLOC_ORIGIN X0Y0',
            'set ::existing other',
            'dict set ::values a IS_LOC_FIXED 1\ndict set ::values a LOC SLICE_X9Y9',
            'set ::list_error a',
            'set ::get_error a/MACRO_NAME',
            'set ::get_error a/IS_LOC_FIXED',
        ]
        for mutation in cases:
            with self.subTest(mutation=mutation):
                self.assertIn('rc=1\n', self.execute(mutation))

    def test_optional_macro_relative_unsupported_policy_is_unchanged(self):
        mutation = r'''
foreach property {MACRO_NAME RLOC RLOC_ORIGIN} {dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] $property]}
'''
        self.assertIn('rc=0\n', self.execute(mutation))

    def test_other_pblock_uses_its_own_support_not_cell_schema(self):
        out = self.execute('set ::existing other')
        self.assertIn('enumerations=a 1 other 1', out)
        self.assertIn('rc=1\n', out)

    def test_soft_other_pblock_remains_compatible(self):
        self.assertIn('rc=0\n', self.execute('set ::existing other\nset ::other_soft 1'))

    def test_cell_row_preserves_all_fields_empty_unsupported_extra_merge(self):
        out = self.execute(operation='row')
        self.assertIn('enumerations=a 1', out)
        self.assertIn('role extra', out)
        self.assertIn('DONT_TOUCH {}', out)
        self.assertIn('SLR UNPLACED clock_region UNPLACED bit 9', out)
        mutation = 'dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] DONT_TOUCH]'
        out = self.execute(mutation, operation='row')
        self.assertIn('DONT_TOUCH NOT_SUPPORTED', out)

    def test_cell_row_support_refreshes_between_calls(self):
        second = r'''
dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] DONT_TOUCH]
set second [m003::cell_row a payload {}]
if {[dict get $second DONT_TOUCH] ne {NOT_SUPPORTED}} {error {Stale support across invocations}}
if {[dict get $::enumerations a]!=2} {error {Expected new enumeration per invocation}}
puts fresh_support_pass
'''
        self.assertIn('fresh_support_pass', self.execute(operation='row', second_call=second))

    def test_placed_cell_row_preserves_site_slr_and_region(self):
        out = self.execute('dict set ::values a LOC SLICE_X0Y0', operation='row')
        self.assertIn('SLR SLR2 clock_region X3Y4', out)
        self.assertIn('enumerations=a 1', out)

    def test_hard_guard_support_refreshes_between_calls(self):
        second = r'''
dict set ::schemas a [lsearch -all -inline -not -exact [dict get $::schemas a] IS_LOC_FIXED]
set ::writes {}
set second_rc [catch {m003::hard_pblock target SLICE_X0Y0 {a b}}]
if {!$second_rc || [llength $::writes]} {error {Stale fixed-policy support or early writes}}
if {[dict get $::enumerations a]!=2} {error {Expected new enumeration per invocation}}
puts fresh_support_pass
'''
        self.assertIn('fresh_support_pass', self.execute(second_call=second))

    def test_cell_row_list_and_get_api_errors_propagate(self):
        for mutation in ('set ::list_error a', 'set ::get_error a/LOC', 'set ::get_error a/DONT_TOUCH'):
            with self.subTest(mutation=mutation):
                self.assertIn('rc=1\n', self.execute(mutation, operation='row'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
