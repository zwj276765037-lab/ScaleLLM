"""Execute real diagnostic Tcl against bounded native-API mocks, never EDA."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
MOCK = r'''
set ::env(M003_ROLE_DIAG_LIBRARY_ONLY) 1
source [lindex $argv 0]
set report [lindex $argv 1]
set mode [lindex $argv 2]
set ::enumerations [dict create]
set ::identity_reads 0
set ::attribute_reads 0
set ::payload {}
foreach family {head tail} {
    for {set bit 0} {$bit < 6560} {incr bit} {
        lappend ::payload [format {core/u_mlp/u_serial_command/u_shared_compute/g_m003_parent_ce.g_payload_bit[%d].parent_%s_r_reg} $bit $family]
    }
}
foreach name {parent_count_r_reg[0] foreign/parent_head_r_reg[6560] g_bad/parent_head_r_reg_replica} {lappend ::payload $name}
set ::groups [dict create parent_scope_candidates {core/u_mlp/u_serial_command/u_shared_compute} parent_payload_and_count_native $::payload parent_buffer_native {core/u_shared_compute/g_ce_group[0].u_ce_buffer} metadata_native_names {core/u_attention/u_meta/addr_reg[0]}]
proc get_cells {args} {
    set filter [lindex $args end]
    foreach pair $::m003_role_diag::collections {
        lassign $pair name wanted
        if {$filter eq $wanted} {return [dict get $::groups $name]}
    }
    error {Unexpected query scope}
}
proc list_property {object} {
    if {![file exists [file join $::report query_counts.json]] || ![file exists [file join $::report parent_scope_candidates.identity.jsonl]]} {error {Attributes preceded closed counts/full identities}}
    dict incr ::enumerations $object
    set props {NAME REF_NAME CLASS PARENT ORIG_CELL_NAME ORIG_REF_NAME IS_PRIMITIVE DONT_TOUCH}
    if {$object eq [lindex $::payload 1]} {set props [lsearch -all -inline -not -exact $props ORIG_CELL_NAME]}
    if {$::mode eq {support_error} && $object eq [lindex $::payload 2]} {error {mock support failure}}
    return $props
}
proc get_property {args} {
    lassign [lrange $args end-1 end] key object
    if {$key in {NAME REF_NAME CLASS}} {incr ::identity_reads} else {incr ::attribute_reads}
    if {$::mode eq {api_error} && $object eq [lindex $::payload 2] && $key eq {ORIG_REF_NAME}} {error {mock native property failure}}
    if {$::mode eq {identity_error} && $object eq [lindex $::payload 2] && $key eq {NAME}} {error {mock NAME failure}}
    switch -- $key {
        NAME {return $object}
        REF_NAME {return FDRE}
        CLASS {return cell}
        PARENT {return {core/parent}}
        ORIG_CELL_NAME {return {}}
        ORIG_REF_NAME {return "origin\tquote\"slash\\line\n"}
        IS_PRIMITIVE {return 1}
        DONT_TOUCH {return 0}
        default {error {Unexpected property}}
    }
}
set rc [catch {::m003_role_diag::run $report} message]
set h [open [file join $report mock_summary.txt] w]
puts $h "rc=$rc\nmessage=$message\nunique=[dict size $::enumerations]\nidentity_reads=$::identity_reads\nattribute_reads=$::attribute_reads"
dict for {object count} $::enumerations {if {$count != 1} {puts $h "BAD_ENUM=$count"}}
close $h
if {$rc} {puts stderr $message; exit 1}
'''


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='m003-role-diag-')
        cls.base = Path(cls.tmp.name)
        cls.mock = cls.base / 'mock.tcl'
        cls.mock.write_text(MOCK)
        cls.runs = {}
        for mode in ('good', 'api_error', 'identity_error', 'support_error'):
            report = cls.base / mode
            report.mkdir()
            run = subprocess.run(['tclsh', str(cls.mock), str(HERE / 'read_core_roles.tcl'), str(report), mode],
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (report / 'stdout.log').write_text(run.stdout)
            cls.runs[mode] = (report, run)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def rows(self, report, name):
        return [json.loads(row) for row in (report / name).read_text().splitlines()]

    def test_complete_large_pool_and_neighbors(self):
        report, run = self.runs['good']
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = self.rows(report, 'parent_payload_and_count_native.jsonl')
        self.assertEqual(len(rows), 13123)
        self.assertEqual([row['index'] for row in rows], list(range(13123)))
        self.assertEqual(len({row['object'] for row in rows}), 13123)
        self.assertIn('parent_count_r_reg[0]', {row['object'] for row in rows})
        for family in ('head', 'tail'):
            for bit in range(6560):
                self.assertEqual(rows[bit + (6560 if family == 'tail' else 0)]['fields']['NAME']['value'],
                    f'core/u_mlp/u_serial_command/u_shared_compute/g_m003_parent_ce.g_payload_bit[{bit}].parent_{family}_r_reg')

    def test_exact_original_fields_and_per_object_enumeration(self):
        report, _ = self.runs['good']
        rows = self.rows(report, 'parent_payload_and_count_native.jsonl')
        self.assertEqual(list(rows[0]['fields']), ['NAME', 'REF_NAME', 'PARENT', 'ORIG_CELL_NAME', 'ORIG_REF_NAME', 'IS_PRIMITIVE', 'DONT_TOUCH'])
        summary = (report / 'mock_summary.txt').read_text()
        self.assertIn('unique=13126', summary)
        self.assertIn('identity_reads=39378', summary)
        self.assertNotIn('BAD_ENUM', summary)

    def test_same_class_ref_can_have_different_support_and_empty(self):
        report, _ = self.runs['good']
        rows = self.rows(report, 'parent_payload_and_count_native.jsonl')
        self.assertEqual(rows[0]['fields']['ORIG_CELL_NAME'], {'status': 'OK_EMPTY', 'value': ''})
        self.assertEqual(rows[1]['fields']['ORIG_CELL_NAME'], {'status': 'UNSUPPORTED', 'value': None})
        self.assertEqual(rows[2]['fields']['ORIG_CELL_NAME'], {'status': 'OK_EMPTY', 'value': ''})
        self.assertEqual(rows[0]['fields']['ORIG_REF_NAME']['value'], 'origin\tquote"slash\\line\n')

    def test_staging_and_finite_batches(self):
        report, _ = self.runs['good']
        events = self.rows(report, 'diagnostic_progress.jsonl')
        kinds = [x['event'] for x in events]
        self.assertLess(kinds.index('counts_closed'), kinds.index('dump_begin'))
        first_attr = next(i for i, x in enumerate(events) if x.get('stage') == 'attributes')
        self.assertLess(kinds.index('all_identities_closed'), first_attr)
        batches = [int(x['rows_written']) for x in events if x['event'] == 'dump_batch' and x.get('collection') == 'parent_payload_and_count_native' and x.get('stage') == 'identity']
        self.assertEqual(batches, list(range(256, 13123, 256)) + [13123])
        self.assertEqual(len(list(report.glob('*.partial'))), 0)
        self.assertTrue((report / 'diagnostic_complete.json').is_file())

    def test_native_api_error_leaves_partial_and_no_complete(self):
        for mode in ('api_error', 'support_error', 'identity_error'):
            with self.subTest(mode=mode):
                report, run = self.runs[mode]
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((report / 'diagnostic_complete.json').exists())
                self.assertTrue((report / 'query_counts.json').is_file())
                self.assertGreater(len(list(report.glob('*.partial'))), 0)
                name = 'parent_payload_and_count_native' + ('.identity' if mode == 'identity_error' else '') + '.jsonl.partial'
                rows = self.rows(report, name)
                self.assertTrue(any(v['status'] == 'API_ERROR' and v['value'] is None for v in rows[2]['fields'].values()))
                if mode != 'identity_error':
                    self.assertTrue((report / 'parent_payload_and_count_native.identity.jsonl').is_file())

    def test_counts_preserve_all_four_native_scopes(self):
        report, _ = self.runs['good']
        data = json.loads((report / 'query_counts.json').read_text())
        self.assertEqual({k: v['count'] for k, v in data['collections'].items()}, {
            'parent_scope_candidates': 1, 'parent_payload_and_count_native': 13123,
            'parent_buffer_native': 1, 'metadata_native_names': 1})
        self.assertFalse(data['constraint_apply_requested'])
        self.assertFalse(data['new_synthesis_launched'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
