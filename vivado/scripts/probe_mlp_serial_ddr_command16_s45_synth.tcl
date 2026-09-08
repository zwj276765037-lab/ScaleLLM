set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part "xcvu9p-flga2104-2L-e"
set top "hap_mlp_serial_ddr_command16_s45"
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project mlp_serial_ddr_command16_s45_synth $build_dir \
    -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    mlp_serial_ddr_command16_s45_sources.list]
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
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $report_dir utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_summary.rpt]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2 && NAME =~ u_shared_compute/*}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
    {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || \
     REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set luts [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ffs [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "formal_gate_tiles=1792"
puts $summary "formal_down_groups=448"
puts $summary "formal_down_tiles=256"
puts $summary "a8w4_kernel_instances=$kernels"
puts $summary "dsp48e2=$dsp"
puts $summary "shared_kernel_dsp48e2=$kernel_dsp"
puts $summary "ramb36e2=$ramb36"
puts $summary "ramb18e2=$ramb18"
puts $summary "uram288=$uram"
puts $summary "lut_primitives=$luts"
puts $summary "ff_primitives=$ffs"
puts $summary "status=[expr {$dsp == 4172 && $kernel_dsp == 4096 && \
    $kernels == 2 && \
    ($ramb36 + $ramb18) > 0 ? "RESOURCE_SHAPE_PASS" : "FAIL"}]"
close $summary
puts "SERIAL_MLP_SYNTH kernels=$kernels DSP=$dsp RAMB36=$ramb36 RAMB18=$ramb18 URAM=$uram LUT=$luts FF=$ffs"
close_project
