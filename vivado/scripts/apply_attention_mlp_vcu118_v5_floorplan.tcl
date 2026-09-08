# Full-board pre-place hook. Apply the same P7 physical contract that must
# first pass the production-core OOC route gate. P7 retains P5 input locality,
# P6's 4/8/4 postprocess split and the Attention region2 row split.
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir v5_production_floorplan_selectors.tcl]
source [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
source [file join $script_dir v5_production_p5_input_partition_floorplan.tcl]
source [file join $script_dir \
    v5_production_p6_postprocess_partition_floorplan.tcl]

set ::hap_v5_floorplan::expected_top attention_mlp_vcu118_v5_bd_wrapper
set base_contract P2_COHORT16_COL2_12_2
set p5_contract P5_INPUT_HALF_LOCAL_8_8
set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4
set p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8
set geometry_prefix p3_
set region2_variant rowsplit_y5_y6_y6_y8

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
set p6_plan [hap_v5_p6_postprocess_partition::discover $plan $p5_plan]

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
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0 \
    $region2_variant
hap_v5_p5_input_partition::apply $p5_plan
hap_v5_p6_postprocess_partition::apply $p6_plan

set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1 $region2_variant]
set base_audit [hap_v5_floorplan::audit_pblock_contract \
    $plan 0 $base_contract \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix \
        $region2_variant]]
set p5_audit [hap_v5_p5_input_partition::audit $p5_plan 0]
set p6_audit [hap_v5_p6_postprocess_partition::audit $p6_plan 0]
set expected_center_extras [expr {
    [llength [dict get $p5_plan center_base_extras]] +
    [llength [dict get $p6_plan center_rows]]}]
if {[dict get $p5_plan contract] ne $p5_contract ||
    [dict get $p6_plan contract] ne $p6_contract ||
    [dict get $geometry_audit pblock_count] != 12 ||
    [dict get $geometry_plan center_region2_row_exact_cover] != 1 ||
    [llength [dict get $geometry_plan \
        center_region2_rows0_3_primitives]] != 26800 ||
    [llength [dict get $geometry_plan \
        center_region2_rows4_7_primitives]] != 26800 ||
    [llength [dict get $geometry_plan \
        center_region2_residual_primitives]] != 15199 ||
    [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
        center_region2_rows0_3_primitives] DSP48E2] != 272 ||
    [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
        center_region2_rows4_7_primitives] DSP48E2] != 272 ||
    [hap_projection_ooc_floorplan::count_ref [dict get $geometry_plan \
        center_region2_residual_primitives] DSP48E2] != 0 ||
    ![dict get $base_audit ok] ||
    [dict get $base_audit pblock_count] != 11 ||
    [dict get $base_audit optimizer_extra_count] != $expected_center_extras ||
    [dict get $base_audit dsp_coverage] != 5453 ||
    [dict get $base_audit uram_coverage] != 752 ||
    ![dict get $p5_audit ok] ||
    [dict get $p5_audit pblock_count] != 2 ||
    [dict get $p5_audit outer_extras] != 0 ||
    ![dict get $p6_audit ok] ||
    [dict get $p6_audit pblock_count] != 2 ||
    [dict get $p6_audit outer_extras] != 0 ||
    [llength [get_pblocks -quiet]] != 27} {
    error "V5 board P7 pre-place physical contract mismatch"
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
hap_v5_p6_postprocess_partition::write_plan $p6_plan \
    [file join $run_dir v5_board_p6_postprocess_plan_pre_place.txt] \
    V5_BOARD_P6_POSTPROCESS_PLAN_PRE_PLACE_PASS
hap_v5_p6_postprocess_partition::write_audit $p6_audit \
    [file join $run_dir v5_board_p6_postprocess_pblocks_pre_place.txt] \
    V5_BOARD_P6_POSTPROCESS_PBLOCK_PRE_PLACE_PASS
