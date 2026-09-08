# Fine-grained production floorplan selectors derived from the independently
# routed cohort16 projection geometry.  This file defines selectors and specs
# only; it never mutates the open design.

namespace eval hap_v5_fine19 {
    variable contract_variant P3_COHORT16_OOC10_19
    variable expected_part xcvu9p-flga2104-2L-e
    variable expected_top hap_attention_mlp_production_core
}

proc hap_v5_fine19::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "V5 fine19 $label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_v5_fine19::count_ref {cells ref_name} {
    return [hap_v5_floorplan::count_ref $cells $ref_name]
}

# Vivado exposes transformed macro implementation children as INTERNAL
# primitives, but add_cells_to_pblock cannot own those objects directly.
# Normalize both the requested and live pblock membership to the same legal
# representation while retaining the all-primitive logical partition above it.
proc hap_v5_fine19::pblockable {cells} {
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

proc hap_v5_fine19::pblockable_descendants {root} {
    return [pblockable [hap_v5_floorplan::primitive_descendants $root]]
}

proc hap_v5_fine19::child {root relative label} {
    set path "[get_property NAME $root]/$relative"
    set cells [get_cells -quiet $path]
    require_count $label $cells 1
    return [lindex $cells 0]
}

proc hap_v5_fine19::partition_region1 {region1_root \
        region1_root_primitives region1_primitives \
        {allow_optimizer_extras 0}} {
    if {$allow_optimizer_extras != 0 && $allow_optimizer_extras != 1} {
        error "V5 fine19 allow_optimizer_extras must be 0 or 1"
    }
    set root_name [get_property NAME $region1_root]
    set root_prefix "${root_name}/"
    set lane_roots [lsort -dictionary -unique [get_cells -quiet \
        -hierarchical -filter \
        "NAME =~ ${root_name}/* && \
         (REF_NAME == hap_a8w8_group32_lane_s42 || \
          ORIG_REF_NAME == hap_a8w8_group32_lane_s42)"]]
    require_count region1_lane_roots $lane_roots 32

    set lane_half [dict create]
    set lane_primitive_count [dict create]
    set lane_dsp_count [dict create]
    set cols4_5_lane_roots {}
    set cols6_7_lane_roots {}
    foreach lane $lane_roots {
        set lane_name [get_property NAME $lane]
        set relative [string range $lane_name [string length $root_prefix] end]
        if {![regexp \
                {^g_row\[([0-7])\]\.g_col\[([0-3])\]\.u_lane$} \
                $relative -> row local_col]} {
            error "V5 fine19 unexpected region1 lane: $lane_name"
        }
        set half [expr {$local_col <= 1 ? "cols4_5" : "cols6_7"}]
        dict set lane_half $lane_name $half
        dict set lane_primitive_count $lane_name 0
        dict set lane_dsp_count $lane_name 0
        if {$half eq "cols4_5"} {
            lappend cols4_5_lane_roots $lane
        } else {
            lappend cols6_7_lane_roots $lane
        }
    }
    require_count region1_cols4_5_lane_roots $cols4_5_lane_roots 16
    require_count region1_cols6_7_lane_roots $cols6_7_lane_roots 16

    set cols4_5_dsp {}
    set cols6_7_dsp {}
    foreach primitive $region1_root_primitives \
            primitive_name [get_property NAME $region1_root_primitives] \
            primitive_ref [get_property REF_NAME $region1_root_primitives] {
        set relative [string range $primitive_name \
            [string length $root_prefix] end]
        if {![regexp \
                {^(g_row\[[0-7]\]\.g_col\[[0-3]\]\.u_lane)(/|$)} \
                $relative -> lane_relative boundary]} {
            continue
        }
        set lane_name "${root_prefix}${lane_relative}"
        if {![dict exists $lane_half $lane_name]} {
            error "V5 fine19 region1 primitive maps to unknown lane: $primitive_name"
        }
        dict incr lane_primitive_count $lane_name
        if {$primitive_ref eq "DSP48E2"} {
            dict incr lane_dsp_count $lane_name
            if {[dict get $lane_half $lane_name] eq "cols4_5"} {
                lappend cols4_5_dsp $primitive
            } else {
                lappend cols6_7_dsp $primitive
            }
        }
    }
    set cols4_5_dsp [lsort -dictionary -unique $cols4_5_dsp]
    set cols6_7_dsp [lsort -dictionary -unique $cols6_7_dsp]
    foreach lane_name [dict keys $lane_half] {
        if {[dict get $lane_primitive_count $lane_name] == 0 ||
            [dict get $lane_dsp_count $lane_name] != 17} {
            error "V5 fine19 region1 lane signature mismatch: lane=$lane_name primitives=[dict get $lane_primitive_count $lane_name] dsp=[dict get $lane_dsp_count $lane_name]"
        }
    }
    require_count region1_cols4_5_dsp $cols4_5_dsp 272
    require_count region1_cols6_7_dsp $cols6_7_dsp 272

    set striped_dsp [hap_v5_floorplan::list_union \
        $cols4_5_dsp $cols6_7_dsp]
    set logic_residual [hap_v5_floorplan::list_subtract \
        $region1_primitives $striped_dsp]
    set logic_count [llength $logic_residual]
    set region1_count [llength $region1_primitives]
    set optimizer_extra_count [expr {$logic_count - 74509}]
    if {[count_ref $logic_residual DSP48E2] != 0 ||
        $optimizer_extra_count < 0 ||
        (!$allow_optimizer_extras && $optimizer_extra_count != 0) ||
        ($allow_optimizer_extras && $optimizer_extra_count > 4096) ||
        $region1_count != 75053 + $optimizer_extra_count} {
        error "V5 fine19 region1 logic signature mismatch: region1=[llength $region1_primitives] logic=[llength $logic_residual] dsp=[count_ref $logic_residual DSP48E2]"
    }
    if {[llength [hap_v5_floorplan::list_intersection \
            $cols4_5_dsp $cols6_7_dsp]] != 0 ||
        [hap_v5_floorplan::object_names [hap_v5_floorplan::list_union \
            $striped_dsp $logic_residual]] ne \
        [hap_v5_floorplan::object_names $region1_primitives]} {
        error "V5 fine19 region1 DSP-stripe partition is not exact"
    }
    return [dict create lane_roots $lane_roots \
        cols4_5_lane_roots $cols4_5_lane_roots \
        cols6_7_lane_roots $cols6_7_lane_roots \
        cols4_5_dsp_primitives $cols4_5_dsp \
        cols6_7_dsp_primitives $cols6_7_dsp \
        logic_residual_primitives $logic_residual \
        optimizer_extra_count $optimizer_extra_count exact_cover 1]
}

proc hap_v5_fine19::partition_owner_inputs {projection_root \
        owner_primitives center_region3_primitives} {
    set root_name [get_property NAME $projection_root]
    set root_prefix "${root_name}/"
    set activation_source 0
    set zero_source 0
    set weight_ff_source 0
    set weight_lut_source 0
    set activation {}
    set zero_point {}
    set region2_weight_ff {}
    set region2_weight_lut {}
    set region3_weight_ff {}
    set region3_weight_lut {}

    foreach primitive $owner_primitives \
            primitive_name [get_property NAME $owner_primitives] \
            primitive_ref [get_property REF_NAME $owner_primitives] {
        if {[string first $root_prefix $primitive_name] != 0} {
            error "V5 fine19 owner primitive is outside projection root: $primitive_name"
        }
        set relative [string range $primitive_name \
            [string length $root_prefix] end]
        if {[regexp \
                {^group_stage_act_u8_region_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr activation_source
            if {$primitive_ref ne "FDRE"} {
                error "V5 fine19 activation staging type mismatch: $primitive_name"
            }
            if {($index / 256) % 4 == 3} {lappend activation $primitive}
            continue
        }
        if {[regexp \
                {^group_stage_act_zero_point_region_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr zero_source
            if {$primitive_ref ne "FDRE"} {
                error "V5 fine19 zero-point staging type mismatch: $primitive_name"
            }
            if {($index / 8) % 4 == 3} {lappend zero_point $primitive}
            continue
        }
        if {[regexp \
                {^group_stage_weight_s8_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr weight_ff_source
            if {$primitive_ref ne "FDRE"} {
                error "V5 fine19 weight staging FF type mismatch: $primitive_name"
            }
            if {$index >= 2048 && $index < 3072} {
                lappend region2_weight_ff $primitive
            }
            if {$index >= 3072 && $index < 3584} {
                lappend region3_weight_ff $primitive
            }
            continue
        }
        if {[regexp \
                {^group_stage_weight_s8_r\[([0-9]+)\]_i_1$} \
                $relative -> index]} {
            incr weight_lut_source
            if {$primitive_ref ne "LUT3"} {
                error "V5 fine19 weight staging LUT type mismatch: $primitive_name"
            }
            if {$index >= 2048 && $index < 3072} {
                lappend region2_weight_lut $primitive
            }
            if {$index >= 3072 && $index < 3584} {
                lappend region3_weight_lut $primitive
            }
        }
    }
    foreach {label actual expected} [list activation_source $activation_source 8192 \
            zero_source $zero_source 256 weight_ff_source $weight_ff_source 4096 \
            weight_lut_source $weight_lut_source 4096] {
        if {$actual != $expected} {
            error "V5 fine19 $label mismatch: expected=$expected actual=$actual"
        }
    }
    foreach {label values expected} [list activation $activation 2048 \
            zero_point $zero_point 64 region2_weight_ff $region2_weight_ff 1024 \
            region2_weight_lut $region2_weight_lut 1024 \
            region3_weight_ff $region3_weight_ff 512 \
            region3_weight_lut $region3_weight_lut 512] {
        set $label [lsort -dictionary -unique $values]
        require_count $label [set $label] $expected
    }

    set region3_input [hap_v5_floorplan::list_union $activation $zero_point]
    set region2_weight [hap_v5_floorplan::list_union \
        $region2_weight_ff $region2_weight_lut]
    set region3_weight [hap_v5_floorplan::list_union \
        $region3_weight_ff $region3_weight_lut]
    set owner_floorplan [hap_v5_floorplan::list_subtract \
        $owner_primitives $region3_input]
    set owner_residual [hap_v5_floorplan::list_subtract \
        $owner_floorplan $region2_weight]
    set center_region3_floorplan [hap_v5_floorplan::list_union \
        $center_region3_primitives $region3_input]

    if {[count_ref $region3_input DSP48E2] != 0 ||
        [count_ref $region3_input FDRE] != 2112 ||
        [llength [hap_v5_floorplan::list_intersection \
            $region3_input $center_region3_primitives]] != 0 ||
        [hap_v5_floorplan::object_names [hap_v5_floorplan::list_union \
            $owner_floorplan $region3_input]] ne \
        [hap_v5_floorplan::object_names $owner_primitives] ||
        [hap_v5_floorplan::object_names [hap_v5_floorplan::list_union \
            $owner_residual $region2_weight]] ne \
        [hap_v5_floorplan::object_names $owner_floorplan] ||
        [llength [hap_v5_floorplan::list_intersection \
            $region3_weight $owner_floorplan]] != 1024} {
        error "V5 fine19 owner/input partition is not exact"
    }
    return [dict create activation_primitives $activation \
        zero_point_primitives $zero_point region3_input_primitives $region3_input \
        owner_region2_weight_ff_primitives $region2_weight_ff \
        owner_region2_weight_lut_primitives $region2_weight_lut \
        owner_region2_weight_primitives $region2_weight \
        owner_region3_weight_ff_primitives $region3_weight_ff \
        owner_region3_weight_lut_primitives $region3_weight_lut \
        owner_region3_weight_primitives $region3_weight \
        owner_floorplan_primitives $owner_floorplan \
        owner_residual_primitives $owner_residual \
        center_region3_floorplan_primitives $center_region3_floorplan \
        exact_cover 1 weight_owner_residency_ok 1]
}

proc hap_v5_fine19::discover {base_plan {allow_optimizer_extras 0}} {
    variable expected_part
    variable expected_top
    variable contract_variant
    if {$allow_optimizer_extras != 0 && $allow_optimizer_extras != 1} {
        error "V5 fine19 allow_optimizer_extras must be 0 or 1"
    }
    if {[get_property PART [current_design]] ne $expected_part ||
        [get_property TOP [current_design]] ne $expected_top ||
        [dict get $base_plan contract_variant] ne \
            "P2_COHORT16_COL2_12_2"} {
        error "V5 fine19 base design identity mismatch"
    }

    set projection_roots [hap_v5_floorplan::module_cells \
        hap_projection_core16x16_w8_reuse]
    require_count projection_roots $projection_roots 1
    set projection_root [lindex $projection_roots 0]
    set frontend_root [child $projection_root u_frontend frontend_root]
    set array_root [child $projection_root u_array array_root]
    set left_root [child $array_root u_left2 left_root]
    set center_root [child $array_root u_center12 center_root]
    set right_root [child $array_root u_right2 right_root]
    set region0_root [child $center_root u_region0_cols2_3 region0_root]
    set region1_root [child $center_root u_region1_cols4_7 region1_root]
    set region2_root [child $center_root u_region2_cols8_11 region2_root]
    set region3_root [child $center_root u_region3_cols12_13 region3_root]
    if {[get_property NAME $array_root] ne \
            [get_property NAME [dict get $base_plan projection_array]] ||
        [get_property NAME $left_root] ne \
            [get_property NAME [dict get $base_plan projection_left_shard]] ||
        [get_property NAME $center_root] ne \
            [get_property NAME [dict get $base_plan projection_center_shard]] ||
        [get_property NAME $right_root] ne \
            [get_property NAME [dict get $base_plan projection_right_shard]]} {
        error "V5 fine19 projection roots disagree with the production selector"
    }

    set projection_primitives \
        [hap_v5_floorplan::primitive_descendants $projection_root]
    set frontend_primitives \
        [hap_v5_floorplan::primitive_descendants $frontend_root]
    set left_primitives [hap_v5_floorplan::primitive_descendants $left_root]
    set center_primitives [hap_v5_floorplan::primitive_descendants $center_root]
    set right_primitives [hap_v5_floorplan::primitive_descendants $right_root]
    set region0_root_primitives \
        [hap_v5_floorplan::primitive_descendants $region0_root]
    set region1_root_primitives \
        [hap_v5_floorplan::primitive_descendants $region1_root]
    set region2_primitives \
        [hap_v5_floorplan::primitive_descendants $region2_root]
    set region3_primitives \
        [hap_v5_floorplan::primitive_descendants $region3_root]
    set center_region_roots [hap_v5_floorplan::list_union \
        $region0_root_primitives $region1_root_primitives \
        $region2_primitives $region3_primitives]
    set center_wrapper [hap_v5_floorplan::list_subtract \
        $center_primitives $center_region_roots]
    set region0_primitives $region0_root_primitives
    set region1_primitives [hap_v5_floorplan::list_union \
        $region1_root_primitives $center_wrapper]

    set shard_primitives [hap_v5_floorplan::list_union \
        $left_primitives $center_primitives $right_primitives]
    set owner_and_frontend [hap_v5_floorplan::list_subtract \
        $projection_primitives $shard_primitives]
    if {[hap_v5_floorplan::object_names [hap_v5_floorplan::list_intersection \
            $owner_and_frontend $frontend_primitives]] ne \
        [hap_v5_floorplan::object_names $frontend_primitives]} {
        error "V5 fine19 frontend is not a projection owner subset"
    }
    set owner_primitives [hap_v5_floorplan::list_subtract \
        $owner_and_frontend $frontend_primitives]
    set owner_plan [partition_owner_inputs $projection_root \
        $owner_primitives $region3_primitives]
    set region1_plan [partition_region1 $region1_root \
        $region1_root_primitives $region1_primitives \
        $allow_optimizer_extras]
    set optimizer_extra_count [dict get $region1_plan optimizer_extra_count]
    set region0_frontend [hap_v5_floorplan::list_union \
        $region0_primitives $frontend_primitives]

    set projection_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
        $projection_root DSP48E2]
    set frontend_dsp [hap_v5_floorplan::primitive_descendants_of_ref \
        $frontend_root DSP48E2]
    # The P2 selector exposes the non-projection count but keeps its live
    # objects inside center_primitives.  Recover that exact 149-DSP set as the
    # complement of center12, then remove the 64 frontend DSPs now owned by
    # the imported projection partition.
    set base_center_extra_dsp [hap_v5_floorplan::list_subtract \
        [dict get $base_plan center_primitives] $center_primitives]
    if {[llength $base_center_extra_dsp] != 149 ||
        [count_ref $base_center_extra_dsp DSP48E2] != 149} {
        error "V5 fine19 P2 center-extra DSP signature mismatch: primitives=[llength $base_center_extra_dsp] dsp=[count_ref $base_center_extra_dsp DSP48E2]"
    }
    set nonprojection_center_dsp [hap_v5_floorplan::list_subtract \
        $base_center_extra_dsp $frontend_dsp]
    foreach {label cells expected_primitives expected_dsp} [list \
            projection $projection_primitives \
                [expr {443480 + $optimizer_extra_count}] 2240 \
            frontend $frontend_primitives 111217 64 \
            left $left_primitives 38909 272 \
            center $center_primitives \
                [expr {227833 + $optimizer_extra_count}] 1632 \
            right $right_primitives 38909 272] {
        set primitive_delta [expr {[llength $cells] - $expected_primitives}]
        if {[count_ref $cells DSP48E2] != $expected_dsp ||
            (!$allow_optimizer_extras && $primitive_delta != 0) ||
            ($allow_optimizer_extras && abs($primitive_delta) > 4096)} {
            error "V5 fine19 $label signature mismatch: primitives=[llength $cells] dsp=[count_ref $cells DSP48E2]"
        }
    }
    foreach {label cells expected_dsp} [list region0 $region0_primitives 272 \
            region1 $region1_primitives 544 region2 $region2_primitives 544 \
            region3 $region3_primitives 272] {
        if {[count_ref $cells DSP48E2] != $expected_dsp} {
            error "V5 fine19 $label DSP mismatch: [count_ref $cells DSP48E2]"
        }
    }
    require_count projection_dsp $projection_dsp 2240
    require_count frontend_dsp $frontend_dsp 64
    require_count nonprojection_center_dsp $nonprojection_center_dsp 85
    if {[count_ref $nonprojection_center_dsp DSP48E2] != 85 ||
        [llength [hap_v5_floorplan::list_intersection \
            $nonprojection_center_dsp $projection_primitives]] != 0} {
        error "V5 fine19 nonprojection center DSP partition failed"
    }

    set fine_projection_collections [list $left_primitives $region2_primitives \
        [dict get $owner_plan center_region3_floorplan_primitives] \
        [dict get $region1_plan logic_residual_primitives] \
        [dict get $region1_plan cols4_5_dsp_primitives] \
        [dict get $region1_plan cols6_7_dsp_primitives] \
        [dict get $owner_plan owner_residual_primitives] \
        [dict get $owner_plan owner_region2_weight_primitives] \
        $region0_frontend $right_primitives]
    set fine_projection_union [hap_v5_floorplan::list_union \
        {*}$fine_projection_collections]
    set member_sum 0
    foreach cells $fine_projection_collections {incr member_sum [llength $cells]}
    if {$member_sum != [llength $fine_projection_union] ||
        [hap_v5_floorplan::object_names $fine_projection_union] ne \
            [hap_v5_floorplan::object_names $projection_primitives]} {
        error "V5 fine19 ten-way projection partition is not exact"
    }

    return [dict create contract_variant $contract_variant \
        projection_root $projection_root projection_primitives $projection_primitives \
        frontend_primitives $frontend_primitives left_primitives $left_primitives \
        center_primitives $center_primitives right_primitives $right_primitives \
        center_region0_primitives $region0_primitives \
        center_region1_primitives $region1_primitives \
        center_region2_primitives $region2_primitives \
        center_region3_primitives $region3_primitives \
        center_region3_floorplan_primitives \
            [dict get $owner_plan center_region3_floorplan_primitives] \
        center_region1_cols4_5_dsp_primitives \
            [dict get $region1_plan cols4_5_dsp_primitives] \
        center_region1_cols6_7_dsp_primitives \
            [dict get $region1_plan cols6_7_dsp_primitives] \
        center_region1_logic_residual_primitives \
            [dict get $region1_plan logic_residual_primitives] \
        center_region0_frontend_primitives $region0_frontend \
        owner_primitives $owner_primitives \
        owner_floorplan_primitives \
            [dict get $owner_plan owner_floorplan_primitives] \
        owner_residual_primitives [dict get $owner_plan owner_residual_primitives] \
        owner_region2_weight_primitives \
            [dict get $owner_plan owner_region2_weight_primitives] \
        owner_region2_weight_ff_primitives \
            [dict get $owner_plan owner_region2_weight_ff_primitives] \
        owner_region2_weight_lut_primitives \
            [dict get $owner_plan owner_region2_weight_lut_primitives] \
        owner_region3_weight_primitives \
            [dict get $owner_plan owner_region3_weight_primitives] \
        region3_input_primitives [dict get $owner_plan region3_input_primitives] \
        region3_input_activation_primitives \
            [dict get $owner_plan activation_primitives] \
        region3_input_zero_point_primitives \
            [dict get $owner_plan zero_point_primitives] \
        region1_lane_roots [dict get $region1_plan lane_roots] \
        region1_cols4_5_lane_roots \
            [dict get $region1_plan cols4_5_lane_roots] \
        region1_cols6_7_lane_roots \
            [dict get $region1_plan cols6_7_lane_roots] \
        region1_exact_cover [dict get $region1_plan exact_cover] \
        owner_exact_cover [dict get $owner_plan exact_cover] \
        weight_owner_residency_ok \
            [dict get $owner_plan weight_owner_residency_ok] \
        nonprojection_center_dsp $nonprojection_center_dsp \
        optimizer_extra_count $optimizer_extra_count \
        projection_exact_cover 1]
}

proc hap_v5_fine19::full_specs {base_plan fine_plan} {
    variable contract_variant
    if {[dict get $fine_plan contract_variant] ne $contract_variant} {
        error "V5 fine19 plan variant mismatch"
    }
    return [list \
        [dict create name pb_v5_mlp_branch_slr0 target 0 range SLR0 \
            cells [dict get $base_plan outer0_primitives]] \
        [dict create name pb_v5_mlp_branch_slr2 target 2 range SLR2 \
            cells [dict get $base_plan outer2_primitives]] \
        [dict create name pb_v5_attention_projection_left2_slr0 target 0 \
            range SLR0 cells [dict get $fine_plan left_primitives]] \
        [dict create name pb_v5_attention_projection_center_region2_cr_x0y5_x0y9 \
            target 1 range CLOCKREGION_X0Y5:CLOCKREGION_X0Y9 \
            cells [dict get $fine_plan center_region2_primitives]] \
        [dict create name pb_v5_attention_projection_center_region3_cr_x1y5_x1y9 \
            target 1 range CLOCKREGION_X1Y5:CLOCKREGION_X1Y9 \
            cells [dict get $fine_plan center_region3_floorplan_primitives]] \
        [dict create name pb_v5_attention_projection_center_region1_logic_cr_x2y5_x4y9 \
            target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
            cells [dict get $fine_plan center_region1_logic_residual_primitives]] \
        [dict create name pb_v5_attention_projection_center_region1_cols4_5_dsp_cr_x3y5_x4y9 \
            target 1 range CLOCKREGION_X3Y5:CLOCKREGION_X4Y9 \
            cells [dict get $fine_plan center_region1_cols4_5_dsp_primitives]] \
        [dict create name pb_v5_attention_projection_center_region1_cols6_7_dsp_cr_x2y5_x3y9 \
            target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X3Y9 \
            cells [dict get $fine_plan center_region1_cols6_7_dsp_primitives]] \
        [dict create name pb_v5_attention_projection_owner_cr_x2y5_x4y9 \
            target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
            cells [dict get $fine_plan owner_residual_primitives]] \
        [dict create name pb_v5_attention_projection_owner_region2_weight_cr_x2y5_x4y6 \
            target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y6 \
            cells [dict get $fine_plan owner_region2_weight_primitives]] \
        [dict create name pb_v5_attention_projection_center_region0_frontend_cr_x4y5_x5y9 \
            target 1 range CLOCKREGION_X4Y5:CLOCKREGION_X5Y9 \
            cells [dict get $fine_plan center_region0_frontend_primitives]] \
        [dict create name pb_v5_attention_projection_right2_slr2 target 2 \
            range SLR2 cells [dict get $fine_plan right_primitives]] \
        [dict create name pb_v5_center_nonprojection_dsp_slr1 target 1 \
            range SLR1 cells [dict get $fine_plan nonprojection_center_dsp]] \
        [dict create name pb_v5_meta_gate_slr0 target 0 range SLR0 \
            cells [dict get $base_plan gate0_primitives]] \
        [dict create name pb_v5_meta_gate_slr2 target 2 range SLR2 \
            cells [dict get $base_plan gate2_primitives]] \
        [dict create name pb_v5_meta_down0_slr1 target 1 range SLR1 \
            cells [dict get $base_plan down0_primitives]] \
        [dict create name pb_v5_meta_down1_slr1 target 1 range SLR1 \
            cells [dict get $base_plan down1_primitives]] \
        [dict create name pb_v5_attention_meta_slr2 target 2 range SLR2 \
            cells [dict get $base_plan attention_meta_primitives]] \
        [dict create name pb_v5_attention_row_kv_cache_slr0 target 0 \
            range SLR0 cells [dict get $base_plan attention_island_primitives]]]
}

proc hap_v5_fine19::property_is_false {object property} {
    set value [string tolower [get_property $property $object]]
    return [expr {$value eq "0" || $value eq "false" || $value eq "no"}]
}

proc hap_v5_fine19::property_is_true {object property} {
    set value [string tolower [get_property $property $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc hap_v5_fine19::spec_is_soft {spec} {
    if {![dict exists $spec soft]} {return 0}
    set soft [dict get $spec soft]
    if {$soft != 0 && $soft != 1} {
        error "V5 floorplan spec has non-boolean soft property: $soft"
    }
    return $soft
}

proc hap_v5_fine19::audit_range {name expected actual} {
    if {[regexp {^SLR[0-2]$} $expected]} {
        set accepted [list $expected ${expected}:${expected}]
    } elseif {[regexp \
            {^CLOCKREGION_X[0-9]+Y[0-9]+:CLOCKREGION_X[0-9]+Y[0-9]+$} \
            $expected]} {
        set accepted [list $expected]
    } else {
        error "V5 fine19 unsupported pblock range: $name range=$expected"
    }
    if {[llength $actual] != 1 ||
        [lsearch -exact $accepted [lindex $actual 0]] < 0} {
        error "V5 fine19 pblock range mismatch: $name expected=$expected actual=$actual"
    }
}

proc hap_v5_fine19::apply_specs {specs} {
    if {[llength [get_pblocks -quiet]] != 0} {
        error "V5 fine19 input checkpoint unexpectedly contains pblocks"
    }
    foreach spec $specs {
        set name [dict get $spec name]
        set cells [pblockable [dict get $spec cells]]
        set range [dict get $spec range]
        set soft [spec_is_soft $spec]
        if {[llength $cells] == 0} {
            error "V5 fine19 pblock selector is empty: $name"
        }
        create_pblock -quiet $name
        add_cells_to_pblock -quiet [get_pblocks $name] $cells
        resize_pblock -quiet [get_pblocks $name] -add [list $range]
        set_property IS_SOFT [expr {$soft ? "true" : "false"}] \
            [get_pblocks $name]
        set_property CONTAIN_ROUTING false [get_pblocks $name]
        set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
    }
}

proc hap_v5_fine19::apply {base_plan fine_plan} {
    apply_specs [full_specs $base_plan $fine_plan]
}

proc hap_v5_fine19::expanded_pblock_primitives {pblock} {
    set direct_members [get_cells -quiet -of_objects $pblock]
    set direct_count [llength $direct_members]
    if {$direct_count == 0} {return {}}
    set primitive_flags [get_property IS_PRIMITIVE $direct_members]
    if {[llength $primitive_flags] != $direct_count} {
        error "V5 fine19 bulk IS_PRIMITIVE cardinality mismatch: members=$direct_count flags=[llength $primitive_flags]"
    }
    set primitive_members {}
    set hierarchy_members {}
    foreach member $direct_members is_primitive $primitive_flags {
        if {$is_primitive} {
            lappend primitive_members $member
        } else {
            lappend hierarchy_members $member
        }
    }
    set result {}
    if {[llength $primitive_members] != 0} {
        set result [pblockable $primitive_members]
    }
    foreach member $hierarchy_members {
        set result [concat $result [pblockable_descendants $member]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_fine19::audit_specs {specs contract_variant require_placed} {
    if {$require_placed != 0 && $require_placed != 1} {
        error "V5 fine19 require_placed must be 0 or 1"
    }
    set expected_names {}
    foreach spec $specs {lappend expected_names [dict get $spec name]}
    set actual_names [hap_v5_floorplan::object_names [get_pblocks -quiet]]
    if {$actual_names ne [lsort -dictionary $expected_names]} {
        error "V5 fine19 pblock namespace mismatch"
    }

    set records [dict create]
    set all_member_names {}
    set member_count_sum 0
    set all_member_dsp {}
    set all_member_uram {}
    set optimizer_extra_count 0
    set placed_wrong_total 0
    set soft_pblock_count 0
    set soft_outside_total 0
    foreach spec $specs {
        set name [dict get $spec name]
        set target [dict get $spec target]
        set soft [spec_is_soft $spec]
        if {$soft} {incr soft_pblock_count}
        set selected [pblockable [dict get $spec cells]]
        set pblock [get_pblocks -quiet $name]
        require_count ${name}_pblock $pblock 1
        set soft_property_ok [expr {$soft ?
            [property_is_true $pblock IS_SOFT] :
            [property_is_false $pblock IS_SOFT]}]
        if {!$soft_property_ok ||
            ![property_is_false $pblock CONTAIN_ROUTING] ||
            ![property_is_false $pblock EXCLUDE_PLACEMENT]} {
            error "V5 fine19 pblock property mismatch: $name"
        }
        audit_range $name [dict get $spec range] \
            [get_property GRID_RANGES $pblock]

        set members [expanded_pblock_primitives $pblock]
        if {[llength $members] == 0} {
            error "V5 fine19 pblock has no primitive member: $name"
        }
        set selected_names [hap_v5_floorplan::object_names $selected]
        set member_names [hap_v5_floorplan::object_names $members]
        set missing [hap_v5_floorplan::list_subtract \
            $selected_names $member_names]
        set extra [hap_v5_floorplan::list_subtract \
            $member_names $selected_names]
        if {[llength $missing] != 0 || (!$require_placed &&
            [llength $extra] != 0)} {
            error "V5 fine19 pblock membership mismatch: $name missing=[llength $missing] extra=[llength $extra]"
        }

        set selected_dsp [count_ref $selected DSP48E2]
        set selected_uram [count_ref $selected URAM288]
        set member_dsp [count_ref $members DSP48E2]
        set member_uram [count_ref $members URAM288]
        if {$selected_dsp != $member_dsp ||
            $selected_uram != $member_uram} {
            error "V5 fine19 hard-resource membership mismatch: $name selected=$selected_dsp/$selected_uram members=$member_dsp/$member_uram"
        }

        set placement [dict create wrong 0 direct_slr_empty 0 \
            physical_count 0 virtual_gnd 0 virtual_vcc 0 virtual_total 0 \
            is_placed_empty 0]
        if {$require_placed} {
            set placement [hap_v5_floorplan::wrong_slr_audit $members $target]
            if {[dict get $placement direct_slr_empty] != 0 ||
                (!$soft && [dict get $placement wrong] != 0)} {
                error "V5 fine19 pblock placement mismatch: $name wrong=[dict get $placement wrong] unplaced=[dict get $placement direct_slr_empty]"
            }
        }
        incr member_count_sum [llength $member_names]
        incr optimizer_extra_count [llength $extra]
        if {$soft} {
            incr soft_outside_total [dict get $placement wrong]
        } else {
            incr placed_wrong_total [dict get $placement wrong]
        }
        set all_member_names [concat $all_member_names $member_names]
        set member_refs [get_property REF_NAME $members]
        if {[llength $member_refs] != [llength $members]} {
            error "V5 fine19 bulk member REF_NAME cardinality mismatch: pblock=$name"
        }
        foreach member $members ref_name $member_refs {
            switch -- $ref_name {
                DSP48E2 {lappend all_member_dsp $member}
                URAM288 {lappend all_member_uram $member}
            }
        }
        dict set records $name [dict create target $target soft $soft \
            range [dict get $spec range] member_count [llength $member_names] \
            dsp $member_dsp uram $member_uram missing [llength $missing] \
            extra [llength $extra] placed_wrong [dict get $placement wrong] \
            direct_slr_empty [dict get $placement direct_slr_empty] \
            physical_count [dict get $placement physical_count] \
            virtual_gnd [dict get $placement virtual_gnd] \
            virtual_vcc [dict get $placement virtual_vcc] \
            virtual_total [dict get $placement virtual_total] \
            is_placed_empty [dict get $placement is_placed_empty]]
    }

    set unique_member_names [lsort -dictionary -unique $all_member_names]
    set overlap [expr {$member_count_sum - [llength $unique_member_names]}]
    if {$overlap != 0} {
        error "V5 fine19 pblock members overlap: $overlap"
    }
    set covered_dsp [hap_v5_floorplan::object_names $all_member_dsp]
    set covered_uram [hap_v5_floorplan::object_names $all_member_uram]
    set design_dsp [hap_v5_floorplan::object_names [get_cells -quiet \
        -hierarchical -filter {REF_NAME == DSP48E2}]]
    set design_uram [hap_v5_floorplan::object_names [get_cells -quiet \
        -hierarchical -filter {REF_NAME == URAM288}]]
    if {$covered_dsp ne $design_dsp || [llength $covered_dsp] != 5453 ||
        $covered_uram ne $design_uram || [llength $covered_uram] != 752} {
        error "V5 fine19 hard-resource coverage mismatch: DSP=[llength $covered_dsp] URAM=[llength $covered_uram]"
    }
    return [dict create ok 1 contract_variant \
        $contract_variant require_placed $require_placed \
        pblock_count [dict size $records] member_count $member_count_sum \
        member_overlap $overlap optimizer_extra_count $optimizer_extra_count \
        soft_pblock_count $soft_pblock_count \
        soft_outside $soft_outside_total \
        dsp_coverage [llength $covered_dsp] \
        uram_coverage [llength $covered_uram] \
        placed_wrong $placed_wrong_total records $records]
}

proc hap_v5_fine19::audit {base_plan fine_plan require_placed} {
    return [audit_specs [full_specs $base_plan $fine_plan] \
        [dict get $fine_plan contract_variant] $require_placed]
}

proc hap_v5_fine19::record_wrong {audit name} {
    if {![dict exists $audit records $name]} {
        error "V5 fine19 physical metrics are missing pblock record: $name"
    }
    return [dict get $audit records $name placed_wrong]
}

proc hap_v5_fine19::physical_metrics {audit {expected_contract_variant ""}} {
    variable contract_variant
    if {$expected_contract_variant eq ""} {
        set expected_contract_variant $contract_variant
    }
    if {[dict get $audit contract_variant] ne $expected_contract_variant ||
        ![dict get $audit require_placed]} {
        error "V5 fine19 physical metrics require the expected placed audit"
    }
    set branch0_wrong [record_wrong $audit pb_v5_mlp_branch_slr0]
    set branch2_wrong [record_wrong $audit pb_v5_mlp_branch_slr2]
    set lane0_wrong [record_wrong $audit \
        pb_v5_attention_projection_left2_slr0]
    set lane2_wrong [record_wrong $audit \
        pb_v5_attention_projection_right2_slr2]
    set center_wrong 0
    foreach name {
        pb_v5_attention_projection_center_region2_cr_x0y5_x0y9
        pb_v5_attention_projection_center_region3_cr_x1y5_x1y9
        pb_v5_attention_projection_center_region1_logic_cr_x2y5_x4y9
        pb_v5_attention_projection_center_region1_cols4_5_dsp_cr_x3y5_x4y9
        pb_v5_attention_projection_center_region1_cols6_7_dsp_cr_x2y5_x3y9
        pb_v5_attention_projection_owner_cr_x2y5_x4y9
        pb_v5_attention_projection_owner_region2_weight_cr_x2y5_x4y6
        pb_v5_attention_projection_center_region0_frontend_cr_x4y5_x5y9
        pb_v5_center_nonprojection_dsp_slr1
    } {
        incr center_wrong [record_wrong $audit $name]
    }
    set gate0_wrong [record_wrong $audit pb_v5_meta_gate_slr0]
    set gate2_wrong [record_wrong $audit pb_v5_meta_gate_slr2]
    set down0_wrong [record_wrong $audit pb_v5_meta_down0_slr1]
    set down1_wrong [record_wrong $audit pb_v5_meta_down1_slr1]
    set attention_meta_wrong [record_wrong $audit pb_v5_attention_meta_slr2]
    set attention_island_wrong \
        [record_wrong $audit pb_v5_attention_row_kv_cache_slr0]
    set classified_wrong [expr {$branch0_wrong + $branch2_wrong +
        $lane0_wrong + $lane2_wrong + $center_wrong + $gate0_wrong +
        $gate2_wrong + $down0_wrong + $down1_wrong +
        $attention_meta_wrong + $attention_island_wrong}]
    set additional_wrong [expr {
        [dict get $audit placed_wrong] - $classified_wrong}]
    if {$additional_wrong < 0} {
        error "V5 fine19 wrong-SLR classification exceeds the full audit"
    }

    set global_audit [hap_v5_floorplan::physical_slr_audit_for_cells \
        [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]]
    set unplaced [dict get $global_audit direct_slr_empty]
    if {$unplaced != 0} {
        error "V5 fine19 global physical audit has unresolved primitives: $unplaced"
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
        additional_wrong $additional_wrong \
        soft_outside [dict get $audit soft_outside] \
        wrong_total [dict get $audit placed_wrong] \
        global_virtual_gnd [dict get $global_audit virtual_gnd] \
        global_virtual_vcc [dict get $global_audit virtual_vcc] \
        global_virtual_total [dict get $global_audit virtual_total] \
        global_physical_count [dict get $global_audit physical_count] \
        global_direct_slr_empty [dict get $global_audit direct_slr_empty] \
        global_is_placed_empty [dict get $global_audit is_placed_empty]]
}

proc hap_v5_fine19::physical_ok {metrics} {
    return [expr {[dict get $metrics unplaced] == 0 &&
        [dict get $metrics wrong_total] == 0 &&
        [dict get $metrics slr_dsp] eq {1862 1781 1810} &&
        [dict get $metrics slr_uram] eq {224 224 304}}]
}

proc hap_v5_fine19::write_discovery {fine_plan path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    puts $fp "contract_variant=[dict get $fine_plan contract_variant]"
    foreach key {projection_primitives frontend_primitives left_primitives \
            center_primitives right_primitives center_region0_primitives \
            center_region1_primitives center_region2_primitives \
            center_region3_primitives center_region3_floorplan_primitives \
            center_region1_logic_residual_primitives \
            center_region1_cols4_5_dsp_primitives \
            center_region1_cols6_7_dsp_primitives \
            center_region0_frontend_primitives owner_primitives \
            owner_floorplan_primitives owner_residual_primitives \
            owner_region2_weight_primitives region3_input_primitives \
            nonprojection_center_dsp} {
        set cells [dict get $fine_plan $key]
        puts $fp "$key=[llength $cells]"
        puts $fp "${key}_dsp48e2=[count_ref $cells DSP48E2]"
        puts $fp "${key}_uram288=[count_ref $cells URAM288]"
    }
    foreach key {projection_exact_cover region1_exact_cover \
            owner_exact_cover weight_owner_residency_ok} {
        puts $fp "$key=[dict get $fine_plan $key]"
    }
    puts $fp "optimizer_extra_count=[dict get $fine_plan optimizer_extra_count]"
    close $fp
}

proc hap_v5_fine19::write_audit {audit path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    foreach key {ok contract_variant require_placed pblock_count member_count \
            member_overlap optimizer_extra_count dsp_coverage uram_coverage \
            placed_wrong soft_pblock_count soft_outside} {
        puts $fp "$key=[dict get $audit $key]"
    }
    foreach name [lsort -dictionary [dict keys [dict get $audit records]]] {
        set record [dict get $audit records $name]
        foreach key {target soft range member_count dsp uram missing extra \
                placed_wrong direct_slr_empty physical_count virtual_gnd \
                virtual_vcc virtual_total is_placed_empty} {
            puts $fp "${name}_${key}=[dict get $record $key]"
        }
    }
    close $fp
}
