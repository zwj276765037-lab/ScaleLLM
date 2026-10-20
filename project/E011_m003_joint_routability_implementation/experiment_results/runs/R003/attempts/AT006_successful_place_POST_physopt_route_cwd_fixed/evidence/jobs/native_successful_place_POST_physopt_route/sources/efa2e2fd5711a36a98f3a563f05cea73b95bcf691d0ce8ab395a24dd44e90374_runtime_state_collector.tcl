# Reuse the reviewed cached collector procedures and exact selected loops.
set state_runtime_here [file dirname [file normalize [info script]]]
set h [open [file join $state_runtime_here query_cached.tcl] r]
set cached_loader [read $h]
close $h
set execute_line {uplevel #0 $cached_body}
set execute_at [string first $execute_line $cached_loader]
if {$execute_at < 0 || [string first $execute_line $cached_loader [expr {$execute_at+1}]] >= 0} {error "Reviewed cached collector execution boundary changed"}
uplevel #0 [string range $cached_loader 0 [expr {$execute_at-1}]]
set defs_at [string first {proc proof_fields } $cached_body]
set loops_at [string first {foreach cell $proof_cells} $cached_body]
set end_loops {close $h
set h [open [file join $out read_only_complete.json]}
set loops_end [string first $end_loops $cached_body]
if {$defs_at < 0 || $loops_at <= $defs_at || $loops_end <= $loops_at} {error "Reviewed collector fields/loop boundaries changed"}
uplevel #0 [string range $cached_body $defs_at [expr {$loops_at-1}]]
set state_runtime_selected_loops [string range $cached_body $loops_at [expr {$loops_end-1}]]
proc m003_collect_actual_write_states {phase out} {
    if {$phase ni {restore place physopt route}} {error "Foreign state-proof phase"}
    source [file join $::state_runtime_here targets.tcl]
    set token [m003_conn::begin ${phase}_write_state [file join $out state_${phase}_API_trace.jsonl] [file join $out state_${phase}_groups.jsonl] [file join $out state_${phase}_bindings.jsonl]]
    set ::proof_token $token
    set h [open [file join $out state_${phase}_actual.jsonl] {WRONLY CREAT EXCL}]
    set ::h $h
    set code [catch {eval $::state_runtime_selected_loops} message options]
    close $h
    if {$code} {m003_conn::abort;return -options $options $message}
    set stats [m003_conn::finish $token]
    set h [open [file join $out state_${phase}_API_counts.tcldict] {WRONLY CREAT EXCL}]
    puts $h $stats
    close $h
    if {$phase in {restore place}} {set checkpoint $::env(HAP_RECOVERY_CHECKPOINT)} else {set checkpoint [file join $out ${phase}.dcp]}
    if {![file isfile $checkpoint]} {error "Actual phase checkpoint missing for state proof"}
    set h [open [file join $out state_${phase}_native_context.json] {WRONLY CREAT EXCL}]
    puts $h [m003::jobject [dict create phase $phase design [current_design] checkpoint [file normalize $checkpoint] new_state_query true selected_cells [llength $proof_cells] selected_root_pins [llength $proof_root_pins]]]
    close $h
}
