set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_attention_mlp_production_core
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set production_profile [expr {[info exists ::env(HAP_PRODUCTION_PROFILE)] ?
    $::env(HAP_PRODUCTION_PROFILE) : ""}]
set attention_board_module [expr {
    [info exists ::env(HAP_ATTENTION_BOARD_MODULE)] ?
    $::env(HAP_ATTENTION_BOARD_MODULE) : ""}]
set expected_manifest [file normalize [file join $root vivado manifests \
    attention_mlp_production_v5_cohort16_sources.list]]
set manifest [expr {[info exists ::env(HAP_PRODUCTION_MANIFEST)] ?
    [file normalize $::env(HAP_PRODUCTION_MANIFEST)] : ""}]
file mkdir $out
file mkdir $build

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "V5 production elaboration requires HAP_JOBS=32"
}
set_param general.maxThreads $jobs
if {$production_profile ne "cohort16"} {
    error "Explicit cohort16 production profile required"
}
if {$attention_board_module ne "hap_attention_board_cohort16_core"} {
    error "Illegal cohort16 Attention board module: $attention_board_module"
}
if {$manifest ne $expected_manifest} {
    error "Illegal cohort16 production manifest: $manifest"
}

proc add_manifest {root manifest} {
    set fh [open $manifest r]
    set body [read $fh]
    close $fh
    foreach raw [split $body "\n"] {
        set line [string trim $raw]
        if {$line eq "" || [string index $line 0] eq "#"} {continue}
        set path [file normalize [file join $root $line]]
        if {![file exists $path]} {error "Missing V5 source $path"}
        if {[string match "*.list" $path]} {
            add_manifest $root $path
            continue
        }
        if {[llength [get_files -quiet $path]] == 0} {
            add_files -fileset sources_1 $path
        }
        if {[string match "*.sv" $path]} {
            set_property file_type SystemVerilog [get_files $path]
        }
        if {[string match "*.mem" $path]} {
            set_property file_type {Memory Initialization Files} \
                [get_files $path]
        }
    }
}

