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
report_utilization -hierarchical -hierarchical_depth 7 -file \
    [file join $out utilization_post_synth_hier.rpt]
report_control_sets -verbose -file [file join $out control_sets_post_synth.rpt]
report_methodology -file [file join $out methodology_post_synth.rpt]
write_checkpoint -force [file join $out post_synth.dcp]
opt_design -directive Explore
place_design -directive ExtraTimingOpt
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_place.rpt]
report_timing -delay_type max -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_setup_place_worst100.rpt]
report_timing -delay_type min -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_hold_place_worst100.rpt]
report_cdc -details -file [file join $out cdc_place.rpt]
report_route_status -file [file join $out route_status_place.rpt]
write_checkpoint -force [file join $out post_place.dcp]

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {error "No setup/hold path returned"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part \
    top hap_axi512_paired_2client_read_wrr stage POST_PLACE_DIAGNOSTIC \
    core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    wns_ns $wns whs_ns $whs lut_primitives $lut ff_primitives $ff \
    dsp48e2 $dsp uram288 $uram status DIAGNOSTIC_NOT_SIGNOFF] {
    puts $fp "$key=$value"
}
close $fp
puts "PAIRED_WRR_PLACE_PROBE WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp URAM=$uram"
