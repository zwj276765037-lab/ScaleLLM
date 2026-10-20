# Same-version native synthesis is already preserved in AT003. This distinct
# attempt repairs and actually reruns selected post-report qualification only.
set script_dir [file dirname [file normalize [info script]]]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
source [file join $script_dir m002_diagnostic_common.tcl]
source [file join $script_dir m003_joint_checks.tcl]
set_param general.maxThreads 8
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
config_ip_cache -disable_cache
require_disabled_ip_cache
set overlay [file normalize [file join $script_dir ../constraints/m003_joint_locality.xdc]]
set file [get_files -quiet -of_objects [get_filesets constrs_1] $overlay]
m003::exact_count $file 1 "original formal overlay"
proc m003_recovery_overlay_metadata {file} {
    set row [dict create]
    foreach property {FILE_TYPE USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED PROCESSING_ORDER SCOPED_TO_REF SCOPED_TO_CELLS} {dict set row $property [m003::prop $file $property]}
    set synth [get_runs synth_1]
    foreach property {STATUS PROGRESS NEEDS_REFRESH} {dict set row SYNTH.$property [m003::prop $synth $property]}
    return [m003::jobject $row]
}
m002_put [file join $report_dir overlay_metadata_before_type.json] [m003_recovery_overlay_metadata $file]
set_property FILE_TYPE TCL $file
m002_put [file join $report_dir overlay_metadata_after_type.json] [m003_recovery_overlay_metadata $file]
# Vivado resets USED_IN when converting an existing registered file's type.
# Reassert the already-frozen implementation-only policy before strict checks.
set_property USED_IN_SYNTHESIS false $file
set_property USED_IN_IMPLEMENTATION true $file
set_property PROCESSING_ORDER LATE $file
m002_put [file join $report_dir overlay_metadata_after_policy.json] [m003_recovery_overlay_metadata $file]
m003::require_project
write_identity [file join $report_dir build_identity.txt]
m003_python [file join $script_dir m003_synth_recovery.py] compare-identity --report $report_dir
foreach run [get_runs -quiet -filter {NAME == synth_1 || NAME =~ *_synth_1}] {require_complete_run [get_property NAME $run]}
open_run synth_1
require_board_clock_groups
source $overlay
m003::require_actual_apply
m003::snapshot synth $report_dir
m003_python [file join $script_dir m003_resource_budget.py] --report-dir $report_dir --output [file join $report_dir m003_same_stage_budget.json]
report_control_sets -verbose -file [file join $report_dir m003_control_sets_synth.rpt]
m003_python [file join $script_dir m003_synth_recovery.py] native-finish --project $project_dir --report $report_dir
close_design
close_project
puts "M003_POSTREPORT_QUALIFICATION_COMPLETED new_synthesis_launched=false original_AT003_exit=1"
