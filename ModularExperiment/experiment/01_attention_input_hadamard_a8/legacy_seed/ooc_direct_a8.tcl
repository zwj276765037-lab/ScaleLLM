set experiment_dir [file dirname [file normalize [info script]]]
set project_root [file normalize [file join $experiment_dir ../..]]
set hap_root [file normalize [file join $project_root ../HAP_new]]
set report_dir [file normalize $::env(M1_REPORT_DIR)]
set build_dir [file normalize $::env(M1_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_attention_frontend_direct_a8_8row

file mkdir $report_dir
file mkdir $build_dir
create_project m1_direct_a8_ooc $build_dir -part $part -force
foreach source [list \
    [file join $hap_root rtl hap_fixbit_v2_pkg.sv] \
    [file join $hap_root rtl hap_u16_div_u8_seq.sv] \
    [file join $hap_root rtl hap_robust_a8_quantizer.sv] \
    [file join $hap_root rtl hap_activation_cache_8row.sv] \
    [file join $experiment_dir rtl hap_attention_frontend_direct_a8_8row.sv]] {
    add_files -fileset sources_1 $source
    set_property file_type SystemVerilog [get_files $source]
}
add_files -fileset constrs_1 -norecurse \
    [file join $experiment_dir constraints clock_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_timing_summary -max_paths 20 \
    -file [file join $report_dir timing_post_synth.rpt]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 5 \
    -file [file join $report_dir utilization_hier_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 50 \
    -file [file join $report_dir timing_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
report_drc -file [file join $report_dir drc_post_route.rpt]

set setup_path [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} { error "M1 timing paths missing" }
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
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "clock_mhz=149.9925"
puts $summary "wns_ns=$wns"
puts $summary "whs_ns=$whs"
puts $summary "lut_primitives=$lut"
puts $summary "ff_primitives=$ff"
puts $summary "dsp48e2=$dsp"
puts $summary "bram36e2=$bram36"
puts $summary "bram18e2=$bram18"
puts $summary "uram288=$uram"
puts $summary "unrouted_nets=$unrouted"
close $summary
puts "M1_DIRECT_A8_OOC_RESULT: WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$bram36 BRAM18=$bram18 URAM=$uram UNROUTED=$unrouted"
if {$wns < 0.0 || $whs < 0.0 || $unrouted != 0} {
    error "M1 direct-A8 routed gate failed"
}
close_project

