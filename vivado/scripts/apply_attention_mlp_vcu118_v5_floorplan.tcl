# Full-board pre-place hook. Apply the same P14 physical contract that must
# first pass the production-core OOC route gate: P5 input locality, P9 6/4/6
# postprocess partitioning, P9 quantizer3 locality and same-SLR region2 relief.
set script_dir [file dirname [file normalize [info script]]]
set rtl_variant [expr {[info exists ::env(HAP_BOARD_RTL_VARIANT)] ?
    $::env(HAP_BOARD_RTL_VARIANT) : "P14_LEGACY"}]
set expected_quantizer3_primitives 11178
set expected_region2_primitives 68799
set expected_total_dsp [expr {
    $rtl_variant eq "P16_NOCLIP" ? 5449 : 5453}]
if {$rtl_variant eq "P16_NOCLIP"} {
    foreach variable {HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES
            HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES HAP_P16_POST_OPT_SUMMARY
            HAP_P16_POST_OPT_SUMMARY_SHA256
            HAP_P16_PRODUCTION_REGION2_SUMMARY
            HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
            HAP_P16_PRODUCTION_DCP_SHA256} {
        if {![info exists ::env($variable)] || $::env($variable) eq ""} {
            error "P16 no-clip board floorplan requires $variable"
        }
    }
    set expected_quantizer3_primitives \
        $::env(HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES)
    set expected_region2_primitives \
        $::env(HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES)
}
if {$rtl_variant ni {P14_LEGACY P16_NOCLIP} ||
    ![string is integer -strict $expected_quantizer3_primitives] ||
    $expected_quantizer3_primitives <= 0 ||
    ![string is integer -strict $expected_region2_primitives] ||
    $expected_region2_primitives <= 0} {
    error "invalid V5 board RTL variant or primitive contract"
}
source [file join $script_dir v5_production_floorplan_selectors.tcl]
if {$rtl_variant eq "P16_NOCLIP"} {
    source [file join $script_dir \
        projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl]
} else {
    source [file join $script_dir \
        projection_core16x16_w8_reuse_ooc_floorplan.tcl]
}
source [file join $script_dir v5_production_p5_input_partition_floorplan.tcl]
source [file join $script_dir \
    v5_production_p9_postprocess_partition_floorplan.tcl]
if {$rtl_variant eq "P16_NOCLIP"} {
    source [file join $script_dir \
        v5_production_p16_noclip_quantizer3_locality_floorplan.tcl]
    source [file join $script_dir \
        v5_production_p16_noclip_region2_x2_relief_floorplan.tcl]
} else {
    source [file join $script_dir \
        v5_production_p9_quantizer3_locality_floorplan.tcl]
    source [file join $script_dir \
        v5_production_p14_region2_x2_relief_floorplan.tcl]
}
if {$rtl_variant eq "P16_NOCLIP" &&
    [hap_projection_ooc_floorplan::get_region2_signature_source] ne
        "P16_PRODUCTION_POST_OPT_SHA256:$::env(HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256)"} {
    error "P16 no-clip board floorplan signature provenance mismatch"
}

set ::hap_v5_floorplan::expected_top attention_mlp_vcu118_v5_bd_wrapper
set base_contract P2_COHORT16_COL2_12_2
set p5_contract P5_INPUT_HALF_LOCAL_8_8
set p9_postprocess_contract P9_POSTPROCESS_SPLIT_6_4_6
set p9_quantizer3_contract P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
set p14_region2_relief_contract P14_ATTN_REGION2_SHARED_X0_X2
set geometry_prefix p3_

proc hap_v5_board_create_hard_slr_pblock {name target cells} {
    if {[llength $cells] == 0 || [llength [get_pblocks -quiet $name]] != 0} {
        error "V5 board invalid canonical pblock: $name"
    }
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] $cells
    resize_pblock [get_pblocks $name] -add [list SLR${target}]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

