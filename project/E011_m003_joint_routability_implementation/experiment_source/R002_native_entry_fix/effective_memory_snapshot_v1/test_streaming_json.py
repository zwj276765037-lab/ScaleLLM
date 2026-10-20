"""Compare actual candidate streaming bytes to the preserved old output block."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parent
text = (BASE / 'm003_joint_checks.tcl.proposed').read_text()
PROCS = 'namespace eval m003 {}\n' + text[text.index('proc m003::jq'):text.index('# Empty native collections')]
OLD = (BASE / 'old_snapshot_output_block.tcl').read_text()
FIXTURE = r'''
set meta [dict create phase {synth} weird "quote\" back\\ line\nnext\tend" unicode {汉字}]
set cells [list [dict create NAME {cell[0]/D} empty {} nets {a b c}] [dict create NAME {cell[1]} escaped {braces{} slash\ quote"}]]
set edges {};set inputs [list [dict create source {core/Q} loads {one two}]]
set pins [list [dict create pin {ADDR_A[22]} drivers {GND/G} startpoints {}]]
set controller {};set pblocks {};set target_sites [dict create first {SLICE_X0Y0 SLICE_X1Y1} empty {}]
set helper_pins {};set configs [list [dict create SELF_MASK_A {11'h7E0} inverted {1'b0}]]
set control_sources [dict create clock {clk} reset {rst_n}]
set boundaries [list [dict create tag {input} width 256]]
'''
PARTS = 'set parts [dict create meta $meta cells $cells ce_edges $edges master_inputs $inputs memory_pins $pins meta_ref_cells $controller pblocks $pblocks target_sites $target_sites helper_pins $helper_pins uram_configs $configs control_sources $control_sources boundaries $boundaries]\n'


class StreamingJSON(unittest.TestCase):
    def run_fixture(self, mutation='', tail=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        body = FIXTURE + mutation + '\nset out {' + str(folder) + '}\nset phase fixture\n' + OLD + PARTS
        body += tail or 'write_snapshot_file [file join $out streamed.json] $parts\n'
        code = PROCS + '\nif {[catch {namespace eval m003 {\n' + body + '\n}} message options]} {puts stderr $message;exit 1}\n'
        result = subprocess.run(['tclsh'], input=code, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result, folder

    def test_exact_old_bytes_and_json_for_all_fields_and_escaping(self):
        _, folder = self.run_fixture()
        old = (folder / 'm003_native_fixture.json').read_bytes()
        new = (folder / 'streamed.json').read_bytes()
        self.assertEqual(new, old)
        value = json.loads(new)
        self.assertEqual(list(value), ['meta', 'cells', 'ce_edges', 'master_inputs', 'memory_pins', 'meta_ref_cells', 'pblocks', 'target_sites', 'helper_pins', 'uram_configs', 'control_sources', 'boundaries'])
        self.assertEqual(value['meta']['unicode'], '汉字')
        self.assertEqual(value['memory_pins'][0]['startpoints'], '')
        self.assertFalse((folder / 'streamed.json.partial').exists())

    def test_large_array_is_byte_identical(self):
        mutation = r'''
set cells {}
for {set i 0} {$i<2000} {incr i} {lappend cells [dict create NAME [format {payload[%d]} $i] nets [string repeat {net/segment[0] net/segment[1] } 20]]}
'''
        _, folder = self.run_fixture(mutation)
        self.assertEqual((folder / 'streamed.json').read_bytes(), (folder / 'm003_native_fixture.json').read_bytes())
        self.assertEqual(len(json.loads((folder / 'streamed.json').read_text())['cells']), 2000)

    def test_bad_row_preserves_partial_no_final_and_closes_channel(self):
        tail = r'''
dict set parts cells [list [list odd]]
set before [lsort [chan names]]
set code [catch {write_snapshot_file [file join $out streamed.json] $parts} message options]
puts "$code [expr {[lsort [chan names]] eq $before}]"
'''
        result, folder = self.run_fixture(tail=tail)
        self.assertEqual(result.stdout.strip(), '1 1')
        self.assertFalse((folder / 'streamed.json').exists())
        self.assertTrue((folder / 'streamed.json.partial').exists())

    def test_existing_final_or_partial_is_never_overwritten(self):
        for suffix in ['', '.partial']:
            with self.subTest(suffix=suffix):
                tail = 'set path [file join $out streamed.json]\nset h [open $path' + suffix + ' w];puts -nonewline $h sentinel;close $h\nputs [catch {write_snapshot_file $path $parts}]\n'
                result, folder = self.run_fixture(tail=tail)
                self.assertEqual(result.stdout.strip(), '1')
                self.assertEqual((folder / ('streamed.json' + suffix)).read_bytes(), b'sentinel')

    def test_original_error_options_propagate_without_cleanup_masking(self):
        tail = r'''
rename write_snapshot_json implementation
proc write_snapshot_json {handle parts} {puts -nonewline $handle \{;return -code error -errorcode {SIM_WRITE IO} {forced writer error}}
set code [catch {write_snapshot_file [file join $out streamed.json] $parts} message options]
puts "$code|$message|[dict get $options -errorcode]"
'''
        result, folder = self.run_fixture(tail=tail)
        self.assertEqual(result.stdout.strip(), '1|forced writer error|SIM_WRITE IO')
        self.assertFalse((folder / 'streamed.json').exists())
        self.assertTrue((folder / 'streamed.json.partial').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
