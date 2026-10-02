if {[info exists ::env(HAP_SCALE_VARIANT)]} {
    set variant $::env(HAP_SCALE_VARIANT)
} elseif {[info exists ::env(HAP_OOC_VARIANT)]} {
    set variant $::env(HAP_OOC_VARIANT)
} else {
    error "HAP_SCALE_VARIANT or HAP_OOC_VARIANT is required"
}
if {$variant ne "fp16" && $variant ne "fp32"} {
    error "unsupported M09 FP variant: $variant"
}

proc make_m09_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip \
        -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

make_m09_ip m09_int17_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {17} CONFIG.C_A_Fraction_Width {0} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
make_m09_ip m09_fp32_to_s24 Float_to_fixed [list \
    CONFIG.A_Precision_Type {Single} \
    CONFIG.Result_Precision_Type {Custom} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {16}]

if {$variant eq "fp16"} {
    make_m09_ip m09_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}]
    make_m09_ip m09_fp16_mul Multiply [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}]
    make_m09_ip m09_fp16_acc Accumulator [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half} \
        CONFIG.C_Rate {1} CONFIG.C_Accum_Input_Msb {15} \
        CONFIG.C_Accum_Lsb {-24} CONFIG.C_Accum_Msb {22} \
        CONFIG.Has_ARESETn {true} \
        CONFIG.Has_A_TLAST {true} CONFIG.RESULT_TLAST_Behv {Pass_A_TLAST}]
    make_m09_ip m09_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
} else {
    make_m09_ip m09_fp32_mul Multiply [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}]
    make_m09_ip m09_fp32_acc Accumulator [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Rate {1} CONFIG.C_Accum_Input_Msb {15} \
        CONFIG.C_Accum_Lsb {-31} CONFIG.C_Accum_Msb {22} \
        CONFIG.Has_ARESETn {true} \
        CONFIG.Has_A_TLAST {true} CONFIG.RESULT_TLAST_Behv {Pass_A_TLAST}]
}
