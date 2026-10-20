set report $::env(HAP_REPORT_DIR)
set top [lindex $argv 0]
set overlay [lindex $argv 1]
set_param general.maxThreads 8
create_project type_probe [file join $report native_project] -part xcvu9p-flga2104-2L-e
add_files $top
set_property TOP type_probe [current_fileset]
add_files -fileset constrs_1 $overlay
set f [get_files $overlay]
puts "NATIVE_CONSTRAINT_FILE_TYPE_BEFORE=[get_property FILE_TYPE $f]"
if {![catch {list_property_value FILE_TYPE $f} allowed]} {puts "NATIVE_ALLOWED_CONSTRAINT_FILE_TYPES=$allowed"}
set_property FILE_TYPE Tcl $f
puts "NATIVE_CONSTRAINT_FILE_TYPE_AFTER=[get_property FILE_TYPE $f]"
if {[get_property FILE_TYPE $f] ne "Tcl"} {error "Tcl file type not preserved"}
set_property USED_IN_SYNTHESIS false $f
set_property USED_IN_IMPLEMENTATION true $f
set_property PROCESSING_ORDER LATE $f
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {![string match {*Complete!} [get_property STATUS [get_runs synth_1]]]} {error "probe synth not completed"}
launch_runs impl_1 -to_step init_design -jobs 1
wait_on_run impl_1
if {![string match {*Complete!} [get_property STATUS [get_runs impl_1]]]} {error "probe init not completed"}
open_run impl_1
set pb [get_pblocks -quiet type_probe_pblock]
if {[llength $pb]!=1 || [llength [get_cells -quiet -of_objects $pb]]!=1} {error "Tcl constraint did not actually apply to native init"}
write_checkpoint [file join $report probe_applied.dcp]
close_project
open_checkpoint [file join $report probe_applied.dcp]
if {[llength [get_pblocks -quiet type_probe_pblock]]!=1} {error "native restore lost applied pblock"}
close_design
set h [open [file join $report native_constraint_type_pass.txt] {WRONLY CREAT EXCL}];puts $h "native_type=Tcl
actual_init_applied=1
restored_without_reapply=1";close $h
puts "NATIVE_TCL_CONSTRAINT_TYPE_PROBE_PASS"
