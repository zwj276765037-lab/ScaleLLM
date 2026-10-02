set dcp [file normalize $::env(M4_DCP)]
set report_dir [file normalize $::env(M4_REPORT_DIR)]
set case_name $::env(M4_CASE_NAME)
file mkdir $report_dir
open_checkpoint $dcp
opt_design -directive Explore
place_design -directive ExtraTimingOpt
if {![info exists ::env(M4_SKIP_PHYSOPT)]} {
    phys_opt_design -directive AggressiveExplore
}
route_design -directive AggressiveExplore
write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 \
    -file [file join $report_dir timing_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
set setup_path [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set bram36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set bram18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set s [open [file join $report_dir summary.txt] w]
foreach {key value} [list tool [version -short] part xcvu9p-flga2104-2L-e \
    clock_mhz 149.9925 case $case_name wns_ns $wns whs_ns $whs \
    lut_primitives $lut ff_primitives $ff dsp48e2 $dsp bram36e2 $bram36 \
    bram18e2 $bram18 uram288 $uram unrouted_nets $unrouted] {
    puts $s "$key=$value"
}
close $s
puts "M4_TILE_OOC_RESULT: CASE=$case_name WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$bram36 BRAM18=$bram18 URAM=$uram UNROUTED=$unrouted"
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0} {error "M4 routed gate failed"}
close_project
