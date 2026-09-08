set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
file mkdir $report_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project -in_memory -part xcvu9p-flga2104-2L-e
read_verilog -sv [file join $root rtl attention hap_u16_div_u8_seq.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_hadamard32_s32_norm_stream.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_robust_a8_quantizer_s35.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_product_frontend16_q4.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_product_frontend16_q4_ooc_wrapper.sv]
read_xdc [file join $root vivado constraints \
    mlp_product_frontend16_q4_ooc_150mhz.xdc]
synth_design -top hap_mlp_product_frontend16_q4_ooc_wrapper \
    -part xcvu9p-flga2104-2L-e -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
opt_design -directive Explore
place_design -directive ExtraTimingOpt
route_design -directive AggressiveExplore
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_summary.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $report_dir utilization_hierarchical.rpt]
report_utilization -file [file join $report_dir utilization.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc.rpt]
write_checkpoint -force [file join $report_dir post_route.dcp]
set wns [get_property SLACK [lindex [get_timing_paths -delay_type max \
    -max_paths 1] 0]]
set whs [get_property SLACK [lindex [get_timing_paths -delay_type min \
    -max_paths 1] 0]]
set unrouted [llength [get_nets -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp_count [llength [get_cells -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set lut_count [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
set bram36_count [llength [get_cells -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp_count == 64 ? "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"
puts $fp "clock_mhz=150"
puts $fp "requests=16"
puts $fp "hadamard_units=1"
puts $fp "quantizers=4"
puts $fp "physical_top=hap_mlp_product_frontend16_q4_ooc_wrapper"
puts $fp "ooc_interface=32bit_serial_load_and_drain"
puts $fp "observed_xsim_max_group_cycles=835"
puts $fp "wns_ns=$wns"
puts $fp "whs_ns=$whs"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "dsp48e2=$dsp_count"
puts $fp "lut_primitives=$lut_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "ramb36e2=$bram36_count"
puts $fp "status=$status"
close $fp
puts "MLP_PRODUCT_FRONTEND16_Q4_RESULT WNS=$wns WHS=$whs LUT=$lut_count FF=$ff_count DSP=$dsp_count BRAM36=$bram36_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "PASS"} { error "MLP product frontend16 Q4 OOC gate failed" }
close_project
