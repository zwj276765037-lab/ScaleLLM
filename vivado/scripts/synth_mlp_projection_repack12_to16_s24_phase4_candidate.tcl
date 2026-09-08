set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_projection_repack12_to16_s24_phase4_candidate
file mkdir $out
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_projection_repack12_to16_s24_phase4_candidate.sv]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high

report_utilization -hierarchical -hierarchical_depth 4 \
    -file [file join $out utilization_hierarchical.rpt]
report_utilization -file [file join $out utilization.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set bram [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB*}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set bufg [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}]]
set status [expr {$lut < 12000 && $dsp == 0 && $bram == 0 &&
    $uram == 0 && $bufg == 0 ? "PHASE4_SYNTH_RESOURCE_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    rows 16 matrices 2 lut_primitives $lut ff_primitives $ff \
    dsp48e2 $dsp bram_primitives $bram uram288 $uram bufg $bufg \
    baseline_lut_primitives 27693 baseline_ff_primitives 15477 \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "PHASE4_SYNTH LUT=$lut FF=$ff DSP=$dsp BRAM=$bram URAM=$uram BUFG=$bufg STATUS=$status"
if {$status ne "PHASE4_SYNTH_RESOURCE_PASS"} {
    error "Run 0124 phase4 resource target failed"
}
close_project
