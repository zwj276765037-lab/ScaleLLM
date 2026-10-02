# Shared selectors and fail-closed physical audits for the registered
# cohort16 projection OOC harness. This file only defines procedures.

namespace eval hap_projection_ooc_floorplan {
    variable expected_part xcvu9p-flga2104-2L-e
    variable expected_top hap_projection_core16x16_w8_reuse_registered_ooc_harness
    variable dsp_signature_source P14_LEGACY
    variable expected_frontend_dsp 64
    variable expected_slr_dsp {272 1696 272}
    variable region2_signature_source P14_LEGACY
    variable region2_residual_lut_removal_limit 0
    variable region2_signature [dict create \
        total_primitives 68799 total_lut 33883 total_ff 32032 total_dsp 544 \
        lane_primitives 1675 lane_dsp 17 \
        rows0_3_primitives 26800 rows0_3_lut 13504 \
        rows0_3_ff 12112 rows0_3_dsp 272 \
        rows4_7_primitives 26800 rows4_7_lut 13504 \
        rows4_7_ff 12112 rows4_7_dsp 272 \
        residual_primitives 15199 residual_lut 6875 \
        residual_ff 7808 residual_dsp 0]
}

proc hap_projection_ooc_floorplan::configure_dsp_signature {
        frontend_dsp slr_dsp source} {
    variable dsp_signature_source
    variable expected_frontend_dsp
    variable expected_slr_dsp
    if {$source eq "" || $source eq "P14_LEGACY"} {
        error "fresh DSP signature requires non-legacy provenance"
    }
    if {![string is integer -strict $frontend_dsp] || $frontend_dsp <= 0} {
        error "frontend DSP signature is not a positive integer: $frontend_dsp"
    }
    if {[llength $slr_dsp] != 3} {
        error "SLR DSP signature must contain exactly three values"
    }
    foreach value $slr_dsp {
        if {![string is integer -strict $value] || $value < 0} {
            error "SLR DSP signature contains an invalid value: $value"
        }
    }
    if {[lindex $slr_dsp 0] != 272 || [lindex $slr_dsp 2] != 272 ||
        [lindex $slr_dsp 1] != 1632 + $frontend_dsp ||
        [expr {[lindex $slr_dsp 0] + [lindex $slr_dsp 1] +
            [lindex $slr_dsp 2]}] != 2176 + $frontend_dsp} {
        error "DSP signature changes the frozen array/frontend topology"
    }
    set expected_frontend_dsp $frontend_dsp
    set expected_slr_dsp $slr_dsp
    set dsp_signature_source $source
}

proc hap_projection_ooc_floorplan::get_dsp_signature_source {} {
    variable dsp_signature_source
    return $dsp_signature_source
}

proc hap_projection_ooc_floorplan::configure_region2_signature {
        signature source} {
    variable region2_signature
    variable region2_signature_source
    set required [list total_primitives total_lut total_ff total_dsp \
        lane_primitives lane_dsp rows0_3_primitives rows0_3_lut \
        rows0_3_ff rows0_3_dsp rows4_7_primitives rows4_7_lut \
        rows4_7_ff rows4_7_dsp residual_primitives residual_lut \
        residual_ff residual_dsp]
    if {$source eq "" || $source eq "P14_LEGACY"} {
        error "fresh region2 signature requires non-legacy provenance"
    }
    foreach key $required {
        if {![dict exists $signature $key]} {
            error "region2 signature is missing '$key'"
        }
        set value [dict get $signature $key]
        if {![string is integer -strict $value] || $value < 0} {
            error "region2 signature '$key' is not a nonnegative integer: $value"
        }
    }
    if {[dict size $signature] != [llength $required]} {
        error "region2 signature contains unexpected fields"
    }
    foreach suffix {primitives lut ff dsp} {
        set sum [expr {[dict get $signature rows0_3_$suffix] +
            [dict get $signature rows4_7_$suffix] +
            [dict get $signature residual_$suffix]}]
        if {$sum != [dict get $signature total_$suffix]} {
            error "region2 signature $suffix partition is not additive"
        }
    }
    if {[dict get $signature rows0_3_dsp] != 272 ||
        [dict get $signature rows4_7_dsp] != 272 ||
        [dict get $signature residual_dsp] != 0 ||
        [dict get $signature total_dsp] != 544 ||
        [dict get $signature lane_dsp] != 17} {
        error "region2 signature changes the frozen DSP architecture"
    }
    set region2_signature $signature
    set region2_signature_source $source
}

proc hap_projection_ooc_floorplan::get_region2_signature_source {} {
    variable region2_signature_source
    return $region2_signature_source
}

proc hap_projection_ooc_floorplan::set_region2_residual_lut_removal_limit {
        limit} {
    variable region2_residual_lut_removal_limit
    if {![string is integer -strict $limit] || $limit < 0 || $limit > 1} {
        error "region2 residual LUT removal limit must be 0 or 1"
    }
    set region2_residual_lut_removal_limit $limit
}

