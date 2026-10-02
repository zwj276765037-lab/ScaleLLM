set variant [expr {[info exists ::env(HAP_SCALE_VARIANT)] ?
    $::env(HAP_SCALE_VARIANT) : $::env(HAP_OOC_VARIANT)}]

proc m1_create_fixed_to_fp32 {name} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [list \
        CONFIG.Flow_Control NonBlocking \
        CONFIG.Operation_Type Fixed_to_float \
        CONFIG.A_Precision_Type Custom \
        CONFIG.C_A_Exponent_Width 4 \
        CONFIG.C_A_Fraction_Width 24 \
        CONFIG.Result_Precision_Type Single \
        CONFIG.C_Result_Exponent_Width 8 \
        CONFIG.C_Result_Fraction_Width 24] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

if {$variant eq "fp16"} {
    m1_create_fixed_to_fp32 m1_scale_q24_to_fp32_for_fp16
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name m1_scale_fp32_to_fp16
    set_property -dict [list \
        CONFIG.Flow_Control NonBlocking \
        CONFIG.Operation_Type Float_to_float \
        CONFIG.A_Precision_Type Single \
        CONFIG.Result_Precision_Type Custom \
        CONFIG.C_Result_Exponent_Width 5 \
        CONFIG.C_Result_Fraction_Width 11] [get_ips m1_scale_fp32_to_fp16]
    set_property generate_synth_checkpoint false \
        [get_files m1_scale_fp32_to_fp16.xci]
    generate_target all [get_ips m1_scale_fp32_to_fp16]
} elseif {$variant eq "fp32"} {
    m1_create_fixed_to_fp32 m1_scale_q24_to_fp32
} else {
    error "unsupported M1 FP variant: $variant"
}
