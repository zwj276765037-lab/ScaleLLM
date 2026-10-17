
set ::env(PATH) [lindex $argv 1]/bin:/usr/bin:/bin
set ::env(PYTHONHOME) [lindex $argv 1]
set ::env(PYTHONPATH) [lindex $argv 1]/lib/python3.13
foreach name {PYTHONPLATLIBDIR PYTHONUSERBASE TCL_LIBRARY TK_LIBRARY LD_LIBRARY_PATH __PYVENV_LAUNCHER__} {set ::env($name) /nonexistent/vendor_pollution}

set ::env(E006_OUT) [lindex $argv 2]
set ::env(E006_DCP) CPU_TEST_NO_DCP_OPENED
set ::env(E006_TARGETS) [file join [lindex $argv 0] targets.tcl]
set ::env(E006_CANDIDATE_ADAPTER) [file join [lindex $argv 0] directed_evidence.py]
proc set_param args {}
proc open_checkpoint args {error "INTENTIONAL_NATIVE_BOUNDARY_STOP\nsecond line\tfield"}
source [file join [lindex $argv 0] attribution_directed.tcl]
