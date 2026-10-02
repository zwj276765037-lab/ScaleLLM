set root /home/user/EDA-202/zhuowenjun/ScaleLLM
set module_dir [file join $root ModularExperiment experiment 07_attention_pv]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
file mkdir $report_dir
create_project modular_pv_sc_power $build_dir \
    -part xcvu9p-flga2104-2L-e -force
foreach source [list \
        [file join $root rtl attention hap_pv_tile16_s43.sv] \
        [file join $module_dir tb hap_pv_tile16_s43_tb.sv]] {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top hap_pv_tile16_s43_tb [get_filesets sim_1]
set_property generic "DATA_DIR=[file join $module_dir data sc_source]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
source [file join $root ModularExperiment tools scripts power_saif_xsim.tcl]
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
