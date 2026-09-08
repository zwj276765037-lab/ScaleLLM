set out [file normalize $::env(HAP_REPORT_DIR)]
open_checkpoint [file join $out post_route.dcp]

proc first_slack {delay from_set to_set label} {
    set paths [get_timing_paths -quiet -delay_type $delay -max_paths 1 \
        -from $from_set -to $to_set]
    if {[llength $paths] != 1} {error "$label path set is empty"}
    return [get_property SLACK [lindex $paths 0]]
}

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set dut_regs [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]
if {[llength $src] != 2318 || [llength $sink] != 1870 ||
    [llength $dut_regs] == 0} {
    error "registered route audit hierarchy/count mismatch"
}

set wns [get_property SLACK [lindex \
    [get_timing_paths -delay_type max -max_paths 1] 0]]
set whs [get_property SLACK [lindex \
    [get_timing_paths -delay_type min -max_paths 1] 0]]
set source_to_dut_wns [first_slack max $src $dut_regs source_to_dut_setup]
set source_to_dut_whs [first_slack min $src $dut_regs source_to_dut_hold]
set dut_internal_wns [first_slack max $dut_regs $dut_regs dut_internal_setup]
set dut_internal_whs [first_slack min $dut_regs $dut_regs dut_internal_hold]
set dut_to_sink_wns [first_slack max $dut_regs $sink dut_to_sink_setup]
set dut_to_sink_whs [first_slack min $dut_regs $sink dut_to_sink_hold]

set route_errors [llength [get_nets -quiet -hierarchical -filter \
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
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]

set all_bufg [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}]
set clock_bufg 0
set data_bufg 0
foreach cell $all_bufg {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] > 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}
set top_ports [get_ports -quiet]
set nonclock_top_ports [get_ports -quiet -filter {NAME != clk}]

set exceptions_file [file join $out exceptions_coverage.rpt]
set exceptions_fh [open $exceptions_file r]
set exceptions_text [read $exceptions_fh]
close $exceptions_fh
set max_delay_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+Max Delay[[:space:]]} $exceptions_text]
set min_delay_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+Min Delay[[:space:]]} $exceptions_text]
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} $exceptions_text]

set status [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $source_to_dut_wns >= 0.0 && $source_to_dut_whs >= 0.0 &&
    $dut_internal_wns >= 0.0 && $dut_internal_whs >= 0.0 &&
    $dut_to_sink_wns >= 0.0 && $dut_to_sink_whs >= 0.0 &&
    $route_errors == 0 && $conflicts == 0 && $drc_errors == 0 &&
    $dut_dsp == 0 && $dut_ramb36 == 96 && $dut_ramb18 == 0 &&
    $dut_uram == 0 && $data_bufg == 0 && [llength $top_ports] == 1 &&
    [llength $nonclock_top_ports] == 0 &&
    $max_delay_rows == 0 && $min_delay_rows == 0 &&
    $false_path_rows == 0 ? "REGISTERED_OOC_ROUTE_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
    part xcvu9p-flga2104-2L-e \
    top hap_mlp_gate_up_gather_pingpong12_registered_ooc_harness \
    clock_mhz 150.015 source_proxy_ff [llength $src] \
    sink_proxy_ff [llength $sink] dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_dsp48e2 $dut_dsp dut_uram288 $dut_uram \
    wns_ns $wns whs_ns $whs source_to_dut_wns_ns $source_to_dut_wns \
    source_to_dut_whs_ns $source_to_dut_whs \
    dut_internal_wns_ns $dut_internal_wns \
    dut_internal_whs_ns $dut_internal_whs \
    dut_to_sink_wns_ns $dut_to_sink_wns \
    dut_to_sink_whs_ns $dut_to_sink_whs \
    top_port_count [llength $top_ports] \
    nonclock_top_port_count [llength $nonclock_top_ports] \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    max_delay_exception_rows $max_delay_rows \
    min_delay_exception_rows $min_delay_rows \
    false_path_exception_rows $false_path_rows \
    unrouted_or_partial_nets $route_errors conflict_nets $conflicts \
    drc_errors $drc_errors status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "REGISTERED_OOC_ROUTE_PASS"} {
    error "V5 gate/up gather registered route checkpoint audit failed"
}
