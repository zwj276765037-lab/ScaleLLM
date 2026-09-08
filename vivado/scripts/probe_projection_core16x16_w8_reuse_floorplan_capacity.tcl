set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set out [file normalize $::env(HAP_REPORT_DIR)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set input_manifest_sha $::env(HAP_CAPACITY_INPUT_MANIFEST_SHA256)
set script_dir [file dirname [file normalize [info script]]]
set jobs 32
if {[info exists ::env(HAP_JOBS)]} {set jobs $::env(HAP_JOBS)}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32, got $jobs"
}
set_param general.maxThreads $jobs
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
    error "projection capacity input DCP hash mismatch"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "projection capacity input manifest hash is invalid"
}

proc count_ref_pattern {cells pattern} {
    set count 0
    foreach cell $cells {
        if {[string match $pattern [get_property REF_NAME $cell]]} {
            incr count
        }
    }
    return $count
}

proc candidate_regions {x_values {min_y 5} {max_y 9}} {
    set names {}
    foreach x $x_values {
        for {set y $min_y} {$y <= $max_y} {incr y} {
            lappend names X${x}Y${y}
        }
    }
    set regions {}
    foreach name $names {
        set match [get_clock_regions -quiet $name]
        if {[llength $match] != 1} {
            error "candidate clock-region lookup mismatch: expected=$name actual=$match"
        }
        lappend regions [lindex $match 0]
    }
    return $regions
}

proc site_capacities {regions} {
    array set type_counts {}
    foreach site [get_sites -quiet -of_objects $regions] {
        set type [get_property SITE_TYPE $site]
        if {![info exists type_counts($type)]} {set type_counts($type) 0}
        incr type_counts($type)
    }

    set slice_sites 0
    set dsp_sites 0
    set ramb36_sites 0
    set ramb18_sites 0
    foreach type [array names type_counts] {
        if {[string match "SLICE*" $type]} {
            incr slice_sites $type_counts($type)
        }
        if {[string match "DSP*" $type]} {
            incr dsp_sites $type_counts($type)
        }
        if {[string match "RAMB36*" $type] ||
            [string match "RAMBFIFO36*" $type]} {
            incr ramb36_sites $type_counts($type)
        }
        if {[string match "RAMB18*" $type] ||
            [string match "RAMBFIFO18*" $type]} {
            incr ramb18_sites $type_counts($type)
        }
    }
    return [dict create slice_sites $slice_sites \
        lut_capacity [expr {$slice_sites * 8}] \
        ff_capacity [expr {$slice_sites * 16}] \
        dsp_capacity $dsp_sites ramb36_sites $ramb36_sites \
        ramb18_sites $ramb18_sites site_types [array get type_counts]]
}

