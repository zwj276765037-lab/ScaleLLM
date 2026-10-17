# Single native session, sequential closed place/physopt reads after route terminal.
# The launch wrapper must bind these Tcl sources, job paths, original checkpoints
# and the parent evidence before execution. No physical command is invoked here.
source $::env(E005_SUPPLEMENT_JOBS)
set ::env(E005_SUPPLEMENT_NO_EXIT) 1
set master_out $::env(E005_SUPPLEMENT_MASTER_OUT)
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