proc hap_projection_ooc_floorplan::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_projection_ooc_floorplan::primitive_descendants {root} {
    set root_name [get_property NAME $root]
    # Transformed DSP and LUTRAM macros expose both their pblockable MACRO
    # cell and non-pblockable INTERNAL implementation children.  Selecting
    # the non-INTERNAL primitive collection retains each physical macro once
    # and avoids silently ignored add_cells_to_pblock objects.
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && \
                 REF_NAME != GND && REF_NAME != VCC && \
                 NAME =~ ${root_name}/*"]]
}

proc hap_projection_ooc_floorplan::list_union {args} {
    set result {}
    foreach values $args {set result [concat $result $values]}
    return [lsort -dictionary -unique $result]
}

proc hap_projection_ooc_floorplan::list_subtract {left right} {
    array set excluded {}
    foreach item $right {set excluded($item) 1}
    set result {}
    foreach item $left {
        if {![info exists excluded($item)]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_projection_ooc_floorplan::list_intersection {left right} {
    array set included {}
    foreach item $right {set included($item) 1}
    set result {}
    foreach item $left {
        if {[info exists included($item)]} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_projection_ooc_floorplan::object_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -dictionary -unique [get_property NAME $objects]]
}

proc hap_projection_ooc_floorplan::count_ref {objects ref_name} {
    set count 0
    foreach object $objects {
        if {[get_property REF_NAME $object] eq $ref_name} {incr count}
    }
    return $count
}

proc hap_projection_ooc_floorplan::count_ref_glob {objects pattern} {
    set count 0
    foreach ref [get_property REF_NAME $objects] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_projection_ooc_floorplan::partition_region3_input_staging {
        owner_primitives center_region3_primitives {dut_name u_dut}} {
    set activation_source_count 0
    set zero_point_source_count 0
    set weight_ff_source_count 0
    set weight_lut_source_count 0
    set region0_activation_primitives {}
    set region0_zero_point_primitives {}
    set region0_weight_ff_primitives {}
    set region0_weight_lut_primitives {}
    set activation_primitives {}
    set zero_point_primitives {}
    set owner_region2_weight_ff_primitives {}
    set owner_region2_weight_lut_primitives {}
    set owner_weight_ff_primitives {}
    set owner_weight_lut_primitives {}

    set primitive_names [get_property NAME $owner_primitives]
    set primitive_refs [get_property REF_NAME $owner_primitives]
    foreach primitive $owner_primitives primitive_name $primitive_names \
            primitive_ref $primitive_refs {
        set prefix "${dut_name}/"
        if {[string first $prefix $primitive_name] != 0} {
            error "projection input staging primitive is outside DUT: dut=$dut_name cell=$primitive_name"
        }
        set relative [string range $primitive_name [string length $prefix] end]
        if {[regexp \
                {^group_stage_act_u8_region_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr activation_source_count
            if {$primitive_ref ne "FDRE"} {
                error "projection OOC activation staging primitive type mismatch: name=$primitive_name ref=$primitive_ref"
            }
            if {($index / 256) % 4 == 0} {
                lappend region0_activation_primitives $primitive
            }
            if {($index / 256) % 4 == 3} {
                lappend activation_primitives $primitive
            }
            continue
        }
        if {[regexp \
                {^group_stage_act_zero_point_region_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr zero_point_source_count
            if {$primitive_ref ne "FDRE"} {
                error "projection OOC zero-point staging primitive type mismatch: name=$primitive_name ref=$primitive_ref"
            }
            if {($index / 8) % 4 == 0} {
                lappend region0_zero_point_primitives $primitive
            }
            if {($index / 8) % 4 == 3} {
                lappend zero_point_primitives $primitive
            }
            continue
        }
        if {[regexp \
                {^group_stage_weight_s8_r_reg\[([0-9]+)\]$} \
                $relative -> index]} {
            incr weight_ff_source_count
            if {$primitive_ref ne "FDRE"} {
                error "projection OOC weight staging FF type mismatch: name=$primitive_name ref=$primitive_ref"
            }
            if {$index >= 512 && $index < 1024} {
                lappend region0_weight_ff_primitives $primitive
            }
            if {$index >= 2048 && $index < 3072} {
                lappend owner_region2_weight_ff_primitives $primitive
            }
            if {$index >= 3072 && $index < 3584} {
                lappend owner_weight_ff_primitives $primitive
            }
            continue
        }
        if {[regexp \
                {^group_stage_weight_s8_r\[([0-9]+)\]_i_1$} \
                $relative -> index]} {
            incr weight_lut_source_count
            if {$primitive_ref ne "LUT3"} {
                error "projection OOC weight staging LUT type mismatch: name=$primitive_name ref=$primitive_ref"
            }
            if {$index >= 512 && $index < 1024} {
                lappend region0_weight_lut_primitives $primitive
            }
            if {$index >= 2048 && $index < 3072} {
                lappend owner_region2_weight_lut_primitives $primitive
            }
            if {$index >= 3072 && $index < 3584} {
                lappend owner_weight_lut_primitives $primitive
            }
        }
    }

    foreach {label actual expected} [list \
            activation_source $activation_source_count 8192 \
            zero_point_source $zero_point_source_count 256 \
            weight_ff_source $weight_ff_source_count 4096 \
            weight_lut_source $weight_lut_source_count 4096] {
        if {$actual != $expected} {
            error "projection OOC region3 input staging source mismatch: label=$label expected=$expected actual=$actual"
        }
    }

    set region0_activation_primitives \
        [lsort -dictionary -unique $region0_activation_primitives]
    set region0_zero_point_primitives \
        [lsort -dictionary -unique $region0_zero_point_primitives]
    set region0_weight_ff_primitives \
        [lsort -dictionary -unique $region0_weight_ff_primitives]
    set region0_weight_lut_primitives \
        [lsort -dictionary -unique $region0_weight_lut_primitives]
    set activation_primitives \
        [lsort -dictionary -unique $activation_primitives]
    set zero_point_primitives \
        [lsort -dictionary -unique $zero_point_primitives]
    set owner_region2_weight_ff_primitives \
        [lsort -dictionary -unique $owner_region2_weight_ff_primitives]
    set owner_region2_weight_lut_primitives \
        [lsort -dictionary -unique $owner_region2_weight_lut_primitives]
    set owner_weight_ff_primitives \
        [lsort -dictionary -unique $owner_weight_ff_primitives]
    set owner_weight_lut_primitives \
        [lsort -dictionary -unique $owner_weight_lut_primitives]
    require_count region0_input_activation_primitives \
        $region0_activation_primitives 2048
    require_count region0_input_zero_point_primitives \
        $region0_zero_point_primitives 64
    require_count region0_input_weight_ff_primitives \
        $region0_weight_ff_primitives 512
    require_count region0_input_weight_lut_primitives \
        $region0_weight_lut_primitives 512
    require_count region3_input_activation_primitives \
        $activation_primitives 2048
    require_count region3_input_zero_point_primitives \
        $zero_point_primitives 64
    require_count owner_region2_weight_ff_primitives \
        $owner_region2_weight_ff_primitives 1024
    require_count owner_region2_weight_lut_primitives \
        $owner_region2_weight_lut_primitives 1024
    require_count region3_owner_weight_ff_primitives \
        $owner_weight_ff_primitives 512
    require_count region3_owner_weight_lut_primitives \
        $owner_weight_lut_primitives 512

    # Region3 weight staging remains owner-resident. Empty Region3-localized
    # weight collections stay explicit while Region0's exact consumer slice
    # is moved with its activation and zero-point staging.
    set region0_weight_primitives [list_union \
        $region0_weight_ff_primitives $region0_weight_lut_primitives]
    set region0_input_primitives [list_union \
        $region0_activation_primitives $region0_zero_point_primitives \
        $region0_weight_primitives]
    if {[llength $region0_input_primitives] != 3136 ||
        [count_ref $region0_input_primitives FDRE] != 2624 ||
        [count_ref $region0_input_primitives LUT3] != 512 ||
        [count_ref $region0_input_primitives DSP48E2] != 0} {
        error "projection OOC region0 input staging identity mismatch"
    }

    set weight_ff_primitives {}
    set weight_lut_primitives {}
    set weight_primitives {}
    set owner_region2_weight_primitives [list_union \
        $owner_region2_weight_ff_primitives \
        $owner_region2_weight_lut_primitives]
    set owner_weight_primitives [list_union $owner_weight_ff_primitives \
        $owner_weight_lut_primitives]
    set region3_input_primitives [list_union $activation_primitives \
        $zero_point_primitives]
    if {[llength $region3_input_primitives] != 2112 ||
        [count_ref $region3_input_primitives FDRE] != 2112 ||
        [count_ref $region3_input_primitives LUT3] != 0 ||
        [count_ref $region3_input_primitives DSP48E2] != 0} {
        error "projection OOC region3 input staging identity mismatch"
    }
    if {[llength [list_intersection $region3_input_primitives \
            $center_region3_primitives]] != 0} {
        error "projection OOC region3 input staging overlaps logical region3"
    }

    set localized_input_primitives [list_union \
        $region0_input_primitives $region3_input_primitives]
    if {[llength [list_intersection $region0_input_primitives \
            $region3_input_primitives]] != 0} {
        error "projection OOC region0/region3 input staging overlap"
    }
    set owner_floorplan_primitives [list_subtract $owner_primitives \
        $localized_input_primitives]
    set owner_residual_floorplan_primitives [list_subtract \
        $owner_floorplan_primitives $owner_region2_weight_primitives]
    set center_region3_floorplan_primitives [list_union \
        $center_region3_primitives $region3_input_primitives]
    if {[llength [list_intersection $owner_floorplan_primitives \
            $localized_input_primitives]] != 0 ||
        [object_names [list_union $owner_floorplan_primitives \
            $localized_input_primitives]] ne [object_names $owner_primitives]} {
        error "projection OOC owner/local input floorplan partition mismatch"
    }
    if {[llength [list_intersection $owner_residual_floorplan_primitives \
            $owner_region2_weight_primitives]] != 0 ||
        [object_names [list_union $owner_residual_floorplan_primitives \
            $owner_region2_weight_primitives]] ne \
            [object_names $owner_floorplan_primitives]} {
        error "projection OOC owner region2 weight anchor partition mismatch"
    }
    if {[llength [list_intersection $owner_weight_primitives \
            $region3_input_primitives]] != 0 ||
        [object_names [list_intersection $owner_weight_primitives \
            $owner_floorplan_primitives]] ne \
            [object_names $owner_weight_primitives]} {
        error "projection OOC region3 weight staging is not owner-resident"
    }

    return [dict create \
        region0_activation_primitives $region0_activation_primitives \
        region0_zero_point_primitives $region0_zero_point_primitives \
        region0_weight_ff_primitives $region0_weight_ff_primitives \
        region0_weight_lut_primitives $region0_weight_lut_primitives \
        region0_weight_primitives $region0_weight_primitives \
        region0_input_primitives $region0_input_primitives \
        activation_primitives $activation_primitives \
        zero_point_primitives $zero_point_primitives \
        weight_ff_primitives $weight_ff_primitives \
        weight_lut_primitives $weight_lut_primitives \
        weight_primitives $weight_primitives \
        owner_region2_weight_ff_primitives \
            $owner_region2_weight_ff_primitives \
        owner_region2_weight_lut_primitives \
            $owner_region2_weight_lut_primitives \
        owner_region2_weight_primitives $owner_region2_weight_primitives \
        owner_weight_ff_primitives $owner_weight_ff_primitives \
        owner_weight_lut_primitives $owner_weight_lut_primitives \
        owner_weight_primitives $owner_weight_primitives \
        region3_input_primitives $region3_input_primitives \
        owner_floorplan_primitives $owner_floorplan_primitives \
        owner_residual_floorplan_primitives \
            $owner_residual_floorplan_primitives \
        center_region3_floorplan_primitives \
            $center_region3_floorplan_primitives exact_cover 1 \
        owner_region0_input_exact_cover 1 \
        weight_owner_residency_ok 1 \
        owner_region2_weight_exact_cover 1]
}

proc hap_projection_ooc_floorplan::region3_input_localization_ok {plan} {
    set primitives [dict get $plan region3_input_primitives]
    return [expr {
        [llength $primitives] == 2112 &&
        [count_ref $primitives FDRE] == 2112 &&
        [count_ref $primitives LUT3] == 0 &&
        [count_ref $primitives DSP48E2] == 0 &&
        [llength [dict get $plan \
            region3_input_activation_primitives]] == 2048 &&
        [llength [dict get $plan \
            region3_input_zero_point_primitives]] == 64 &&
        [llength [dict get $plan \
            region3_input_weight_ff_primitives]] == 0 &&
        [llength [dict get $plan \
            region3_input_weight_lut_primitives]] == 0 &&
        [llength [dict get $plan \
            region3_owner_weight_ff_primitives]] == 512 &&
        [llength [dict get $plan \
            region3_owner_weight_lut_primitives]] == 512 &&
        [dict get $plan owner_region3_input_exact_cover] == 1 &&
        [dict get $plan region3_weight_owner_residency_ok] == 1}]
}

proc hap_projection_ooc_floorplan::region0_input_localization_ok {plan} {
    set primitives [dict get $plan region0_input_primitives]
    return [expr {
        [llength $primitives] == 3136 &&
        [count_ref $primitives FDRE] == 2624 &&
        [count_ref $primitives LUT3] == 512 &&
        [count_ref $primitives DSP48E2] == 0 &&
        [llength [dict get $plan \
            region0_input_activation_primitives]] == 2048 &&
        [llength [dict get $plan \
            region0_input_zero_point_primitives]] == 64 &&
        [llength [dict get $plan \
            region0_input_weight_ff_primitives]] == 512 &&
        [llength [dict get $plan \
            region0_input_weight_lut_primitives]] == 512 &&
        [llength [dict get $plan \
            region0_input_weight_primitives]] == 1024 &&
        [dict get $plan owner_region0_input_exact_cover] == 1}]
}

proc hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok {plan} {
    set primitives [dict get $plan owner_region2_weight_primitives]
    return [expr {
        [llength $primitives] == 2048 &&
        [count_ref $primitives FDRE] == 1024 &&
        [count_ref $primitives LUT3] == 1024 &&
        [count_ref $primitives DSP48E2] == 0 &&
        [llength [dict get $plan \
            owner_region2_weight_ff_primitives]] == 1024 &&
        [llength [dict get $plan \
            owner_region2_weight_lut_primitives]] == 1024 &&
        [dict get $plan owner_region2_weight_exact_cover] == 1}]
}

proc hap_projection_ooc_floorplan::partition_region1_lanes {
        region1_root region1_root_primitives region1_primitives} {
    set root_name [get_property NAME $region1_root]
    set root_prefix "${root_name}/"
    set lane_roots [lsort -dictionary -unique [get_cells -quiet \
        -hierarchical -filter \
        "NAME =~ ${root_name}/* && \
         (REF_NAME == hap_a8w8_group32_lane_s42 || \
          ORIG_REF_NAME == hap_a8w8_group32_lane_s42)"]]
    require_count center_region1_lane_roots $lane_roots 32

    set cols4_5_lane_roots {}
    set cols6_7_lane_roots {}
    set lane_half_by_name [dict create]
    set lane_primitive_counts [dict create]
    set lane_dsp_counts [dict create]
    foreach lane_root $lane_roots {
        set lane_name [get_property NAME $lane_root]
        if {[string first $root_prefix $lane_name] != 0} {
            error "projection OOC region1 lane is outside its root: $lane_name"
        }
        set relative [string range $lane_name [string length $root_prefix] end]
        if {![regexp \
                {^g_row\[([0-7])\]\.g_col\[([0-3])\]\.u_lane$} \
                $relative -> row local_col]} {
            error "projection OOC unexpected region1 lane name: $lane_name"
        }
        if {[dict exists $lane_half_by_name $lane_name]} {
            error "projection OOC duplicate region1 lane root: $lane_name"
        }
        if {$local_col <= 1} {
            set half cols4_5
            lappend cols4_5_lane_roots $lane_root
        } else {
            set half cols6_7
            lappend cols6_7_lane_roots $lane_root
        }
        dict set lane_half_by_name $lane_name $half
        dict set lane_primitive_counts $lane_name 0
        dict set lane_dsp_counts $lane_name 0
    }
    require_count center_region1_cols4_5_lane_roots \
        $cols4_5_lane_roots 16
    require_count center_region1_cols6_7_lane_roots \
        $cols6_7_lane_roots 16

    # Classify the materialized region1 primitive collection once. Re-running
    # primitive_descendants for all 32 lane roots causes 32 hierarchy scans.
    set cols4_5_primitives {}
    set cols6_7_primitives {}
    set cols4_5_dsp_primitives {}
    set cols6_7_dsp_primitives {}
    set primitive_names [get_property NAME $region1_root_primitives]
    set primitive_refs [get_property REF_NAME $region1_root_primitives]
    foreach primitive $region1_root_primitives primitive_name $primitive_names \
            primitive_ref $primitive_refs {
        if {[string first $root_prefix $primitive_name] != 0} {
            error "projection OOC region1 primitive is outside its root: $primitive_name"
        }
        set relative [string range $primitive_name \
            [string length $root_prefix] end]
        if {![regexp \
                {^(g_row\[[0-7]\]\.g_col\[[0-3]\]\.u_lane)(/|$)} \
                $relative -> lane_relative boundary]} {
            continue
        }
        set lane_name "${root_prefix}${lane_relative}"
        if {![dict exists $lane_half_by_name $lane_name]} {
            error "projection OOC region1 primitive maps to unknown lane: $primitive_name"
        }
        set half [dict get $lane_half_by_name $lane_name]
        if {$half eq "cols4_5"} {
            lappend cols4_5_primitives $primitive
            if {$primitive_ref eq "DSP48E2"} {
                lappend cols4_5_dsp_primitives $primitive
            }
        } else {
            lappend cols6_7_primitives $primitive
            if {$primitive_ref eq "DSP48E2"} {
                lappend cols6_7_dsp_primitives $primitive
            }
        }
        dict incr lane_primitive_counts $lane_name
        if {$primitive_ref eq "DSP48E2"} {
            dict incr lane_dsp_counts $lane_name
        }
    }
    set cols4_5_primitives [lsort -dictionary -unique $cols4_5_primitives]
    set cols6_7_primitives [lsort -dictionary -unique $cols6_7_primitives]
    set cols4_5_dsp_primitives \
        [lsort -dictionary -unique $cols4_5_dsp_primitives]
    set cols6_7_dsp_primitives \
        [lsort -dictionary -unique $cols6_7_dsp_primitives]
    foreach lane_name [dict keys $lane_half_by_name] {
        if {[dict get $lane_primitive_counts $lane_name] == 0 ||
            [dict get $lane_dsp_counts $lane_name] != 17} {
            error "projection OOC region1 lane signature mismatch: lane=$lane_name primitives=[dict get $lane_primitive_counts $lane_name] dsp=[dict get $lane_dsp_counts $lane_name]"
        }
    }
    if {[llength $cols4_5_primitives] == 0 ||
        [llength $cols6_7_primitives] == 0 ||
        [count_ref $cols4_5_primitives DSP48E2] != 272 ||
        [count_ref $cols6_7_primitives DSP48E2] != 272 ||
        [llength $cols4_5_dsp_primitives] != 272 ||
        [llength $cols6_7_dsp_primitives] != 272} {
        error "projection OOC region1 lane-half signature mismatch"
    }
    if {[llength [list_intersection $cols4_5_primitives \
            $cols6_7_primitives]] != 0} {
        error "projection OOC region1 lane halves overlap"
    }

    set lane_primitives [list_union $cols4_5_primitives \
        $cols6_7_primitives]
    set residual_primitives [list_subtract $region1_primitives \
        $lane_primitives]
    if {[llength $residual_primitives] == 0 ||
        [count_ref $residual_primitives DSP48E2] != 0} {
        error "projection OOC region1 residual signature mismatch"
    }
    set covered [list_union $lane_primitives $residual_primitives]
    if {[object_names $covered] ne [object_names $region1_primitives]} {
        error "projection OOC region1 bisect does not exactly cover region1"
    }
    foreach {label lhs rhs} [list cols4_5_cols6_7 $cols4_5_primitives \
            $cols6_7_primitives cols4_5_residual $cols4_5_primitives \
            $residual_primitives cols6_7_residual $cols6_7_primitives \
            $residual_primitives] {
        if {[llength [list_intersection $lhs $rhs]] != 0} {
            error "projection OOC region1 partition overlap: $label"
        }
    }

    set striped_dsp_primitives [list_union $cols4_5_dsp_primitives \
        $cols6_7_dsp_primitives]
    set logic_residual_primitives [list_subtract $region1_primitives \
        $striped_dsp_primitives]
    if {[llength $logic_residual_primitives] == 0 ||
        [count_ref $logic_residual_primitives DSP48E2] != 0} {
        error "projection OOC region1 DSP-stripe logic complement mismatch"
    }
    foreach {label lhs rhs} [list dsp4_5_dsp6_7 \
            $cols4_5_dsp_primitives $cols6_7_dsp_primitives \
            dsp4_5_logic $cols4_5_dsp_primitives \
            $logic_residual_primitives dsp6_7_logic \
            $cols6_7_dsp_primitives $logic_residual_primitives] {
        if {[llength [list_intersection $lhs $rhs]] != 0} {
            error "projection OOC region1 DSP-stripe overlap: $label"
        }
    }
    set stripe_covered [list_union $striped_dsp_primitives \
        $logic_residual_primitives]
    if {[object_names $stripe_covered] ne \
        [object_names $region1_primitives]} {
        error "projection OOC region1 DSP stripes do not exactly cover region1"
    }

    return [dict create lane_roots $lane_roots \
        cols4_5_lane_roots $cols4_5_lane_roots \
        cols6_7_lane_roots $cols6_7_lane_roots \
        cols4_5_primitives $cols4_5_primitives \
        cols6_7_primitives $cols6_7_primitives \
        residual_primitives $residual_primitives exact_cover 1 \
        cols4_5_dsp_primitives $cols4_5_dsp_primitives \
        cols6_7_dsp_primitives $cols6_7_dsp_primitives \
        logic_residual_primitives $logic_residual_primitives \
        dsp_stripe_exact_cover 1]
}

proc hap_projection_ooc_floorplan::partition_region2_rows {
        region2_root region2_primitives} {
    variable region2_signature
    variable region2_signature_source
    variable region2_residual_lut_removal_limit
    set root_name [get_property NAME $region2_root]
    set root_prefix "${root_name}/"
    set lane_roots [lsort -dictionary -unique [get_cells -quiet \
        -hierarchical -filter \
        "NAME =~ ${root_name}/* && \
         (REF_NAME == hap_a8w8_group32_lane_s42 || \
          ORIG_REF_NAME == hap_a8w8_group32_lane_s42)"]]
    require_count center_region2_lane_roots $lane_roots 32

    set lane_group_by_name [dict create]
    set lane_primitive_counts [dict create]
    set lane_dsp_counts [dict create]
    set rows0_3_lane_roots {}
    set rows4_7_lane_roots {}
    foreach lane_root $lane_roots {
        set lane_name [get_property NAME $lane_root]
        if {[string first $root_prefix $lane_name] != 0} {
            error "projection OOC region2 lane is outside its root: $lane_name"
        }
        set relative [string range $lane_name [string length $root_prefix] end]
        if {![regexp \
                {^g_row\[([0-7])\]\.g_col\[([0-3])\]\.u_lane$} \
                $relative -> row local_col]} {
            error "projection OOC unexpected region2 lane name: $lane_name"
        }
        set group [expr {$row < 4 ? "rows0_3" : "rows4_7"}]
        if {$group eq "rows0_3"} {
            lappend rows0_3_lane_roots $lane_root
        } else {
            lappend rows4_7_lane_roots $lane_root
        }
        dict set lane_group_by_name $lane_name $group
        dict set lane_primitive_counts $lane_name 0
        dict set lane_dsp_counts $lane_name 0
    }
    require_count center_region2_rows0_3_lane_roots \
        $rows0_3_lane_roots 16
    require_count center_region2_rows4_7_lane_roots \
        $rows4_7_lane_roots 16

    set rows0_3_primitives {}
    set rows4_7_primitives {}
    set primitive_names [get_property NAME $region2_primitives]
    set primitive_refs [get_property REF_NAME $region2_primitives]
    foreach primitive $region2_primitives primitive_name $primitive_names \
            primitive_ref $primitive_refs {
        if {[string first $root_prefix $primitive_name] != 0} {
            error "projection OOC region2 primitive is outside its root: $primitive_name"
        }
        set relative [string range $primitive_name \
            [string length $root_prefix] end]
        if {![regexp \
                {^(g_row\[[0-7]\]\.g_col\[[0-3]\]\.u_lane)(/|$)} \
                $relative -> lane_relative boundary]} {
            continue
        }
        set lane_name "${root_prefix}${lane_relative}"
        if {![dict exists $lane_group_by_name $lane_name]} {
            error "projection OOC region2 primitive maps to unknown lane: $primitive_name"
        }
        set group [dict get $lane_group_by_name $lane_name]
        if {$group eq "rows0_3"} {
            lappend rows0_3_primitives $primitive
        } else {
            lappend rows4_7_primitives $primitive
        }
        dict incr lane_primitive_counts $lane_name
        if {$primitive_ref eq "DSP48E2"} {
            dict incr lane_dsp_counts $lane_name
        }
    }
    set rows0_3_primitives [lsort -dictionary -unique $rows0_3_primitives]
    set rows4_7_primitives [lsort -dictionary -unique $rows4_7_primitives]
    foreach lane_name [dict keys $lane_group_by_name] {
        if {[dict get $lane_primitive_counts $lane_name] !=
                [dict get $region2_signature lane_primitives] ||
            [dict get $lane_dsp_counts $lane_name] !=
                [dict get $region2_signature lane_dsp]} {
            error "projection OOC region2 lane signature mismatch: lane=$lane_name primitives=[dict get $lane_primitive_counts $lane_name] dsp=[dict get $lane_dsp_counts $lane_name]"
        }
    }

    set lane_primitives [list_union $rows0_3_primitives \
        $rows4_7_primitives]
    set residual_primitives [list_subtract $region2_primitives \
        $lane_primitives]
    set residual_removed_lut 0
    foreach {label cells} [list rows0_3 $rows0_3_primitives \
            rows4_7 $rows4_7_primitives residual $residual_primitives] {
        set expected_primitives [dict get $region2_signature \
            ${label}_primitives]
        set expected_lut [dict get $region2_signature ${label}_lut]
        set expected_ff [dict get $region2_signature ${label}_ff]
        set expected_dsp [dict get $region2_signature ${label}_dsp]
        set actual_primitives [llength $cells]
        set actual_lut [count_ref_glob $cells LUT*]
        set actual_ff [count_ref_glob $cells FD*]
        set actual_dsp [count_ref $cells DSP48E2]
        set primitive_delta [expr {$expected_primitives - $actual_primitives}]
        set lut_delta [expr {$expected_lut - $actual_lut}]
        set signature_ok [expr {
            $actual_ff == $expected_ff && $actual_dsp == $expected_dsp}]
        if {$label eq "residual"} {
            set signature_ok [expr {$signature_ok &&
                $primitive_delta == $lut_delta && $primitive_delta >= 0 &&
                $primitive_delta <= $region2_residual_lut_removal_limit}]
            set residual_removed_lut $primitive_delta
        } else {
            set signature_ok [expr {$signature_ok &&
                $primitive_delta == 0 && $lut_delta == 0}]
        }
        if {!$signature_ok} {
            error "projection OOC region2 row signature mismatch: group=$label primitives=[llength $cells] LUT=[count_ref_glob $cells LUT*] FF=[count_ref_glob $cells FD*] DSP=[count_ref $cells DSP48E2]"
        }
    }
    foreach {label lhs rhs} [list rows0_3_rows4_7 $rows0_3_primitives \
            $rows4_7_primitives rows0_3_residual $rows0_3_primitives \
            $residual_primitives rows4_7_residual $rows4_7_primitives \
            $residual_primitives] {
        if {[llength [list_intersection $lhs $rhs]] != 0} {
            error "projection OOC region2 row partition overlap: $label"
        }
    }
    set covered [list_union $lane_primitives $residual_primitives]
    if {[object_names $covered] ne [object_names $region2_primitives]} {
        error "projection OOC region2 row partition is not an exact cover"
    }
    set total_primitive_delta [expr {
        [dict get $region2_signature total_primitives] -
        [llength $region2_primitives]}]
    set total_lut_delta [expr {
        [dict get $region2_signature total_lut] -
        [count_ref_glob $region2_primitives LUT*]}]
    if {$total_primitive_delta != $residual_removed_lut ||
        $total_lut_delta != $residual_removed_lut ||
        [count_ref_glob $region2_primitives FD*] !=
            [dict get $region2_signature total_ff] ||
        [count_ref $region2_primitives DSP48E2] !=
            [dict get $region2_signature total_dsp]} {
        error "projection OOC region2 total signature mismatch"
    }
    return [dict create lane_roots $lane_roots \
        rows0_3_lane_roots $rows0_3_lane_roots \
        rows4_7_lane_roots $rows4_7_lane_roots \
        rows0_3_primitives $rows0_3_primitives \
        rows4_7_primitives $rows4_7_primitives \
        residual_primitives $residual_primitives exact_cover 1 \
        residual_removed_lut $residual_removed_lut \
        signature_source $region2_signature_source]
}

proc hap_projection_ooc_floorplan::discover {{dut_path u_dut} \
        {allow_empty_center_wrapper 0}} {
    variable expected_part
    variable expected_frontend_dsp
    set actual_part [get_property PART [current_project]]
    if {$actual_part ne $expected_part} {
        error "projection OOC floorplan part mismatch: $actual_part"
    }

    set dut_roots [get_cells -quiet $dut_path]
    set frontend_roots [get_cells -quiet ${dut_path}/u_frontend]
    set array_roots [get_cells -quiet ${dut_path}/u_array]
    set left_roots [get_cells -quiet ${dut_path}/u_array/u_left2]
    set center_roots [get_cells -quiet ${dut_path}/u_array/u_center12]
    set center_region0_roots [get_cells -quiet \
        ${dut_path}/u_array/u_center12/u_region0_cols2_3]
    set center_region1_roots [get_cells -quiet \
        ${dut_path}/u_array/u_center12/u_region1_cols4_7]
    set center_region2_roots [get_cells -quiet \
        ${dut_path}/u_array/u_center12/u_region2_cols8_11]
    set center_region3_roots [get_cells -quiet \
        ${dut_path}/u_array/u_center12/u_region3_cols12_13]
    set right_roots [get_cells -quiet ${dut_path}/u_array/u_right2]
    require_count projection_dut_root $dut_roots 1
    require_count projection_frontend_root $frontend_roots 1
    require_count projection_array_root $array_roots 1
    require_count projection_left2_root $left_roots 1
    require_count projection_center12_root $center_roots 1
    require_count projection_center_region0_root $center_region0_roots 1
    require_count projection_center_region1_root $center_region1_roots 1
    require_count projection_center_region2_root $center_region2_roots 1
    require_count projection_center_region3_root $center_region3_roots 1
    require_count projection_right2_root $right_roots 1

    set dut_primitives [primitive_descendants [lindex $dut_roots 0]]
    set frontend_primitives \
        [primitive_descendants [lindex $frontend_roots 0]]
    set left_primitives [primitive_descendants [lindex $left_roots 0]]
    set center_primitives [primitive_descendants [lindex $center_roots 0]]
    set center_region0_root_primitives \
        [primitive_descendants [lindex $center_region0_roots 0]]
    set center_region1_root_primitives \
        [primitive_descendants [lindex $center_region1_roots 0]]
    set center_region2_root_primitives \
        [primitive_descendants [lindex $center_region2_roots 0]]
    set center_region3_root_primitives \
        [primitive_descendants [lindex $center_region3_roots 0]]
    set center_region_root_primitives [list_union \
        $center_region0_root_primitives $center_region1_root_primitives \
        $center_region2_root_primitives $center_region3_root_primitives]
    set center_wrapper_primitives \
        [list_subtract $center_primitives $center_region_root_primitives]
    # The center12 wrapper takes region1's control outputs as authoritative.
    # Keep its small residual logic with that region so the four stripe
    # collections form an exact partition of center12.
    set center_region0_primitives $center_region0_root_primitives
    set center_region1_primitives [list_union \
        $center_region1_root_primitives $center_wrapper_primitives]
    set center_region2_primitives $center_region2_root_primitives
    set center_region3_primitives $center_region3_root_primitives
    set right_primitives [primitive_descendants [lindex $right_roots 0]]
    set shard_primitives [list_union $left_primitives $center_primitives \
        $right_primitives]
    set owner_and_frontend_primitives \
        [list_subtract $dut_primitives $shard_primitives]
    if {[object_names [list_intersection $owner_and_frontend_primitives \
            $frontend_primitives]] ne [object_names $frontend_primitives]} {
        error "projection OOC frontend is not an owner partition subset"
    }
    set owner_primitives [list_subtract $owner_and_frontend_primitives \
        $frontend_primitives]
       set region3_input_partition [partition_region3_input_staging \
        $owner_primitives $center_region3_primitives \
        [get_property NAME [lindex $dut_roots 0]]]
    set region0_input_activation_primitives \
        [dict get $region3_input_partition region0_activation_primitives]
    set region0_input_zero_point_primitives \
        [dict get $region3_input_partition region0_zero_point_primitives]
    set region0_input_weight_ff_primitives \
        [dict get $region3_input_partition region0_weight_ff_primitives]
    set region0_input_weight_lut_primitives \
        [dict get $region3_input_partition region0_weight_lut_primitives]
    set region0_input_weight_primitives \
        [dict get $region3_input_partition region0_weight_primitives]
    set region0_input_primitives \
        [dict get $region3_input_partition region0_input_primitives]
    set region3_input_activation_primitives \
        [dict get $region3_input_partition activation_primitives]
    set region3_input_zero_point_primitives \
        [dict get $region3_input_partition zero_point_primitives]
    set region3_input_weight_ff_primitives \
        [dict get $region3_input_partition weight_ff_primitives]
    set region3_input_weight_lut_primitives \
        [dict get $region3_input_partition weight_lut_primitives]
    set region3_input_weight_primitives \
        [dict get $region3_input_partition weight_primitives]
    set owner_region2_weight_ff_primitives \
        [dict get $region3_input_partition \
            owner_region2_weight_ff_primitives]
    set owner_region2_weight_lut_primitives \
        [dict get $region3_input_partition \
            owner_region2_weight_lut_primitives]
    set owner_region2_weight_primitives \
        [dict get $region3_input_partition owner_region2_weight_primitives]
    set region3_owner_weight_ff_primitives \
        [dict get $region3_input_partition owner_weight_ff_primitives]
    set region3_owner_weight_lut_primitives \
        [dict get $region3_input_partition owner_weight_lut_primitives]
    set region3_owner_weight_primitives \
        [dict get $region3_input_partition owner_weight_primitives]
    set region3_input_primitives \
        [dict get $region3_input_partition region3_input_primitives]
    set owner_floorplan_primitives \
        [dict get $region3_input_partition owner_floorplan_primitives]
    set owner_residual_floorplan_primitives \
        [dict get $region3_input_partition \
            owner_residual_floorplan_primitives]
    set center_region3_floorplan_primitives \
        [dict get $region3_input_partition \
            center_region3_floorplan_primitives]
    set center_region0_frontend_primitives [list_union \
        $center_region0_primitives $frontend_primitives \
        $region0_input_primitives]
    set region1_partition [partition_region1_lanes \
        [lindex $center_region1_roots 0] $center_region1_root_primitives \
        $center_region1_primitives]
    set center_region1_cols4_5_primitives \
        [dict get $region1_partition cols4_5_primitives]
    set center_region1_cols6_7_primitives \
        [dict get $region1_partition cols6_7_primitives]
    set center_region1_residual_primitives \
        [dict get $region1_partition residual_primitives]
    set center_region1_cols4_5_dsp_primitives \
        [dict get $region1_partition cols4_5_dsp_primitives]
    set center_region1_cols6_7_dsp_primitives \
        [dict get $region1_partition cols6_7_dsp_primitives]
    set center_region1_logic_residual_primitives \
        [dict get $region1_partition logic_residual_primitives]
    set region2_partition [partition_region2_rows \
        [lindex $center_region2_roots 0] $center_region2_primitives]
    set center_region2_rows0_3_primitives \
        [dict get $region2_partition rows0_3_primitives]
    set center_region2_rows4_7_primitives \
        [dict get $region2_partition rows4_7_primitives]
    set center_region2_residual_primitives \
        [dict get $region2_partition residual_primitives]

    foreach {label values} [list left $left_primitives \
            frontend $frontend_primitives center $center_primitives \
            center_region0 \
            $center_region0_primitives center_region1 \
            $center_region1_primitives center_region2 \
            $center_region2_primitives center_region3 \
            $center_region3_primitives right $right_primitives \
            owner $owner_primitives center_region0_frontend \
            $center_region0_frontend_primitives \
            region0_input_activation $region0_input_activation_primitives \
            region0_input_zero_point $region0_input_zero_point_primitives \
            region0_input_weight_ff $region0_input_weight_ff_primitives \
            region0_input_weight_lut $region0_input_weight_lut_primitives \
            region0_input_weight $region0_input_weight_primitives \
            region0_input $region0_input_primitives \
            center_region1_cols4_5 \
            $center_region1_cols4_5_primitives center_region1_cols6_7 \
            $center_region1_cols6_7_primitives center_region1_residual \
            $center_region1_residual_primitives \
            center_region1_cols4_5_dsp \
            $center_region1_cols4_5_dsp_primitives \
            center_region1_cols6_7_dsp \
            $center_region1_cols6_7_dsp_primitives \
            center_region1_logic_residual \
            $center_region1_logic_residual_primitives \
            center_region2_rows0_3 \
            $center_region2_rows0_3_primitives \
            center_region2_rows4_7 \
            $center_region2_rows4_7_primitives \
            center_region2_residual \
            $center_region2_residual_primitives \
            region3_input_activation \
            $region3_input_activation_primitives \
            region3_input_zero_point \
            $region3_input_zero_point_primitives \
            owner_region2_weight_ff \
            $owner_region2_weight_ff_primitives \
            owner_region2_weight_lut \
            $owner_region2_weight_lut_primitives \
            owner_region2_weight $owner_region2_weight_primitives \
            region3_owner_weight_ff \
            $region3_owner_weight_ff_primitives \
            region3_owner_weight_lut \
            $region3_owner_weight_lut_primitives \
            region3_owner_weight $region3_owner_weight_primitives \
            region3_input $region3_input_primitives \
            owner_floorplan $owner_floorplan_primitives \
            owner_residual_floorplan $owner_residual_floorplan_primitives \
            center_region3_floorplan \
            $center_region3_floorplan_primitives] {
        if {[llength $values] == 0} {
            error "projection OOC floorplan collection is empty: $label"
        }
    }
    # Full-production synthesis can absorb all pass-through center12 wrapper
    # primitives into its four child regions.  OOC runs retain the stricter
    # nonempty signature; production callers opt in only to this legal empty
    # complement while all child-region and exact-cover checks remain active.
    if {!$allow_empty_center_wrapper &&
        [llength $center_wrapper_primitives] == 0} {
        error "projection OOC floorplan collection is empty: center_wrapper"
    }
    foreach {label lhs rhs} [list left_center $left_primitives \
            $center_primitives left_right $left_primitives \
            $right_primitives center_right $center_primitives \
            $right_primitives owner_shards $owner_primitives \
            $shard_primitives frontend_shards $frontend_primitives \
            $shard_primitives owner_frontend $owner_primitives \
            $frontend_primitives] {
        if {[llength [list_intersection $lhs $rhs]] != 0} {
            error "projection OOC floorplan overlap: $label"
        }
    }
    set covered [list_union $owner_primitives $frontend_primitives \
        $shard_primitives]
    if {[object_names $covered] ne [object_names $dut_primitives]} {
        error "projection OOC floorplan does not exactly cover DUT primitives"
    }

    set center_regions [list $center_region0_primitives \
        $center_region1_primitives $center_region2_primitives \
        $center_region3_primitives]
    for {set lhs_index 0} {$lhs_index < [llength $center_regions]} \
            {incr lhs_index} {
        for {set rhs_index [expr {$lhs_index + 1}]} \
                {$rhs_index < [llength $center_regions]} {incr rhs_index} {
            if {[llength [list_intersection \
                    [lindex $center_regions $lhs_index] \
                    [lindex $center_regions $rhs_index]]] != 0} {
                error "projection OOC center region overlap: ${lhs_index}_${rhs_index}"
            }
        }
    }
    set covered_center [list_union {*}$center_regions]
    if {[object_names $covered_center] ne [object_names $center_primitives]} {
        error "projection OOC center regions do not exactly cover center12"
    }

    require_count left2_dsp_signature \
        [lsearch -all -inline -exact [get_property REF_NAME $left_primitives] \
            DSP48E2] 272
    require_count center12_dsp_signature \
        [lsearch -all -inline -exact [get_property REF_NAME $center_primitives] \
            DSP48E2] 1632
    foreach {label values expected} [list \
            center_region0 $center_region0_primitives 272 \
            center_region1 $center_region1_primitives 544 \
            center_region2 $center_region2_primitives 544 \
            center_region3 $center_region3_primitives 272] {
        if {[count_ref $values DSP48E2] != $expected} {
            error "projection OOC $label DSP signature mismatch: expected=$expected actual=[count_ref $values DSP48E2]"
        }
    }
    require_count right2_dsp_signature \
        [lsearch -all -inline -exact [get_property REF_NAME $right_primitives] \
            DSP48E2] 272
    require_count owner_dsp_signature \
        [lsearch -all -inline -exact [get_property REF_NAME $owner_primitives] \
            DSP48E2] 0
    require_count frontend_dsp_signature \
        [lsearch -all -inline -exact \
            [get_property REF_NAME $frontend_primitives] DSP48E2] \
        $expected_frontend_dsp
    if {[count_ref $center_region0_frontend_primitives DSP48E2] !=
            272 + $expected_frontend_dsp} {
        error "projection OOC region0/frontend DSP signature mismatch"
    }
    if {[count_ref $center_region1_cols4_5_dsp_primitives DSP48E2] != 272 ||
        [count_ref $center_region1_cols6_7_dsp_primitives DSP48E2] != 272 ||
        [count_ref $center_region1_logic_residual_primitives DSP48E2] != 0} {
        error "projection OOC region1 DSP-only stripe signature mismatch"
    }
    if {[count_ref $owner_primitives RAMB36E2] != 0 ||
        [count_ref $owner_primitives RAMB18E2] != 0 ||
        [count_ref $frontend_primitives RAMB36E2] != 31 ||
        [count_ref $frontend_primitives RAMB18E2] != 4 ||
        [count_ref $dut_primitives URAM288] != 0} {
        error "projection OOC frontend/owner BRAM/URAM signature mismatch"
    }

    return [dict create dut_primitives $dut_primitives \
        frontend_primitives $frontend_primitives \
        left_primitives $left_primitives \
        center_primitives $center_primitives \
        center_region0_primitives $center_region0_primitives \
        center_region1_primitives $center_region1_primitives \
        center_region2_primitives $center_region2_primitives \
        center_region3_primitives $center_region3_primitives \
        center_region3_floorplan_primitives \
            $center_region3_floorplan_primitives \
        center_region1_lane_roots [dict get $region1_partition lane_roots] \
        center_region1_cols4_5_lane_roots \
            [dict get $region1_partition cols4_5_lane_roots] \
        center_region1_cols6_7_lane_roots \
            [dict get $region1_partition cols6_7_lane_roots] \
        center_region1_cols4_5_primitives \
            $center_region1_cols4_5_primitives \
        center_region1_cols6_7_primitives \
            $center_region1_cols6_7_primitives \
        center_region1_residual_primitives \
            $center_region1_residual_primitives \
        center_region1_cols4_5_dsp_primitives \
            $center_region1_cols4_5_dsp_primitives \
        center_region1_cols6_7_dsp_primitives \
            $center_region1_cols6_7_dsp_primitives \
        center_region1_logic_residual_primitives \
            $center_region1_logic_residual_primitives \
        center_region2_lane_roots [dict get $region2_partition lane_roots] \
        center_region2_rows0_3_lane_roots \
            [dict get $region2_partition rows0_3_lane_roots] \
        center_region2_rows4_7_lane_roots \
            [dict get $region2_partition rows4_7_lane_roots] \
        center_region2_rows0_3_primitives \
            $center_region2_rows0_3_primitives \
        center_region2_rows4_7_primitives \
            $center_region2_rows4_7_primitives \
        center_region2_residual_primitives \
            $center_region2_residual_primitives \
        center_region2_residual_removed_lut \
            [dict get $region2_partition residual_removed_lut] \
        center_region2_row_exact_cover \
            [dict get $region2_partition exact_cover] \
        center_region1_bisect_exact_cover \
            [dict get $region1_partition exact_cover] \
        center_region1_dsp_stripe_exact_cover \
            [dict get $region1_partition dsp_stripe_exact_cover] \
        center_region0_frontend_primitives \
            $center_region0_frontend_primitives \
        region0_input_activation_primitives \
            $region0_input_activation_primitives \
        region0_input_zero_point_primitives \
            $region0_input_zero_point_primitives \
        region0_input_weight_ff_primitives \
            $region0_input_weight_ff_primitives \
        region0_input_weight_lut_primitives \
            $region0_input_weight_lut_primitives \
        region0_input_weight_primitives $region0_input_weight_primitives \
        region0_input_primitives $region0_input_primitives \
        owner_region0_input_exact_cover \
            [dict get $region3_input_partition \
                owner_region0_input_exact_cover] \
        center_wrapper_primitives $center_wrapper_primitives \
        right_primitives $right_primitives \
        owner_primitives $owner_primitives \
        owner_floorplan_primitives $owner_floorplan_primitives \
        owner_residual_floorplan_primitives \
            $owner_residual_floorplan_primitives \
        owner_region2_weight_ff_primitives \
            $owner_region2_weight_ff_primitives \
        owner_region2_weight_lut_primitives \
            $owner_region2_weight_lut_primitives \
        owner_region2_weight_primitives $owner_region2_weight_primitives \
        region3_input_activation_primitives \
            $region3_input_activation_primitives \
        region3_input_zero_point_primitives \
            $region3_input_zero_point_primitives \
        region3_input_weight_ff_primitives \
            $region3_input_weight_ff_primitives \
        region3_input_weight_lut_primitives \
            $region3_input_weight_lut_primitives \
        region3_input_weight_primitives $region3_input_weight_primitives \
        region3_owner_weight_ff_primitives \
            $region3_owner_weight_ff_primitives \
        region3_owner_weight_lut_primitives \
            $region3_owner_weight_lut_primitives \
        region3_owner_weight_primitives $region3_owner_weight_primitives \
        region3_input_primitives $region3_input_primitives \
        owner_region3_input_exact_cover \
            [dict get $region3_input_partition exact_cover] \
        owner_region2_weight_exact_cover \
            [dict get $region3_input_partition \
                owner_region2_weight_exact_cover] \
        region3_weight_owner_residency_ok \
            [dict get $region3_input_partition weight_owner_residency_ok]]
}

proc hap_projection_ooc_floorplan::specs {plan {name_prefix ""} \
        {region2_variant shared}} {
    set result [list [dict create \
        name ${name_prefix}pb_projection_left2_slr0 target 0 range SLR0 \
        key left_primitives cells [dict get $plan left_primitives]]]
    switch -- $region2_variant {
        shared {
            lappend result [dict create name \
                ${name_prefix}pb_projection_center_region2_shared_cr_x0y5_x1y9 \
                target 1 range CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
                key center_region2_primitives \
                cells [dict get $plan center_region2_primitives]]
        }
        rowsplit_y5_y6_y6_y8 {
            lappend result [dict create name \
                ${name_prefix}pb_projection_center_region2_rows0_3_cr_x0y5_x1y6 \
                target 1 range CLOCKREGION_X0Y5:CLOCKREGION_X1Y6 \
                key center_region2_rows0_3_primitives \
                cells [dict get $plan center_region2_rows0_3_primitives]]
            lappend result [dict create name \
                ${name_prefix}pb_projection_center_region2_rows4_7_cr_x0y6_x1y8 \
                target 1 range CLOCKREGION_X0Y6:CLOCKREGION_X1Y8 \
                key center_region2_rows4_7_primitives \
                cells [dict get $plan center_region2_rows4_7_primitives]]
            lappend result [dict create name \
                ${name_prefix}pb_projection_center_region2_residual_cr_x0y5_x1y9 \
                target 1 range CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
                key center_region2_residual_primitives \
                cells [dict get $plan center_region2_residual_primitives]]
        }
        default {
            error "projection OOC unsupported region2 variant: $region2_variant"
        }
    }
    foreach spec [list \
            [dict create name \
                ${name_prefix}pb_projection_center_region3_shared_cr_x0y5_x1y9 \
                target 1 range CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
                key center_region3_floorplan_primitives \
                cells [dict get $plan center_region3_floorplan_primitives]] \
            [dict create name \
                ${name_prefix}pb_projection_center_region1_logic_residual_cr_x2y5_x4y9 \
                target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
                key center_region1_logic_residual_primitives \
                cells [dict get $plan center_region1_logic_residual_primitives]] \
            [dict create name \
                ${name_prefix}pb_projection_center_region1_cols4_5_dsp_cr_x3y5_x4y9 \
                target 1 range CLOCKREGION_X3Y5:CLOCKREGION_X4Y9 \
                key center_region1_cols4_5_dsp_primitives \
                cells [dict get $plan center_region1_cols4_5_dsp_primitives]] \
            [dict create name \
                ${name_prefix}pb_projection_center_region1_cols6_7_dsp_cr_x2y5_x3y9 \
                target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X3Y9 \
                key center_region1_cols6_7_dsp_primitives \
                cells [dict get $plan center_region1_cols6_7_dsp_primitives]] \
            [dict create name ${name_prefix}pb_projection_owner_cr_x2y5_x4y9 \
                target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
                key owner_residual_floorplan_primitives \
                cells [dict get $plan owner_residual_floorplan_primitives]] \
            [dict create name \
                ${name_prefix}pb_projection_owner_region2_weight_cr_x2y5_x4y6 \
                target 1 range CLOCKREGION_X2Y5:CLOCKREGION_X4Y6 \
                key owner_region2_weight_primitives \
                cells [dict get $plan owner_region2_weight_primitives]] \
            [dict create name \
                ${name_prefix}pb_projection_center_region0_frontend_cr_x4y5_x5y9 \
                target 1 range CLOCKREGION_X4Y5:CLOCKREGION_X5Y9 \
                key center_region0_frontend_primitives \
                cells [dict get $plan center_region0_frontend_primitives]] \
            [dict create name ${name_prefix}pb_projection_right2_slr2 \
                target 2 range SLR2 key right_primitives \
                cells [dict get $plan right_primitives]]] {
        lappend result $spec
    }
    return $result
}

proc hap_projection_ooc_floorplan::apply {plan {name_prefix ""} \
        {require_empty_namespace 1} {region2_variant shared}} {
    if {$require_empty_namespace && [llength [get_pblocks -quiet]] != 0} {
        error "projection OOC input checkpoint unexpectedly contains pblocks"
    }
    foreach spec [specs $plan $name_prefix $region2_variant] {
        set name [dict get $spec name]
        set range [dict get $spec range]
        set cells [dict get $spec cells]
        create_pblock $name
        add_cells_to_pblock [get_pblocks $name] $cells
        resize_pblock [get_pblocks $name] -add [list $range]
        set_property IS_SOFT false [get_pblocks $name]
        set_property CONTAIN_ROUTING false [get_pblocks $name]
        set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
    }
}

proc hap_projection_ooc_floorplan::property_is_false {object property} {
    set value [string tolower [get_property $property $object]]
    return [expr {$value eq "0" || $value eq "false" || $value eq "no"}]
}

proc hap_projection_ooc_floorplan::audit_range {name spec ranges} {
    set expected [dict get $spec range]
    if {[regexp {^SLR[0-2]$} $expected]} {
        set accepted [list $expected ${expected}:${expected}]
    } elseif {[regexp \
            {^CLOCKREGION_X[0-9]+Y[0-9]+:CLOCKREGION_X[0-9]+Y[0-9]+$} \
            $expected]} {
        set accepted [list $expected]
    } else {
        error "projection OOC unsupported pblock range: $name range=$expected"
    }
    if {[llength $ranges] != 1 || \
        [lsearch -exact $accepted [lindex $ranges 0]] < 0} {
        error "projection OOC pblock range mismatch: $name expected=$expected actual=$ranges"
    }
}

proc hap_projection_ooc_floorplan::normalized_range_set {ranges} {
    set result {}
    foreach range $ranges {
        if {[regexp {^CLOCKREGION_(X[0-9]+Y[0-9]+):CLOCKREGION_\1$} \
                $range -> singleton]} {
            lappend result CLOCKREGION_$singleton
        } else {
            lappend result $range
        }
    }
    return [lsort -dictionary -unique $result]
}

proc hap_projection_ooc_floorplan::audit_range_override {
        name ranges expected_ranges} {
    set actual [normalized_range_set $ranges]
    set expected [normalized_range_set $expected_ranges]
    if {$actual ne $expected} {
        error "projection OOC pblock override range mismatch: $name expected=$expected actual=$actual"
    }
}

proc hap_projection_ooc_floorplan::audit_pblocks {plan {exact_membership 1} \
        {name_prefix ""} {allow_extra_pblocks 0} {region2_variant shared} \
        {range_overrides {}}} {
    set expected_names {}
    foreach spec [specs $plan $name_prefix $region2_variant] {
        lappend expected_names [dict get $spec name]
    }
    set expected_names [lsort -dictionary $expected_names]
    set actual_names [object_names [get_pblocks -quiet]]
    if {$allow_extra_pblocks} {
        set missing_names [list_subtract $expected_names $actual_names]
        if {[llength $missing_names] != 0} {
            error "projection OOC pblock namespace is missing: $missing_names"
        }
    } elseif {$actual_names ne $expected_names} {
        error "projection OOC pblock namespace mismatch"
    }

    foreach spec [specs $plan $name_prefix $region2_variant] {
        set name [dict get $spec name]
        set selected [dict get $spec cells]
        set pblocks [get_pblocks -quiet $name]
        require_count ${name}_count $pblocks 1
        set pblock [lindex $pblocks 0]
        if {![property_is_false $pblock IS_SOFT] ||
            ![property_is_false $pblock CONTAIN_ROUTING] ||
            ![property_is_false $pblock EXCLUDE_PLACEMENT]} {
            error "projection OOC pblock property mismatch: $name"
        }
        set ranges [get_property GRID_RANGES $pblock]
        if {[dict exists $range_overrides $name]} {
            audit_range_override $name $ranges \
                [dict get $range_overrides $name]
        } else {
            audit_range $name $spec $ranges
        }
        # Vivado can retain a hierarchical member or a transformed macro in
        # the pblock. Expand and normalize membership in every audit. Before
        # placement it must be exact; after placement replicated optimizer
        # extras are allowed, but no canonical member may disappear.
        set members [get_cells -quiet -of_objects $pblock -filter \
            {IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL}]
        set hierarchy_members [get_cells -quiet -of_objects $pblock \
            -filter {!IS_PRIMITIVE}]
        foreach member $hierarchy_members {
            set members [concat $members [primitive_descendants $member]]
        }
        set members [lsort -dictionary -unique $members]
        set member_names [object_names $members]
        set selected_names [object_names $selected]
        set missing [list_subtract $selected_names $member_names]
        set extra [list_subtract $member_names $selected_names]
        if {[llength $missing] != 0 ||
            ($exact_membership && [llength $extra] != 0)} {
            error "projection OOC pblock membership mismatch: $name missing=[llength $missing] extra=[llength $extra] exact=$exact_membership missing_sample=[lrange $missing 0 7] extra_sample=[lrange $extra 0 7]"
        }
    }
    return [dict create pblock_count [llength $expected_names] \
        exact_membership $exact_membership \
        name_prefix $name_prefix allow_extra_pblocks $allow_extra_pblocks]
}

proc hap_projection_ooc_floorplan::slr_index {cell} {
    set direct [get_property SLR_INDEX $cell]
    if {[regexp {([0-2])$} $direct -> index]} {return $index}
    return -1
}

proc hap_projection_ooc_floorplan::wrong_slr {cells target} {
    set wrong 0
    set unplaced 0
    foreach cell $cells {
        set index [slr_index $cell]
        if {$index < 0} {
            incr unplaced
        } elseif {$index != $target} {
            incr wrong
        }
    }
    return [dict create wrong $wrong unplaced $unplaced]
}

proc hap_projection_ooc_floorplan::placed_ref_counts {cells ref_name} {
    set counts {0 0 0}
    foreach cell $cells {
        if {[get_property REF_NAME $cell] ne $ref_name} {continue}
        set index [slr_index $cell]
        if {$index >= 0} {lset counts $index [expr {[lindex $counts $index] + 1}]}
    }
    return $counts
}

proc hap_projection_ooc_floorplan::audit_placement {plan} {
    variable expected_slr_dsp
    set left [wrong_slr [dict get $plan left_primitives] 0]
    set center [wrong_slr [dict get $plan center_primitives] 1]
    set right [wrong_slr [dict get $plan right_primitives] 2]
    set owner [wrong_slr [dict get $plan owner_primitives] 1]
    set frontend [wrong_slr [dict get $plan frontend_primitives] 1]
    set wrong [expr {[dict get $left wrong] + [dict get $center wrong] +
        [dict get $right wrong] + [dict get $owner wrong] +
        [dict get $frontend wrong]}]
    set unplaced [expr {[dict get $left unplaced] +
        [dict get $center unplaced] + [dict get $right unplaced] +
        [dict get $owner unplaced] + [dict get $frontend unplaced]}]
    set dsp [placed_ref_counts [dict get $plan dut_primitives] DSP48E2]
    set ok [expr {$wrong == 0 && $unplaced == 0 &&
        $dsp eq $expected_slr_dsp}]
    return [dict create left_wrong [dict get $left wrong] \
        center_wrong [dict get $center wrong] \
        right_wrong [dict get $right wrong] \
        owner_wrong [dict get $owner wrong] \
        frontend_wrong [dict get $frontend wrong] wrong_total $wrong \
        unplaced_total $unplaced slr_dsp $dsp ok $ok]
}

proc hap_projection_ooc_floorplan::write_plan {plan path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    puts $fp "dut_primitives=[llength [dict get $plan dut_primitives]]"
    foreach key {left_primitives frontend_primitives center_primitives \
            center_region0_primitives center_region1_primitives \
            center_region2_primitives center_region3_primitives \
            center_region3_floorplan_primitives \
            center_region1_cols4_5_primitives \
            center_region1_cols6_7_primitives \
            center_region1_residual_primitives \
            center_region1_cols4_5_dsp_primitives \
            center_region1_cols6_7_dsp_primitives \
            center_region1_logic_residual_primitives \
            center_region2_rows0_3_primitives \
            center_region2_rows4_7_primitives \
            center_region2_residual_primitives \
            center_region0_frontend_primitives center_wrapper_primitives \
            region0_input_activation_primitives \
            region0_input_zero_point_primitives \
            region0_input_weight_ff_primitives \
            region0_input_weight_lut_primitives \
            region0_input_weight_primitives region0_input_primitives \
            right_primitives owner_primitives owner_floorplan_primitives \
            owner_residual_floorplan_primitives \
            owner_region2_weight_ff_primitives \
            owner_region2_weight_lut_primitives \
            owner_region2_weight_primitives \
            region3_input_activation_primitives \
            region3_input_zero_point_primitives \
            region3_input_weight_ff_primitives \
            region3_input_weight_lut_primitives \
            region3_input_weight_primitives \
            region3_owner_weight_ff_primitives \
            region3_owner_weight_lut_primitives \
            region3_owner_weight_primitives region3_input_primitives} {
        set cells [dict get $plan $key]
        puts $fp "$key=[llength $cells]"
        puts $fp "${key}_dsp48e2=[count_ref $cells DSP48E2]"
        puts $fp "${key}_ramb36e2=[count_ref $cells RAMB36E2]"
        puts $fp "${key}_ramb18e2=[count_ref $cells RAMB18E2]"
    }
    puts $fp "center_region1_lane_roots=[llength [dict get $plan center_region1_lane_roots]]"
    puts $fp "center_region1_cols4_5_lane_roots=[llength [dict get $plan center_region1_cols4_5_lane_roots]]"
    puts $fp "center_region1_cols6_7_lane_roots=[llength [dict get $plan center_region1_cols6_7_lane_roots]]"
    puts $fp "center_region1_bisect_exact_cover=[dict get $plan center_region1_bisect_exact_cover]"
    puts $fp "center_region1_dsp_stripe_exact_cover=[dict get $plan center_region1_dsp_stripe_exact_cover]"
    puts $fp "center_region2_lane_roots=[llength [dict get $plan center_region2_lane_roots]]"
    puts $fp "center_region2_rows0_3_lane_roots=[llength [dict get $plan center_region2_rows0_3_lane_roots]]"
    puts $fp "center_region2_rows4_7_lane_roots=[llength [dict get $plan center_region2_rows4_7_lane_roots]]"
    puts $fp "center_region2_row_exact_cover=[dict get $plan center_region2_row_exact_cover]"
    puts $fp "center_region2_residual_removed_lut=[dict get $plan center_region2_residual_removed_lut]"
    puts $fp "owner_region0_input_exact_cover=[dict get $plan owner_region0_input_exact_cover]"
    puts $fp "owner_region3_input_exact_cover=[dict get $plan owner_region3_input_exact_cover]"
    puts $fp "owner_region2_weight_exact_cover=[dict get $plan owner_region2_weight_exact_cover]"
    puts $fp "region3_weight_owner_residency_ok=[dict get $plan region3_weight_owner_residency_ok]"
    close $fp
}

proc hap_projection_ooc_floorplan::write_placement {metrics path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    foreach key {left_wrong center_wrong right_wrong owner_wrong \
            frontend_wrong wrong_total unplaced_total slr_dsp ok} {
        puts $fp "$key=[dict get $metrics $key]"
    }
    close $fp
}

proc hap_projection_ooc_floorplan::congestion_counts_at_or_above {
        text minimum_level} {
    if {![string is integer -strict $minimum_level] || $minimum_level < 1} {
        error "invalid congestion minimum level: $minimum_level"
    }
    set section none
    set placer 0
    set router 0
    foreach line [split $text "\n"] {
        if {[string first "Placer Final Level Congestion Reporting" $line] >= 0} {
            set section placer
            continue
        }
        if {[string first "Router Initial Congestion" $line] >= 0} {
            set section router
            continue
        }
        if {[regexp {^\|[[:space:]]*(North|South|East|West)[[:space:]]+\|[[:space:]]*(Global|Long|Short)[[:space:]]+\|[[:space:]]*([0-9]+)[[:space:]]+\|} \
                $line -> direction type level] && $level >= $minimum_level} {
            if {$section eq "placer"} {incr placer}
            if {$section eq "router"} {incr router}
        }
    }
    return [dict create placer $placer router $router \
        total [expr {$placer + $router}]]
}

proc hap_projection_ooc_floorplan::congestion_level6_counts {text} {
    return [congestion_counts_at_or_above $text 6]
}
