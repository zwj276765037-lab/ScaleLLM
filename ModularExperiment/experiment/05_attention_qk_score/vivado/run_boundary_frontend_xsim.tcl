set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]

if {$variant eq "fp16"} {
    set case_id 1
} elseif {$variant eq "fp32"} {
    set case_id 2
} else {
    error "unsupported M05 boundary frontend variant: $variant"
}

file mkdir $report_dir
create_project modular_m05_boundary_frontend_${variant} $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
source [file join $vivado_dir create_boundary_fp_ip.tcl]

set list_file [file join $vivado_dir boundary_frontend.sources]
set fp [open $list_file r]
set source_text [read $fp]
close $fp
foreach source [split $source_text "\n"] {
    if {[string trim $source] ne ""} {
        add_files -fileset sources_1 -norecurse [string trim $source]
        set_property file_type SystemVerilog [get_files [string trim $source]]
    }
}
set tb [file join $module_dir tb m05_boundary_frontend_tb.sv]
add_files -fileset sources_1 -norecurse $tb
set_property file_type SystemVerilog [get_files $tb]
set_property top m05_boundary_frontend_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id DATA_DIR=[file join $module_dir data_boundary]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
