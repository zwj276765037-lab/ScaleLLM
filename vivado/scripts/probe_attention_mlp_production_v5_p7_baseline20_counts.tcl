foreach variable {HAP_DCP HAP_P7_PROBE_DIR HAP_P7_INPUT_SHA
        HAP_P7_INPUT_MANIFEST_SHA256 HAP_EXPECTED_DCP_SHA256
        HAP_SELECTOR_LIB HAP_FINE19_LIB HAP_COMPOSITE20_LIB} {
    if {![info exists ::env($variable)] || $::env($variable) eq ""} {
        error "Missing required environment variable: $variable"
    }
}

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_P7_PROBE_DIR)]
set input_sha [file normalize $::env(HAP_P7_INPUT_SHA)]
set expected_manifest_sha $::env(HAP_P7_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set selector_lib [file normalize $::env(HAP_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_FINE19_LIB)]
set composite_lib [file normalize $::env(HAP_COMPOSITE20_LIB)]
set p8_discovery [expr {[info exists ::env(HAP_P8_DISCOVERY)] &&
    $::env(HAP_P8_DISCOVERY) eq "1"}]

proc p7_sha256 {path} {
    return [lindex [exec sha256sum -- $path] 0]
}

proc p7_verify_manifest {path expected_sha} {
    if {[p7_sha256 $path] ne $expected_sha} {
        error "P7 baseline20 input-manifest identity mismatch"
    }
    set entries 0
    foreach raw [split [read [set fp [open $path r]]] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed P7 baseline20 input-manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {![file exists $normalized] || [file size $normalized] == 0 ||
            [p7_sha256 $normalized] ne $expected} {
            error "P7 baseline20 frozen input mismatch: $normalized"
        }
        incr entries
    }
    close $fp
    return $entries
}

proc p7_count_ref_glob {cells pattern} {
    set count 0
    foreach ref_name [get_property REF_NAME $cells] {
        if {[string match $pattern $ref_name]} {incr count}
    }
    return $count
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P7 baseline20 probe requires a fresh Vivado process"
}
set manifest_entries [p7_verify_manifest $input_sha $expected_manifest_sha]
if {[p7_sha256 $dcp] ne $expected_dcp_sha} {
    error "P7 baseline20 DCP identity mismatch"
}

source $selector_lib
source $fine_lib
source $composite_lib
open_checkpoint $dcp
if {[llength [get_pblocks -quiet]] != 0} {
    error "P7 baseline20 input unexpectedly contains pblocks"
}

set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set fine_plan [hap_v5_fine19::discover $base_plan $p8_discovery]
set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan 1]
set specs [hap_v5_composite21::full_specs \
    $base_plan $fine_plan $composite_plan]
set spec_members [hap_v5_composite21::spec_member_union $specs]
set attention_direct [dict get $composite_plan attention_direct_primitives]
set hard_slr_lut {0 0 0}
set hard_slr_ff {0 0 0}
set hard_slr_ramb36 {0 0 0}
set hard_slr_ramb18 {0 0 0}
foreach spec $specs {
    set target [dict get $spec target]
    set cells [hap_v5_fine19::pblockable [dict get $spec cells]]
    lset hard_slr_lut $target [expr {[lindex $hard_slr_lut $target] +
        [p7_count_ref_glob $cells LUT*]}]
    lset hard_slr_ff $target [expr {[lindex $hard_slr_ff $target] +
        [p7_count_ref_glob $cells FD*]}]
    lset hard_slr_ramb36 $target [expr {
        [lindex $hard_slr_ramb36 $target] +
        [hap_v5_floorplan::count_ref $cells RAMB36E2]}]
    lset hard_slr_ramb18 $target [expr {
        [lindex $hard_slr_ramb18 $target] +
        [hap_v5_floorplan::count_ref $cells RAMB18E2]}]
}

set query_roots [hap_v5_floorplan::module_cells \
    hap_attention_cohort16_query_store]
