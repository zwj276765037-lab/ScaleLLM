set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part "xcvu9p-flga2104-2L-e"
set top $::env(HAP_TOP)
set expected_dsp $::env(HAP_EXPECTED_DSP)
set manifest_name $::env(HAP_MANIFEST)

file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project kernel12_synth_probe $build_dir -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests $manifest_name]
set handle [open $manifest r]
foreach raw_line [split [read $handle] "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string index $line 0] eq "#"} { continue }
    set path [file normalize [file join $root $line]]
    if {![file exists $path]} { error "Missing source: $path" }
    add_files -fileset sources_1 $path
    set_property file_type SystemVerilog [get_files $path]
}
close $handle
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $report_dir utilization_hier_post_synth.rpt]
report_timing_summary -max_paths 20 -file \
    [file join $report_dir timing_post_synth.rpt]
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
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "top=$top"
puts $summary "stage=post_synth"
puts $summary "lut_primitives=$lut_count"
puts $summary "ff_primitives=$ff_count"
puts $summary "dsp48e2=$dsp_count"
puts $summary "expected_dsp48e2=$expected_dsp"
puts $summary "ramb36e2=$bram36_count"
puts $summary "ramb18e2=$bram18_count"
puts $summary "uram288=$uram_count"
set active_rows [expr {$top eq "hap_a8w4_slice8x12_group_s36" ? 8 : 16}]
puts $summary "active_rows=$active_rows"
puts $summary "columns=12"
puts $summary "group_size=32"
puts $summary "steady_ii=1"
puts $summary "status=$status"
close $summary
puts "KERNEL12_SYNTH_RESULT TOP=$top LUT=$lut_count FF=$ff_count DSP=$dsp_count EXPECTED=$expected_dsp STATUS=$status"
if {$status ne "PASS"} { error "V5 kernel12 structural gate failed" }
close_project
