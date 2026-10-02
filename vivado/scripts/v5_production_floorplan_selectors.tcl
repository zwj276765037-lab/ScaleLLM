# Shared, read-only hierarchy/resource selectors for the V5 production
# floorplan.  This file only defines procedures.  Both the selector audit and
# the placement flow source it so that a successful preflight cannot drift
# away from the cells that placement later constrains.

namespace eval hap_v5_floorplan {
    variable expected_part xcvu9p-flga2104-2L-e
    variable expected_top hap_attention_mlp_production_core
    variable slr_dsp_limit 1900
    variable slr_dsp_target 1884
    # String-only device geometry cache.  Never retain Vivado object handles
    # across place/route/design reopen; cache only immutable site names and
    # their owning SLR index for the currently loaded part.
    variable site_slr_part ""
    variable site_to_slr_cache [dict create]
    variable slr_site_names_cache [list {} {} {}]
}

proc hap_v5_floorplan::module_cells {module_name} {
    # ORIG_REF_NAME is the stable synthesis identity.  REF_NAME is retained as
    # an exact fallback for checkpoints that do not carry ORIG_REF_NAME.
    return [lsort -dictionary [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc hap_v5_floorplan::primitive_descendants {root} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique \
        [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ ${root_name}/*"]]
}

proc hap_v5_floorplan::primitive_descendants_of_ref {root ref_name} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique \
        [get_cells -quiet -hierarchical -filter \
            "REF_NAME == $ref_name && NAME =~ ${root_name}/*"]]
}

proc hap_v5_floorplan::primitive_descendants_except_ref {root ref_name} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique \
        [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && REF_NAME != $ref_name && NAME =~ ${root_name}/*"]]
}

proc hap_v5_floorplan::cell_is_below {cell root} {
    set name [get_property NAME $cell]
    set prefix "[get_property NAME $root]/"
    return [expr {[string first $prefix $name] == 0}]
}

proc hap_v5_floorplan::list_subtract {left right} {
    array set excluded {}
    foreach item $right {set excluded($item) 1}
    set result {}
    foreach item $left {
        if {![info exists excluded($item)]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::list_union {args} {
    set result {}
    foreach values $args {set result [concat $result $values]}
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::list_intersection {left right} {
    array set included {}
    foreach item $right {set included($item) 1}
    set result {}
    foreach item $left {
        if {[info exists included($item)]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::collect_primitives {roots} {
    set result {}
    foreach root $roots {
        set result [concat $result \
            [hap_v5_floorplan::primitive_descendants $root]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::collect_primitives_except_ref {roots ref_name} {
    set result {}
    foreach root $roots {
        set result [concat $result \
            [hap_v5_floorplan::primitive_descendants_except_ref \
                $root $ref_name]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::collect_ref_primitives {roots ref_name} {
    set result {}
    foreach root $roots {
        set result [concat $result \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $root $ref_name]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_floorplan::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_v5_floorplan::audit_weight_capture_class {root_name label stem \
        expected_nets expected_loads} {
    set nets [lsort -dictionary [get_nets -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/${stem}*"]]
    hap_v5_floorplan::require_count ${label}_capture_nets \
        $nets $expected_nets
    set min_load 1000000000
    set max_load 0
    foreach net $nets {
        set driver_pins [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        hap_v5_floorplan::require_count ${label}_capture_driver_pin \
            $driver_pins 1
        set driver [get_cells -quiet -of_objects $driver_pins]
        hap_v5_floorplan::require_count ${label}_capture_driver $driver 1
        if {[get_property REF_NAME $driver] ne "LUT2"} {
            error "$label capture driver is not a LUT2: $driver"
        }
        set loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN}]
        hap_v5_floorplan::require_count ${label}_capture_loads \
            $loads $expected_loads
        set ce_loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN && REF_PIN_NAME == CE}]
        hap_v5_floorplan::require_count ${label}_capture_ce_loads \
            $ce_loads $expected_loads
        set load_count [llength $loads]
        if {$load_count < $min_load} {set min_load $load_count}
        if {$load_count > $max_load} {set max_load $load_count}
    }
    return [dict create nets [llength $nets] min_load $min_load \
        max_load $max_load]
}

proc hap_v5_floorplan::audit_projection_weight_capture {} {
    set roots [hap_v5_floorplan::module_cells \
        hap_projection_core16x16_w8_reuse]
    hap_v5_floorplan::require_count projection_weight_capture_roots $roots 1
    set root_name [get_property NAME [lindex $roots 0]]
    set raw_weight_push [get_nets -quiet -hierarchical -filter \
        "NAME == ${root_name}/weight_push"]
    hap_v5_floorplan::require_count raw_weight_push_net $raw_weight_push 1
    set raw_loads [get_pins -quiet -leaf -of_objects $raw_weight_push \
        -filter {DIRECTION == IN}]
    hap_v5_floorplan::require_count raw_weight_push_loads $raw_loads 37
    set data [hap_v5_floorplan::audit_weight_capture_class $root_name \
        weight_data weight_data_capture_enable 32 256]
    set meta [hap_v5_floorplan::audit_weight_capture_class $root_name \
        weight_meta weight_meta_capture_enable 2 256]
    set group [hap_v5_floorplan::audit_weight_capture_class $root_name \
        weight_group weight_group_capture_enable 2 7]
    return [dict create audited 1 ok 1 root $root_name \
        raw_loads [llength $raw_loads] \
        data_nets [dict get $data nets] \
        data_min [dict get $data min_load] \
        data_max [dict get $data max_load] \
        meta_nets [dict get $meta nets] \
        meta_min [dict get $meta min_load] \
        meta_max [dict get $meta max_load] \
        group_nets [dict get $group nets] \
        group_min [dict get $group min_load] \
        group_max [dict get $group max_load]]
}

proc hap_v5_floorplan::require_variant {variant} {
    if {$variant ne "P2_COHORT16_COL2_12_2" &&
        $variant ne "P1_ATTN_COL2_12_2" &&
        $variant ne "P0_11" && $variant ne "legacy10"} {
        error "Illegal V5 floorplan contract variant: $variant"
    }
    return $variant
}

proc hap_v5_floorplan::rtl_resource_variant {} {
    set variants {}
    foreach name {HAP_PREPLACE_RTL_VARIANT HAP_PLACE_RTL_VARIANT
            HAP_ROUTE_RTL_VARIANT HAP_BOARD_RTL_VARIANT} {
        if {[info exists ::env($name)] && $::env($name) ne ""} {
            lappend variants $::env($name)
        }
    }
    set variants [lsort -unique $variants]
    if {[llength $variants] > 1} {
        error "Conflicting V5 RTL resource variants: $variants"
    }
    if {[llength $variants] == 0} {return P14_LEGACY}
    set variant [lindex $variants 0]
    if {$variant ni {P14_LEGACY P16_NOCLIP}} {
        error "Unsupported V5 RTL resource variant: $variant"
    }
    return $variant
}

proc hap_v5_floorplan::choose_lane_split {total_dsp fixed0_dsp \
        fixed2_dsp lane_dsp lane_count} {
    variable slr_dsp_limit
    variable slr_dsp_target

    set center_before_lanes [expr {$total_dsp - $fixed0_dsp - \
        $fixed2_dsp}]
    # Plan one 16-DSP guard band below the hard 1900 ceiling.  The granularity
    # is one complete 17-DSP Attention projection lane, so a 1884 target
    # guarantees that a legal plan never relies on a one-DSP margin.
    set center_excess [expr {$center_before_lanes > $slr_dsp_target ? \
        $center_before_lanes - $slr_dsp_target : 0}]
    set move_count [expr {($center_excess + $lane_dsp - 1) / $lane_dsp}]
    set capacity0 [expr {($slr_dsp_limit - $fixed0_dsp) / $lane_dsp}]
    set capacity2 [expr {($slr_dsp_limit - $fixed2_dsp) / $lane_dsp}]
    if {$capacity0 < 0 || $capacity2 < 0 ||
        $move_count > $capacity0 + $capacity2 ||
        $move_count >= $lane_count / 2} {
        error "No legal V5 whole-lane DSP split: total=$total_dsp move=$move_count capacity=$capacity0/$capacity2 lanes=$lane_count"
    }

    set best0 -1
    set best2 -1
    set best_max 2147483647
    set best_delta 2147483647
    for {set n0 0} {$n0 <= $move_count} {incr n0} {
        set n2 [expr {$move_count - $n0}]
        if {$n0 > $capacity0 || $n2 > $capacity2} {continue}
        set dsp0 [expr {$fixed0_dsp + $n0 * $lane_dsp}]
        set dsp2 [expr {$fixed2_dsp + $n2 * $lane_dsp}]
        set peak [expr {$dsp0 > $dsp2 ? $dsp0 : $dsp2}]
        set delta [expr {abs($dsp0 - $dsp2)}]
        if {$peak < $best_max || ($peak == $best_max && \
            $delta < $best_delta)} {
            set best0 $n0
            set best2 $n2
            set best_max $peak
            set best_delta $delta
        }
    }
    if {$best0 < 0} {error "V5 lane split search returned no candidate"}

    set planned0 [expr {$fixed0_dsp + $best0 * $lane_dsp}]
    set planned2 [expr {$fixed2_dsp + $best2 * $lane_dsp}]
    set planned1 [expr {$total_dsp - $planned0 - $planned2}]
    if {$planned0 > $slr_dsp_limit || $planned1 > $slr_dsp_limit ||
        $planned2 > $slr_dsp_limit} {
        error "V5 planned SLR DSP exceeds limit: $planned0/$planned1/$planned2"
    }
    return [dict create move0 $best0 move2 $best2 \
        planned0 $planned0 planned1 $planned1 planned2 $planned2]
}

proc hap_v5_floorplan::discover {variant} {
    variable expected_part
    variable expected_top
    variable slr_dsp_limit
    variable slr_dsp_target

    hap_v5_floorplan::require_variant $variant
    set fresh_contract [expr {$variant ne "legacy10"}]
    set p1_contract [expr {$variant eq "P1_ATTN_COL2_12_2"}]
    set p2_contract [expr {$variant eq "P2_COHORT16_COL2_12_2"}]
    set col3_contract [expr {$p1_contract || $p2_contract}]
    set rtl_resource_variant [hap_v5_floorplan::rtl_resource_variant]
    set p16_noclip [expr {$rtl_resource_variant eq "P16_NOCLIP"}]
    if {$p16_noclip && !$p2_contract} {
        error "P16 no-clip resources require the P2 cohort16 contract"
    }

    set actual_part [get_property PART [current_design]]
    set actual_top [get_property TOP [current_design]]
    if {$actual_part ne $expected_part || $actual_top ne $expected_top} {
        error "Unexpected V5 design identity: part=$actual_part top=$actual_top"
    }

    set v5_serial [hap_v5_floorplan::module_cells \
        hap_mlp_serial_ddr_command16_v5_s46]
    set old_serial [hap_v5_floorplan::module_cells \
        hap_mlp_serial_ddr_command16_s45]
    set shared [hap_v5_floorplan::module_cells \
        hap_mlp_shared_dual_slice16x12_s44_s46]
    set branches [hap_v5_floorplan::module_cells \
        hap_mlp_shared_local_slice8x12_s44_s46]
    set kernels [hap_v5_floorplan::module_cells \
        hap_a8w4_slice8x12_group_s37]
    set old_kernels [hap_v5_floorplan::module_cells \
        hap_a8w4_slice8x16_group_s36]
    set history2 [hap_v5_floorplan::module_cells \
        hap_mlp_projection_repack12_to16_s24_history2]
    set generic_repack [hap_v5_floorplan::module_cells \
        hap_mlp_projection_repack12_to16_s24]
    set metadata_leaves [hap_v5_floorplan::module_cells \
        hap_mlp_weight_meta_uram_leaf]
    set swiglu_frontends [hap_v5_floorplan::module_cells \
        hap_mlp_swiglu_product_frontend16_q4]
    set row_leaves [hap_v5_floorplan::module_cells \
        hap_mlp_swiglu_row_stream8_q4]
    set central_hadamards [hap_v5_floorplan::module_cells \
        hap_mlp_hadamard32_s32_norm_stream]
    set fold2_hadamards [hap_v5_floorplan::module_cells \
        hap_mlp_hadamard32_s32_norm_fold2]
    set central_quantizers [hap_v5_floorplan::module_cells \
        hap_mlp_robust_a8_quantizer_s35]
    set silu_units [hap_v5_floorplan::module_cells hap_mlp_silu_mul]
    set attention_legacy_roots [hap_v5_floorplan::module_cells \
        hap_attention_board_core]
    set attention_cohort16_roots [hap_v5_floorplan::module_cells \
        hap_attention_board_cohort16_core]
    set attention_roots [hap_v5_floorplan::list_union \
        $attention_legacy_roots $attention_cohort16_roots]
    set attention_meta_roots [hap_v5_floorplan::module_cells \
        hap_weight_meta_resident]
    set projection_arrays_p0 [hap_v5_floorplan::module_cells \
        hap_a8w8_array_16x16_s42]
    set projection_arrays_p1 [hap_v5_floorplan::module_cells \
        hap_a8w8_array_16x16_s42_col3]
    set projection_left_shards [hap_v5_floorplan::module_cells \
        hap_a8w8_col_shard_left2_s42]
    set projection_center_shards [hap_v5_floorplan::module_cells \
        hap_a8w8_col_shard_center12_s42]
    set projection_right_shards [hap_v5_floorplan::module_cells \
        hap_a8w8_col_shard_right2_s42]
    set projection_generic_shards [hap_v5_floorplan::module_cells \
        hap_a8w8_col_shard_s42]
    set projection_lanes_all [hap_v5_floorplan::module_cells \
        hap_a8w8_group32_lane_s42]
    set attention_rows [hap_v5_floorplan::module_cells \
        hap_attention_row_head128]
    set kv_caches [hap_v5_floorplan::module_cells hap_kv12_cache]
    set kv_quantizers4 [hap_v5_floorplan::module_cells hap_kv12_quantizer4]

    hap_v5_floorplan::require_count v5_serial $v5_serial 1
    hap_v5_floorplan::require_count old_serial $old_serial 0
    hap_v5_floorplan::require_count v5_shared $shared 1
    hap_v5_floorplan::require_count v5_branches $branches 2
    hap_v5_floorplan::require_count v5_kernels $kernels 2
    hap_v5_floorplan::require_count old_kernels $old_kernels 0
    hap_v5_floorplan::require_count history2_repack $history2 2
    hap_v5_floorplan::require_count generic_repack $generic_repack 0
    hap_v5_floorplan::require_count metadata_leaves $metadata_leaves 4
    if {$fresh_contract} {
        hap_v5_floorplan::require_count swiglu_frontends \
            $swiglu_frontends 1
        hap_v5_floorplan::require_count swiglu_row_leaves $row_leaves 2
        hap_v5_floorplan::require_count swiglu_unique_hadamard \
            $central_hadamards 1
        hap_v5_floorplan::require_count swiglu_fold2_hadamard \
            $fold2_hadamards 0
        hap_v5_floorplan::require_count swiglu_quantizers \
            $central_quantizers 4
        hap_v5_floorplan::require_count swiglu_silu_units $silu_units 2
    }
    hap_v5_floorplan::require_count attention_roots $attention_roots 1
    if {[llength $attention_legacy_roots] == 1} {
        set attention_board_variant legacy8
    } elseif {[llength $attention_cohort16_roots] == 1} {
        set attention_board_variant cohort16
    } else {
        error "Unable to identify the unique Attention board variant"
    }
    hap_v5_floorplan::require_count attention_metadata_roots \
        $attention_meta_roots 1
    if {$col3_contract} {
        hap_v5_floorplan::require_count col3_projection_arrays \
            $projection_arrays_p1 1
        hap_v5_floorplan::require_count p0_projection_arrays \
            $projection_arrays_p0 0
        hap_v5_floorplan::require_count projection_left_shards \
            $projection_left_shards 1
        hap_v5_floorplan::require_count projection_center_shards \
            $projection_center_shards 1
        hap_v5_floorplan::require_count projection_right_shards \
            $projection_right_shards 1
        hap_v5_floorplan::require_count projection_generic_shards \
            $projection_generic_shards 6
        set projection_arrays $projection_arrays_p1
    } else {
        hap_v5_floorplan::require_count p0_projection_arrays \
            $projection_arrays_p0 1
        hap_v5_floorplan::require_count col3_projection_arrays \
            $projection_arrays_p1 0
        set projection_arrays $projection_arrays_p0
    }
    hap_v5_floorplan::require_count attention_rows $attention_rows 1
    hap_v5_floorplan::require_count kv_caches $kv_caches 1
    hap_v5_floorplan::require_count kv_quantizers4 $kv_quantizers4 1
    if {$p2_contract && $attention_board_variant ne "cohort16"} {
        error "P2 requires the cohort16 Attention board hierarchy"
    }
    set projection_weight_capture [dict create audited 0 ok 0 root NONE \
        raw_loads 0 data_nets 0 data_min 0 data_max 0 \
        meta_nets 0 meta_min 0 meta_max 0 \
        group_nets 0 group_min 0 group_max 0]
    if {$p2_contract} {
        set projection_weight_capture \
            [hap_v5_floorplan::audit_projection_weight_capture]
    }

    set attention_root [lindex $attention_roots 0]
    set attention_meta [lindex $attention_meta_roots 0]
    set projection_array [lindex $projection_arrays 0]
    set attention_row [lindex $attention_rows 0]
    set kv_cache [lindex $kv_caches 0]
    set kv_quantizer4 [lindex $kv_quantizers4 0]
    set swiglu_frontend [lindex $swiglu_frontends 0]
    set row_leaf0 {}
    set row_leaf1 {}
    if {$fresh_contract} {
        set swiglu_frontend_name [get_property NAME $swiglu_frontend]
        set row_leaf0_name [format {%s/g_row_branch[0].u_branch_leaf} \
            $swiglu_frontend_name]
        set row_leaf1_name [format {%s/g_row_branch[1].u_branch_leaf} \
            $swiglu_frontend_name]
        set row_leaf_by_name [dict create]
        foreach leaf $row_leaves {
            dict set row_leaf_by_name [get_property NAME $leaf] $leaf
        }
        foreach required_name [list $row_leaf0_name $row_leaf1_name] {
            if {![dict exists $row_leaf_by_name $required_name]} {
                error "Missing exact SwiGLU row-leaf hierarchy: $required_name"
            }
        }
        set row_leaf0 [dict get $row_leaf_by_name $row_leaf0_name]
        set row_leaf1 [dict get $row_leaf_by_name $row_leaf1_name]
    }
    if {![hap_v5_floorplan::cell_is_below $projection_array \
        $attention_root]} {
        error "Projection array is not below the unique Attention root"
    }
    if {![hap_v5_floorplan::cell_is_below $attention_meta \
        $attention_root]} {
        error "Attention metadata is not below the unique Attention root"
    }
    foreach {label root} [list attention_row $attention_row \
            kv_cache $kv_cache kv_quantizer4 $kv_quantizer4] {
        if {![hap_v5_floorplan::cell_is_below $root $attention_root]} {
            error "P0 $label is not below the unique Attention root: $root"
        }
    }

    # P0 is a complete Attention-row/KV-cache locality island.  The adjacent
    # quantizer remains deliberately unconstrained: pulling its large LUT/FF
    # fanout cone into the island would defeat the SLR1 congestion relief.
    set attention_row_primitives \
        [hap_v5_floorplan::primitive_descendants $attention_row]
    set kv_cache_primitives \
        [hap_v5_floorplan::primitive_descendants $kv_cache]
    set kv_quantizer4_primitives \
        [hap_v5_floorplan::primitive_descendants $kv_quantizer4]
    set attention_row_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
        $attention_row DSP48E2]
    set attention_row_ramb36 \
        [hap_v5_floorplan::primitive_descendants_of_ref \
            $attention_row RAMB36E2]
    set attention_row_ramb18 \
        [hap_v5_floorplan::primitive_descendants_of_ref \
            $attention_row RAMB18E2]
    set attention_row_uram [hap_v5_floorplan::primitive_descendants_of_ref \
        $attention_row URAM288]
    set kv_cache_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
        $kv_cache DSP48E2]
    set kv_cache_ramb36 [hap_v5_floorplan::primitive_descendants_of_ref \
        $kv_cache RAMB36E2]
    set kv_cache_ramb18 [hap_v5_floorplan::primitive_descendants_of_ref \
        $kv_cache RAMB18E2]
    set kv_cache_uram [hap_v5_floorplan::primitive_descendants_of_ref \
        $kv_cache URAM288]
    if {[llength $attention_row_primitives] == 0 ||
        [llength $kv_cache_primitives] == 0 ||
        [llength $kv_quantizer4_primitives] == 0} {
        error "P0 root primitive collection is empty"
    }
    if {[llength $attention_row_dsp] != 52 ||
        [llength $attention_row_ramb36] != 0 ||
        [llength $attention_row_ramb18] != 0 ||
        [llength $attention_row_uram] != 0} {
        error "P0 Attention-row signature mismatch: DSP=[llength $attention_row_dsp] RAMB36=[llength $attention_row_ramb36] RAMB18=[llength $attention_row_ramb18] URAM=[llength $attention_row_uram]"
    }
    if {[llength $kv_cache_dsp] != 0 ||
        [llength $kv_cache_ramb36] != 88 ||
        [llength $kv_cache_ramb18] != 2 ||
        [llength $kv_cache_uram] != 0} {
        error "P0 KV-cache signature mismatch: DSP=[llength $kv_cache_dsp] RAMB36=[llength $kv_cache_ramb36] RAMB18=[llength $kv_cache_ramb18] URAM=[llength $kv_cache_uram]"
    }
    set attention_island_primitives [hap_v5_floorplan::list_union \
        $attention_row_primitives $kv_cache_primitives]
    set row_cache_overlap [hap_v5_floorplan::list_intersection \
        $attention_row_primitives $kv_cache_primitives]
    set island_quantizer_overlap [hap_v5_floorplan::list_intersection \
        $attention_island_primitives $kv_quantizer4_primitives]
    if {[llength $row_cache_overlap] != 0 ||
        [llength $attention_island_primitives] !=
            [llength $attention_row_primitives] +
            [llength $kv_cache_primitives]} {
        error "P0 Attention-row and KV-cache primitive sets overlap: [llength $row_cache_overlap]"
    }
    if {[llength $island_quantizer_overlap] != 0} {
        error "P0 Attention-row/KV-cache island includes u_kv_quantizer4 primitives: [llength $island_quantizer_overlap]"
    }

    # Restrict lane candidates to descendants of the discovered projection
    # array. P1/P2 own three complete column shards; P0/legacy keep
    # the earlier arbitrary whole-lane split for immutable-artifact audits.
    set projection_lanes {}
    foreach lane $projection_lanes_all {
        if {[hap_v5_floorplan::cell_is_below $lane $projection_array]} {
            lappend projection_lanes $lane
        }
    }
    set projection_lanes [lsort -dictionary $projection_lanes]
    hap_v5_floorplan::require_count attention_projection_lanes \
        $projection_lanes 128

    set projection_left_shard {}
    set projection_center_shard {}
    set projection_right_shard {}
    set left_shard_primitives {}
    set center_shard_primitives {}
    set right_shard_primitives {}
    set left_shard_lanes {}
    set center_shard_lanes {}
    set right_shard_lanes {}
    if {$col3_contract} {
        set projection_left_shard [lindex $projection_left_shards 0]
        set projection_center_shard [lindex $projection_center_shards 0]
        set projection_right_shard [lindex $projection_right_shards 0]
        foreach {label shard} [list left $projection_left_shard \
                center $projection_center_shard right $projection_right_shard] {
            if {![hap_v5_floorplan::cell_is_below $shard $projection_array]} {
                error "$variant projection $label shard is outside the unique col3 array"
            }
        }
        foreach lane $projection_lanes {
            if {[hap_v5_floorplan::cell_is_below $lane \
                    $projection_left_shard]} {
                lappend left_shard_lanes $lane
            } elseif {[hap_v5_floorplan::cell_is_below $lane \
                    $projection_center_shard]} {
                lappend center_shard_lanes $lane
            } elseif {[hap_v5_floorplan::cell_is_below $lane \
                    $projection_right_shard]} {
                lappend right_shard_lanes $lane
            } else {
                error "$variant projection lane is outside all three shards: $lane"
            }
        }
        foreach {label lanes expected} [list left $left_shard_lanes 16 \
                center $center_shard_lanes 96 right $right_shard_lanes 16] {
            hap_v5_floorplan::require_count col3_${label}_projection_lanes \
                $lanes $expected
        }
        set left_shard_primitives \
            [hap_v5_floorplan::primitive_descendants $projection_left_shard]
        set center_shard_primitives \
            [hap_v5_floorplan::primitive_descendants $projection_center_shard]
        set right_shard_primitives \
            [hap_v5_floorplan::primitive_descendants $projection_right_shard]
        foreach {label primitives} [list left $left_shard_primitives \
                center $center_shard_primitives right $right_shard_primitives] {
            if {[llength $primitives] == 0} {
                error "$variant projection $label shard primitive selector is empty"
            }
        }
        foreach {label a b} [list left_center $left_shard_primitives \
                $center_shard_primitives left_right $left_shard_primitives \
                $right_shard_primitives center_right $center_shard_primitives \
                $right_shard_primitives] {
            if {[llength [hap_v5_floorplan::list_intersection $a $b]] != 0} {
                error "$variant projection shard primitive overlap: $label"
            }
        }
    }

    set branch_dsp_counts {}
    set branch_kernel_counts {}
    foreach branch $branches {
        set branch_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
            $branch DSP48E2]
        lappend branch_dsp_counts [llength $branch_dsp]
        set local_kernel_count 0
        foreach kernel $kernels {
            if {[hap_v5_floorplan::cell_is_below $kernel $branch]} {
                incr local_kernel_count
            }
        }
        lappend branch_kernel_counts $local_kernel_count
    }
    if {$branch_dsp_counts ne {1536 1536} ||
        $branch_kernel_counts ne {1 1}} {
        error "V5 branch signature mismatch: DSP=$branch_dsp_counts kernels=$branch_kernel_counts"
    }

    set kernel_dsp [hap_v5_floorplan::collect_ref_primitives \
        $kernels DSP48E2]
    if {[llength $kernel_dsp] != 3072} {
        error "V5 kernel DSP signature mismatch: [llength $kernel_dsp]"
    }

    set lane_dsp_count -1
    set projection_lane_dsp {}
    foreach lane $projection_lanes {
        set lane_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
            $lane DSP48E2]
        if {$lane_dsp_count < 0} {set lane_dsp_count [llength $lane_dsp]}
        if {[llength $lane_dsp] != $lane_dsp_count} {
            error "Non-uniform Attention projection lane DSP signature"
        }
        set projection_lane_dsp [concat $projection_lane_dsp $lane_dsp]
    }
    set projection_lane_dsp [lsort -dictionary -unique $projection_lane_dsp]
    if {$lane_dsp_count != 17 || [llength $projection_lane_dsp] != 2176} {
        error "Attention projection signature mismatch: lane_DSP=$lane_dsp_count total=[llength $projection_lane_dsp]"
    }

    set attention_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
        $attention_root DSP48E2]
    set attention_uram [hap_v5_floorplan::primitive_descendants_of_ref \
        $attention_root URAM288]
    set expected_attention_dsp [expr {$p2_contract ? 2296 : 2304}]
    if {[llength $attention_dsp] != $expected_attention_dsp ||
        [llength $attention_uram] != 80} {
        error "Attention resource signature mismatch: DSP=[llength $attention_dsp] URAM=[llength $attention_uram]"
    }
    set attention_meta_uram \
        [hap_v5_floorplan::primitive_descendants_of_ref \
            $attention_meta URAM288]
    set attention_meta_primitives \
        [hap_v5_floorplan::primitive_descendants $attention_meta]
    if {[llength $attention_meta_uram] != 80} {
        error "Attention metadata URAM signature mismatch: [llength $attention_meta_uram]"
    }

    # Identify metadata leaves by physical URAM capacity, not by an absolute
    # u_meta_bank/u_* path.  Dictionary order only assigns the two equivalent
    # A/B images to opposite SLRs; it does not determine correctness.
    set gate_leaves {}
    set down_leaves {}
    foreach leaf $metadata_leaves {
        set leaf_uram [hap_v5_floorplan::primitive_descendants_of_ref \
            $leaf URAM288]
        set leaf_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
            $leaf DSP48E2]
        if {[llength $leaf_dsp] != 0} {
            error "Metadata leaf unexpectedly contains DSP: $leaf"
        }
        switch -- [llength $leaf_uram] {
            224 {lappend gate_leaves $leaf}
            112 {lappend down_leaves $leaf}
            default {
                error "Metadata leaf has illegal URAM signature: leaf=$leaf URAM=[llength $leaf_uram]"
            }
        }
    }
    set gate_leaves [lsort -dictionary $gate_leaves]
    set down_leaves [lsort -dictionary $down_leaves]
    hap_v5_floorplan::require_count metadata_gate_leaves $gate_leaves 2
    hap_v5_floorplan::require_count metadata_down_leaves $down_leaves 2

    set all_dsp [lsort -dictionary \
        [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
    set all_uram [lsort -dictionary \
        [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
    set total_dsp [llength $all_dsp]
    set total_uram [llength $all_uram]
    set expected_total_dsp [expr {$p16_noclip ? 5449 : 5453}]
    if {$total_dsp != $expected_total_dsp || $total_uram != 752} {
        error "V5 hard-resource contract failed: DSP=$total_dsp URAM=$total_uram"
    }

    set branch0 [lindex $branches 0]
    set branch2 [lindex $branches 1]
    set compute_branch0_primitives \
        [hap_v5_floorplan::primitive_descendants $branch0]
    set compute_branch2_primitives \
        [hap_v5_floorplan::primitive_descendants $branch2]
    set row_leaf0_primitives {}
    set row_leaf1_primitives {}
    set row_leaf0_dsp {}
    set row_leaf1_dsp {}
    set row_leaf0_ramb36 {}
    set row_leaf1_ramb36 {}
    set row_leaf0_ramb18 {}
    set row_leaf1_ramb18 {}
    set row_leaf0_uram {}
    set row_leaf1_uram {}
    set swiglu_frontend_ramb36 {}
    set swiglu_leaf_ramb36 {}
    set swiglu_central_ramb36 {}
    set outer0_primitives $compute_branch0_primitives
    set outer2_primitives $compute_branch2_primitives
    if {$fresh_contract} {
        set row_leaf0_primitives \
            [hap_v5_floorplan::primitive_descendants $row_leaf0]
        set row_leaf1_primitives \
            [hap_v5_floorplan::primitive_descendants $row_leaf1]
        set row_leaf0_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
            $row_leaf0 DSP48E2]
        set row_leaf1_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
            $row_leaf1 DSP48E2]
        set row_leaf0_ramb36 \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $row_leaf0 RAMB36E2]
        set row_leaf1_ramb36 \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $row_leaf1 RAMB36E2]
        set row_leaf0_ramb18 \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $row_leaf0 RAMB18E2]
        set row_leaf1_ramb18 \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $row_leaf1 RAMB18E2]
        set row_leaf0_uram [hap_v5_floorplan::primitive_descendants_of_ref \
            $row_leaf0 URAM288]
        set row_leaf1_uram [hap_v5_floorplan::primitive_descendants_of_ref \
            $row_leaf1 URAM288]
        if {[llength $row_leaf0_primitives] == 0 ||
            [llength $row_leaf1_primitives] == 0 ||
            [llength $row_leaf0_dsp] != 2 ||
            [llength $row_leaf1_dsp] != 2 ||
            [llength $row_leaf0_ramb36] != 6 ||
            [llength $row_leaf1_ramb36] != 6 ||
            [llength $row_leaf0_ramb18] != 0 ||
            [llength $row_leaf1_ramb18] != 0 ||
            [llength $row_leaf0_uram] != 0 ||
            [llength $row_leaf1_uram] != 0} {
            error "V5 row-leaf hard-resource signature mismatch: DSP=[llength $row_leaf0_dsp]/[llength $row_leaf1_dsp] RAMB36=[llength $row_leaf0_ramb36]/[llength $row_leaf1_ramb36] RAMB18=[llength $row_leaf0_ramb18]/[llength $row_leaf1_ramb18] URAM=[llength $row_leaf0_uram]/[llength $row_leaf1_uram]"
        }
        set swiglu_frontend_ramb36 \
            [hap_v5_floorplan::primitive_descendants_of_ref \
                $swiglu_frontend RAMB36E2]
        set swiglu_leaf_ramb36 [hap_v5_floorplan::list_union \
            $row_leaf0_ramb36 $row_leaf1_ramb36]
        set swiglu_central_ramb36 [hap_v5_floorplan::list_subtract \
            $swiglu_frontend_ramb36 $swiglu_leaf_ramb36]
        set expected_swiglu_central_ramb36 [expr {$p16_noclip ? 28 : 0}]
        if {[llength $swiglu_leaf_ramb36] != 12 ||
            [llength $swiglu_central_ramb36] !=
                $expected_swiglu_central_ramb36 ||
            [llength $swiglu_frontend_ramb36] !=
                12 + $expected_swiglu_central_ramb36} {
            error "V5 SwiGLU BRAM ownership mismatch: frontend=[llength $swiglu_frontend_ramb36] leaf=[llength $swiglu_leaf_ramb36] central=[llength $swiglu_central_ramb36]"
        }
        set central_hadamard_primitives \
            [hap_v5_floorplan::collect_primitives $central_hadamards]
        set central_quantizer_primitives \
            [hap_v5_floorplan::collect_primitives $central_quantizers]
        foreach {label left right} [list \
                leaf_pair $row_leaf0_primitives $row_leaf1_primitives \
                branch0_leaf0 $compute_branch0_primitives \
                    $row_leaf0_primitives \
                branch0_leaf1 $compute_branch0_primitives \
                    $row_leaf1_primitives \
                branch2_leaf0 $compute_branch2_primitives \
                    $row_leaf0_primitives \
                branch2_leaf1 $compute_branch2_primitives \
                    $row_leaf1_primitives \
                leaf0_hadamard $row_leaf0_primitives \
                    $central_hadamard_primitives \
                leaf1_hadamard $row_leaf1_primitives \
                    $central_hadamard_primitives \
                leaf0_quantizer $row_leaf0_primitives \
                    $central_quantizer_primitives \
                leaf1_quantizer $row_leaf1_primitives \
                    $central_quantizer_primitives] {
            set overlap [hap_v5_floorplan::list_intersection $left $right]
            if {[llength $overlap] != 0} {
                error "V5 row-local selector overlap: $label=[llength $overlap]"
            }
        }
        set outer0_primitives [hap_v5_floorplan::list_union \
            $compute_branch0_primitives $row_leaf0_primitives]
        set outer2_primitives [hap_v5_floorplan::list_union \
            $compute_branch2_primitives $row_leaf1_primitives]
    }
    set outer0_dsp [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch0] DSP48E2] $row_leaf0_dsp]
    set outer2_dsp [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch2] DSP48E2] $row_leaf1_dsp]
    set outer0_ramb36 [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch0] RAMB36E2] $row_leaf0_ramb36]
    set outer2_ramb36 [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch2] RAMB36E2] $row_leaf1_ramb36]
    if {$fresh_contract &&
        ([llength $outer0_dsp] != 1538 ||
         [llength $outer2_dsp] != 1538 ||
         [llength $outer0_ramb36] != 102 ||
         [llength $outer2_ramb36] != 102)} {
        error "V5 augmented outer signature mismatch: DSP=[llength $outer0_dsp]/[llength $outer2_dsp] RAMB36=[llength $outer0_ramb36]/[llength $outer2_ramb36]"
    }

    # P1/P2 assign complete 2/12/2-column shards. P0 searches an arbitrary
    # whole-lane split, while legacy10 reproduces the frozen Run0138 equation.
    if {$col3_contract} {
        set move0 [llength $left_shard_lanes]
        set move2 [llength $right_shard_lanes]
        set lanes_slr0 $left_shard_lanes
        set lanes_slr1 $center_shard_lanes
        set lanes_slr2 $right_shard_lanes
        set planned0 [expr {[llength $outer0_dsp] +
            [llength $attention_row_dsp] +
            [llength [hap_v5_floorplan::collect_ref_primitives \
                [list $projection_left_shard] DSP48E2]]}]
        set planned2 [expr {[llength $outer2_dsp] +
            [llength [hap_v5_floorplan::collect_ref_primitives \
                [list $projection_right_shard] DSP48E2]]}]
        set planned1 [expr {$total_dsp - $planned0 - $planned2}]
        set split [dict create move0 $move0 move2 $move2 \
            planned0 $planned0 planned1 $planned1 planned2 $planned2]
    } elseif {$variant eq "P0_11"} {
        set fixed0_dsp [expr {[llength $outer0_dsp] + \
            [llength $attention_row_dsp]}]
        set fixed2_dsp [llength $outer2_dsp]
    } else {
        # The frozen Run0138 checkpoint predates row-local SwiGLU.  Populate
        # explicit zero-valued compatibility records without weakening fresh
        # P0_11 hierarchy requirements.
        set swiglu_frontends {}
        set row_leaves {}
        set central_hadamards {}
        set fold2_hadamards {}
        set central_quantizers {}
        set silu_units {}
        set fixed0_dsp [lindex $branch_dsp_counts 0]
        set fixed2_dsp [lindex $branch_dsp_counts 1]
    }
    if {!$col3_contract} {
        set split [hap_v5_floorplan::choose_lane_split $total_dsp \
            $fixed0_dsp $fixed2_dsp $lane_dsp_count \
            [llength $projection_lanes]]
        set move0 [dict get $split move0]
        set move2 [dict get $split move2]
        set last_center_index [expr {[llength $projection_lanes] - $move2 - 1}]
        set lanes_slr0 [lrange $projection_lanes 0 [expr {$move0 - 1}]]
        set lanes_slr2 [expr {$move2 == 0 ? {} : \
            [lrange $projection_lanes end-[expr {$move2 - 1}] end]}]
        set lanes_slr1 [lrange $projection_lanes $move0 $last_center_index]
    }
    if {[llength [hap_v5_floorplan::list_union \
            $lanes_slr0 $lanes_slr1 $lanes_slr2]] != 128 ||
        [llength $lanes_slr1] <= 64} {
        error "Attention lane partition is incomplete or not center-majority"
    }

    set branch0_primitives $compute_branch0_primitives
    set branch2_primitives $compute_branch2_primitives
    if {$col3_contract} {
        set lane0_primitives $left_shard_primitives
        set lane2_primitives $right_shard_primitives
    } else {
        set lane0_primitives \
            [hap_v5_floorplan::collect_primitives $lanes_slr0]
        set lane2_primitives \
            [hap_v5_floorplan::collect_primitives $lanes_slr2]
    }
    set legacy_outer_dsp [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch0] DSP48E2] \
        [hap_v5_floorplan::collect_ref_primitives \
            [list $branch2] DSP48E2] \
        [hap_v5_floorplan::collect_ref_primitives $lanes_slr0 DSP48E2] \
        [hap_v5_floorplan::collect_ref_primitives $lanes_slr2 DSP48E2]]
    set legacy_center_dsp \
        [hap_v5_floorplan::list_subtract $all_dsp $legacy_outer_dsp]
    set p0_outer_dsp [hap_v5_floorplan::list_union $outer0_dsp $outer2_dsp \
        [hap_v5_floorplan::collect_ref_primitives $lanes_slr0 DSP48E2] \
        [hap_v5_floorplan::collect_ref_primitives $lanes_slr2 DSP48E2] \
        $attention_row_dsp]
    set center_dsp [hap_v5_floorplan::list_subtract $all_dsp $p0_outer_dsp]
    set center_projection_dsp {}
    set center_nonprojection_dsp {}
    if {$col3_contract} {
        # The column-shard center pblock owns the complete projection shard plus
        # every remaining center-assigned DSP outside that shard. This keeps
        # exact full-design DSP coverage while physically localizing the
        # shard's activation stage, lane FIFOs and accumulator with its DSPs.
        set center_projection_dsp \
            [hap_v5_floorplan::collect_ref_primitives \
                [list $projection_center_shard] DSP48E2]
        set center_nonprojection_dsp \
            [hap_v5_floorplan::list_subtract $center_dsp \
                $center_projection_dsp]
        # P16 removes the four no-clip quantizer DSPs from the P2 center
        # remainder.  The legacy P2 and P1 signatures remain unchanged.
        set expected_center_nonprojection_dsp [expr {
            $p2_contract ? ($p16_noclip ? 145 : 149) : 161}]
        if {[llength $center_projection_dsp] != 1632 ||
            [llength $center_nonprojection_dsp] !=
                $expected_center_nonprojection_dsp ||
            [llength [hap_v5_floorplan::list_intersection \
                $center_projection_dsp $center_dsp]] != 1632} {
            error "$variant center projection/nonprojection DSP signature mismatch: projection=[llength $center_projection_dsp] nonprojection=[llength $center_nonprojection_dsp]"
        }
        set center_primitives [hap_v5_floorplan::list_union \
            $center_shard_primitives $center_nonprojection_dsp \
            $swiglu_central_ramb36]
    } else {
        set center_primitives [hap_v5_floorplan::list_union \
            $center_dsp $swiglu_central_ramb36]
    }

    set gate0 [lindex $gate_leaves 0]
    set gate2 [lindex $gate_leaves 1]
    set down0 [lindex $down_leaves 0]
    set down1 [lindex $down_leaves 1]
    set gate0_primitives [hap_v5_floorplan::primitive_descendants $gate0]
    set gate2_primitives [hap_v5_floorplan::primitive_descendants $gate2]
    set down0_primitives [hap_v5_floorplan::primitive_descendants $down0]
    set down1_primitives [hap_v5_floorplan::primitive_descendants $down1]

    # The five bank roots must cover every URAM in the design exactly once.
    set bank_uram [hap_v5_floorplan::list_union \
        [hap_v5_floorplan::primitive_descendants_of_ref $gate0 URAM288] \
        [hap_v5_floorplan::primitive_descendants_of_ref $gate2 URAM288] \
        [hap_v5_floorplan::primitive_descendants_of_ref $down0 URAM288] \
        [hap_v5_floorplan::primitive_descendants_of_ref $down1 URAM288] \
        $attention_meta_uram]
    if {[llength $bank_uram] != $total_uram} {
        error "Bank-local URAM coverage mismatch: banks=[llength $bank_uram] total=$total_uram"
    }

    set attention_island_dsp [llength $attention_row_dsp]
    set planned0 [dict get $split planned0]
    set planned1 [dict get $split planned1]
    set planned2 [dict get $split planned2]
    set legacy_planned0 $planned0
    set legacy_planned1 $planned1
    set legacy_planned2 $planned2
    if {$p2_contract} {
        set expected_p2_slr1 [expr {$p16_noclip ? 1777 : 1781}]
        if {$move0 != 16 || [llength $lanes_slr1] != 96 ||
            $move2 != 16 || $planned0 != 1862 ||
            $planned1 != $expected_p2_slr1 ||
            $planned2 != 1810} {
            error "P2 cohort16 column-shard split drifted: lanes=$move0/[llength $lanes_slr1]/$move2 plan=$planned0/$planned1/$planned2"
        }
    } elseif {$p1_contract} {
        if {$move0 != 16 || [llength $lanes_slr1] != 96 ||
            $move2 != 16 || $planned0 != 1862 || $planned1 != 1793 ||
            $planned2 != 1810} {
            error "P1 column-shard split drifted: lanes=$move0/[llength $lanes_slr1]/$move2 plan=$planned0/$planned1/$planned2"
        }
    } elseif {$variant eq "P0_11"} {
        if {$move0 != 12 || [llength $lanes_slr1] != 101 ||
            $move2 != 15 || $planned0 != 1794 || $planned1 != 1878 ||
            $planned2 != 1793} {
            error "Fresh P0_11 split drifted: lanes=$move0/[llength $lanes_slr1]/$move2 plan=$planned0/$planned1/$planned2"
        }
    } elseif {[llength $legacy_center_dsp] != $legacy_planned1} {
        error "Legacy center DSP selector mismatch: expected=$legacy_planned1 actual=[llength $legacy_center_dsp]"
    }
    if {$fresh_contract} {
        foreach {label left right} [list \
                outer_pair $outer0_primitives $outer2_primitives \
                outer0_lane0 $outer0_primitives $lane0_primitives \
                outer0_lane2 $outer0_primitives $lane2_primitives \
                outer2_lane0 $outer2_primitives $lane0_primitives \
                outer2_lane2 $outer2_primitives $lane2_primitives \
                outer0_island $outer0_primitives \
                    $attention_island_primitives \
                outer2_island $outer2_primitives \
                    $attention_island_primitives \
                outer0_gate0 $outer0_primitives $gate0_primitives \
                outer0_gate2 $outer0_primitives $gate2_primitives \
                outer0_down0 $outer0_primitives $down0_primitives \
                outer0_down1 $outer0_primitives $down1_primitives \
                outer0_attention_meta $outer0_primitives \
                    $attention_meta_primitives \
                outer2_gate0 $outer2_primitives $gate0_primitives \
                outer2_gate2 $outer2_primitives $gate2_primitives \
                outer2_down0 $outer2_primitives $down0_primitives \
                outer2_down1 $outer2_primitives $down1_primitives \
                outer2_attention_meta $outer2_primitives \
                    $attention_meta_primitives \
                leaf0_center $row_leaf0_primitives $center_primitives \
                leaf1_center $row_leaf1_primitives $center_primitives] {
            set overlap [hap_v5_floorplan::list_intersection $left $right]
            if {[llength $overlap] != 0} {
                error "V5 augmented outer/pblock selector overlap: $label=[llength $overlap]"
            }
        }
    }
    if {$col3_contract} {
        foreach {label left right} [list \
                lane0_lane2 $lane0_primitives $lane2_primitives \
                lane0_center $lane0_primitives $center_primitives \
                lane2_center $lane2_primitives $center_primitives \
                lane0_island $lane0_primitives $attention_island_primitives \
                lane2_island $lane2_primitives $attention_island_primitives \
                center_island $center_primitives $attention_island_primitives \
                lane0_gate0 $lane0_primitives $gate0_primitives \
                lane0_gate2 $lane0_primitives $gate2_primitives \
                lane0_down0 $lane0_primitives $down0_primitives \
                lane0_down1 $lane0_primitives $down1_primitives \
                lane0_attention_meta $lane0_primitives \
                    $attention_meta_primitives \
                lane2_gate0 $lane2_primitives $gate0_primitives \
                lane2_gate2 $lane2_primitives $gate2_primitives \
                lane2_down0 $lane2_primitives $down0_primitives \
                lane2_down1 $lane2_primitives $down1_primitives \
                lane2_attention_meta $lane2_primitives \
                    $attention_meta_primitives \
                center_gate0 $center_primitives $gate0_primitives \
                center_gate2 $center_primitives $gate2_primitives \
                center_down0 $center_primitives $down0_primitives \
                center_down1 $center_primitives $down1_primitives \
                center_attention_meta $center_primitives \
                    $attention_meta_primitives] {
            set overlap [hap_v5_floorplan::list_intersection $left $right]
            if {[llength $overlap] != 0} {
                error "$variant hard-owner selector overlap: $label=[llength $overlap]"
            }
        }
    }
    set selected_center_dsp [expr {$fresh_contract ?
        [hap_v5_floorplan::count_ref $center_primitives DSP48E2] :
        [llength $legacy_center_dsp]}]
    if {$selected_center_dsp != $planned1 ||
        $planned0 > $slr_dsp_limit || $planned1 > $slr_dsp_limit ||
        $planned2 > $slr_dsp_limit ||
        $planned0 + $planned1 + $planned2 != $total_dsp} {
        error "V5 DSP plan mismatch: variant=$variant plan=$planned0/$planned1/$planned2 center=$selected_center_dsp total=$total_dsp"
    }

    return [dict create \
        part $actual_part top $actual_top contract_variant $variant \
        rtl_resource_variant $rtl_resource_variant \
        total_dsp $total_dsp total_uram $total_uram \
        history2_count [llength $history2] generic_repack_count 0 \
        v5_serial [lindex $v5_serial 0] shared [lindex $shared 0] \
        branch0 $branch0 branch2 $branch2 \
        branch0_primitives $branch0_primitives \
        branch2_primitives $branch2_primitives \
        branch0_dsp [lindex $branch_dsp_counts 0] \
        branch2_dsp [lindex $branch_dsp_counts 1] \
        swiglu_frontend_count [llength $swiglu_frontends] \
        row_leaf_count [llength $row_leaves] \
        unique_hadamard_count [llength $central_hadamards] \
        fold2_count [llength $fold2_hadamards] \
        quantizer_count [llength $central_quantizers] \
        silu_count [llength $silu_units] \
        swiglu_frontend_ramb36 [llength $swiglu_frontend_ramb36] \
        swiglu_leaf_ramb36 [llength $swiglu_leaf_ramb36] \
        swiglu_central_ramb36 [llength $swiglu_central_ramb36] \
        swiglu_central_ramb36_primitives $swiglu_central_ramb36 \
        leaf0 $row_leaf0 leaf1 $row_leaf1 \
        leaf0_primitives $row_leaf0_primitives \
        leaf1_primitives $row_leaf1_primitives \
        leaf0_dsp [llength $row_leaf0_dsp] \
        leaf1_dsp [llength $row_leaf1_dsp] \
        leaf0_ramb36 [llength $row_leaf0_ramb36] \
        leaf1_ramb36 [llength $row_leaf1_ramb36] \
        outer0_primitives $outer0_primitives \
        outer2_primitives $outer2_primitives \
        outer0_dsp [llength $outer0_dsp] \
        outer2_dsp [llength $outer2_dsp] \
        outer0_ramb36 [llength $outer0_ramb36] \
        outer2_ramb36 [llength $outer2_ramb36] \
        kernel_count [llength $kernels] kernel_dsp [llength $kernel_dsp] \
        attention_root $attention_root \
        attention_board_variant $attention_board_variant \
        attention_dsp [llength $attention_dsp] \
        attention_meta $attention_meta \
        attention_row $attention_row kv_cache $kv_cache \
        kv_quantizer4 $kv_quantizer4 \
        attention_row_primitives $attention_row_primitives \
        kv_cache_primitives $kv_cache_primitives \
        kv_quantizer4_primitives $kv_quantizer4_primitives \
        attention_island_primitives $attention_island_primitives \
        attention_row_dsp [llength $attention_row_dsp] \
        attention_row_ramb36 [llength $attention_row_ramb36] \
        attention_row_ramb18 [llength $attention_row_ramb18] \
        kv_cache_dsp [llength $kv_cache_dsp] \
        kv_cache_ramb36 [llength $kv_cache_ramb36] \
        kv_cache_ramb18 [llength $kv_cache_ramb18] \
        attention_island_dsp $attention_island_dsp \
        attention_island_ramb36 [llength $kv_cache_ramb36] \
        attention_island_ramb18 [llength $kv_cache_ramb18] \
        attention_island_uram 0 \
        attention_island_quantizer_overlap \
            [llength $island_quantizer_overlap] \
        attention_island_row_cache_overlap [llength $row_cache_overlap] \
        attention_island_target 0 \
        attention_meta_primitives $attention_meta_primitives \
        attention_meta_uram [llength $attention_meta_uram] \
        projection_array $projection_array \
        projection_left_shard $projection_left_shard \
        projection_center_shard $projection_center_shard \
        projection_right_shard $projection_right_shard \
        projection_lane_count [llength $projection_lanes] \
        projection_lane_dsp $lane_dsp_count \
        projection_weight_capture_audited \
            [dict get $projection_weight_capture audited] \
        projection_weight_capture_ok [dict get $projection_weight_capture ok] \
        projection_weight_capture_root \
            [dict get $projection_weight_capture root] \
        raw_weight_push_loads [dict get $projection_weight_capture raw_loads] \
        weight_data_capture_nets [dict get $projection_weight_capture data_nets] \
        weight_data_capture_min [dict get $projection_weight_capture data_min] \
        weight_data_capture_max [dict get $projection_weight_capture data_max] \
        weight_meta_capture_nets [dict get $projection_weight_capture meta_nets] \
        weight_meta_capture_min [dict get $projection_weight_capture meta_min] \
        weight_meta_capture_max [dict get $projection_weight_capture meta_max] \
        weight_group_capture_nets \
            [dict get $projection_weight_capture group_nets] \
        weight_group_capture_min [dict get $projection_weight_capture group_min] \
        weight_group_capture_max [dict get $projection_weight_capture group_max] \
        lanes_slr0 $lanes_slr0 lanes_slr1 $lanes_slr1 \
        lanes_slr2 $lanes_slr2 lane0_primitives $lane0_primitives \
        lane2_primitives $lane2_primitives \
        center_primitives $center_primitives center_dsp $center_dsp \
        center_projection_dsp [llength $center_projection_dsp] \
        center_nonprojection_dsp [llength $center_nonprojection_dsp] \
        legacy_center_dsp $legacy_center_dsp \
        gate0 $gate0 gate2 $gate2 down0 $down0 down1 $down1 \
        gate0_primitives $gate0_primitives \
        gate2_primitives $gate2_primitives \
        down0_primitives $down0_primitives \
        down1_primitives $down1_primitives \
        move0 $move0 move2 $move2 center_lanes [llength $lanes_slr1] \
        planned_slr0_dsp $planned0 planned_slr1_dsp $planned1 \
        planned_slr2_dsp $planned2 slr_dsp_limit $slr_dsp_limit \
        slr_dsp_target $slr_dsp_target \
        legacy_planned_slr0_dsp $legacy_planned0 \
        legacy_planned_slr1_dsp $legacy_planned1 \
        legacy_planned_slr2_dsp $legacy_planned2]
}

proc hap_v5_floorplan::write_discovery {plan path status} {
    set fp [open $path w]
    foreach key {part top contract_variant rtl_resource_variant total_dsp
        total_uram history2_count
        generic_repack_count v5_serial shared branch0 branch2 branch0_dsp
        branch2_dsp swiglu_frontend_count row_leaf_count
        unique_hadamard_count fold2_count quantizer_count silu_count
        swiglu_frontend_ramb36 swiglu_leaf_ramb36
        swiglu_central_ramb36
        leaf0 leaf1 leaf0_dsp leaf1_dsp leaf0_ramb36 leaf1_ramb36
        outer0_dsp outer2_dsp outer0_ramb36 outer2_ramb36
        kernel_count kernel_dsp attention_root attention_board_variant
        attention_dsp
        attention_meta
        attention_row kv_cache kv_quantizer4 attention_row_dsp
        attention_row_ramb36 attention_row_ramb18 kv_cache_dsp
        kv_cache_ramb36 kv_cache_ramb18 attention_island_dsp
        attention_island_ramb36 attention_island_ramb18
        attention_island_uram attention_island_quantizer_overlap
        attention_island_row_cache_overlap
        attention_island_target
        attention_meta_uram projection_array projection_left_shard
        projection_center_shard projection_right_shard
        center_projection_dsp center_nonprojection_dsp
        projection_lane_count projection_lane_dsp
        projection_weight_capture_audited projection_weight_capture_ok
        projection_weight_capture_root raw_weight_push_loads
        weight_data_capture_nets weight_data_capture_min
        weight_data_capture_max weight_meta_capture_nets
        weight_meta_capture_min weight_meta_capture_max
        weight_group_capture_nets weight_group_capture_min
        weight_group_capture_max gate0 gate2 down0 down1
        move0 move2 center_lanes planned_slr0_dsp planned_slr1_dsp
        planned_slr2_dsp legacy_planned_slr0_dsp
        legacy_planned_slr1_dsp legacy_planned_slr2_dsp
        slr_dsp_limit slr_dsp_target} {
        puts $fp "$key=[dict get $plan $key]"
    }
    foreach {label key} {
        slr0_attention_lanes lanes_slr0
        slr1_attention_lanes lanes_slr1
        slr2_attention_lanes lanes_slr2
    } {
        puts $fp "$label=[llength [dict get $plan $key]]"
        foreach cell [dict get $plan $key] {
            puts $fp "${label}_cell=$cell"
        }
    }
    puts $fp "branch0_primitives=[llength [dict get $plan branch0_primitives]]"
    puts $fp "branch2_primitives=[llength [dict get $plan branch2_primitives]]"
    puts $fp "leaf0_primitives=[llength [dict get $plan leaf0_primitives]]"
    puts $fp "leaf1_primitives=[llength [dict get $plan leaf1_primitives]]"
    puts $fp "outer0_primitives=[llength [dict get $plan outer0_primitives]]"
    puts $fp "outer2_primitives=[llength [dict get $plan outer2_primitives]]"
    puts $fp "lane0_primitives=[llength [dict get $plan lane0_primitives]]"
    puts $fp "lane2_primitives=[llength [dict get $plan lane2_primitives]]"
    puts $fp "center_primitives=[llength [dict get $plan center_primitives]]"
    puts $fp "center_dsp_cells=[llength [dict get $plan center_dsp]]"
    puts $fp "legacy_center_dsp_cells=[llength [dict get $plan legacy_center_dsp]]"
    puts $fp "attention_row_primitives=[llength [dict get $plan attention_row_primitives]]"
    puts $fp "kv_cache_primitives=[llength [dict get $plan kv_cache_primitives]]"
    puts $fp "kv_quantizer4_primitives=[llength [dict get $plan kv_quantizer4_primitives]]"
    puts $fp "attention_island_primitives=[llength [dict get $plan attention_island_primitives]]"
    puts $fp "status=$status"
    close $fp
}

# Physical implementation commands can invalidate Tcl object handles held in
# an earlier collection.  The procedures below therefore accept only a plan
# returned by a *current* discover call.  Place/route callers must rediscover
# immediately after every netlist-changing command before using this audit.
proc hap_v5_floorplan::object_names {cells} {
    set cell_count [llength $cells]
    if {$cell_count == 0} {return {}}
    set names [get_property NAME $cells]
    if {[llength $names] != $cell_count} {
        error "V5 bulk NAME cardinality mismatch: cells=$cell_count names=[llength $names]"
    }
    foreach name $names {
        if {$name eq ""} {
            error "V5 physical audit received a stale/nameless cell handle"
        }
    }
    return [lsort -dictionary -unique $names]
}

proc hap_v5_floorplan::count_ref {cells ref_name} {
    set count 0
    set cell_count [llength $cells]
    if {$cell_count == 0} {return 0}
    set refs [get_property REF_NAME $cells]
    if {[llength $refs] != $cell_count} {
        error "V5 bulk REF_NAME cardinality mismatch: cells=$cell_count refs=[llength $refs]"
    }
    foreach ref $refs {
        if {$ref eq $ref_name} {incr count}
    }
    return $count
}

# Vivado 2025.2 site objects have no SLR_INDEX property.  Build the physical
# ownership map from the supported relationship in three bulk queries:
# get_sites -of_objects [get_slrs SLRn].  Verify the three sets are nonempty,
# pairwise disjoint, exactly cover every device site, and round-trip through
# bulk get_slrs before caching only string names.
proc hap_v5_floorplan::device_site_slr_map {} {
    variable expected_part
    variable site_slr_part
    variable site_to_slr_cache
    variable slr_site_names_cache

    set actual_part [get_property PART [current_design]]
    if {$actual_part ne $expected_part} {
        error "V5 device site/SLR map part mismatch: expected=$expected_part actual=$actual_part"
    }
    if {$site_slr_part eq $actual_part &&
        [dict size $site_to_slr_cache] != 0} {
        return [dict create site_to_slr $site_to_slr_cache \
            slr_site_names $slr_site_names_cache]
    }

    set site_to_slr [dict create]
    set slr_site_names [list {} {} {}]
    for {set index 0} {$index < 3} {incr index} {
        set slr_name SLR${index}
        set slr [get_slrs -quiet $slr_name]
        if {[llength $slr] != 1} {
            error "V5 device SLR identity is not unique: $slr_name"
        }
        set slr_sites [get_sites -quiet -of_objects $slr]
        set names [get_property NAME $slr_sites]
        set unique_names [lsort -dictionary -unique $names]
        if {[llength $slr_sites] == 0 ||
            [llength $names] != [llength $slr_sites] ||
            [llength $unique_names] != [llength $names]} {
            error "V5 device SLR/site bulk query failed: slr=$slr_name sites=[llength $slr_sites] names=[llength $names] unique=[llength $unique_names]"
        }

        set reverse_slrs [lsort -dictionary -unique [get_property NAME \
            [get_slrs -quiet -of_objects $slr_sites]]]
        if {$reverse_slrs ne [list $slr_name]} {
            error "V5 device bulk site/SLR round-trip mismatch: expected=$slr_name actual=$reverse_slrs"
        }
        foreach name $unique_names {
            if {[dict exists $site_to_slr $name]} {
                error "V5 device site belongs to multiple SLR sets: site=$name old=[dict get $site_to_slr $name] new=$index"
            }
            dict set site_to_slr $name $index
        }
        lset slr_site_names $index $unique_names
    }

    set all_site_names [lsort -dictionary -unique [get_property NAME \
        [get_sites -quiet]]]
    set mapped_site_names [lsort -dictionary [dict keys $site_to_slr]]
    if {$mapped_site_names ne $all_site_names} {
        error "V5 device SLR site sets do not exactly cover the device: mapped=[llength $mapped_site_names] all=[llength $all_site_names]"
    }
    set site_slr_part $actual_part
    set site_to_slr_cache $site_to_slr
    set slr_site_names_cache $slr_site_names
    return [dict create site_to_slr $site_to_slr \
        slr_site_names $slr_site_names]
}

proc hap_v5_floorplan::cell_physical_slr_index {cell} {
    set audit [hap_v5_floorplan::physical_slr_audit_for_cells \
        [list $cell]]
    if {[dict get $audit physical_count] != 1 ||
        [dict get $audit virtual_total] != 0} {
        error "V5 single-cell SLR query received a virtual constant: $cell"
    }
    set counts [dict get $audit slr_counts]
    for {set index 0} {$index < 3} {incr index} {
        if {[lindex $counts $index] == 1} {return $index}
    }
    error "V5 single-cell SLR query returned no physical SLR: $cell"
}

# Resolve physical SLR placement in bulk while preserving virtual constants as
# an explicit, audited class.  Vivado keeps synthesized GND/VCC source cells in
# the hierarchy after placement; they have no LOC/BEL/site and therefore no
# physical SLR.  Vivado 2025.2 does not expose a usable IS_PLACED value for
# this checkpoint class, so LOC plus the device site-to-SLR map is
# authoritative.  Only exact REF_NAME GND/VCC objects with every supported
# direct physical property and relationship empty are excluded from
# wrong/unplaced counts.  Any other unresolved object fails closed.
proc hap_v5_floorplan::physical_slr_audit_for_cells {cells} {
    set cell_count [llength $cells]
    if {$cell_count == 0} {
        return [dict create slr_counts {0 0 0} physical_count 0 \
            virtual_gnd 0 virtual_vcc 0 virtual_total 0 total 0 \
            direct_slr_empty 0 is_placed_empty 0]
    }

    set virtual_cells {}
    set physical_cells {}
    set virtual_gnd 0
    set virtual_vcc 0
    set refs [get_property REF_NAME $cells]
    if {[llength $refs] != $cell_count} {
        error "V5 bulk REF_NAME cardinality mismatch: cells=$cell_count values=[llength $refs]"
    }
    foreach cell $cells ref $refs {
        if {$ref eq "GND" || $ref eq "VCC"} {
            lappend virtual_cells $cell
            if {$ref eq "GND"} {incr virtual_gnd} else {incr virtual_vcc}
        } else {
            lappend physical_cells $cell
        }
    }

    # Virtual constants are the only objects allowed to lack supported direct
    # physical properties and site/BEL relationships.  Their cardinality is
    # tiny, so scalar property checks avoid Tcl's loss of a sole empty list
    # element.
    foreach cell $virtual_cells {
        set ref [get_property REF_NAME $cell]
        foreach property {SLR_INDEX LOC BEL} {
            set value [get_property $property $cell]
            if {$value ne ""} {
                error "V5 virtual constant has a nonempty physical property: cell=$cell ref=$ref property=$property value=$value"
            }
        }
    }
    set virtual_sites {}
    set virtual_bels {}
    if {[llength $virtual_cells] != 0} {
        set virtual_sites [get_sites -quiet -of_objects $virtual_cells]
        set virtual_bels [get_bels -quiet -of_objects $virtual_cells]
    }
    if {[llength $virtual_sites] != 0 || [llength $virtual_bels] != 0} {
        error "V5 virtual constants unexpectedly resolve physically: sites=[llength $virtual_sites] bels=[llength $virtual_bels]"
    }

    set physical_count [llength $physical_cells]
    set counts {0 0 0}
    if {$physical_count == 0} {
        return [dict create slr_counts $counts physical_count 0 \
            virtual_gnd $virtual_gnd virtual_vcc $virtual_vcc \
            virtual_total [llength $virtual_cells] total $cell_count \
            direct_slr_empty 0 is_placed_empty 0]
    }

    set physical_direct [get_property SLR_INDEX $physical_cells]
    set physical_locs [get_property LOC $physical_cells]
    set physical_bels [get_property BEL $physical_cells]
    foreach {label values} [list SLR_INDEX $physical_direct \
            LOC $physical_locs BEL $physical_bels] {
        if {[llength $values] != $physical_count} {
            error "V5 bulk physical-property cardinality mismatch: cells=$physical_count property=$label values=[llength $values]"
        }
    }

    set direct_slr_empty 0
    foreach cell $physical_cells direct $physical_direct loc $physical_locs {
        if {$direct eq ""} {
            incr direct_slr_empty
        } elseif {![string is integer -strict $direct] ||
                $direct < 0 || $direct > 2} {
            error "V5 nonconstant primitive has an illegal direct SLR_INDEX: cell=$cell value=$direct"
        }
        if {$loc eq ""} {
            error "V5 nonconstant primitive has no physical LOC: cell=$cell"
        }
    }
    # Retain the historical report field while making its non-authoritative
    # status explicit: every physical primitive is counted as lacking a usable
    # IS_PLACED observation in this checkpoint class.
    set is_placed_empty $physical_count

    # LOC is the authoritative physical mapping.  Query all unique LOCs at
    # once and require a one-to-one LOC/site-name set before assigning SLRs.
    set unique_locs [lsort -dictionary -unique $physical_locs]
    set sites [get_sites -quiet $unique_locs]
    set site_names [get_property NAME $sites]
    if {[llength $site_names] != [llength $sites]} {
        error "V5 physical site NAME cardinality mismatch"
    }
    set unique_site_names [lsort -dictionary -unique $site_names]
    if {$unique_site_names ne $unique_locs} {
        error "V5 physical LOC/site coverage mismatch: LOCs=[llength $unique_locs] sites=[llength $unique_site_names]"
    }

    set device_map [hap_v5_floorplan::device_site_slr_map]
    set site_to_index [dict get $device_map site_to_slr]

    foreach cell $physical_cells direct $physical_direct loc $physical_locs {
        if {![dict exists $site_to_index $loc]} {
            error "V5 placed LOC is absent from the exact device SLR site map: $loc"
        }
        set index [dict get $site_to_index $loc]
        if {$direct ne "" && $direct != $index} {
            error "V5 direct/site SLR mismatch: cell=$cell direct=$direct LOC=$loc site_index=$index"
        }
        lset counts $index [expr {[lindex $counts $index] + 1}]
    }
    if {[tcl::mathop::+ {*}$counts] != $physical_count ||
        $physical_count + [llength $virtual_cells] != $cell_count} {
        error "V5 physical/virtual classes do not cover every cell"
    }
    return [dict create slr_counts $counts physical_count $physical_count \
        virtual_gnd $virtual_gnd virtual_vcc $virtual_vcc \
        virtual_total [llength $virtual_cells] total $cell_count \
        direct_slr_empty $direct_slr_empty \
        is_placed_empty $is_placed_empty]
}

proc hap_v5_floorplan::physical_slr_counts_for_cells {cells} {
    return [dict get \
        [hap_v5_floorplan::physical_slr_audit_for_cells $cells] \
        slr_counts]
}

proc hap_v5_floorplan::wrong_slr_audit {cells target} {
    if {$target < 0 || $target > 2} {
        error "Illegal V5 target SLR index: $target"
    }
    set audit [hap_v5_floorplan::physical_slr_audit_for_cells $cells]
    set counts [dict get $audit slr_counts]
    dict set audit wrong [expr {
        [dict get $audit physical_count] - [lindex $counts $target]}]
    dict set audit target $target
    return $audit
}

proc hap_v5_floorplan::count_wrong_slr {cells target} {
    return [dict get \
        [hap_v5_floorplan::wrong_slr_audit $cells $target] wrong]
}

proc hap_v5_floorplan::placed_slr_counts {ref_name} {
    set counts {0 0 0}
    set cells [get_cells -quiet -hierarchical -filter \
        "REF_NAME == $ref_name"]
    if {[llength $cells] == 0} {
        error "V5 physical audit found no $ref_name primitives"
    }
    set counts [hap_v5_floorplan::physical_slr_counts_for_cells $cells]
    if {[tcl::mathop::+ {*}$counts] != [llength $cells]} {
        error "V5 hard resource unexpectedly classified as virtual: ref=$ref_name cells=[llength $cells] counts=$counts"
    }
    return $counts
}

proc hap_v5_floorplan::physical_metrics {live_plan {pblock_audit {}}} {
    set audits [dict create]
    set contract_variant [dict get $live_plan contract_variant]
    if {$pblock_audit ne ""} {
        set contract_variant [dict get $pblock_audit contract_variant]
    }
    if {$contract_variant ne [dict get $live_plan contract_variant]} {
        error "V5 physical-metrics plan/audit variant mismatch"
    }
    set pblock_to_label [dict create \
        pb_v5_mlp_branch_slr0 branch0 \
        pb_v5_mlp_branch_slr2 branch2 \
        pb_v5_attention_projection_lanes_slr0 lane0 \
        pb_v5_attention_projection_lanes_slr2 lane2 \
        pb_v5_center_dsp_slr1 center \
        pb_v5_meta_gate_slr0 gate0 \
        pb_v5_meta_gate_slr2 gate2 \
        pb_v5_meta_down0_slr1 down0 \
        pb_v5_meta_down1_slr1 down1 \
        pb_v5_attention_meta_slr2 attention_meta]
    set fresh_contract [expr {$contract_variant ne "legacy10"}]
    set col3_contract [expr {
        $contract_variant eq "P1_ATTN_COL2_12_2" ||
        $contract_variant eq "P2_COHORT16_COL2_12_2"}]
    if {$col3_contract} {
        dict unset pblock_to_label pb_v5_attention_projection_lanes_slr0
        dict unset pblock_to_label pb_v5_attention_projection_lanes_slr2
        dict unset pblock_to_label pb_v5_center_dsp_slr1
        dict set pblock_to_label \
            pb_v5_attention_projection_left2_slr0 lane0
        dict set pblock_to_label \
            pb_v5_attention_projection_right2_slr2 lane2
        dict set pblock_to_label \
            pb_v5_attention_projection_center12_slr1 center
    }
    if {$fresh_contract} {
        dict set pblock_to_label \
            pb_v5_attention_row_kv_cache_slr0 attention_island
    } elseif {$contract_variant ne "legacy10"} {
        error "Illegal V5 physical-metrics contract variant: $contract_variant"
    }
    if {$pblock_audit ne "" && [dict get $pblock_audit require_placed]} {
        foreach name [dict keys $pblock_to_label] {
            set label [dict get $pblock_to_label $name]
            set record [dict get $pblock_audit records $name]
            dict set audits $label [dict create \
                physical_count [dict get $record physical_count] \
                virtual_gnd [dict get $record virtual_gnd] \
                virtual_vcc [dict get $record virtual_vcc] \
                virtual_total [dict get $record virtual_total] \
                direct_slr_empty [dict get $record direct_slr_empty] \
                is_placed_empty [dict get $record is_placed_empty] \
                target [dict get $record target] \
                wrong [dict get $record placed_wrong]]
        }
    } else {
        set branch0_key [expr {$fresh_contract ?
            "outer0_primitives" : "branch0_primitives"}]
        set branch2_key [expr {$fresh_contract ?
            "outer2_primitives" : "branch2_primitives"}]
        set center_key [expr {$col3_contract ? "center_primitives" :
            ($fresh_contract ? "center_dsp" : "legacy_center_dsp")}]
        foreach {label key target} [list \
            branch0 $branch0_key 0 \
            branch2 $branch2_key 2 \
            lane0 lane0_primitives 0 \
            lane2 lane2_primitives 2 \
            center $center_key 1 \
            gate0 gate0_primitives 0 \
            gate2 gate2_primitives 2 \
            down0 down0_primitives 1 \
            down1 down1_primitives 1 \
            attention_meta attention_meta_primitives 2] {
            dict set audits $label [hap_v5_floorplan::wrong_slr_audit \
                [dict get $live_plan $key] $target]
        }
        if {$fresh_contract} {
            dict set audits attention_island \
                [hap_v5_floorplan::wrong_slr_audit \
                    [dict get $live_plan attention_island_primitives] 0]
        }
    }
    set branch0_wrong [dict get $audits branch0 wrong]
    set branch2_wrong [dict get $audits branch2 wrong]
    set lane0_wrong [dict get $audits lane0 wrong]
    set lane2_wrong [dict get $audits lane2 wrong]
    set center_wrong [dict get $audits center wrong]
    set gate0_wrong [dict get $audits gate0 wrong]
    set gate2_wrong [dict get $audits gate2 wrong]
    set down0_wrong [dict get $audits down0 wrong]
    set down1_wrong [dict get $audits down1 wrong]
    set attention_meta_wrong [dict get $audits attention_meta wrong]
    set attention_island_wrong 0
    if {$fresh_contract} {
        set attention_island_wrong \
            [dict get $audits attention_island wrong]
    }
    set wrong_total [expr {$branch0_wrong + $branch2_wrong +
        $lane0_wrong + $lane2_wrong + $center_wrong + $gate0_wrong +
        $gate2_wrong + $down0_wrong + $down1_wrong +
        $attention_meta_wrong + $attention_island_wrong}]
    # Global unplaced excludes only rigorously classified virtual GND/VCC.
    set global_audit [hap_v5_floorplan::physical_slr_audit_for_cells \
        [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]]
    # Vivado 2025.2 leaves IS_PLACED empty on these physical primitives even
    # when LOC and SLR_INDEX are valid (the frozen Run0138 audit proves that
    # behavior).  LOC is required for every nonconstant above; unresolved
    # placement is therefore the direct-SLR-empty count, not IS_PLACED empties.
    set unplaced [dict get $global_audit direct_slr_empty]
    if {$unplaced != 0} {
        error "V5 global physical audit found unresolved primitives: direct_slr_empty=[dict get $global_audit direct_slr_empty]"
    }
    return [dict create \
        slr_dsp [hap_v5_floorplan::placed_slr_counts DSP48E2] \
        slr_uram [hap_v5_floorplan::placed_slr_counts URAM288] \
        slr_ramb36 [hap_v5_floorplan::placed_slr_counts RAMB36E2] \
        unplaced $unplaced branch0_wrong $branch0_wrong \
        branch2_wrong $branch2_wrong lane0_wrong $lane0_wrong \
        lane2_wrong $lane2_wrong center_wrong $center_wrong \
        gate0_wrong $gate0_wrong gate2_wrong $gate2_wrong \
        down0_wrong $down0_wrong down1_wrong $down1_wrong \
        attention_meta_wrong $attention_meta_wrong \
        attention_island_wrong $attention_island_wrong \
        pblock_variant $contract_variant \
        wrong_total $wrong_total collection_audits $audits \
        global_virtual_gnd [dict get $global_audit virtual_gnd] \
        global_virtual_vcc [dict get $global_audit virtual_vcc] \
        global_virtual_total [dict get $global_audit virtual_total] \
        global_physical_count [dict get $global_audit physical_count] \
        global_direct_slr_empty [dict get $global_audit direct_slr_empty] \
        global_is_placed_empty [dict get $global_audit is_placed_empty]]
}

proc hap_v5_floorplan::physical_ok {live_plan metrics} {
    set dsp [dict get $metrics slr_dsp]
    set uram [dict get $metrics slr_uram]
    set variant [dict get $metrics pblock_variant]
    if {$variant ne [dict get $live_plan contract_variant]} {
        error "V5 physical-ok plan/metrics variant mismatch"
    }
    if {$variant eq "P2_COHORT16_COL2_12_2" ||
        $variant eq "P1_ATTN_COL2_12_2" || $variant eq "P0_11"} {
        set expected_dsp [list [dict get $live_plan planned_slr0_dsp] \
            [dict get $live_plan planned_slr1_dsp] \
            [dict get $live_plan planned_slr2_dsp]]
    } elseif {$variant eq "legacy10"} {
        set expected_dsp [list \
            [dict get $live_plan legacy_planned_slr0_dsp] \
            [dict get $live_plan legacy_planned_slr1_dsp] \
            [dict get $live_plan legacy_planned_slr2_dsp]]
    } else {
        error "Illegal V5 physical-ok contract variant: $variant"
    }
    return [expr {[dict get $metrics unplaced] == 0 &&
        [dict get $metrics wrong_total] == 0 &&
        $dsp eq $expected_dsp &&
        [lindex $dsp 0] <= 1900 && [lindex $dsp 1] <= 1900 &&
        [lindex $dsp 2] <= 1900 && $uram eq {224 224 304}}]
}

proc hap_v5_floorplan::pblock_specs {live_plan {variant P0_11}} {
    hap_v5_floorplan::require_variant $variant
    if {$variant ne [dict get $live_plan contract_variant]} {
        error "V5 pblock-spec plan/argument variant mismatch"
    }
    set lane_dsp [dict get $live_plan projection_lane_dsp]
    set col3_contract [expr {
        $variant eq "P1_ATTN_COL2_12_2" ||
        $variant eq "P2_COHORT16_COL2_12_2"}]
    if {$col3_contract || $variant eq "P0_11"} {
        set center_key [expr {$col3_contract ?
            "center_primitives" : "center_dsp"}]
        set center_dsp [dict get $live_plan planned_slr1_dsp]
        set outer0_key outer0_primitives
        set outer2_key outer2_primitives
        set outer0_dsp [dict get $live_plan outer0_dsp]
        set outer2_dsp [dict get $live_plan outer2_dsp]
        set outer0_ramb36 [dict get $live_plan outer0_ramb36]
        set outer2_ramb36 [dict get $live_plan outer2_ramb36]
    } elseif {$variant eq "legacy10"} {
        set center_key legacy_center_dsp
        set center_dsp [dict get $live_plan legacy_planned_slr1_dsp]
        set outer0_key branch0_primitives
        set outer2_key branch2_primitives
        set outer0_dsp [dict get $live_plan branch0_dsp]
        set outer2_dsp [dict get $live_plan branch2_dsp]
        set outer0_ramb36 [hap_v5_floorplan::count_ref \
            [dict get $live_plan branch0_primitives] RAMB36E2]
        set outer2_ramb36 [hap_v5_floorplan::count_ref \
            [dict get $live_plan branch2_primitives] RAMB36E2]
    } else {
        error "Illegal V5 pblock contract variant: $variant"
    }
    set lane0_pblock [expr {$col3_contract ?
        "pb_v5_attention_projection_left2_slr0" :
        "pb_v5_attention_projection_lanes_slr0"}]
    set lane2_pblock [expr {$col3_contract ?
        "pb_v5_attention_projection_right2_slr2" :
        "pb_v5_attention_projection_lanes_slr2"}]
    set center_pblock [expr {$col3_contract ?
        "pb_v5_attention_projection_center12_slr1" :
        "pb_v5_center_dsp_slr1"}]
    set specs [list \
        [dict create name pb_v5_mlp_branch_slr0 target 0 \
            key $outer0_key dsp $outer0_dsp uram 0 \
            ramb36 $outer0_ramb36 ramb18 0] \
        [dict create name pb_v5_mlp_branch_slr2 target 2 \
            key $outer2_key dsp $outer2_dsp uram 0 \
            ramb36 $outer2_ramb36 ramb18 0] \
        [dict create name $lane0_pblock \
            target 0 key lane0_primitives \
            dsp [expr {[dict get $live_plan move0] * $lane_dsp}] uram 0 \
            ramb36 0 ramb18 0] \
        [dict create name $lane2_pblock \
            target 2 key lane2_primitives \
            dsp [expr {[dict get $live_plan move2] * $lane_dsp}] uram 0 \
            ramb36 0 ramb18 0] \
        [dict create name $center_pblock target 1 \
            key $center_key dsp $center_dsp \
            uram 0 ramb36 [dict get $live_plan swiglu_central_ramb36] \
            ramb18 0] \
        [dict create name pb_v5_meta_gate_slr0 target 0 \
            key gate0_primitives dsp 0 uram 224] \
        [dict create name pb_v5_meta_gate_slr2 target 2 \
            key gate2_primitives dsp 0 uram 224] \
        [dict create name pb_v5_meta_down0_slr1 target 1 \
            key down0_primitives dsp 0 uram 112] \
        [dict create name pb_v5_meta_down1_slr1 target 1 \
            key down1_primitives dsp 0 uram 112] \
        [dict create name pb_v5_attention_meta_slr2 target 2 \
            key attention_meta_primitives dsp 0 uram 80]]
    if {$col3_contract || $variant eq "P0_11"} {
        lappend specs [dict create \
            name pb_v5_attention_row_kv_cache_slr0 target 0 \
            key attention_island_primitives \
            dsp [dict get $live_plan attention_island_dsp] \
            uram [dict get $live_plan attention_island_uram] \
            ramb36 [dict get $live_plan attention_island_ramb36] \
            ramb18 [dict get $live_plan attention_island_ramb18]]
    }
    return $specs
}

proc hap_v5_floorplan::property_is_false {object property} {
    set value [string tolower [get_property $property $object]]
    return [expr {$value eq "0" || $value eq "false"}]
}

proc hap_v5_floorplan::expanded_pblock_primitives {pblock} {
    set direct_members [get_cells -quiet -of_objects $pblock]
    set members {}
    foreach member $direct_members {
        if {[get_property IS_PRIMITIVE $member]} {
            lappend members $member
        } else {
            set members [concat $members \
                [hap_v5_floorplan::primitive_descendants $member]]
        }
    }
    return [lsort -dictionary -unique $members]
}

proc hap_v5_floorplan::pblockable_primitives {cells} {
    set result {}
    foreach cell $cells \
            is_primitive [get_property IS_PRIMITIVE $cells] \
            primitive_level [get_property PRIMITIVE_LEVEL $cells] \
            ref_name [get_property REF_NAME $cells] {
        if {$is_primitive && $primitive_level ne "INTERNAL" &&
            $ref_name ne "GND" && $ref_name ne "VCC"} {
            lappend result $cell
        }
    }
    return [lsort -dictionary -unique $result]
}

# Prove that the selected canonical hard-pblock contract covers every live
# selected for them.  A post-place optimizer is allowed to add replicated
# descendants to a hard pblock; those extras are accepted only when they are
# primitive, physically in the same target SLR, and do not alter the exact
# DSP/URAM signature.  Missing canonical members always fail closed.
proc hap_v5_floorplan::audit_pblock_contract {live_plan require_placed \
        {variant P0_11} {delegate_specs {}}} {
    if {$require_placed != 0 && $require_placed != 1} {
        error "require_placed must be 0 or 1"
    }
    set records [dict create]
    set all_member_names {}
    set all_member_dsp {}
    set all_member_uram {}
    set member_count_sum 0
    set placed_wrong_total 0
    set extra_count_total 0
    set delegated_count_total 0

    hap_v5_floorplan::require_variant $variant
    if {$variant ne [dict get $live_plan contract_variant]} {
        error "V5 pblock-audit plan/argument variant mismatch"
    }
    set delegate_records {}
    set delegate_names {}
    foreach delegate_spec $delegate_specs {
        foreach key {name target} {
            if {![dict exists $delegate_spec $key]} {
                error "V5 delegated pblock spec lacks $key"
            }
        }
        set delegate_name [dict get $delegate_spec name]
        if {[lsearch -exact $delegate_names $delegate_name] >= 0} {
            error "V5 delegated pblock spec is duplicated: $delegate_name"
        }
        lappend delegate_names $delegate_name
        set delegate_pblock [get_pblocks -quiet $delegate_name]
        if {[llength $delegate_pblock] != 1} {
            error "V5 delegated pblock is not unique: $delegate_name"
        }
        set delegate_members [hap_v5_floorplan::expanded_pblock_primitives \
            [lindex $delegate_pblock 0]]
        set delegate_members [hap_v5_floorplan::pblockable_primitives \
            $delegate_members]
        if {[llength $delegate_members] == 0} {
            error "V5 delegated pblock is empty: $delegate_name"
        }
        lappend delegate_records [dict create name $delegate_name \
            target [dict get $delegate_spec target] \
            members $delegate_members]
    }
    foreach spec [hap_v5_floorplan::pblock_specs $live_plan $variant] {
        set name [dict get $spec name]
        set target [dict get $spec target]
        set key [dict get $spec key]
        set expected_dsp [dict get $spec dsp]
        set expected_uram [dict get $spec uram]
        set expected_ramb36 -1
        set expected_ramb18 -1
        if {[dict exists $spec ramb36]} {
            set expected_ramb36 [dict get $spec ramb36]
            set expected_ramb18 [dict get $spec ramb18]
        }
        set selected [dict get $live_plan $key]
        if {[llength $selected] == 0} {
            error "V5 canonical selector for $name is empty"
        }

        set pblock [get_pblocks -quiet $name]
        if {[llength $pblock] != 1} {
            error "Required V5 hard pblock is not unique: $name -> $pblock"
        }
        if {![hap_v5_floorplan::property_is_false $pblock IS_SOFT] ||
            ![hap_v5_floorplan::property_is_false \
                $pblock CONTAIN_ROUTING] ||
            ![hap_v5_floorplan::property_is_false \
                $pblock EXCLUDE_PLACEMENT]} {
            error "Required V5 pblock property contract failed: $name"
        }

        set target_name SLR${target}
        set ranges [get_property GRID_RANGES $pblock]
        set target_seen 0
        set foreign_seen 0
        foreach range $ranges {
            foreach slr [regexp -all -inline {SLR[0-2]} $range] {
                if {$slr eq $target_name} {
                    set target_seen 1
                } else {
                    set foreign_seen 1
                }
            }
        }
        if {!$target_seen || $foreign_seen} {
            error "V5 pblock target mismatch: $name expected=$target_name actual=$ranges"
        }

        # Pblock constraints are hierarchical: Vivado may preserve the
        # canonical root/member object in the checkpoint instead of
        # materializing every descendant in get_cells -of_objects.  Expand
        # the live pblock membership to primitives for an apples-to-apples
        # comparison with the canonical primitive selector.
        set direct_members [get_cells -quiet -of_objects $pblock]
        set direct_count [llength $direct_members]
        if {$direct_count == 0 && [llength $delegate_records] == 0} {
            error "Required V5 pblock has no direct member: $name"
        }
        set members [hap_v5_floorplan::expanded_pblock_primitives $pblock]
        set selected_membership $selected
        if {[llength $delegate_records] != 0} {
            # Delegated fine pblocks own transformed macro objects.  INTERNAL
            # macro children and global constants cannot be pblock members,
            # so compare both sides in Vivado's legal membership domain.
            set members [hap_v5_floorplan::pblockable_primitives $members]
            set selected_membership \
                [hap_v5_floorplan::pblockable_primitives $selected]
        }
        set selected_names \
            [hap_v5_floorplan::object_names $selected_membership]
        set member_names [hap_v5_floorplan::object_names $members]
        set delegated_members {}
        foreach delegate_record $delegate_records {
            set overlap [hap_v5_floorplan::list_intersection \
                $selected_membership \
                [dict get $delegate_record members]]
            if {[llength $overlap] == 0} {continue}
            if {[dict get $delegate_record target] != $target} {
                error "V5 canonical member delegated to wrong SLR: $name delegate=[dict get $delegate_record name] count=[llength $overlap]"
            }
            set delegated_members [concat $delegated_members $overlap]
        }
        set delegated_members [lsort -dictionary -unique $delegated_members]
        set delegated_names [hap_v5_floorplan::object_names $delegated_members]
        set members [hap_v5_floorplan::list_union $members $delegated_members]
        set member_names [hap_v5_floorplan::object_names $members]
        if {[llength $members] == 0} {
            error "Required V5 pblock has neither direct nor delegated members: $name"
        }
        set missing [hap_v5_floorplan::list_subtract \
            $selected_names $member_names]
        set extra [hap_v5_floorplan::list_subtract \
            $member_names $selected_names]
        if {[llength $missing] != 0} {
            error "V5 pblock/live-selector membership is incomplete: $name missing=[llength $missing] extra=[llength $extra]"
        }

        set selected_dsp [hap_v5_floorplan::count_ref \
            $selected DSP48E2]
        set selected_uram [hap_v5_floorplan::count_ref \
            $selected URAM288]
        set member_dsp [hap_v5_floorplan::count_ref $members DSP48E2]
        set member_uram [hap_v5_floorplan::count_ref $members URAM288]
        set selected_ramb36 [hap_v5_floorplan::count_ref \
            $selected RAMB36E2]
        set selected_ramb18 [hap_v5_floorplan::count_ref \
            $selected RAMB18E2]
        set member_ramb36 [hap_v5_floorplan::count_ref $members RAMB36E2]
        set member_ramb18 [hap_v5_floorplan::count_ref $members RAMB18E2]
        if {$selected_dsp != $expected_dsp ||
            $member_dsp != $expected_dsp ||
            $selected_uram != $expected_uram ||
            $member_uram != $expected_uram} {
            error "V5 pblock resource signature mismatch: $name selected=$selected_dsp/$selected_uram members=$member_dsp/$member_uram expected=$expected_dsp/$expected_uram"
        }
        if {$expected_ramb36 >= 0 &&
            ($selected_ramb36 != $expected_ramb36 ||
             $member_ramb36 != $expected_ramb36 ||
             $selected_ramb18 != $expected_ramb18 ||
             $member_ramb18 != $expected_ramb18)} {
            error "V5 P0 pblock BRAM signature mismatch: $name selected=$selected_ramb36/$selected_ramb18 members=$member_ramb36/$member_ramb18 expected=$expected_ramb36/$expected_ramb18"
        }

        set placed_wrong 0
        set placement_audit [dict create slr_counts {0 0 0} \
            physical_count 0 virtual_gnd 0 virtual_vcc 0 \
            virtual_total 0 total [llength $members] wrong 0 \
            direct_slr_empty 0 is_placed_empty 0 target $target]
        set extra_wrong 0
        if {$require_placed} {
            set placement_audit [hap_v5_floorplan::wrong_slr_audit \
                $members $target]
            set placed_wrong [dict get $placement_audit wrong]
            if {$placed_wrong != 0} {
                error "V5 pblock has wrong/unplaced members: $name count=$placed_wrong"
            }
            set extra_cells {}
            foreach extra_name $extra {
                set extra_cell [get_cells -quiet $extra_name]
                if {[llength $extra_cell] != 1 ||
                    ![get_property IS_PRIMITIVE $extra_cell]} {
                    error "V5 pblock extra member is not a unique live primitive: $name cell=$extra_name"
                }
                lappend extra_cells $extra_cell
            }
            set extra_wrong [hap_v5_floorplan::count_wrong_slr \
                $extra_cells $target]
            if {$extra_wrong != 0} {
                error "V5 pblock has wrong/unplaced optimizer extras: $name count=$extra_wrong"
            }
        }
        incr placed_wrong_total $placed_wrong
        incr extra_count_total [llength $extra]
        incr delegated_count_total [llength $delegated_names]
        incr member_count_sum [llength $member_names]
        set all_member_names [concat $all_member_names $member_names]
        set member_refs [get_property REF_NAME $members]
        if {[llength $member_refs] != [llength $members]} {
            error "V5 pblock bulk member REF_NAME cardinality mismatch: $name"
        }
        foreach member $members ref_name $member_refs {
            switch -- $ref_name {
                DSP48E2 {lappend all_member_dsp $member}
                URAM288 {lappend all_member_uram $member}
            }
        }
        dict set records $name [dict create target $target \
            member_count [llength $member_names] dsp $member_dsp \
            uram $member_uram ramb36 $member_ramb36 \
            ramb18 $member_ramb18 missing 0 extra [llength $extra] \
            delegated [llength $delegated_names] \
            physical_count [dict get $placement_audit physical_count] \
            virtual_gnd [dict get $placement_audit virtual_gnd] \
            virtual_vcc [dict get $placement_audit virtual_vcc] \
            virtual_total [dict get $placement_audit virtual_total] \
            direct_slr_empty [dict get $placement_audit direct_slr_empty] \
            is_placed_empty [dict get $placement_audit is_placed_empty] \
            placed_wrong $placed_wrong extra_wrong $extra_wrong]
    }

    set unique_member_names [lsort -dictionary -unique $all_member_names]
    if {[llength $unique_member_names] != $member_count_sum} {
        error "V5 canonical hard pblocks have overlapping member assignments"
    }
    set covered_dsp_names [hap_v5_floorplan::object_names $all_member_dsp]
    set covered_uram_names [hap_v5_floorplan::object_names $all_member_uram]
    set all_dsp_names [hap_v5_floorplan::object_names \
        [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
    set all_uram_names [hap_v5_floorplan::object_names \
        [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
    if {$covered_dsp_names ne $all_dsp_names ||
        [llength $covered_dsp_names] != [dict get $live_plan total_dsp]} {
        error "V5 hard-pblock DSP coverage is not exact"
    }
    if {$covered_uram_names ne $all_uram_names ||
        [llength $covered_uram_names] != [dict get $live_plan total_uram]} {
        error "V5 hard-pblock URAM coverage is not exact"
    }
    set expected_count [expr {$variant eq "legacy10" ? 10 : 11}]
    if {[dict size $records] != $expected_count} {
        error "V5 pblock variant/count mismatch: variant=$variant expected=$expected_count actual=[dict size $records]"
    }
    return [dict create ok 1 require_placed $require_placed \
        contract_variant $variant \
        pblock_count [dict size $records] \
        member_count $member_count_sum \
        optimizer_extra_count $extra_count_total \
        delegated_member_count $delegated_count_total \
        dsp_coverage [llength $covered_dsp_names] \
        uram_coverage [llength $covered_uram_names] \
        placed_wrong $placed_wrong_total records $records]
}

proc hap_v5_floorplan::write_pblock_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok require_placed contract_variant pblock_count member_count
        optimizer_extra_count delegated_member_count dsp_coverage uram_coverage
        placed_wrong} {
        puts $fp "$key=[dict get $audit $key]"
    }
    foreach name [lsort -dictionary [dict keys [dict get $audit records]]] {
        set record [dict get $audit records $name]
        foreach key {target member_count dsp uram ramb36 ramb18 missing extra
            delegated
            physical_count virtual_gnd virtual_vcc virtual_total
            direct_slr_empty is_placed_empty
            placed_wrong extra_wrong} {
            puts $fp "${name}_${key}=[dict get $record $key]"
        }
    }
    puts $fp "status=$status"
    close $fp
}
