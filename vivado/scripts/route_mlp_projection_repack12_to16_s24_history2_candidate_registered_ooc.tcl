set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc_harness
set xdc_path [file join $root vivado constraints \
    mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc_150mhz.xdc]
set harness_path [file join $root rtl mlp \
    hap_mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc_harness.sv]
set dut_path [file join $root rtl mlp \
    hap_mlp_projection_repack12_to16_s24_history2_candidate.sv]
file mkdir $out

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

proc report_pair {out stem from_set to_set} {
    set common [list -max_paths 100 -path_type full_clock_expanded]
    if {[llength $from_set] != 0} {lappend common -from $from_set}
    if {[llength $to_set] != 0} {lappend common -to $to_set}
    report_timing -delay_type max {*}$common -file \
        [file join $out ${stem}_setup_worst100.rpt]
    report_timing -delay_type min {*}$common -file \
        [file join $out ${stem}_hold_worst100.rpt]
}

proc route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    if {$required} {error "Required route-status row '$label' is missing"}
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

# Fail closed on timing-policy drift.  Build the expression from fragments so
# this source can audit itself without the expression becoming a match.
set audit_text ""
foreach path [list $xdc_path [file normalize [info script]]] {
    set fh [open $path r]
    append audit_text [read $fh]
    close $fh
}
set forbidden_pattern [join [list \
    "set_false" "_path|set_multi" "cycle_path|-data" "path_only|set_clock" \
    "_groups"] ""]
set forbidden_count [regexp -all -nocase $forbidden_pattern $audit_text]
if {$forbidden_count != 0} {
    error "history2 registered OOC contains a forbidden timing waiver"
}

create_project -in_memory -part $part
read_verilog -sv $dut_path
read_verilog -sv $harness_path
read_xdc $xdc_path
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set src_count [require_count source_proxy_ff $src 4637]
set sink_count [require_count sink_proxy_ff $sink 6240]
require_count history2_dut [get_cells -quiet u_dut] 1
set top_ports [get_ports -quiet]
set nonclock_top_ports [get_ports -quiet -filter {NAME != clk}]
require_count top_port_count $top_ports 1
require_count nonclock_top_port_count $nonclock_top_ports 0

set dut_ff_synth [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]
set dut_srl_synth [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == SRL16E}]
require_count candidate_history_srl16e $dut_srl_synth 4608
if {[llength $dut_ff_synth] == 0} {error "history2 DUT contains no FF"}

opt_design -directive ExploreWithRemap

