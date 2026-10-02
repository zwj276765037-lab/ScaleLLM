set e [file dirname [file normalize [info script]]]
set id $::env(M6_CASE_ID)
set name $::env(M6_CASE_NAME)
set top $::env(M6_TOP)
set rd [file normalize $::env(M6_REPORT_DIR)]
set bd [file normalize $::env(M6_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $rd
create_project m6_$name $bd -part $part -force
set hap [file normalize [file join $e .. .. .. HAP_new]]
set files {}
if {$id==0} {
  set files [list [file join $hap rtl hap_unsigned_div_seq.sv] [file join $hap rtl hap_kv12_quantizer.sv] [file join $e rtl m6_kv12_quantizer2.sv]]
} else {
  set files [list [file join $e rtl m6_kv16_cache.sv]]
}
foreach s $files {add_files $s;set_property file_type SystemVerilog [get_files $s]}
add_files -fileset constrs_1 [file join $e constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
synth_design -top $top -part $part -mode out_of_context -flatten_hierarchy none -directive PerformanceOptimized
report_utilization -file [file join $rd utilization_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
write_checkpoint -force [file join $rd post_route.dcp]
report_utilization -file [file join $rd utilization_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 -file [file join $rd timing_post_route.rpt]
report_route_status -file [file join $rd route_status.rpt]
report_drc -file [file join $rd drc_post_route.rpt]
set sp [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hp [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $sp];set whs [get_property SLACK $hp]
set lut [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -hierarchical -filter {REF_NAME == DSP48E2}]]
set b36 [llength [get_cells -hierarchical -filter {REF_NAME == RAMB36E2}]]
set b18 [llength [get_cells -hierarchical -filter {REF_NAME == RAMB18E2}]]
set unr [llength [get_nets -hierarchical -filter {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set f [open [file join $rd summary.txt] w]
foreach {k v} [list tool [version -short] part $part case $name wns_ns $wns whs_ns $whs lut_primitives $lut ff_primitives $ff dsp48e2 $dsp ramb36e2 $b36 ramb18e2 $b18 unrouted_nets $unr] {puts $f "$k=$v"}
close $f
puts "M6_OOC_RESULT CASE=$name WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$b36 BRAM18=$b18 UNROUTED=$unr"
if {$wns<0||$whs<0||$unr!=0} {error "M6 gate"}
close_project
