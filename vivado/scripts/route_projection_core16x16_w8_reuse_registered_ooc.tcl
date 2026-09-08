set out [file normalize $::env(HAP_REPORT_DIR)]
set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
file mkdir $out

if {![file exists $input_dcp]} {error "missing input DCP $input_dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set actual_dcp_sha [lindex [exec sha256sum -- $input_dcp] 0]
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    $actual_dcp_sha ne $expected_dcp_sha} {
    error "projection route input DCP hash mismatch"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "projection route input manifest hash is invalid"
}
set jobs 32
if {[info exists ::env(HAP_JOBS)]} {set jobs $::env(HAP_JOBS)}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32, got '$jobs'"
}
set place_directive AltSpreadLogic_high
if {[info exists ::env(HAP_PLACE_DIRECTIVE)]} {
    set place_directive $::env(HAP_PLACE_DIRECTIVE)
}
set pre_route_physopt_directive AggressiveExplore
if {[info exists ::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE)]} {
    set pre_route_physopt_directive $::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE)
}
set route_directive AggressiveExplore
if {[info exists ::env(HAP_ROUTE_DIRECTIVE)]} {
    set route_directive $::env(HAP_ROUTE_DIRECTIVE)
}
set post_route_physopt_directive AggressiveExplore
if {[info exists ::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE)]} {
    set post_route_physopt_directive $::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE)
}
set max_post_place_level5_windows 1
if {[info exists ::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)]} {
    set max_post_place_level5_windows \
        $::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)
}
if {![string is integer -strict $max_post_place_level5_windows] ||
    $max_post_place_level5_windows < 0 ||
    $max_post_place_level5_windows > 100} {
    error "HAP_MAX_POST_PLACE_LEVEL5_WINDOWS must be an integer in 0..100"
}
set_param general.maxThreads $jobs

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc get_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} {return -999.0}
    return [get_property SLACK [lindex $paths 0]]
}

proc check_timing_count {text check_name} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $check_name]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "check_timing category '$check_name' is missing"
    }
    return $count
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

proc read_text {path} {
    set fp [open $path r]
    set result [read $fp]
    close $fp
    return $result
}

open_checkpoint $input_dcp
set expected_part xcvu9p-flga2104-2L-e
set expected_top hap_projection_core16x16_w8_reuse_registered_ooc_harness
set actual_part [get_property PART [current_project]]
set checkpoint_design [current_design]
if {$actual_part ne $expected_part} {
    error "part mismatch expected=$expected_part actual=$actual_part"
}

# open_checkpoint exposes a checkpoint label such as checkpoint_post_synth as
# current_design.  Authenticate the HDL harness with the exact structural
# fingerprint below and retain the checkpoint label only as evidence.

set src_count [require_count source_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ src_r_reg* && REF_NAME =~ FD*}] 10600]
set sink_count [require_count sink_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ sink_r_reg* && REF_NAME =~ FD*}] 3327]
require_count dut_instance [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1

opt_design -directive ExploreWithRemap

# Keep high-fanout DUT data and control nets off global clock resources.
set dut_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
if {[llength $dut_nets] != 0} {
    set_property CLOCK_BUFFER_TYPE NONE $dut_nets
}

set floorplan_plan [hap_projection_ooc_floorplan::discover]
hap_projection_ooc_floorplan::apply $floorplan_plan
set pre_place_pblock_audit \
    [hap_projection_ooc_floorplan::audit_pblocks $floorplan_plan 1]
hap_projection_ooc_floorplan::write_plan $floorplan_plan \
    [file join $out floorplan_pre_place.txt] \
    PROJECTION_REUSE_OOC_FLOORPLAN_PRE_PLACE_PASS

report_drc -file [file join $out drc_post_opt.rpt]
set post_opt_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
if {$post_opt_drc_errors != 0} {
    error "post-opt DRC has $post_opt_drc_errors Error violations"
}
write_checkpoint -force [file join $out post_opt.dcp]

place_design -directive $place_directive
write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]
set post_place_plan [hap_projection_ooc_floorplan::discover]
set post_place_region0_localization_ok \
    [hap_projection_ooc_floorplan::region0_input_localization_ok \
        $post_place_plan]
set post_place_region3_localization_ok \
    [hap_projection_ooc_floorplan::region3_input_localization_ok \
        $post_place_plan]
set post_place_owner_region2_weight_anchor_ok \
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
        $post_place_plan]
set post_place_metrics \
    [hap_projection_ooc_floorplan::audit_placement $post_place_plan]
