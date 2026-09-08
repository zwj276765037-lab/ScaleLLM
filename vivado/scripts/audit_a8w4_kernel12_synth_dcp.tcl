set dcp [file normalize $::env(HAP_SOURCE_DCP)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set top $::env(HAP_TOP)
set expected_dsp $::env(HAP_EXPECTED_DSP)
file mkdir $report_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
open_checkpoint $dcp
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set bram36_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set bram18_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set uram_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set status [expr {$dsp_count == $expected_dsp && $uram_count == 0 ?
    "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "top=$top"
puts $fp "stage=post_synth_dcp_audit"
puts $fp "source_dcp=$dcp"
puts $fp "lut_primitives=$lut_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "dsp48e2=$dsp_count"
puts $fp "expected_dsp48e2=$expected_dsp"
puts $fp "ramb36e2=$bram36_count"
puts $fp "ramb18e2=$bram18_count"
puts $fp "uram288=$uram_count"
puts $fp "status=$status"
close $fp
puts "KERNEL12_DCP_AUDIT TOP=$top DSP=$dsp_count EXPECTED=$expected_dsp STATUS=$status"
if {$status ne "PASS"} {error "kernel12 DCP audit failed"}
close_design

