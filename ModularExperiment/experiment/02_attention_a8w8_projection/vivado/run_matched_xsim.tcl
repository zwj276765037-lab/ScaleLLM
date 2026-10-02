set module_dir [file normalize [file join [file dirname [info script]] ..]]
set exp_dir [file normalize [file join $module_dir .. ..]]
set root [file normalize [file join $exp_dir ..]]
set m0 [file join $exp_dir experiment 00_scale_apply_microkernel]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set dataset $::env(HAP_DATASET)
set data_dir [file normalize $::env(HAP_DATA_DIR)]
set backpressure $::env(HAP_BACKPRESSURE)

if {$variant eq "sc"} {
    set case_id 1
} elseif {$variant eq "fp16"} {
    set case_id 2
} elseif {$variant eq "fp32"} {
    set case_id 3
} else {
    error "unsupported M4 variant: $variant"
}

file mkdir $report_dir
create_project modular_projection_$variant $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

if {$variant ne "sc"} {
    source [file join $m0 vivado create_fp_ip.tcl]
}

set sources [list \
    [file join $root rtl attention hap_a8w8_group32_lane_s42.sv] \
    [file join $root rtl attention hap_linear_tile_accum_s42.sv] \
    [file join $m0 legacy_seed rtl m3_precenter_mac_group32.sv] \
    [file join $m0 legacy_seed rtl m3_s42_fifo.sv] \
    [file join $m0 legacy_seed rtl m3_mac_only_lane.sv] \
    [file join $m0 legacy_seed rtl m3_fp_scale_lanes.sv] \
    [file join $module_dir legacy_seed rtl m4_matched_tile.sv]]
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
if {$dataset eq "trace"} {
    set tb [file join $module_dir tb m02_projection_trace_tb.sv]
    add_files -fileset sources_1 -norecurse $tb
    set_property file_type SystemVerilog [get_files $tb]
    set_property top m02_projection_trace_tb [get_filesets sim_1]
    set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure TILES=18 DATA_DIR=$data_dir" \
        [get_filesets sim_1]
} elseif {$dataset eq "synthetic"} {
    set tb [file join $module_dir legacy_seed tb m4_tile_tb.sv]
    add_files -fileset sources_1 -norecurse $tb
    set_property file_type SystemVerilog [get_files $tb]
    set_property top m4_tile_tb [get_filesets sim_1]
    set sim_generics "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir"
    if {[info exists ::env(HAP_SAIF_RAW_PATH)]} {
        append sim_generics " CLOCK_PERIOD_PS=10000 USE_OOC_WRAPPER=1"
    }
    set_property generic $sim_generics [get_filesets sim_1]
} else {
    error "unsupported M02 dataset: $dataset"
}
update_compile_order -fileset sources_1
source /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/tools/scripts/power_saif_xsim.tcl
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