hap_projection_ooc_floorplan::write_placement $post_place_metrics \
    [file join $out floorplan_post_place.txt] \
    PROJECTION_REUSE_OOC_FLOORPLAN_POST_PLACE_PASS
if {![dict get $post_place_metrics ok]} {
    error "projection reuse OOC post-place SLR floorplan failed"
}
report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation \
    -file [file join $out timing_post_place.rpt]
set post_place_congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $post_place_congestion_path
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
report_drc -file [file join $out drc_post_place.rpt]
set post_place_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set post_place_data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr post_place_data_bufg
    }
}
set post_place_congestion_text [read_text $post_place_congestion_path]
set post_place_congestion_counts \
    [hap_projection_ooc_floorplan::congestion_level6_counts \
        $post_place_congestion_text]
set post_place_level5_counts \
    [hap_projection_ooc_floorplan::congestion_counts_at_or_above \
        $post_place_congestion_text 5]
set post_place_placer_level6 \
    [dict get $post_place_congestion_counts placer]
set post_place_router_level6 \
    [dict get $post_place_congestion_counts router]
set post_place_level6_total \
    [dict get $post_place_congestion_counts total]
set post_place_placer_level5 [dict get $post_place_level5_counts placer]
set post_place_router_level5 [dict get $post_place_level5_counts router]
set post_place_level5_total [dict get $post_place_level5_counts total]
set post_place_strict_gate_ok [expr {
    [dict get $post_place_metrics ok] && $post_place_drc_errors == 0 &&
    $post_place_data_bufg == 0 && $post_place_level6_total == 0 &&
    $post_place_region0_localization_ok &&
    $post_place_region3_localization_ok &&
    $post_place_owner_region2_weight_anchor_ok}]
set post_place_level5_screen_ok [expr {
    $post_place_level5_total <= $max_post_place_level5_windows}]
set post_place_fast_gate_ok [expr {
    $post_place_strict_gate_ok && $post_place_level5_screen_ok}]
set post_place_gate [open [file join $out post_place_fast_gate.txt] w]
foreach {key value} [list \
        stage REGISTERED_OOC_POST_PLACE_FAST_GATE \
        floorplan_ok [dict get $post_place_metrics ok] \
        drc_errors $post_place_drc_errors data_bufg $post_place_data_bufg \
        placer_level6_or_higher_windows $post_place_placer_level6 \
        router_level6_or_higher_windows $post_place_router_level6 \
        level6_or_higher_congestion_windows $post_place_level6_total \
        region0_input_localization_ok \
            $post_place_region0_localization_ok \
        region3_input_localization_ok \
            $post_place_region3_localization_ok \
        owner_region2_weight_anchor_ok \
            $post_place_owner_region2_weight_anchor_ok \
        placer_level5_or_higher_windows $post_place_placer_level5 \
        router_level5_or_higher_windows $post_place_router_level5 \
        level5_or_higher_congestion_windows $post_place_level5_total \
        max_level5_or_higher_congestion_windows \
            $max_post_place_level5_windows \
        strict_gate_ok $post_place_strict_gate_ok \
        level5_screen_ok $post_place_level5_screen_ok \
        route_authorized $post_place_fast_gate_ok \
        status [expr {$post_place_fast_gate_ok ? "PASS" : "FAIL"}]] {
    puts $post_place_gate "$key=$value"
}
close $post_place_gate
if {!$post_place_fast_gate_ok} {
    error "projection reuse OOC post-place fast gate failed"
}
write_checkpoint -force [file join $out post_place.dcp]

phys_opt_design -directive $pre_route_physopt_directive
route_design -directive $route_directive
write_checkpoint -force [file join $out post_route_before_physopt.dcp]
phys_opt_design -directive $post_route_physopt_directive

set final_floorplan_plan [hap_projection_ooc_floorplan::discover]
set final_pblock_audit \
    [hap_projection_ooc_floorplan::audit_pblocks $final_floorplan_plan 0]
set final_floorplan_metrics \
    [hap_projection_ooc_floorplan::audit_placement $final_floorplan_plan]
set final_region0_localization_ok \
    [hap_projection_ooc_floorplan::region0_input_localization_ok \
        $final_floorplan_plan]
set final_region3_localization_ok \
    [hap_projection_ooc_floorplan::region3_input_localization_ok \
        $final_floorplan_plan]
set final_owner_region2_weight_anchor_ok \
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
        $final_floorplan_plan]
hap_projection_ooc_floorplan::write_plan $final_floorplan_plan \
    [file join $out floorplan_post_route_selectors.txt] \
    PROJECTION_REUSE_OOC_FLOORPLAN_POST_ROUTE_SELECTORS_PASS