set postprocess_roots [hap_v5_floorplan::module_cells \
    hap_attention_cohort16_postprocess_store]
set context_roots [hap_v5_floorplan::module_cells \
    hap_attention_cohort16_context_store]
hap_v5_composite21::require_count query_roots $query_roots 1
hap_v5_composite21::require_count postprocess_roots $postprocess_roots 1
hap_v5_composite21::require_count context_roots $context_roots 1
set query_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $query_roots 0]]
set postprocess_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $postprocess_roots 0]]
set context_primitives [hap_v5_fine19::pblockable_descendants \
    [lindex $context_roots 0]]
set owner_union [hap_v5_floorplan::list_union $query_primitives \
    $postprocess_primitives $context_primitives]
set owner_member_sum [expr {[llength $query_primitives] +
    [llength $postprocess_primitives] + [llength $context_primitives]}]
set owner_overlap [expr {$owner_member_sum - [llength $owner_union]}]
set owner_outside_attention [hap_v5_floorplan::list_subtract \
    $owner_union $attention_direct]
set owner_inside_hard [hap_v5_floorplan::list_intersection \
    $owner_union $spec_members]

set all_design_primitives [hap_v5_fine19::pblockable \
    [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE}]]
set flexible_residual [hap_v5_floorplan::list_subtract \
    $all_design_primitives $spec_members]
set flexible_residual_lut [p7_count_ref_glob $flexible_residual LUT*]
set outer_90pct_lut_headroom [expr {
    2 * int(394080 * 0.90) - [lindex $hard_slr_lut 0] -
    [lindex $hard_slr_lut 2]}]
