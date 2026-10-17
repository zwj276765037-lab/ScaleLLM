
set ::env(PATH) [lindex $argv 1]/bin:/usr/bin:/bin
set ::env(PYTHONHOME) [lindex $argv 1]
set ::env(PYTHONPATH) [lindex $argv 1]/lib/python3.13
foreach name {PYTHONPLATLIBDIR PYTHONUSERBASE TCL_LIBRARY TK_LIBRARY LD_LIBRARY_PATH __PYVENV_LAUNCHER__} {set ::env($name) /nonexistent/vendor_pollution}

source [file join [lindex $argv 0] system_python.tcl]
set before [array get ::env]
set result [m002_system_python [file join [lindex $argv 0] directed_evidence.py] runtime-preflight]
set h [open [lindex $argv 2] {WRONLY CREAT EXCL}];puts $h $result;close $h
if {[array get ::env] ne $before} {error "Vivado parent environment changed"}
