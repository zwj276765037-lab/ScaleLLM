# System Tcl syntax completeness only: never evaluate the Vivado script.
set f [open [lindex $argv 0] r]
set text [read $f]
close $f
if {![info complete $text]} {error "incomplete Tcl source"}
puts "SYSTEM_TCL=[info patchlevel] SOURCE_COMPLETENESS=PASS NATIVE_COMMANDS=NOT_EXECUTED"
