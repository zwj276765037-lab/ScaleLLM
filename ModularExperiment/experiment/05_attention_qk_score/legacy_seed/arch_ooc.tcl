set e [file dirname [file normalize [info script]]]
set id $::env(M7_CASE_ID)
set n $::env(M7_CASE_NAME)
set top m7_attention_row_arch
set rd [file normalize $::env(M7_REPORT_DIR)]
set bd [file normalize $::env(M7_BUILD_DIR)]
set rtl [file normalize [file join $e .. .. .. HAP_new rtl]]
set part xcvu9p-flga2104-2L-e
file mkdir $rd
file delete -force $bd
create_project m7_arch_ooc_$n $bd -part $part -force
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sources_1]

proc mip {n op p} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $n
    set_property -dict [concat [list CONFIG.Flow_Control NonBlocking CONFIG.Operation_Type $op] $p] [get_ips $n]
    set_property generate_synth_checkpoint false [get_files ${n}.xci]
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
foreach s $sources {
    add_files $s
    set_property file_type SystemVerilog [get_files [file tail $s]]
}
add_files [file join $rtl .. data softmax_exp_u17 exp_lut_u17.mem]
add_files -fileset constrs_1 [file join $e constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
set_property generic "CASE_ID=$id" [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
report_utilization -file [file join $rd utilization_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
write_checkpoint -force [file join $rd post_route.dcp]
report_utilization -file [file join $rd utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $rd utilization_hier_post_route.rpt]

set qk [get_cells -quiet -hierarchical -filter {
    NAME =~ *u_qk && (REF_NAME =~ *qk* || ORIG_REF_NAME =~ *qk*)}]
if {[llength $qk] != 1} {
    error "expected exactly one physical QK slot, got [llength $qk]: $qk"
}
report_utilization -cells $qk \
    -file [file join $rd qk_slot_utilization_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 \
    -file [file join $rd timing_post_route.rpt]
report_route_status -file [file join $rd route_status.rpt]

set sp [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hp [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $sp]
set whs [get_property SLACK $hp]
set unr [llength [get_nets -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set error_messages [get_msg_config -count -severity ERROR]
set critical_warning_messages \
    [get_msg_config -count -severity {CRITICAL WARNING}]
set util [report_utilization -return_string]
set qk_util [report_utilization -cells $qk -return_string]
set row_lut NA
set row_ff NA
set row_dsp NA
set row_bram NA
set qk_lut NA
set qk_ff NA
set qk_dsp NA
set qk_bram NA
regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util _ row_lut
regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util _ row_ff
regexp {\| DSPs\s+\|\s*([0-9]+)} $util _ row_dsp
regexp {\| Block RAM Tile\s+\|\s*([0-9]+)} $util _ row_bram
regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $qk_util _ qk_lut
regexp {\| CLB Registers\s+\|\s*([0-9]+)} $qk_util _ qk_ff
regexp {\| DSPs\s+\|\s*([0-9]+)} $qk_util _ qk_dsp
regexp {\| Block RAM Tile\s+\|\s*([0-9]+)} $qk_util _ qk_bram
set f [open [file join $rd summary.txt] w]
foreach {k v} [list tool [version -short] part $part case $n \
    resource_contract hierarchical_Total_LUTs clock_mhz 150 \
    setup_uncertainty_ns 0.150 io_delay_constraints none \
    row_total_luts $row_lut row_flip_flops $row_ff row_dsps $row_dsp \
    row_bram_tiles $row_bram qk_cell [get_property NAME $qk] \
    qk_total_luts $qk_lut qk_flip_flops $qk_ff qk_dsps $qk_dsp \
    qk_bram_tiles $qk_bram \
    qk_detail_report qk_slot_utilization_post_route.rpt \
    hierarchy_report utilization_hier_post_route.rpt \
    wns_ns $wns whs_ns $whs unrouted_nets $unr drc_errors $drc_errors \
    error_messages $error_messages \
    critical_warning_messages $critical_warning_messages] {
    puts $f "$k=$v"
}
close $f
puts "M7_ARCH_OOC_RESULT CASE=$n ROW_TOTAL_LUT=$row_lut ROW_FF=$row_ff ROW_DSP=$row_dsp QK_CELL=[get_property NAME $qk] QK_TOTAL_LUT=$qk_lut QK_FF=$qk_ff QK_DSP=$qk_dsp WNS=$wns WHS=$whs UNROUTED=$unr DRC_ERRORS=$drc_errors ERROR_MESSAGES=$error_messages CRITICAL_WARNING_MESSAGES=$critical_warning_messages"
if {$wns < 0 || $whs < 0 || $unr != 0 || $drc_errors != 0 ||
        $error_messages != 0 || $critical_warning_messages != 0} {
    error "M7 architecture OOC gate"
}
close_project
