set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_a8w4_slice8x12_group_registered_ooc_harness
file mkdir $out
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
create_project -in_memory -part $part
foreach f {
    hap_a8w4_pack2_dsp.sv hap_a8w4_group32_pack2_s17.sv
    hap_a8w4_scalecode_recover2_lut.sv hap_a8w4_group32_lane2_s36.sv
    hap_a8w4_slice8x12_group_s36.sv
    hap_a8w4_slice8x12_group_registered_ooc_harness.sv
} {read_verilog -sv [file join $root rtl mlp $f]}
set xdc_path [file join $root vivado constraints \
    a8w4_slice8x12_group_registered_ooc_150mhz.xdc]
set fp [open $xdc_path r]; set xdc_text [read $fp]; close $fp
set forbidden_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only} \
    $xdc_text]
if {$forbidden_count != 0} {error "registered OOC XDC exception found"}
read_xdc $xdc_path
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
if {[llength $src] != 4136 || [llength $sink] != 3523} {
    error "registered proxy FF mismatch src=[llength $src] sink=[llength $sink]"
}
if {[llength [get_cells -quiet u_dut]] != 1} {error "kernel DUT missing"}
opt_design -directive Explore
set dut_nonclock [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock
place_design
route_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -from $src \
    -to [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && REF_NAME =~ FD*}] -file \
    [file join $out source_to_dut_setup_worst100.rpt]
report_timing -delay_type max -max_paths 100 \
    -from [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && REF_NAME =~ FD*}] -to $sink -file \
    [file join $out dut_to_sink_setup_worst100.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $out utilization_hierarchical.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set wns [get_property SLACK [lindex [get_timing_paths -delay_type max \
    -max_paths 1] 0]]
set whs [get_property SLACK [lindex [get_timing_paths -delay_type min \
    -max_paths 1] 0]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set global_buffers [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ BUFG*}]]
set route_gap_count 0
set log_path [file join $out vivado.log]
if {[file exists $log_path]} {
    set log_fp [open $log_path r]; set log_text [read $log_fp]; close $log_fp
    set route_gap_count [regexp -all {Route 35-198} $log_text]
}
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $conflicts == 0 && $drc_errors == 0 && $dut_dsp == 1536 &&
    $global_buffers == 0 && $forbidden_count == 0 && $route_gap_count == 0 ?
    "REGISTERED_EXCEPTION_FREE_OOC_PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    clock_mhz 150.015 shell_budget_ns 1.000 \
    source_proxy_ff [llength $src] sink_proxy_ff [llength $sink] \
    dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff \
    dut_dsp48e2 $dut_dsp wns_ns $wns whs_ns $whs \
    unrouted_nets $unrouted conflict_nets $conflicts drc_errors $drc_errors \
    global_buffer_count $global_buffers functional_partpin_gap_count \
    $route_gap_count forbidden_timing_exception_count $forbidden_count \
    status $status] {puts $fp "$key=$value"}
close $fp
puts "KERNEL12_REGISTERED_OOC WNS=$wns WHS=$whs DSP=$dut_dsp BUFG=$global_buffers GAPS=$route_gap_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "REGISTERED_EXCEPTION_FREE_OOC_PASS"} {
    error "kernel12 registered OOC gate failed"
}
close_project