hap_projection_ooc_floorplan::write_placement $final_floorplan_metrics \
    [file join $out floorplan_post_route.txt] \
    PROJECTION_REUSE_OOC_FLOORPLAN_POST_ROUTE_PASS
set floorplan_ok [expr {[dict get $final_floorplan_metrics ok] &&
    [dict get $final_floorplan_plan center_region1_bisect_exact_cover] == 1 &&
    [dict get $final_floorplan_plan center_region1_dsp_stripe_exact_cover] == 1 &&
    $final_region0_localization_ok &&
    $final_region3_localization_ok &&
    $final_owner_region2_weight_anchor_ok}]

set lanes [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && (REF_NAME == hap_a8w8_group32_lane_s42 || \
     ORIG_REF_NAME == hap_a8w8_group32_lane_s42)}]
set dual_accumulators [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && (REF_NAME == hap_linear_tile_accum_dual_s42 || \
     ORIG_REF_NAME == hap_linear_tile_accum_dual_s42)}]
set lane_count [require_count attention_lane_instances $lanes 128]
set dual_accumulator_count [require_count local_dual_accumulator_instances \
    $dual_accumulators 6]
set accum_context_count [expr {$dual_accumulator_count * 2}]
if {$accum_context_count != 12} {
    error "local accumulator context mismatch: expected=12 actual=$accum_context_count"
}

