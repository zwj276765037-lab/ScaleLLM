set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part "xcvu9p-flga2104-2L-e"
set top "hap_mlp_full_command16_s45"
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project mlp_full_command16_s45_synth $build_dir -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    mlp_full_command16_s45_sources.list]
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
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 10 -file \
    [file join $report_dir utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_summary.rpt]

set dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_serial_command/u_shared_compute/*}]]
set input_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_input_frontend/*}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
    {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || \
     REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set luts [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ffs [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set util [report_utilization -return_string]
if {![regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util unused clb_lut]} {
    error "Unable to parse CLB LUT count"
}
set shape_status [expr {$kernels == 2 && $kernel_dsp == 4096 &&
    $input_dsp == 16 && $dsp == 4188 &&
    ($ramb36 + $ramb18 + $uram) > 0 ? "RESOURCE_SHAPE_PASS" : "FAIL"}]
# Attention v3.1 signed-off board figures.  This is deliberately a static
# upper-bound gate, not a replacement for resource-only full-top opt_design.
set attention_clb_lut 314203
set attention_ff 321770
set attention_dsp 2302
set combined_clb_lut [expr {$clb_lut + $attention_clb_lut}]
set combined_ff [expr {$ffs + $attention_ff}]
set combined_dsp [expr {$dsp + $attention_dsp}]
set headroom_status [expr {$combined_clb_lut <= 1064016 &&
    $combined_dsp <= 6498 ? "STATIC_HEADROOM_PASS" :
    "STATIC_HEADROOM_FAIL"}]
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "formal_hidden_groups=128"
puts $summary "formal_gate_tiles=1792"
puts $summary "formal_down_groups=448"
puts $summary "formal_down_tiles=256"
puts $summary "a8w4_kernel_instances=$kernels"
puts $summary "dsp48e2=$dsp"
puts $summary "shared_kernel_dsp48e2=$kernel_dsp"
puts $summary "input_frontend_dsp48e2=$input_dsp"
puts $summary "ramb36e2=$ramb36"
puts $summary "ramb18e2=$ramb18"
puts $summary "uram288=$uram"
puts $summary "lut_primitives=$luts"
puts $summary "clb_lut=$clb_lut"
puts $summary "ff_primitives=$ffs"
puts $summary "shape_status=$shape_status"
puts $summary "attention_static_clb_lut=$attention_clb_lut"
puts $summary "attention_static_ff=$attention_ff"
puts $summary "attention_static_dsp=$attention_dsp"
puts $summary "combined_static_clb_lut=$combined_clb_lut"
puts $summary "combined_static_ff=$combined_ff"
puts $summary "combined_static_dsp=$combined_dsp"
puts $summary "headroom_status=$headroom_status"
close $summary
puts "FULL_MLP_SYNTH kernels=$kernels DSP=$dsp INPUT_DSP=$input_dsp RAMB36=$ramb36 RAMB18=$ramb18 URAM=$uram LUT=$luts FF=$ffs SHAPE=$shape_status HEADROOM=$headroom_status"
if {$shape_status ne "RESOURCE_SHAPE_PASS"} {
    error "Full MLP formal-shape resource gate failed"
}
if {$headroom_status ne "STATIC_HEADROOM_PASS"} {
    error "Attention plus full MLP static headroom gate failed"
}
close_project
