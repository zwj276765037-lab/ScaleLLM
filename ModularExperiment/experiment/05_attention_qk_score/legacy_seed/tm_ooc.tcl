set e [file dirname [file normalize [info script]]]
set id $::env(M7_CASE_ID)
set n $::env(M7_CASE_NAME)
set top $::env(M7_TOP)
set rd [file normalize $::env(M7_REPORT_DIR)]
set bd [file normalize $::env(M7_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $rd
create_project m7_tm_$n $bd -part $part -force
proc mip {n op p} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $n
    set_property -dict [concat [list CONFIG.Flow_Control NonBlocking CONFIG.Operation_Type $op] $p] [get_ips $n]
    set_property generate_synth_checkpoint false [get_files ${n}.xci]
    generate_target all [get_ips $n]
}
if {$id==1} {
    mip m7_f16_mul Multiply [list CONFIG.A_Precision_Type Half CONFIG.Result_Precision_Type Half]
    mip m7_f16_to_f32 Float_to_float [list CONFIG.A_Precision_Type Half CONFIG.Result_Precision_Type Single CONFIG.C_Result_Exponent_Width 8 CONFIG.C_Result_Fraction_Width 24]
}
if {$id==2} {
    mip m7_f32_mul Multiply [list CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Single]
}
mip m7_f32_add Add_Subtract [list CONFIG.Add_Sub_Value Add CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Single]
mip m7_f32_to_s20 Float_to_fixed [list CONFIG.A_Precision_Type Single CONFIG.Result_Precision_Type Custom CONFIG.C_Result_Exponent_Width 6 CONFIG.C_Result_Fraction_Width 14 CONFIG.C_Has_UNDERFLOW 0 CONFIG.C_Has_OVERFLOW 0]
add_files [file join $e rtl m7_fp_qk_row_tm.sv]
set_property file_type SystemVerilog [get_files m7_fp_qk_row_tm.sv]
add_files -fileset constrs_1 [file join $e constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
synth_design -top $top -part $part -mode out_of_context -flatten_hierarchy none -directive PerformanceOptimized
report_utilization -file [file join $rd utilization_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
write_checkpoint -force [file join $rd post_route.dcp]
report_utilization -file [file join $rd utilization_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 -file [file join $rd timing_post_route.rpt]
report_route_status -file [file join $rd route_status.rpt]
set sp [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hp [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $sp]
set whs [get_property SLACK $hp]
set lut [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -hierarchical -filter {REF_NAME == DSP48E2}]]
set b36 [llength [get_cells -hierarchical -filter {REF_NAME == RAMB36E2}]]
set b18 [llength [get_cells -hierarchical -filter {REF_NAME == RAMB18E2}]]
set unr [llength [get_nets -hierarchical -filter {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set f [open [file join $rd summary.txt] w]
foreach {k v} [list tool [version -short] part $part case $n wns_ns $wns whs_ns $whs lut_primitives $lut ff_primitives $ff dsp48e2 $dsp ramb36e2 $b36 ramb18e2 $b18 unrouted_nets $unr] {puts $f "$k=$v"}
close $f
puts "M7_TM_OOC_RESULT CASE=$n WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$b36 BRAM18=$b18 UNROUTED=$unr"
if {$wns<0||$whs<0||$unr!=0} {error "M7 TM gate"}
close_project