set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set array_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_array/* && REF_NAME == DSP48E2}]]
set frontend_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_frontend/* && REF_NAME == DSP48E2}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set tfp [open [file join $out timing_post_route.rpt] w]
puts $tfp $timing_text
close $tfp
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_text no_input_delay]
set no_output_delay [check_timing_count $timing_text no_output_delay]
set partial_input_delay [check_timing_count $timing_text partial_input_delay]
set partial_output_delay [check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 && \
    $no_input_delay == 0 && $no_output_delay == 0 && \
    $partial_input_delay == 0 && $partial_output_delay == 0}]

report_utilization -file [file join $out utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 20 -file \
    [file join $out utilization_hier_post_route.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_route.rpt]
set route_text [report_route_status -return_string]
report_route_status -file [file join $out route_status_post_route.rpt]
report_drc -file [file join $out drc_post_route.rpt]
report_clock_utilization -file \
    [file join $out clock_utilization_post_route.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage_post_route.rpt]
report_design_analysis -congestion -file \
    [file join $out congestion_post_route.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set route_errors [route_row $route_text "# of nets with routing errors" 1]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text \
    "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]
set partial_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED || \
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

set exception_text [read_text \
    [file join $out exceptions_coverage_post_route.rpt]]
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exception_text] >= 0}]
set congestion_text [read_text [file join $out congestion_post_route.rpt]]
set congestion_counts \
    [hap_projection_ooc_floorplan::congestion_level6_counts $congestion_text]
set placer_level6 [dict get $congestion_counts placer]
set router_level6 [dict get $congestion_counts router]
set level6_total [dict get $congestion_counts total]
set no_placer_above5 [expr {$placer_level6 == 0}]
set no_router_above5 [expr {$router_level6 == 0}]

set wns [get_slack max]
set whs [get_slack min]
set structural_ok [expr {$lane_count == 128 && \
    $accum_context_count == 12 && $dut_dsp == 2240 && \
    $array_dsp == 2176 && $frontend_dsp == 64 && \
    $dut_ramb36 == 31 && $dut_ramb18 == 4 && $dut_uram == 0}]
set route_clean [expr {$route_errors == 0 && $unrouted_rows == 0 && \
    $unrouted_pins == 0 && $resource_conflicts == 0 && $antennas == 0 && \
    [llength $bad_partial] == 0 && $conflict_status == 0}]
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set congestion_ok [expr {$no_placer_above5 && $no_router_above5}]
set status [expr {$structural_ok && $timing_ok && $route_clean && \
    $post_opt_drc_errors == 0 && $drc_errors == 0 && $data_bufg == 0 && \
    $no_timing_exceptions && $timing_coverage_ok && $congestion_ok && \
    $floorplan_ok ? \
    "PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $actual_part \
    top $expected_top checkpoint_design $checkpoint_design \
    stage REGISTERED_OOC_POST_ROUTE clock_mhz 150 \
    input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 $input_manifest_sha \
    jobs $jobs place_directive $place_directive \
    max_post_place_level5_windows $max_post_place_level5_windows \
    pre_route_physopt_directive $pre_route_physopt_directive \
    route_directive $route_directive \
    post_route_physopt_directive $post_route_physopt_directive \
    input_dcp $input_dcp source_proxy_ff $src_count sink_proxy_ff $sink_count \
    attention_lane_instances $lane_count \
    local_dual_accumulator_instances $dual_accumulator_count \
    local_accumulator_contexts $accum_context_count \
    dut_dsp48e2 $dut_dsp array_dsp48e2 $array_dsp \
    frontend_dsp48e2 $frontend_dsp dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_uram288 $dut_uram \
    wns_ns $wns whs_ns $whs timing_ok $timing_ok \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial_total [llength $partial_all] \
    accepted_ooc_clock_partial [llength $accepted_clock_partial] \
    bad_partial_nets [llength $bad_partial] conflict_nets $conflict_status \
    post_opt_drc_errors $post_opt_drc_errors drc_errors $drc_errors \
    no_timing_exceptions $no_timing_exceptions \
    no_clock_endpoints $no_clock \
    unconstrained_internal_endpoints $unconstrained \
    no_input_delay_endpoints $no_input_delay \
    no_output_delay_endpoints $no_output_delay \
    partial_input_delay_endpoints $partial_input_delay \
    partial_output_delay_endpoints $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok \
    pblock_count [dict get $final_pblock_audit pblock_count] \
    floorplan_dut_primitives \
        [llength [dict get $final_floorplan_plan dut_primitives]] \
    floorplan_left_primitives \
        [llength [dict get $final_floorplan_plan left_primitives]] \
    floorplan_frontend_primitives \
        [llength [dict get $final_floorplan_plan frontend_primitives]] \
    floorplan_center_primitives \
        [llength [dict get $final_floorplan_plan center_primitives]] \
    floorplan_center_region0_frontend_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region0_frontend_primitives]] \
    floorplan_center_region1_cols4_5_lane_roots \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols4_5_lane_roots]] \
    floorplan_center_region1_cols6_7_lane_roots \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols6_7_lane_roots]] \
    floorplan_center_region1_cols4_5_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols4_5_primitives]] \
    floorplan_center_region1_cols6_7_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols6_7_primitives]] \
    floorplan_center_region1_residual_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_residual_primitives]] \
    floorplan_center_region1_cols4_5_dsp_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols4_5_dsp_primitives]] \
    floorplan_center_region1_cols6_7_dsp_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_cols6_7_dsp_primitives]] \
    floorplan_center_region1_logic_residual_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region1_logic_residual_primitives]] \
    floorplan_center_region1_logic_residual_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan \
                center_region1_logic_residual_primitives] DSP48E2] \
    floorplan_center_region1_bisect_exact_cover \
        [dict get $final_floorplan_plan center_region1_bisect_exact_cover] \
    floorplan_center_region1_dsp_stripe_exact_cover \
        [dict get $final_floorplan_plan \
            center_region1_dsp_stripe_exact_cover] \
    floorplan_right_primitives \
        [llength [dict get $final_floorplan_plan right_primitives]] \
    floorplan_owner_primitives \
        [llength [dict get $final_floorplan_plan owner_primitives]] \
    floorplan_owner_floorplan_primitives \
        [llength [dict get $final_floorplan_plan \
            owner_floorplan_primitives]] \
    floorplan_owner_residual_floorplan_primitives \
        [llength [dict get $final_floorplan_plan \
            owner_residual_floorplan_primitives]] \
    floorplan_owner_region2_weight_ff_primitives \
        [llength [dict get $final_floorplan_plan \
            owner_region2_weight_ff_primitives]] \
    floorplan_owner_region2_weight_lut_primitives \
        [llength [dict get $final_floorplan_plan \
            owner_region2_weight_lut_primitives]] \
    floorplan_owner_region2_weight_primitives \
        [llength [dict get $final_floorplan_plan \
            owner_region2_weight_primitives]] \
    floorplan_owner_region2_weight_exact_cover \
        [dict get $final_floorplan_plan \
            owner_region2_weight_exact_cover] \
    floorplan_region0_input_activation_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_activation_primitives]] \
    floorplan_region0_input_zero_point_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_zero_point_primitives]] \
    floorplan_region0_input_weight_ff_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_weight_ff_primitives]] \
    floorplan_region0_input_weight_lut_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_weight_lut_primitives]] \
    floorplan_region0_input_weight_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_weight_primitives]] \
    floorplan_region0_input_primitives \
        [llength [dict get $final_floorplan_plan \
            region0_input_primitives]] \
    floorplan_region0_input_fdre \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan region0_input_primitives] FDRE] \
    floorplan_region0_input_lut3 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan region0_input_primitives] LUT3] \
    floorplan_region0_input_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan \
                region0_input_primitives] DSP48E2] \
    floorplan_owner_region0_input_exact_cover \
        [dict get $final_floorplan_plan owner_region0_input_exact_cover] \
    floorplan_region0_input_localization_ok \
        $final_region0_localization_ok \
    floorplan_center_region3_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region3_primitives]] \
    floorplan_center_region3_floorplan_primitives \
        [llength [dict get $final_floorplan_plan \
            center_region3_floorplan_primitives]] \
    floorplan_region3_input_activation_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_input_activation_primitives]] \
    floorplan_region3_input_zero_point_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_input_zero_point_primitives]] \
    floorplan_region3_input_weight_ff_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_input_weight_ff_primitives]] \
    floorplan_region3_input_weight_lut_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_input_weight_lut_primitives]] \
    floorplan_region3_owner_weight_ff_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_owner_weight_ff_primitives]] \
    floorplan_region3_owner_weight_lut_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_owner_weight_lut_primitives]] \
    floorplan_region3_input_primitives \
        [llength [dict get $final_floorplan_plan \
            region3_input_primitives]] \
    floorplan_region3_input_fdre \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan region3_input_primitives] FDRE] \
    floorplan_region3_input_lut3 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan region3_input_primitives] LUT3] \
    floorplan_region3_input_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $final_floorplan_plan \
                region3_input_primitives] DSP48E2] \
    floorplan_owner_region3_input_exact_cover \
        [dict get $final_floorplan_plan owner_region3_input_exact_cover] \
    floorplan_region3_weight_owner_residency_ok \
        [dict get $final_floorplan_plan \
            region3_weight_owner_residency_ok] \
    floorplan_region3_input_localization_ok \
        $final_region3_localization_ok \
    floorplan_owner_region2_weight_anchor_ok \
        $final_owner_region2_weight_anchor_ok \
    floorplan_frontend_wrong \
        [dict get $final_floorplan_metrics frontend_wrong] \
    floorplan_wrong_total \
        [dict get $final_floorplan_metrics wrong_total] \
    floorplan_unplaced_total \
        [dict get $final_floorplan_metrics unplaced_total] \
    floorplan_slr0_dsp48e2 \
        [lindex [dict get $final_floorplan_metrics slr_dsp] 0] \
    floorplan_slr1_dsp48e2 \
        [lindex [dict get $final_floorplan_metrics slr_dsp] 1] \
    floorplan_slr2_dsp48e2 \
        [lindex [dict get $final_floorplan_metrics slr_dsp] 2] \
    floorplan_ok $floorplan_ok \
    post_place_drc_errors $post_place_drc_errors \
    post_place_data_bufg $post_place_data_bufg \
    post_place_placer_level6_or_higher_windows $post_place_placer_level6 \
    post_place_router_level6_or_higher_windows $post_place_router_level6 \
    post_place_level6_or_higher_congestion_windows $post_place_level6_total \
    post_place_region0_input_localization_ok \
        $post_place_region0_localization_ok \
    post_place_region3_input_localization_ok \
        $post_place_region3_localization_ok \
    post_place_owner_region2_weight_anchor_ok \
        $post_place_owner_region2_weight_anchor_ok \
    post_place_placer_level5_or_higher_windows $post_place_placer_level5 \
    post_place_router_level5_or_higher_windows $post_place_router_level5 \
    post_place_level5_or_higher_congestion_windows $post_place_level5_total \
    post_place_strict_gate_ok $post_place_strict_gate_ok \
    post_place_level5_screen_ok $post_place_level5_screen_ok \
    post_place_fast_gate_ok $post_place_fast_gate_ok \
    no_placer_congestion_above_level5 $no_placer_above5 \
    no_router_congestion_above_level5 $no_router_above5 \
    placer_level6_or_higher_windows $placer_level6 \
    router_level6_or_higher_windows $router_level6 \
    level6_or_higher_congestion_windows $level6_total \
    structural_ok $structural_ok route_clean $route_clean status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "PROJECTION_REUSE_OOC_ROUTE WNS=$wns WHS=$whs DSP=$dut_dsp ARRAY_DSP=$array_dsp FRONTEND_DSP=$frontend_dsp ROUTE_ERRORS=$route_errors DRC_ERRORS=$drc_errors FLOORPLAN=$floorplan_ok LEVEL6_PLUS=$level6_total STATUS=$status"
if {$status ne "PASS"} {
    error "cohort16 projection reuse registered OOC route gate failed"
}
close_project