proc cells_below_roots {roots candidates} {
    set result {}
    foreach cell $candidates {
        set cell_name [get_property NAME $cell]
        foreach root_cell $roots {
            set root_name [get_property NAME $root_cell]
            if {[string match "${root_name}/*" $cell_name]} {
                lappend result $cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

create_project production_v5_elaboration $build -part $part -force
set_property target_language Verilog [current_project]
set_property verilog_define {
    HAP_BOARD_BUILD
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s45
    HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core
} [get_filesets sources_1]
add_manifest $root $manifest
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
set_msg_config -id {Synth 8-324} -new_severity ERROR
synth_design -top $top -part $part -mode out_of_context -rtl \
    -flatten_hierarchy none

set old_serial [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_serial_ddr_command16_s45 ||
    REF_NAME == hap_mlp_serial_ddr_command16_s45
}]
set v5_serial [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_serial_ddr_command16_v5_s45 ||
    REF_NAME == hap_mlp_serial_ddr_command16_v5_s45
}]
set v5_shared [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_shared_dual_slice16x12_s43_s45 ||
    REF_NAME == hap_mlp_shared_dual_slice16x12_s43_s45
}]
set v5_local [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_shared_local_slice8x12_s43_s45 ||
    REF_NAME == hap_mlp_shared_local_slice8x12_s43_s45
}]
set v4_shared [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_shared_dual_slice16x16_s43_s45 ||
    REF_NAME == hap_mlp_shared_dual_slice16x16_s43_s45
}]
set v4_kernel [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w4_slice8x16_group_s36 ||
    REF_NAME == hap_a8w4_slice8x16_group_s36
}]
set v5_kernel [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w4_slice8x12_group_s36 ||
    REF_NAME == hap_a8w4_slice8x12_group_s36
}]
set history2_repack [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_projection_repack12_to16_s24_history2 ||
    REF_NAME == hap_mlp_projection_repack12_to16_s24_history2
}]
set generic_repack [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_projection_repack12_to16_s24 ||
    REF_NAME == hap_mlp_projection_repack12_to16_s24
}]
set swiglu_frontend [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_swiglu_product_frontend16_q4 ||
    REF_NAME == hap_mlp_swiglu_product_frontend16_q4
}]
set swiglu_row_leaf [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_swiglu_row_stream8_q4 ||
    REF_NAME == hap_mlp_swiglu_row_stream8_q4
}]
set swiglu_hadamard [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_hadamard32_s32_norm_stream ||
    REF_NAME == hap_mlp_hadamard32_s32_norm_stream
}]
set swiglu_fold2 [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_hadamard32_s32_norm_fold2 ||
    REF_NAME == hap_mlp_hadamard32_s32_norm_fold2
}]
set swiglu_quantizer [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_robust_a8_quantizer_s35 ||
    REF_NAME == hap_mlp_robust_a8_quantizer_s35
}]
set swiglu_silu [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_silu_mul ||
    REF_NAME == hap_mlp_silu_mul
}]
set attention_col3_array [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_array_16x16_s42_col3 ||
    REF_NAME == hap_a8w8_array_16x16_s42_col3
}]
set attention_old_array [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_array_16x16_s42 ||
    REF_NAME == hap_a8w8_array_16x16_s42
}]
set attention_left_shard [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_col_shard_left2_s42 ||
    REF_NAME == hap_a8w8_col_shard_left2_s42
}]
set attention_center_shard [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_col_shard_center12_s42 ||
    REF_NAME == hap_a8w8_col_shard_center12_s42
}]
set attention_right_shard [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_col_shard_right2_s42 ||
    REF_NAME == hap_a8w8_col_shard_right2_s42
}]
set attention_leaf_shards [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_col_shard_s42 ||
    REF_NAME == hap_a8w8_col_shard_s42
}]
set attention_cohort16_board [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_board_cohort16_core ||
    REF_NAME == hap_attention_board_cohort16_core
}]
set attention_legacy_board [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_board_core ||
    REF_NAME == hap_attention_board_core
}]
set attention_cohort16_compute [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_compute_cohort16_top ||
    REF_NAME == hap_attention_compute_cohort16_top
}]
set attention_legacy_compute [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_compute_top ||
    REF_NAME == hap_attention_compute_top
}]
set attention_projection16 [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_projection_core16x16_w8_reuse ||
    REF_NAME == hap_projection_core16x16_w8_reuse
}]
set attention_projection8 [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_projection_core8x16 ||
    REF_NAME == hap_projection_core8x16
}]
set attention_lanes [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_a8w8_group32_lane_s42 ||
    REF_NAME == hap_a8w8_group32_lane_s42
}]
set attention_dual_accumulators [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_linear_tile_accum_dual_s42 ||
    REF_NAME == hap_linear_tile_accum_dual_s42
}]
set attention_local_contexts [expr {2 *
    [llength $attention_dual_accumulators]}]
set compact_input_frontend [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_input_frontend16_compact_cache ||
    REF_NAME == hap_mlp_input_frontend16_compact_cache
}]
set down_activation_cache [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_down_activation_cache16 ||
    REF_NAME == hap_mlp_down_activation_cache16
}]
set gate_accums [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_tile_accum_s36 ||
    REF_NAME == hap_mlp_tile_accum_s36
}]
set down_accums [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_down_group_major_accum_s45 ||
    REF_NAME == hap_mlp_down_group_major_accum_s45
}]
set down_elastic2 [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_down_branch_elastic2_s24 ||
    REF_NAME == hap_mlp_down_branch_elastic2_s24
}]
set attention_center_subshards \
    [cells_below_roots $attention_center_shard $attention_leaf_shards]

