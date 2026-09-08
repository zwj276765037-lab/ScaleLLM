set artifact [file normalize $::env(HAP_ROUTE_ARTIFACT)]
set dcp [file join $artifact post_route.dcp]
if {![file exists $dcp]} {error "missing post-route checkpoint $dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set_param general.maxThreads 8

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc first_slack {delay from_set to_set label} {
    set args [list -quiet -delay_type $delay -max_paths 1]
    if {[llength $from_set] != 0} {lappend args -from $from_set}
    if {[llength $to_set] != 0} {lappend args -to $to_set}
    set paths [get_timing_paths {*}$args]
    if {[llength $paths] == 0} {error "$label returned no timing path"}
    return [get_property SLACK [lindex $paths 0]]
}

proc route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    if {$required} {error "required route-status row '$label' is missing"}
    return 0
}

proc hierarchy_util_row {path instance} {
    set fh [open $path r]
    set text [read $fh]
    close $fh
    foreach line [split $text "\n"] {
        set fields [split $line "|"]
        if {[llength $fields] < 13 ||
            [string trim [lindex $fields 1]] ne $instance} {
            continue
        }
        set result {}
        for {set index 3} {$index <= 11} {incr index} {
            set value [string trim [lindex $fields $index]]
            if {![string is integer -strict $value]} {
                error "non-integer utilization field for $instance: $value"
            }
            lappend result $value
        }
        return $result
    }
    error "utilization hierarchy row '$instance' is missing"
}

open_checkpoint $dcp
set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set src_count [require_count source_proxy_ff $src 4637]
set sink_count [require_count sink_proxy_ff $sink 6240]
require_count history2_dut [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1
require_count nonclock_top_port_count \
    [get_ports -quiet -filter {NAME != clk}] 0

set dut_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]
set dut_srl [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == SRL16E}]
set dut_seq [concat $dut_ff $dut_srl]
require_count candidate_ff $dut_ff 6261
require_count candidate_srl16e $dut_srl 4608

set wns [first_slack max {} {} global_setup]
set whs [first_slack min {} {} global_hold]
set source_to_dut_wns [first_slack max $src $dut_seq source_to_dut_setup]
set source_to_dut_whs [first_slack min $src $dut_seq source_to_dut_hold]
set dut_internal_wns [first_slack max $dut_seq $dut_seq dut_internal_setup]
set dut_internal_whs [first_slack min $dut_seq $dut_seq dut_internal_hold]
set dut_to_sink_wns [first_slack max $dut_seq $sink dut_to_sink_setup]
set dut_to_sink_whs [first_slack min $dut_seq $sink dut_to_sink_hold]
set source_to_sink_wns [first_slack max $src $sink source_to_sink_setup]
set source_to_sink_whs [first_slack min $src $sink source_to_sink_hold]

set util_hier [file join $artifact utilization_hierarchical_audit.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file $util_hier
lassign [hierarchy_util_row $util_hier u_dut] \
    dut_clb_lut_standard dut_lut_logic_standard dut_lutram_standard \
    dut_srl_lut_standard dut_clb_register_standard \
    dut_ramb36_standard dut_ramb18_standard dut_uram_standard \
    dut_dsp_standard

set dut_lut_primitive [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_srl_primitive [llength $dut_srl]
set dut_ff_primitive [llength $dut_ff]
set dut_dsp_primitive [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_ramb36_primitive [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18_primitive [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram_primitive [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]

set all_bufg [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}]
set clock_bufg 0
set data_bufg 0
foreach cell $all_bufg {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set route_text [report_route_status -return_string]
report_route_status -file [file join $artifact route_status_audit.rpt]
set route_errors [route_row $route_text "# of nets with routing errors" 1]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]
set partial_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == UNROUTED}]
set bad_partial {}
set accepted_clock_partial {}
foreach net $partial_all {
    set parent [get_property PARENT $net]
    set type [get_property TYPE $net]
    set ports [lsort -unique [get_property NAME \
        [get_ports -quiet -of_objects $net]]]
    if {$type eq "LOCAL_CLOCK" && $parent eq "clk" &&
        [llength $ports] == 1 && [lindex $ports 0] eq "clk"} {
        lappend accepted_clock_partial $net
    } else {
        lappend bad_partial $net
    }
}
set conflict_status [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]

report_drc -file [file join $artifact drc_audit.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]

set exceptions_path [file join $artifact exceptions_coverage_audit.rpt]
report_exceptions -coverage -file $exceptions_path
set fh [open $exceptions_path r]
set exceptions_text [read $fh]
close $fh
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exceptions_text] >= 0}]

set congestion_path [file join $artifact congestion_audit.rpt]
report_design_analysis -congestion -file $congestion_path
set fh [open $congestion_path r]
set congestion_text [read $fh]
close $fh
set no_placer_above5 [expr {[string first \
    "No congestion windows are found above level 5" $congestion_text] >= 0}]
set no_router_above5 [expr {[string first \
    "No effective congestion windows are found above level 5" \
    $congestion_text] >= 0}]

