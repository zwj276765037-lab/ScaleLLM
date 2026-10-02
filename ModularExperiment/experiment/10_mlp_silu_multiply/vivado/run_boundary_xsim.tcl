set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set variant $::env(HAP_FP_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set backpressure $::env(HAP_BACKPRESSURE)
set data_dir [file normalize $::env(HAP_DATA_DIR)]

if {$variant eq "sc"} {
    set case_id 0
    set list_file [file join $vivado_dir boundary_sc.sources]
} elseif {$variant eq "fp16"} {
    set case_id 1
    set list_file [file join $vivado_dir boundary_fp.sources]
} elseif {$variant eq "fp32"} {
    set case_id 2
    set list_file [file join $vivado_dir boundary_fp.sources]
} else {
    error "unsupported M10 boundary variant: $variant"
}

file mkdir $report_dir
create_project modular_m10_boundary_${variant}_bp${backpressure} $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
if {$variant ne "sc"} {
    set ::env(HAP_OOC_VARIANT) $variant
    source [file join $vivado_dir create_boundary_all_fp_ip.tcl]
}
set fp [open $list_file r]
set source_text [read $fp]
close $fp
foreach source [split $source_text "\n"] {
    set source [string trim $source]
    if {$source ne ""} {
        add_files -fileset sources_1 -norecurse $source
        if {[file extension $source] eq ".sv"} {
            set_property file_type SystemVerilog [get_files $source]
        }
    }
}
set tb [file join $module_dir tb m10_silu_boundary_tb.sv]
add_files -fileset sources_1 -norecurse $tb
set_property file_type SystemVerilog [get_files $tb]
set_property top m10_silu_boundary_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