set plan [hap_v5_floorplan::discover $base_contract]
set projection_root [file dirname \
    [get_property NAME [dict get $plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set p5_plan [hap_v5_p5_input_partition::discover $plan]
set p9_postprocess_plan \
    [hap_v5_p9_postprocess_partition::discover $plan $p5_plan]
set p9_quantizer3_plan [hap_v5_p9_quantizer3_locality::discover \
    $plan $p5_plan $p9_postprocess_plan]
set p14_relief_plan \
    [hap_v5_p14_region2_relief::discover $geometry_plan]

set compute_nets [get_nets -quiet -hierarchical -filter {
    NAME =~ u_compute/* || NAME =~ */u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "V5 board compute-net selector is empty"
}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "V5 board compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
}

foreach spec [hap_v5_floorplan::pblock_specs $plan $base_contract] {
    hap_v5_board_create_hard_slr_pblock [dict get $spec name] \
        [dict get $spec target] [dict get $plan [dict get $spec key]]
}
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0
hap_v5_p5_input_partition::apply $p5_plan
hap_v5_p9_postprocess_partition::apply $p9_postprocess_plan
hap_v5_p9_quantizer3_locality::apply $p9_quantizer3_plan
hap_v5_p14_region2_relief::apply $p14_relief_plan

set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1 shared \
    [hap_v5_p14_region2_relief::range_overrides $p14_relief_plan]]
set base_delegate_specs [concat \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix] \
    [list [dict create name [dict get $p9_quantizer3_plan pblock_name] \
        target 1]]]
set base_audit [hap_v5_floorplan::audit_pblock_contract \
    $plan 0 $base_contract $base_delegate_specs]
set p5_audit [hap_v5_p5_input_partition::audit $p5_plan 0]
set p9_postprocess_audit \
    [hap_v5_p9_postprocess_partition::audit $p9_postprocess_plan 0]
set p9_quantizer3_audit \
    [hap_v5_p9_quantizer3_locality::audit $p9_quantizer3_plan 0]
set p14_relief_audit \
    [hap_v5_p14_region2_relief::audit $p14_relief_plan 0]
set expected_center_extras [expr {
    [llength [dict get $p5_plan center_base_extras]] +
    [llength [dict get $p9_postprocess_plan center_rows]]}]
if {[dict get $p5_plan contract] ne $p5_contract ||
    [dict get $p9_postprocess_plan contract] ne $p9_postprocess_contract ||
    [dict get $p9_quantizer3_plan contract] ne $p9_quantizer3_contract ||
    [dict get $p14_relief_plan contract] ne $p14_region2_relief_contract ||
    [dict get $plan rtl_resource_variant] ne $rtl_variant ||
    [dict get $plan total_dsp] != $expected_total_dsp ||
    [dict get $plan total_uram] != 752 ||
    [dict get $plan kernel_dsp] != 3072 ||
    [dict get $plan history2_count] != 2 ||
    [dict get $plan generic_repack_count] != 0 ||
    [dict get $plan projection_weight_capture_ok] != 1 ||
    [dict get $geometry_audit pblock_count] != 10 ||
    ![dict get $base_audit ok] ||
    [dict get $base_audit pblock_count] != 11 ||
    [dict get $base_audit optimizer_extra_count] != $expected_center_extras ||
    [dict get $base_audit dsp_coverage] != $expected_total_dsp ||
    [dict get $base_audit uram_coverage] != 752 ||
    ![dict get $p5_audit ok] ||
    [dict get $p5_audit pblock_count] != 2 ||
    [dict get $p5_audit outer_extras] != 0 ||
    ![dict get $p9_postprocess_audit ok] ||
    [dict get $p9_postprocess_audit pblock_count] != 2 ||
    [dict get $p9_postprocess_audit outer_extras] != 0 ||
    ![dict get $p9_quantizer3_audit ok] ||
    [dict get $p9_quantizer3_audit missing] != 0 ||
    [dict get $p9_quantizer3_audit extras] != 0 ||
    [dict get $p9_quantizer3_plan primitive_count] !=
        $expected_quantizer3_primitives ||
    [dict get $p9_quantizer3_plan grid_range] ne
        CLOCKREGION_X2Y5:CLOCKREGION_X3Y6 ||
    ![dict get $p14_relief_audit ok] ||
    [dict get $p14_relief_audit missing] != 0 ||
    [dict get $p14_relief_plan primitive_count] !=
        $expected_region2_primitives ||
    [dict get $p14_relief_plan base_range] ne
        CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 ||
    [dict get $p14_relief_plan relief_range] ne
        CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 ||
    [dict get $p14_relief_plan expected_range] ne
        CLOCKREGION_X0Y5:CLOCKREGION_X2Y9 ||
    [llength [dict get $p9_postprocess_plan slr0_rows]] != 16044 ||
    [llength [dict get $p9_postprocess_plan center_rows]] != 10696 ||
    [llength [dict get $p9_postprocess_plan slr2_rows]] != 16044 ||
    [llength [get_pblocks -quiet]] != 26} {
    error "V5 board P14 pre-place physical contract mismatch"
}

set run_dir [get_property DIRECTORY [current_run]]
hap_v5_floorplan::write_discovery $plan \
    [file join $run_dir v5_board_floorplan_discovery.txt] \
    V5_BOARD_FLOORPLAN_APPLIED
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $run_dir v5_board_attention_geometry_pre_place.txt] \
    V5_BOARD_ATTENTION_GEOMETRY_PRE_PLACE_PASS
