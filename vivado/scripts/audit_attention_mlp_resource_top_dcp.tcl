set checkpoint [file normalize $::env(HAP_CHECKPOINT)]
set output [file normalize $::env(HAP_OUTPUT)]

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
if {![file exists $checkpoint]} {
    error "Missing checkpoint: $checkpoint"
}

open_checkpoint $checkpoint

set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_mlp/u_serial_command/u_shared_compute/*}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
    {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || \
     REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]

set util [report_utilization -return_string]
if {![regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util unused clb_lut]} {
    error "Unable to parse CLB LUT count"
}
if {![regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util unused clb_ff]} {
    error "Unable to parse CLB register count"
}

# These are exact assertions for the signed-pack2 Run 0028 post-opt DCP.  A
# later architecture must deliberately update the golden values instead of
# silently accepting resource drift.
set exact_status [expr {
    $kernels == 2 &&
    $kernel_dsp == 4096 &&
    $dsp == 6492 &&
    $clb_lut == 884328 &&
    $clb_ff == 952586 &&
    $ramb36 == 659 &&
    $ramb18 == 24 &&
    $uram == 80 ? "DCP_EXACT_AUDIT_PASS" : "FAIL"
}]
set gate_status [expr {
    $kernels == 2 &&
    $kernel_dsp == 4096 &&
    $dsp <= 6498 &&
    $clb_lut <= 1064016 &&
    $uram >= 80 ? "INTEGRATED_RESOURCE_PASS" : "FAIL"
}]

set handle [open $output w]
puts $handle "tool=[version -short]"
puts $handle "checkpoint=$checkpoint"
puts $handle "top=[get_property TOP [current_design]]"
puts $handle "a8w4_kernel_instances=$kernels"
puts $handle "mlp_kernel_dsp48e2=$kernel_dsp"
puts $handle "dsp48e2=$dsp"
puts $handle "clb_lut=$clb_lut"
puts $handle "clb_register=$clb_ff"
puts $handle "ramb36e2=$ramb36"
puts $handle "ramb18e2=$ramb18"
puts $handle "uram288=$uram"
puts $handle "exact_status=$exact_status"
puts $handle "gate_status=$gate_status"
close $handle

puts "ATTENTION_MLP_DCP_AUDIT DSP=$dsp LUT=$clb_lut FF=$clb_ff BRAM36=$ramb36 BRAM18=$ramb18 URAM=$uram KERNELS=$kernels KERNEL_DSP=$kernel_dsp EXACT=$exact_status GATE=$gate_status"
if {$exact_status ne "DCP_EXACT_AUDIT_PASS" ||
    $gate_status ne "INTEGRATED_RESOURCE_PASS"} {
    error "Attention+MLP integrated post-opt DCP audit failed"
}
close_design
