set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_AUDIT_DIR)]
set expect_dsp $::env(HAP_EXPECT_DSP)
set expect_uram $::env(HAP_EXPECT_URAM)
set expect_ramb36 $::env(HAP_EXPECT_RAMB36)
set expect_ramb18 $::env(HAP_EXPECT_RAMB18)
set expect_kernels $::env(HAP_EXPECT_KERNELS)
set expect_kernel_dsp $::env(HAP_EXPECT_KERNEL_DSP)
set expect_lut $::env(HAP_EXPECT_LUT)
set expect_ff $::env(HAP_EXPECT_FF)
file mkdir $out
if {![string match "2025.2*" [version -short]]} {error "Vivado 2025.2 required"}
open_checkpoint $dcp
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
 {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
 {REF_NAME == DSP48E2 && NAME =~ u_compute/u_mlp/u_serial_command/u_shared_compute/*}]]
set util [report_utilization -return_string]
regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util unused clb_lut
regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util unused clb_ff
set status [expr {$dsp==$expect_dsp && $uram==$expect_uram &&
 $ramb36==$expect_ramb36 && $ramb18==$expect_ramb18 &&
 $kernels==$expect_kernels && $kernel_dsp==$expect_kernel_dsp &&
 $clb_lut==$expect_lut && $clb_ff==$expect_ff ?
 "DCP_EXACT_AUDIT_PASS" : "FAIL"}]
set f [open [file join $out audit.txt] w]
foreach {k v} [list dcp $dcp dsp48e2 $dsp uram288 $uram ramb36e2 $ramb36 \
 ramb18e2 $ramb18 a8w4_kernel_instances $kernels mlp_kernel_dsp48e2 $kernel_dsp \
 clb_lut $clb_lut clb_register $clb_ff status $status] {puts $f "$k=$v"}
close $f
puts "PRODUCTION_DCP_AUDIT DSP=$dsp URAM=$uram LUT=$clb_lut FF=$clb_ff STATUS=$status"
if {$status ne "DCP_EXACT_AUDIT_PASS"} {error "production DCP exact audit failed"}
close_design
