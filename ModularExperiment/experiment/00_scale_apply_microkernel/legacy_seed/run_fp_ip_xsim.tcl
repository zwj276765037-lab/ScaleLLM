set experiment_dir [file dirname [file normalize [info script]]]
set case_id $::env(M3_CASE_ID)
set case_name $::env(M3_CASE_NAME)
set project_dir [file normalize [file join $experiment_dir artifacts fp_ip_xsim_project $case_name]]
file delete -force $project_dir
file mkdir $project_dir
create_project "m3_${case_name}_ip_xsim" $project_dir \
    -part xcvu9p-flga2104-2L-e -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

proc make_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    generate_target all [get_ips $name]
}
make_ip m3_int21_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} CONFIG.C_A_Exponent_Width {21} \
    CONFIG.C_A_Fraction_Width {0} CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
make_ip m3_fp32_mul Multiply [list CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Single}]
make_ip m3_fp32_to_s42 Float_to_fixed [list CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} CONFIG.C_Result_Exponent_Width {18} \
    CONFIG.C_Result_Fraction_Width {24}]
if {$case_id == 2} {
    make_ip m3_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}]
    make_ip m3_fp16_mul Multiply [list CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_ip m3_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
}

foreach source [list \
    [file join $experiment_dir rtl m3_precenter_mac_group32.sv] \
    [file join $experiment_dir rtl m3_s42_fifo.sv] \
    [file join $experiment_dir rtl m3_fp_scale_lanes.sv] \
    [file join $experiment_dir tb m3_lane_tb.sv]] {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
set_property top m3_lane_tb [get_filesets sim_1]
set_property generic "CASE_ID=$case_id DATA_DIR=[file join $experiment_dir data]" \
    [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project

