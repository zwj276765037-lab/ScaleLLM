if {[info exists ::env(HAP_FP_VARIANT)]} {
    set variant $::env(HAP_FP_VARIANT)
} else {
    set variant $::env(HAP_OOC_VARIANT)
}
if {$variant ne "fp16" && $variant ne "fp32"} {
    error "M10 boundary FP variant must be fp16 or fp32"
}

proc make_m10_boundary_ip {name operation config expected_latency} {
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

make_m10_boundary_ip m10_boundary_s24q16_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {8} CONFIG.C_A_Fraction_Width {16} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 6

if {$variant eq "fp16"} {
    make_m10_boundary_ip m10_boundary_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}] 3
}
