# P13 forces three capacity-proven Attention region1 lane-logic groups into
# X5Y5. Their DSPs remain in the qualified region1 DSP stripe pblocks.

namespace eval hap_v5_p13_region1_lane_relief {
    variable contract P13_ATTN_REGION1_LANES_R2C3_R6C3_R7C3_X5Y5
    variable pblock_name pb_v5_p13_attn_region1_lanes_r2c3_r6c3_r7c3_x5y5
    variable parent_pblock_name \
        p3_pb_projection_center_region1_logic_residual_cr_x2y5_x4y9
    variable grid_range CLOCKREGION_X5Y5:CLOCKREGION_X5Y5
    variable allowed_region X5Y5
    variable selected_lane_ids {r2c3 r6c3 r7c3}
}

proc hap_v5_p13_region1_lane_relief::count_ref_glob {cells pattern} {
    set count 0
    foreach ref [get_property REF_NAME $cells] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_v5_p13_region1_lane_relief::discover {geometry_plan relief_plan} {
    variable contract
    variable pblock_name
    variable parent_pblock_name
    variable grid_range
    variable allowed_region
    variable selected_lane_ids
    if {[dict get $relief_plan contract] ne
            "P13_ATTN_REGION1_LOGIC_PLUS_X5Y5" ||
        [dict get $relief_plan pblock_name] ne $parent_pblock_name ||
        [dict get $relief_plan relief_range] ne $grid_range} {
        error "P13 lane relief requires the canonical P12 parent range"
    }
    set lane_roots [dict get $geometry_plan center_region1_lane_roots]
    hap_projection_ooc_floorplan::require_count \
        p13_region1_lane_roots $lane_roots 32
    set selected_roots {}
    set selected_primitives {}
    set selected_names {}
    foreach root $lane_roots {
        set root_name [get_property NAME $root]
        if {![regexp {g_row\[([0-7])\]\.g_col\[([0-3])\]\.u_lane$} \
                $root_name -> row local_col]} {
            error "P13 unexpected region1 lane root: $root_name"
        }
        set lane_id r${row}c${local_col}
        if {[lsearch -exact $selected_lane_ids $lane_id] < 0} {continue}
        lappend selected_roots $root
        lappend selected_names $root_name
        set lane_primitives [hap_v5_floorplan::pblockable_primitives \
            [hap_v5_floorplan::primitive_descendants $root]]
        set selected_primitives [concat $selected_primitives \
            [filter $lane_primitives {REF_NAME != DSP48E2}]]
    }
    set selected_roots [lsort -dictionary -unique $selected_roots]
    set selected_names [lsort -dictionary -unique $selected_names]
    set selected_primitives [lsort -dictionary -unique $selected_primitives]
    hap_projection_ooc_floorplan::require_count \
        p13_selected_lane_roots $selected_roots 3
    set lut [count_ref_glob $selected_primitives LUT*]
    set ff [count_ref_glob $selected_primitives FD*]
    set dsp [hap_projection_ooc_floorplan::count_ref \
        $selected_primitives DSP48E2]
    set uram [hap_projection_ooc_floorplan::count_ref \
        $selected_primitives URAM288]
    set ramb36 [hap_projection_ooc_floorplan::count_ref \
        $selected_primitives RAMB36E2]
    set ramb18 [hap_projection_ooc_floorplan::count_ref \
        $selected_primitives RAMB18E2]
    if {[llength $selected_primitives] != 4974 || $lut != 2532 ||
        $ff != 2271 || $dsp != 0 || $uram != 0 ||
        $ramb36 != 0 || $ramb18 != 0} {
        error "P13 selected lane signature mismatch: primitives=[llength $selected_primitives] LUT=$lut FF=$ff DSP=$dsp URAM=$uram RAMB36=$ramb36 RAMB18=$ramb18"
    }
    set parent_logic [dict get $geometry_plan \
        center_region1_logic_residual_primitives]
    set missing_from_parent [hap_v5_floorplan::list_subtract \
        $selected_primitives $parent_logic]
    if {[llength $missing_from_parent] != 0} {
        error "P13 selected lane logic escapes parent: [llength $missing_from_parent]"
    }
    return [dict create contract $contract pblock_name $pblock_name \
        parent_pblock_name $parent_pblock_name grid_range $grid_range \
        allowed_region $allowed_region selected_lane_ids $selected_lane_ids \
        selected_root_names $selected_names primitives $selected_primitives \
        primitive_count [llength $selected_primitives] lut $lut ff $ff \
        dsp $dsp uram $uram ramb36 $ramb36 ramb18 $ramb18]
}

proc hap_v5_p13_region1_lane_relief::geometry_audit_view {
        geometry_plan lane_plan} {
    set parent_key center_region1_logic_residual_primitives
    set parent [dict get $geometry_plan $parent_key]
    set delegated [dict get $lane_plan primitives]
    set missing [hap_v5_floorplan::list_subtract $delegated $parent]
    set remaining [hap_v5_floorplan::list_subtract $parent $delegated]
    set overlap [hap_v5_floorplan::list_intersection $remaining $delegated]
    set covered [hap_v5_floorplan::list_union $remaining $delegated]
    set lut [count_ref_glob $remaining LUT*]
    set ff [count_ref_glob $remaining FD*]
    if {[llength $missing] != 0 || [llength $overlap] != 0 ||
        [llength $covered] != [llength $parent] ||
        [llength $remaining] != 63283 || $lut != 31353 || $ff != 29761 ||
        [hap_projection_ooc_floorplan::count_ref $remaining DSP48E2] != 0} {
        error "P13 delegated parent membership signature mismatch: missing=[llength $missing] overlap=[llength $overlap] parent=[llength $parent] remaining=[llength $remaining] covered=[llength $covered] LUT=$lut FF=$ff"
    }
    set audit_plan $geometry_plan
    dict set audit_plan $parent_key $remaining
    return $audit_plan
}

proc hap_v5_p13_region1_lane_relief::delegate_spec {plan} {
    return [dict create name [dict get $plan pblock_name] target 1]
}

proc hap_v5_p13_region1_lane_relief::apply {plan} {
    variable contract
    if {[dict get $plan contract] ne $contract} {
        error "P13 lane relief contract mismatch"
    }
    set parent [get_pblocks -quiet [dict get $plan parent_pblock_name]]
    hap_projection_ooc_floorplan::require_count \
        p13_parent_logic_pblock $parent 1
    set parent_ranges [hap_projection_ooc_floorplan::normalized_range_set \
        [get_property GRID_RANGES $parent]]
    set expected_parent [hap_projection_ooc_floorplan::normalized_range_set \
        [list CLOCKREGION_X2Y5:CLOCKREGION_X5Y5 \
            CLOCKREGION_X2Y6:CLOCKREGION_X4Y9]]
    if {$parent_ranges ne $expected_parent} {
        error "P13 parent logic range mismatch: $parent_ranges"
    }
    set name [dict get $plan pblock_name]
    if {[llength [get_pblocks -quiet $name]] != 0} {
        error "P13 lane relief pblock already exists: $name"
    }
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] [dict get $plan primitives]
    resize_pblock [get_pblocks $name] -add \
        [list [dict get $plan grid_range]]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

proc hap_v5_p13_region1_lane_relief::audit {plan require_placed} {
    set pblocks [get_pblocks -quiet [dict get $plan pblock_name]]
    hap_projection_ooc_floorplan::require_count p13_lane_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    if {![hap_v5_floorplan::property_is_false $pblock IS_SOFT] ||
        ![hap_v5_floorplan::property_is_false $pblock CONTAIN_ROUTING] ||
        ![hap_v5_floorplan::property_is_false $pblock EXCLUDE_PLACEMENT]} {
        error "P13 lane relief pblock policy mismatch"
    }
    set ranges [get_property GRID_RANGES $pblock]
    if {[llength $ranges] != 1 ||
        [lindex $ranges 0] ne [dict get $plan grid_range]} {
        error "P13 lane relief range mismatch: $ranges"
    }
    set members [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::expanded_pblock_primitives $pblock]]
    set missing [hap_v5_floorplan::list_subtract \
        [dict get $plan primitives] $members]
    set extras [hap_v5_floorplan::list_subtract \
        $members [dict get $plan primitives]]
    if {[llength $missing] != 0 || [llength $extras] != 0} {
        error "P13 lane membership mismatch: missing=[llength $missing] extras=[llength $extras]"
    }
    set wrong 0
    set unplaced 0
    if {$require_placed} {
        foreach cell [dict get $plan primitives] {
            set sites [get_sites -quiet -of_objects $cell]
            if {[llength $sites] != 1} {
                incr unplaced
                continue
            }
            set regions [get_clock_regions -quiet -of_objects $sites]
            if {[llength $regions] != 1 ||
                [get_property NAME $regions] ne \
                    [dict get $plan allowed_region]} {
                incr wrong
            }
        }
        if {$wrong != 0 || $unplaced != 0} {
            error "P13 lane placement mismatch: wrong=$wrong unplaced=$unplaced"
        }
    }
    return [dict create ok 1 require_placed $require_placed \
        contract [dict get $plan contract] name [dict get $plan pblock_name] \
        grid_range [dict get $plan grid_range] \
        expected [dict get $plan primitive_count] members [llength $members] \
        missing [llength $missing] extras [llength $extras] \
        wrong $wrong unplaced $unplaced]
}

proc hap_v5_p13_region1_lane_relief::write_plan {plan path status} {
    set fp [open $path w]
    foreach key {contract pblock_name parent_pblock_name grid_range
            allowed_region selected_lane_ids selected_root_names
            primitive_count lut ff dsp uram ramb36 ramb18} {
        puts $fp "$key=[dict get $plan $key]"
    }
    puts $fp "status=$status"
    close $fp
}

proc hap_v5_p13_region1_lane_relief::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok require_placed contract name grid_range expected members
            missing extras wrong unplaced} {
        puts $fp "$key=[dict get $audit $key]"
    }
    puts $fp "status=$status"
    close $fp
}
