run 120ns
set dut_scopes [list]
foreach candidate [get_scopes -quiet -r *] {
    if {[regexp {([/.])dut$} [get_property NAME $candidate]]} {
        lappend dut_scopes $candidate
    }
}
if {[llength $dut_scopes] != 1} {
    error "expected one post-route DUT scope, found [llength $dut_scopes]: $dut_scopes"
}
set dut_path [lindex $dut_scopes 0]
set dut_objects [get_objects -quiet -r ${dut_path}/*]
if {[llength $dut_objects] == 0} {
    error "no post-route objects below $dut_path"
}
puts "POWER_SAIF_DUT_SCOPE: $dut_path"
puts "POWER_SAIF_CAPTURE_MODE: full_post_route_timing_netlist"
puts "POWER_SAIF_OBJECT_COUNT: [llength $dut_objects]"
open_saif $::env(HAP_SAIF_RAW_PATH)
log_saif $dut_objects
run all
close_saif
