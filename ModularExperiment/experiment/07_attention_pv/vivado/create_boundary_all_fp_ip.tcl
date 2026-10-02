# Self-contained so the common OOC runner hashes every operator and boundary
# FP IP configuration through its single HAP_OOC_PRE_SYNTH_TCL artifact.
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
    make_fp_ip m9_f16_mul Multiply [list CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m9_f16_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_fp_ip m9_f16_to_f32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
} elseif {$variant eq "fp32"} {
    make_fp_ip m9_f32_mul Multiply [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Single}]
    make_fp_ip m9_f32_add Add_Subtract [list CONFIG.Add_Sub_Value {Add} \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
} else {
    error "PV FP IP variant must be fp16 or fp32, got $variant"
}
make_fp_ip m9_f32_to_s24 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {16} \
    CONFIG.C_Has_UNDERFLOW {0} CONFIG.C_Has_OVERFLOW {0}]

proc make_m07_boundary_ip {name operation config expected_latency} {
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

make_m07_boundary_ip m07_boundary_u17q16_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {1} CONFIG.C_A_Fraction_Width {16} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 6

make_m07_boundary_ip m07_boundary_s12_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {12} CONFIG.C_A_Fraction_Width {0} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 6

if {$variant eq "fp16"} {
    make_m07_boundary_ip m07_boundary_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}] 3
}
