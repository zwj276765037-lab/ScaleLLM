set experiment_dir [file dirname [file normalize [info script]]]
set project_dir [file normalize [file join $experiment_dir artifacts ip_probe_project]]
file delete -force $project_dir
file mkdir $project_dir
create_project m3_ip_probe $project_dir -part xcvu9p-flga2104-2L-e -force

proc make_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    puts "M3_IP_CONFIG: name=$name operation=$operation latency=[get_property CONFIG.C_Latency [get_ips $name]] a_precision=[get_property CONFIG.A_Precision_Type [get_ips $name]] result_precision=[get_property CONFIG.Result_Precision_Type [get_ips $name]]"
}

make_ip m3_int21_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {21} \
    CONFIG.C_A_Fraction_Width {0} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} \
    CONFIG.C_Result_Fraction_Width {24}]
make_ip m3_fp32_mul Multiply [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Single}]
make_ip m3_fp32_to_s42 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {18} \
    CONFIG.C_Result_Fraction_Width {24}]
make_ip m3_fp32_to_fp16 Float_to_float [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {5} \
    CONFIG.C_Result_Fraction_Width {11}]
make_ip m3_fp16_mul Multiply [list \
    CONFIG.A_Precision_Type {Half} \
    CONFIG.Result_Precision_Type {Half}]
make_ip m3_fp16_to_fp32 Float_to_float [list \
    CONFIG.A_Precision_Type {Half} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} \
    CONFIG.C_Result_Fraction_Width {24}]
close_project
