set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_attention_mlp_resource_top
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project attention_mlp_resource_top $build_dir -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests attention_mlp_resource_top_sources.list]
set fh [open $manifest r]
foreach raw [split [read $fh] "\n"] {
    set line [string trim $raw]
    if {$line eq "" || [string index $line 0] eq "#"} { continue }
    set path [file normalize [file join $root $line]]
    if {![file exists $path]} { error "Missing source: $path" }
    add_files -fileset sources_1 $path
    if {[string match "*.mem" $path]} {
        set_property file_type {Memory Initialization Files} [get_files $path]
    } elseif {[string match "*.sv" $path]} {
        set_property file_type SystemVerilog [get_files $path]
    }
}
close $fh
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sources_1]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $report_dir utilization_hier_post_synth.rpt]

# Resource-only opt is the gate before any place/route attempt.
opt_design -directive ExploreWithRemap
write_checkpoint -force [file join $report_dir post_opt.dcp]
report_utilization -file [file join $report_dir utilization_post_opt.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $report_dir utilization_hier_post_opt.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_post_opt.rpt]

set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
    {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || \
     REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_mlp/u_serial_command/u_shared_compute/*}]]
set util [report_utilization -return_string]
if {![regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util unused clb_lut]} {
    error "Unable to parse CLB LUT count"
}
if {![regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util unused clb_ff]} {
    error "Unable to parse CLB register count"
}
set status [expr {$kernels == 2 && $kernel_dsp == 4096 &&
    $dsp <= 6498 && $clb_lut <= 1064016 && $uram >= 80 ?
    "INTEGRATED_RESOURCE_PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=$part"
puts $fp "top=$top"
puts $fp "probe_only=1"
puts $fp "a8w4_kernel_instances=$kernels"
puts $fp "mlp_kernel_dsp48e2=$kernel_dsp"
puts $fp "dsp48e2=$dsp"
puts $fp "clb_lut=$clb_lut"
puts $fp "clb_register=$clb_ff"
puts $fp "ramb36e2=$ramb36"
puts $fp "ramb18e2=$ramb18"
puts $fp "uram288=$uram"
puts $fp "status=$status"
close $fp
puts "ATTENTION_MLP_RESOURCE DSP=$dsp LUT=$clb_lut FF=$clb_ff BRAM36=$ramb36 BRAM18=$ramb18 URAM=$uram KERNELS=$kernels KERNEL_DSP=$kernel_dsp STATUS=$status"
if {$status ne "INTEGRATED_RESOURCE_PASS"} {
    error "Attention+MLP integrated resource-only gate failed"
}
close_project
