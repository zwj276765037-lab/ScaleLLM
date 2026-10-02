set variant [expr {[info exists ::env(HAP_SCALE_VARIANT)] ?
    $::env(HAP_SCALE_VARIANT) : $::env(HAP_OOC_VARIANT)}]

proc m5_create_fp_ip {name operation properties} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control NonBlocking \
        CONFIG.Operation_Type $operation] $properties] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

if {$variant eq "fp16"} {
    m5_create_fp_ip m7_f16_mul Multiply [list \
        CONFIG.A_Precision_Type Half \
        CONFIG.Result_Precision_Type Half]
    m5_create_fp_ip m7_f16_to_f32 Float_to_float [list \
        CONFIG.A_Precision_Type Half \
        CONFIG.Result_Precision_Type Single \
        CONFIG.C_Result_Exponent_Width 8 \
        CONFIG.C_Result_Fraction_Width 24]
} elseif {$variant eq "fp32"} {
    m5_create_fp_ip m7_f32_mul Multiply [list \
        CONFIG.A_Precision_Type Single \
        CONFIG.Result_Precision_Type Single]
} else {
    error "unsupported M5 FP IP variant: $variant"
}

m5_create_fp_ip m7_f32_add Add_Subtract [list \
    CONFIG.Add_Sub_Value Add \
    CONFIG.A_Precision_Type Single \
    CONFIG.Result_Precision_Type Single]
m5_create_fp_ip m7_f32_to_s20 Float_to_fixed [list \
    CONFIG.A_Precision_Type Single \
    CONFIG.Result_Precision_Type Custom \
    CONFIG.C_Result_Exponent_Width 6 \
    CONFIG.C_Result_Fraction_Width 14 \
    CONFIG.C_Has_UNDERFLOW 0 \
    CONFIG.C_Has_OVERFLOW 0]
