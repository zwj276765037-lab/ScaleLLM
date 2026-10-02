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
    make_fp_ip m8_f16_sub Add_Subtract [list CONFIG.Add_Sub_Value {Subtract} \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m8_f16_exp Exponential [list CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m8_f16_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m8_f16_div Divide [list CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m8_f16_to_f32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
} elseif {$variant eq "fp32"} {
    make_fp_ip m8_f32_sub Add_Subtract [list CONFIG.Add_Sub_Value {Subtract} \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m8_f32_exp Exponential [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m8_f32_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m8_f32_div Divide [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Single}]
} else {
    error "Softmax FP IP variant must be fp16 or fp32, got $variant"
}
make_fp_ip m8_f32_mul Multiply [list CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Single}]
make_fp_ip m8_f32_to_u17 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {17} CONFIG.C_Result_Fraction_Width {0} \
    CONFIG.C_Has_UNDERFLOW {0} CONFIG.C_Has_OVERFLOW {0}]