proc write_candidate {fp label regions cells} {
    set capacity [site_capacities $regions]
    set lut [count_ref_pattern $cells LUT*]
    set ff [count_ref_pattern $cells FD*]
    set dsp [count_ref_pattern $cells DSP48E2]
    set ramb36 [count_ref_pattern $cells RAMB36E2]
    set ramb18 [count_ref_pattern $cells RAMB18E2]
    set lut_capacity [dict get $capacity lut_capacity]
    set ff_capacity [dict get $capacity ff_capacity]
    set dsp_capacity [dict get $capacity dsp_capacity]
    set ramb36_capacity [dict get $capacity ramb36_sites]
    set ramb18_capacity [dict get $capacity ramb18_sites]
    set bram36_tile_equiv_demand [expr {$ramb36 + ($ramb18 + 1) / 2}]
    set lut_util_pct [expr {100.0 * $lut / $lut_capacity}]
    set ff_util_pct [expr {100.0 * $ff / $ff_capacity}]
    set dsp_util_pct [expr {100.0 * $dsp / $dsp_capacity}]
    set bram36_tile_equiv_util_pct \
        [expr {100.0 * $bram36_tile_equiv_demand / $ramb36_capacity}]
    set capacity_ok [expr {$lut <= $lut_capacity && $ff <= $ff_capacity &&
        $dsp <= $dsp_capacity &&
        $bram36_tile_equiv_demand <= $ramb36_capacity &&
        $ramb18 <= $ramb18_capacity}]
    puts $fp "candidate=$label"
    puts $fp "clock_regions=[lsort -dictionary [get_property NAME $regions]]"
    puts $fp "primitive_count=[llength $cells]"
    puts $fp "lut_demand=$lut"
    puts $fp "ff_demand=$ff"
    puts $fp "dsp_demand=$dsp"
    puts $fp "ramb36_demand=$ramb36"
    puts $fp "ramb18_demand=$ramb18"
    puts $fp "slice_sites=[dict get $capacity slice_sites]"
    puts $fp "lut_capacity=$lut_capacity"
    puts $fp "ff_capacity=$ff_capacity"
    puts $fp "dsp_capacity=$dsp_capacity"
    puts $fp "ramb36_sites=$ramb36_capacity"
    puts $fp "ramb18_sites=$ramb18_capacity"
    puts $fp "bram36_tile_equiv_demand=$bram36_tile_equiv_demand"
    puts $fp [format "lut_util_pct=%.3f" $lut_util_pct]
    puts $fp [format "ff_util_pct=%.3f" $ff_util_pct]
    puts $fp [format "dsp_util_pct=%.3f" $dsp_util_pct]
    puts $fp [format "bram36_tile_equiv_util_pct=%.3f" \
        $bram36_tile_equiv_util_pct]
    puts $fp "bram36_capacity_ok=[expr {$bram36_tile_equiv_demand <=
        $ramb36_capacity}]"
    puts $fp "ramb18_capacity_ok=[expr {$ramb18 <= $ramb18_capacity}]"
    puts $fp "raw_capacity_ok=$capacity_ok"
    foreach {type count} [lsort -stride 2 -dictionary -index 0 \
            [dict get $capacity site_types]] {
        puts $fp "site_type_${type}=$count"
    }
    puts $fp ""
    return [dict create label $label primitive_count [llength $cells] \
        lut_demand $lut \
        lut_capacity $lut_capacity lut_util_pct $lut_util_pct \
        ff_demand $ff ff_capacity $ff_capacity ff_util_pct $ff_util_pct \
        dsp_demand $dsp dsp_capacity $dsp_capacity \
        dsp_util_pct $dsp_util_pct \
        bram36_tile_equiv_demand $bram36_tile_equiv_demand \
        bram36_capacity $ramb36_capacity \
        bram36_tile_equiv_util_pct $bram36_tile_equiv_util_pct \
        capacity_ok $capacity_ok]
}

open_checkpoint $input_dcp
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e"} {
    error "projection capacity probe part mismatch"
}
if {[llength [get_pblocks -quiet]] != 0} {
    error "projection capacity probe input unexpectedly contains pblocks"
}
set plan [hap_projection_ooc_floorplan::discover]

set region2_cells [dict get $plan center_region2_primitives]
set region3_cells [dict get $plan center_region3_floorplan_primitives]
set region23_cells [hap_projection_ooc_floorplan::list_union \
    $region2_cells $region3_cells]
set region1_cells [dict get $plan center_region1_primitives]
set region1_cols4_5_dsp_cells \
    [dict get $plan center_region1_cols4_5_dsp_primitives]
set region1_cols6_7_dsp_cells \
    [dict get $plan center_region1_cols6_7_dsp_primitives]
set region1_logic_residual_cells \
    [dict get $plan center_region1_logic_residual_primitives]
set owner_floorplan_cells [dict get $plan owner_floorplan_primitives]
set owner_residual_cells \
    [dict get $plan owner_residual_floorplan_primitives]
set owner_region2_weight_cells \
    [dict get $plan owner_region2_weight_primitives]
set region0_input_cells [dict get $plan region0_input_primitives]
set region0_input_activation_cells \
    [dict get $plan region0_input_activation_primitives]
set region0_input_zero_point_cells \
    [dict get $plan region0_input_zero_point_primitives]
set region0_input_weight_ff_cells \
    [dict get $plan region0_input_weight_ff_primitives]
set region0_input_weight_lut_cells \
    [dict get $plan region0_input_weight_lut_primitives]
set region0_input_weight_cells \
    [dict get $plan region0_input_weight_primitives]
set region3_input_cells [dict get $plan region3_input_primitives]
set region3_input_activation_cells \
    [dict get $plan region3_input_activation_primitives]
set region3_input_zero_point_cells \
    [dict get $plan region3_input_zero_point_primitives]
set region3_input_weight_ff_cells \
    [dict get $plan region3_input_weight_ff_primitives]
set region3_input_weight_lut_cells \
    [dict get $plan region3_input_weight_lut_primitives]
set region3_owner_weight_ff_cells \
    [dict get $plan region3_owner_weight_ff_primitives]
set region3_owner_weight_lut_cells \
    [dict get $plan region3_owner_weight_lut_primitives]
set active_region0_frontend_cells \
    [dict get $plan center_region0_frontend_primitives]
