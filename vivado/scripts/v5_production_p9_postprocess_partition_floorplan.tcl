# P9 postprocess partition layered on the P5 input-local floorplan.  Complete
# six-row storage groups move to the outer SLRs while the middle four banks
# and the postprocess mux/quantizer remain central.  This preserves functional
# grouping and avoids splitting a row bank across an SLR boundary.

namespace eval hap_v5_p9_postprocess_partition {
    variable contract P9_POSTPROCESS_SPLIT_6_4_6
    variable slr0_pblock pb_v5_p9_postprocess_rows0_5_slr0
    variable slr2_pblock pb_v5_p9_postprocess_rows10_15_slr2
    variable center_pblock pb_v5_attention_projection_center12_slr1
}

proc hap_v5_p9_postprocess_partition::count_ref_glob {cells pattern} {
    set count 0
    foreach ref [get_property REF_NAME $cells] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_v5_p9_postprocess_partition::discover {base_plan p5_plan} {
    variable contract
    if {[dict get $base_plan contract_variant] ne
            "P2_COHORT16_COL2_12_2" ||
        [dict get $p5_plan contract] ne "P5_INPUT_HALF_LOCAL_8_8"} {
        error "P9 requires the canonical P3 base plan and P5 input plan"
    }
    set roots [hap_v5_floorplan::module_cells \
        hap_attention_cohort16_postprocess_store]
    hap_v5_p5_input_partition::require_count postprocess_store $roots 1
    set root [lindex $roots 0]
    set root_name [get_property NAME $root]
    set row_roots [hap_v5_p5_input_partition::module_children $root \
        hap_attention_cohort16_postprocess_row_bank]
    hap_v5_p5_input_partition::require_count postprocess_row_banks \
        $row_roots 16

    set by_name [dict create]
    foreach row_root $row_roots {
        dict set by_name [get_property NAME $row_root] $row_root
    }
    set row_primitives {}
    for {set row 0} {$row < 16} {incr row} {
        set name [format {%s/g_row_bank[%d].u_bank} $root_name $row]
        if {![dict exists $by_name $name]} {
            error "P9 exact postprocess row hierarchy is missing: $name"
        }
        set cells [hap_v5_floorplan::pblockable_primitives \
            [hap_v5_floorplan::primitive_descendants [dict get $by_name $name]]]
        set hard [hap_v5_p5_input_partition::hard_signature $cells]
        set ff [hap_v5_p9_postprocess_partition::count_ref_glob $cells FD*]
        set lut [hap_v5_p9_postprocess_partition::count_ref_glob $cells LUT*]
        if {[llength $cells] != 2674 || $lut != 994 || $ff != 1536 ||
            [dict get $hard dsp] != 0 || [dict get $hard uram] != 0 ||
            [dict get $hard ramb36] != 0 || [dict get $hard ramb18] != 0} {
            error "P9 postprocess row signature mismatch: row=$row primitives=[llength $cells] LUT=$lut FF=$ff hard=$hard"
        }
        lappend row_primitives $cells
    }

    set slr0_rows [concat {*}[lrange $row_primitives 0 5]]
    set center_rows [concat {*}[lrange $row_primitives 6 9]]
    set slr2_rows [concat {*}[lrange $row_primitives 10 15]]
    set all_rows [hap_v5_floorplan::list_union \
        $slr0_rows $center_rows $slr2_rows]
    if {[llength $all_rows] != 42784 ||
        [llength [hap_v5_floorplan::list_intersection $slr0_rows \
            $center_rows]] != 0 ||
        [llength [hap_v5_floorplan::list_intersection $slr0_rows \
            $slr2_rows]] != 0 ||
        [llength [hap_v5_floorplan::list_intersection $center_rows \
            $slr2_rows]] != 0} {
        error "P9 postprocess row partition is incomplete or overlapping"
    }

    set existing [hap_v5_floorplan::list_union \
        [dict get $p5_plan half0_primitives] \
        [dict get $p5_plan half1_primitives] \
        [dict get $p5_plan center_primitives]]
    if {[llength [hap_v5_floorplan::list_intersection $all_rows \
            $existing]] != 0} {
        error "P9 postprocess rows overlap the P5 input partition"
    }

    return [dict create contract $contract root $root root_name $root_name \
        row_primitives $row_primitives all_rows $all_rows \
        slr0_rows $slr0_rows center_rows $center_rows slr2_rows $slr2_rows \
        per_row_primitives 2674 per_row_lut 994 per_row_ff 1536]
}

proc hap_v5_p9_postprocess_partition::apply {plan} {
    variable contract
    variable slr0_pblock
    variable slr2_pblock
    variable center_pblock
    if {[dict get $plan contract] ne $contract} {
        error "P9 postprocess plan contract mismatch"
    }
    set center [get_pblocks -quiet $center_pblock]
    if {[llength $center] != 1} {
        error "P9 canonical center pblock is not unique: $center_pblock"
    }
    hap_v5_p5_input_partition::create_hard_pblock $slr0_pblock 0 \
        [dict get $plan slr0_rows]
    hap_v5_p5_input_partition::create_hard_pblock $slr2_pblock 2 \
        [dict get $plan slr2_rows]
    add_cells_to_pblock $center [dict get $plan center_rows]
}

proc hap_v5_p9_postprocess_partition::audit {plan require_placed} {
    variable slr0_pblock
    variable slr2_pblock
    variable center_pblock
    set slr0 [hap_v5_p5_input_partition::audit_outer $slr0_pblock 0 \
        [dict get $plan slr0_rows] $require_placed]
    set slr2 [hap_v5_p5_input_partition::audit_outer $slr2_pblock 2 \
        [dict get $plan slr2_rows] $require_placed]
    set center_pb [get_pblocks -quiet $center_pblock]
    if {[llength $center_pb] != 1 ||
        ![hap_v5_p5_input_partition::pblock_target_ok \
            [lindex $center_pb 0] 1]} {
        error "P9 canonical center pblock target mismatch"
    }
    set center_members [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::expanded_pblock_primitives [lindex $center_pb 0]]]
    set center_missing [hap_v5_floorplan::list_subtract \
        [dict get $plan center_rows] $center_members]
    set center_outer_overlap [hap_v5_floorplan::list_intersection \
        $center_members [hap_v5_floorplan::list_union \
            [dict get $plan slr0_rows] [dict get $plan slr2_rows]]]
    if {[llength $center_missing] != 0 ||
        [llength $center_outer_overlap] != 0} {
        error "P9 center membership mismatch: missing=[llength $center_missing] outer_overlap=[llength $center_outer_overlap]"
    }
    set center_wrong 0
    if {$require_placed} {
        set placement [hap_v5_floorplan::wrong_slr_audit \
            [dict get $plan center_rows] 1]
        set center_wrong [dict get $placement wrong]
        if {$center_wrong != 0 || [dict get $placement direct_slr_empty] != 0} {
            error "P9 center postprocess rows have wrong/unresolved placement"
        }
    }
    return [dict create ok 1 require_placed $require_placed pblock_count 2 \
        slr0 $slr0 slr2 $slr2 center_missing [llength $center_missing] \
        center_outer_overlap [llength $center_outer_overlap] \
        center_wrong $center_wrong outer_wrong \
        [expr {[dict get $slr0 wrong] + [dict get $slr2 wrong]}] \
        outer_extras [expr {[dict get $slr0 extras] +
            [dict get $slr2 extras]}]]
}

