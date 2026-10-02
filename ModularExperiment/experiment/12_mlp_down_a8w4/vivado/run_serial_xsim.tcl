set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set backpressure $::env(HAP_BACKPRESSURE)
set data_dir [file normalize $::env(HAP_DATA_DIR)]
set wave_mode $::env(HAP_WAVE_MODE)

if {$variant eq "sc"} {
    set case_id 0
    set list_file [file join $vivado_dir sc_ooc.sources]
} elseif {$variant eq "fp16"} {
    set case_id 1
    set list_file [file join $vivado_dir fp_ooc.sources]
} elseif {$variant eq "fp32"} {
    set case_id 2
    set list_file [file join $vivado_dir fp_ooc.sources]
} else {
    error "unsupported M12 serial variant: $variant"
}

file mkdir $report_dir
create_project modular_m12_serial_${variant}_bp${backpressure} $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
if {$wave_mode eq "nowave"} {
    set_property xsim.elaborate.debug_level off [get_filesets sim_1]
    set_property xsim.simulate.log_all_signals false [get_filesets sim_1]
    set_property xsim.simulate.custom_tcl \
        [file join $vivado_dir run_1000ns_no_wave.tcl] [get_filesets sim_1]
} elseif {$wave_mode ne "wave"} {
    error "unsupported M12 serial wave mode: $wave_mode"
}
if {$variant ne "sc"} {
    source [file join $vivado_dir create_fp_ip.tcl]
}

set fp [open $list_file r]
set source_text [read $fp]
close $fp
foreach source [split $source_text "\n"] {
    if {[string trim $source] ne ""} {
        add_files -fileset sources_1 -norecurse [string trim $source]
        set_property file_type SystemVerilog [get_files [string trim $source]]
    }
}
set tb [file join $module_dir tb m12_down_serial_ooc_wrapper_tb.sv]
add_files -fileset sources_1 -norecurse $tb
set_property file_type SystemVerilog [get_files $tb]
set_property top m12_down_serial_ooc_wrapper_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