set active_region1_owner_cells \
    [hap_projection_ooc_floorplan::list_union \
        $region1_cells $owner_floorplan_cells]
set active_center_x2_x5_cells \
    [hap_projection_ooc_floorplan::list_union \
        $region1_cells $owner_floorplan_cells \
        $active_region0_frontend_cells]

set fp [open [file join $out candidate_capacity.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=[get_property PART [current_project]]"
puts $fp "jobs=$jobs"
puts $fp "input_dcp=$input_dcp"
puts $fp "input_dcp_sha256=$actual_dcp_sha"
puts $fp "input_manifest_sha256=$input_manifest_sha"
puts $fp "status=CAPACITY_PROBE_ONLY"
puts $fp ""
set candidate_region2 [write_candidate $fp active_region2_shared_x0_x1 \
    [candidate_regions {0 1}] $region2_cells
]
set candidate_region3 [write_candidate $fp active_region3_shared_x0_x1 \
    [candidate_regions {0 1}] $region3_cells
]
set candidate_region23 [write_candidate $fp active_region23_shared_x0_x1 \
    [candidate_regions {0 1}] $region23_cells
]
set candidate_region1_owner [write_candidate $fp \
    active_region1_owner_x2_x4 [candidate_regions {2 3 4}] \
    $active_region1_owner_cells]
set candidate_region0_frontend [write_candidate $fp \
    active_region0_frontend_x4_x5 [candidate_regions {4 5}] \
    $active_region0_frontend_cells]
set candidate_center_total [write_candidate $fp \
    active_center_total_x2_x5 [candidate_regions {2 3 4 5}] \
    $active_center_x2_x5_cells]
set candidate_region1_cols4_5_dsp [write_candidate $fp \
    active_region1_cols4_5_dsp_x3_x4 [candidate_regions {3 4}] \
    $region1_cols4_5_dsp_cells]
set candidate_region1_cols6_7_dsp [write_candidate $fp \
    active_region1_cols6_7_dsp_x2_x3 [candidate_regions {2 3}] \
    $region1_cols6_7_dsp_cells]
set candidate_region1_logic_residual [write_candidate $fp \
    active_region1_logic_residual_x2_x4 [candidate_regions {2 3 4}] \
    $region1_logic_residual_cells]
set candidate_owner_region2_weight [write_candidate $fp \
    active_owner_region2_weight_x2_x4_y5_y6 \
    [candidate_regions {2 3 4} 5 6] $owner_region2_weight_cells]
close $fp

set canonical_pblock_count [llength [get_pblocks -quiet]]
set region3_localization_ok \
    [hap_projection_ooc_floorplan::region3_input_localization_ok $plan]
set region0_localization_ok \
    [hap_projection_ooc_floorplan::region0_input_localization_ok $plan]
set owner_region2_weight_anchor_ok \
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok $plan]
set active_capacity_ok [expr {
    [dict get $candidate_region2 capacity_ok] &&
    [dict get $candidate_region3 capacity_ok] &&
    [dict get $candidate_region23 capacity_ok] &&
    [dict get $candidate_region1_owner capacity_ok] &&
    [dict get $candidate_region0_frontend capacity_ok] &&
    [dict get $candidate_center_total capacity_ok] &&
    [dict get $candidate_region1_cols4_5_dsp capacity_ok] &&
    [dict get $candidate_region1_cols6_7_dsp capacity_ok] &&
    [dict get $candidate_region1_logic_residual capacity_ok] &&
    [dict get $candidate_owner_region2_weight capacity_ok] &&
    $region0_localization_ok && $region3_localization_ok &&
    $owner_region2_weight_anchor_ok}]
set status [expr {$canonical_pblock_count == 0 && $active_capacity_ok ?
    "PASS" : "FAIL"}]
set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        part [get_property PART [current_project]] \
        stage PROJECTION_REUSE_OOC_FLOORPLAN_CAPACITY_PROBE \
        evidence_class READ_ONLY_POST_SYNTH_CAPACITY_PROBE jobs $jobs \
        input_dcp $input_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 $input_manifest_sha candidate_count 10 \
        target_candidate_count 10 \
        candidate_region2_label [dict get $candidate_region2 label] \
        candidate_region2_raw_capacity_ok \
            [dict get $candidate_region2 capacity_ok] \
        candidate_region3_label [dict get $candidate_region3 label] \
        candidate_region3_primitive_count \
            [dict get $candidate_region3 primitive_count] \
        candidate_region3_lut_demand \
            [dict get $candidate_region3 lut_demand] \
        candidate_region3_lut_util_pct \
            [format %.3f [dict get $candidate_region3 lut_util_pct]] \
        candidate_region3_ff_demand \
            [dict get $candidate_region3 ff_demand] \
        candidate_region3_ff_util_pct \
            [format %.3f [dict get $candidate_region3 ff_util_pct]] \
        candidate_region3_dsp_demand \
            [dict get $candidate_region3 dsp_demand] \
        candidate_region3_dsp_util_pct \
            [format %.3f [dict get $candidate_region3 dsp_util_pct]] \
        candidate_region3_raw_capacity_ok \
            [dict get $candidate_region3 capacity_ok] \
        candidate_region23_label [dict get $candidate_region23 label] \
        candidate_region23_primitive_count \
            [dict get $candidate_region23 primitive_count] \
        candidate_region23_lut_demand \
            [dict get $candidate_region23 lut_demand] \
        candidate_region23_lut_capacity \
            [dict get $candidate_region23 lut_capacity] \
        candidate_region23_lut_util_pct \
            [format %.3f [dict get $candidate_region23 lut_util_pct]] \
        candidate_region23_ff_demand \
            [dict get $candidate_region23 ff_demand] \
        candidate_region23_ff_capacity \
            [dict get $candidate_region23 ff_capacity] \
        candidate_region23_ff_util_pct \
            [format %.3f [dict get $candidate_region23 ff_util_pct]] \
        candidate_region23_dsp_demand \
            [dict get $candidate_region23 dsp_demand] \
        candidate_region23_dsp_capacity \
            [dict get $candidate_region23 dsp_capacity] \
        candidate_region23_dsp_util_pct \
            [format %.3f [dict get $candidate_region23 dsp_util_pct]] \
        candidate_region23_raw_capacity_ok \
            [dict get $candidate_region23 capacity_ok] \
        candidate_region1_owner_label \
            [dict get $candidate_region1_owner label] \
        candidate_region1_owner_lut_demand \
            [dict get $candidate_region1_owner lut_demand] \
        candidate_region1_owner_lut_util_pct \
            [format %.3f [dict get $candidate_region1_owner lut_util_pct]] \
        candidate_region1_owner_dsp_demand \
            [dict get $candidate_region1_owner dsp_demand] \
        candidate_region1_owner_dsp_util_pct \
            [format %.3f [dict get $candidate_region1_owner dsp_util_pct]] \
        candidate_region1_owner_raw_capacity_ok \
            [dict get $candidate_region1_owner capacity_ok] \
        candidate_region0_frontend_label \
            [dict get $candidate_region0_frontend label] \
        candidate_region0_frontend_raw_capacity_ok \
            [dict get $candidate_region0_frontend capacity_ok] \
        candidate_center_total_label \
            [dict get $candidate_center_total label] \
        candidate_center_total_lut_util_pct \
            [format %.3f [dict get $candidate_center_total lut_util_pct]] \
        candidate_center_total_dsp_util_pct \
            [format %.3f [dict get $candidate_center_total dsp_util_pct]] \
        candidate_center_total_raw_capacity_ok \
            [dict get $candidate_center_total capacity_ok] \
        candidate_region1_cols4_5_dsp_label \
            [dict get $candidate_region1_cols4_5_dsp label] \
        candidate_region1_cols4_5_dsp_demand \
            [dict get $candidate_region1_cols4_5_dsp dsp_demand] \
        candidate_region1_cols4_5_dsp_raw_capacity_ok \
            [dict get $candidate_region1_cols4_5_dsp capacity_ok] \
        candidate_region1_cols6_7_dsp_label \
            [dict get $candidate_region1_cols6_7_dsp label] \
        candidate_region1_cols6_7_dsp_demand \
            [dict get $candidate_region1_cols6_7_dsp dsp_demand] \
        candidate_region1_cols6_7_dsp_raw_capacity_ok \
            [dict get $candidate_region1_cols6_7_dsp capacity_ok] \
        candidate_region1_logic_residual_label \
            [dict get $candidate_region1_logic_residual label] \
        candidate_region1_logic_residual_dsp_demand \
            [dict get $candidate_region1_logic_residual dsp_demand] \
        candidate_region1_logic_residual_raw_capacity_ok \
            [dict get $candidate_region1_logic_residual capacity_ok] \
        candidate_owner_region2_weight_label \
            [dict get $candidate_owner_region2_weight label] \
        candidate_owner_region2_weight_primitive_count \
            [dict get $candidate_owner_region2_weight primitive_count] \
        candidate_owner_region2_weight_lut_demand \
            [dict get $candidate_owner_region2_weight lut_demand] \
        candidate_owner_region2_weight_ff_demand \
            [dict get $candidate_owner_region2_weight ff_demand] \
        candidate_owner_region2_weight_dsp_demand \
            [dict get $candidate_owner_region2_weight dsp_demand] \
        candidate_owner_region2_weight_raw_capacity_ok \
            [dict get $candidate_owner_region2_weight capacity_ok] \
        center_region1_lane_roots \
            [llength [dict get $plan center_region1_lane_roots]] \
        center_region1_cols4_5_lane_roots \
            [llength [dict get $plan center_region1_cols4_5_lane_roots]] \
        center_region1_cols6_7_lane_roots \
            [llength [dict get $plan center_region1_cols6_7_lane_roots]] \
        center_region1_bisect_exact_cover \
            [dict get $plan center_region1_bisect_exact_cover] \
        center_region1_dsp_stripe_exact_cover \
            [dict get $plan center_region1_dsp_stripe_exact_cover] \
        logical_owner_primitives \
            [llength [dict get $plan owner_primitives]] \
        owner_floorplan_primitives \
            [llength [dict get $plan owner_floorplan_primitives]] \
        owner_residual_floorplan_primitives \
            [llength $owner_residual_cells] \
        owner_region2_weight_ff_primitives \
            [llength [dict get $plan \
                owner_region2_weight_ff_primitives]] \
        owner_region2_weight_lut_primitives \
            [llength [dict get $plan \
                owner_region2_weight_lut_primitives]] \
        owner_region2_weight_primitives \
            [llength $owner_region2_weight_cells] \
        owner_region2_weight_exact_cover \
            [dict get $plan owner_region2_weight_exact_cover] \
        region0_input_activation_primitives \
            [llength $region0_input_activation_cells] \
        region0_input_zero_point_primitives \
            [llength $region0_input_zero_point_cells] \
        region0_input_weight_ff_primitives \
            [llength $region0_input_weight_ff_cells] \
        region0_input_weight_lut_primitives \
            [llength $region0_input_weight_lut_cells] \
        region0_input_weight_primitives \
            [llength $region0_input_weight_cells] \
        region0_input_primitives [llength $region0_input_cells] \
        region0_input_fdre \
            [count_ref_pattern $region0_input_cells FDRE] \
        region0_input_lut3 \
            [count_ref_pattern $region0_input_cells LUT3] \
        region0_input_dsp48e2 \
            [count_ref_pattern $region0_input_cells DSP48E2] \
        owner_region0_input_exact_cover \
            [dict get $plan owner_region0_input_exact_cover] \
        region0_input_localization_ok $region0_localization_ok \
        logical_center_region3_primitives \
            [llength [dict get $plan center_region3_primitives]] \
        center_region3_floorplan_primitives \
            [llength [dict get $plan center_region3_floorplan_primitives]] \
        region3_input_activation_primitives \
            [llength $region3_input_activation_cells] \
        region3_input_zero_point_primitives \
            [llength $region3_input_zero_point_cells] \
        region3_input_weight_ff_primitives \
            [llength $region3_input_weight_ff_cells] \
        region3_input_weight_lut_primitives \
            [llength $region3_input_weight_lut_cells] \
        region3_owner_weight_ff_primitives \
            [llength $region3_owner_weight_ff_cells] \
        region3_owner_weight_lut_primitives \
            [llength $region3_owner_weight_lut_cells] \
        region3_input_primitives [llength $region3_input_cells] \
        region3_input_fdre \
            [count_ref_pattern $region3_input_cells FDRE] \
        region3_input_lut3 \
            [count_ref_pattern $region3_input_cells LUT3] \
        region3_input_dsp48e2 \
            [count_ref_pattern $region3_input_cells DSP48E2] \
        owner_region3_input_exact_cover \
            [dict get $plan owner_region3_input_exact_cover] \
        region3_weight_owner_residency_ok \
            [dict get $plan region3_weight_owner_residency_ok] \
        region3_input_localization_ok $region3_localization_ok \
        owner_region2_weight_anchor_ok $owner_region2_weight_anchor_ok \
        active_floorplan_raw_capacity_ok $active_capacity_ok \
        canonical_pblock_count $canonical_pblock_count \
        canonical_floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 status $status] {
    puts $summary "$key=$value"
}
close $summary

puts "PROJECTION_REUSE_OOC_CAPACITY_PROBE_COMPLETE"
if {$status ne "PASS"} {
    error "projection reuse OOC capacity probe failed"
}
close_project
