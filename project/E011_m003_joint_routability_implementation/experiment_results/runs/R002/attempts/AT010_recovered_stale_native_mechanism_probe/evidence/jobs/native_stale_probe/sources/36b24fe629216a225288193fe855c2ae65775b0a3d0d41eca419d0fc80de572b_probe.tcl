set report $::env(HAP_REPORT_DIR)
set top [lindex $argv 0]
set overlay [lindex $argv 1]
set extractor [lindex $argv 2]
set_param general.maxThreads 8
source $::env(HAP_PROBE_HELPER)
create_project type_probe [file join $report native_project] -part xcvu9p-flga2104-2L-e
add_files $top
set_property TOP type_probe [current_fileset]
set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs synth_1]
add_files -fileset constrs_1 $overlay
set f [get_files $overlay]
set_property FILE_TYPE XDC $f
set_property USED_IN_SYNTHESIS false $f
set_property USED_IN_IMPLEMENTATION true $f
set_property PROCESSING_ORDER LATE $f
if {[get_property FILE_TYPE $f] ne "XDC"} {error "initial XDC not registered"}
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {![string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {error "probe synth not complete"}
set_property FILE_TYPE TCL $f
set_property USED_IN_SYNTHESIS false $f
set_property USED_IN_IMPLEMENTATION true $f
set_property PROCESSING_ORDER LATE $f
set run [get_runs synth_1]
set h [open [file join $report actual_stale_metadata.txt] {WRONLY CREAT EXCL}]
foreach property {STATUS PROGRESS NEEDS_REFRESH} {puts $h "$property=[get_property $property $run]"};close $h
if {[get_property STATUS $run] ne "Out-of-date" || [get_property PROGRESS $run] ne "100%" || [get_property NEEDS_REFRESH $run] ne "1"} {error "native metadata did not reproduce stale"}
open_run synth_1
close_design
launch_runs impl_1 -to_step opt_design -jobs 1 -scripts_only
set directory [get_property DIRECTORY [get_runs impl_1]]
set driver [file join $directory type_probe.tcl]
close_project
set prefix [file join $report native_init_prefix.tcl]
exec /usr/bin/env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 $extractor --driver $driver --output $prefix
set h [open $prefix r];set text [read $h];close $h
if {![info complete $text]} {error "INIT prefix not complete Tcl syntax"}
set previous [pwd]
cd $directory
try {source $prefix} finally {cd $previous}
if {![file exists [file join $directory .init_design.end.rst]] || [file exists [file join $directory .init_design.error.rst]] || [file exists [file join $directory .opt_design.begin.rst]]} {error "native INIT/OPT boundary did not hold"}
set pb [get_pblocks -quiet type_probe_pblock]
if {[llength $pb]!=1 || [llength [get_cells -quiet -of_objects $pb]]!=1 || $::constraint_probe::attempts != 1} {error "native TCL constraint actual apply not established"}
write_checkpoint [file join $report probe_init_applied.dcp]
set before $::constraint_probe::attempts
set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1
close_project
open_checkpoint [file join $report probe_init_applied.dcp]
if {[llength [get_pblocks -quiet type_probe_pblock]]!=1 || [llength [get_cells -quiet -of_objects [get_pblocks type_probe_pblock]]]!=1 || $::constraint_probe::attempts != $before} {error "restore changed constraints or called apply"}
close_project
set h [open [file join $report native_constraint_type_pass.txt] {WRONLY CREAT EXCL}]
puts $h "native_type=TCL\nactual_init_applied=1\nrestore_apply_attempt_delta=0\nopt_command_started=0\ninit_prefix_native_completed=1"
close $h
puts "STALE_CONTENT_OPEN_RUN_AND_NATIVE_SCRIPT_GENERATION_PROBE_PASS"
