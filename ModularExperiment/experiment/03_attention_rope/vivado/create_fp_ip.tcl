proc make_fp_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

set variant $::env(HAP_OOC_VARIANT)
if {$variant eq "fp16"} {
    make_fp_ip m5_fp16_mul Multiply [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m5_fp16_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m5_fp16_sub Add_Subtract [list CONFIG.Add_Sub_Value {Subtract} \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m5_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
} elseif {$variant eq "fp32"} {
    make_fp_ip m5_fp32_mul Multiply [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m5_fp32_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m5_fp32_sub Add_Subtract [list CONFIG.Add_Sub_Value {Subtract} \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
} else {
    error "RoPE FP IP variant must be fp16 or fp32, got $variant"
}
make_fp_ip m5_fp32_to_s24 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {16}]
