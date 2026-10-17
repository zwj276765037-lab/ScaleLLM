
set ::env(PATH) [lindex $argv 1]/bin:/usr/bin:/bin
set ::env(PYTHONHOME) [lindex $argv 1]
set ::env(PYTHONPATH) [lindex $argv 1]/lib/python3.13
foreach name {PYTHONPLATLIBDIR PYTHONUSERBASE TCL_LIBRARY TK_LIBRARY LD_LIBRARY_PATH __PYVENV_LAUNCHER__} {set ::env($name) /nonexistent/vendor_pollution}

set ::env(SLR2_REUSED_SCRIPT_DIR) [lindex $argv 3]
set ::env(SLR2_HOOKS) [file join [lindex $argv 0] E008_entry candidate_hooks.tcl]
set ::env(SLR2_ADAPTER) [file join [lindex $argv 0] E008_entry evidence_adapter.py]
set ::env(SLR2_CANDIDATE_ROOT) CPU_TEST_LITERAL_ROOT
set ::env(SLR2_CANDIDATE_ID) C01
set ::env(HAP_REPORT_DIR) [lindex $argv 2]
set ::env(HAP_PROJECT_DIR) CPU_TEST_NO_PROJECT_OPENED
set ::env(HAP_STAGE) place
set ::env(HAP_EXECUTION_MODE) checkpoint_restored_commands
proc version args {return 2025.2}
proc set_param args {}
proc open_project args {error INTENTIONAL_NATIVE_PROJECT_BOUNDARY_STOP}
set code [catch {source [file join [lindex $argv 0] E008_entry implementation.tcl]} result options]
if {$code!=1 || $result ne "INTENTIONAL_NATIVE_PROJECT_BOUNDARY_STOP"} {error "Unexpected actual E008 entry result: $code/$result"}
foreach name {m002_live_pre_place_restore m002_post} {
    set body [info body $name]
    if {[string first {exec python3} $body]>=0 || [string first {m002_system_python $::env(SLR2_ADAPTER)} $body]<0} {error "Unsanitized rewritten native helper: $name"}
}
puts E008_FULL_ACTUAL_ENTRY_PREFLIGHT_PASS
