# Independent PREPARED lean candidate; never hot-edits AT001.
# E006 read-only current-physopt attribution. No physical/write-checkpoint commands.
set out $::env(E006_OUT)
file mkdir $out
set_param general.maxThreads 8
source $::env(E006_TARGETS)
source [file join [file dirname [info script]] system_python.tcl]
source [file join [file dirname [info script]] property_alignment.tcl]
set failures [list]
set receipt [open [file join $out query_receipts.tsv] {WRONLY CREAT EXCL}]
puts $receipt "query\tnative_tcl_code\tstarted_epoch\tended_epoch\tresult"
set stages [open [file join $out stage_receipts.tsv] {WRONLY CREAT EXCL}]
puts $stages "stage\tnative_tcl_code\tstarted_epoch\tended_epoch\tfailed_queries"
proc query {name body} {
    global receipt failures out
    set started [clock seconds]
    set code [catch {uplevel 1 $body} result options]
    if {$code} {
        lappend failures $name
        set h [open [file join $out error_${name}.txt] {WRONLY CREAT EXCL}]
        puts $h [list result $result options $options];close $h
    }
    if {[string length $result] > 1000 && !$code} {set result "SUCCESS_RESULT_LENGTH=[string length $result]; actual artifacts retained"}
    set receiptResult [string map [list \n {\n} \r {\r} \t {\t}] [list $result]]
    puts $receipt "$name\t$code\t$started\t[clock seconds]\t$receiptResult";flush $receipt
    puts "E006_QUERY_COMPLETED $name native_tcl_code=$code"
    return $code
}
proc stage_done {name start before} {
    global failures stages out
    set failed [lrange $failures $before end]
    set code [expr {[llength $failed] ? 1 : 0}]
    set h [open [file join $out stage_${name}_closed.txt] {WRONLY CREAT EXCL}]
    puts $h "stage=$name\nnative_tcl_code=$code\nstarted_epoch=$start\nended_epoch=[clock seconds]\nfailed_queries=$failed\nphysical_commands_executed=false\ncheckpoint_write_executed=false";close $h
    puts $stages "$name\t$code\t$start\t[clock seconds]\t[list $failed]";flush $stages
    puts "E006_STAGE_COMPLETED $name native_tcl_code=$code"
}
proc m002_put {path text} {set h [open $path {WRONLY CREAT EXCL}];puts $h $text;close $h}

if {[query system_python_runtime_preflight {
    set runtime [m002_system_python $::env(E006_CANDIDATE_ADAPTER) runtime-preflight]
    m002_put [file join $out native_system_python_preflight.json] $runtime
}]} {close $receipt;close $stages;exit 1}
if {[query open_checkpoint {open_checkpoint $::env(E006_DCP)}]} {close $receipt;close $stages;exit 1}
if {[query identity {
    m002_put [file join $out identity.tsv] "tool\t[version -short]\ncheckpoint\t$::env(E006_DCP)\nPART\t[get_property PART [current_design]]\nNAME\t[get_property NAME [current_design]]\nblackboxes\t[llength [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]]"
}]} {close $receipt;close $stages;exit 1}
if {[query topology {
    set siteSLR [dict create]
    foreach slr [get_slrs] {foreach site [get_sites -of_objects $slr] {dict set siteSLR [get_property NAME $site] [get_property NAME $slr]}}
    if {![dict size $siteSLR]} {error "Actual device SLR/site map empty"}
}]} {close $receipt;close $stages;exit 1}
source [file join [file dirname [info script]] candidate_inspector.tcl]
source [file join [file dirname [info script]] directed_exporter.tcl]
set ::m002_report_dir $out
set ::slr2::siteSLR $siteSLR
set memberStatus [dict create]
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set code [query candidate_${point}_membership_qualification {
        slr2::readonly_resolve $point $root
        m002_system_python $::env(E006_CANDIDATE_ADAPTER) qualify-membership $point $out
    }]
    dict set memberStatus $point $code
    stage_done candidate_${point}_membership_qualification $start $before
}
query candidate_disjointness {
    set seen [dict create]
    foreach spec $exact_candidate_targets {
        lassign $spec point root
        if {[dict get $memberStatus $point]} {error "Candidate native membership did not qualify: $point"}
        foreach key {RAW P} {
            foreach name [dict keys [dict get $::slr2::candidateSets $point $key]] {
                set identity [list $key $name]
                if {[dict exists $seen $identity]} {error "Independent candidates overlap: $identity"}
                dict set seen $identity $point
            }
        }
    }
    m002_put [file join $out candidate_disjointness.txt] "disjoint=true\ncombined_migration=false"
}
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set code [query candidate_${point}_directed_cut {
        if {[dict get $memberStatus $point]} {error "Actual candidate membership unqualified"}
        foreach key {RAW S P} {set ::slr2::$key [dict get $::slr2::candidateSets $point $key]}
        slr2::cut $point
    }]
    stage_done candidate_${point}_directed_cut $start $before
    set start [clock seconds];set before [llength $failures]
    query candidate_${point}_bounded_timing {
        if {$code} {error "Directed candidate boundary did not close"}
        slr2::scoped_timing $point
        m002_system_python $::env(E006_CANDIDATE_ADAPTER) timing $point $out
    }
    stage_done candidate_${point}_bounded_timing $start $before
}
close $receipt;close $stages
m002_put [file join $out result.txt] "failed_queries=$failures\ncoverage_version=candidate_directed_cut_v1\nwhole_hotspot_UNION_full_endpoint_recovery=NOT_IN_SCOPE_UNFINISHED_OLD_SCOPE_PRESERVED\nphysical_commands_executed=false\ncheckpoint_write_executed=false\nsource_graph=E005_closed_physopt_not_failed_route\nformal_signoff=false"
close_design
if {[llength $failures]} {exit 1}
puts "E006_TWO_CANDIDATE_DIRECTED_CUT_COMPLETED"
exit 0
