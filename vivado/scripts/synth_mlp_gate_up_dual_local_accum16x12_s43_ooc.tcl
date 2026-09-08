set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_gate_up_dual_local_accum16x12_s43

file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

create_project gate_local12_synth $build_dir -part $part -force
set_property target_language Verilog [current_project]
set manifest [file join $root vivado manifests \
    mlp_gate_up_dual_local_accum16x12_s43_sources.list]
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
report_utilization -hierarchical -hierarchical_depth 14 \
    -file [file join $report_dir utilization_hier_post_synth.rpt]
report_timing_summary -max_paths 20 \
    -file [file join $report_dir timing_post_synth.rpt]

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

set branch0 [get_cells -quiet u_branch0]
set branch1 [get_cells -quiet u_branch1]
set branch0_kernel [get_cells -quiet u_branch0/u_kernel]
set branch1_kernel [get_cells -quiet u_branch1/u_kernel]
set branch0_accum [get_cells -quiet u_branch0/u_accum]
set branch1_accum [get_cells -quiet u_branch1/u_accum]
set branch0_dsp [llength [get_cells -quiet -hierarchical \
    -filter {REF_NAME == DSP48E2 && NAME =~ u_branch0/*}]]
set branch1_dsp [llength [get_cells -quiet -hierarchical \
    -filter {REF_NAME == DSP48E2 && NAME =~ u_branch1/*}]]
set outside_dsp [expr {$dsp_total-$branch0_dsp-$branch1_dsp}]

# Each branch must retain both the kernel and local accumulator hierarchy.
# This structural gate prevents an accidental return to one central 192-lane
# accumulator even though completed numerical results would still match.
set hierarchy_ok [expr {
    [llength $branch0] == 1 && [llength $branch1] == 1 &&
    [llength $branch0_kernel] == 1 &&
    [llength $branch1_kernel] == 1 &&
    [llength $branch0_accum] == 1 &&
    [llength $branch1_accum] == 1}]
set resource_ok [expr {
    $dsp_total == 3072 &&
    $branch0_dsp == 1536 && $branch1_dsp == 1536 &&
    $outside_dsp == 0 &&
    $bram36_total == 0 && $bram18_total == 0 &&
    $uram_total == 0}]
set status [expr {$hierarchy_ok && $resource_ok ? "PASS" : "FAIL"}]

set summary [open [file join $report_dir summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part top $top stage post_synth \
    lut_primitives $lut_total ff_primitives $ff_total \
    dsp48e2 $dsp_total expected_dsp48e2 3072 \
    branch0_dsp48e2 $branch0_dsp branch1_dsp48e2 $branch1_dsp \
    outside_branch_dsp48e2 $outside_dsp \
    branch0_kernel_instances [llength $branch0_kernel] \
    branch1_kernel_instances [llength $branch1_kernel] \
    branch0_accum_instances [llength $branch0_accum] \
    branch1_accum_instances [llength $branch1_accum] \
    ramb36e2 $bram36_total ramb18e2 $bram18_total \
    uram288 $uram_total local_s36_width_per_branch_bits 3456 \
    joined_s24_width_bits 4608 formal_groups 128 \
    hierarchy_ok $hierarchy_ok resource_ok $resource_ok status $status] {
    puts $summary "$key=$value"
}
close $summary

puts "GATE_LOCAL12_SYNTH_RESULT DSP=$dsp_total BRANCH=$branch0_dsp/$branch1_dsp BRAM=$bram36_total/$bram18_total URAM=$uram_total HIER=$hierarchy_ok STATUS=$status"
if {$status ne "PASS"} {
    error "V5 dual-local gate S43 structural gate failed"
}
close_project