set all_dsp [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set all_uram [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]
set all_ramb36 [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]

set expected_fine_members 1432847
set expected_mlp_residual_members 285796
set expected_attention_direct_members 71350

set structural_ok [expr {
    [llength $specs] == 20 &&
    [dict get $composite_plan owner_overlap] == 0 &&
    [dict get $composite_plan hard_resource_intrusion] == 0 &&
    [dict get $composite_plan attention_direct_constrained] == 0 &&
    $owner_overlap == 0 &&
    [llength $owner_outside_attention] == 0 &&
    [llength $owner_inside_hard] == 0 &&
    [llength $all_dsp] == 5453 &&
    [llength $all_uram] == 752 &&
    [llength $all_ramb36] == 801 &&
    [llength [get_pblocks -quiet]] == 0
}]
set counts_exact [expr {
    [dict get $composite_plan fine_member_count] ==
        $expected_fine_members &&
    [dict get $composite_plan mlp_residual_count] ==
        $expected_mlp_residual_members &&
    [dict get $composite_plan attention_direct_count] ==
        $expected_attention_direct_members
}]
set pass_marker [expr {$p8_discovery ?
    "P8_BASELINE20_DISCOVERY_PASS" : "P8_BASELINE20_COUNTS_PASS"}]
set status [expr {$structural_ok && ($p8_discovery || $counts_exact) ?
    $pass_marker : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
        tool [version -short] part [get_property PART [current_design]] \
        top [get_property TOP [current_design]] \
        stage [expr {$p8_discovery ? "P8_BASELINE20_READ_ONLY_DISCOVERY" :
            "P7_BASELINE20_READ_ONLY_COUNTS"}] \
        evidence_class DIAGNOSTIC_NO_FLOORPLAN_MUTATION \
        p8_discovery $p8_discovery structural_ok $structural_ok \
        baseline_counts_exact $counts_exact \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_manifest_sha \
        input_manifest_entries $manifest_entries \
        inherited_contract_variant [dict get $composite_plan contract_variant] \
        fine_optimizer_extra_count [dict get $fine_plan optimizer_extra_count] \
        projection_primitive_count \
            [llength [dict get $fine_plan projection_primitives]] \
        projection_frontend_primitive_count \
            [llength [dict get $fine_plan frontend_primitives]] \
        projection_left_primitive_count \
            [llength [dict get $fine_plan left_primitives]] \
        projection_center_primitive_count \
            [llength [dict get $fine_plan center_primitives]] \
        projection_right_primitive_count \
            [llength [dict get $fine_plan right_primitives]] \
        center_region0_primitive_count \
            [llength [dict get $fine_plan center_region0_primitives]] \
        center_region1_primitive_count \
            [llength [dict get $fine_plan center_region1_primitives]] \
        center_region1_logic_primitive_count \
            [llength [dict get $fine_plan \
                center_region1_logic_residual_primitives]] \
        center_region2_primitive_count \
            [llength [dict get $fine_plan center_region2_primitives]] \
        center_region3_primitive_count \
            [llength [dict get $fine_plan center_region3_primitives]] \
        expected_fine_member_count $expected_fine_members \
        expected_mlp_residual_count $expected_mlp_residual_members \
        expected_attention_direct_count $expected_attention_direct_members \
        pblock_spec_count [llength $specs] \
        fine_member_count [dict get $composite_plan fine_member_count] \
        fine_member_delta [dict get $composite_plan fine_member_delta] \
        mlp_residual_count [dict get $composite_plan mlp_residual_count] \
        mlp_residual_delta [dict get $composite_plan mlp_residual_delta] \
        attention_direct_count [dict get $composite_plan attention_direct_count] \
        attention_direct_delta [dict get $composite_plan attention_direct_delta] \
        hard_member_count [llength $spec_members] \
        flexible_residual_count [llength $flexible_residual] \
        flexible_residual_lut $flexible_residual_lut \
        flexible_residual_ff [p7_count_ref_glob $flexible_residual FD*] \
        hard_slr0_lut [lindex $hard_slr_lut 0] \
        hard_slr1_lut [lindex $hard_slr_lut 1] \
        hard_slr2_lut [lindex $hard_slr_lut 2] \
        hard_slr0_ff [lindex $hard_slr_ff 0] \
        hard_slr1_ff [lindex $hard_slr_ff 1] \
        hard_slr2_ff [lindex $hard_slr_ff 2] \
        hard_slr0_ramb36 [lindex $hard_slr_ramb36 0] \
        hard_slr1_ramb36 [lindex $hard_slr_ramb36 1] \
        hard_slr2_ramb36 [lindex $hard_slr_ramb36 2] \
        hard_slr0_ramb18 [lindex $hard_slr_ramb18 0] \
        hard_slr1_ramb18 [lindex $hard_slr_ramb18 1] \
        hard_slr2_ramb18 [lindex $hard_slr_ramb18 2] \
        outer_90pct_lut_headroom $outer_90pct_lut_headroom \
        flexible_outer_90pct_fit \
            [expr {$outer_90pct_lut_headroom >= $flexible_residual_lut}] \
        query_store_pblockable_primitives [llength $query_primitives] \
        postprocess_store_pblockable_primitives \
            [llength $postprocess_primitives] \
        context_store_pblockable_primitives [llength $context_primitives] \
        local_store_union_primitives [llength $owner_union] \
        local_store_owner_overlap $owner_overlap \
        local_store_outside_attention_direct \
            [llength $owner_outside_attention] \
        local_store_inside_hard_members [llength $owner_inside_hard] \
        dsp48e2 [llength $all_dsp] uram288 [llength $all_uram] \
        ramb36e2 [llength $all_ramb36] canonical_pblock_count 0 \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "BASELINE20_COUNTS STATUS=$status ATTENTION=[dict get $composite_plan attention_direct_count] DELTA=[dict get $composite_plan attention_direct_delta] OWNERS=[llength $query_primitives]/[llength $postprocess_primitives]/[llength $context_primitives]"
if {$status ne $pass_marker} {
    error "Baseline20 read-only count probe failed"
}
close_design
