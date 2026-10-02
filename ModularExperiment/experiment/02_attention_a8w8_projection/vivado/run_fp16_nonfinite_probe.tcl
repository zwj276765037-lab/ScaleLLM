set module_dir [file normalize [file join [file dirname [info script]] ..]]
set exp_dir [file normalize [file join $module_dir .. ..]]
set root [file normalize [file join $exp_dir ..]]
set m0 [file join $exp_dir experiment 00_scale_apply_microkernel]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]

file mkdir $report_dir
create_project modular_m02_fp16_nonfinite_probe $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

set ::env(HAP_SCALE_VARIANT) fp16
source [file join $m0 vivado create_fp_ip.tcl]

set sources [list \
    [file join $m0 legacy_seed rtl m3_precenter_mac_group32.sv] \
    [file join $m0 legacy_seed rtl m3_s42_fifo.sv] \
    [file join $m0 legacy_seed rtl m3_fp_scale_lanes.sv] \
    [file join $module_dir tb m02_fp16_nonfinite_probe_tb.sv]]
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m02_fp16_nonfinite_probe_tb [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
