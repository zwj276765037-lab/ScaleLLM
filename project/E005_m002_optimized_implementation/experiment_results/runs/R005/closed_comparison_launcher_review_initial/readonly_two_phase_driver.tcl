# Single native session, sequential closed place/physopt reads after route terminal.
# The launch wrapper must bind these Tcl sources, job paths, original checkpoints
# and the parent evidence before execution. No physical command is invoked here.
source $::env(E005_SUPPLEMENT_JOBS)
if {![info exists jobs] || [llength $jobs] != 2} {error "Expected exactly two closed-DCP jobs"}
set phases [list];set checkpoints [list];set outputs [list]
set master_out [file normalize $::env(E005_SUPPLEMENT_MASTER_OUT)]
foreach job $jobs {
    if {[llength $job] != 3} {error "Each job requires phase/checkpoint/output"}
    lassign $job phase checkpoint phase_out
    if {$phase ni {place physopt}} {error "Unexpected comparison phase: $phase"}
    set checkpoint [file normalize $checkpoint]
    set phase_out [file normalize $phase_out]
    if {![file isfile $checkpoint]} {error "Missing closed checkpoint: $checkpoint"}
    if {$phase_out eq $master_out || [file exists $phase_out]} {error "Output already used or aliases master: $phase_out"}
    lappend phases $phase;lappend checkpoints $checkpoint;lappend outputs $phase_out
}
if {[lsort $phases] ne {physopt place} || [llength [lsort -unique $checkpoints]] != 2 || [llength [lsort -unique $outputs]] != 2} {
    error "Comparison phases, checkpoints and outputs must each be distinct"
}
set ::env(E005_SUPPLEMENT_NO_EXIT) 1
file mkdir $master_out
set phase_receipt [open [file join $master_out phase_receipts.tsv] {WRONLY CREAT EXCL}]
puts $phase_receipt "phase\tnative_tcl_code\tstarted_epoch\tended_epoch\tresult_and_options_file"
set failed_phases [list]
foreach job $jobs {
    lassign $job phase checkpoint phase_out
    set ::env(E005_SUPPLEMENT_PHASE) $phase
    set ::env(E005_SUPPLEMENT_DCP) $checkpoint
    set ::env(E005_SUPPLEMENT_OUT) $phase_out
    set ::e005_supplement_design_closed 0
    set started [clock seconds]
    set code [catch {source $::env(E005_SUPPLEMENT_CORE)} result options]
    if {$code} {
        lappend failed_phases $phase
        if {!$::e005_supplement_design_closed} {catch {close_design}}
    }
    set disposition [file join $master_out ${phase}_result_and_options.txt]
    set h [open $disposition {WRONLY CREAT EXCL}]
    puts $h [list result $result options $options];close $h
    puts $phase_receipt "$phase\t$code\t$started\t[clock seconds]\t$disposition";flush $phase_receipt
    puts "E005_READONLY_PHASE_COMPLETED $phase native_tcl_code=$code"
}
close $phase_receipt
set h [open [file join $master_out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_phases=$failed_phases\nphysical_commands_executed=false\ncheckpoint_write_executed=false\ncomparison_phase_scope=each_own_closed_DCP\nformal_signoff=false";close $h
if {[llength $failed_phases]} {exit 1}
puts "E005_READONLY_TWO_PHASE_SUPPLEMENT_COMPLETED"
exit 0
