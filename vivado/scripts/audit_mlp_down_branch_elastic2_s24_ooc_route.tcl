set artifact [file normalize $::env(HAP_ROUTE_ARTIFACT)]
set dcp [file join $artifact post_route.dcp]
if {![file exists $dcp]} {error "missing post-route checkpoint $dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
open_checkpoint $dcp

set queue_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_queue/*}]
set max_fanout 0
set max_fanout_net NONE
foreach net $queue_nets {
    set net_name [get_property NAME $net]
    set net_clocks [get_clocks -quiet -of_objects [concat \
        [get_pins -quiet -of_objects $net] \
        [get_ports -quiet -of_objects $net]]]
    if {[llength $net_clocks] != 0 ||
        $net_name eq "u_queue/<const0>" ||
        $net_name eq "u_queue/<const1>"} {
        continue
    }
    set fanout [llength [get_pins -quiet -leaf -of_objects $net -filter \
        {DIRECTION == IN}]]
    if {$fanout > $max_fanout} {
        set max_fanout $fanout
        set max_fanout_net $net_name
    }
}

set out_ready_max_fanout 0
foreach net [get_nets -quiet -hierarchical -filter {NAME =~ *out_ready*}] {
    set fanout [llength [get_pins -quiet -leaf -of_objects $net -filter \
        {DIRECTION == IN}]]
    if {$fanout > $out_ready_max_fanout} {
        set out_ready_max_fanout $fanout
    }
}

set partial_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == PARTIAL}]
set bad_partial {}
set accepted_clock_partial {}
set accepted_clock_partial_detail {}
foreach net $partial_all {
    set objects [concat [get_pins -quiet -of_objects $net] \
        [get_ports -quiet -of_objects $net]]
    set clocks [get_clocks -quiet -of_objects $objects]
    if {[llength $clocks] != 0} {
        lappend accepted_clock_partial $net
        lappend accepted_clock_partial_detail [format \
            "name=%s type=%s parent=%s ports=%s clocks=%s" \
            [get_property NAME $net] [get_property TYPE $net] \
            [get_property PARENT $net] \
            [get_property NAME [get_ports -quiet -of_objects $net]] \
            [get_property NAME $clocks]]
    } else {
        lappend bad_partial $net
    }
}

set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
    }
}
set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_paths] == 0 || [llength $hold_paths] == 0} {
    error "audit found no setup or hold timing path"
}
set wns [get_property SLACK [lindex $setup_paths 0]]
set whs [get_property SLACK [lindex $hold_paths 0]]
set status [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $max_fanout == 292 && $out_ready_max_fanout == 9 &&
    [llength $partial_all] == 2 &&
    [llength $accepted_clock_partial] == 2 &&
    [llength $bad_partial] == 0 && $data_bufg == 0 ?
    "DOWN_ELASTIC2_READ_ONLY_AUDIT_PASS" : "FAIL"}]

set fp [open [file join $artifact fanout_route_audit.txt] w]
foreach {key value} [list tool [version -short] source_checkpoint $dcp \
    wns_ns $wns whs_ns $whs \
    maximum_nonclock_nonconstant_queue_net_fanout $max_fanout \
    maximum_nonclock_nonconstant_queue_net_name $max_fanout_net \
    maximum_out_ready_named_net_fanout $out_ready_max_fanout \
    partial_nets_total [llength $partial_all] \
    accepted_clock_partial_nets [llength $accepted_clock_partial] \
    accepted_clock_partial_detail $accepted_clock_partial_detail \
    bad_partial_nets [llength $bad_partial] data_bufg $data_bufg \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "DOWN_ELASTIC2_AUDIT MAX_NONCLOCK=$max_fanout NET=$max_fanout_net OUT_READY=$out_ready_max_fanout BAD_PARTIAL=[llength $bad_partial] STATUS=$status"
if {$status ne "DOWN_ELASTIC2_READ_ONLY_AUDIT_PASS"} {
    error "down elastic2 read-only audit failed"
}
close_project
