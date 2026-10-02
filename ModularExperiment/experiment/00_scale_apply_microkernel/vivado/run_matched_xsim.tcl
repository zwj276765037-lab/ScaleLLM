set module_dir [file normalize [file join [file dirname [info script]] ..]]
set legacy_dir [file join $module_dir legacy_seed]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]

if {$variant eq "sc"} {
    set case_id 1
} elseif {$variant eq "fp16"} {
    set case_id 2
} elseif {$variant eq "fp32"} {
    set case_id 3
} else {
    error "unsupported M3 variant: $variant"
}

file mkdir $report_dir
create_project modular_scale_apply_$variant $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

if {$variant eq "sc"} {
    set sources [list \
        [file join $module_dir .. .. .. rtl attention \
            hap_a8w8_group32_lane_s42.sv] \
        [file join $legacy_dir tb m3_lane_tb.sv]]
} else {
    source [file join $module_dir vivado create_fp_ip.tcl]
    set sources [list \
        [file join $legacy_dir rtl m3_precenter_mac_group32.sv] \
        [file join $legacy_dir rtl m3_s42_fifo.sv] \
        [file join $legacy_dir rtl m3_fp_scale_lanes.sv] \
        [file join $legacy_dir tb m3_lane_tb.sv]]
}
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
if {[info exists ::env(HAP_SAIF_PATH)]} {
    if {$variant eq "sc"} {
        set sim_top m3_power_sc_tb
    } elseif {$variant eq "fp16"} {
        set sim_top m3_power_fp16_tb
    } else {
        set sim_top m3_power_fp32_tb
    }
    set_property top $sim_top [get_filesets sim_1]
} else {
    set_property top m3_lane_tb [get_filesets sim_1]
    set sim_generics "CASE_ID=$case_id DATA_DIR=[file join $legacy_dir data]"
    if {[info exists ::env(HAP_CLOCK_PERIOD_PS)]} {
        append sim_generics " CLOCK_PERIOD_PS=$::env(HAP_CLOCK_PERIOD_PS)"
    }
    set_property generic $sim_generics [get_filesets sim_1]
}
update_compile_order -fileset sources_1
if {[info exists ::env(HAP_SAIF_PATH)]} {
    # launch_simulation otherwise advances XSim by its 1000 ns GUI default
    # before returning control to this script.
    set_property xsim.simulate.runtime 0ns [get_filesets sim_1]
}
launch_simulation -simset sim_1 -mode behavioral
if {[info exists ::env(HAP_SAIF_PATH)]} {
    # Exclude reset from activity statistics.  The testbench releases reset
    # on the eighth rising edge, so one complete extra cycle is included as a
    # guard before the continuous-workload capture starts.
    set clock_period_ps 6667
    if {[info exists ::env(HAP_CLOCK_PERIOD_PS)]} {
        set clock_period_ps $::env(HAP_CLOCK_PERIOD_PS)
    }
    set warmup_ns [expr {9.0 * $clock_period_ps / 1000.0}]
    run ${warmup_ns}ns

    # Parameterized generate branches acquire simulator-specific genblk names;
    # discover the unique top-level instance named "dut" instead of hardcoding
    # those generated scope names.
    set dut_scopes [list]
    foreach candidate [get_scopes -quiet -r *] {
        if {[regexp {([/.])dut$} [get_property NAME $candidate]]} {
            lappend dut_scopes $candidate
        }
    }
    if {[llength $dut_scopes] != 1} {
        error "expected one simulation DUT scope, found [llength $dut_scopes]: $dut_scopes"
    }
    set dut_path [lindex $dut_scopes 0]
    puts "POWER_SAIF_DUT_SCOPE: $dut_path"
    set dut_objects [get_objects -quiet -r ${dut_path}/*]
    if {[llength $dut_objects] == 0} {
        error "no simulation objects found below $dut_path"
    }
    open_saif $::env(HAP_SAIF_PATH)
    log_saif $dut_objects
    run all
    close_saif
} else {
    run all
}
close_sim
close_project
