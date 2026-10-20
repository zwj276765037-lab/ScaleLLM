# Read-only native role attribution. All names/counts are observations, never G4.
namespace eval ::m003_role_diag {
    variable batch_size 256
    variable progress
    variable identity_cache [dict create]
    variable support_cache [dict create]
    variable errors 0
    variable fields {NAME REF_NAME PARENT ORIG_CELL_NAME ORIG_REF_NAME IS_PRIMITIVE DONT_TOUCH}
    variable collections {
        {parent_scope_candidates {NAME =~ "*u_mlp/u_serial_command/u_shared_compute"}}
        {parent_payload_and_count_native {IS_PRIMITIVE == 1 && NAME =~ "*parent_*_r_reg*"}}
        {parent_buffer_native {IS_PRIMITIVE == 1 && NAME =~ "*u_shared_compute/*u_ce_buffer"}}
        {metadata_native_names {IS_PRIMITIVE == 1 && NAME =~ "*u_attention/u_meta/*"}}
    }
}
proc ::m003_role_diag::quote {value} {
    set out {"}
    foreach ch [split $value {}] {
        scan $ch %c code
        if {$ch eq "\""} {append out {\"}} elseif {$ch eq "\\"} {append out {\\}} elseif {$code < 32} {
            append out [format {\u%04x} $code]
        } else {append out $ch}
    }
    append out {"}; return $out
}
proc ::m003_role_diag::event {kind args} {
    variable progress
    set parts [list "\"event\":[quote $kind]" "\"clock_ms\":[clock milliseconds]"]
    foreach {key value} $args {lappend parts "[quote $key]:[quote $value]"}
    set row "\{[join $parts ,]\}"
    puts $progress $row; flush $progress
    puts "M003_ROLE_DIAG $row"; flush stdout
}
proc ::m003_role_diag::failure {message} {
    variable errors; incr errors
    return [dict create status API_ERROR value {} error $message]
}
proc ::m003_role_diag::read_value {object key representative collection stage} {
    if {$representative} {event field_begin collection $collection stage $stage field $key object $object}
    set started [clock milliseconds]
    if {[catch {get_property -quiet $key $object} value]} {
        set result [failure $value]
    } else {
        set status [expr {$value eq {} ? {OK_EMPTY} : {OK}}]
        set result [dict create status $status value $value]
    }
    if {$representative} {
        event field_end collection $collection stage $stage field $key status [dict get $result status] \
            value [dict get $result value] elapsed_ms [expr {[clock milliseconds]-$started}]
    }
    return $result
}
proc ::m003_role_diag::support {object representative collection} {
    variable support_cache
    if {![dict exists $support_cache $object]} {
        if {$representative} {event field_begin collection $collection stage attributes field list_property object $object}
        set started [clock milliseconds]
        if {[catch {list_property $object} properties]} {
            set result [failure $properties]
        } else {set result [dict create status OK properties $properties]}
        dict set support_cache $object $result
        if {$representative} {event field_end collection $collection stage attributes field list_property \
            status [dict get $result status] elapsed_ms [expr {[clock milliseconds]-$started}]}
    }
    return [dict get $support_cache $object]
}
proc ::m003_role_diag::row_values {object stage representative collection} {
    variable identity_cache; variable fields
    if {$stage eq {identity}} {
        if {![dict exists $identity_cache $object]} {
            set values [dict create]
            foreach key {NAME REF_NAME CLASS} {
                dict set values $key [read_value $object $key $representative $collection $stage]
            }
            dict set identity_cache $object $values
        }
        return [dict get $identity_cache $object]
    }
    set supported [support $object $representative $collection]
    set values [dict create]
    foreach key $fields {
        if {$key in {NAME REF_NAME}} {
            set result [dict get $identity_cache $object $key]
        } elseif {[dict get $supported status] eq {API_ERROR}} {
            set result [dict create status API_ERROR value {} error {list_property failed}]
        } elseif {$key ni [dict get $supported properties]} {
            set result [dict create status UNSUPPORTED value {}]
        } else {set result [read_value $object $key $representative $collection $stage]}
        dict set values $key $result
    }
    return $values
}
proc ::m003_role_diag::dump {report collection objects stage} {
    variable fields; variable batch_size; variable errors
    set keys [expr {$stage eq {identity} ? {NAME REF_NAME CLASS} : $fields}]
    set stem [file join $report $collection]
    if {$stage eq {identity}} {append stem .identity}
    set jp "$stem.jsonl.partial"; set tp "$stem.tsv.partial"
    set j [open $jp {WRONLY CREAT EXCL}]; set t [open $tp {WRONLY CREAT EXCL}]
    set header {index object}
    foreach key $keys {lappend header $key "${key}_STATUS"}
    puts $t [join $header "\t"]; flush $t; flush $j
    set before $errors; set index 0; set jb {}; set tb {}; set started [clock milliseconds]
    event dump_begin collection $collection stage $stage count [llength $objects]
    foreach object $objects {
        set values [row_values $object $stage [expr {$index == 0}] $collection]
        set pairs {}; set columns [list $index [quote $object]]
        foreach key $keys {
            set result [dict get $values $key]; set status [dict get $result status]
            set value [expr {$status in {UNSUPPORTED API_ERROR} ? {null} : [quote [dict get $result value]]}]
            set json "\{\"status\":[quote $status],\"value\":$value"
            if {[dict exists $result error]} {append json ",\"error\":[quote [dict get $result error]]"}
            append json "\}"
            lappend pairs "[quote $key]:$json"; lappend columns $value $status
        }
        lappend jb "\{\"index\":$index,\"object\":[quote $object],\"fields\":\{[join $pairs ,]\}\}"
        lappend tb [join $columns "\t"]; incr index
        if {$index % $batch_size == 0 || $index == [llength $objects]} {
            puts $j [join $jb "\n"]; puts $t [join $tb "\n"]; flush $j; flush $t
            set jb {}; set tb {}
            event dump_batch collection $collection stage $stage rows_written $index elapsed_ms [expr {[clock milliseconds]-$started}]
        }
    }
    close $j; close $t
    if {$errors == $before} {
        file rename $jp "$stem.jsonl"; file rename $tp "$stem.tsv"
        event dump_closed collection $collection stage $stage rows_written $index
    } else {event dump_error collection $collection stage $stage rows_written $index errors [expr {$errors-$before}]}
}
proc ::m003_role_diag::run {report} {
    variable progress; variable collections; variable errors
    set progress [open [file join $report diagnostic_progress.jsonl] {WRONLY CREAT EXCL}]
    event diagnostic_begin constraint_apply_requested 0 new_synthesis_launched 0
    set groups [dict create]; set count_rows {}; set text_rows {}
    foreach entry $collections {
        lassign $entry collection filter
        event collection_begin collection $collection filter $filter
        set start [clock milliseconds]
        set objects [get_cells -quiet -hier -filter $filter]
        set elapsed [expr {[clock milliseconds]-$start}]
        dict set groups $collection $objects
        set count [llength $objects]
        lappend count_rows "[quote $collection]:\{\"count\":$count,\"query_ms\":$elapsed,\"filter\":[quote $filter]\}"
        lappend text_rows "$collection=$count query_ms=$elapsed"
        event collection_end collection $collection count $count query_ms $elapsed
    }
    set h [open [file join $report query_counts.json.partial] {WRONLY CREAT EXCL}]
    puts $h "\{\"collections\":\{[join $count_rows ,]\},\"constraint_apply_requested\":false,\"new_synthesis_launched\":false\}"; close $h
    file rename [file join $report query_counts.json.partial] [file join $report query_counts.json]
    set h [open [file join $report query_counts.txt] {WRONLY CREAT EXCL}]; puts $h [join $text_rows "\n"]; close $h
    event counts_closed
    # All canonical identities close before any optional/origin property enumeration.
    set order {parent_payload_and_count_native parent_buffer_native metadata_native_names parent_scope_candidates}
    foreach collection $order {dump $report $collection [dict get $groups $collection] identity}
    if {$errors} {event diagnostic_error stage identity errors $errors; close $progress; error {Native identity API errors; no completion artifact}}
    event all_identities_closed
    foreach collection $order {dump $report $collection [dict get $groups $collection] attributes}
    if {$errors} {event diagnostic_error stage attributes errors $errors; close $progress; error {Native attribute API errors; no completion artifact}}
    set h [open [file join $report diagnostic_complete.json.partial] {WRONLY CREAT EXCL}]
    puts $h {"execution":"completed","api_errors":0,"scope":"read-only observed names/fields; not G4 or family qualification"}; close $h
    file rename [file join $report diagnostic_complete.json.partial] [file join $report diagnostic_complete.json]
    event diagnostic_complete; close $progress
}
if {![info exists ::env(M003_ROLE_DIAG_LIBRARY_ONLY)]} {
    set_param general.maxThreads 8
    open_checkpoint [lindex $argv 0]
    ::m003_role_diag::run $::env(HAP_REPORT_DIR)
    close_design
    puts M003_FRESH_CORE_NATIVE_ROLE_ATTRIBUTION_COMPLETED; flush stdout
}
