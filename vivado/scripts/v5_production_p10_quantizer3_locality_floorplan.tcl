# P10 physical-only locality for the fourth SwiGLU quantizer.  P9 removed the
# original south cluster but overlapped Attention region1.  P10 uses the
# lowest-pressure Y5 row, outside all five P9 Level-6 windows.

namespace eval hap_v5_p10_quantizer3_locality {
    variable contract P10_SWIGLU_QUANTIZER3_CR_X0Y5_X2Y5
    variable pblock_name pb_v5_p10_swiglu_quantizer3_cr_x0y5_x2y5
    variable grid_range CLOCKREGION_X0Y5:CLOCKREGION_X2Y5
    variable allowed_regions {X0Y5 X1Y5 X2Y5}
}

proc hap_v5_p10_quantizer3_locality::count_ref_glob {cells pattern} {
    set count 0
    foreach ref [get_property REF_NAME $cells] {
        if {[string match $pattern $ref]} {incr count}
    }
    return $count
}

proc hap_v5_p10_quantizer3_locality::discover {base_plan p5_plan post_plan} {
    variable contract
    variable pblock_name
    variable grid_range
    variable allowed_regions
    if {[dict get $base_plan contract_variant] ne
            "P2_COHORT16_COL2_12_2" ||
        [dict get $p5_plan contract] ne "P5_INPUT_HALF_LOCAL_8_8" ||
        [dict get $post_plan contract] ne "P9_POSTPROCESS_SPLIT_6_4_6"} {
        error "P10 quantizer3 locality requires canonical base/P5/P9 plans"
    }

    set roots [hap_v5_floorplan::module_cells \
        hap_mlp_robust_a8_quantizer_s35]
    hap_v5_p5_input_partition::require_count swiglu_quantizer_roots $roots 4
    set root ""
    foreach candidate $roots {
        if {[regexp {/g_quantizer\[3\]\.u_quantizer$} \
                [get_property NAME $candidate]]} {
            lappend root $candidate
        }
    }
    hap_v5_p5_input_partition::require_count swiglu_quantizer3_root $root 1
    set root [lindex $root 0]
    set primitives [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants $root]]
    set hard [hap_v5_p5_input_partition::hard_signature $primitives]
    set lut [count_ref_glob $primitives LUT*]
    set ff [count_ref_glob $primitives FD*]
    if {[llength $primitives] != 11178 || $lut != 6731 || $ff != 3955 ||
        [dict get $hard dsp] != 1 || [dict get $hard uram] != 0 ||
        [dict get $hard ramb36] != 0 || [dict get $hard ramb18] != 0} {
        error "P10 quantizer3 signature mismatch: primitives=[llength $primitives] LUT=$lut FF=$ff hard=$hard"
    }

    set p5_cells [hap_v5_floorplan::list_union \
        [dict get $p5_plan half0_primitives] \
        [dict get $p5_plan half1_primitives] \
        [dict get $p5_plan center_primitives]]
    if {[llength [hap_v5_floorplan::list_intersection $primitives \
            $p5_cells]] != 0 ||
        [llength [hap_v5_floorplan::list_intersection $primitives \
            [dict get $post_plan all_rows]]] != 0} {
        error "P10 quantizer3 overlaps an existing P5/P9 partition"
    }

    return [dict create contract $contract root $root \
        root_name [get_property NAME $root] primitives $primitives \
        primitive_count [llength $primitives] lut $lut ff $ff hard $hard \
        pblock_name $pblock_name grid_range $grid_range \
        allowed_regions $allowed_regions]
}

proc hap_v5_p10_quantizer3_locality::apply {plan} {
    variable contract
    if {[dict get $plan contract] ne $contract} {
        error "P10 quantizer3 plan contract mismatch"
    }
    set name [dict get $plan pblock_name]
    if {[llength [get_pblocks -quiet $name]] != 0} {
        error "P10 quantizer3 pblock already exists: $name"
    }
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] [dict get $plan primitives]
    resize_pblock [get_pblocks $name] -add \
        [list [dict get $plan grid_range]]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

proc hap_v5_p10_quantizer3_locality::audit {plan require_placed} {
    set name [dict get $plan pblock_name]
    set pblocks [get_pblocks -quiet $name]
    hap_v5_p5_input_partition::require_count quantizer3_pblock $pblocks 1
    set pblock [lindex $pblocks 0]
    if {![hap_v5_floorplan::property_is_false $pblock IS_SOFT] ||
        ![hap_v5_floorplan::property_is_false $pblock CONTAIN_ROUTING] ||
        ![hap_v5_floorplan::property_is_false $pblock EXCLUDE_PLACEMENT]} {
        error "P10 quantizer3 pblock policy mismatch"
    }
    set ranges [get_property GRID_RANGES $pblock]
    if {[llength $ranges] != 1 ||
        [lindex $ranges 0] ne [dict get $plan grid_range]} {
        error "P10 quantizer3 pblock range mismatch: $ranges"
    }

    set members [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::expanded_pblock_primitives $pblock]]
    set missing [hap_v5_floorplan::list_subtract \
        [dict get $plan primitives] $members]
    set extras [hap_v5_floorplan::list_subtract \
        $members [dict get $plan primitives]]
    if {[llength $missing] != 0 || [llength $extras] != 0} {
        error "P10 quantizer3 membership mismatch: missing=[llength $missing] extras=[llength $extras]"
    }

    set wrong 0
    set unplaced 0
    if {$require_placed} {
        set allowed [dict create]
        foreach region [dict get $plan allowed_regions] {
            dict set allowed $region 1
        }
        foreach cell [dict get $plan primitives] {
            set sites [get_sites -quiet -of_objects $cell]
            if {[llength $sites] != 1} {
                incr unplaced
                continue
            }
            set regions [get_clock_regions -quiet -of_objects $sites]
            if {[llength $regions] != 1 ||
                ![dict exists $allowed [get_property NAME $regions]]} {
                incr wrong
            }
        }
        if {$wrong != 0 || $unplaced != 0} {
            error "P10 quantizer3 placement mismatch: wrong=$wrong unplaced=$unplaced"
        }
    }
    return [dict create ok 1 require_placed $require_placed name $name \
        contract [dict get $plan contract] \
        grid_range [dict get $plan grid_range] \
        expected [llength [dict get $plan primitives]] \
        members [llength $members] missing [llength $missing] \
        extras [llength $extras] wrong $wrong unplaced $unplaced]
}

proc hap_v5_p10_quantizer3_locality::write_plan {plan path status} {
    set fp [open $path w]
    foreach key {contract root_name primitive_count lut ff pblock_name
            grid_range allowed_regions} {
        puts $fp "$key=[dict get $plan $key]"
    }
    foreach key {dsp uram ramb36 ramb18} {
        puts $fp "${key}=[dict get [dict get $plan hard] $key]"
    }
    puts $fp "status=$status"
    close $fp
}

proc hap_v5_p10_quantizer3_locality::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok require_placed name contract grid_range expected members
            missing extras wrong unplaced} {
        puts $fp "$key=[dict get $audit $key]"
    }
    puts $fp "status=$status"
    close $fp
}
