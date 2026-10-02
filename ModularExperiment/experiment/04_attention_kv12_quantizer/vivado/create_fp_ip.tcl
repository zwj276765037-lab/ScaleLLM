if {[info exists ::env(HAP_SCALE_VARIANT)]} {
    set variant $::env(HAP_SCALE_VARIANT)
} else {
    set variant $::env(HAP_OOC_VARIANT)
}

proc m4_create_fp_ip {name result_type result_exp result_frac} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [list \
        CONFIG.Flow_Control NonBlocking \
        CONFIG.Operation_Type Fixed_to_float \
        CONFIG.A_Precision_Type Custom \
        CONFIG.C_A_Exponent_Width 8 \
        CONFIG.C_A_Fraction_Width 16 \
        CONFIG.Result_Precision_Type $result_type \
        CONFIG.C_Result_Exponent_Width $result_exp \
        CONFIG.C_Result_Fraction_Width $result_frac] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

if {$variant eq "fp16"} {
    m4_create_fp_ip m4_s24_to_fp32_for_fp16 Single 8 24
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name m4_fp32_to_fp16
    set_property -dict [list \
        CONFIG.Flow_Control NonBlocking \
        CONFIG.Operation_Type Float_to_float \
        CONFIG.A_Precision_Type Single \
        CONFIG.Result_Precision_Type Custom \
        CONFIG.C_Result_Exponent_Width 5 \
        CONFIG.C_Result_Fraction_Width 11] [get_ips m4_fp32_to_fp16]
    set_property generate_synth_checkpoint false \
        [get_files m4_fp32_to_fp16.xci]
    generate_target all [get_ips m4_fp32_to_fp16]
} elseif {$variant eq "fp32"} {
    m4_create_fp_ip m4_s24_to_fp32 Single 8 24
} else {
    error "unsupported M4 FP variant: $variant"
}
