set root [file normalize [file join [file dirname [file normalize [info script]]] ../..]]
set in_dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PLACE_DIR)]
file mkdir $out
if {![string match "2025.2*" [version -short]]} {error "Vivado 2025.2 required"}
open_checkpoint $in_dcp
read_xdc [file join $root vivado constraints attention_mlp_production_ooc_clocks.xdc]

# Place only the two physical MLP slices on opposite outer SLRs. Attention and
# the large URAM banks remain free in this first feasibility run; their measured
# post-place distribution is the input to the next floorplan iteration.
set slice_roots [get_cells -quiet -hier -filter \
 {ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
  REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*}]
if {[llength $slice_roots] != 2} {
 error "Expected two synthesized MLP slice roots, got [llength $slice_roots]"
}
set slice_roots [lsort -dictionary $slice_roots]
set slice0_root [lindex $slice_roots 0]
set slice1_root [lindex $slice_roots 1]
puts "MLP_SLICE_ROOTS slice0=$slice0_root slice1=$slice1_root"
create_pblock pb_mlp_slice0
add_cells_to_pblock [get_pblocks pb_mlp_slice0] $slice0_root
resize_pblock [get_pblocks pb_mlp_slice0] -add {SLR0}
set_property CONTAIN_ROUTING false [get_pblocks pb_mlp_slice0]
set_property EXCLUDE_PLACEMENT false [get_pblocks pb_mlp_slice0]
create_pblock pb_mlp_slice1
add_cells_to_pblock [get_pblocks pb_mlp_slice1] $slice1_root
resize_pblock [get_pblocks pb_mlp_slice1] -add {SLR2}
set_property CONTAIN_ROUTING false [get_pblocks pb_mlp_slice1]
set_property EXCLUDE_PLACEMENT false [get_pblocks pb_mlp_slice1]

place_design -directive Quick
write_checkpoint -force [file join $out post_place.dcp]
report_utilization -file [file join $out utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 9 -file [file join $out utilization_hier.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
report_timing_summary -delay_type min_max -max_paths 100 -file [file join $out timing_post_place.rpt]
report_design_analysis -congestion -file [file join $out congestion_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization.rpt]
set placed [llength [get_cells -quiet -hier -filter {PRIMITIVE_LEVEL == LEAF && IS_PLACED}]]
set unplaced [llength [get_cells -quiet -hier -filter {PRIMITIVE_LEVEL == LEAF && !IS_PLACED}]]
set slice0_dsp [get_cells -quiet -hier -filter \
 "REF_NAME == DSP48E2 && NAME =~ $slice0_root/*"]
set slice1_dsp [get_cells -quiet -hier -filter \
 "REF_NAME == DSP48E2 && NAME =~ $slice1_root/*"]
set s0_bad 0
foreach c $slice0_dsp {if {[get_property SLR_INDEX $c] != 0} {incr s0_bad}}
set s1_bad 0
foreach c $slice1_dsp {if {[get_property SLR_INDEX $c] != 2} {incr s1_bad}}
set wns [get_property SLACK [lindex [get_timing_paths -delay_type max -max_paths 1] 0]]
set whs [get_property SLACK [lindex [get_timing_paths -delay_type min -max_paths 1] 0]]
set status [expr {$unplaced==0 && $s0_bad==0 && $s1_bad==0 ?
 "PLACEMENT_FEASIBILITY_PASS" : "FAIL"}]
set f [open [file join $out summary.txt] w]
foreach {k v} [list placed_leaf_cells $placed unplaced_leaf_cells $unplaced \
 slice0_dsp [llength $slice0_dsp] slice0_wrong_slr $s0_bad \
 slice1_dsp [llength $slice1_dsp] slice1_wrong_slr $s1_bad \
 post_place_wns_ns $wns post_place_whs_ns $whs status $status] {puts $f "$k=$v"}
close $f
puts "PRODUCTION_PLACE UNPLACED=$unplaced S0_BAD=$s0_bad S1_BAD=$s1_bad WNS=$wns WHS=$whs STATUS=$status"
if {$status ne "PLACEMENT_FEASIBILITY_PASS"} {error "production placement feasibility failed"}
close_design