set timing_text [report_timing_summary -delay_type min_max \
    -report_unconstrained -return_string]
set unconstrained 0
foreach line [split $timing_text "\n"] {
    if {[regexp -nocase \
            {Unconstrained Paths[[:space:]]+([1-9][0-9]*)} \
            $line -> count]} {
        incr unconstrained $count
    }
}

set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $source_to_dut_wns >= 0.0 && $source_to_dut_whs >= 0.0 &&
    $dut_internal_wns >= 0.0 && $dut_internal_whs >= 0.0 &&
    $dut_to_sink_wns >= 0.0 && $dut_to_sink_whs >= 0.0 &&
    $source_to_sink_wns >= 0.0 && $source_to_sink_whs >= 0.0}]
set resources_ok [expr {$dut_clb_lut_standard == 8503 &&
    $dut_lut_logic_standard == 6199 && $dut_lutram_standard == 0 &&
    $dut_srl_lut_standard == 2304 && $dut_clb_register_standard == 6261 &&
    $dut_dsp_standard == 0 && $dut_ramb36_standard == 0 &&
    $dut_ramb18_standard == 0 && $dut_uram_standard == 0 &&
    $dut_lut_primitive == 6216 && $dut_srl_primitive == 4608 &&
    $dut_ff_primitive == 6261 && $dut_dsp_primitive == 0 &&
    $dut_ramb36_primitive == 0 && $dut_ramb18_primitive == 0 &&
    $dut_uram_primitive == 0 && $data_bufg == 0}]
set route_ok [expr {$route_errors == 0 && $explicit_gaps == 1 &&
    $unrouted_rows == 0 && $unrouted_pins == 0 &&
    $resource_conflicts == 0 && $antennas == 0 &&
    [llength $partial_all] == 2 &&
    [llength $accepted_clock_partial] == 2 &&
    [llength $bad_partial] == 0 && $conflict_status == 0}]
set status [expr {$timing_ok && $resources_ok && $route_ok &&
    $drc_errors == 0 && $no_timing_exceptions &&
    $no_placer_above5 && $no_router_above5 && $unconstrained == 0 ?
    "POST_ROUTE_CHECKPOINT_AUDIT_PASS_DIAGNOSTIC_NO_SHELL_BUDGET" :
    "POST_ROUTE_CHECKPOINT_AUDIT_FAIL"}]

set fp [open [file join $artifact audit_summary.txt] w]
foreach {key value} [list \
    tool [version -short] source_checkpoint $dcp \
    evidence_class REGISTERED_OOC_PHYSICAL_DIAGNOSTIC_ONLY \
    boundary_shell_budget_ns 0.000 boundary_shell_budget_complete 0 \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    wns_ns $wns whs_ns $whs \
    source_to_dut_wns_ns $source_to_dut_wns \
    source_to_dut_whs_ns $source_to_dut_whs \
    dut_internal_wns_ns $dut_internal_wns \
    dut_internal_whs_ns $dut_internal_whs \
    dut_to_sink_wns_ns $dut_to_sink_wns \
    dut_to_sink_whs_ns $dut_to_sink_whs \
    source_to_sink_wns_ns $source_to_sink_wns \
    source_to_sink_whs_ns $source_to_sink_whs \
    dut_clb_lut_standard $dut_clb_lut_standard \
    dut_lut_as_logic_standard $dut_lut_logic_standard \
    dut_lutram_standard $dut_lutram_standard \
    dut_lut_as_shift_register_standard $dut_srl_lut_standard \
    dut_clb_register_standard $dut_clb_register_standard \
    dut_lut_primitives $dut_lut_primitive \
    dut_srl16e_primitives $dut_srl_primitive \
    dut_ff_primitives $dut_ff_primitive dut_dsp48e2 $dut_dsp_primitive \
    dut_ramb36e2 $dut_ramb36_primitive \
    dut_ramb18e2 $dut_ramb18_primitive dut_uram288 $dut_uram_primitive \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial_total [llength $partial_all] \
    accepted_ooc_clock_partial [llength $accepted_clock_partial] \
    bad_partial_nets [llength $bad_partial] conflict_nets $conflict_status \
    drc_errors $drc_errors no_timing_exceptions $no_timing_exceptions \
    unconstrained_paths $unconstrained \
    no_placer_congestion_above_level5 $no_placer_above5 \
    no_router_congestion_above_level5 $no_router_above5 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "HISTORY2_CHECKPOINT_AUDIT WNS=$wns WHS=$whs STANDARD_CLB_LUT=$dut_clb_lut_standard LOGIC_LUT_PRIMITIVE=$dut_lut_primitive SRL16E_PRIMITIVE=$dut_srl_primitive ROUTE_ERRORS=$route_errors DRC_ERRORS=$drc_errors STATUS=$status"
if {$status ne \
        "POST_ROUTE_CHECKPOINT_AUDIT_PASS_DIAGNOSTIC_NO_SHELL_BUDGET"} {
    error "history2 registered OOC checkpoint audit failed"
}
close_project
