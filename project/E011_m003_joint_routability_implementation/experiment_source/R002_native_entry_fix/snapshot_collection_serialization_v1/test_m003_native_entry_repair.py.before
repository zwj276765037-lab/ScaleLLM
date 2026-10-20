"""Actual Tcl name-filter semantics for the native payload selection repair."""
from pathlib import Path
import subprocess, importlib.util, json, sys, tempfile
import unittest
from unittest.mock import patch

HW = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HW/'vivado/scripts'))
import m003_entry as ENTRY
import m003_native_init as INIT
import m003_synth_recovery as RECOVERY


class PayloadSelection(unittest.TestCase):
    def run_fixture(self, mutation='', body=None):
        source = HW/'vivado/scripts/m003_joint_checks.tcl'
        code = 'source {'+str(source)+'}\n'+r'''
set ::m003::parent_scope root
set pool [dict create]
foreach family {head tail} {
    for {set bit 0} {$bit < 6560} {incr bit} {
        dict set pool ${family}$bit [dict create NAME [format {root/g_m003_parent_ce.g_payload_bit[%d].parent_%s_r_reg[%d]} $bit $family $bit] REF_NAME FDRE]
    }
}
foreach bit {0 1} {
    dict set pool count$bit [dict create NAME [format {root/parent_count_r_reg[%d]} $bit] REF_NAME FDRE]
}
dict set pool foreign [dict create NAME {other/parent_head_r_reg[0]} REF_NAME FDRE]
proc get_cells {args} {
    set filter [lindex $args [expr {[lsearch -exact $args -filter]+1}]]
    set patterns [regexp -all -inline {NAME =~ "([^"]+)"} $filter]
    if {![llength $patterns]} {error "fixture cannot evaluate the actual NAME query"}
    set result {}
    dict for {id row} $::pool {
        foreach {expression pattern} $patterns {
            if {[string match $pattern [dict get $row NAME]]} {lappend result $id;break}
        }
    }
    return $result
}
proc get_property {property object} {return [dict get $::pool $object $property]}
'''
        code += mutation+'\n'
        code += body or r'''
set selected [m003::payload_members]
puts "[dict size [dict get $selected head]] [dict size [dict get $selected tail]] [dict exists $selected head 0] [dict exists $selected head 6559] [dict exists $selected tail 0] [dict exists $selected tail 6559]"
'''
        wrapped = 'if {[catch {\n'+code+'\n} message]} {puts stderr $message;exit 1}\n'
        result = subprocess.run(['tclsh'], input=wrapped, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_full_13120_payload_with_count_and_foreign_scope_in_same_pool(self):
        self.assertEqual(self.run_fixture(), '6560 6560 1 1 1 1')

    def test_old_query_actually_admits_count_from_same_pool(self):
        body = r'''
set old [get_cells -quiet -hier -filter {IS_PRIMITIVE == 1 && NAME =~ "root/*parent_*_r_reg*"}]
puts "[llength $old] [expr {"count0" in $old}] [expr {"count1" in $old}]"
'''
        self.assertEqual(self.run_fixture(body=body), '13122 1 1')

    def test_malformed_incomplete_duplicate_or_wrong_scope_still_rejected(self):
        mutations = [
            'dict unset pool head6559',
            'dict unset pool tail6550',
            'dict set pool duplicate [dict get $pool head0]',
            'dict set pool extra [dict create NAME {root/g_m003_parent_ce.g_payload_bit[6560].parent_head_r_reg[6560]} REF_NAME FDRE]',
            'dict set pool head9 REF_NAME LUT6',
            'dict set pool replica [dict create NAME {root/g_m003_parent_ce.g_payload_bit[0].parent_head_r_reg[0]_replica} REF_NAME FDRE]',
            'dict set pool head0 NAME {other/parent_head_r_reg[0]}',
            'dict set pool malformed [dict create NAME {root/g_m003_parent_ce.g_payload_bit[abc].parent_tail_r_reg[abc]} REF_NAME FDRE]',
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertEqual(self.run_fixture(mutation, 'puts [catch {m003::payload_members}]'), '1')


class NativeEntryGuards(unittest.TestCase):
    def test_recovery_metadata_accepts_only_complete_content_bound_inventory(self):
        runs=[dict(run='run'+str(i),checkpoint=dict(path='/fixture/run'+str(i)+'/new.dcp')) for i in range(23)]
        records=[dict(NAME=r['run'],DIRECTORY=str(Path(r['checkpoint']['path']).parent),STATUS='synth_design Complete!',PROGRESS='100%',NEEDS_REFRESH='0') for r in runs]
        records[-1].update(STATUS='Out-of-date',NEEDS_REFRESH='1')
        self.assertEqual(RECOVERY.check_run_metadata(records,runs),['run22'])
        import copy
        mutations=[('PROGRESS','99%'),('STATUS','ERROR'),('NEEDS_REFRESH','NOT_SUPPORTED'),('DIRECTORY','/foreign'),('STATUS','synth_design Complete!')]
        for key,value in mutations:
            bad=copy.deepcopy(records);bad[-1][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):RECOVERY.check_run_metadata(bad,runs)
        for bad in [records[:-1],records+[records[0]],[*records[:-1],records[0]],[*records[:-1],{**records[-1],'NAME':'foreign'}]]:
            with self.assertRaises(ValueError):RECOVERY.check_run_metadata(bad,runs)

    def test_ordinary_fresh_run_guard_still_rejects_stale_without_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            code='source {'+str(HW/'vivado/scripts/m003_joint_checks.tcl')+'}\n'+r'''
proc get_runs {args} {return synth_1}
proc get_property {args} {return synth_1}
proc require_complete_run {name} {error "strict stale rejection"}
unset -nocomplain ::env(HAP_M003_RECOVERED_SYNTHESIS)
puts [catch {m003::require_synthesis_runs} message]
puts $message
'''
            result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.splitlines(),['1','strict stale rejection'])

    def test_existing_file_type_conversion_restores_frozen_policy(self):
        text=(HW/'vivado/scripts/m003_recover_synthesis.tcl').read_text()
        section=text[text.index('set_property FILE_TYPE TCL $file'):text.index('m003::require_project')]
        code=r'''
set file overlay
set report_dir fixture
set properties [dict create FILE_TYPE XDC USED_IN_SYNTHESIS false USED_IN_IMPLEMENTATION true PROCESSING_ORDER LATE]
proc set_property {property value object} {
 if {$property eq "FILE_TYPE"} {dict set ::properties USED_IN_SYNTHESIS true}
 dict set ::properties $property $value
}
proc m002_put {args} {}
proc m003_recovery_overlay_metadata {args} {return fixture}
'''+section+r'''
puts "[dict get $properties FILE_TYPE] [dict get $properties USED_IN_SYNTHESIS] [dict get $properties USED_IN_IMPLEMENTATION] [dict get $properties PROCESSING_ORDER]"
'''
        result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'TCL false true LATE')

    def test_restore_attempt_is_recorded_before_refusing_all_native_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            code='set ::env(HAP_REPORT_DIR) {'+d+'}\nsource {'+str(HW/'vivado/scripts/m003_joint_checks.tcl')+'}\n'+r'''
set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1
puts [catch {m003::apply} message]
puts [string match {*restore must verify*} $message]
puts $::m003::apply_attempts
puts [llength [glob -nocomplain -directory $::env(HAP_REPORT_DIR) m003_apply_success_*]]
'''
            result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.splitlines(),['1','1','1','0'])
            trace=list(Path(d).glob('m003_apply_attempts_*'))
            self.assertEqual(len(trace),1);self.assertIn('restore_verify_only=1',trace[0].read_text())

    def test_missing_or_wrong_source_apply_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with self.assertRaises(ValueError):ENTRY.check_apply(p)
            row=dict(kind='native',success='true',attempt='1',pid='123',source_manifest_sha256=ENTRY.sha(ENTRY.MANIFEST),overlay_sha256=ENTRY.sha(HW/'vivado/constraints/m003_joint_locality.xdc'))
            f=p/'m003_apply_success_123_1.json';f.write_text(json.dumps(row))
            self.assertEqual(ENTRY.check_apply(p)['actual_native_apply_count'],1)
            for key,value in [('success','false'),('kind','fixture'),('pid','0'),('source_manifest_sha256','wrong'),('overlay_sha256','wrong')]:
                f.write_text(json.dumps({**row,key:value}))
                with self.subTest(key=key),self.assertRaises(ValueError):ENTRY.check_apply(p)

    def test_current_native_init_prefix_and_complete_driver_are_both_preserved(self):
        root=HW.parent.parent
        p=root/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT007_native_tcl_and_complete_init_prefix_probe/evidence/native_init_driver_preserved/type_probe.tcl'
        text=p.read_text();prefix=INIT.init_prefix(text)
        self.assertTrue(prefix.rstrip().endswith('OPTRACE "Phase: Init Design" END { }'))
        self.assertNotIn('\nstart_step opt_design\n',prefix)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'prefix.tcl';value=INIT.prepare(p,out)
            self.assertEqual(Path(value['preserved_driver']['path']).read_bytes(),p.read_bytes())
            self.assertEqual(out.read_text(),prefix)
            with self.assertRaises(ValueError):INIT.prepare(p,out)

    def test_native_init_boundary_mutations_rejected(self):
        root=HW.parent.parent
        p=root/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT007_native_tcl_and_complete_init_prefix_probe/evidence/native_init_driver_preserved/type_probe.tcl'
        text=p.read_text();boundary='\nOPTRACE "Phase: Opt Design" START { ROLLUP_AUTO }\n'
        bad=[text.replace(boundary,''),text+boundary,
             text.replace('  end_step init_design','  end_step wrong'),
             text.replace('  link_design -top','  wrong_link -top'),
             text.replace('\nstart_step init_design\n','\nstart_step init_design\nopt_design\n'),
             text.replace('\nstart_step init_design\n','\nstart_step init_design\nstart_step init_design\n')]
        for index,value in enumerate(bad):
            with self.subTest(case=index),self.assertRaises(ValueError):INIT.init_prefix(value)

    def test_recovery_source_delta_rejects_design_or_closure_changes(self):
        design=HW/'rtl/attention/hap_weight_meta_resident.sv'
        entry=HW/'vivado/scripts/m003_entry.py'
        before={design:dict(sha256='design'),entry:dict(sha256='old')}
        after={design:dict(sha256='design'),entry:dict(sha256='new'),**{p:dict(sha256='new-helper') for p in RECOVERY.ADDITIONS}}
        self.assertEqual(RECOVERY.validate_delta(before,after)['changed'],[str(entry)])
        bad={**after,design:dict(sha256='changed-design')}
        with self.assertRaises(ValueError):RECOVERY.validate_delta(before,bad)
        bad=dict(after);bad.pop(next(iter(RECOVERY.ADDITIONS)))
        with self.assertRaises(ValueError):RECOVERY.validate_delta(before,bad)
        with self.assertRaises(ValueError):RECOVERY.validate_delta(before,{**after,HW/'rtl/new.sv':dict(sha256='unexpected')})


