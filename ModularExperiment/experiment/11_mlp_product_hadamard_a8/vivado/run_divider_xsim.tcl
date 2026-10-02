set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]

file mkdir $report_dir
create_project modular_m11_divider $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set divider [file join $module_dir rtl m11_u44_div_u36_radix16.sv]
set tb [file join $module_dir tb m11_div_tb.sv]
add_files -fileset sources_1 -norecurse $divider $tb
set_property file_type SystemVerilog [get_files $divider]
set_property file_type SystemVerilog [get_files $tb]
set_property top m11_div_tb [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
