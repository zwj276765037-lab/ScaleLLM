# Standalone read-only original-address attribution on the original fresh core.
# No production helper source, constraint application, synthesis, checkpoint writes,
# or property enumeration. Standard fields are read directly per primitive.
namespace eval ::m003_addr_diag {
    variable max_rows 2048
    variable errors 0
    variable collections {
        {original_address_broad {IS_PRIMITIVE == 1 && NAME =~ "inst/u_core/u_compute/u_attention/*meta_read_addr_r_reg*"}}
        {local_control_luts {IS_PRIMITIVE == 1 && NAME =~ "inst/u_core/u_compute/u_attention/u_meta/*u_addr/u_local_*"}}
    }
}
proc ::m003_addr_diag::quote {value} {
    set out {"}
    foreach ch [split $value {}] {
        scan $ch %c code
        if {$ch eq "\""} {append out {\"}} elseif {$ch eq "\\"} {append out {\\}} elseif {$code<32} {append out [format {\u%04x} $code]} else {append out $ch}
    }
    append out {"};return $out
}
proc ::m003_addr_diag::event {kind args} {
    variable progress
    set parts [list "\"event\":[quote $kind]" "\"clock_ms\":[clock milliseconds]"]
    foreach {k v} $args {lappend parts "[quote $k]:[quote $v]"}
    puts $progress "\{[join $parts ,]\}";flush $progress
    puts "M003_ADDR_DIAG $kind $args";flush stdout
}
proc ::m003_addr_diag::read_field {object key} {
    variable errors
    if {[catch {get_property -quiet $key $object} value]} {
        incr errors;return "\{\"status\":\"API_ERROR\",\"value\":null,\"error\":[quote $value]\}"
    }
    set status [expr {$value eq {} ? {OK_EMPTY} : {OK}}]
    return "\{\"status\":[quote $status],\"value\":[quote $value]\}"
}
proc ::m003_addr_diag::run {report} {
    variable collections;variable max_rows;variable errors;variable progress
    set errors 0
    set progress [open [file join $report diagnostic_progress.jsonl] {WRONLY CREAT EXCL}]
    event diagnostic_begin constraint_apply_requested 0 new_synthesis_launched 0
    set counts {}
    foreach collection $collections {
        lassign $collection name filter
        event collection_begin collection $name filter $filter
        set start [clock milliseconds];set objects [get_cells -quiet -hier -filter $filter];set ms [expr {[clock milliseconds]-$start}]
        set n [llength $objects];event collection_end collection $name count $n query_ms $ms
        lappend counts "[quote $name]:\{\"count\":$n,\"query_ms\":$ms,\"filter\":[quote $filter]\}"
        if {$n==0 || $n>$max_rows || [llength [lsort -unique $objects]]!=$n} {event diagnostic_error collection $name reason invalid_count count $n;close $progress;error "M003 address diagnostic empty/duplicate/over-bound collection: $name/$n"}
        set partial [file join $report ${name}.jsonl.partial]
        set h [open $partial {WRONLY CREAT EXCL}];set before $errors;set index 0
        foreach object $objects {
            set pairs {}
            foreach key {NAME REF_NAME IS_PRIMITIVE DONT_TOUCH} {lappend pairs "[quote $key]:[read_field $object $key]"}
            if {$name eq {local_control_luts}} {lappend pairs "\"INIT\":[read_field $object INIT]"}
            puts $h "\{\"index\":$index,\"object\":[quote $object],\"fields\":\{[join $pairs ,]\}\}"
            incr index
            if {$index%64==0} {flush $h;event dump_batch collection $name rows_written $index}
        }
        close $h
        if {$errors!=$before} {event diagnostic_error collection $name reason field_API_error;close $progress;error "M003 address diagnostic native field API error"}
        file rename $partial [file join $report ${name}.jsonl]
        event dump_closed collection $name rows_written $index
    }
    set h [open [file join $report query_counts.json] {WRONLY CREAT EXCL}]
    puts $h "\{\"collections\":\{[join $counts ,]\},\"constraint_apply_requested\":false,\"new_synthesis_launched\":false\}";close $h
    set h [open [file join $report diagnostic_complete.json] {WRONLY CREAT EXCL}]
    puts $h "\{\"execution\":\"completed\",\"api_errors\":$errors,\"scope\":\"read-only original address and protected local-control identities; no role or G4 verdict\"\}";close $h
    event diagnostic_complete;close $progress
}
if {![info exists ::env(M003_ORIGINAL_ADDRESS_LIBRARY_ONLY)]} {
    set_param general.maxThreads 8
    open_checkpoint [lindex $argv 0]
    ::m003_addr_diag::run $::env(HAP_REPORT_DIR)
    close_design
    puts M003_FRESH_CORE_ORIGINAL_ADDRESS_ATTRIBUTION_COMPLETED;flush stdout
}
