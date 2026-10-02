set root /home/user/EDA-202/zhuowenjun/ScaleLLM
set module_dir [file join $root ModularExperiment experiment 06_attention_softmax]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
file mkdir $report_dir
create_project modular_softmax_sc_power $build_dir \
    -part xcvu9p-flga2104-2L-e -force
# hap_softmax_exp_u17 intentionally uses the repository-relative ROM path
# data/softmax_exp_u17.mem.  Project-mode XSim changes its working directory,
# so stage that immutable ROM at the same relative path before elaboration.
set sim_data_dir [file join $build_dir modular_softmax_sc_power.sim \
    sim_1 behav xsim data]
file mkdir $sim_data_dir
file copy -force [file join $root data softmax_exp_u17.mem] \
    [file join $sim_data_dir softmax_exp_u17.mem]
foreach source [list \
        [file join $root rtl attention hap_fixbit_v2_pkg.sv] \
        [file join $root rtl attention hap_unsigned_div_seq.sv] \
        [file join $root rtl attention hap_softmax_exp_u17.sv] \
        [file join $root rtl attention hap_softmax_recip_u17.sv] \
        [file join $root rtl attention hap_softmax_prob_u16.sv] \
        [file join $root rtl attention hap_softmax_row_128.sv] \
        [file join $module_dir tb hap_softmax_row_128_long_tb.sv]] {
    add_files -fileset sources_1 -norecurse $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top hap_softmax_row_128_long_tb [get_filesets sim_1]
set_property generic "DATA_DIR=[file join $root data softmax_row_128]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
source [file join $root ModularExperiment tools scripts power_saif_xsim.tcl]
hap_power_saif_prepare sim_1
launch_simulation -simset sim_1 -mode behavioral
hap_power_saif_run
close_sim
close_project
