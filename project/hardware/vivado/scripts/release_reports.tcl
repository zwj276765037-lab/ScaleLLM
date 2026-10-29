# SPDX-License-Identifier: Apache-2.0
# Shared design identity, reporting and bit-publication acceptance checks.
proc require_design_identity {} {
    if {[version -short] ne {2025.2} || [get_property PART [current_design]] ne {xcvu9p-flga2104-2L-e}} {error {Tool or part mismatch}}
    if {[get_property NAME [current_design]] ne {scalellm_final_decode16_bd_wrapper}} {error {Top mismatch}}
    foreach {pin expected} {core_clk 12.5 ddr0_clk 5.0 ddr1_clk 5.0} {
        set pins [get_pins -quiet scalellm_final_decode16_bd_i/core/inst/$pin]
        set clocks [get_clocks -quiet -of_objects $pins]
        if {[llength $pins]!=1 || [llength $clocks]!=1} {error "Missing unique clock at $pin"}
        if {abs(double([get_property PERIOD $clocks])-$expected)>0.001} {error "Clock period mismatch at $pin"}
    }
}
proc report_scene {out} {
    report_utilization -file [file join $out utilization.rpt]
    report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out timing_summary.rpt]
    report_clocks -file [file join $out clocks.rpt]
    check_timing -verbose -file [file join $out check_timing.rpt]
    report_drc -file [file join $out drc.rpt]
}
proc require_timing {out} {
    report_timing_summary -delay_type min_max -no_detailed_paths -file [file join $out timing_acceptance.rpt]
    set f [open [file join $out timing_acceptance.rpt]];set txt [read $f];close $f
    set after_header 0
    set v {}
    foreach line [split $txt "\n"] {
        if {[string first {WNS(ns)} $line]>=0 && [string first {WHS(ns)} $line]>=0 && [string first {WPWS(ns)} $line]>=0} {set after_header 1;continue}
        if {!$after_header} {continue}
        set fields [regexp -all -inline {\S+} $line]
        if {[llength $fields]==12 && [string is double -strict [lindex $fields 0]]} {set v $fields;break}
    }
    if {[llength $v]!=12} {error {Cannot parse global timing summary}}
    foreach i {0 4 8} {if {![string is double -strict [lindex $v $i]] || [lindex $v $i]<0} {error {Setup, hold or pulse timing failed}}}
    foreach i {1 2 5 6 9 10} {if {[lindex $v $i]!=0} {error {Timing failures remain}}}
    if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {error {Design not fully routed}}
    report_route_status -file [file join $out route_status.rpt]
    report_drc -file [file join $out drc_acceptance.rpt]
    if {[llength [get_drc_violations -quiet -filter {SEVERITY == "Error" || SEVERITY == "Critical Warning"}]]} {error {DRC Error or Critical Warning remains}}
}
