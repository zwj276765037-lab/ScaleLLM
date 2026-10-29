# SPDX-License-Identifier: Apache-2.0
# Fresh native build. No incremental/recovery checkpoint is consumed.
set scripts [file dirname [file normalize [info script]]]
set hw $::env(HAP_HW_ROOT)
set out $::env(HAP_REPORT_DIR)
set stage $::env(HAP_STAGE)
set_param general.maxThreads $::env(HAP_JOBS)
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}

source [file join $scripts release_reports.tcl]

if {$stage eq {bitstream}} {
    set dcp $::env(HAP_SOURCE_DCP)
    if {[lindex [exec sha256sum -- $dcp] 0] ne $::env(HAP_SOURCE_DCP_SHA256)} {error {Selected routed checkpoint changed}}
    if {![file isfile $dcp]} {error {Successful fresh implementation checkpoint required}}
    open_checkpoint $dcp
    require_design_identity
    require_timing $out
    write_bitstream [file join $out ScaleLLM_Final_Decode16_80MHz.bit]
    close_design
} else {
    open_project [file join $::env(HAP_PROJECT_DIR) scalellm_final_decode16.xpr]
    if {[get_property PART [current_project]] ne {xcvu9p-flga2104-2L-e}} {error {Part mismatch}}
    if {$stage eq {elaborate}} {
        update_compile_order -fileset sources_1
        synth_design -rtl -top scalellm_final_decode16_bd_wrapper -part xcvu9p-flga2104-2L-e
        set f [open [file join $out elaboration.txt] w]
        puts $f "scope=RTL elaboration only; synthesized or implemented design not produced"
        puts $f "top=[get_property NAME [current_design]] part=[get_property PART [current_design]]"
        close $f
    } elseif {$stage eq {synth}} {
        set bd [get_files -quiet */scalellm_final_decode16_bd.bd]
        create_ip_run $bd
        foreach run [get_runs -filter {IS_SYNTHESIS == 1}] {
            set_property STEPS.SYNTH_DESIGN.TCL.PRE [file join $scripts release_thread_hook.tcl] $run
            set dir [get_property DIRECTORY $run];file mkdir [file join $dir data]
            foreach name {mlp_silu_q16.mem softmax_exp_u17.mem} {file copy -force [file join $hw data $name] [file join $dir data $name]}
        }
        launch_runs synth_1 -jobs 1
        wait_on_run synth_1
        if {![string match {synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error {Synthesis failed}}
        open_run synth_1
        write_checkpoint [file join $out synthesized.dcp]
        report_scene $out
    } elseif {$stage eq {impl}} {
        if {![string match {synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error {Fresh successful synthesis required}}
        set run [get_runs impl_1]
        set_property AUTO_INCREMENTAL_CHECKPOINT 0 $run
        set_property INCREMENTAL_CHECKPOINT {} $run
        set_property STRATEGY {Vivado Implementation Defaults} $run
        foreach step {OPT_DESIGN PLACE_DESIGN PHYS_OPT_DESIGN ROUTE_DESIGN} {
            set_property STEPS.${step}.ARGS.DIRECTIVE Default $run
        }
        set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true $run
        foreach step {POWER_OPT_DESIGN POST_PLACE_POWER_OPT_DESIGN POST_ROUTE_PHYS_OPT_DESIGN} {set_property STEPS.${step}.IS_ENABLED false $run}
        set_property STEPS.OPT_DESIGN.TCL.PRE [file join $scripts release_thread_hook.tcl] $run
        foreach step {OPT_DESIGN PLACE_DESIGN PHYS_OPT_DESIGN ROUTE_DESIGN} {
            set_property STEPS.${step}.TCL.POST [file join $scripts release_save_[string tolower $step].tcl] $run
        }
        launch_runs impl_1 -to_step route_design -jobs 1
        wait_on_run impl_1
        if {![string match {route_design Complete*} [get_property STATUS $run]]} {error {Implementation failed}}
        open_run impl_1
        write_checkpoint [file join $out routed.dcp]
        report_scene $out
        require_timing $out
    } else {error {Unknown build stage}}
    close_project
}
puts "SCALELLM_RELEASE_STAGE_PASS stage=$stage"
