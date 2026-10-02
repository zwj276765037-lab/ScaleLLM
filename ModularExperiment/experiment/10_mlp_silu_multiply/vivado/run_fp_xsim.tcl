set module_dir [file normalize [file join [file dirname [info script]] ..]]
set variant $::env(HAP_FP_VARIANT)
set case_id [expr {$variant eq "fp16" ? 1 : 2}]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
file mkdir $report_dir
create_project modular_m10_silu_$variant $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set ::env(HAP_OOC_VARIANT) $variant
source [file join $module_dir vivado create_fp_ip.tcl]
foreach source [list \
        [file join $module_dir rtl fp_common m10_fp_silu_mul.sv] \
        [file join $module_dir tb m10_fp_silu_mul_tb.sv]] {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m10_fp_silu_mul_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id DATA_DIR=[file join $module_dir data]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
