# OPT-only reuse. The full original actual debug command/POST/preplace are intact.
set qualified_opt_dir [file dirname [file normalize [info script]]]
set original_recovery_dir [file normalize [file join $qualified_opt_dir ../AT028_init_recovery]]
set h [open [file join $original_recovery_dir recover_init.tcl] r];set original_body [read $h];close $h
set old_dir {set adapter_dir [file dirname [file normalize [info script]]]}
set old_opt {    set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
    set h [open [file join $report_dir blackboxes_opt.tsv] w];m002_dump_cells $h $bb;close $h
    m002_dump_xdc opt
    m002_debug_probe opt $bb
    report_drc -file [file join $report_dir drc_opt_live.rpt]
    m003_complete_opt_post}
foreach needle [list $old_dir $old_opt] {
    set pos [string first $needle $original_body]
    if {$pos < 0 || [string first $needle $original_body [expr {$pos+1}]] >= 0} {error "Frozen qualified OPT continuation target changed"}
}
set new_opt {    m002_dump_xdc opt
    report_drc -file [file join $report_dir drc_OPT_restore_live.rpt]
    require_board_clock_groups
    require_no_drc_blockers physopt
    m003_python [file join $::qualified_opt_dir qualified_opt_evidence.py] --dependency-package $::env(HAP_QUALIFIED_OPT_DEPENDENCY_PACKAGE) --report $report_dir}
set adapted_body [string map [list $old_dir [list set adapter_dir $original_recovery_dir] $old_opt $new_opt] $original_body]
if {![info complete $adapted_body]} {error "Qualified OPT continuation Tcl incomplete"}
uplevel #0 $adapted_body
