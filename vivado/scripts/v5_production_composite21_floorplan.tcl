# Composite production floorplan layered over the qualified Fine19 hard
# resource plan. P9 splits the central MLP frontends from the SLR1-wide
# residual and anchors them east of projection region2/region3.

namespace eval hap_v5_composite21 {
    variable contract_variant P9_COHORT16_MLP_CENTRAL_X2X4_21
    variable expected_fine_variant P3_COHORT16_OOC10_19
    variable expected_fine_members 1432847
    variable expected_mlp_residual_members 285796
    variable expected_attention_direct_members 71350
    variable expected_central_island_members 197091
    variable expected_mlp_remaining_members 88785
    variable expected_center_dsp_remaining 5
    variable central_anchor_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9
    variable post_place_delta_limit 65536
    variable attention_direct_constrained 0
}

proc hap_v5_composite21::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "V5 composite21 $label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_v5_composite21::spec_member_union {specs} {
    set result {}
    foreach spec $specs {
        set result [concat $result [hap_v5_fine19::pblockable \
            [dict get $spec cells]]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_composite21::discover {base_plan fine_plan
        {allow_optimizer_changes 0}} {
    variable contract_variant
    variable expected_fine_variant
    variable expected_fine_members
    variable expected_mlp_residual_members
    variable expected_attention_direct_members
    variable expected_central_island_members
    variable expected_mlp_remaining_members
    variable expected_center_dsp_remaining
    variable central_anchor_range
    variable post_place_delta_limit
    variable attention_direct_constrained
    if {$allow_optimizer_changes != 0 && $allow_optimizer_changes != 1} {
        error "V5 composite21 allow_optimizer_changes must be 0 or 1"
    }
    if {[dict get $fine_plan contract_variant] ne $expected_fine_variant} {
        error "V5 composite21 requires the Fine19 base contract"
    }

    set fine_specs [hap_v5_fine19::full_specs $base_plan $fine_plan]
    require_count fine_spec_count $fine_specs 19
    set fine_members [spec_member_union $fine_specs]

    set mlp_roots [hap_v5_floorplan::module_cells hap_mlp_full_command16_s45]
    set attention_compute_roots [hap_v5_floorplan::module_cells \
        hap_attention_compute_cohort16_top]
    require_count mlp_roots $mlp_roots 1
    require_count attention_compute_roots $attention_compute_roots 1
    set mlp_root [lindex $mlp_roots 0]
    set attention_compute_root [lindex $attention_compute_roots 0]
    set attention_kv_quant_root [hap_v5_fine19::child \
        $attention_compute_root u_kv_quantizer4 attention_kv_quant_root]
    set attention_rope_root [hap_v5_fine19::child \
        $attention_compute_root u_rope attention_rope_root]

    set mlp_primitives [hap_v5_fine19::pblockable_descendants $mlp_root]
    set mlp_residual [hap_v5_floorplan::list_subtract \
        $mlp_primitives $fine_members]
    set attention_compute_primitives [hap_v5_fine19::pblockable_descendants \
        $attention_compute_root]
    set attention_uncovered [hap_v5_floorplan::list_subtract \
        $attention_compute_primitives $fine_members]
    set attention_kv_quant [hap_v5_floorplan::list_intersection \
        $attention_uncovered [hap_v5_fine19::pblockable_descendants \
            $attention_kv_quant_root]]
    set attention_rope [hap_v5_floorplan::list_intersection \
        $attention_uncovered [hap_v5_fine19::pblockable_descendants \
            $attention_rope_root]]
    set attention_direct [hap_v5_floorplan::list_subtract \
        $attention_uncovered [hap_v5_floorplan::list_union \
            $attention_kv_quant $attention_rope]]

    set swiglu_roots [hap_v5_floorplan::module_cells \
        hap_mlp_swiglu_product_frontend16_q4]
    set input_frontend_roots [hap_v5_floorplan::module_cells \
        hap_mlp_input_frontend16_compact_cache]
    require_count central_swiglu_roots $swiglu_roots 1
    require_count central_input_frontend_roots $input_frontend_roots 1
    set swiglu_all [hap_v5_fine19::pblockable_descendants \
        [lindex $swiglu_roots 0]]
    set swiglu_leaf_union [hap_v5_floorplan::list_union \
        [dict get $base_plan leaf0_primitives] \
        [dict get $base_plan leaf1_primitives]]
    set swiglu_central [hap_v5_floorplan::list_subtract \
        $swiglu_all $swiglu_leaf_union]
    set input_frontend [hap_v5_fine19::pblockable_descendants \
        [lindex $input_frontend_roots 0]]
    set central_island [hap_v5_floorplan::list_union \
        $swiglu_central $input_frontend]
    set center_dsp [dict get $fine_plan nonprojection_center_dsp]
    set movable_source [hap_v5_floorplan::list_union \
        $mlp_residual $center_dsp]
    set central_island_outside_source [hap_v5_floorplan::list_subtract \
        $central_island $movable_source]
    set mlp_remaining [hap_v5_floorplan::list_subtract \
        $mlp_residual $central_island]
    set center_dsp_remaining [hap_v5_floorplan::list_subtract \
        $center_dsp $central_island]
    set central_partition [hap_v5_floorplan::list_union \
        $central_island $mlp_remaining $center_dsp_remaining]
    if {[llength $central_island_outside_source] != 0 ||
        [hap_v5_floorplan::object_names $central_partition] ne
            [hap_v5_floorplan::object_names $movable_source]} {
        error "V5 composite21 P9 central partition is not exact"
    }
    if {[hap_v5_floorplan::count_ref $central_island DSP48E2] != 80 ||
        [hap_v5_floorplan::count_ref $central_island URAM288] != 0 ||
        [hap_v5_floorplan::count_ref $mlp_remaining DSP48E2] != 0 ||
        [hap_v5_floorplan::count_ref $mlp_remaining URAM288] != 0 ||
        [hap_v5_floorplan::count_ref $center_dsp_remaining DSP48E2] !=
            $expected_center_dsp_remaining} {
        error "V5 composite21 P9 central hard-resource signature mismatch"
    }

    set fine_mlp_overlap [hap_v5_floorplan::list_intersection \
        $fine_members $mlp_residual]
    set fine_attention_overlap [hap_v5_floorplan::list_intersection \
        $fine_members $attention_direct]
    set extra_overlap [hap_v5_floorplan::list_intersection \
        $mlp_residual $attention_direct]
    if {[llength $fine_mlp_overlap] != 0 ||
        [llength $fine_attention_overlap] != 0 ||
        [llength $extra_overlap] != 0} {
        error "V5 composite21 logic owners overlap the Fine19 partition"
    }
    if {[hap_v5_floorplan::count_ref $mlp_residual DSP48E2] != 0 ||
        [hap_v5_floorplan::count_ref $mlp_residual URAM288] != 0 ||
        [hap_v5_floorplan::count_ref $attention_direct DSP48E2] != 0 ||
        [hap_v5_floorplan::count_ref $attention_direct URAM288] != 0} {
        error "V5 composite21 residual owners contain DSP/URAM"
    }

    set fine_delta [expr {[llength $fine_members] - $expected_fine_members}]
    set mlp_delta [expr {[llength $mlp_residual] -
        $expected_mlp_residual_members}]
    set attention_delta [expr {[llength $attention_direct] -
        $expected_attention_direct_members}]
    set central_island_delta [expr {[llength $central_island] -
        $expected_central_island_members}]
    set mlp_remaining_delta [expr {[llength $mlp_remaining] -
        $expected_mlp_remaining_members}]
    if {!$allow_optimizer_changes &&
        ($fine_delta != 0 || $mlp_delta != 0 || $attention_delta != 0 ||
         $central_island_delta != 0 || $mlp_remaining_delta != 0)} {
        error "V5 composite21 pre-place signature mismatch: fine/mlp/attention/island/remaining=$fine_delta/$mlp_delta/$attention_delta/$central_island_delta/$mlp_remaining_delta"
    }
    if {$allow_optimizer_changes &&
        (abs($fine_delta) > $post_place_delta_limit ||
         abs($mlp_delta) > $post_place_delta_limit ||
         abs($attention_delta) > $post_place_delta_limit ||
         abs($central_island_delta) > $post_place_delta_limit ||
         abs($mlp_remaining_delta) > $post_place_delta_limit)} {
        error "V5 composite21 post-place optimizer delta exceeds limit: fine/mlp/attention/island/remaining=$fine_delta/$mlp_delta/$attention_delta/$central_island_delta/$mlp_remaining_delta"
    }

    return [dict create contract_variant $contract_variant \
        allow_optimizer_changes $allow_optimizer_changes \
        fine_member_count [llength $fine_members] fine_member_delta $fine_delta \
        mlp_residual_primitives $mlp_residual \
        mlp_residual_count [llength $mlp_residual] \
        mlp_residual_delta $mlp_delta \
        central_anchor_range $central_anchor_range \
        central_island_primitives $central_island \
        central_island_count [llength $central_island] \
        central_island_delta $central_island_delta \
        central_island_dsp [hap_v5_floorplan::count_ref \
            $central_island DSP48E2] \
        mlp_remaining_primitives $mlp_remaining \
        mlp_remaining_count [llength $mlp_remaining] \
        mlp_remaining_delta $mlp_remaining_delta \
        center_dsp_remaining_primitives $center_dsp_remaining \
        center_dsp_remaining_count [llength $center_dsp_remaining] \
        center_dsp_remaining_dsp [hap_v5_floorplan::count_ref \
            $center_dsp_remaining DSP48E2] \
        central_partition_ok 1 \
        attention_direct_primitives $attention_direct \
        attention_direct_count [llength $attention_direct] \
        attention_direct_delta $attention_delta \
        attention_kv_quant_count [llength $attention_kv_quant] \
        attention_rope_count [llength $attention_rope] \
        owner_overlap 0 hard_resource_intrusion 0 exact_partition 1 \
        attention_direct_constrained $attention_direct_constrained]
}

proc hap_v5_composite21::full_specs {base_plan fine_plan composite_plan} {
    variable contract_variant
    if {[dict get $composite_plan contract_variant] ne $contract_variant} {
        error "V5 composite21 plan variant mismatch"
    }
    set specs {}
    foreach spec [hap_v5_fine19::full_specs $base_plan $fine_plan] {
        if {[dict get $spec name] eq "pb_v5_center_nonprojection_dsp_slr1"} {
            continue
        }
        lappend specs $spec
    }
    lappend specs \
        [dict create name pb_v5_mlp_central_frontends_cr_x2y5_x4y9 \
            target 1 range [dict get $composite_plan central_anchor_range] \
            soft 0 cells [dict get $composite_plan central_island_primitives]] \
        [dict create name pb_v5_center_nonprojection_dsp_residual_slr1 \
            target 1 range SLR1 soft 0 \
            cells [dict get $composite_plan center_dsp_remaining_primitives]] \
        [dict create name pb_v5_mlp_residual_without_central_frontends_slr1 \
            target 1 range SLR1 soft 0 \
            cells [dict get $composite_plan mlp_remaining_primitives]]
    return $specs
}

proc hap_v5_composite21::apply {base_plan fine_plan composite_plan} {
    hap_v5_fine19::apply_specs \
        [full_specs $base_plan $fine_plan $composite_plan]
}

proc hap_v5_composite21::audit {base_plan fine_plan composite_plan
        require_placed} {
    variable contract_variant
    return [hap_v5_fine19::audit_specs \
        [full_specs $base_plan $fine_plan $composite_plan] \
        $contract_variant $require_placed]
}

proc hap_v5_composite21::physical_metrics {audit} {
    variable contract_variant
    foreach name {
        pb_v5_mlp_central_frontends_cr_x2y5_x4y9
        pb_v5_center_nonprojection_dsp_residual_slr1
        pb_v5_mlp_residual_without_central_frontends_slr1
    } {
        if {![dict exists $audit records $name placed_wrong]} {
            error "V5 composite21 physical metrics are missing P9 pblock record: $name"
        }
    }
    set central_island_wrong [dict get $audit records \
        pb_v5_mlp_central_frontends_cr_x2y5_x4y9 placed_wrong]
    set center_dsp_remaining_wrong [dict get $audit records \
        pb_v5_center_nonprojection_dsp_residual_slr1 placed_wrong]
    set mlp_remaining_wrong [dict get $audit records \
        pb_v5_mlp_residual_without_central_frontends_slr1 placed_wrong]

    # Fine19 classifies the original center-DSP pblock as a center owner. P9
    # splits those DSPs between the central island and a five-DSP residual, so
    # provide a metrics-only compatibility record without mutating the audit.
    set compatibility_audit $audit
    dict set compatibility_audit records \
        pb_v5_center_nonprojection_dsp_slr1 placed_wrong \
        [expr {$central_island_wrong + $center_dsp_remaining_wrong}]
    set metrics [hap_v5_fine19::physical_metrics \
        $compatibility_audit $contract_variant]
    dict set metrics central_island_wrong $central_island_wrong
    dict set metrics center_dsp_remaining_wrong $center_dsp_remaining_wrong
    dict set metrics mlp_remaining_wrong $mlp_remaining_wrong
    return $metrics
}

proc hap_v5_composite21::physical_ok {metrics} {
    return [hap_v5_fine19::physical_ok $metrics]
}

proc hap_v5_composite21::write_discovery {plan path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    foreach key {contract_variant allow_optimizer_changes fine_member_count
            fine_member_delta mlp_residual_count mlp_residual_delta
            central_anchor_range central_island_count central_island_delta
            central_island_dsp mlp_remaining_count mlp_remaining_delta
            center_dsp_remaining_count center_dsp_remaining_dsp
            central_partition_ok
            attention_direct_count attention_direct_delta
            attention_kv_quant_count attention_rope_count owner_overlap
            hard_resource_intrusion exact_partition
            attention_direct_constrained} {
        puts $fp "$key=[dict get $plan $key]"
    }
    close $fp
}

proc hap_v5_composite21::write_audit {audit path marker} {
    hap_v5_fine19::write_audit $audit $path $marker
}
