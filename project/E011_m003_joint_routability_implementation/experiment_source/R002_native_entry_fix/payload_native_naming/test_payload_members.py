"""Run real candidate Tcl against every closed AT014 native payload name."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HW = ROOT / 'project/hardware'
AT = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT014_fresh_core_native_role_attribution_v2'


class NativeNamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        facts_path = AT / 'evidence/AT014_closed_identity_facts.json'
        facts = json.loads(facts_path.read_text())
        assert hashlib.sha256(facts_path.read_bytes()).hexdigest() == '349af9d966438890b2174355da79f19387dac25f0b99778a0878d4694bbcd8cf'
        native = next(row for row in facts['identities'] if Path(row['path']).name == 'parent_payload_and_count_native.identity.jsonl')
        path = Path(native['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == native['sha256']
        rows = [json.loads(x)['fields'] for x in path.read_text().splitlines()]
        cls.parent = facts['actual_native_parent']
        cls.tmp = tempfile.TemporaryDirectory(prefix='m003-native-payload-')
        cls.pool = Path(cls.tmp.name) / 'native_pool.tcl'
        lines = ['set pool [dict create]', 'set expected [dict create]']
        cls.ids = {}
        for index, row in enumerate(rows):
            name = row['NAME']['value']
            ref = row['REF_NAME']['value']
            assert '{' not in name and '}' not in name and '\\' not in name
            object_id = f'obj{index}'
            lines.append(f'dict set pool {object_id} [dict create NAME {{{name}}} REF_NAME {ref}]')
            if 'g_m003_parent_ce.g_payload_bit[' in name:
                family = 'head' if '.parent_head_r_reg[' in name else 'tail'
                bit = int(name.rsplit('[', 1)[1][:-1])
                cls.ids[family, bit] = object_id
                lines.append(f'dict set expected {family} {bit} {object_id}')
        cls.pool.write_text('\n'.join(lines) + '\n')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_fixture(self, mutation='', body='', full_overlay=False):
        code = f'source {{{HW / "vivado/scripts/m003_joint_checks.tcl"}}}\n'
        code += f'source {{{HERE / "payload_members.tcl"}}}\n'
        code += f'source {{{self.pool}}}\nset ::m003::parent_scope {{{self.parent}}}\n'
        code += r'''
proc get_cells {args} {
    if {[info exists ::forced_return]} {return $::forced_return}
    set filter [lindex $args end]
    set expressions [regexp -all -inline {NAME =~ "([^"]+)"} $filter]
    if {[llength $expressions] != 4} {error {Expected actual two-family NAME query}}
    set selected {}
    dict for {id row} $::pool {
        foreach {whole pattern} $expressions {
            if {[string match $pattern [dict get $row NAME]]} {lappend selected $id; break}
        }
    }
    return $selected
}
proc get_property {key object} {return [dict get $::pool $object $key]}
'''
        if full_overlay:
            code += r'''
set prefix {scalellm_vcu118_f05_bd_i/core/}
dict for {id row} $pool {dict set pool $id NAME "$prefix[dict get $row NAME]"}
set ::m003::parent_scope "$prefix$::m003::parent_scope"
'''
        code += mutation + '\n'
        code += body or r'''
set selected [m003::payload_members]
foreach family {head tail} {
    for {set bit 0} {$bit < 6560} {incr bit} {
        if {[dict get $selected $family $bit] ne [dict get $expected $family $bit]} {error {Native bit identity mismatch}}
    }
}
puts "[dict size [dict get $selected head]] [dict size [dict get $selected tail]] verified_all_13120"
'''
        wrapped = 'if {[catch {\n' + code + '\n} message]} {puts stderr $message;exit 1}\n'
        run = subprocess.run(['tclsh'], input=wrapped, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout.strip()

    def test_every_actual_native_name_and_bit(self):
        self.assertEqual(self.run_fixture(), '6560 6560 verified_all_13120')

    def test_same_relative_roles_under_declared_full_overlay_prefix(self):
        # Prefix assembly is CPU coverage; actual board graph admission is later native recovery.
        self.assertEqual(self.run_fixture(full_overlay=True), '6560 6560 verified_all_13120')

    def test_count_foreign_names_excluded_and_compatible_ff_supported(self):
        mutation = f'dict set pool {self.ids["head", 0]} REF_NAME FDCE\n' + r'''
dict set pool foreign [dict create NAME {other/parent_head_r_reg[0]} REF_NAME FDRE]
dict set pool lookalike [dict create NAME "$::m003::parent_scope\_foreign/g_m003_parent_ce.g_payload_bit\[0\].parent_head_r_reg\[0\]" REF_NAME FDRE]
'''
        self.assertEqual(self.run_fixture(mutation), '6560 6560 verified_all_13120')

    def test_malformed_replica_duplicate_missing_wrong_origin_or_ref_rejected(self):
        head0 = self.ids['head', 0]
        head9 = self.ids['head', 9]
        cases = [
            f'dict unset pool {self.ids["head", 6559]}',
            f'dict unset pool {self.ids["tail", 6550]}',
            f'dict set pool duplicate [dict get $pool {head0}]',
            f'dict set pool {head9} REF_NAME LUT6',
            f'dict set pool replica [dict get $pool {head0}]\ndict set pool replica NAME "[dict get $pool {head0} NAME]_replica"',
            f'dict set pool {head0} NAME {{other/parent_head_r_reg[0]}}',
        ]
        for relative in (
            'g_m003_parent_ce.g_payload_bit[6560].parent_head_r_reg[6560]',
            'g_m003_parent_ce.g_payload_bit[1].parent_head_r_reg[0]',
            'g_m003_parent_ce.g_payload_bit[0].parent_tail_r_reg[1]',
            'g_m003_parent_ce.g_payload_bit[00].parent_head_r_reg[0]',
            'g_m003_parent_ce.g_payload_bit[0].parent_head_r_reg[00]',
            'g_original_parent_ce.parent_head_r_reg[0]',
            'parent_head_r_reg[0]',
            'foreign/g_m003_parent_ce.g_payload_bit[0].parent_head_r_reg[0]',
            'g_m003_parent_ce.g_payload_bit[abc].parent_head_r_reg[0]',
            'g_m003_parent_ce.g_payload_bit[-1].parent_head_r_reg[-1]',
            'g_m003_parent_ce.g_payload_bit[0].parent_head_r_reg[0]/nested',
        ):
            cases.append(f'dict set pool extra [dict create NAME {{{self.parent}/{relative}}} REF_NAME FDRE]')
        for mutation in cases:
            with self.subTest(mutation=mutation):
                self.assertEqual(self.run_fixture(mutation, 'puts [catch {m003::payload_members}]'), '1')

    def test_query_failure_to_filter_foreign_is_still_rejected(self):
        mutation = r'''
dict set pool foreign [dict create NAME {other/g_m003_parent_ce.g_payload_bit[0].parent_head_r_reg[0]} REF_NAME FDRE]
set forced_return [concat [dict values [dict get $expected head]] [dict values [dict get $expected tail]] foreign]
'''
        self.assertEqual(self.run_fixture(mutation, 'puts [catch {m003::payload_members}]'), '1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
