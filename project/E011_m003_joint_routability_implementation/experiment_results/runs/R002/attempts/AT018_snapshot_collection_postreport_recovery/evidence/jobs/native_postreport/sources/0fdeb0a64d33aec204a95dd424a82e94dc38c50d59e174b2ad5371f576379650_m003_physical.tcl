# M003 fresh selected synthesis -> native init -> explicit OPT/debug gate;
# separately restored qualified preplace -> fixed place/physopt/route. No bitstream.
set script_dir [file dirname [file normalize [info script]]]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set stage $::env(HAP_STAGE)
if {$stage ni {qualify implement} || ![info exists ::env(HAP_M003_ACTIVE)]} {error "M003 selected physical stage required"}
if {![string match "2025.2*" [version -short]] || $::env(HAP_JOBS) ne "8"} {error "M003 tool/thread identity mismatch"}
source [file join $script_dir m002_diagnostic_common.tcl]
source [file join $script_dir m003_joint_checks.tcl]
set_param general.maxThreads 8
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
config_ip_cache -disable_cache
require_disabled_ip_cache
m003::require_project
foreach name {mission0004_metadata_width_local.xdc mission0005_coordinated_partition.xdc} {
    if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] "*/$name"]]} {error "Legacy constraint active: $name"}
}
write_identity [file join $report_dir effective_build_identity.txt]
if {[hash_file [file join $report_dir effective_build_identity.txt]] ne [hash_file [file join $::env(HAP_SYNTH_REPORT_DIR) build_identity.txt]]} {error "M003 original synthesis identity changed"}
m003_python [file join $script_dir m003_stage.py] lineage --project $project_dir --report $::env(HAP_SYNTH_REPORT_DIR) --attempt $::env(HAP_SYNTH_ATTEMPT_DIR)
m002_dump_xdc project
m003_python [file join $script_dir m003_physical_evidence.py] constraints project $report_dir
proc m003_command {point command} {
    set started_epoch [clock seconds]
    if {$point eq "route"} {
        source [file join $::script_dir m002_route_failure_capture.tcl]
        set rc [catch {m002_route_with_failure_capture $command} result options]
    } else {set rc [catch {uplevel #0 $command} result options]}
    m002_put [file join $::report_dir ${point}_command_result.txt] "phase=$point\ncommand=$command\nstarted_epoch=$started_epoch\nended_epoch=[clock seconds]\nnative_tcl_code=$rc"
    if {$rc} {return -options $options $result}
}
if {$stage eq "qualify"} {
    m003::require_synthesis_runs
    reset_run impl_1
    set run [get_runs impl_1]
    set_property STRATEGY {Vivado Implementation Defaults} $run
    set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE SSI_SpreadSLLs $run
    set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE Default $run
    set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE Default $run
    set_property AUTO_INCREMENTAL_CHECKPOINT 0 $run
    set_property INCREMENTAL_CHECKPOINT {} $run
    foreach step {INIT_DESIGN OPT_DESIGN PLACE_DESIGN PHYS_OPT_DESIGN ROUTE_DESIGN} {
        foreach direction {PRE POST} {
            set hook [get_property -quiet STEPS.$step.TCL.$direction $run]
            if {$hook ne "" && !($direction eq "PRE" && $hook eq [file join $script_dir m002_impl_threads.tcl])} {error "M003 new project has a foreign hook: $step/$direction"}
        }
        set_property STEPS.$step.TCL.PRE [file join $script_dir m002_impl_threads.tcl] $run
    }
    set h [open [file join $report_dir implementation_settings.txt] w]
    foreach property [lsort [list_property $run]] {puts $h "$property=[m002_prop $run $property]"};close $h
    # Native launch_runs has no init_design target in this tool. Generate the
    # current complete implementation driver, then execute only its complete
    # INIT phase. The full driver and exact prefix are preserved independently.
    launch_runs impl_1 -to_step opt_design -jobs 1 -scripts_only
    set directory [get_property DIRECTORY $run]
    set driver [file join $directory scalellm_vcu118_f05_bd_wrapper.tcl]
    close_project
    m003_python [file join $script_dir m003_stage.py] prepare-native-init --report $report_dir --driver $driver
    set prefix [file join $report_dir native_init_prefix.tcl]
    set h [open $prefix r];set text [read $h];close $h
    if {![info complete $text]} {error "M003 native INIT prefix is not complete Tcl"}
    set previous [pwd];cd $directory
    try {source $prefix} finally {cd $previous}
    if {![file exists [file join $directory .init_design.end.rst]] || [file exists [file join $directory .init_design.error.rst]] || [file exists [file join $directory .opt_design.begin.rst]]} {error "M003 native INIT boundary not established"}
    require_disabled_ip_cache
    m003::require_actual_apply
    m002_post init
    m003_command opt opt_design
    m002_post opt
    set cores [get_debug_cores -quiet]
    m002_put [file join $report_dir debug_materialization_condition.txt] "debug_core_count=[llength $cores]\ndebug_cores=$cores\ncondition=actual_get_debug_cores_nonempty"
    if {[llength $cores]} {m003_command debug_materialization implement_debug_core} else {m003_command debug_materialization {set ::m002_debug_skipped no_debug_cores}}
    m002_post debug_materialized
    m003_python [file join $script_dir m003_stage.py] preplace --report $report_dir
    close_design
    close_project
    puts "M003_G4_NATIVE_PREPLACE_COMPLETED independent_review_required=true no_place_started=true"
} else {
    # Candidate registration was checked above. Effective checkpoint constraints
    # are examined immediately after restore, without sourcing/reapplying XDC.
    set ::m003_restore_registry_verified 1
    set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1
    set apply_before $::m003::apply_attempts
    close_project
    open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)
    if {$::m003::apply_attempts != $apply_before} {error "M003 checkpoint restore attempted to reapply constraints"}
    m002_put [file join $report_dir m003_restore_apply_attempts.json] [m003::jobject [dict create before $apply_before after $::m003::apply_attempts delta 0]]
    set_property IP_CACHE_PERMISSIONS disable [current_project]
    require_disabled_ip_cache
    set ::m003_restored 1
    m003::snapshot restore $report_dir
    require_board_clock_groups
    require_no_drc_blockers physopt
    m003_command place {place_design -directive SSI_SpreadSLLs}
    m002_post place
    m003_command physopt {phys_opt_design -directive Default}
    m002_post physopt
    m003_command route {route_design -directive Default}
    m002_post route
    close_design
    puts "M003_FIXED_IMPLEMENTATION_COMPLETED physical_signoff_pending_full_review=true"
}
