set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_projection_repack12_to16_s24_registered_ooc_harness
file mkdir $out
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

set xdc_path [file join $root vivado constraints \
    mlp_projection_repack12_to16_s24_registered_ooc_150mhz.xdc]
set audit_text ""
foreach path [list $xdc_path [file normalize [info script]]] {
    set fh [open $path r]
    append audit_text [read $fh]
    close $fh
}
# Build the audit expression from fragments so this script can audit its own
# source without the audit expression itself becoming a false positive.
set forbidden_pattern [join [list \
    "set_false" "_path|set_clock" "_groups|-datapath" "_only"] ""]
set forbidden_count [regexp -all -nocase $forbidden_pattern $audit_text]
if {$forbidden_count != 0} {
    error "projection registered OOC contains forbidden timing exception"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_projection_repack12_to16_s24.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_projection_repack12_to16_s24_registered_ooc_harness.sv]
read_xdc $xdc_path
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
if {[llength $src] != 4637 || [llength $sink] != 6240} {
    error "projection registered proxy FF mismatch src=[llength $src] sink=[llength $sink]"
}
if {[llength [get_cells -quiet u_dut]] != 1} {
    error "projection repacker DUT hierarchy missing"
}

opt_design -directive Explore
set dut_nonclock_nets [get_nets -quiet -hierarchical -filter \
    {NAME =~ u_dut/*}]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
place_design
route_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 \
    -file [file join $out timing_summary.rpt]
report_utilization -hierarchical -hierarchical_depth 5 \
    -file [file join $out utilization_hierarchical.rpt]
report_utilization -file [file join $out utilization.rpt]
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
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_bram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ RAMB*}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set data_bufg [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ BUFG*}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $conflicts == 0 && $drc_errors == 0 && $dut_dsp == 0 &&
    $dut_bram == 0 && $dut_uram == 0 && $data_bufg == 0 &&
    $forbidden_count == 0 ? "REGISTERED_EXCEPTION_FREE_OOC_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    clock_mhz 150 rows 16 matrices 2 source_proxy_ff [llength $src] \
    sink_proxy_ff [llength $sink] wns_ns $wns whs_ns $whs \
    unrouted_nets $unrouted conflict_nets $conflicts drc_errors $drc_errors \
    dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff \
    dut_dsp48e2 $dut_dsp dut_bram_primitives $dut_bram \
    dut_uram288 $dut_uram data_bufg $data_bufg \
    forbidden_timing_exception_count $forbidden_count status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "REGISTERED_EXCEPTION_FREE_OOC_PASS"} {
    error "projection repacker registered OOC gate failed"
}
close_project