class CurrentNativeConstraintReads(unittest.TestCase):
    def exercise(self,kind):
        import m003_physical_evidence as PHYSICAL
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);board=p/'board.xdc';overlay=p/'m003_joint_locality.xdc'
            board.write_text('board fixture');overlay.write_text('overlay fixture')
            lines=[]
            if kind!='empty':lines.append('Parsing XDC File ['+str(board)+']')
            if kind=='both':lines.append('Sourcing Tcl File ['+str(overlay)+']')
            (p/'vivado.log').write_text('\n'.join(lines)+'\n')
            (p/'constraints_project.json').write_text(json.dumps(dict(hashes={},metadata={})))
            (p/'xdc_registry_init_hashed.tsv').write_text('explicit parser unit fixture')
            with patch.object(PHYSICAL,'hash_registry',return_value=({},{})),patch.object(PHYSICAL.entry,'check_apply',return_value=dict(passed=True,fixture=True)):
                result=PHYSICAL.current_native_constraints('init',p)
            return result,json.loads((p/'actual_xdc_reads_init.json').read_text())

    def test_both_native_read_kinds_keep_actual_operation_and_line(self):
        result,reads=self.exercise('both')
        self.assertEqual([r['native_operation'] for r in reads['records']],['Parsing XDC File','Sourcing Tcl File'])
        self.assertEqual([r['line'] for r in reads['records']],[1,2])
        self.assertEqual(result['mode'],'M003_current_native_process')

    def test_missing_native_tcl_or_all_reads_rejected(self):
        for kind in ('xdc_only','empty'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.exercise(kind)




class OriginalAddressSelection(unittest.TestCase):
    # AT016 measured17FDCE state plus2 nonstateCARRY8 neighbors.
    def run_fixture(self, mutation='', prefix='root'):
        code='source {'+str(HW/'vivado/scripts/m003_joint_checks.tcl')+'}\nset ::m003::core_meta_scope {'+prefix+'}\n'+r'''
set pool [dict create]
for {set bit 0} {$bit<17} {incr bit} {dict set pool ff$bit [dict create NAME [format {%s/meta_read_addr_r_reg[%d]} $::m003::core_meta_scope $bit] REF_NAME FDCE]}
foreach {bit index} {16 5 8 2} {dict set pool carry$bit [dict create NAME [format {%s/meta_read_addr_r_reg[%d]_i_%d} $::m003::core_meta_scope $bit $index] REF_NAME CARRY8]}
proc get_cells {args} {
 if {[info exists ::forced]} {return $::forced}
 set filter [lindex $args end]
 if {![regexp {NAME =~ "([^"]+)"} $filter -> pattern]} {error {fixture missing actual family query}}
 set result {};dict for {id row} $::pool {if {[string match $pattern [dict get $row NAME]]} {lappend result $id}};return $result
}
proc get_property {args} {return [dict get $::pool [lindex $args end] [lindex $args end-1]]}
'''
        code+=mutation+'\n';code+=r'''
if {[info exists ::expect_reject]} {puts [catch {m003::original_address_members}]} else {
 set result [m003::original_address_members]
 for {set bit 0} {$bit<17} {incr bit} {if {[dict get $result $bit] ne "ff$bit"} {error {wrong state bit identity}}}
 puts [dict size $result]
}
'''
        proc=subprocess.run(['tclsh'],input='if {[catch {\n'+code+'\n} msg]} {puts stderr $msg;exit 1}\n',text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stderr);return proc.stdout.strip()
    def test_measured17_state_and2_combinational_neighbors(self):
        self.assertEqual(self.run_fixture(),'17')
        self.assertEqual(self.run_fixture(prefix='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention'),'17')
    def test_invalid_state_or_unmeasured_neighbor_still_rejected(self):
        cases=['dict unset pool ff16','dict set pool ff0 REF_NAME LUT2','dict set pool carry16 REF_NAME LUT2','dict set pool duplicate [dict get $pool ff0]','dict set pool ff0 NAME {root/meta_read_addr_r_reg[00]}','dict set pool ff0 NAME {root/meta_read_addr_r_reg[17]}','dict set pool ff0 NAME {root/meta_read_addr_r_reg[0]_replica}','dict set pool carry16 NAME {root/meta_read_addr_r_reg[16]_i_6}','dict set pool ff0 NAME {other/meta_read_addr_r_reg[0]};set forced [dict keys $pool]','set forced [concat [dict keys $pool] ff0]']
        for mutation in cases:
            with self.subTest(mutation=mutation):self.assertEqual(self.run_fixture(mutation+'\nset expect_reject 1'),'1')
    def test_compatible_state_FF_aliases_and_optional_nonstate_logic(self):
        self.assertEqual(self.run_fixture('dict set pool ff0 REF_NAME FDRE;dict set pool ff1 REF_NAME FDSE;dict set pool ff2 REF_NAME FDPE;dict unset pool carry16;dict unset pool carry8'),'17')

if __name__ == '__main__':
    unittest.main()
