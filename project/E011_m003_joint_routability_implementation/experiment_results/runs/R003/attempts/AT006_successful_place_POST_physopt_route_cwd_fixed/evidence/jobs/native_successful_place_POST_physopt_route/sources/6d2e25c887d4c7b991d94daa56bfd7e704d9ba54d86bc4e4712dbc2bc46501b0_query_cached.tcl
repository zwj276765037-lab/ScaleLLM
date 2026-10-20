# Nonactive candidate: preserve the exact selected-pin schema and all FF facts;
# use the existing immutable-phase native group cache for signal inventories.
set cached_here [file dirname [file normalize [info script]]]
set h [open [file join $cached_here query.tcl] r]
set cached_body [read $h]
close $h
set old_source {    set nets [get_nets -quiet -segments -of_objects $pin]
    if {![llength $nets]} {error "Proof pin disconnected $pin"}
    set drivers [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]
    set owners {};set refs {}
    foreach driver $drivers {
        set owner [get_cells -quiet -of_objects $driver]
        m003::exact_count $owner 1 "proof actual leaf driver owner"
        lappend owners [get_property NAME $owner]
        lappend refs [get_property REF_NAME $owner]
    }
    set ports [get_ports -quiet -of_objects $nets]}
set new_source {    set binding [m003_conn::bind $::proof_token $pin]
    set group [m003_conn::source $::proof_token [dict get $binding group] 1]
    set nets [dict get $group objects]
    set drivers [dict get $group leaf_driver_objects]
    set owners [dict get $group driver_cells]
    set refs [dict get $group driver_refs]
    set ports [dict get $group primary_port_objects]}
set substitutions [list $old_source $new_source \
    {nets [lsort -unique [get_property NAME $nets]]} {nets [lsort -unique [dict get $group nets]]} \
    {set out $::env(HAP_REPORT_DIR)} {set out $::env(HAP_REPORT_DIR)
set ::proof_token [m003_conn::begin placed_write_replica_proof [file join $out grouped_API_trace.jsonl] [file join $out grouped_native_sources.jsonl] [file join $out grouped_native_pin_bindings.jsonl]]} \
    {close_design} {set grouped_stats [m003_conn::finish $::proof_token]
set h [open [file join $out grouped_API_counts.tcldict] {WRONLY CREAT EXCL}]
puts $h $grouped_stats
close $h
close_design}]
foreach {old new} $substitutions {
    set first [string first $old $cached_body]
    if {$first < 0 || [string first $old $cached_body [expr {$first+1}]] >= 0} {error "Cached proof exact substitution changed"}
    set cached_body [string map [list $old $new] $cached_body]
}
if {![info complete $cached_body]} {error "Cached proof body incomplete"}
uplevel #0 $cached_body
