set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set checkpoint [file normalize $::env(HAP_CHECKPOINT)]
file mkdir $report_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
if {![file exists $checkpoint]} {
    error "Missing routed checkpoint: $checkpoint"
}
open_checkpoint $checkpoint

set setup_before [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_before [get_timing_paths -quiet -delay_type min -max_paths 1]
set wns_before [get_property SLACK [lindex $setup_before 0]]
set whs_before [get_property SLACK [lindex $hold_before 0]]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_before_hold_fix.rpt]

# Explore skips all work when setup is already non-negative.  This explicit
# Vivado 2025.2 hold pass is isolated from the input checkpoint and followed
# by a preserve reroute so modified delay cells/nets become fully routed.
phys_opt_design -hold_fix
route_design -preserve

write_checkpoint -force [file join $report_dir post_hold_fix.dcp]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_after_hold_fix.rpt]
report_timing -delay_type min -max_paths 100 \
    -path_type full_clock_expanded -file \
    [file join $report_dir timing_min100_after_hold_fix.rpt]
report_utilization -file [file join $report_dir utilization_after_hold_fix.rpt]
report_route_status -file [file join $report_dir route_status_after_hold_fix.rpt]
report_drc -file [file join $report_dir drc_after_hold_fix.rpt]

set setup_after [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_after [get_timing_paths -quiet -delay_type min -max_paths 1]
set wns_after [get_property SLACK [lindex $setup_after 0]]
set whs_after [get_property SLACK [lindex $hold_after 0]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set status [expr {$wns_after >= 0.0 && $whs_after >= 0.0 &&
    $unrouted == 0 && $drc_errors == 0 && $dsp_count == 2048 ?
    "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"
puts $fp "source_checkpoint=$checkpoint"
puts $fp "repair=phys_opt_design_-hold_fix_then_route_design_-preserve"
puts $fp "wns_before_ns=$wns_before"
puts $fp "whs_before_ns=$whs_before"
puts $fp "wns_after_ns=$wns_after"
puts $fp "whs_after_ns=$whs_after"
puts $fp "lut_primitives=$lut_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "dsp48e2=$dsp_count"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "status=$status"
close $fp
puts "A8W4_SLICE_HOLD_REPAIR WNS=$wns_before->$wns_after WHS=$whs_before->$whs_after LUT=$lut_count FF=$ff_count DSP=$dsp_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "PASS"} { error "A8W4 single-SLR slice hold repair failed" }
close_design
