set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set exp_dir [file normalize [file join $module_dir .. ..]]
set root [file normalize [file join $exp_dir ..]]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set backpressure $::env(HAP_BACKPRESSURE)
set data_dir [file normalize $::env(HAP_DATA_DIR)]

if {$variant eq "sc"} {
    set case_id 0
} elseif {$variant eq "fp16"} {
    set case_id 1
} elseif {$variant eq "fp32"} {
    set case_id 2
} else {
    error "unsupported M4 variant: $variant"
}

file mkdir $report_dir
create_project modular_kv_${variant}_bp${backpressure} $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
if {$variant ne "sc"} {
    source [file join $vivado_dir create_fp_ip.tcl]
}

set sources [list]
if {$variant eq "sc"} {
    lappend sources [file join $root rtl attention hap_unsigned_div_seq.sv]
    lappend sources [file join $root rtl attention hap_kv12_quantizer.sv]
    lappend sources [file join $root rtl attention hap_kv12_quantizer4.sv]
    lappend sources [file join $root rtl attention hap_kv12_cache.sv]
} else {
    lappend sources [file join $module_dir rtl m4_fp_kv_producer.sv]
    lappend sources [file join $module_dir rtl m4_fp_kv_cache.sv]
}
lappend sources [file join $module_dir rtl m4_kv_boundary_top.sv]
lappend sources [file join $module_dir tb m4_kv_boundary_tb.sv]
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m4_kv_boundary_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
source /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/tools/scripts/power_saif_xsim.tcl
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
