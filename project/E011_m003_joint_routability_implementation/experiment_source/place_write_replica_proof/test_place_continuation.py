"""CPU-only exact original-body/suffix tests; never create native PASS artifacts."""
from pathlib import Path
import ast
import json
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCRIPTS = ROOT / 'project/hardware/vivado/scripts'
for name in ['continue_successful_place.py', 'runtime_qualify.py']:
    ast.parse((HERE / name).read_text())
common = (SCRIPTS / 'm002_diagnostic_common.tcl').read_text()
start = common.index('proc m002_post ')
post = common[start:common.index('\nproc ', start + 1)]
original = (SCRIPTS / 'm003_physical.tcl').read_text()
results = []
for scenario in ['complete_suffix', 'state_proof_rejected']:
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory)
        captured = report / 'CPU_adapted_original.tcl'
        script = '\n'.join([
            'rename uplevel real_uplevel',
            'proc uplevel {args} {',
            ' set body [lindex $args end]',
            ' if {[string first {M003_PLACE_COMMAND_INHERITED} $body]>=0 && [string first {set project_dir} $body]>=0} {',
            '  set h [open {' + str(captured) + '} w];puts -nonewline $h $body;close $h;return',
            ' }',
            ' return [real_uplevel 1 [linsert $args 0 real_uplevel]]',
            '}',
            'source {' + str(HERE / 'continue_successful_place.tcl') + '}',
            post,
            'm003_continue_install_post',
            'set ::m002_report_dir {' + str(report) + '}',
            'set ::m002_script_dir {' + str(SCRIPTS) + '}',
            'set ::env(HAP_M003_ACTIVE) 1',
            'set ::env(HAP_SYNTH_REPORT_DIR) CPU_fixture_synth',
            'set ::env(HAP_PROJECT_DIR) CPU_fixture_project',
            'set scenario ' + scenario,
        ])
        script += r'''
set calls {}
proc get_cells {args} {return {}}
proc m003_collect_actual_write_states {point report} {lappend ::calls [list actual_state_query $point]}
proc report_utilization {args} {lappend ::calls [list report_utilization {*}$args]}
proc report_design_analysis {args} {lappend ::calls [list report_design_analysis {*}$args]}
proc report_slr_crossing {args} {lappend ::calls [list report_slr_crossing {*}$args]}
proc m002_reset_snapshot {args} {lappend ::calls [list reset_snapshot {*}$args]}
proc m002_cdc_change_probe {args} {lappend ::calls [list cdc_change_probe {*}$args]}
proc m002_bram_clock_probe {args} {lappend ::calls [list bram_clock_probe {*}$args]}
proc require_board_clock_groups {} {lappend ::calls board_clock_groups}
proc require_no_drc_blockers {point} {lappend ::calls [list drc_blockers $point]}
proc m002_put {path text} {set h [open $path w];puts $h $text;close $h}
proc m003_python {args} {
 lappend ::calls [list m003_python {*}$args]
 if {[file tail [lindex $args 0]] eq "runtime_qualify.py" && $::scenario eq "state_proof_rejected"} {error "CPU fixture state qualification rejected"}
 if {[file tail [lindex $args 0]] eq "m003_physical_evidence.py"} {
  set h [open [file join $::m002_report_dir admission_place.txt] w]
  puts $h {clock_coverage COMPLETE diagnostic_eligible 1 debug_materialization_eligible 0}
  close $h
 }
}
set rc [catch {m003_complete_inherited_place_POST place} message options]
if {$::scenario eq "complete_suffix" && $rc} {puts stderr [dict get $options -errorinfo];exit 1}
if {$::scenario eq "state_proof_rejected" && !$rc} {error "Failed actual state proof was ignored"}
set h [open [file join $::m002_report_dir CPU_call_trace.txt] w]
foreach call $calls {puts $h $call}
close $h
puts "CPU_ONLY_CONTINUATION_TEST_PASS $::scenario native_executed=false"
'''
        run = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
        assert run.returncode == 0 and not run.stderr and 'CPU_ONLY_CONTINUATION_TEST_PASS' in run.stdout, (scenario, run.stderr, run.stdout)
        body = captured.read_text()
        source_root = 'set script_dir [file dirname [file normalize [info script]]]'
        actual_root = 'set script_dir ' + str(SCRIPTS)
        source_line = 'source [file join $script_dir m003_joint_checks.tcl]'
        reverse = body.replace(actual_root, source_root, 1).replace(
            source_line + '\nm003_continue_install_qualifier\nm003_continue_install_post', source_line, 1).replace(
            '    puts "M003_PLACE_COMMAND_INHERITED actual_parent_AT001_native_tcl_code=0 no_place_reexecuted=true"',
            '    m003_command place {place_design -directive SSI_SpreadSLLs}', 1).replace(
            '    m003_complete_inherited_place_POST place', '    m002_post place', 1)
        assert reverse == original, 'An original command/guard was silently changed'
        for command in ['m003_command physopt {phys_opt_design -directive Default}',
                        'm003_command route {route_design -directive Default}',
                        'm003::snapshot restore $report_dir', 'm002_post physopt', 'm002_post route']:
            assert body.count(command) == 1
        trace = (report / 'CPU_call_trace.txt').read_text()
        assert 'actual_state_query place' in trace and 'runtime_qualify.py' in trace
        if scenario == 'complete_suffix':
            for name in ['report_utilization', 'report_design_analysis', 'report_slr_crossing',
                         'prepare-probe', 'reset_snapshot place', 'cdc_change_probe place',
                         'bram_clock_probe place', 'board_clock_groups', 'drc_blockers physopt',
                         'm003_physical_evidence.py']:
                assert name in trace, (scenario, name)
            assert 'completed=1' in (report / 'place_result.txt').read_text()
        else:
            assert 'report_utilization' not in trace and not (report / 'place_result.txt').exists()
        results.append(dict(case=scenario, original_body_exact_reversible=True,
                            fresh_state_proof_precedes_full_suffix=True,
                            no_place_reexecution=True, native_executed=False))
print(json.dumps(dict(passed=True, cases=results, CPU_fixture_only=True), indent=2))
