set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
file mkdir $report_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project -in_memory -part xcvu9p-flga2104-2L-e
read_verilog -sv [file join $root rtl mlp hap_mlp_tile_accum_s36.sv]
read_xdc [file join $root vivado constraints \
    mlp_tile_accum_s45_ooc_150mhz.xdc]
synth_design -top hap_mlp_tile_accum_s36 \
    -part xcvu9p-flga2104-2L-e -mode out_of_context \
    -generic LANES=128 -generic ACC_W=45 -generic GROUPS=448
opt_design
place_design -directive ExtraTimingOpt
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
set uram_count [llength [get_cells -hierarchical -filter \
    {REF_NAME == URAM288}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp_count == 0 ? "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"
puts $fp "clock_mhz=150"
puts $fp "lanes=128"
puts $fp "groups=448"
puts $fp "accumulator_width=45"
puts $fp "wns_ns=$wns"
puts $fp "whs_ns=$whs"
puts $fp "unrouted_nets=$unrouted"
puts $fp "drc_errors=$drc_errors"
puts $fp "dsp48e2=$dsp_count"
puts $fp "lut_primitives=$lut_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "ramb36e2=$bram36_count"
puts $fp "uram288=$uram_count"
puts $fp "status=$status"
close $fp
puts "MLP_TILE_ACCUM_S45_RESULT WNS=$wns WHS=$whs LUT=$lut_count FF=$ff_count DSP=$dsp_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "PASS"} { error "MLP S45 accumulator OOC gate failed" }
close_project
