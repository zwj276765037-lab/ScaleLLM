set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [expr {[info exists ::env(HAP_REPORT_DIR)] ?
    [file normalize $::env(HAP_REPORT_DIR)] :
    [file join $root vivado reports mlp_robust_a8_s35_ooc]}]
file mkdir $report_dir
create_project -in_memory -part xcvu9p-flga2104-2L-e
read_verilog -sv [file join $root rtl attention hap_u16_div_u8_seq.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_robust_a8_quantizer_s35.sv]
read_xdc [file join $root vivado constraints \
    mlp_robust_a8_s35_ooc_150mhz.xdc]
synth_design -top hap_mlp_robust_a8_quantizer_s35 \
    -part xcvu9p-flga2104-2L-e -mode out_of_context
opt_design
place_design
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_summary.rpt]
report_utilization -file [file join $report_dir utilization.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc.rpt]
write_checkpoint -force [file join $report_dir post_route.dcp]
set wns [get_property SLACK [lindex \
    [get_timing_paths -delay_type max -max_paths 1] 0]]
set whs [get_property SLACK [lindex \
    [get_timing_paths -delay_type min -max_paths 1] 0]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 ? "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"
puts $fp "wns_ns=$wns"
puts $fp "whs_ns=$whs"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "status=$status"
close $fp
if {$status ne "PASS"} { error "MLP S35 Robust A8 OOC gate failed" }
