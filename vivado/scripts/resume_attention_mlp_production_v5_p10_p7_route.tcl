# Strict route-only flow for a manifested P7 row-split checkpoint.

set p7_route_script [file normalize [info script]]
set p7_script_dir [file dirname $p7_route_script]
set p7_root [file normalize [file join $p7_script_dir ../..]]
set helper_lib [file normalize $::env(HAP_ROUTE_HELPER_LIB)]
set ::env(HAP_ROUTE_SOURCE_PROCS_ONLY) 1
source $helper_lib
unset ::env(HAP_ROUTE_SOURCE_PROCS_ONLY)

set in_dcp [file normalize $::env(HAP_POST_PLACE_DCP)]
set place_summary [file normalize $::env(HAP_PLACE_SUMMARY)]
set place_input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
set place_output_sha [file normalize $::env(HAP_PLACE_OUTPUT_SHA)]
set place_dir [file dirname $place_output_sha]
set place_launcher_status [file normalize \
    [file join $place_dir launcher_status.txt]]
set place_input_files [file normalize [file join $place_dir INPUT_FILES]]
set place_selectors [file normalize \
    [file join $place_dir selectors_post_place.txt]]
set place_geometry [file normalize \
    [file join $place_dir attention_geometry_post_place.txt]]
set place_geometry_placement [file normalize \
    [file join $place_dir attention_geometry_placement.txt]]
set place_base_pblocks [file normalize \
    [file join $place_dir base_pblocks_post_place.txt]]
set place_p5_plan [file normalize \
    [file join $place_dir p5_input_plan_post_place.txt]]
set place_p5_pblocks [file normalize \
    [file join $place_dir p5_input_pblocks_post_place.txt]]
set place_p6_plan [file normalize \
    [file join $place_dir p6_postprocess_plan_post_place.txt]]
set place_p6_pblocks [file normalize \
    [file join $place_dir p6_postprocess_pblocks_post_place.txt]]
set place_pre_gate [file normalize [file join $place_dir pre_place_gate.txt]]
set place_fast_gate [file normalize \
    [file join $place_dir post_place_fast_gate.txt]]
set out [file normalize $::env(HAP_ROUTE_DIR)]
set route_input_sha [file normalize [file join $out INPUT_SHA256SUMS]]
set expected_place_input_manifest_sha \
    $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
set expected_place_output_manifest_sha \
    $::env(HAP_PLACE_OUTPUT_MANIFEST_SHA256)
set expected_route_input_manifest_sha \
    $::env(HAP_ROUTE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_ROUTE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_ROUTE_GEOMETRY_LIB)]
