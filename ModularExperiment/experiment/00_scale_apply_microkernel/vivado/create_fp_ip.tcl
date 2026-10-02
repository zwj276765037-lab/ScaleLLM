if {[info exists ::env(HAP_SCALE_VARIANT)]} {
    set variant $::env(HAP_SCALE_VARIANT)
} elseif {[info exists ::env(HAP_OOC_VARIANT)]} {
    set variant $::env(HAP_OOC_VARIANT)
} else {
    error "HAP_SCALE_VARIANT or HAP_OOC_VARIANT is required"
}
if {$variant ne "fp16" && $variant ne "fp32"} {
    error "unsupported floating-point scale variant: $variant"
}

proc make_m3_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [concat [list \
        CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

make_m3_ip m3_int21_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {21} \
    CONFIG.C_A_Fraction_Width {0} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} \
    CONFIG.C_Result_Fraction_Width {24}]
make_m3_ip m3_fp32_mul Multiply [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Single}]
make_m3_ip m3_fp32_to_s42 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {18} \
    CONFIG.C_Result_Fraction_Width {24}]

if {$variant eq "fp16"} {
    make_m3_ip m3_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} \
        CONFIG.C_Result_Fraction_Width {11}]
    make_m3_ip m3_fp16_mul Multiply [list \
        CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_m3_ip m3_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} \
        CONFIG.C_Result_Fraction_Width {24}]
}
