set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set dcp [file join $report_dir post_synth.dcp]
if {![file exists $dcp]} { error "Missing synthesized checkpoint $dcp" }
open_checkpoint $dcp

set dsp_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set lut_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set bram36_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set bram18_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set uram_total [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set branch0_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_branch0/*}]]
set branch1_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_branch1/*}]]
set branch0_kernel [llength [get_cells -quiet u_branch0/u_kernel]]
set branch1_kernel [llength [get_cells -quiet u_branch1/u_kernel]]
set branch0_accum [llength [get_cells -quiet u_branch0/u_accum]]
set branch1_accum [llength [get_cells -quiet u_branch1/u_accum]]
set outside_dsp [expr {$dsp_total-$branch0_dsp-$branch1_dsp}]
set status [expr {
    $dsp_total == 3072 &&
    $branch0_dsp == 1536 && $branch1_dsp == 1536 &&
    $outside_dsp == 0 &&
    $branch0_kernel == 1 && $branch1_kernel == 1 &&
    $branch0_accum == 1 && $branch1_accum == 1 &&
    $bram36_total == 0 && $bram18_total == 0 &&
    $uram_total == 0 ? "PASS" : "FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
foreach {key value} [list \
    tool [version -short] part xcvu9p-flga2104-2L-e \
    top hap_mlp_gate_up_dual_local_accum16x12_s43 stage post_synth \
    lut_primitives $lut_total ff_primitives $ff_total \
    dsp48e2 $dsp_total expected_dsp48e2 3072 \
    branch0_dsp48e2 $branch0_dsp branch1_dsp48e2 $branch1_dsp \
    outside_branch_dsp48e2 $outside_dsp \
    branch0_kernel_instances $branch0_kernel \
    branch1_kernel_instances $branch1_kernel \
    branch0_accum_instances $branch0_accum \
    branch1_accum_instances $branch1_accum \
    ramb36e2 $bram36_total ramb18e2 $bram18_total \
    uram288 $uram_total local_s36_width_per_branch_bits 3456 \
    joined_s24_width_bits 4608 formal_groups 128 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "GATE_LOCAL12_DCP_AUDIT DSP=$dsp_total BRANCH=$branch0_dsp/$branch1_dsp BRAM=$bram36_total/$bram18_total URAM=$uram_total STATUS=$status"
if {$status ne "PASS"} {
    error "V5 dual-local gate S43 post-synth DCP audit failed"
}
close_design
