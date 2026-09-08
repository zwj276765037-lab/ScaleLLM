set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set checkpoint [file normalize $::env(HAP_SYNTH_DCP)]
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
open_checkpoint $checkpoint
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_shared_compute/*}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
    {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || \
     REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set luts [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ffs [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set status [expr {$dsp == 4172 && $kernel_dsp == 4096 && $kernels == 2 &&
    $ramb36 == 360 && $ramb18 == 2 ? "RESOURCE_SHAPE_PASS" : "FAIL"}]
set fp [open [file join $report_dir resource_audit.txt] w]
puts $fp "tool=[version -short]"
puts $fp "source_checkpoint=$checkpoint"
puts $fp "a8w4_kernel_instances=$kernels"
puts $fp "shared_kernel_dsp48e2=$kernel_dsp"
puts $fp "top_dsp48e2=$dsp"
puts $fp "ramb36e2=$ramb36"
puts $fp "ramb18e2=$ramb18"
puts $fp "lut_primitives=$luts"
puts $fp "ff_primitives=$ffs"
puts $fp "status=$status"
close $fp
puts "SERIAL_MLP_RESOURCE_AUDIT kernels=$kernels kernelDSP=$kernel_dsp topDSP=$dsp RAMB36=$ramb36 RAMB18=$ramb18 STATUS=$status"
if {$status ne "RESOURCE_SHAPE_PASS"} { error "MLP resource shape audit failed" }
close_design
