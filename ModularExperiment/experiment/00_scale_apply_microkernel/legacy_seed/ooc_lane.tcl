set experiment_dir [file dirname [file normalize [info script]]]
set case_name $::env(M3_CASE_NAME)
set top $::env(M3_TOP)
set report_dir [file normalize $::env(M3_REPORT_DIR)]
set build_dir [file normalize $::env(M3_BUILD_DIR)]
set hap_dir [file normalize [file join $experiment_dir .. .. .. HAP_new]]
set part xcvu9p-flga2104-2L-e

file mkdir $report_dir
file mkdir $build_dir
create_project "m3_${case_name}_ooc" $build_dir -part $part -force
set_property target_language Verilog [current_project]

proc make_ip {name operation config} {
    create_ip -name floating_point -vendor xilinx.com -library ip -module_name $name
    set_property -dict [concat [list CONFIG.Flow_Control {NonBlocking} \
        CONFIG.Operation_Type $operation] $config] [get_ips $name]
    # Include generated RTL in the parent OOC synthesis.  A per-IP synthesis
    # checkpoint otherwise leaves the manually invoked synth_design unable to
    # resolve the floating-point module names.
    set_property generate_synth_checkpoint false [get_files ${name}.xci]
    generate_target all [get_ips $name]
}

set sources [list]
if {$case_name eq "mac_only"} {
    lappend sources \
        [file join $experiment_dir rtl m3_precenter_mac_group32.sv] \
        [file join $experiment_dir rtl m3_s42_fifo.sv] \
        [file join $experiment_dir rtl m3_mac_only_lane.sv]
} elseif {$case_name eq "scalecode"} {
    lappend sources [file join $hap_dir rtl hap_a8w8_group32_lane_s42.sv]
} else {
    make_ip m3_int21_to_fp32 Fixed_to_float [list \
        CONFIG.A_Precision_Type {Custom} CONFIG.C_A_Exponent_Width {21} \
        CONFIG.C_A_Fraction_Width {0} CONFIG.Result_Precision_Type {Single} \
        CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
    make_ip m3_fp32_mul Multiply [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Single}]
    make_ip m3_fp32_to_s42 Float_to_fixed [list CONFIG.A_Precision_Type {Single} \
        CONFIG.Result_Precision_Type {Custom} CONFIG.C_Result_Exponent_Width {18} \
        CONFIG.C_Result_Fraction_Width {24}]
    if {$case_name eq "fp16"} {
        make_ip m3_fp32_to_fp16 Float_to_float [list \
            CONFIG.A_Precision_Type {Single} CONFIG.Result_Precision_Type {Custom} \
            CONFIG.C_Result_Exponent_Width {5} CONFIG.C_Result_Fraction_Width {11}]
        make_ip m3_fp16_mul Multiply [list CONFIG.A_Precision_Type {Half} \
            CONFIG.Result_Precision_Type {Half}]
        make_ip m3_fp16_to_fp32 Float_to_float [list \
            CONFIG.A_Precision_Type {Half} CONFIG.Result_Precision_Type {Single} \
            CONFIG.C_Result_Exponent_Width {8} CONFIG.C_Result_Fraction_Width {24}]
    }
    lappend sources \
        [file join $experiment_dir rtl m3_precenter_mac_group32.sv] \
        [file join $experiment_dir rtl m3_s42_fifo.sv] \
        [file join $experiment_dir rtl m3_fp_scale_lanes.sv]
}

foreach source $sources {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
add_files -fileset constrs_1 -norecurse \
    [file join $experiment_dir constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
# The generated floating-point cores contain same-cycle intra-DSP arcs whose
# minimum delay cannot be detoured by the router.  Keep the common 0.150 ns
# setup uncertainty, but use a 0.050 ns hold uncertainty for these generated
# IP internals instead of charging setup uncertainty a second time.
if {$case_name eq "fp16" || $case_name eq "fp32"} {
    set_clock_uncertainty -hold 0.050 [get_clocks clk]
}
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_timing_summary -max_paths 20 \
    -file [file join $report_dir timing_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
# OOC interfaces can expose very short local paths.  Apply the same explicit
# post-route hold repair to every case before collecting the timing gate.
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
if {$setup_path eq "" || $hold_path eq ""} { error "M3 timing paths missing" }
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
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "clock_mhz=149.9925"
puts $summary "case=$case_name"
puts $summary "top=$top"
puts $summary "wns_ns=$wns"
puts $summary "whs_ns=$whs"
puts $summary "lut_primitives=$lut"
puts $summary "ff_primitives=$ff"
puts $summary "dsp48e2=$dsp"
puts $summary "bram36e2=$bram36"
puts $summary "bram18e2=$bram18"
puts $summary "uram288=$uram"
puts $summary "unrouted_nets=$unrouted"
close $summary
puts "M3_LANE_OOC_RESULT: CASE=$case_name TOP=$top WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$bram36 BRAM18=$bram18 URAM=$uram UNROUTED=$unrouted"
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0} {
    error "M3 routed gate failed"
}
close_project