set p5_lib [file normalize $::env(HAP_ROUTE_P5_LIB)]
set p6_lib [file normalize $::env(HAP_ROUTE_P6_LIB)]
set io_audit [file normalize $::env(HAP_ROUTE_IO_AUDIT)]
set clock_xdc [file normalize $::env(HAP_ROUTE_CLOCK_XDC)]
set expected_launcher [file normalize $::env(HAP_ROUTE_LAUNCHER)]
set pre_physopt_directive [expr {
    [info exists ::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set route_directive [expr {[info exists ::env(HAP_ROUTE_DIRECTIVE)] ?
    $::env(HAP_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
set post_physopt_directive [expr {
    [info exists ::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set expected_part xcvu9p-flga2104-2L-e
set expected_top hap_attention_mlp_production_core
set base_contract P2_COHORT16_COL2_12_2
set p5_contract P5_INPUT_HALF_LOCAL_8_8
set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4
set p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8
set geometry_prefix p3_
set region2_variant rowsplit_y5_y6_y6_y8
file mkdir $out

proc hap_p7_require_base_identity {plan} {
    foreach {key expected} {
        contract_variant P2_COHORT16_COL2_12_2
        total_dsp 5453 total_uram 752 history2_count 2
        generic_repack_count 0 branch0_dsp 1536 branch2_dsp 1536
        kernel_count 2 kernel_dsp 3072 swiglu_frontend_count 1
        row_leaf_count 2 unique_hadamard_count 1 fold2_count 0
        quantizer_count 4 silu_count 2 leaf0_dsp 2 leaf1_dsp 2
        leaf0_ramb36 6 leaf1_ramb36 6 outer0_dsp 1538 outer2_dsp 1538
        outer0_ramb36 102 outer2_ramb36 102 projection_lane_count 128
        projection_lane_dsp 17 projection_weight_capture_audited 1
        projection_weight_capture_ok 1 raw_weight_push_loads 37
        weight_data_capture_nets 32 weight_data_capture_min 256
        weight_data_capture_max 256 weight_meta_capture_nets 2
        weight_meta_capture_min 256 weight_meta_capture_max 256
        weight_group_capture_nets 2 weight_group_capture_min 7
        weight_group_capture_max 7 attention_meta_uram 80
        attention_island_target 0 attention_island_dsp 52
        attention_island_ramb36 88 attention_island_ramb18 2
        attention_island_uram 0 attention_island_quantizer_overlap 0
        attention_island_row_cache_overlap 0
    } {
        if {![dict exists $plan $key] || [dict get $plan $key] ne $expected} {
            set actual [expr {[dict exists $plan $key] ?
                [dict get $plan $key] : "MISSING"}]
            error "P7 base identity mismatch: $key expected=$expected actual=$actual"
        }
    }
}

proc hap_p7_reapply_compute_policy {} {
    set nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
    if {[llength $nets] == 0} {error "P7 route compute-net selector is empty"}
    set before 0
    foreach net $nets {
        if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {incr before}
    }
    set_property CLOCK_BUFFER_TYPE NONE $nets
    set after 0
    foreach net $nets {
        if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {incr after}
    }
    if {$after != 0} {error "P7 route compute-net property reapply failed"}
    return [list [llength $nets] $before $after]
}

proc hap_p7_audit_live {out suffix marker} {
    set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
    hap_p7_require_base_identity $base_plan
    set projection_root [file dirname \
        [get_property NAME [dict get $base_plan projection_array]]]
    set geometry_plan \
        [hap_projection_ooc_floorplan::discover $projection_root 1]
    if {![hap_projection_ooc_floorplan::region0_input_localization_ok \
            $geometry_plan] ||
        ![hap_projection_ooc_floorplan::region3_input_localization_ok \
            $geometry_plan] ||
        ![hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $geometry_plan]} {
        error "P7 route projection geometry identity failed"
    }
    set p5_plan [hap_v5_p5_input_partition::discover $base_plan]
    set p6_plan [hap_v5_p6_postprocess_partition::discover \
        $base_plan $p5_plan]
    set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
        $geometry_plan 0 p3_ 1 rowsplit_y5_y6_y6_y8]
    set geometry_placement \
        [hap_projection_ooc_floorplan::audit_placement $geometry_plan]
    set base_audit [hap_v5_floorplan::audit_pblock_contract \
        $base_plan 1 P2_COHORT16_COL2_12_2 \
        [hap_projection_ooc_floorplan::specs $geometry_plan p3_ \
            rowsplit_y5_y6_y6_y8]]
    set p5_audit [hap_v5_p5_input_partition::audit $p5_plan 1]
    set p6_audit [hap_v5_p6_postprocess_partition::audit $p6_plan 1]
    set metrics [hap_v5_floorplan::physical_metrics $base_plan $base_audit]
    set slr_dsp [dict get $metrics slr_dsp]
    set slr_uram [dict get $metrics slr_uram]
    set expected_center_extras [expr {\
        [llength [dict get $p5_plan center_base_extras]] +\
        [llength [dict get $p6_plan center_rows]]}]
    set base_extra_delta [expr {
        [dict get $base_audit optimizer_extra_count] - $expected_center_extras}]
    if {[dict get $p5_plan contract] ne P5_INPUT_HALF_LOCAL_8_8 ||
        [dict get $geometry_audit pblock_count] != 12 ||
        [dict get $geometry_plan center_region2_row_exact_cover] != 1 ||
        [llength [dict get $geometry_plan \
            center_region2_rows0_3_primitives]] != 26800 ||
        [llength [dict get $geometry_plan \
            center_region2_rows4_7_primitives]] != 26800 ||
        [llength [dict get $geometry_plan \
            center_region2_residual_primitives]] != 15199 ||
        [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
            center_region2_rows0_3_primitives] DSP48E2] != 272 ||
        [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
            center_region2_rows4_7_primitives] DSP48E2] != 272 ||
        [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
            center_region2_residual_primitives] DSP48E2] != 0 ||
        ![dict get $geometry_placement ok] ||
        ![dict get $base_audit ok] ||
        [dict get $base_audit pblock_count] != 11 ||
        [dict get $base_audit dsp_coverage] != 5453 ||
        [dict get $base_audit uram_coverage] != 752 ||
        [dict get $base_audit placed_wrong] != 0 ||
        $base_extra_delta < 0 || $base_extra_delta > 4096 ||
        ![dict get $p5_audit ok] ||
        [dict get $p5_audit center_wrong] != 0 ||
        [dict get $p5_audit outer_wrong] != 0 ||
        [dict get $p5_audit outer_extras] > 4096 ||
        ![dict get $p6_audit ok] ||
        [dict get $p6_audit center_wrong] != 0 ||
        [dict get $p6_audit outer_wrong] != 0 ||
        [dict get $p6_audit outer_extras] > 4096 ||
        [llength [get_pblocks -quiet]] != 27 ||
        $slr_dsp ne {1862 1781 1810} ||
        $slr_uram ne {224 224 304} ||
        ![hap_v5_floorplan::physical_ok $base_plan $metrics]} {
        error "P7 route physical identity failed: base=$base_audit geometry=$geometry_audit p5=$p5_audit p6=$p6_audit metrics=$metrics"
    }
    set clear [hap_route_mlp_local_clear_audit 1]
    set metadata [hap_route_metadata_local_write_audit 1]
    set capture [hap_route_mlp_capture_leaf_audit 1]
    hap_route_require_boundary_contract $clear $metadata $capture $marker
    set compute_count [hap_route_compute_clock_buffer_none]
    hap_v5_floorplan::write_discovery $base_plan \
        [file join $out selectors_${suffix}.txt] ${marker}_SELECTORS_PASS
    hap_projection_ooc_floorplan::write_plan $geometry_plan \
        [file join $out attention_geometry_${suffix}.txt] \
        ${marker}_GEOMETRY_PASS
    hap_projection_ooc_floorplan::write_placement $geometry_placement \
        [file join $out attention_geometry_placement_${suffix}.txt] \
        ${marker}_GEOMETRY_PLACEMENT_PASS
    hap_v5_floorplan::write_pblock_audit $base_audit \
        [file join $out base_pblocks_${suffix}.txt] ${marker}_BASE_PBLOCKS_PASS
    hap_v5_p5_input_partition::write_plan $p5_plan \
        [file join $out p5_input_plan_${suffix}.txt] ${marker}_INPUT_PLAN_PASS
    hap_v5_p5_input_partition::write_audit $p5_audit \
        [file join $out p5_input_pblocks_${suffix}.txt] \
        ${marker}_INPUT_PBLOCKS_PASS
    hap_v5_p6_postprocess_partition::write_plan $p6_plan \
        [file join $out p6_postprocess_plan_${suffix}.txt] \
        ${marker}_POSTPROCESS_PLAN_PASS
    hap_v5_p6_postprocess_partition::write_audit $p6_audit \
        [file join $out p6_postprocess_pblocks_${suffix}.txt] \
        ${marker}_POSTPROCESS_PBLOCKS_PASS
    hap_route_write_boundary_audit \
        [file join $out architecture_boundaries_${suffix}.txt] \
        $clear $metadata $capture ${marker}_BOUNDARIES_PASS
    return [dict create base $base_plan geometry $geometry_plan \
        geometry_audit $geometry_audit geometry_placement $geometry_placement \
        p5_plan $p5_plan p5_audit $p5_audit \
        p6_plan $p6_plan p6_audit $p6_audit \
        audit $base_audit metrics $metrics \
        expected_center_extras $expected_center_extras \
        base_extra_delta $base_extra_delta \
        clear $clear metadata $metadata capture $capture \
        compute_count $compute_count]
}

proc hap_p7_require_place_matches_live {place live} {
    set base [dict get $live base]
    set audit [dict get $live audit]
    set metrics [dict get $live metrics]
    set p5_plan [dict get $live p5_plan]
    set p6_plan [dict get $live p6_plan]
    foreach {summary_key plan_key} {
        dsp48e2 total_dsp uram288 total_uram
        mlp_kernel_dsp48e2 kernel_dsp
        history2_repack_instances history2_count
        generic_repack_instances generic_repack_count
        projection_weight_capture_ok projection_weight_capture_ok
    } {
        hap_require_summary $place $summary_key [dict get $base $plan_key]
    }
    foreach {key expected} {
        canonical_pblock_count 11 geometry_pblock_count 12
        p5_added_pblock_count 2 p6_added_pblock_count 2 total_pblock_count 27
        unplaced_primitives 0 wrong_slr_primitives 0
        completed_u8_ff 4096 completed_meta_ff 352
        input_capture_ff 12288 input_capture_controls 48
        p6_slr0_row_primitives 10696 p6_center_row_primitives 21392
        p6_slr2_row_primitives 10696
        p7_region2_rows0_3_primitives 26800
        p7_region2_rows4_7_primitives 26800
        p7_region2_residual_primitives 15199
        p7_region2_rows0_3_dsp48e2 272
        p7_region2_rows4_7_dsp48e2 272
        p7_region2_residual_dsp48e2 0
        compute_clock_buffer_none_missing_after_reapply 0
    } {
        hap_require_summary $place $key $expected
    }
    for {set index 0} {$index < 3} {incr index} {
        hap_require_summary $place slr${index}_dsp48e2 \
            [lindex [dict get $metrics slr_dsp] $index]
        hap_require_summary $place slr${index}_uram288 \
            [lindex [dict get $metrics slr_uram] $index]
    }
    if {[dict get $audit contract_variant] ne \
            [dict get $place contract_variant] ||
        [dict get $p5_plan contract] ne [dict get $place p5_contract] ||
        [dict get $p6_plan contract] ne [dict get $place p6_contract] ||
        [dict get $place p7_contract] ne \
            P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8 ||
        [dict get $place region2_variant] ne rowsplit_y5_y6_y6_y8} {
        error "P7 place/live contract mismatch"
    }
}

proc hap_p7_congestion_level6 {path} {
    set text [hap_read_nonempty $path "P7 post-route congestion report"]
    set rows 0
    set level6 0
    foreach line [split $text "\n"] {
        if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|} \
                $line -> direction type level]} {
            continue
        }
        incr rows
        if {$level >= 6} {incr level6}
    }
    if {$rows == 0 &&
        [string first "No congestion windows are found above level 5" $text] < 0 &&
        [string first \
            "No effective congestion windows are found above level 5" $text] < 0} {
        error "P6 congestion report schema is unrecognized"
    }
    return $level6
}

if {![string match "2025.2*" [version -short]] ||
    [llength [get_designs -quiet]] != 0} {
    error "P7 route requires fresh Vivado 2025.2"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P7 production route requires HAP_JOBS=32"
}
foreach {label value} [list pre_route_physopt $pre_physopt_directive \
        route $route_directive post_route_physopt $post_physopt_directive] {
    if {![regexp {^[A-Za-z][A-Za-z0-9_]*$} $value]} {
        error "Illegal P6 $label directive: $value"
    }
}
foreach {label path} [list post_place_dcp $in_dcp \
        place_summary $place_summary place_input_sha $place_input_sha \
        place_output_sha $place_output_sha \
        place_launcher_status $place_launcher_status \
        place_pre_gate $place_pre_gate place_fast_gate $place_fast_gate \
        selector_library $selector_lib geometry_library $geometry_lib \
        p5_library $p5_lib p6_library $p6_lib \
        io_selector_audit $io_audit clock_xdc $clock_xdc \
        route_helper $helper_lib route_launcher $expected_launcher] {
    hap_read_nonempty $path $label
}
foreach digest [list $expected_place_input_manifest_sha \
        $expected_place_output_manifest_sha $expected_route_input_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed P7 route manifest SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen_place_inputs [hap_verify_sha_manifest $place_input_sha 11 \
    $expected_place_input_manifest_sha]
set frozen_place_outputs [hap_verify_sha_manifest $place_output_sha -1 \
    $expected_place_output_manifest_sha]
set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 25 \
    $expected_route_input_manifest_sha]
hap_require_complete_place_output_manifest \
    $frozen_place_outputs $place_output_sha
foreach required [list $in_dcp $place_summary $place_input_sha \
        $place_output_sha $place_input_files $place_launcher_status \
        $place_selectors $place_geometry $place_geometry_placement \
        $place_base_pblocks $place_p5_plan $place_p5_pblocks \
        $place_p6_plan $place_p6_pblocks $place_pre_gate $place_fast_gate \
        $selector_lib $geometry_lib $p5_lib $p6_lib $io_audit $clock_xdc \
        $helper_lib $p7_route_script $expected_launcher] {
    hap_require_manifest_path $frozen_route_inputs $required p7_route_input
}
hap_require_exact_manifest_paths $frozen_route_inputs [list \
    $in_dcp $place_summary $place_input_sha $place_output_sha \
    $place_input_files $place_launcher_status $place_selectors $place_geometry \
    $place_geometry_placement $place_base_pblocks $place_p5_plan \
    $place_p5_pblocks $place_p6_plan $place_p6_pblocks $place_pre_gate \
    $place_fast_gate $selector_lib $geometry_lib $p5_lib $p6_lib $io_audit \
    $clock_xdc $helper_lib $p7_route_script $expected_launcher] p7_route_input
foreach required [list $selector_lib $geometry_lib $p5_lib $p6_lib $clock_xdc] {
    hap_require_manifest_path $frozen_place_inputs $required p7_place_input
}
hap_require_manifest_path $frozen_place_outputs $in_dcp post_place_dcp
hap_require_manifest_path $frozen_place_outputs $place_summary place_summary

set launcher [hap_parse_summary $place_launcher_status \
    "P7 place launcher status"]
foreach {key value} {
    status PASS flow_mode accept acceptance_evidence 1 route_eligible 1
    final_exit_code 0 vivado_exit_code 0 input_sha_recheck_exit_code 0
    input_manifest_sha_match 1 place_gate_exit_code 0 checkpoint_written 1
    implementation_commands_requested 1 bitstream_generated 0
} {
    hap_require_summary $launcher $key $value
}
set place [hap_parse_summary $place_summary "P7 place summary"]
foreach {key value} {
    status V5_P10_P7_PRODUCTION_PLACE_PASS
    stage V5_P10_P7_POST_PLACE_ACCEPT flow_mode accept
    acceptance_evidence 1 route_eligible 1 checkpoint_written 1
    input_manifest_entries 11 provenance_verified 1 pre_place_verified 1
    part xcvu9p-flga2104-2L-e top hap_attention_mlp_production_core
    contract_variant P2_COHORT16_COL2_12_2
    p5_contract P5_INPUT_HALF_LOCAL_8_8
    p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4
    p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8
    region2_variant rowsplit_y5_y6_y6_y8
    jobs 32 core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300
    dsp48e2 5453 uram288 752 mlp_kernel_dsp48e2 3072
    history2_repack_instances 2 generic_repack_instances 0
    projection_weight_capture_ok 1 canonical_pblock_count 11
    geometry_pblock_count 12 p5_added_pblock_count 2
    p6_added_pblock_count 2 total_pblock_count 27
    slr0_dsp48e2 1862 slr1_dsp48e2 1781 slr2_dsp48e2 1810
    slr0_uram288 224 slr1_uram288 224 slr2_uram288 304
    unplaced_primitives 0 wrong_slr_primitives 0
    completed_u8_ff 4096 completed_meta_ff 352
    input_capture_ff 12288 input_capture_controls 48
    p6_slr0_row_primitives 10696 p6_center_row_primitives 21392
    p6_slr2_row_primitives 10696
    p7_region2_rows0_3_primitives 26800
    p7_region2_rows4_7_primitives 26800
    p7_region2_residual_primitives 15199
    p7_region2_rows0_3_dsp48e2 272
    p7_region2_rows4_7_dsp48e2 272
    p7_region2_residual_dsp48e2 0
    compute_clock_buffer_none_missing_after_reapply 0
    pre_place_drc_errors 0 post_place_drc_errors 0
    false_path_exception_rows 0 datapath_only_exception_rows 0
    timing_coverage_ok 1 cdc_critical 0 data_bufg 0
    congestion_level6_or_higher_windows 0
    resource_ok 1 structure_ok 1 placement_ok 1 optimizer_extras_ok 1
    fast_gate_ok 1 policy_ok 1 level5_screen_ok 1 level6_congestion_ok 1
} {
    hap_require_summary $place $key $value
}
set pre_gate [hap_parse_summary $place_pre_gate "P7 pre-place gate"]
foreach {key value} {
    status V5_P10_P7_PRE_PLACE_IN_PROCESS_PASS
    pre_place_lineage_verified 1 pblock_count 27
    base_pblock_count 11 geometry_pblock_count 12
    p5_pblock_count 2 p6_pblock_count 2
    p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8
    region2_variant rowsplit_y5_y6_y6_y8
    p5_outer_extras 0 p6_outer_extras 0
    pre_place_drc_errors 0 implementation_commands_run 0
    checkpoint_written 0 route_eligible 0
} {
    hap_require_summary $pre_gate $key $value
}
set fast_gate [hap_parse_summary $place_fast_gate "P7 post-place fast gate"]
foreach {key value} {
    resource_ok 1 structure_ok 1 placement_ok 1 optimizer_extras_ok 1
    pre_place_drc_errors 0 post_place_drc_errors 0
    data_bufg 0
    level6_or_higher_windows 0 fast_gate_ok 1
} {
    hap_require_summary $fast_gate $key $value
}
hap_xdc_contract $clock_xdc

source $selector_lib
source $geometry_lib
source $p5_lib
source $p6_lib
open_checkpoint $in_dcp
set actual_part [get_property PART [current_design]]
set actual_top [get_property TOP [current_design]]
if {$actual_part ne $expected_part || $actual_top ne $expected_top} {
    error "Illegal P7 route input identity: $actual_part/$actual_top"
}
hap_clock_contract
source $io_audit
set input_live [hap_p7_audit_live $out input V5_P7_ROUTE_INPUT]
hap_p7_require_place_matches_live $place $input_live

set operation_ok 1
set operation_stage pre_route_phys_opt
set operation_message ""
if {[catch {phys_opt_design -directive $pre_physopt_directive} \
        operation_message operation_options]} {
    set operation_ok 0
}
set pre_route_compute_nets 0
set pre_route_compute_missing_before 0
set pre_route_compute_missing_after 0
if {$operation_ok} {
    if {[catch {lassign [hap_p7_reapply_compute_policy] \
            pre_route_compute_nets pre_route_compute_missing_before \
            pre_route_compute_missing_after} operation_message]} {
        set operation_ok 0
        set operation_stage pre_route_compute_policy
    }
}
set post_phys_opt_written 0
if {[catch {write_checkpoint -force [file join $out post_phys_opt.dcp]} \
        checkpoint_message]} {
    set operation_ok 0
    append operation_message " | post_phys_opt checkpoint: $checkpoint_message"
    set operation_stage write_post_phys_opt
} else {
    set post_phys_opt_written 1
}
if {$operation_ok} {
    if {![hap_safe_report $out timing_post_phys_opt [list \
            report_timing_summary -delay_type min_max -max_paths 100 \
            -report_unconstrained -file \
            [file join $out timing_post_phys_opt.rpt]]]} {
        set operation_ok 0
        set operation_stage report_timing_post_phys_opt
        set operation_message "post-phys-opt timing report failed"
    } else {
        set operation_stage route_design
        if {[catch {route_design -directive $route_directive} \
                operation_message operation_options]} {
            set operation_ok 0
        }
    }
}

set post_setup_physopt_applied 0
set post_hold_physopt_applied 0
set setup_compute_missing_before 0
set hold_compute_missing_before 0
if {$operation_ok} {
    if {[catch {set preliminary_wns [hap_first_slack max]
            set preliminary_whs [hap_first_slack min]} \
            operation_message operation_options]} {
        set operation_ok 0
        set operation_stage preliminary_timing_query
    }
}
if {$operation_ok && $preliminary_wns < 0.0} {
    set post_setup_physopt_applied 1
    set operation_stage post_route_setup_phys_opt
    if {[catch {phys_opt_design -directive $post_physopt_directive
            lassign [hap_p7_reapply_compute_policy] setup_compute_nets \
                setup_compute_missing_before setup_compute_missing_after
            route_design -preserve} operation_message operation_options]} {
        set operation_ok 0
    }
}
if {$operation_ok} {
    if {[catch {set after_setup_whs [hap_first_slack min]} \
            operation_message operation_options]} {
        set operation_ok 0
        set operation_stage post_setup_timing_query
    }
}
if {$operation_ok && $after_setup_whs < 0.0} {
    set post_hold_physopt_applied 1
    set operation_stage post_route_hold_phys_opt
    if {[catch {phys_opt_design -hold_fix
            lassign [hap_p7_reapply_compute_policy] hold_compute_nets \
                hold_compute_missing_before hold_compute_missing_after
            route_design -preserve} operation_message operation_options]} {
        set operation_ok 0
    }
}
set final_compute_nets 0
set final_compute_missing_before 0
set final_compute_missing_after 0
if {[catch {lassign [hap_p7_reapply_compute_policy] final_compute_nets \
        final_compute_missing_before final_compute_missing_after} \
        final_compute_message]} {
    set operation_ok 0
    append operation_message " | final compute policy: $final_compute_message"
    set operation_stage final_compute_policy
}

# Preserve a diagnostic checkpoint on every completed route attempt. The
# route-eligible checkpoint is written only after all final gates pass.
set diagnostic_checkpoint_written 0
if {![catch {write_checkpoint -force \
        [file join $out post_route_diagnostic.dcp]}]} {
    set diagnostic_checkpoint_written 1
}

set report_ok 1
foreach {label command} [list \
    utilization_post_route [list report_utilization -file \
        [file join $out utilization_post_route.rpt]] \
    utilization_hier_post_route [list report_utilization -hierarchical \
        -hierarchical_depth 12 -file \
        [file join $out utilization_hier_post_route.rpt]] \
    utilization_slr_post_route [list report_utilization -slr -file \
        [file join $out utilization_slr_post_route.rpt]] \
    timing_setup_worst100_post_route [list report_timing -delay_type max \
        -max_paths 100 -path_type full_clock_expanded -file \
        [file join $out timing_setup_worst100_post_route.rpt]] \
    timing_hold_worst100_post_route [list report_timing -delay_type min \
        -max_paths 100 -path_type full_clock_expanded -file \
        [file join $out timing_hold_worst100_post_route.rpt]] \
    drc_post_route [list report_drc -file \
        [file join $out drc_post_route.rpt]] \
    cdc_post_route [list report_cdc -details -file \
        [file join $out cdc_post_route.rpt]] \
    clock_interaction_post_route [list report_clock_interaction \
        -delay_type min_max -file \
        [file join $out clock_interaction_post_route.rpt]] \
    clock_utilization_post_route [list report_clock_utilization -file \
        [file join $out clock_utilization_post_route.rpt]] \
    congestion_post_route [list report_design_analysis -congestion -file \
        [file join $out congestion_post_route.rpt]] \
    exceptions_coverage_post_route [list report_exceptions -coverage -file \
        [file join $out exceptions_coverage_post_route.rpt]]] {
    if {![hap_safe_report $out $label $command]} {set report_ok 0}
}
set timing_text ""
if {[catch {set timing_text [report_timing_summary -delay_type min_max \
        -max_paths 100 -report_unconstrained -warn_on_violation \
        -return_string]} timing_message]} {
    set report_ok 0
    hap_write_text [file join $out timing_post_route.error.txt] \
        "message=$timing_message\n"
} else {
    hap_write_text [file join $out timing_post_route.rpt] $timing_text
}
set route_text ""
if {[catch {set route_text [report_route_status -return_string]} \
        route_report_message]} {
    set report_ok 0
    hap_write_text [file join $out route_status_post_route.error.txt] \
        "message=$route_report_message\n"
} else {
    hap_write_text [file join $out route_status_post_route.rpt] $route_text
}

set audit_ok 1
set audit_message ""
if {[catch {
    set final_live [hap_p7_audit_live $out post_route V5_P7_ROUTE_FINAL]
    set final_base [dict get $final_live base]
    set final_audit [dict get $final_live audit]
    set final_geometry_plan [dict get $final_live geometry]
    set final_geometry_audit [dict get $final_live geometry_audit]
    set final_geometry_placement [dict get $final_live geometry_placement]
    set final_p5_plan [dict get $final_live p5_plan]
    set final_p5_audit [dict get $final_live p5_audit]
    set final_p6_plan [dict get $final_live p6_plan]
    set final_p6_audit [dict get $final_live p6_audit]
    set final_base_extra_delta [dict get $final_live base_extra_delta]
    set final_metrics [dict get $final_live metrics]
    set final_clear [dict get $final_live clear]
    set final_metadata [dict get $final_live metadata]
    set final_capture [dict get $final_live capture]
    set utilization [hap_utilization_totals \
        [file join $out utilization_post_route.rpt]]
    set resource_ok [expr {
        [dict get $final_base total_dsp] == 5453 &&
        [dict get $final_base total_uram] == 752 &&
        [dict get $utilization dsp] == 5453 &&
        [dict get $utilization uram] == 752 &&
        [dict get $final_base kernel_dsp] == 3072 &&
        [dict get $final_base history2_count] == 2 &&
        [dict get $final_base generic_repack_count] == 0 &&
        [dict get $final_base projection_weight_capture_ok] == 1}]
    set physical_ok [expr {
        [hap_v5_floorplan::physical_ok $final_base $final_metrics] &&
        [dict get $final_audit ok] &&
        [dict get $final_audit pblock_count] == 11 &&
        [dict get $final_audit placed_wrong] == 0 &&
        $final_base_extra_delta >= 0 && $final_base_extra_delta <= 4096 &&
        [dict get $final_geometry_audit pblock_count] == 12 &&
        [dict get $final_geometry_plan center_region2_row_exact_cover] == 1 &&
        [llength [dict get $final_geometry_plan \
            center_region2_rows0_3_primitives]] == 26800 &&
        [llength [dict get $final_geometry_plan \
            center_region2_rows4_7_primitives]] == 26800 &&
        [llength [dict get $final_geometry_plan \
            center_region2_residual_primitives]] == 15199 &&
        [dict get $final_geometry_placement ok] &&
        [dict get $final_p5_audit ok] &&
        [dict get $final_p5_audit pblock_count] == 2 &&
        [dict get $final_p5_audit center_wrong] == 0 &&
        [dict get $final_p5_audit outer_wrong] == 0 &&
        [dict get $final_p5_audit outer_extras] <= 4096 &&
        [dict get $final_p6_audit ok] &&
        [dict get $final_p6_audit pblock_count] == 2 &&
        [dict get $final_p6_audit center_wrong] == 0 &&
        [dict get $final_p6_audit outer_wrong] == 0 &&
        [dict get $final_p6_audit outer_extras] <= 4096 &&
        [llength [get_pblocks -quiet]] == 27}]
    set architecture_boundary_ok 1
    hap_clock_contract
    set wns [hap_first_slack max]
    set whs [hap_first_slack min]
    set route_errors [hap_route_row $route_text \
        "# of nets with routing errors" 1]
    set explicit_gaps [hap_route_row $route_text \
        "# of nets with explicit gaps"]
    set unrouted_rows [hap_route_row $route_text "# of unrouted nets"]
    set unrouted_pins [hap_route_row $route_text \
        "# of nets with some unrouted pins"]
    set resource_conflicts [hap_route_row $route_text \
        "# of nets with resource conflicts"]
    set antennas [hap_route_row $route_text \
        "# of nets with antennas/islands"]
    set partial_nets [llength [get_nets -quiet -hierarchical -filter {
        ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
        ROUTE_STATUS == UNROUTED || ROUTE_STATUS == HIERPORT}]]
    set conflict_nets [llength [get_nets -quiet -hierarchical -filter {
        ROUTE_STATUS == CONFLICTS}]]
    set route_clean [expr {$route_errors == 0 && $explicit_gaps == 0 &&
        $unrouted_rows == 0 && $unrouted_pins == 0 &&
        $resource_conflicts == 0 && $antennas == 0 &&
        $partial_nets == 0 && $conflict_nets == 0}]
    set no_clock [hap_timing_count $timing_text no_clock]
    set unconstrained [hap_timing_count $timing_text \
        unconstrained_internal_endpoints]
    set no_input_delay [hap_timing_count $timing_text no_input_delay]
    set no_output_delay [hap_timing_count $timing_text no_output_delay]
    set partial_input_delay [hap_timing_count $timing_text partial_input_delay]
    set partial_output_delay [hap_timing_count $timing_text partial_output_delay]
    set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
        $no_input_delay == 3 && $no_output_delay == 0 &&
        $partial_input_delay == 0 && $partial_output_delay == 0}]
    set drc_errors [llength [get_drc_violations -quiet -filter {
        SEVERITY == Error}]]
    set drc_report_error_rows [hap_drc_error_rows \
        [file join $out drc_post_route.rpt]]
    set cdc_critical [hap_cdc_critical [file join $out cdc_post_route.rpt]]
    set congestion_level6 [hap_p7_congestion_level6 \
        [file join $out congestion_post_route.rpt]]
    lassign [hap_bufg_counts] clock_bufg data_bufg
    set exception_text [hap_read_nonempty \
        [file join $out exceptions_coverage_post_route.rpt] \
        "P7 post-route exception report"]
    set false_path_rows [regexp -all -line \
        {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} \
        $exception_text]
    set datapath_only_rows [regexp -all -line \
        {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} \
        $exception_text]
    set policy_ok [expr {$drc_errors == 0 && $drc_report_error_rows == 0 &&
        $cdc_critical == 0 && $data_bufg == 0 && $false_path_rows == 0 &&
        $datapath_only_rows == 0 && $timing_coverage_ok &&
        $congestion_level6 == 0 && $final_compute_missing_after == 0}]
    set frozen_place_inputs_post [hap_verify_sha_manifest $place_input_sha 11 \
        $expected_place_input_manifest_sha]
    set frozen_place_outputs_post [hap_verify_sha_manifest $place_output_sha -1 \
        $expected_place_output_manifest_sha]
    set frozen_route_inputs_post [hap_verify_sha_manifest $route_input_sha 25 \
        $expected_route_input_manifest_sha]
    hap_require_complete_place_output_manifest \
        $frozen_place_outputs_post $place_output_sha
    if {$frozen_place_inputs_post ne $frozen_place_inputs ||
        $frozen_place_outputs_post ne $frozen_place_outputs ||
        $frozen_route_inputs_post ne $frozen_route_inputs} {
        error "Frozen P7 route input set changed during Vivado"
    }
} audit_message audit_options]} {
    set audit_ok 0
}
if {!$audit_ok} {
    hap_write_failure $out final_audit $audit_message
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list tool [version -short] part $actual_part \
            top $actual_top input_dcp $in_dcp operation_ok $operation_ok \
            report_ok $report_ok audit_ok 0 audit_error \
            [string map [list "\n" " | " "\r" " "] $audit_message] \
            route_eligible 0 checkpoint_written 0 \
            status V5_P10_P7_PRODUCTION_OOC_ROUTE_FAIL] {
        puts $fp "$key=$value"
    }
    close $fp
    close_design
    error "P7 production route final audit failed: $audit_message"
}

