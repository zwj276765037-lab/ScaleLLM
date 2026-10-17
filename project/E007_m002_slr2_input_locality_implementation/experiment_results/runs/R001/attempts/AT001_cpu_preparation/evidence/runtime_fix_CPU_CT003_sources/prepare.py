#!/usr/bin/env python3
"""Prepare agent-owned E007 entry; CPU/filesystem only, never launches EDA."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SCRIPTS=ROOT/'project/hardware/vivado/scripts'


def identity(path):
    return dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def replace_once(text, old, new):
    assert text.count(old)==1, f'Upstream adapter anchor changed: {old[:80]}'
    return text.replace(old,new,1)


def controller():
    text=(SCRIPTS/'m002_resume_physical.tcl').read_text()
    text=replace_once(text,'set script_dir [file dirname [file normalize [info script]]]',
        'set script_dir [file normalize $::env(SLR2_REUSED_SCRIPT_DIR)]')
    text=replace_once(text,'source [file join $script_dir m002_diagnostic_common.tcl]',
        'source [file join $script_dir m002_diagnostic_common.tcl]\nsource $::env(SLR2_HOOKS)')
    text=text.replace('exec python3 [file join $script_dir m002_physical_evidence.py]',
                      'exec python3 $::env(SLR2_ADAPTER)')
    anchor='if {$stage eq "place"} {\n    set restore_placed'
    policy='''# Direct commands do not load/read an incremental checkpoint.
set runtime_runs [get_runs -quiet impl_1]
if {[llength $runtime_runs]} {
    set_property AUTO_INCREMENTAL_CHECKPOINT 0 $runtime_runs
    set_property INCREMENTAL_CHECKPOINT {} $runtime_runs
}
set h [open [file join $report_dir candidate_runtime_policy.tsv] {WRONLY CREAT EXCL}]
puts $h "actual_project\\t[current_project]\\nthreads\\t[get_param general.maxThreads]\\nip_cache\\t[require_disabled_ip_cache]\\nexecution\\tdirect_commands_no_incremental_checkpoint_read\\nplace_directive\\tSSI_SpreadSLLs\\nphysopt_directive\\tDefault\\nroute_directive\\tDefault"
foreach run $runtime_runs {puts $h "runtime_run\\t$run\\tauto_incremental=[m002_prop $run AUTO_INCREMENTAL_CHECKPOINT]\\tincremental_checkpoint=[m002_prop $run INCREMENTAL_CHECKPOINT]"}
close $h
slr2::topology
slr2::resolve pre_place
slr2::constrain
slr2::cut pre_place
'''
    text=replace_once(text,anchor,policy+anchor)
    text=replace_once(text,'    m002_post place\n    if {$optimized}',
        '    slr2::post_phase place\n    if {$optimized}')
    text=replace_once(text,'    m002_post physopt\n    set checkpoint [file join $report_dir physopt.dcp]',
        '''    slr2::post_phase physopt
    set route_code [catch {m002_command route {route_design -directive Default}} route_result route_options]
    if {$route_code} {
        # Original failure is already captured by the unchanged route wrapper.
        set capture_code [catch {slr2::phase route_failed} capture_result capture_options]
        m002_put [file join $report_dir candidate_failed_route_capture.txt] [list code $capture_code result $capture_result options $capture_options]
        return -options $route_options $route_result
    }
    slr2::post_phase route
    set checkpoint [file join $report_dir route.dcp]''')
    text=replace_once(text,'puts "M002_RECOVERED_COMMAND_CONTROLLER_COMPLETED $stage physical_signoff=false"',
        'puts "M002_SLR2_FULL_IMPLEMENTATION_CONTROLLER_COMPLETED physical_signoff=false"')
    return '# Generated from frozen production controller by agent-owned prepare.py.\n'+text


def main():
    target=HERE/'implementation.tcl'
    target.write_text(controller())
    python_sources=list(HERE.glob('*.py'))
    for path in python_sources:ast.parse(path.read_text(),filename=str(path))
    tcls=sorted(HERE.glob('*.tcl'))
    for path in tcls:
        result=subprocess.run(['tclsh'],input='set h [open {'+str(path)+'} r]\nset body [read $h]\nclose $h\nputs [info complete $body]\n',
                              text=True,capture_output=True,check=True)
        assert result.stdout.strip()=='1',path
    # Bind every reused production Python module: dynamic imports remain truthful.
    reused=sorted(set(SCRIPTS.glob('*.py'))|{SCRIPTS/name for name in (
        'm002_resume_physical.tcl','m002_diagnostic_common.tcl','m002_optimized_structure.tcl',
        'm002_route_failure_capture.tcl')}|{HERE.parent/'E006_lean_candidate/run_attribution_lean.py'})
    own=sorted(set(python_sources+tcls))
    manifest=dict(status='CPU_PREPARED_NOT_EXECUTED',EDA_executed=False,
        own_sources=[identity(p) for p in own],reused_sources=[identity(p) for p in reused],
        contract=identity(ROOT/'mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md'),
        selector_reference=identity(ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/audit_input_frontend_candidate.py'),
        architecture_boundary_plan=identity(ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/input_frontend_locality_execution_boundary_plan.json'),
        CPU_checks=[identity(HERE/name) for name in ('bounded_CPU_validation.json',
            'selector_before_S_terminology_revision.json','bounded_CPU_validation_current.json',
            'parent_CPU_validation.json','runtime_fix_CPU_validation.json') if (HERE/name).exists()],
        documentation=[identity(HERE/'README.md')],
        validation=dict(Python_AST='PASS',Tcl_info_complete='PASS',native_APIs='NOT_RUN',
                        actual_pre_place_membership='NOT_RUN',geometry_readback='NOT_RUN',complete_cut='NOT_RUN'),
        current_EDA_unchanged=True,
        launch_dependencies=['E006 actual terminal, complete attribution and independently supported candidate scope',
          'All registered prior process PID/start identities closed and single EDA lock released',
          'A new E007 R002 attempt/report with this prepared source manifest unchanged',
          'Actual source/pre-place/synthesis/144 input/175 constraint identities revalidated',
          'Native pre-place selector/banks/DSP/ranges/fixed constraints/complete cut/live qualification must pass before place'])
    (HERE/'prepared_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(manifest=identity(HERE/'prepared_manifest.json'),own_sources=len(own),
                         reused_sources=len(reused),native_executed=False)))


if __name__=='__main__':main()
