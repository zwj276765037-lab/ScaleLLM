# Continue only an identified genuine project-init or physopt checkpoint.
set script_dir [file dirname [file normalize [info script]]]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set stage $::env(HAP_STAGE)
if {$stage ni {place route} || $::env(HAP_EXECUTION_MODE) ne "checkpoint_restored_commands"} {error "Invalid recovery execution mode"}
if {![string match "2025.2*" [version -short]]} {error "Expected Vivado 2025.2"}
source [file join $script_dir m002_diagnostic_common.tcl]
set_param general.maxThreads 8
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
require_disabled_ip_cache
write_identity [file join $report_dir effective_build_identity.txt]
if {[hash_file [file join $report_dir effective_build_identity.txt]] ne [hash_file [file join $::env(HAP_SYNTH_REPORT_DIR) build_identity.txt]]} {error "Recovery original project synthesis identity changed"}
m002_dump_xdc project
exec python3 [file join $script_dir m002_physical_evidence.py] constraints project $report_dir
set run [get_runs impl_1]
set h [open [file join $report_dir implementation_settings.txt] w]
foreach property [lsort [list_property $run]] {puts $h "$property=[m002_prop $run $property]"}
close $h
# Original impl_1 remains failed. This flow never writes success receipts there.
close_project
open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)
set design [current_design]
if {[get_property PART $design] ne "xcvu9p-flga2104-2L-e" || [get_property NAME $design] ne "scalellm_vcu118_f05_bd_wrapper"} {error "Restored design part/top mismatch"}
set h [open [file join $report_dir restored_design_properties.tsv] w]
foreach property [lsort [list_property $design]] {puts $h "$property\t[m002_prop $design $property]"}
close $h
m002_put [file join $report_dir restored_checkpoint_mode.txt] "execution_mode=checkpoint_restored_commands\nconstraint_mode=embedded_checkpoint_inherited\ncheckpoint=$::env(HAP_RECOVERY_CHECKPOINT)\noriginal_impl_1_status=FAIL_not_reinterpreted"
proc m002_command {point command} {
    set start [clock seconds]
    set rc [catch {uplevel #0 $command} result options]
    m002_put [file join $::m002_report_dir ${point}_command_result.txt] "phase=$point\ncommand=$command\nstarted_epoch=$start\nended_epoch=[clock seconds]\nnative_tcl_code=$rc"
    if {$rc} {return -options $options $result}
}
if {$stage eq "place"} {
    set h [open [file join $report_dir exact_target_queries.tsv] w]
    source [file join $report_dir probe_targets.tcl]
    foreach target $::m002_cdc_targets {
        set exact [m002_exact get_pins $target]
        puts $h "TARGET\t$target\tEXACT_NAME_MATCHES=[llength $exact]\t$exact"
        if {[llength $exact] != 1 || [get_property NAME $exact] ne $target} {close $h;error "Restored CDC target not uniquely resolved by literal NAME: $target"}
    }
    close $h
    m002_post init
    m002_command opt opt_design
    m002_post opt
    m002_command place place_design
    m002_post place
    m002_command physopt phys_opt_design
    m002_post physopt
    set checkpoint [file join $report_dir physopt.dcp]
} else {
    # Explicitly restore the qualified physopt DCP of this execution mode.
    m002_command route route_design
    m002_post route
    set checkpoint [file join $report_dir route.dcp]
}
m002_put [file join $report_dir implementation_checkpoint.sha256] "[hash_file $checkpoint]  $checkpoint"
close_design
puts "M002_RECOVERED_COMMAND_CONTROLLER_COMPLETED $stage physical_signoff=false"
