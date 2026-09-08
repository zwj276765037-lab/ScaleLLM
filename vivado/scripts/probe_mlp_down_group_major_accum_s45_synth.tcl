set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part "xcvu9p-flga2104-2L-e"
set top "hap_mlp_down_group_major_accum_s45_ooc_wrapper"

file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project mlp_down_group_major_accum_s45_synth $build_dir \
    -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    mlp_down_group_major_accum_s45_sources.list]
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
add_files -fileset constrs_1 -norecurse [file join $root vivado \
    constraints mlp_down_group_major_accum_s45_ooc_150mhz.xdc]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $report_dir utilization_hierarchical.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file \
    [file join $report_dir timing_summary.rpt]

set ramb36_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set ramb18_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set uram_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set summary [open [file join $report_dir summary.txt] w]
puts $summary "tool=[version -short]"
puts $summary "part=$part"
puts $summary "lanes=128"
puts $summary "tiles=256"
puts $summary "groups=448"
puts $summary "ramb36e2=$ramb36_count"
puts $summary "ramb18e2=$ramb18_count"
puts $summary "uram288=$uram_count"
puts $summary "lut_primitives=$lut_count"
puts $summary "ff_primitives=$ff_count"
puts $summary "status=[expr {$ramb36_count > 0 && $ff_count < 100000 ? \
    "RAM_INFERRED" : "FAIL"}]"
close $summary
puts "DOWN_GROUP_MAJOR_SYNTH RAMB36=$ramb36_count RAMB18=$ramb18_count URAM=$uram_count LUT=$lut_count FF=$ff_count"
close_project
