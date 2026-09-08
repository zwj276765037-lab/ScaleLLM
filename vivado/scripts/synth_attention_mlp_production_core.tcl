set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $out
file mkdir $build
if {![string match "2025.2*" [version -short]]} {error "Vivado 2025.2 required"}
create_project production_synth $build -part $part -force
set_property target_language Verilog [current_project]
set_property verilog_define {HAP_BOARD_BUILD} [get_filesets sources_1]
proc add_manifest {root manifest} {
 set fh [open $manifest r]
 foreach raw [split [read $fh] "\n"] {
  set line [string trim $raw]
  if {$line eq "" || [string index $line 0] eq "#"} {continue}
  set path [file normalize [file join $root $line]]
  if {[string match "*.list" $path]} {add_manifest $root $path;continue}
  if {![file exists $path]} {error "Missing source $path"}
  if {[llength [get_files -quiet $path]]==0} {add_files -fileset sources_1 $path}
  if {[string match "*.sv" $path]} {set_property file_type SystemVerilog [get_files $path]}
  if {[string match "*.mem" $path]} {set_property file_type {Memory Initialization Files} [get_files $path]}
 }
 close $fh
}
set production_manifest [expr {[info exists ::env(HAP_PRODUCTION_MANIFEST)] ?
 $::env(HAP_PRODUCTION_MANIFEST) :
 [file join $root vivado manifests attention_mlp_production_core_sources.list]}]
add_manifest $root [file normalize $production_manifest]
set_property top hap_attention_mlp_production_core [current_fileset]
update_compile_order -fileset sources_1
set_msg_config -id {Synth 8-4445} -new_severity ERROR
set_msg_config -id {Synth 8-3848} -new_severity ERROR
set_msg_config -id {Synth 8-6901} -new_severity ERROR
synth_design -top hap_attention_mlp_production_core -part $part -mode out_of_context \
 -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $out post_synth.dcp]
report_utilization -file [file join $out utilization_post_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 9 -file [file join $out utilization_hier_post_synth.rpt]
opt_design -directive ExploreWithRemap
write_checkpoint -force [file join $out post_opt.dcp]
report_utilization -file [file join $out utilization_post_opt.rpt]
report_utilization -hierarchical -hierarchical_depth 9 -file [file join $out utilization_hier_post_opt.rpt]
report_timing_summary -delay_type min_max -max_paths 50 -file [file join $out timing_post_opt.rpt]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set kernels [llength [get_cells -quiet -hierarchical -filter \
 {ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 || REF_NAME == hap_a8w4_slice8x16_group_s36}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter \
 {REF_NAME == DSP48E2 && NAME =~ u_compute/u_mlp/u_serial_command/u_shared_compute/*}]]
set util [report_utilization -return_string]
if {![regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util unused clb_lut]} {error "CLB LUT parse"}
if {![regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util unused clb_ff]} {error "CLB FF parse"}
set status [expr {$kernels==2 && $kernel_dsp==4096 && $dsp==6492 &&
 $uram==752 && $clb_lut<=1064016 ? "PRODUCTION_RESOURCE_PASS" : "FAIL"}]
set f [open [file join $out summary.txt] w]
foreach {k v} [list tool [version -short] part $part top hap_attention_mlp_production_core \
 a8w4_kernel_instances $kernels mlp_kernel_dsp48e2 $kernel_dsp dsp48e2 $dsp \
 clb_lut $clb_lut clb_register $clb_ff ramb36e2 $ramb36 ramb18e2 $ramb18 \
 uram288 $uram status $status] {puts $f "$k=$v"}
close $f
puts "PRODUCTION_RESOURCE DSP=$dsp LUT=$clb_lut FF=$clb_ff URAM=$uram KERNELS=$kernels KERNEL_DSP=$kernel_dsp STATUS=$status"
if {$status ne "PRODUCTION_RESOURCE_PASS"} {error "production resource gate failed"}
close_project
