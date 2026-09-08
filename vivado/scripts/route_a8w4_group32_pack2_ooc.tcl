set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [expr {[info exists ::env(HAP_REPORT_DIR)] ?
    [file normalize $::env(HAP_REPORT_DIR)] :
    [file join $root vivado reports a8w4_group32_pack2_ooc]}]
file mkdir $report_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project -in_memory -part xcvu9p-flga2104-2L-e
read_verilog -sv [file join $root rtl mlp hap_a8w4_pack2_dsp.sv]
read_verilog -sv [file join $root rtl mlp hap_a8w4_group32_pack2_s17.sv]
read_xdc [file join $root vivado constraints \
    a8w4_group32_pack2_ooc_150mhz.xdc]
synth_design -top hap_a8w4_group32_pack2_s17 \
    -part xcvu9p-flga2104-2L-e -mode out_of_context
opt_design
place_design
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_summary.rpt]
report_utilization -hierarchical -file \
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
    {ROUTE_STATUS == UNROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp_count [llength [get_cells -hierarchical -filter \
    {REF_NAME =~ DSP48E2*}]]
set lut_count [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp_count == 32 ? "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"
puts $fp "clock_mhz=150"
puts $fp "wns_ns=$wns"
puts $fp "whs_ns=$whs"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "dsp48e2=$dsp_count"
puts $fp "lut_primitives=$lut_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "status=$status"
close $fp
if {$status ne "PASS"} { error "A8W4 group32 pack2 OOC gate failed" }