# Never promote a wide DUT data/control net onto a global clock resource.
set dut_nonclock_nets [get_nets -quiet -hierarchical -filter \
    {NAME =~ u_dut/*}]
if {[llength $dut_nonclock_nets] != 0} {
    set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
}

place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

set dut_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]
set dut_srl [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == SRL16E}]
set dut_seq [concat $dut_ff $dut_srl]
if {[llength $dut_seq] == 0} {error "history2 DUT sequential set is empty"}

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

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation \
    -file [file join $out timing_summary.rpt]
report_pair $out source_to_dut $src $dut_seq
report_pair $out dut_internal $dut_seq $dut_seq
report_pair $out dut_to_sink $dut_seq $sink
report_pair $out source_to_sink $src $sink
report_utilization -hierarchical -hierarchical_depth 6 \
    -file [file join $out utilization_hierarchical.rpt]
report_utilization -file [file join $out utilization.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
set route_text [report_route_status -return_string]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_clock_utilization -file [file join $out clock_utilization.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
report_design_analysis -congestion -file [file join $out congestion.rpt]
write_checkpoint -force [file join $out post_route.dcp]

# `report_utilization` is the canonical CLB resource accounting.  It adjusts
# for LUT combining and, in this design, packs two SRL16E primitives into one
# physical shift-register LUT.  Preserve this standard accounting separately
# from the raw primitive counts below; the two metrics must not be added or
# described as the same quantity.
lassign [hierarchy_util_row \
    [file join $out utilization_hierarchical.rpt] u_dut] \
    dut_clb_lut_standard dut_lut_logic_standard dut_lutram_standard \
    dut_srl_lut_standard dut_clb_register_standard \
    dut_ramb36_standard dut_ramb18_standard dut_uram_standard \
    dut_dsp_standard

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
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]

set dut_lut_logic [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_srl_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == SRL16E}]]
set dut_clb_lut_total [expr {$dut_lut_logic + $dut_srl_count}]
set dut_ff_count [llength $dut_ff]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set total_lut_logic [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ LUT*}]]
set total_srl [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == SRL16E}]]
set total_ff [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME =~ FD*}]]

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

set congestion_fh [open [file join $out congestion.rpt] r]
set congestion_text [read $congestion_fh]
close $congestion_fh
set congestion_level6_or_higher 0
foreach line [split $congestion_text "\n"] {
    if {[regexp \
            {^[[:space:]]*\|[^|]*\|[^|]*\|[[:space:]]*([0-9]+)[[:space:]]*\|} \
            $line -> level] && $level >= 6} {
        incr congestion_level6_or_higher
    }
}

set unconstrained 0
set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -return_string]
foreach line [split $timing_text "\n"] {
    if {[regexp -nocase \
            {Unconstrained Paths[[:space:]]+([1-9][0-9]*)} \
            $line -> count]} {
        incr unconstrained $count
    }
}

# This registered harness gives both boundaries the complete 6.667 ns cycle.
# It reserves no integration-shell delay, so even a clean result remains an
# isolated physical diagnostic and is not a production timing signoff.
set shell_budget_ns 0.000
set shell_budget_complete 0
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $source_to_dut_wns >= 0.0 && $source_to_dut_whs >= 0.0 &&
    $dut_internal_wns >= 0.0 && $dut_internal_whs >= 0.0 &&
    $dut_to_sink_wns >= 0.0 && $dut_to_sink_whs >= 0.0 &&
    $source_to_sink_wns >= 0.0 && $source_to_sink_whs >= 0.0}]
set route_clean [expr {$route_errors == 0 && $unrouted_rows == 0 &&
    $unrouted_pins == 0 && $resource_conflicts == 0 && $antennas == 0 &&
    [llength $bad_partial] == 0 && $conflict_status == 0}]
set resources_ok [expr {$dut_srl_count == 4608 && $dut_dsp == 0 &&
    $dut_ramb36 == 0 && $dut_ramb18 == 0 && $dut_uram == 0 &&
    $data_bufg == 0}]
set status [expr {$timing_ok && $route_clean && $drc_errors == 0 &&
    $resources_ok && $congestion_level6_or_higher == 0 &&
    $unconstrained == 0 && $forbidden_count == 0 ?
    "REGISTERED_OOC_DIAGNOSTIC_PASS_NO_SHELL_BUDGET" :
    "REGISTERED_OOC_DIAGNOSTIC_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part top $top threads_max 8 \
    clock_period_ns 6.667 clock_mhz 150 \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    boundary_proxy_ff_total [expr {$src_count + $sink_count}] \
    boundary_shell_budget_ns $shell_budget_ns \
    boundary_shell_budget_complete $shell_budget_complete \
    evidence_class REGISTERED_OOC_PHYSICAL_DIAGNOSTIC_ONLY \
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
    dut_lut_logic_primitives $dut_lut_logic \
    dut_srl16e_primitives $dut_srl_count \
    dut_clb_lut_primitive_total $dut_clb_lut_total \
    dut_ff_primitives $dut_ff_count dut_dsp48e2 $dut_dsp \
    dut_ramb36e2 $dut_ramb36 dut_ramb18e2 $dut_ramb18 \
    dut_uram288 $dut_uram total_lut_logic_primitives $total_lut_logic \
    total_srl16e_primitives $total_srl total_ff_primitives $total_ff \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial_total [llength $partial_all] \
    accepted_ooc_clock_partial [llength $accepted_clock_partial] \
    bad_partial_nets [llength $bad_partial] conflict_nets $conflict_status \
    drc_errors $drc_errors unconstrained_paths $unconstrained \
    congestion_level6_or_higher_windows $congestion_level6_or_higher \
    forbidden_timing_exception_count $forbidden_count status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "HISTORY2_REGISTERED_OOC_DIAGNOSTIC WNS=$wns WHS=$whs ROUTE_ERRORS=$route_errors UNROUTED=$unrouted_rows DRC_ERRORS=$drc_errors STANDARD_CLB_LUT=$dut_clb_lut_standard LOGIC_LUT_PRIMITIVE=$dut_lut_logic SRL16E_PRIMITIVE=$dut_srl_count FF=$dut_ff_count L6PLUS=$congestion_level6_or_higher STATUS=$status"
if {$status ne "REGISTERED_OOC_DIAGNOSTIC_PASS_NO_SHELL_BUDGET"} {
    error "history2 candidate registered OOC diagnostic gate failed"
}
close_project