# The macro intentionally gives the V5 full wrapper the frozen V4 module name.
# Its unique descendants are the unambiguous implementation identity gate.
set status [expr {
    [llength $old_serial] == 0 &&
    [llength $v5_serial] == 1 &&
    [llength $v5_shared] == 1 &&
    [llength $v5_local] == 2 &&
    [llength $v4_shared] == 0 &&
    [llength $v4_kernel] == 0 &&
    [llength $v5_kernel] == 2 &&
    [llength $history2_repack] == 2 &&
    [llength $generic_repack] == 0 &&
    [llength $swiglu_frontend] == 1 &&
    [llength $swiglu_row_leaf] == 2 &&
    [llength $swiglu_hadamard] == 1 &&
    [llength $swiglu_fold2] == 0 &&
    [llength $swiglu_quantizer] == 4 &&
    [llength $swiglu_silu] == 2 &&
    [llength $attention_cohort16_board] == 1 &&
    [llength $attention_legacy_board] == 0 &&
    [llength $attention_cohort16_compute] == 1 &&
    [llength $attention_legacy_compute] == 0 &&
    [llength $attention_projection16] == 1 &&
    [llength $attention_projection8] == 0 &&
    [llength $attention_lanes] == 128 &&
    [llength $attention_dual_accumulators] == 6 &&
    $attention_local_contexts == 12 &&
    [llength $attention_col3_array] == 1 &&
    [llength $attention_old_array] == 0 &&
    [llength $attention_left_shard] == 1 &&
    [llength $attention_center_shard] == 1 &&
    [llength $attention_right_shard] == 1 &&
    [llength $attention_center_subshards] == 4 &&
    [llength $attention_leaf_shards] == 6 &&
    [llength $compact_input_frontend] == 1 &&
    [llength $down_activation_cache] == 1 &&
    [llength $gate_accums] == 2 &&
    [llength $down_accums] == 2 &&
    [llength $down_elastic2] == 2 ?
    "V5_PRODUCTION_ELABORATION_PASS" : "FAIL"
}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part top $top jobs $jobs manifest $manifest \
    production_profile $production_profile \
    attention_board_module $attention_board_module \
    attention_cohort16_board_instances [llength $attention_cohort16_board] \
    attention_legacy_board_instances [llength $attention_legacy_board] \
    attention_cohort16_compute_instances [llength $attention_cohort16_compute] \
    attention_legacy_compute_instances [llength $attention_legacy_compute] \
    attention_projection16_instances [llength $attention_projection16] \
    attention_projection8_instances [llength $attention_projection8] \
    attention_lane_instances [llength $attention_lanes] \
    attention_dual_accumulator_instances \
        [llength $attention_dual_accumulators] \
    attention_local_accumulator_contexts $attention_local_contexts \
    old_serial_instances [llength $old_serial] \
    v5_serial_instances [llength $v5_serial] \
    v5_shared_dual_instances [llength $v5_shared] \
    v5_local_branch_instances [llength $v5_local] \
    v4_shared_dual_instances [llength $v4_shared] \
    v4_kernel16_instances [llength $v4_kernel] \
    v5_kernel12_instances [llength $v5_kernel] \
    history2_repack_instances [llength $history2_repack] \
    generic_repack_instances [llength $generic_repack] \
    swiglu_frontend_instances [llength $swiglu_frontend] \
    swiglu_row_leaf_instances [llength $swiglu_row_leaf] \
    swiglu_unique_hadamard_instances [llength $swiglu_hadamard] \
    swiglu_fold2_hadamard_instances [llength $swiglu_fold2] \
    swiglu_quantizer_instances [llength $swiglu_quantizer] \
    swiglu_silu_instances [llength $swiglu_silu] \
    attention_col3_array_instances [llength $attention_col3_array] \
    attention_old_array_instances [llength $attention_old_array] \
    attention_left2_shard_instances [llength $attention_left_shard] \
    attention_center12_shard_instances [llength $attention_center_shard] \
    attention_right2_shard_instances [llength $attention_right_shard] \
    attention_center_subshard_instances [llength $attention_center_subshards] \
    attention_leaf_shard_instances [llength $attention_leaf_shards] \
    compact_input_frontend_instances [llength $compact_input_frontend] \
    down_activation_cache_instances [llength $down_activation_cache] \
    gate_accum_instances [llength $gate_accums] \
    down_accum_instances [llength $down_accums] \
    down_elastic2_instances [llength $down_elastic2] status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "V5_PRODUCTION_ELABORATION OLD_SERIAL=[llength $old_serial] V5_SERIAL=[llength $v5_serial] V5_SHARED=[llength $v5_shared] V5_LOCAL=[llength $v5_local] V4_KERNEL=[llength $v4_kernel] V5_KERNEL=[llength $v5_kernel] HISTORY2=[llength $history2_repack] GENERIC_REPACK=[llength $generic_repack] SWIGLU=[llength $swiglu_frontend]/[llength $swiglu_row_leaf]/[llength $swiglu_hadamard]/[llength $swiglu_fold2]/[llength $swiglu_quantizer]/[llength $swiglu_silu] STATUS=$status"
if {$status ne "V5_PRODUCTION_ELABORATION_PASS"} {
    error "V5 production hierarchy identity gate failed"
}
close_project
