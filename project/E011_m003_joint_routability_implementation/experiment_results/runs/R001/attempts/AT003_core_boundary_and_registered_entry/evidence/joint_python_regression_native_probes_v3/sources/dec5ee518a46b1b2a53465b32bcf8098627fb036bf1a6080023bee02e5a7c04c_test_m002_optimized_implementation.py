"""E005 authorization and injected native Tcl failures; no EDA required."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_m002_physical_diagnostic import m
from test_m002_physical_diagnostic import manifest, put
import test_m002_physical_diagnostic as base_tests
import m002_execution_profile as p

SCRIPT = Path(__file__).resolve().parents[1]/'vivado/scripts/m002_route_failure_capture.tcl'


class FailureCapture(unittest.TestCase):
    def run_tcl(self, body):
        with tempfile.TemporaryDirectory() as directory:
            top = Path(directory)
            prefix = 'set ::env(HAP_REPORT_DIR) {'+str(top)+'}\nsource {'+str(SCRIPT)+'}\n'
            script = top/'injection.tcl'
            script.write_text(prefix+body)
            result = subprocess.run(['tclsh',str(script)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('TEST_PASS',result.stdout,result.stdout+result.stderr)

    def test_failed_report_does_not_stop_other_capture_and_original_options_survive(self):
        self.run_tcl(r'''
proc current_design {} {return design}
proc emit {path} {set h [open $path w];puts $h diagnostic;close $h}
proc write_checkpoint {path} {emit $path}
proc report_route_status {args} {error {INJECTED REPORT ERROR}}
proc report_timing_summary {args} {emit [lindex $args end]}
proc report_design_analysis {args} {emit [lindex $args end]}
proc report_drc {args} {emit [lindex $args end]}
proc route_design {args} {return -code error -errorcode {ORIGINAL ROUTE FAILURE} {ORIGINAL ROUTE RESULT}}
m002_install_route_failure_capture
set code [catch {route_design -directive Default} result options]
if {$code != 1 || $result ne {ORIGINAL ROUTE RESULT} || [dict get $options -errorcode] ne {ORIGINAL ROUTE FAILURE}} {error {original error changed}}
foreach name {route_failed.dcp route_failed_timing.rpt route_failed_congestion.rpt route_failed_drc.rpt route_failed_original_error.tcllist} {if {![file exists [file join $::env(HAP_REPORT_DIR) $name]]} {error "missing capture $name"}}
set h [open [file join $::env(HAP_REPORT_DIR) route_failed_capture_receipts.tsv] r];set receipts [read $h];close $h
if {![string match "*route_status\t1*" $receipts] || ![string match "*drc\t0*" $receipts]} {error "independent capture failed: $receipts"}
set h [open [file join $::env(HAP_REPORT_DIR) route_failed_original_error.tcllist] r];set saved [read $h];close $h
if {[dict get $saved result] ne {ORIGINAL ROUTE RESULT} || [dict get [dict get $saved options] -errorcode] ne {ORIGINAL ROUTE FAILURE}} {error {original options not saved}}
puts TEST_PASS
''')

    def test_no_design_is_recorded_without_fabricating_checkpoint(self):
        self.run_tcl(r'''
proc current_design {} {error {no open design}}
set code [catch {m002_route_with_failure_capture {error ORIGINAL}} result]
if {$code != 1 || $result ne {ORIGINAL} || [file exists [file join $::env(HAP_REPORT_DIR) route_failed.dcp]]} {error {no-design disposition failed}}
set h [open [file join $::env(HAP_REPORT_DIR) route_failed_capture_receipts.tsv] r];set value [read $h];close $h
if {![string match {*design_unavailable*} $value]} {error {missing unavailable receipt}}
puts TEST_PASS
''')

    def test_existing_evidence_not_overwritten_and_success_unchanged(self):
        self.run_tcl(r'''
proc current_design {} {return design}
proc route_design {args} {return [list success {*}$args]}
m002_install_route_failure_capture
if {[route_design a b] ne {success a b} || [file exists [file join $::env(HAP_REPORT_DIR) route_failed_original_error.tcllist]]} {error {success path changed}}
set path [file join $::env(HAP_REPORT_DIR) route_failed.dcp];set h [open $path w];puts -nonewline $h SENTINEL;close $h
foreach name {report_route_status report_timing_summary report_design_analysis report_drc} {proc $name {args} {set h [open [lindex $args end] w];puts $h diagnostic;close $h}}
proc write_checkpoint {path} {error {must not overwrite}}
catch {m002_route_with_failure_capture {error ORIGINAL}}
set h [open $path r];set value [read $h];close $h
if {$value ne {SENTINEL} || ![file exists [file join $::env(HAP_REPORT_DIR) route_failed_drc.rpt]]} {error {existing evidence lost or capture stopped}}
set path [file join $::env(HAP_REPORT_DIR) route_failed_capture_receipts.tsv];set h [open $path r];set before [read $h];close $h
catch {m002_route_with_failure_capture {error SECOND}}
set h [open $path r];set after [read $h];close $h
if {$before ne $after} {error {second capture overwrote receipts}}
puts TEST_PASS
''')

    def test_nonstandard_original_tcl_return_code_preserved(self):
        self.run_tcl(r'''
proc current_design {} {return {}}
set code [catch {m002_route_with_failure_capture {return -code 5 -level 0 ORIGINAL}} result]
if {$code != 5 || $result ne {ORIGINAL}} {error {original return code changed}}
puts TEST_PASS
''')

    def test_failed_diagnostic_cannot_be_a_successful_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'diagnostic_evidence.json'
            path.write_text(json.dumps(dict(schema=m.SCHEMA,stage='place',execution_state='failed',diagnostic_eligible=False)))
            with self.assertRaisesRegex(ValueError,'not a completed'):
                m.parent_place(path,Path(directory)/'project',{})


class OptimizedAuthorization(unittest.TestCase):
    def test_new_synthesis_anchor_uses_actual_new_manifest_and_rejects_later_source_change(self):
        fixture=base_tests.Lineage('test_complete')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        auth={'profile':p.OPTIMIZED_PROFILE,'contract':{'sha256':'new-contract'}}
        p.save(fixture.attempt/'execution_authorization.json',auth)
        status=json.loads((fixture.attempt/'status.json').read_text())
        status.update(execution_profile=p.OPTIMIZED_PROFILE,authorization=p.identity(fixture.attempt/'execution_authorization.json'))
        p.save(fixture.attempt/'status.json',status)
        extra=put(fixture.root/'src/new-optimized-source','new RTL')
        manifest(fixture.report/'inputs.sha256',sorted((fixture.root/'src').iterdir()))
        anchors={name:m.sha256((fixture.report if name in {'inputs.sha256','build_identity.txt','fresh_synth_complete.txt'} else fixture.attempt)/name) for name in m.SYNTH_ANCHORS}
        p.save(fixture.attempt/'frozen_synthesis_anchor.json',dict(project=str(fixture.project),report=str(fixture.report),execution_authorization=auth,source_rows=340,anchors=anchors))
        with patch.object(p,'authorization',return_value=auth):
            value=fixture.check()
            self.assertEqual(value['source_rows'],340)
            self.assertEqual(value['execution_authorization'],auth)
            extra.write_text('mutated after synthesis')
            with self.assertRaises(ValueError):fixture.check()

    def test_new_contract_and_new_stage_roots_without_legacy_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);contract=root/p.OPTIMIZED_CONTRACT;contract.parent.mkdir(parents=True);contract.write_text('E005 contract')
            with patch.object(p,'OPTIMIZED_CONTRACT_SHA',p.identity(contract)['sha256']):
                for stage,run in [('create','R002'),('synth','R003'),('place','R004'),('route','R004')]:
                    attempt=root/p.OPTIMIZED_EXPERIMENT/f'experiment_results/runs/{run}/attempts/AT001_new'
                    auth=p.authorization(root,stage,attempt,root/'report',p.OPTIMIZED_PROFILE)
                    self.assertIsNone(auth['timeout_seconds']);self.assertIsNone(auth['no_output_timeout_seconds'])
                    self.assertEqual(auth['placement_directive'],'SSI_SpreadSLLs')
                with self.assertRaisesRegex(ValueError,'stage/attempt'):
                    p.authorization(root,'place',root/p.EXPERIMENT/'experiment_results/runs/R002/attempts/AT001_old',root/'report',p.OPTIMIZED_PROFILE)


if __name__ == '__main__': unittest.main()
