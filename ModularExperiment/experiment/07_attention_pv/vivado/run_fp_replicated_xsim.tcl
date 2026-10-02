set module_dir [file normalize [file join [file dirname [info script]] ..]]
set variant $::env(HAP_FP_VARIANT)
set case_id [expr {$variant eq "fp16" ? 1 : 2}]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
file mkdir $report_dir
create_project modular_pv_replicated_$variant $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set ::env(HAP_OOC_VARIANT) $variant
source [file join $module_dir vivado create_fp_ip.tcl]
foreach source [list \
        [file join $module_dir rtl fp_common m9_fp_pv.sv] \
        [file join $module_dir rtl fp_common m9_fp_pv_replicated.sv] \
        [file join $module_dir tb m9_pv_replicated_tb.sv]] {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m9_pv_replicated_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id DATA_DIR=[file join $module_dir data]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
source /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/tools/scripts/power_saif_xsim.tcl
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
