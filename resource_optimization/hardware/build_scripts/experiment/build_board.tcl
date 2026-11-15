# SPDX-License-Identifier: Apache-2.0
# Fresh native build. No incremental/recovery checkpoint is consumed.
set hw $::env(HAP_HW_ROOT)
set scripts [file join $hw vivado scripts]
set local_scripts [file dirname [info script]]
set out $::env(HAP_REPORT_DIR)
set stage $::env(HAP_STAGE)
set_param general.maxThreads $::env(HAP_JOBS)
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}

source [file join $scripts release_reports.tcl]

proc report_candidate_scene {out stage} {
    report_scene $out
    report_utilization -hierarchical -file [file join $out utilization_hierarchical.rpt]
    if {$stage in {place route}} {
        report_utilization -slr -file [file join $out utilization_slr.rpt]
        if {[catch {report_design_analysis -congestion -file [file join $out congestion.rpt]} message]} {
            set f [open [file join $out congestion_command_error.txt] w]
            puts $f $message
            close $f
        }
        if {[catch {report_high_fanout_nets -file [file join $out high_fanout_nets.rpt]} message]} {
            set f [open [file join $out high_fanout_command_error.txt] w]
            puts $f $message
            close $f
        }
    }
    set dsps [lsort [get_cells -hierarchical -quiet -filter {REF_NAME == DSP48E2}]]
    set f [open [file join $out dsp_inventory.tsv] w]
    puts $f "name\tref_name\tloc\tbel\torig_ref_name"
    foreach cell $dsps {
        set fields [list [get_property NAME $cell]]
        foreach property {REF_NAME LOC BEL ORIG_REF_NAME} {
            set value ""
            catch {set value [get_property $property $cell]}
            lappend fields $value
        }
        puts $f [join $fields "\t"]
    }
    close $f
    set recovery_cells [lsort -unique [concat \
        [get_cells -hierarchical -quiet -filter {REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}] \
        [get_cells -hierarchical -quiet -filter {ORIG_REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}]]]
    set f [open [file join $out recovery_mapping.tsv] w]
    puts $f "name\tref_name\torig_ref_name\tdsp_descendants"
    set recovery_count 0
    foreach cell $recovery_cells {
        set name [get_property NAME $cell]
        if {![string match {*u_recover*} $name]} {continue}
        set ref ""
        set orig ""
        catch {set ref [get_property REF_NAME $cell]}
        catch {set orig [get_property ORIG_REF_NAME $cell]}
        set child_dsp 0
        foreach dsp $dsps {
            if {[string first "$name/" [get_property NAME $dsp]] == 0} {incr child_dsp}
        }
        puts $f "$name\t$ref\t$orig\t$child_dsp"
        incr recovery_count
    }
    close $f
    puts "RECOVERY_LEAF_QUERY_COUNT stage=$stage count=$recovery_count"
    if {[catch {get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}} bb]} {
        error "Blackbox query failed: $bb"
    }
    set f [open [file join $out blackboxes.txt] w]
    foreach cell $bb {puts $f [get_property NAME $cell]}
    close $f
    set f [open [file join $out blackboxes_identity.tsv] w]
    puts $f "name\tref_name\tis_primitive\tis_debug_core"
    set debug_cores [get_debug_cores -quiet]
    foreach cell $bb {
        set name [get_property NAME $cell]
        puts $f "$name\t[get_property REF_NAME $cell]\t[get_property IS_PRIMITIVE $cell]\t[expr {[lsearch -exact $debug_cores $name] >= 0}]"
    }
    close $f
    if {$stage eq {synth} && [llength $bb] == 1} {
        set cell [lindex $bb 0]
        set name [get_property NAME $cell]
        if {$name ne {dbg_hub} || [get_property REF_NAME $cell] ne {dbg_hub_CV} ||
            [get_property IS_PRIMITIVE $cell] || [lsearch -exact $debug_cores $name] < 0 ||
            ![string match {*labtools_xsdbm_v3_00_a*component_name=dbg_hub_CV*} [get_property DEBUG_CORE_INFO $cell]]} {
            error {Synthesis blackbox differs from the exact debug-hub placeholder}
        }
        puts {SYNTH_DEBUG_PLACEHOLDER_PASS name=dbg_hub ref=dbg_hub_CV}
    } elseif {[llength $bb]} {
        error "Unresolved blackboxes: [llength $bb]"
    }
}

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
        if {![string is integer -strict $::env(HAP_IP_JOBS)] || $::env(HAP_IP_JOBS) < 1 || $::env(HAP_IP_JOBS) > 12} {
            error {HAP_IP_JOBS must be in 1..12}
        }
        launch_runs synth_1 -jobs $::env(HAP_IP_JOBS)
        wait_on_run synth_1
        if {![string match {synth_design Complete*} [get_property STATUS [get_runs synth_1]]]} {error {Synthesis failed}}
        open_run synth_1
        write_checkpoint [file join $out synthesized.dcp]
        report_candidate_scene $out synth
    } elseif {$stage eq {place}} {
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
        set_property STEPS.OPT_DESIGN.TCL.POST [file join $local_scripts post_opt_guard.tcl] $run
        foreach step {PLACE_DESIGN PHYS_OPT_DESIGN ROUTE_DESIGN} {
            set_property STEPS.${step}.TCL.POST [file join $scripts release_save_[string tolower $step].tcl] $run
        }
        launch_runs impl_1 -to_step phys_opt_design -jobs 1
        wait_on_run impl_1
        if {![string match {phys_opt_design Complete*} [get_property STATUS $run]]} {error {Placement or physical optimization failed}}
        open_run impl_1
        write_checkpoint [file join $out placed.dcp]
        report_candidate_scene $out place
        require_design_identity
    } elseif {$stage eq {route}} {
        set run [get_runs impl_1]
        if {![string match {phys_opt_design Complete*} [get_property STATUS $run]]} {error {Successful placement/physical optimization required}}
        # Resume the same native run. The release post-step hook saves the
        # routed checkpoint before any report command can time out.
        launch_runs impl_1 -to_step route_design -jobs 1
        wait_on_run impl_1
        if {![string match {route_design Complete*} [get_property STATUS $run]]} {error {Routing failed}}
        open_run impl_1
        write_checkpoint [file join $out routed.dcp]
        report_candidate_scene $out route
        require_design_identity
        report_route_status -file [file join $out route_status_pre_gate.rpt]
        if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {
            error {Design not fully routed or routing errors remain}
        }
        if {[catch {require_timing $out} timing_error]} {
            set gate [open [file join $out timing_gate.txt] w]
            puts $gate "FAIL: $timing_error"
            close $gate
            puts "ROUTE_TIMING_GATE_FAIL $timing_error"
            error "Route timing gate failed: $timing_error"
        } else {
            set gate [open [file join $out timing_gate.txt] w]
            puts $gate {PASS}
            close $gate
        }
    } else {error {Unknown build stage}}
    close_project
}
puts "SCALELLM_RELEASE_STAGE_PASS stage=$stage"
