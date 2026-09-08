# P12 extends only the existing Attention region1 non-DSP logic pblock with
# the low-occupancy X5Y5 clock region.  DSP stripes and exact membership stay
# unchanged.

namespace eval hap_v5_p12_region1_relief {
    variable contract P12_ATTN_REGION1_LOGIC_PLUS_X5Y5
    variable pblock_name \
        p3_pb_projection_center_region1_logic_residual_cr_x2y5_x4y9
    variable base_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9
    variable relief_range CLOCKREGION_X5Y5:CLOCKREGION_X5Y5
    # Vivado canonicalizes the L-shaped union into these two rectangles.
    variable canonical_ranges [list \
        CLOCKREGION_X2Y5:CLOCKREGION_X5Y5 \
        CLOCKREGION_X2Y6:CLOCKREGION_X4Y9]
}

proc hap_v5_p12_region1_relief::discover {geometry_plan} {
    variable contract
    variable pblock_name
    variable base_range
    variable relief_range
    variable canonical_ranges
    set cells [dict get $geometry_plan \
        center_region1_logic_residual_primitives]
    if {[llength $cells] != 68257 ||
        [hap_projection_ooc_floorplan::count_ref $cells DSP48E2] != 0} {
        error "P12 region1 relief membership signature mismatch"
    }
    set lut [hap_projection_ooc_floorplan::count_ref_glob $cells LUT*]
    set ff [hap_projection_ooc_floorplan::count_ref_glob $cells FD*]
    if {$lut != 33885 || $ff != 32032} {
        error "P12 region1 relief LUT/FF signature mismatch: LUT=$lut FF=$ff"
    }
    return [dict create contract $contract pblock_name $pblock_name \
        base_range $base_range relief_range $relief_range \
        expected_ranges $canonical_ranges \
        primitives $cells primitive_count [llength $cells] lut $lut ff $ff \
        dsp 0]
}

proc hap_v5_p12_region1_relief::apply {plan} {
    variable contract
    if {[dict get $plan contract] ne $contract} {
        error "P12 region1 relief contract mismatch"
    }
    set name [dict get $plan pblock_name]
    set pblocks [get_pblocks -quiet $name]
    hap_projection_ooc_floorplan::require_count \
        p12_region1_relief_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    set before [hap_projection_ooc_floorplan::normalized_range_set \
        [get_property GRID_RANGES $pblock]]
    set expected_before [hap_projection_ooc_floorplan::normalized_range_set \
        [list [dict get $plan base_range]]]
    if {$before ne $expected_before} {
        error "P12 region1 relief base range mismatch: $before"
    }
    resize_pblock $pblock -add [list [dict get $plan relief_range]]
}

proc hap_v5_p12_region1_relief::range_overrides {plan} {
    return [dict create [dict get $plan pblock_name] \
        [dict get $plan expected_ranges]]
}

proc hap_v5_p12_region1_relief::audit {plan require_placed} {
    set name [dict get $plan pblock_name]
    set pblocks [get_pblocks -quiet $name]
    hap_projection_ooc_floorplan::require_count \
        p12_region1_relief_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    if {![hap_projection_ooc_floorplan::property_is_false \
            $pblock IS_SOFT] ||
        ![hap_projection_ooc_floorplan::property_is_false \
            $pblock CONTAIN_ROUTING] ||
        ![hap_projection_ooc_floorplan::property_is_false \
            $pblock EXCLUDE_PLACEMENT]} {
        error "P12 region1 relief pblock policy mismatch"
    }
    hap_projection_ooc_floorplan::audit_range_override $name \
        [get_property GRID_RANGES $pblock] [dict get $plan expected_ranges]
    set members [get_cells -quiet -of_objects $pblock -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL}]
    set member_names [hap_projection_ooc_floorplan::object_names $members]
    set expected_names [hap_projection_ooc_floorplan::object_names \
        [dict get $plan primitives]]
    set missing [hap_projection_ooc_floorplan::list_subtract \
        $expected_names $member_names]
    if {[llength $missing] != 0} {
        error "P12 region1 relief missing canonical members: [llength $missing]"
    }
    set wrong 0
    set unplaced 0
    set relief_placed 0
    if {$require_placed} {
        foreach slr [get_property SLR_INDEX [dict get $plan primitives]] {
            if {![regexp {1$} $slr]} {
                incr unplaced
            }
        }
        set relief_regions [get_clock_regions -quiet X5Y5]
        hap_projection_ooc_floorplan::require_count \
            p12_relief_clock_region $relief_regions 1
        set relief_sites [get_sites -quiet -of_objects $relief_regions]
        set direct [get_cells -quiet -of_objects $relief_sites]
        set via_bels [get_cells -quiet -of_objects \
            [get_bels -quiet -of_objects $relief_sites]]
        set relief_names [lsort -dictionary -unique [concat \
            [get_property NAME $direct] [get_property NAME $via_bels]]]
        set relief_placed [llength \
            [hap_projection_ooc_floorplan::list_intersection \
                $expected_names $relief_names]]
        if {$wrong != 0 || $unplaced != 0} {
            error "P12 region1 relief placement mismatch: wrong=$wrong unplaced=$unplaced"
        }
    }
    return [dict create ok 1 contract [dict get $plan contract] \
        require_placed $require_placed name $name \
        primitive_count [dict get $plan primitive_count] \
        lut [dict get $plan lut] ff [dict get $plan ff] dsp 0 \
        missing [llength $missing] wrong $wrong unplaced $unplaced \
        relief_placed $relief_placed]
}

proc hap_v5_p12_region1_relief::write_plan {plan path status} {
    set fp [open $path w]
    foreach key {contract pblock_name base_range relief_range \
            expected_ranges primitive_count lut ff dsp} {
        puts $fp "$key=[dict get $plan $key]"
    }
    puts $fp "status=$status"
    close $fp
}

proc hap_v5_p12_region1_relief::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok contract require_placed name primitive_count lut ff dsp \
            missing wrong unplaced relief_placed} {
        puts $fp "$key=[dict get $audit $key]"
    }
    puts $fp "status=$status"
    close $fp
}
