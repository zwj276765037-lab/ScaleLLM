set module_dir [file normalize [file join [file dirname [info script]] ..]]
set variant $::env(HAP_VARIANT)
set backpressure $::env(HAP_BACKPRESSURE)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set data_dir [file normalize $::env(HAP_DATA_DIR)]
set expected_saturations $::env(HAP_EXPECTED_SATURATIONS)
if {$variant eq "sc"} {
    set case_id 0
    set list_file [file join $module_dir vivado boundary_sc.sources]
} elseif {$variant eq "fp16"} {
    set case_id 1
    set list_file [file join $module_dir vivado boundary_fp.sources]
} elseif {$variant eq "fp32"} {
    set case_id 2
    set list_file [file join $module_dir vivado boundary_fp.sources]
} else {
    error "M07 boundary variant must be sc, fp16, or fp32"
}

file mkdir $report_dir
create_project modular_m07_pv_boundary_$variant $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
if {$variant ne "sc"} {
    set ::env(HAP_OOC_VARIANT) $variant
    source [file join $module_dir vivado create_boundary_all_fp_ip.tcl]
}

set fp [open $list_file r]
set source_text [read $fp]
close $fp
foreach source [split $source_text "\n"] {
    set source [string trim $source]
    if {$source eq "" || [string index $source 0] eq "#"} {
        continue
    }
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
set tb [file join $module_dir tb m07_pv_boundary_tb.sv]
add_files -fileset sim_1 $tb
set_property file_type SystemVerilog [get_files $tb]
set_property top m07_pv_boundary_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir EXPECTED_SATURATIONS=$expected_saturations" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
