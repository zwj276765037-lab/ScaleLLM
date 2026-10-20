set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set synth_report_dir [file normalize $::env(HAP_SYNTH_REPORT_DIR)]
set stage $::env(HAP_STAGE)
set jobs $::env(HAP_JOBS)
if {$stage ni {place route} || ![string is integer -strict $jobs] || $jobs < 1 || $jobs > 8} {error "Invalid diagnostic stage/jobs"}
if {![string match "2025.2*" [version -short]]} {error "Expected Vivado 2025.2"}
source [file join $script_dir m002_diagnostic_common.tcl]
set_param general.maxThreads $jobs
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
config_ip_cache -disable_cache
require_disabled_ip_cache
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e" ||
    [get_property BOARD_PART [current_project]] ne "xilinx.com:vcu118:part0:2.0" ||
    [get_property NAME [current_project]] ne "scalellm_vcu118_f05" ||
    [get_property TOP [get_filesets sources_1]] ne "scalellm_vcu118_f05_bd_wrapper"} {error "Project identity changed"}
foreach name {mission0004_metadata_width_local.xdc mission0005_coordinated_partition.xdc} {
    if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] "*/$name"]]} {error "Legacy constraint active: $name"}
}
foreach name {attention_mlp_vcu118_board_v5.xdc vcu118_ddr4_explicit_pins.xdc board_clock_domains.xdc ddr_timing_recovery.xdc m003_joint_locality.xdc} {
    set path [file join $root vivado constraints $name]
    set file [get_files -quiet -of_objects [get_filesets constrs_1] $path]
    if {[llength $file] != 1} {error "Required board XDC not active: $path"}
    if {$name eq "board_clock_domains.xdc" && [get_property PROCESSING_ORDER $file] ne "LATE"} {error "Clock-domain XDC is not LATE"}
}
foreach run [get_runs -quiet -filter {NAME == synth_1 || NAME =~ *_synth_1}] {require_complete_run [get_property NAME $run]}
write_identity [file join $report_dir effective_build_identity.txt]
if {[hash_file [file join $report_dir effective_build_identity.txt]] ne [hash_file [file join $synth_report_dir build_identity.txt]]} {error "Effective synthesis identity changed"}
set h [open [file join $synth_report_dir fresh_synth_complete.txt] r]
set marker [read $h]; close $h
if {[dict get $marker project] ne $project_dir ||
    [dict get $marker inputs_sha256] ne [hash_file [file join $synth_report_dir inputs.sha256]] ||
    [dict get $marker identity_sha256] ne [hash_file [file join $synth_report_dir build_identity.txt]]} {error "Original completion lineage changed"}
source [file join $script_dir m003_joint_checks.tcl]
m003::require_project
set run [get_runs impl_1]
if {$stage eq "place"} {
    reset_run impl_1
    set_property STRATEGY {Vivado Implementation Defaults} $run
    if {([info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation") || [info exists ::env(HAP_M003_ACTIVE)]} {
        set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE SSI_SpreadSLLs $run
        set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE Default $run
        set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE Default $run
    }
    set_property AUTO_INCREMENTAL_CHECKPOINT 0 $run
    set_property INCREMENTAL_CHECKPOINT {} $run
    set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED 1 $run
    foreach {step name} {INIT_DESIGN init OPT_DESIGN opt PLACE_DESIGN place PHYS_OPT_DESIGN physopt ROUTE_DESIGN route} {
        set pre [get_property -quiet STEPS.$step.TCL.PRE $run]
        set post [get_property -quiet STEPS.$step.TCL.POST $run]
        set expected_pre [file join $script_dir m002_impl_threads.tcl]
        set expected_post [file join $script_dir m002_diagnostic_${name}_post.tcl]
        if {($pre ne "" && $pre ne $expected_pre) || ($post ne "" && $post ne $expected_post)} {
            error "Unexpected foreign implementation hook: $step"
        }
        if {$pre ne "" || $post ne ""} {
            # Existing hooks alone are not provenance. Require the preceding
            # managed M002 attempt archive to identify these exact paths.
            exec python3 [file join $script_dir m002_physical_evidence.py] prior-hooks $step $project_dir
        }
        set_property STEPS.$step.TCL.PRE [file join $script_dir m002_impl_threads.tcl] $run
        set_property STEPS.$step.TCL.POST [file join $script_dir m002_diagnostic_${name}_post.tcl] $run
    }
    exec python3 [file join $script_dir m002_physical_evidence.py] claim-hooks place $report_dir
}
set h [open [file join $report_dir implementation_settings.txt] w]
foreach property [lsort [list_property $run]] {
    puts $h "$property=[m002_prop $run $property]"
}
close $h
if {$stage eq "route"} {
    set h [open [file join $::env(HAP_PLACE_REPORT_DIR) implementation_settings.txt] r]
    foreach line [split [read $h] \n] {
        if {![regexp {^([^=]+)=(.*)$} $line -> key value]} {continue}
        if {[string match STEPS.* $key] || $key in {FLOW STRATEGY PART SRCSET CONSTRSET INCREMENTAL_CHECKPOINT AUTO_INCREMENTAL_CHECKPOINT}} {
            if {[m002_prop $run $key] ne $value} {error "Implementation setting changed since physopt: $key"}
        }
    }
    close $h
}
# Candidate registry before launch is also required for route continuation.
m002_dump_xdc project
exec python3 [file join $script_dir m002_physical_evidence.py] constraints project $report_dir
if {$stage eq "route"} {
    set stale [string tolower [get_property NEEDS_REFRESH $run]]
    set status [get_property STATUS $run]
    set directory [get_property DIRECTORY $run]
    if {$stale ni {0 false} || ![string match "*Complete*" $status] ||
        ![file isfile [file join $directory .phys_opt_design.end.rst]] ||
        [file exists [file join $directory .phys_opt_design.error.rst]] ||
        [file exists [file join $directory .vivado.error.rst]]} {error "Native parent phys_opt run is not complete/nonstale: $status"}
}
set launched_at [clock seconds]
set step [expr {$stage eq "place" ? "phys_opt_design" : "route_design"}]
launch_runs impl_1 -to_step $step -jobs 1
wait_on_run impl_1
set name [expr {$stage eq "place" ? "physopt" : "routed"}]
set run_checkpoint [require_completed_impl_step $step scalellm_vcu118_f05_bd_wrapper_${name}.dcp $launched_at]
set directory [get_property DIRECTORY [get_runs impl_1]]
file copy [file join $directory runme.log] [file join $report_dir implementation_run.log]
foreach file [glob -nocomplain -directory $directory *.tcl] {
    file copy $file [file join $report_dir [file tail $file]]
}
m002_put [file join $report_dir implementation_checkpoint.sha256] "[hash_file $run_checkpoint]  $run_checkpoint"
close_project
puts "M002_DIAGNOSTIC_CONTROLLER_COMPLETED $stage; no bitstream requested"
