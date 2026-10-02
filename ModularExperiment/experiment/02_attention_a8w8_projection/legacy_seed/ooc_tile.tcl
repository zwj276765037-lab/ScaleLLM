set e [file dirname [file normalize [info script]]]
set case_name $::env(M4_CASE_NAME)
set case_id $::env(M4_CASE_ID)
set top $::env(M4_TOP)
set report_dir [file normalize $::env(M4_REPORT_DIR)]
set build_dir [file normalize $::env(M4_BUILD_DIR)]
set root [file normalize [file join $e .. ..]]
set hap [file normalize [file join $root .. HAP_new]]
set m3 [file normalize [file join $root experiment M3_group32_lane]]
set part xcvu9p-flga2104-2L-e
file mkdir $report_dir
file mkdir $build_dir
create_project "m4_${case_name}_ooc" $build_dir -part $part -force
set_property target_language Verilog [current_project]

proc make_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}
if {$case_id == 2 || $case_id == 3} {
    make_ip m3_int21_to_fp32 Fixed_to_float [list \
        CONFIG.A_Precision_Type {Custom} CONFIG.C_A_Exponent_Width {21} \
        CONFIG.C_A_Fraction_Width {0} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
    make_ip m3_fp32_mul Multiply [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Single}]
    make_ip m3_fp32_to_s42 Float_to_fixed [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} CONFIG.C_Result_Exponent_Width {18} \
        CONFIG.C_Result_Fraction_Width {24}]
}
if {$case_id == 2} {
    make_ip m3_fp32_to_fp16 Float_to_float [list \
        CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
        CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}]
    make_ip m3_fp16_mul Multiply [list CONFIG.A_Precision_Type {Half} \
        CONFIG.Result_Precision_Type {Half}]
    make_ip m3_fp16_to_fp32 Float_to_float [list \
        CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
}

foreach source [list \
    [file join $hap rtl hap_a8w8_group32_lane_s42.sv] \
    [file join $hap rtl hap_linear_tile_accum_s42.sv] \
    [file join $m3 rtl m3_precenter_mac_group32.sv] \
    [file join $m3 rtl m3_s42_fifo.sv] \
    [file join $m3 rtl m3_mac_only_lane.sv] \
    [file join $m3 rtl m3_fp_scale_lanes.sv] \
    [file join $e rtl m4_matched_tile.sv]] {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
add_files -fileset constrs_1 -norecurse [file join $e constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
if {$case_id == 2 || $case_id == 3} {
    set_clock_uncertainty -hold 0.050 [get_clocks clk]
}
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_timing_summary -max_paths 20 -file [file join $report_dir timing_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 5 \
    -file [file join $report_dir utilization_hierarchical_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 \
    -file [file join $report_dir timing_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
set setup_path [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {error "M4 timing paths missing"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set bram36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set bram18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set s [open [file join $report_dir summary.txt] w]
foreach {key value} [list tool [version -short] part $part clock_mhz 149.9925 \
    case $case_name top $top wns_ns $wns whs_ns $whs lut_primitives $lut \
    ff_primitives $ff dsp48e2 $dsp bram36e2 $bram36 bram18e2 $bram18 \
    uram288 $uram unrouted_nets $unrouted] {puts $s "$key=$value"}
close $s
puts "M4_TILE_OOC_RESULT: CASE=$case_name WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$bram36 BRAM18=$bram18 URAM=$uram UNROUTED=$unrouted"
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0} {error "M4 routed gate failed"}
close_project
