set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
create_project a8w4_slice8x16_group_regfifo_synth_probe $build_dir \
    -part xcvu9p-flga2104-2L-e -force
set manifest [file join $root vivado manifests \
    a8w4_slice8x16_group_sources.list]
set handle [open $manifest r]
foreach raw_line [split [read $handle] "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string index $line 0] eq "#"} { continue }
    set path [file normalize [file join $root $line]]
    add_files -fileset sources_1 $path
    if {[string match "*.sv" $path]} {
        set_property file_type SystemVerilog [get_files $path]
    }
}
close $handle
synth_design -top hap_a8w4_slice8x16_group_s36 \
    -part xcvu9p-flga2104-2L-e -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
write_checkpoint -force [file join $report_dir post_synth.dcp]
set ram32_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ RAM32*}]]
set guard_ram_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ RAM32* && NAME =~ *guard*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set status [expr {$guard_ram_count == 0 && $dsp_count == 2048 ?
    "PASS" : "FAIL"}]
set fp [open [file join $report_dir summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "ram32_primitives=$ram32_count"
puts $fp "guard_ram32_primitives=$guard_ram_count"
puts $fp "ff_primitives=$ff_count"
puts $fp "dsp48e2=$dsp_count"
puts $fp "status=$status"
close $fp
puts "REGFIFO_SYNTH RAM32=$ram32_count GUARD_RAM32=$guard_ram_count FF=$ff_count DSP=$dsp_count STATUS=$status"
if {$status ne "PASS"} { error "register guard FIFO inference gate failed" }
close_project
