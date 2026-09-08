set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $report_dir

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl integration \
    hap_ddr_read_owner_guard.sv]
read_xdc [file join $root vivado constraints \
    ddr_read_owner_guard_ooc.xdc]
synth_design -top hap_ddr_read_owner_guard -part $part \
    -mode out_of_context -flatten_hierarchy none
opt_design
place_design
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_summary.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $report_dir utilization.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc.rpt]
report_cdc -details -file [file join $report_dir cdc.rpt]
write_checkpoint -force [file join $report_dir post_route.dcp]

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set luts [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ffs [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp == 0 ? "PASS" : "FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=$part"
puts $fp "top=hap_ddr_read_owner_guard"
puts $fp "core_clock_mhz=150"
puts $fp "ddr0_clock_mhz=300"
puts $fp "ddr1_clock_mhz=300"
puts $fp "wns_ns=$wns"
puts $fp "whs_ns=$whs"
puts $fp "lut_primitives=$luts"
puts $fp "ff_primitives=$ffs"
puts $fp "dsp48e2=$dsp"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "status=$status"
close $fp

if {$status ne "PASS"} {
    error "Three-clock DDR owner guard OOC implementation gate failed"
}
