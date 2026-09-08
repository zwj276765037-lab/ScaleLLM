set checkpoint [file normalize $::env(HAP_CHECKPOINT)]
set output [file normalize $::env(HAP_OUTPUT)]
if {![file exists $checkpoint]} { error "Missing checkpoint: $checkpoint" }
open_checkpoint $checkpoint
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
set attention_clb_lut 314203
set attention_ff 321770
set attention_dsp 2302
set combined_clb_lut [expr {$clb_lut + $attention_clb_lut}]
set combined_ff [expr {$ffs + $attention_ff}]
set combined_dsp [expr {$dsp + $attention_dsp}]
set shape_status [expr {$kernels == 2 && $kernel_dsp == 4096 &&
    $input_dsp == 16 && $dsp == 4188 &&
    ($ramb36 + $ramb18 + $uram) > 0 ? "RESOURCE_SHAPE_PASS" : "FAIL"}]
set headroom_status [expr {$combined_clb_lut <= 1064016 &&
    $combined_dsp <= 6498 ? "STATIC_HEADROOM_PASS" :
    "STATIC_HEADROOM_FAIL"}]
set handle [open $output w]
puts $handle "checkpoint=$checkpoint"
puts $handle "a8w4_kernel_instances=$kernels"
puts $handle "dsp48e2=$dsp"
puts $handle "shared_kernel_dsp48e2=$kernel_dsp"
puts $handle "input_frontend_dsp48e2=$input_dsp"
puts $handle "clb_lut=$clb_lut"
puts $handle "lut_primitives=$luts"
puts $handle "ff_primitives=$ffs"
puts $handle "ramb36e2=$ramb36"
puts $handle "ramb18e2=$ramb18"
puts $handle "uram288=$uram"
puts $handle "shape_status=$shape_status"
puts $handle "combined_static_clb_lut=$combined_clb_lut"
puts $handle "combined_static_ff=$combined_ff"
puts $handle "combined_static_dsp=$combined_dsp"
puts $handle "headroom_status=$headroom_status"
close $handle
if {$shape_status ne "RESOURCE_SHAPE_PASS"} {
    error "Fold4 full MLP resource-shape audit failed"
}
close_design
