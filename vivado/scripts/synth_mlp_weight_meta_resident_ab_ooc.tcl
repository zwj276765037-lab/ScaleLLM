set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $report_dir
file mkdir $build_dir

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
set_param general.maxThreads $jobs

create_project mlp_weight_meta_resident_ab_ooc $build_dir -part $part -force
add_files [file join $root rtl mlp hap_mlp_weight_meta_resident_ab.sv]
set_property file_type SystemVerilog [get_files hap_mlp_weight_meta_resident_ab.sv]
add_files -fileset constrs_1 [file join $root vivado constraints \
    mlp_weight_meta_resident_ab_ooc_150mhz.xdc]
set_property top hap_mlp_weight_meta_resident_ab [current_fileset]
synth_design -top hap_mlp_weight_meta_resident_ab -part $part \
    -mode out_of_context -flatten_hierarchy none -directive PerformanceOptimized
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -hierarchical -hierarchical_depth 4 -file \
    [file join $report_dir utilization.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_summary.rpt]

set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set luts [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ffs [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set metadata_leaves [get_cells -quiet -hierarchical -filter {
    REF_NAME == hap_mlp_weight_meta_uram_leaf ||
    ORIG_REF_NAME == hap_mlp_weight_meta_uram_leaf
}]
set local_wr_en_ffs [get_cells -quiet -hierarchical -filter {
    NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*
}]
set local_wr_addr_ffs [get_cells -quiet -hierarchical -filter {
    NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*
}]
set local_wr_data_ffs [get_cells -quiet -hierarchical -filter {
    NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*
}]
set protected_local_write_ffs 0
foreach cell [concat $local_wr_en_ffs $local_wr_addr_ffs \
        $local_wr_data_ffs] {
    set protected [string tolower [get_property DONT_TOUCH $cell]]
    if {$protected eq "1" || $protected eq "true" || $protected eq "yes"} {
        incr protected_local_write_ffs
    }
}
set local_write_ff_count [expr {[llength $local_wr_en_ffs] +
    [llength $local_wr_addr_ffs] + [llength $local_wr_data_ffs]}]
set local_write_boundary_ok [expr {[llength $metadata_leaves] == 4 &&
    [llength $local_wr_en_ffs] == 4 &&
    [llength $local_wr_addr_ffs] == 70 &&
    [llength $local_wr_data_ffs] == 896 &&
    $protected_local_write_ffs == $local_write_ff_count}]
set gate0_capture_ffs [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD* && NAME =~ u_gate_bank0/rsp_fifo_slot*
}]]
set gate1_capture_ffs [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD* && NAME =~ u_gate_bank1/rsp_fifo_slot*
}]]
set down0_capture_ffs [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD* && NAME =~ u_down_bank0/rsp_fifo_slot*
}]]
set down1_capture_ffs [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD* && NAME =~ u_down_bank1/rsp_fifo_slot*
}]]
set response_lutram [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ RAMD* || REF_NAME =~ RAMS* || REF_NAME =~ RAM32M* ||
    REF_NAME =~ RAM64M*
}]]
set status [expr {$uram == 672 && $dsp == 0 && $luts <= 10000 &&
    $ffs <= 10000 && $gate0_capture_ffs == 448 &&
    $gate1_capture_ffs == 448 && $down0_capture_ffs == 448 &&
    $down1_capture_ffs == 448 && $response_lutram == 0 &&
    $local_write_boundary_ok ?
    "METADATA_SHAPE_PASS" : "FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=$part"
puts $fp "top=hap_mlp_weight_meta_resident_ab"
puts $fp "jobs=$jobs"
puts $fp "gate_records_per_bank=229376"
puts $fp "down_records_per_bank=114688"
puts $fp "record_width=224"
puts $fp "bank_count=2"
puts $fp "uram288=$uram"
puts $fp "dsp48e2=$dsp"
puts $fp "lut_primitives=$luts"
puts $fp "ff_primitives=$ffs"
puts $fp "gate0_capture_ff=$gate0_capture_ffs"
puts $fp "gate1_capture_ff=$gate1_capture_ffs"
puts $fp "down0_capture_ff=$down0_capture_ffs"
puts $fp "down1_capture_ff=$down1_capture_ffs"
puts $fp "response_lutram=$response_lutram"
puts $fp "metadata_leaf_instances=[llength $metadata_leaves]"
puts $fp "local_wr_en_ff=[llength $local_wr_en_ffs]"
puts $fp "local_wr_addr_ff=[llength $local_wr_addr_ffs]"
puts $fp "local_wr_data_ff=[llength $local_wr_data_ffs]"
puts $fp "protected_local_write_ff=$protected_local_write_ffs"
puts $fp "local_write_boundary_ok=$local_write_boundary_ok"
puts $fp "status=$status"
close $fp

if {$status ne "METADATA_SHAPE_PASS"} {
    error "MLP metadata A/B resident synthesis gate failed"
}
close_project
