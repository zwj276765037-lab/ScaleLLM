if {[info exists ::env(HAP_SCALE_VARIANT)]} {
    set variant $::env(HAP_SCALE_VARIANT)
} elseif {[info exists ::env(HAP_OOC_VARIANT)]} {
    set variant $::env(HAP_OOC_VARIANT)
} else {
    error "HAP_SCALE_VARIANT or HAP_OOC_VARIANT is required"
}
if {$variant ne "fp16" && $variant ne "fp32"} {
    error "unsupported M12 FP variant: $variant"
}

proc make_m12_ip {name operation config expected_latency} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    set actual_latency [get_property CONFIG.C_Latency [get_ips $name]]
    if {$actual_latency != $expected_latency} {
        error "$name latency changed: expected $expected_latency got $actual_latency"
    }
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

make_m12_ip m12_int17_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {17} CONFIG.C_A_Fraction_Width {0} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 6
make_m12_ip m12_fp32_add Add_Subtract [list \
    CONFIG.Add_Sub_Value {Add} CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Single}] 11
make_m12_ip m12_fp32_to_s24 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {16}] 6

if {$variant eq "fp16"} {
    make_m12_ip m12_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}] 3
    make_m12_ip m12_fp16_mul Multiply [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}] 6
    make_m12_ip m12_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 2
} else {
    make_m12_ip m12_fp32_mul Multiply [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}] 8
}
