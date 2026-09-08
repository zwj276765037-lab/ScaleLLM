set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl integration \
    hap_axi512_paired_2client_read_wrr.sv]
read_xdc [file join $root vivado constraints \
    axi512_paired_2client_read_wrr_ooc_150_300_300.xdc]
synth_design -top hap_axi512_paired_2client_read_wrr -part $part \
    -mode out_of_context -flatten_hierarchy none -directive PerformanceOptimized
opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_setup_worst100.rpt]
report_timing -delay_type min -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_hold_worst100.rpt]
report_utilization -hierarchical -hierarchical_depth 7 -file \
    [file join $out utilization_hier.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction.rpt]
report_methodology -file [file join $out methodology.rpt]
report_design_analysis -congestion -file [file join $out congestion.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {error "No setup/hold path returned"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set unrouted [llength [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set cdc_fh [open [file join $out cdc.rpt] r]
set cdc_text [read $cdc_fh]
close $cdc_fh
set cdc_critical 0
foreach {whole count} [regexp -all -inline \
        {Critical[[:space:]]+([1-9][0-9]*)} $cdc_text] {
    incr cdc_critical $count
}
set unconstrained 0
foreach line [split [report_timing_summary -return_string] "\n"] {
    if {[regexp -nocase {Unconstrained Paths[[:space:]]+([1-9][0-9]*)} $line -> count]} {
        incr unconstrained $count
    }
}
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $drc_errors == 0 && $cdc_critical == 0 && $unconstrained == 0 &&
    $dsp == 0 && $uram == 0 ? "OOC_POST_ROUTE_PASS" : "OOC_POST_ROUTE_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part \
    top hap_axi512_paired_2client_read_wrr core_clock_mhz 150 \
    ddr0_clock_mhz 300 ddr1_clock_mhz 300 core_io_budget_ns 1.000 \
    ddr_io_budget_ns 0.800 wns_ns $wns whs_ns $whs \
    lut_primitives $lut ff_primitives $ff ramb36e2 $ramb36 ramb18e2 $ramb18 \
    dsp48e2 $dsp uram288 $uram unrouted_nets $unrouted drc_errors $drc_errors \
    cdc_critical $cdc_critical unconstrained_paths $unconstrained status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "PAIRED_WRR_OOC WNS=$wns WHS=$whs UNROUTED=$unrouted DRC=$drc_errors CDC=$cdc_critical DSP=$dsp URAM=$uram STATUS=$status"
if {$status ne "OOC_POST_ROUTE_PASS"} {
    error "Paired AXI512 arbiter OOC acceptance failed"
}
