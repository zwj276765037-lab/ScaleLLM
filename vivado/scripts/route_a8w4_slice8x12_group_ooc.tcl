set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part "xcvu9p-flga2104-2L-e"
set top "hap_a8w4_slice8x12_group_s36"
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project a8w4_slice8x12_group_ooc $build_dir -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    a8w4_slice8x12_group_sources.list]
set handle [open $manifest r]
foreach raw_line [split [read $handle] "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string index $line 0] eq "#"} { continue }
    set path [file normalize [file join $root $line]]
    add_files -fileset sources_1 $path
    set_property file_type SystemVerilog [get_files $path]
}
close $handle
add_files -fileset constrs_1 -norecurse [file join $root vivado \
    constraints a8w4_slice8x12_group_ooc_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
write_checkpoint -force [file join $report_dir post_synth.dcp]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
write_checkpoint -force [file join $report_dir post_place.dcp]
route_design -directive AggressiveExplore
phys_opt_design -directive Explore
write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file \
    [file join $report_dir utilization_hier_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $report_dir timing_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
report_drc -file [file join $report_dir drc_post_route.rpt]
set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 1]
set wns [get_property SLACK [lindex $setup_paths 0]]
set whs [get_property SLACK [lindex $hold_paths 0]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == CONFLICTS}]]
# Clock buffers may legally drive only the clock port in this leaf OOC.
# Any BUFG driven by functional data/control is a non-production workaround
# and makes the timing artifact ineligible for a clean PASS.
set data_bufg_count 0
foreach bufg [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set input_pins [get_pins -quiet -of_objects $bufg -filter \
        {DIRECTION == IN && (REF_PIN_NAME == I || REF_PIN_NAME == I0 ||
         REF_PIN_NAME == I1)}]
    foreach pin $input_pins {
        set driver_ports [get_ports -quiet -of_objects \
            [get_nets -quiet -of_objects $pin]]
        if {[llength $driver_ports] > 0 &&
            [llength [filter $driver_ports {NAME == clk}]] == 0} {
            incr data_bufg_count
            break
        }
    }
}
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $dsp_count == 1536 && $data_bufg_count == 0 ?
    "PASS" : "FAIL"}]
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "clock_mhz=150"
puts $summary "wns_ns=$wns"
puts $summary "whs_ns=$whs"
puts $summary "lut_primitives=$lut_count"
puts $summary "ff_primitives=$ff_count"
puts $summary "dsp48e2=$dsp_count"
puts $summary "unrouted_nets=$unrouted"
puts $summary "drc_errors=$drc_errors"
puts $summary "data_bufg_count=$data_bufg_count"
puts $summary "active_rows=8"
puts $summary "columns=12"
puts $summary "group_size=32"
puts $summary "steady_ii=1"
puts $summary "useful_tops=0.9216"
puts $summary "status=$status"
close $summary
puts "A8W4_SLICE8X12_RESULT WNS=$wns WHS=$whs LUT=$lut_count FF=$ff_count DSP=$dsp_count UNROUTED=$unrouted DRC=$drc_errors DATA_BUFG=$data_bufg_count STATUS=$status"
if {$status ne "PASS"} { error "A8W4 slice8x12 OOC gate failed" }
close_project
