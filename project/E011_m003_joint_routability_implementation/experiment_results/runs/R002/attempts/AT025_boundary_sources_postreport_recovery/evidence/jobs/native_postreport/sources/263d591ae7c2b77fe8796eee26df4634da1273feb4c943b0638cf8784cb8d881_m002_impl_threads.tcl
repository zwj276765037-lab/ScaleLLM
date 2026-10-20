set_param general.maxThreads 8
puts "M002_IMPL_CHILD_MAX_THREADS [get_param general.maxThreads]"
if {[info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"} {
    source [file join [file dirname [file normalize [info script]]] m002_route_failure_capture.tcl]
    m002_install_route_failure_capture
}
