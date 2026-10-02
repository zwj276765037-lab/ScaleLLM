set vivado_dir [file dirname [file normalize [info script]]]
set module_dir [file normalize [file join $vivado_dir ..]]
set exp_dir [file normalize [file join $module_dir .. ..]]
set root [file normalize [file join $exp_dir ..]]
set variant $::env(HAP_SCALE_VARIANT)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set backpressure $::env(HAP_BACKPRESSURE)

if {$variant eq "sc"} {
    set case_id 0
} elseif {$variant eq "fp16"} {
    set case_id 1
} elseif {$variant eq "fp32"} {
    set case_id 2
} else {
    error "unsupported M5 variant: $variant"
}

file mkdir $report_dir
create_project modular_qk_${variant}_bp${backpressure} $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

if {$variant ne "sc"} {
    source [file join $vivado_dir create_fp_ip.tcl]
}

set sources [list]
if {$variant eq "sc"} {
    lappend sources [file join $root rtl attention hap_q24k12_group_dot_s40.sv]
    lappend sources [file join $root rtl attention hap_score_group_scale_s35.sv]
    lappend sources [file join $root rtl attention hap_score_accum4_s20.sv]
    lappend sources [file join $root rtl attention hap_qk_score_row_128.sv]
} else {
    lappend sources [file join $module_dir legacy_seed rtl m7_fp_qk_slot_arch.sv]
    lappend sources [file join $module_dir rtl m5_fp_qk_top.sv]
}
lappend sources [file join $module_dir tb m5_qk_matched_tb.sv]
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m5_qk_matched_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=[file join $module_dir data]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
source /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/tools/scripts/power_saif_xsim.tcl
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