hap_v5_floorplan::write_pblock_audit $base_audit \
    [file join $run_dir v5_board_base_pblocks_pre_place.txt] \
    V5_BOARD_BASE_PBLOCK_PRE_PLACE_PASS
hap_v5_p5_input_partition::write_plan $p5_plan \
    [file join $run_dir v5_board_p5_input_plan_pre_place.txt] \
    V5_BOARD_P5_INPUT_PLAN_PRE_PLACE_PASS
hap_v5_p5_input_partition::write_audit $p5_audit \
    [file join $run_dir v5_board_p5_input_pblocks_pre_place.txt] \
    V5_BOARD_P5_INPUT_PBLOCK_PRE_PLACE_PASS
hap_v5_p9_postprocess_partition::write_plan $p9_postprocess_plan \
    [file join $run_dir v5_board_p9_postprocess_plan_pre_place.txt] \
    V5_BOARD_P9_POSTPROCESS_PLAN_PRE_PLACE_PASS
hap_v5_p9_postprocess_partition::write_audit $p9_postprocess_audit \
    [file join $run_dir v5_board_p9_postprocess_pblocks_pre_place.txt] \
    V5_BOARD_P9_POSTPROCESS_PBLOCK_PRE_PLACE_PASS
hap_v5_p9_quantizer3_locality::write_plan $p9_quantizer3_plan \
    [file join $run_dir v5_board_p9_quantizer3_plan_pre_place.txt] \
    V5_BOARD_P9_QUANTIZER3_PLAN_PRE_PLACE_PASS
hap_v5_p9_quantizer3_locality::write_audit $p9_quantizer3_audit \
    [file join $run_dir v5_board_p9_quantizer3_pblock_pre_place.txt] \
    V5_BOARD_P9_QUANTIZER3_PBLOCK_PRE_PLACE_PASS
hap_v5_p14_region2_relief::write_plan $p14_relief_plan \
    [file join $run_dir v5_board_p14_region2_relief_plan_pre_place.txt] \
    V5_BOARD_P14_REGION2_RELIEF_PLAN_PRE_PLACE_PASS
hap_v5_p14_region2_relief::write_audit $p14_relief_audit \
    [file join $run_dir v5_board_p14_region2_relief_pblock_pre_place.txt] \
    V5_BOARD_P14_REGION2_RELIEF_PBLOCK_PRE_PLACE_PASS