proc hap_v5_p9_postprocess_partition::write_plan {plan path status} {
    set fp [open $path w]
    foreach {key value} [list contract [dict get $plan contract] \
            root_name [dict get $plan root_name] \
            row_bank_count [llength [dict get $plan row_primitives]] \
            all_row_primitives [llength [dict get $plan all_rows]] \
            slr0_row_primitives [llength [dict get $plan slr0_rows]] \
            center_row_primitives [llength [dict get $plan center_rows]] \
            slr2_row_primitives [llength [dict get $plan slr2_rows]] \
            per_row_primitives [dict get $plan per_row_primitives] \
            per_row_lut [dict get $plan per_row_lut] \
            per_row_ff [dict get $plan per_row_ff] status $status] {
        puts $fp "$key=$value"
    }
    close $fp
}

proc hap_v5_p9_postprocess_partition::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok require_placed pblock_count center_missing
            center_outer_overlap center_wrong outer_wrong outer_extras} {
        puts $fp "$key=[dict get $audit $key]"
    }
    foreach group {slr0 slr2} {
        set record [dict get $audit $group]
        foreach key {name target expected members missing extras wrong hard} {
            puts $fp "${group}_${key}=[dict get $record $key]"
        }
    }
    puts $fp "status=$status"
    close $fp
}
