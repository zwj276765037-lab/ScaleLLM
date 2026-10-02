# Keep this boundary OOC driver self-contained.  The common OOC runner hashes
# and preserves HAP_OOC_PRE_SYNTH_TCL but does not recursively hash nested Tcl
# sources, so this file contains the exact operator and boundary IP requests.
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

if {[info exists ::env(HAP_SCALE_VARIANT)]} {
    set variant $::env(HAP_SCALE_VARIANT)
} elseif {[info exists ::env(HAP_OOC_VARIANT)]} {
    set variant $::env(HAP_OOC_VARIANT)
} else {
    error "HAP_SCALE_VARIANT or HAP_OOC_VARIANT is required"
}
if {$variant ne "fp16" && $variant ne "fp32"} {
    error "M05 boundary FP variant must be fp16 or fp32"
}

proc make_m05_boundary_ip {name operation config expected_latency} {
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

make_m05_boundary_ip m05_s28q16_to_fp32 Fixed_to_float [list \
    CONFIG.A_Precision_Type {Custom} \
    CONFIG.C_A_Exponent_Width {12} CONFIG.C_A_Fraction_Width {16} \
    CONFIG.Result_Precision_Type {Single} \
    CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}] 6

if {$variant eq "fp16"} {
    make_m05_boundary_ip m05_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}] 3
    make_m05_boundary_ip m05_boundary_fp16_mul Multiply [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Half}] 6
} else {
    make_m05_boundary_ip m05_boundary_fp32_mul Multiply [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Single}] 8
}
