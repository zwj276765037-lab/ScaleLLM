# P14 preserves the complete Attention region2 membership and SLR1 residency,
# while widening its existing shared clock-region pblock by one X column.

namespace eval hap_v5_p14_region2_relief {
    variable contract P14_ATTN_REGION2_SHARED_X0_X2
    variable pblock_name \
        p3_pb_projection_center_region2_shared_cr_x0y5_x1y9
    variable base_range CLOCKREGION_X0Y5:CLOCKREGION_X1Y9
    variable relief_range CLOCKREGION_X2Y5:CLOCKREGION_X2Y9
    variable expected_range CLOCKREGION_X0Y5:CLOCKREGION_X2Y9
}

proc hap_v5_p14_region2_relief::discover {geometry_plan} {
    variable contract
    variable pblock_name
    variable base_range
    variable relief_range
    variable expected_range
    set cells [dict get $geometry_plan center_region2_primitives]
    set lut [hap_projection_ooc_floorplan::count_ref_glob $cells LUT*]
    set ff [hap_projection_ooc_floorplan::count_ref_glob $cells FD*]
    set dsp [hap_projection_ooc_floorplan::count_ref $cells DSP48E2]
    if {[llength $cells] != 68799 || $lut != 33883 || $ff != 32032 ||
        $dsp != 544 ||
        [hap_projection_ooc_floorplan::count_ref $cells URAM288] != 0} {
        error "P14 region2 signature mismatch: primitives=[llength $cells] LUT=$lut FF=$ff DSP=$dsp"
    }
    return [dict create contract $contract pblock_name $pblock_name \
        base_range $base_range relief_range $relief_range \
        expected_range $expected_range primitives $cells \
        primitive_count [llength $cells] lut $lut ff $ff dsp $dsp]
}

proc hap_v5_p14_region2_relief::apply {plan} {
    variable contract
    if {[dict get $plan contract] ne $contract} {
        error "P14 region2 relief contract mismatch"
    }
    set name [dict get $plan pblock_name]
    set pblocks [get_pblocks -quiet $name]
    hap_projection_ooc_floorplan::require_count p14_region2_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    set before [hap_projection_ooc_floorplan::normalized_range_set \
        [get_property GRID_RANGES $pblock]]
    set expected_before [hap_projection_ooc_floorplan::normalized_range_set \
        [list [dict get $plan base_range]]]
    if {$before ne $expected_before} {
        error "P14 region2 base range mismatch: expected=$expected_before actual=$before"
    }
    resize_pblock $pblock -add [list [dict get $plan relief_range]]
}

proc hap_v5_p14_region2_relief::range_overrides {plan} {
    return [dict create [dict get $plan pblock_name] \
        [list [dict get $plan expected_range]]]
}

proc hap_v5_p14_region2_relief::audit {plan require_placed} {
    set name [dict get $plan pblock_name]
    set pblocks [get_pblocks -quiet $name]
    hap_projection_ooc_floorplan::require_count p14_region2_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    if {![hap_projection_ooc_floorplan::property_is_false $pblock IS_SOFT] ||
        ![hap_projection_ooc_floorplan::property_is_false \
            $pblock CONTAIN_ROUTING] ||
        ![hap_projection_ooc_floorplan::property_is_false \
            $pblock EXCLUDE_PLACEMENT]} {
        error "P14 region2 pblock policy mismatch"
    }
    hap_projection_ooc_floorplan::audit_range_override $name \
        [get_property GRID_RANGES $pblock] \
        [list [dict get $plan expected_range]]

    set expected_names [hap_projection_ooc_floorplan::object_names \
        [dict get $plan primitives]]
    set members [get_cells -quiet -of_objects $pblock -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL}]
    set member_names [hap_projection_ooc_floorplan::object_names $members]
    set missing [hap_projection_ooc_floorplan::list_subtract \
        $expected_names $member_names]
    if {[llength $missing] != 0} {
        error "P14 region2 pblock is missing [llength $missing] canonical members"
    }

    set wrong 0
    set unplaced 0
    set relief_placed 0
    if {$require_placed} {
        foreach cell [dict get $plan primitives] {
            set loc [get_property LOC $cell]
            if {$loc eq ""} {
                incr unplaced
                continue
            }
            set site [get_sites -quiet $loc]
            set region [get_clock_regions -quiet -of_objects $site]
            if {[llength $region] != 1} {
                incr unplaced
                continue
            }
            set region_name [get_property NAME $region]
            if {![regexp {^X[0-2]Y[5-9]$} $region_name]} {
                incr wrong
            } elseif {[string match X2Y* $region_name]} {
                incr relief_placed
            }
        }
        if {$wrong != 0 || $unplaced != 0} {
            error "P14 region2 placement mismatch: wrong=$wrong unplaced=$unplaced"
        }
    }
    return [dict create ok 1 contract [dict get $plan contract] \
        require_placed $require_placed name $name \
        primitive_count [dict get $plan primitive_count] \
        lut [dict get $plan lut] ff [dict get $plan ff] \
        dsp [dict get $plan dsp] missing [llength $missing] \
        wrong $wrong unplaced $unplaced relief_placed $relief_placed]
}

proc hap_v5_p14_region2_relief::write_plan {plan path status} {
    set fp [open $path w]
    foreach key {contract pblock_name base_range relief_range expected_range
            primitive_count lut ff dsp} {
        puts $fp "$key=[dict get $plan $key]"
    }
    puts $fp "status=$status"
    close $fp
}

proc hap_v5_p14_region2_relief::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok contract require_placed name primitive_count lut ff dsp
            missing wrong unplaced relief_placed} {
        puts $fp "$key=[dict get $audit $key]"
    }
    puts $fp "status=$status"
    close $fp
}