set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set status [expr {$operation_ok && $report_ok && $resource_ok &&
    $physical_ok && $architecture_boundary_ok && $timing_ok &&
    $route_clean && $policy_ok ?
    "V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS" :
    "V5_P10_P7_PRODUCTION_OOC_ROUTE_FAIL"}]
set route_eligible [expr {
    $status eq "V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS"}]
set checkpoint_written 0
if {$route_eligible} {
    write_checkpoint -force [file join $out post_route.dcp]
    set checkpoint_written 1
}
set slr_dsp [dict get $final_metrics slr_dsp]
set slr_uram [dict get $final_metrics slr_uram]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $actual_part top $actual_top \
    evidence_class P7_PRODUCTION_CORE_OOC_POST_ROUTE jobs $jobs \
    input_dcp $in_dcp input_place_summary $place_summary \
    input_place_sha256 [hap_sha256 $in_dcp] \
    pre_route_physopt_directive $pre_physopt_directive \
    route_directive $route_directive \
    post_route_physopt_directive $post_physopt_directive \
    post_phys_opt_checkpoint_written $post_phys_opt_written \
    diagnostic_checkpoint_written $diagnostic_checkpoint_written \
    post_setup_physopt_applied $post_setup_physopt_applied \
    post_hold_physopt_applied $post_hold_physopt_applied \
    core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    input_sha_manifests_verified 1 place_input_manifest_entries 11 \
    place_input_manifest_sha256 $expected_place_input_manifest_sha \
    place_output_manifest_entries [dict size $frozen_place_outputs] \
    place_output_manifest_sha256 $expected_place_output_manifest_sha \
    route_input_manifest_entries 25 \
    route_input_manifest_sha256 $expected_route_input_manifest_sha \
    base_contract_variant $base_contract \
    p5_contract $p5_contract p6_contract $p6_contract \
    p7_contract $p7_contract region2_variant $region2_variant \
    dsp48e2 [dict get $final_base total_dsp] \
    uram288 [dict get $final_base total_uram] \
    mlp_kernel_dsp48e2 [dict get $final_base kernel_dsp] \
    history2_repack_instances [dict get $final_base history2_count] \
    generic_repack_instances [dict get $final_base generic_repack_count] \
    projection_weight_capture_ok \
        [dict get $final_base projection_weight_capture_ok] \
    pblock_count [llength [get_pblocks -quiet]] \
    canonical_pblock_count [dict get $final_audit pblock_count] \
    geometry_pblock_count [dict get $final_geometry_audit pblock_count] \
    p5_added_pblock_count [dict get $final_p5_audit pblock_count] \
    p6_added_pblock_count [dict get $final_p6_audit pblock_count] \
    pblock_dsp_coverage [dict get $final_audit dsp_coverage] \
    pblock_uram_coverage [dict get $final_audit uram_coverage] \
    pblock_wrong_slr [dict get $final_audit placed_wrong] \
    pblock_optimizer_extras [dict get $final_audit optimizer_extra_count] \
    base_optimizer_extra_delta $final_base_extra_delta \
    p5_center_wrong_slr [dict get $final_p5_audit center_wrong] \
    p5_outer_wrong_slr [dict get $final_p5_audit outer_wrong] \
    p5_outer_optimizer_extras [dict get $final_p5_audit outer_extras] \
    p6_center_wrong_slr [dict get $final_p6_audit center_wrong] \
    p6_outer_wrong_slr [dict get $final_p6_audit outer_wrong] \
    p6_outer_optimizer_extras [dict get $final_p6_audit outer_extras] \
    p6_slr0_row_primitives [llength [dict get $final_p6_plan slr0_rows]] \
    p6_center_row_primitives [llength [dict get $final_p6_plan center_rows]] \
    p6_slr2_row_primitives [llength [dict get $final_p6_plan slr2_rows]] \
    p7_region2_rows0_3_primitives [llength [dict get $final_geometry_plan \
        center_region2_rows0_3_primitives]] \
    p7_region2_rows4_7_primitives [llength [dict get $final_geometry_plan \
        center_region2_rows4_7_primitives]] \
    p7_region2_residual_primitives [llength [dict get $final_geometry_plan \
        center_region2_residual_primitives]] \
    p7_region2_rows0_3_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $final_geometry_plan center_region2_rows0_3_primitives] \
        DSP48E2] \
    p7_region2_rows4_7_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $final_geometry_plan center_region2_rows4_7_primitives] \
        DSP48E2] \
    p7_region2_residual_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $final_geometry_plan center_region2_residual_primitives] \
        DSP48E2] \
    completed_u8_ff [dict get $final_p5_plan completed_u8_ff] \
    completed_meta_ff [dict get $final_p5_plan completed_meta_ff] \
    input_capture_ff [dict get $final_p5_plan input_capture_ff] \
    input_capture_controls [dict get $final_p5_plan capture_leaf_count] \
    slr0_dsp48e2 [lindex $slr_dsp 0] slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] \
    slr0_uram288 [lindex $slr_uram 0] slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    unplaced_primitives [dict get $final_metrics unplaced] \
    wrong_slr_primitives [dict get $final_metrics wrong_total] \
    metadata_local_write_protected_ff [dict get $final_metadata protected] \
    mlp_capture_leaf_instances [dict get $final_capture instances] \
    mlp_capture_leaf_lut1 [dict get $final_capture lut1] \
    pre_route_compute_missing_before $pre_route_compute_missing_before \
    pre_route_compute_missing_after $pre_route_compute_missing_after \
    setup_compute_missing_before $setup_compute_missing_before \
    hold_compute_missing_before $hold_compute_missing_before \
    final_compute_nets $final_compute_nets \
    final_compute_missing_before $final_compute_missing_before \
    final_compute_missing_after $final_compute_missing_after \
    wns_ns $wns whs_ns $whs route_error_nets $route_errors \
    explicit_gap_nets $explicit_gaps unrouted_nets $unrouted_rows \
    some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial $partial_nets route_status_conflicts $conflict_nets \
    route_clean $route_clean drc_errors $drc_errors \
    drc_report_error_rows $drc_report_error_rows \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    congestion_level6_or_higher_windows $congestion_level6 \
    operation_ok $operation_ok report_ok $report_ok resource_ok $resource_ok \
    physical_ok $physical_ok architecture_boundary_ok $architecture_boundary_ok \
    timing_ok $timing_ok policy_ok $policy_ok route_eligible $route_eligible \
    checkpoint_written $checkpoint_written bitstream_generated 0 \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
if {!$operation_ok} {hap_write_failure $out $operation_stage $operation_message}
close_design
if {!$route_eligible} {error "P6 production OOC post-route acceptance failed"}
