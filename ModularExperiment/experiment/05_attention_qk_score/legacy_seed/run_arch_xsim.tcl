set e [file dirname [file normalize [info script]]]
set id $::env(M7_CASE_ID)
set n $::env(M7_CASE_NAME)
set qs $::env(M7_QUERY_START)
set vk $::env(M7_VALID_KEYS)
set data_dir $::env(M7_DATA_DIR)
set pd [file join $e artifacts project_arch_$n]
set rtl [file normalize [file join $e .. .. .. HAP_new rtl]]
file delete -force $pd
create_project m7_arch_$n $pd -part xcvu9p-flga2104-2L-e -force
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sources_1]
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sim_1]

proc mip {n op p} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $n
    set_property -dict [concat [list CONFIG.Flow_Control NonBlocking CONFIG.Operation_Type $op] $p] [get_ips $n]
    generate_target all [get_ips $n]
}
if {$id == 1} {
    mip m7_f16_mul Multiply [list CONFIG.A_Precision_Type Half CONFIG.Result_Precision_Type Half]
    mip m7_f16_to_f32 Float_to_float [list CONFIG.A_Precision_Type Half CONFIG.Result_Precision_Type Single CONFIG.C_Result_Exponent_Width 8 CONFIG.C_Result_Fraction_Width 24]
}
if {$id == 2} {
    mip m7_f32_mul Multiply [list CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Single]
}
if {$id != 0} {
    mip m7_f32_add Add_Subtract [list CONFIG.Add_Sub_Value Add CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Single]
    mip m7_f32_to_s20 Float_to_fixed [list CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Custom CONFIG.C_Result_Exponent_Width 6 CONFIG.C_Result_Fraction_Width 14 CONFIG.C_Has_UNDERFLOW 0 CONFIG.C_Has_OVERFLOW 0]
}

set sources [list \
    [file join $rtl hap_unsigned_div_seq.sv] \
    [file join $rtl hap_softmax_exp_u17.sv] \
    [file join $rtl hap_softmax_recip_u17.sv] \
    [file join $rtl hap_softmax_prob_u16.sv] \
    [file join $rtl hap_softmax_row_128.sv] \
    [file join $rtl hap_pv_tile16_s43.sv]]
if {$id == 0} {
    lappend sources [file join $rtl hap_q24k12_group_dot_s40.sv]
    lappend sources [file join $rtl hap_score_group_scale_s35.sv]
    lappend sources [file join $rtl hap_score_accum4_s20.sv]
    lappend sources [file join $rtl hap_qk_score_row_128.sv]
} else {
    lappend sources [file join $e rtl m7_fp_qk_slot_arch.sv]
}
lappend sources [file join $e rtl m7_attention_row_arch.sv]
lappend sources [file join $e rtl m7_attention_accel_arch.sv]
lappend sources [file join $e tb m7_qk_arch_tb.sv]
foreach s $sources {
    add_files $s
    set_property file_type SystemVerilog [get_files [file tail $s]]
}
add_files -fileset sim_1 [file join $rtl .. data softmax_exp_u17 exp_lut_u17.mem]
set_property top m7_qk_arch_tb [get_filesets sim_1]
set_property generic "CASE_ID=$id QUERY_START=$qs VALID_KEYS=$vk DATA_DIR=$data_dir" [get_filesets sim_1]
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
