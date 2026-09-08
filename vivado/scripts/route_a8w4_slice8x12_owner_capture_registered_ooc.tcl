set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "AltSpreadLogic_high"}]
set pre_route_physopt_directive [expr {
    [info exists ::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set route_directive [expr {[info exists ::env(HAP_ROUTE_DIRECTIVE)] ?
    $::env(HAP_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
set post_route_physopt_directive [expr {
    [info exists ::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set max_level5 [expr {[info exists ::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)] ?
    $::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS) : 1}]
set top hap_a8w4_slice8x12_group_registered_ooc_harness
set part xcvu9p-flga2104-2L-e
set floorplan_lib [file join $root vivado scripts \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32"
}
if {![string is integer -strict $max_level5] || $max_level5 < 0 ||
    $max_level5 > 100} {
    error "HAP_MAX_POST_PLACE_LEVEL5_WINDOWS must be an integer in 0..100"
}
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    ![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "MLP OOC provenance hash is invalid"
}
set_param general.maxThreads $jobs

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc placed_slr_audit {cells label expected_slr} {
    set total [llength $cells]
    if {$total == 0} {error "$label collection is empty"}
    set slr_values [get_property SLR_INDEX $cells]
    if {[llength $slr_values] != $total} {
        error "$label placement-property vector length mismatch"
    }
    set placed_expected 0
    set placed_other 0
    set unplaced 0
    foreach slr $slr_values {
        if {$slr eq ""} {
            incr unplaced
        } elseif {![regexp {([0-2])$} $slr -> slr_index]} {
            error "$label placed cell has invalid SLR_INDEX '$slr'"
        } elseif {$slr_index == $expected_slr} {
            incr placed_expected
        } else {
            incr placed_other
        }
    }
    if {$placed_expected + $placed_other + $unplaced != $total} {
        error "$label placement audit accounting mismatch"
    }
    return [dict create total $total placed_expected $placed_expected \
        placed_other $placed_other unplaced $unplaced]
}

proc first_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} {error "No $delay_type timing path"}
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

proc write_summary {out values} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} $values {puts $fp "$key=$value"}
    close $fp
}

set actual_dcp_sha [lindex [exec sha256sum -- $input_dcp] 0]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "MLP OOC input DCP SHA256 mismatch"
}
source $floorplan_lib
open_checkpoint $input_dcp
if {[get_property PART [current_project]] ne $part} {
    error "MLP OOC input part mismatch"
}
require_count dut_instance [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1
require_count existing_pblocks [get_pblocks -quiet] 0
set clocks [get_clocks -quiet clk]
require_count core_clock $clocks 1
if {abs([get_property PERIOD $clocks] - 10.000) > 0.001} {
    error "MLP OOC clock is not 100 MHz"
}

set src [get_cells -quiet -hierarchical -filter {
    NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter {
    NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set lanes [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_a8w4_group32_lane2_s36 ||
    ORIG_REF_NAME == hap_a8w4_group32_lane2_s36)}]
set leaves [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_a8w4_ingress_capture_leaf ||
    ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf)}]
set leaf_lut [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/*/u_leaf && REF_NAME == LUT1}]
set dsp [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]
set src_count [require_count source_proxy_ff $src 4136]
set sink_count [require_count sink_proxy_ff $sink 3523]
set lane_count [require_count mlp_pack2_lane_instances $lanes 48]
set leaf_count [require_count ingress_capture_leaf_instances $leaves 816]
set leaf_lut_count [require_count ingress_capture_leaf_lut1 $leaf_lut 816]
set dsp_count [require_count dut_dsp48e2 $dsp 1536]

opt_design -directive Explore
set pblock_cells [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND &&
    REF_NAME != VCC && REF_NAME !~ BUFG*}]
if {[llength $pblock_cells] == 0} {error "MLP OOC pblock is empty"}
create_pblock pb_mlp_owner_capture_slr0
add_cells_to_pblock [get_pblocks pb_mlp_owner_capture_slr0] $pblock_cells
resize_pblock [get_pblocks pb_mlp_owner_capture_slr0] -add [list SLR0]
set_property IS_SOFT false [get_pblocks pb_mlp_owner_capture_slr0]
set_property CONTAIN_ROUTING false [get_pblocks pb_mlp_owner_capture_slr0]
set_property EXCLUDE_PLACEMENT false [get_pblocks pb_mlp_owner_capture_slr0]

place_design -directive $place_directive
write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]
set post_place_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND &&
    REF_NAME != VCC && REF_NAME !~ BUFG*}]
set post_place_primitive_audit [placed_slr_audit \
    $post_place_primitives post_place_primitives 0]
set post_place_dsp [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]
require_count post_place_dut_dsp48e2 $post_place_dsp 1536
set post_place_dsp_audit [placed_slr_audit \
    $post_place_dsp post_place_dsp48e2 0]
set post_place_dsp0 [dict get $post_place_dsp_audit placed_expected]
set post_place_dsp_other [dict get $post_place_dsp_audit placed_other]
set unplaced [dict get $post_place_primitive_audit unplaced]
set wrong_slr [dict get $post_place_primitive_audit placed_other]
set post_place_wns [first_slack max]
set post_place_whs [first_slack min]
set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion_text [read_text $congestion_path]
set level5 [dict get \
    [hap_projection_ooc_floorplan::congestion_counts_at_or_above \
        $congestion_text 5] total]
set level6 [dict get \
    [hap_projection_ooc_floorplan::congestion_counts_at_or_above \
        $congestion_text 6] total]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 10 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
report_drc -file [file join $out drc_post_place.rpt]
set post_place_drc [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
set fast_gate [expr {$post_place_dsp0 == 1536 && $post_place_dsp_other == 0 &&
    $unplaced == 0 && $wrong_slr == 0 && $post_place_drc == 0 &&
    $level6 == 0 && $level5 <= $max_level5}]
set fp [open [file join $out post_place_fast_gate.txt] w]
foreach {key value} [list post_place_dsp_slr0 $post_place_dsp0 \
    post_place_dsp_other_slr $post_place_dsp_other unplaced_primitives $unplaced \
    wrong_slr_primitives $wrong_slr drc_errors $post_place_drc \
    level5_or_higher_windows $level5 level6_or_higher_windows $level6 \
    max_level5_windows $max_level5 fast_gate_ok $fast_gate] {
    puts $fp "$key=$value"
}
close $fp
if {!$fast_gate} {
    write_summary $out [list tool [version -short] part $part top $top \
        stage OWNER_CAPTURE_REGISTERED_OOC_POST_PLACE \
        clock_mhz 100 input_dcp $input_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 $input_manifest_sha jobs $jobs \
        place_directive $place_directive \
        pre_route_physopt_directive $pre_route_physopt_directive \
        route_directive $route_directive \
        post_route_physopt_directive $post_route_physopt_directive \
        source_proxy_ff $src_count sink_proxy_ff $sink_count \
        mlp_pack2_lane_instances $lane_count \
        ingress_capture_leaf_instances $leaf_count \
        ingress_capture_leaf_lut1 $leaf_lut_count dut_dsp48e2 $dsp_count \
        post_place_wns_ns $post_place_wns post_place_whs_ns $post_place_whs \
        post_place_level5_or_higher_windows $level5 \
        post_place_level6_or_higher_windows $level6 fast_gate_ok 0 \
        route_started 0 status FAIL]
    close_design
    error "MLP OOC post-place fast gate failed"
}
write_checkpoint -force [file join $out post_place.dcp]

phys_opt_design -directive $pre_route_physopt_directive
route_design -directive $route_directive
write_checkpoint -force [file join $out post_route_before_physopt.dcp]
phys_opt_design -directive $post_route_physopt_directive

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set fp [open [file join $out timing_post_route.rpt] w]
puts $fp $timing_text
close $fp
report_timing -delay_type max -max_paths 100 -file \
    [file join $out timing_setup_worst100_post_route.rpt]
report_timing -delay_type min -max_paths 100 -file \
    [file join $out timing_hold_worst100_post_route.rpt]
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_text no_input_delay]
set no_output_delay [check_timing_count $timing_text no_output_delay]
set partial_input_delay [check_timing_count $timing_text partial_input_delay]
set partial_output_delay [check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 0 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]

set route_text [report_route_status -return_string]
set fp [open [file join $out route_status_post_route.rpt] w]
puts $fp $route_text
close $fp
report_drc -file [file join $out drc_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 10 -file \
    [file join $out utilization_hier_post_route.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_route.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage_post_route.rpt]
set final_congestion_path [file join $out congestion_post_route.rpt]
report_design_analysis -congestion -file $final_congestion_path

set route_errors [route_row $route_text "# of nets with routing errors" 1]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text \
    "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]
set partial_all [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
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
set conflict_status [llength [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
set accepted_clock_explicit_gaps [expr {
    $explicit_gaps == 1 && [llength $accepted_clock_partial] > 0 &&
    [llength $bad_partial] == 0 ? 1 : 0}]
set unaccepted_explicit_gaps \
    [expr {$explicit_gaps - $accepted_clock_explicit_gaps}]
if {$unaccepted_explicit_gaps < 0} {
    error "MLP OOC explicit-gap accounting is invalid"
}
set route_clean [expr {$route_errors == 0 && $unaccepted_explicit_gaps == 0 &&
    $unrouted_rows == 0 && $unrouted_pins == 0 && $resource_conflicts == 0 &&
    $antennas == 0 && [llength $bad_partial] == 0 && $conflict_status == 0}]

set exception_text [read_text \
    [file join $out exceptions_coverage_post_route.rpt]]
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exception_text] >= 0}]
set final_congestion_text [read_text $final_congestion_path]
set final_level6 [dict get \
    [hap_projection_ooc_floorplan::congestion_counts_at_or_above \
        $final_congestion_text 6] total]
set final_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND &&
    REF_NAME != VCC && REF_NAME !~ BUFG*}]
set final_primitive_audit [placed_slr_audit \
    $final_primitives final_primitives 0]
set final_unplaced [dict get $final_primitive_audit unplaced]
set final_wrong_slr [dict get $final_primitive_audit placed_other]
set final_dsp [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]
require_count final_dut_dsp48e2 $final_dsp 1536
set final_dsp_audit [placed_slr_audit $final_dsp final_dsp48e2 0]
set final_dsp0 [dict get $final_dsp_audit placed_expected]
set final_dsp_other [dict get $final_dsp_audit placed_other]
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {incr data_bufg}
}
set wns [first_slack max]
set whs [first_slack min]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $route_clean &&
    $drc_errors == 0 && $data_bufg == 0 && $final_level6 == 0 &&
    $timing_coverage_ok && $no_timing_exceptions && $final_unplaced == 0 &&
    $final_wrong_slr == 0 && $final_dsp0 == 1536 && $final_dsp_other == 0 ?
    "PASS" : "FAIL"}]
if {$status eq "PASS"} {
    write_checkpoint -force [file join $out post_route.dcp]
}
write_summary $out [list tool [version -short] part $part top $top \
    stage OWNER_CAPTURE_REGISTERED_OOC_POST_ROUTE clock_mhz 100 \
    input_dcp $input_dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 $input_manifest_sha jobs $jobs \
    place_directive $place_directive \
    pre_route_physopt_directive $pre_route_physopt_directive \
    route_directive $route_directive \
    post_route_physopt_directive $post_route_physopt_directive \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    mlp_pack2_lane_instances $lane_count \
    ingress_capture_leaf_instances $leaf_count \
    ingress_capture_leaf_lut1 $leaf_lut_count dut_dsp48e2 $dsp_count \
    post_place_wns_ns $post_place_wns post_place_whs_ns $post_place_whs \
    post_place_level5_or_higher_windows $level5 \
    post_place_level6_or_higher_windows $level6 fast_gate_ok 1 \
    wns_ns $wns whs_ns $whs route_errors $route_errors \
    explicit_route_gaps $explicit_gaps unrouted_rows $unrouted_rows \
    accepted_clock_explicit_gaps $accepted_clock_explicit_gaps \
    unaccepted_explicit_route_gaps $unaccepted_explicit_gaps \
    unrouted_pins $unrouted_pins resource_conflicts $resource_conflicts \
    antennas_or_islands $antennas bad_partial_nets [llength $bad_partial] \
    accepted_clock_partial_nets [llength $accepted_clock_partial] \
    conflict_status_nets $conflict_status route_clean $route_clean \
    drc_errors $drc_errors data_bufg $data_bufg \
    final_level6_or_higher_windows $final_level6 \
    final_unplaced_primitives $final_unplaced \
    final_wrong_slr_primitives $final_wrong_slr \
    final_dsp_slr0 $final_dsp0 final_dsp_other_slr $final_dsp_other \
    no_timing_exceptions $no_timing_exceptions \
    no_clock_endpoints $no_clock \
    unconstrained_internal_endpoints $unconstrained \
    no_input_delay_endpoints $no_input_delay \
    no_output_delay_endpoints $no_output_delay \
    partial_input_delay_endpoints $partial_input_delay \
    partial_output_delay_endpoints $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok route_started 1 status $status]
close_design
if {$status ne "PASS"} {error "MLP owner-capture OOC route gate failed"}
