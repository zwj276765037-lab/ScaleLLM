# CPU timing scope integration only. Never invokes Vivado.
source [file join [lindex $argv 0] candidate_inspector.tcl]
set fixtureRoot [lindex $argv 1]
proc get_timing_paths args {
    lappend ::calls $args
    if {$::case eq "disconnected"} {return [list]}
    return {MOCK_PATH_1 MOCK_PATH_2}
}
proc report_timing args {
    set n [lsearch -exact $args -file]
    set h [open [lindex $args [expr {$n+1}]] {WRONLY CREAT EXCL}]
    puts $h "CPU MOCK TIMING REPORT. NOT NATIVE TIMING EVIDENCE."
    close $h
}
proc list_property args {return {STARTPOINT_PIN ENDPOINT_PIN STARTPOINT_CLOCK ENDPOINT_CLOCK SLACK LOGIC_DELAY NET_DELAY DATAPATH_DELAY EXCEPTION}}
proc get_property args {
    if {[lindex $args 0] eq "-quiet"} {set args [lrange $args 1 end]}
    lassign $args property object
    set values [dict create STARTPOINT_PIN {start[1]/Q} ENDPOINT_PIN {end[2]/D} STARTPOINT_CLOCK {clock one} ENDPOINT_CLOCK {clock one} SLACK -0.25 LOGIC_DELAY 1.5 NET_DELAY 0.75 DATAPATH_DELAY 2.25 EXCEPTION {}]
    return [dict get $values $property]
}
foreach case {control optional_unsupported scalar_fallback literal_mixed_inout} {
    set ::case $case
    set ::m002_report_dir [file join $fixtureRoot $case]
    set ::slr2::boundaryPins [dict create]
    set h [open [file join $::m002_report_dir candidate_boundary_timing_scope_test.tsv]]
    gets $h header
    while {[gets $h line]>=0} {
        set fields [split $line "\t"]
        dict set ::slr2::boundaryPins [lindex $fields 1] [lindex $fields 3] 1
    }
    close $h
    set ::calls [list]
    slr2::scoped_timing test
    if {[llength $::calls] != 2 * [dict size $::slr2::boundaryPins]} {error "Timing direction/delay query missing"}
    foreach call $::calls {
        if {[lrange $call end-3 end] ne {-max_paths 16 -nworst 1}} {error "Timing cap changed"}
    }
    puts "TIMING_CASE\t$case\tPASS\t[llength $::calls]"
}
