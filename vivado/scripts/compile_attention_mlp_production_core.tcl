set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set out [file normalize $::env(HAP_COMPILE_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $out
if {![string match "2025.2*" [version -short]]} {
 error "Vivado 2025.2 required, got [version -short]"
}
create_project production_compile $out -part $part -force
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
 -rtl -flatten_hierarchy none
set f [open [file join $out summary.txt] w]
puts $f "tool=[version -short]"
puts $f "part=$part"
puts $f "top=hap_attention_mlp_production_core"
puts $f "status=ELABORATION_PASS"
close $f
puts "PRODUCTION_CORE_ELABORATION_PASS"
close_project
