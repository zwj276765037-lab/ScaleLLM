set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_w4_repack48_to12_registered_ooc_harness
file mkdir $out

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp hap_mlp_w4_repack48_to12.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_w4_repack48_to12_registered_ooc_harness.sv]
read_xdc [file join $root vivado constraints \
    mlp_w4_repack48_to12_registered_ooc_150mhz.xdc]
set_msg_config -id {Synth 8-324} -new_severity ERROR
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
if {[llength $src] != 2327 || [llength $sink] != 1850} {
    error "registered OOC proxy FF count mismatch src=[llength $src] sink=[llength $sink]"
}
set dut [get_cells -quiet u_dut]
if {[llength $dut] != 1} {error "repacker DUT hierarchy missing"}

opt_design
# Prevent the placer from promoting non-clock DUT data/control nets to global
# clock buffers.  CLOCK_BUFFER_TYPE NONE is a supported per-net property in
# Vivado 2025.2 and is narrower/safer than a nonexistent global placer param.
set dut_nonclock_nets [get_nets -quiet -hierarchical -filter \
    {NAME =~ u_dut/*}]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
place_design
# Do not run AggressiveExplore here.  On this wide payload leaf it can promote
# data/mask nets to BUFGs, which would be an invalid implementation strategy
# and a misleading timing pass.  Full production later owns any legal physopt.
route_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 \
    -file [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -from $src \
    -to [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && REF_NAME =~ FD*}] \
    -file [file join $out source_to_dut_setup_worst100.rpt]
report_timing -delay_type max -max_paths 100 \
    -from [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && REF_NAME =~ FD*}] -to $sink \
    -file [file join $out dut_to_sink_setup_worst100.rpt]
report_utilization -hierarchical -file [file join $out utilization.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set wns [get_property SLACK [lindex \
    [get_timing_paths -delay_type max -max_paths 1] 0]]
set whs [get_property SLACK [lindex \
    [get_timing_paths -delay_type min -max_paths 1] 0]]
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
    $dut_bram == 0 && $dut_uram == 0 && $data_bufg == 0 ?
    "REGISTERED_OOC_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part top $top clock_mhz 150.015 \
    source_proxy_ff [llength $src] sink_proxy_ff [llength $sink] \
    dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff \
    dut_dsp48e2 $dut_dsp dut_bram_primitives $dut_bram \
    dut_uram288 $dut_uram wns_ns $wns whs_ns $whs \
    data_bufg $data_bufg unrouted_nets $unrouted conflict_nets $conflicts \
    drc_errors $drc_errors status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "REGISTERED_OOC_PASS"} {
    error "MLP W4 repack48-to12 registered OOC implementation gate failed"
}
