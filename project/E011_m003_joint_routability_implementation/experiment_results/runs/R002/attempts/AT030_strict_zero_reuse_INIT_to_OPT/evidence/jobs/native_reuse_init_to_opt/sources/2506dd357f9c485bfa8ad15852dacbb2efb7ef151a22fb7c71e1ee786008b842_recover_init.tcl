# Explicit recovery of AT028's actual INIT DCP. No relink, no reapply, no placement.
set adapter_dir [file dirname [file normalize [info script]]]
set script_dir [file normalize $::env(HAP_M003_SCRIPTS_DIR)]
set project_dir $::env(HAP_PROJECT_DIR)
set report_dir $::env(HAP_REPORT_DIR)
source [file join $script_dir m002_diagnostic_common.tcl]
source [file join $script_dir m003_joint_checks.tcl]
set_param general.maxThreads 8
if {![string match "2025.2*" [version -short]]} {error "M003 INIT recovery tool changed"}
m003_python [file join $adapter_dir native_init_recovery.py] verify --package $::env(HAP_M003_INIT_RECOVERY_PACKAGE)
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
config_ip_cache -disable_cache
require_disabled_ip_cache
# This is still the original strict persistent-project guard, before restore.
m003::require_project
write_identity [file join $report_dir effective_build_identity.txt]
if {[hash_file [file join $report_dir effective_build_identity.txt]] ne [hash_file [file join $::env(HAP_SYNTH_REPORT_DIR) build_identity.txt]]} {error "Original source-project identity changed"}
m003::require_synthesis_runs
m002_dump_xdc project
m003_python [file join $adapter_dir native_init_recovery.py] constraints project $report_dir
set row [dict create]
set selected [get_files -quiet -of_objects [get_filesets constrs_1] [file join $script_dir ../constraints/m003_joint_locality.xdc]]
foreach key {NAME FILE_TYPE USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED PROCESSING_ORDER SCOPED_TO_REF SCOPED_TO_CELLS} {dict set row $key [m003::prop $selected $key]}
m002_put [file join $report_dir source_project_overlay_before_restore.json] [m003::jobject $row]
set ::m003_restore_registry_verified 1
set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1
set before $::m003::apply_attempts
close_project
open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)
set after $::m003::apply_attempts
if {$before != 0 || $after != 0} {error "Restored INIT checkpoint attempted overlay reapplication"}
m002_put [file join $report_dir restore_apply_attempts.json] [m003::jobject [dict create before $before after $after delta 0]]
set_property IP_CACHE_PERMISSIONS disable [current_project]
require_disabled_ip_cache
set ::m003_restored 1
# Preserve actual available native properties; do not copy XPR flags over them.
set h [open [file join $report_dir actual_restored_overlay_file_properties.tsv] w]
puts $h "NAME\tFILE_TYPE\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tPROCESSING_ORDER\tSCOPED_TO_REF\tSCOPED_TO_CELLS"
foreach object [get_files -all -quiet] {
    if {[file tail [get_property NAME $object]] eq "m003_joint_locality.xdc"} {
        set values {}
        foreach key {NAME FILE_TYPE USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED PROCESSING_ORDER SCOPED_TO_REF SCOPED_TO_CELLS} {lappend values [m003::prop $object $key]}
        puts $h [join $values \t]
    }
}
close $h
m002_put [file join $report_dir restored_design_SRC_FILE_INFO.txt] [m003::prop [current_design] SRC_FILE_INFO]
# One exact call-site adaptation, retaining the entire frozen m002_post body.
set body [info body m002_post]
set needle {m003_python [file join $::m002_script_dir m003_physical_evidence.py] hook-batch $point $::m002_report_dir}
if {[llength [split $body \n]] < 100 || [llength [regexp -all -inline {m003_physical_evidence.py} $body]] != 1 || [string first $needle $body] < 0} {error "Frozen stage hook adapter target changed"}
set replacement [format {m003_python {%s} hook-batch $point $::m002_report_dir} [file join $adapter_dir native_init_recovery.py]]
proc m002_post {point} [string map [list $needle $replacement] $body]
m002_put [file join $report_dir stage_hook_adapter.txt] "changed_call_count=1\noriginal=m003_physical_evidence.py hook-batch\nreplacement=native_init_recovery.py hook-batch\nall_other_original_guards_retained=true"
proc m003_recovery_command {point command} {
    set started_epoch [clock seconds]
    set rc [catch {uplevel #0 $command} result options]
    m002_put [file join $::report_dir ${point}_command_result.txt] "phase=$point\ncommand=$command\nstarted_epoch=$started_epoch\nended_epoch=[clock seconds]\nnative_tcl_code=$rc"
    if {$rc} {return -options $options $result}
}
if {[info exists ::env(HAP_M003_QUALIFIED_INIT_REPORT)]} {
    # Same immutable INIT DCP and unchanged core collector: reuse its completed
    # snapshot/reports, then verify only restored effective constraints here.
    set h [open [file join $report_dir restored_effective_membership.jsonl] w]
    set r [m003::resolve]
    set members {}
    foreach key {payload buffers} {
        dict for {family values} [dict get $r $key] {dict for {index cell} $values {lappend members $cell}}
    }
    set members [concat $members [dict get $r c01]]
    foreach index {0 1} {set members [concat $members [dict get $r memory $index] [dict get $r helpers $index]]}
    foreach cell $members {
        puts $h [m003::jobject [dict create kind cell NAME [get_property NAME $cell] PBLOCKS [m003::collection_property NAME [get_pblocks -quiet -of_objects $cell]]]]
    }
    foreach pb [get_pblocks -quiet -filter {NAME =~ m003_* || NAME == m002_exact_hotspot_SLR2}] {
        set row [dict create kind pblock NAME [get_property NAME $pb]]
        foreach property {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING GRID_RANGES PARENT} {dict set row $property [m003::prop $pb $property]}
        dict set row actual_sites [get_property NAME [get_sites -quiet -of_objects $pb]]
        puts $h [m003::jobject $row]
    }
    close $h
    m003_python [file join $adapter_dir native_init_recovery.py] restore-proof init $report_dir
    puts "M003_REUSED_ACTUAL_INIT_POST_QUALIFIED original=AT029 snapshot_recollected=false current_restore_effective_membership=true"
} else {m002_post init}
m003_recovery_command opt opt_design
m002_post opt
set cores [get_debug_cores -quiet]
m002_put [file join $report_dir debug_materialization_condition.txt] "debug_core_count=[llength $cores]\ndebug_cores=$cores\ncondition=actual_get_debug_cores_nonempty"
if {[llength $cores]} {m003_recovery_command debug_materialization implement_debug_core} else {m003_recovery_command debug_materialization {set ::m002_debug_skipped no_debug_cores}}
m002_post debug_materialized
m003_python [file join $script_dir m003_stage.py] preplace --report $report_dir
close_design
close_project
puts "M003_G4_RECOVERED_INIT_PREPLACE_COMPLETED inherited_AT028_INIT=true new_opt=true independent_review_required=true no_place_started=true"
