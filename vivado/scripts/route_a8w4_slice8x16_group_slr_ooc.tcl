set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set target_slr [expr {[info exists ::env(HAP_TARGET_SLR)] ?
    $::env(HAP_TARGET_SLR) : "SLR0"}]
set part "xcvu9p-flga2104-2L-e"
set top "hap_a8w4_slice8x16_group_s36"

file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project a8w4_slice8x16_group_slr_ooc $build_dir \
    -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    a8w4_slice8x16_group_sources.list]
set handle [open $manifest r]
foreach raw_line [split [read $handle] "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string index $line 0] eq "#"} { continue }
    set path [file normalize [file join $root $line]]
    if {![file exists $path]} { error "Missing source: $path" }
    add_files -fileset sources_1 $path
    if {[string match "*.sv" $path]} {
        set_property file_type SystemVerilog [get_files $path]
    }
}
close $handle
add_files -fileset constrs_1 -norecurse [file join $root vivado \
    constraints a8w4_slice8x16_group_ooc_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_timing_summary -max_paths 20 -file \
    [file join $report_dir timing_post_synth.rpt]

opt_design -directive Explore
set slr_object [get_slrs -quiet $target_slr]
if {[llength $slr_object] != 1} {
    error "Expected one target SLR named $target_slr, got $slr_object"
}
create_pblock pblock_mlp_slice
resize_pblock [get_pblocks pblock_mlp_slice] -add $target_slr
set leaf_cells [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]
if {[llength $leaf_cells] == 0} { error "No primitive cells for SLR pblock" }
add_cells_to_pblock [get_pblocks pblock_mlp_slice] $leaf_cells
set_property SNAPPING_MODE ROUTING [get_pblocks pblock_mlp_slice]
write_checkpoint -force [file join $report_dir post_opt_slr_pblock.dcp]
report_utilization -pblocks pblock_mlp_slice -file \
    [file join $report_dir utilization_pblock_post_opt.rpt]

place_design -directive ExtraTimingOpt
write_checkpoint -force [file join $report_dir post_place.dcp]
report_utilization -file [file join $report_dir utilization_post_place.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_post_place.rpt]
route_design -directive AggressiveExplore
write_checkpoint -force [file join $report_dir post_route_before_physopt.dcp]
phys_opt_design -directive Explore
write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $report_dir utilization_hier_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_post_route.rpt]
report_timing -delay_type max -max_paths 20 -path_type full_clock_expanded \
    -file [file join $report_dir timing_worst20_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
report_drc -file [file join $report_dir drc_post_route.rpt]
report_design_analysis -congestion -file \
    [file join $report_dir congestion_post_route.rpt]

set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_paths] == 0 || [llength $hold_paths] == 0} {
    error "SLR slice OOC timing paths are missing"
}
set wns [get_property SLACK [lindex $setup_paths 0]]
set whs [get_property SLACK [lindex $hold_paths 0]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set bram36_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set bram18_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set uram_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp_count == 2048 && $lut_count <= 420000 &&
    $ff_count <= 420000 ? "PASS" : "FAIL"}]
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "target_slr=$target_slr"
puts $summary "clock_mhz=150"
puts $summary "wns_ns=$wns"
puts $summary "whs_ns=$whs"
puts $summary "lut_primitives=$lut_count"
puts $summary "ff_primitives=$ff_count"
puts $summary "dsp48e2=$dsp_count"
puts $summary "ramb36e2=$bram36_count"
puts $summary "ramb18e2=$bram18_count"
puts $summary "uram288=$uram_count"
puts $summary "unrouted_nets=$unrouted"
puts $summary "drc_errors=$drc_errors"
puts $summary "active_rows=8"
puts $summary "columns=16"
puts $summary "group_size=32"
puts $summary "steady_ii=1"
puts $summary "useful_tops=1.2288"
puts $summary "status=$status"
close $summary
puts "A8W4_SLICE8X16_SLR_RESULT SLR=$target_slr WNS=$wns WHS=$whs LUT=$lut_count FF=$ff_count DSP=$dsp_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "PASS"} { error "A8W4 single-SLR slice OOC gate failed" }
close_project
