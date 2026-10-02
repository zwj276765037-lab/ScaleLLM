# Reuse the P9 quantizer3 locality policy while binding primitive counts to
# the authenticated no-clip production DCP instead of the legacy robust netlist.

set p16_quantizer3_script_dir [file dirname [file normalize [info script]]]
source [file join $p16_quantizer3_script_dir \
    v5_production_p9_quantizer3_locality_floorplan.tcl]

proc hap_v5_p9_quantizer3_locality::discover {base_plan p5_plan post_plan} {
    variable contract
    variable pblock_name
    variable grid_range
    variable allowed_regions
    set signature_source \
        [hap_projection_ooc_floorplan::get_region2_signature_source]
    if {![regexp {^P16_(PRODUCTION_)?POST_OPT_SHA256:[0-9a-f]{64}$} \
            $signature_source]} {
        error "P16 no-clip quantizer3 requires fresh P16 provenance"
    }
    if {[dict get $base_plan contract_variant] ne
            "P2_COHORT16_COL2_12_2" ||
        [dict get $p5_plan contract] ne "P5_INPUT_HALF_LOCAL_8_8" ||
        [dict get $post_plan contract] ne "P9_POSTPROCESS_SPLIT_6_4_6"} {
        error "P16 no-clip quantizer3 requires canonical base/P5/P9 plans"
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
    if {[llength $primitives] == 0 || $lut == 0 || $ff == 0 ||
        [dict get $hard dsp] != 0 || [dict get $hard uram] != 0 ||
        [dict get $hard ramb36] != 0 || [dict get $hard ramb18] != 0} {
        error "P16 no-clip quantizer3 signature mismatch: primitives=[llength $primitives] LUT=$lut FF=$ff hard=$hard"
    }

    set p5_cells [hap_v5_floorplan::list_union \
        [dict get $p5_plan half0_primitives] \
        [dict get $p5_plan half1_primitives] \
        [dict get $p5_plan center_primitives]]
    if {[llength [hap_v5_floorplan::list_intersection $primitives \
            $p5_cells]] != 0 ||
        [llength [hap_v5_floorplan::list_intersection $primitives \
            [dict get $post_plan all_rows]]] != 0} {
        error "P16 no-clip quantizer3 overlaps an existing P5/P9 partition"
    }

    return [dict create contract $contract root $root \
        root_name [get_property NAME $root] primitives $primitives \
        primitive_count [llength $primitives] lut $lut ff $ff hard $hard \
        pblock_name $pblock_name grid_range $grid_range \
        allowed_regions $allowed_regions signature_source $signature_source]
}
