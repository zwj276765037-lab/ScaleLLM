set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set project_file [file normalize $::env(HAP_PROJECT_FILE)]
set out [file normalize $::env(HAP_REPORT_DIR)]
set xdc_inventory [file normalize $::env(HAP_XDC_INVENTORY)]
set ooc_route_artifact [file normalize $::env(HAP_OOC_ROUTE_DIR)]
set input_sha_manifest [file normalize $::env(HAP_INPUT_SHA_MANIFEST)]
set input_files [file normalize $::env(HAP_INPUT_FILES)]
set expected_input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set immutable_input_sha_manifest \
    [file normalize $::env(HAP_IMMUTABLE_INPUT_SHA_MANIFEST)]
set immutable_input_files \
    [file normalize $::env(HAP_IMMUTABLE_INPUT_FILES)]
set expected_immutable_input_manifest_sha \
    $::env(HAP_IMMUTABLE_INPUT_MANIFEST_SHA256)
set expected_recursive_source_manifest_sha \
    $::env(HAP_RECURSIVE_SOURCE_MANIFEST_SHA256)
set expected_ooc_authorization_manifest_sha \
    $::env(HAP_OOC_ROUTE_AUTHORIZATION_MANIFEST_SHA256)
set source_sha_manifest \
    [file normalize $::env(HAP_RECURSIVE_SOURCE_SHA_MANIFEST)]
set ooc_route_sha_manifest \
    [file normalize $::env(HAP_OOC_ROUTE_AUTHORIZATION_SHA_MANIFEST)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set place_directive [expr {[info exists ::env(HAP_BOARD_PLACE_DIRECTIVE)] ?
    $::env(HAP_BOARD_PLACE_DIRECTIVE) : "SSI_SpreadLogic_high"}]
set route_directive [expr {[info exists ::env(HAP_BOARD_ROUTE_DIRECTIVE)] ?
    $::env(HAP_BOARD_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
set rtl_variant [expr {[info exists ::env(HAP_BOARD_RTL_VARIANT)] ?
    $::env(HAP_BOARD_RTL_VARIANT) : "P14_LEGACY"}]
set place_input_manifest_entries 14
set expected_quantizer3_primitives 11178
set expected_relief_primitives 68799
set expected_total_dsp 5453
set expected_slr_dsp {1862 1781 1810}
set p16_post_opt_summary ""
set expected_p16_post_opt_summary_sha ""
set p16_production_region2_summary ""
set expected_p16_production_region2_summary_sha ""
set expected_p16_production_dcp_sha ""
set expected_board_input_count 134
set expected_board_immutable_input_count 133
set expected_ooc_route_input_count 33
if {$rtl_variant eq "P16_NOCLIP"} {
    foreach variable {HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES
            HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES HAP_P16_POST_OPT_SUMMARY
            HAP_P16_POST_OPT_SUMMARY_SHA256
            HAP_P16_PRODUCTION_REGION2_SUMMARY
            HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
            HAP_P16_PRODUCTION_DCP_SHA256} {
        if {![info exists ::env($variable)] || $::env($variable) eq ""} {
            error "P16 no-clip board build requires $variable"
        }
    }
    set place_input_manifest_entries 20
    set expected_quantizer3_primitives \
        $::env(HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES)
    set expected_relief_primitives \
        $::env(HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES)
    set p16_post_opt_summary [file normalize \
        $::env(HAP_P16_POST_OPT_SUMMARY)]
    set expected_p16_post_opt_summary_sha \
        $::env(HAP_P16_POST_OPT_SUMMARY_SHA256)
    set p16_production_region2_summary [file normalize \
        $::env(HAP_P16_PRODUCTION_REGION2_SUMMARY)]
    set expected_p16_production_region2_summary_sha \
        $::env(HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256)
    set expected_p16_production_dcp_sha \
        $::env(HAP_P16_PRODUCTION_DCP_SHA256)
    set expected_board_input_count 140
    set expected_board_immutable_input_count 139
    set expected_ooc_route_input_count 39
    set expected_total_dsp 5449
    set expected_slr_dsp {1862 1777 1810}
}
file mkdir $out
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
if {$rtl_variant ni {P14_LEGACY P16_NOCLIP} ||
    ![string is integer -strict $expected_quantizer3_primitives] ||
    $expected_quantizer3_primitives <= 0 ||
    ![string is integer -strict $expected_relief_primitives] ||
    $expected_relief_primitives <= 0} {
    error "invalid V5 board RTL variant or primitive contract"
}
if {$rtl_variant eq "P16_NOCLIP"} {
    if {![file exists $p16_post_opt_summary] ||
        ![file isfile $p16_post_opt_summary] ||
        [file size $p16_post_opt_summary] == 0} {
        error "P16 no-clip board post-opt summary is missing"
    }
    set actual_p16_post_opt_summary_sha \
        [lindex [exec sha256sum -- $p16_post_opt_summary] 0]
    if {![regexp {^[0-9a-f]{64}$} $expected_p16_post_opt_summary_sha] ||
        $actual_p16_post_opt_summary_sha ne
            $expected_p16_post_opt_summary_sha} {
        error "P16 no-clip board post-opt summary binding failed"
    }
    if {![file exists $p16_production_region2_summary] ||
        ![file isfile $p16_production_region2_summary] ||
        [file size $p16_production_region2_summary] == 0} {
        error "P16 production region2 summary is missing"
    }
    set actual_p16_production_region2_summary_sha \
        [lindex [exec sha256sum -- $p16_production_region2_summary] 0]
    if {![regexp {^[0-9a-f]{64}$} \
            $expected_p16_production_region2_summary_sha] ||
        ![regexp {^[0-9a-f]{64}$} $expected_p16_production_dcp_sha] ||
        $actual_p16_production_region2_summary_sha ne
            $expected_p16_production_region2_summary_sha} {
        error "P16 production region2 summary binding failed"
    }
}
set_param general.maxThreads $jobs

proc hap_board_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_board_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_board_read_path_list {path expected_count label} {
    set entries [dict create]
    foreach raw [split [hap_board_read_nonempty $path $label] "\n"] {
        set row [string trim $raw]
        if {$row eq ""} {continue}
        set normalized [file normalize $row]
        if {[file pathtype $row] ne "absolute" || $row ne $normalized} {
            error "$label contains a noncanonical path: $row"
        }
        if {[dict exists $entries $normalized]} {
            error "$label contains a duplicate path: $normalized"
        }
        hap_board_read_nonempty $normalized "$label member"
        dict set entries $normalized 1
    }
    if {[dict size $entries] != $expected_count} {
        error "$label cardinality mismatch: expected=$expected_count actual=[dict size $entries]"
    }
    return $entries
}

proc hap_board_verify_sha_manifest {path expected_sha expected_count label} {
    if {![regexp {^[0-9a-f]{64}$} $expected_sha]} {
        error "Malformed expected $label self-SHA256: $expected_sha"
    }
    if {[hap_board_sha256 $path] ne $expected_sha} {
        error "$label self-SHA256 mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_board_read_nonempty $path $label] "\n"] {
        set row [string trim $raw]
        if {$row eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(/.+)$} \
                $row -> expected path]} {
            error "Malformed $label row: $row"
        }
        set normalized [file normalize $path]
        if {$path ne $normalized || [dict exists $entries $normalized]} {
            error "$label contains a noncanonical or duplicate path: $path"
        }
        hap_board_read_nonempty $normalized "$label member"
        set actual [hap_board_sha256 $normalized]
        if {$actual ne $expected} {
            error "$label member SHA256 mismatch: $normalized"
        }
        dict set entries $normalized $actual
    }
    if {[dict size $entries] != $expected_count} {
        error "$label cardinality mismatch: expected=$expected_count actual=[dict size $entries]"
    }
    return $entries
}

proc hap_board_require_same_paths {left right label} {
    if {[lsort -dictionary [dict keys $left]] ne
        [lsort -dictionary [dict keys $right]]} {
        error "$label exact path-set mismatch"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![file exists $project_file] || ![file isfile $project_file] ||
    [file size $project_file] == 0} {
    error "Missing or empty V5 board project: $project_file"
}
if {![file exists $ooc_route_artifact] ||
    ![file isdirectory $ooc_route_artifact]} {
    error "Missing OOC route authorization artifact: $ooc_route_artifact"
}

# Bind both manifests by their launcher-frozen self SHA before sourcing any
# build/gate Tcl or opening the mutable Vivado project.  INPUT_FILES is an
# independent exact-path witness.  The project .xpr is the sole member omitted
# from the immutable post-build set.
set complete_paths [hap_board_read_path_list $input_files \
    $expected_board_input_count \
    "complete INPUT_FILES"]
set complete_inputs [hap_board_verify_sha_manifest $input_sha_manifest \
    $expected_input_manifest_sha $expected_board_input_count \
    "complete INPUT_SHA256SUMS"]
hap_board_require_same_paths $complete_paths $complete_inputs \
    "complete board input"
if {$rtl_variant eq "P16_NOCLIP"} {
    foreach required [list $p16_post_opt_summary \
            $p16_production_region2_summary \
            [file join $script_dir \
                projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl] \
            [file join $script_dir \
                projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl] \
            [file join $script_dir \
                projection_core16x16_w8_reuse_ooc_floorplan.tcl] \
            [file join $script_dir \
                v5_production_p16_noclip_quantizer3_locality_floorplan.tcl] \
            [file join $script_dir \
                v5_production_p9_quantizer3_locality_floorplan.tcl] \
            [file join $script_dir \
                v5_production_p16_noclip_region2_x2_relief_floorplan.tcl] \
            [file join $script_dir \
                v5_production_p14_region2_x2_relief_floorplan.tcl]] {
        set required [file normalize $required]
        if {![dict exists $complete_paths $required]} {
            error "P16 no-clip board input closure is missing: $required"
        }
    }
}
set immutable_paths [hap_board_read_path_list $immutable_input_files \
    $expected_board_immutable_input_count \
    "immutable INPUT_FILES"]
set immutable_inputs [hap_board_verify_sha_manifest \
    $immutable_input_sha_manifest \
    $expected_immutable_input_manifest_sha \
    $expected_board_immutable_input_count \
    "immutable INPUT_SHA256SUMS"]
hap_board_require_same_paths $immutable_paths $immutable_inputs \
    "immutable board input"
set expected_immutable [dict remove $complete_paths $project_file]
if {![dict exists $complete_paths $project_file] ||
    [dict size $expected_immutable] != $expected_board_immutable_input_count} {
    error "Complete board input does not contain exactly one mutable project file"
}
hap_board_require_same_paths $expected_immutable $immutable_inputs \
    "complete-minus-project immutable input"

# These two nested manifests are themselves members of the frozen immutable
# set; bind their own launcher-captured SHA as well as their contents.
foreach {label path expected_sha expected_count} [list \
        recursive_source $source_sha_manifest \
            $expected_recursive_source_manifest_sha 90 \
        ooc_route_authorization $ooc_route_sha_manifest \
            $expected_ooc_authorization_manifest_sha 22] {
    hap_board_verify_sha_manifest $path $expected_sha $expected_count \
        "$label SHA256SUMS"
}

source [file join $script_dir attention_mlp_vcu118_v5_post_route_gate.tcl]
set expected_region2_signature \
    $::hap_projection_ooc_floorplan::region2_signature
set expected_region2_rows0_3_primitives \
    [dict get $expected_region2_signature rows0_3_primitives]
set expected_region2_rows4_7_primitives \
    [dict get $expected_region2_signature rows4_7_primitives]
set expected_region2_residual_primitives \
    [dict get $expected_region2_signature residual_primitives]
if {[dict get $expected_region2_signature total_primitives] !=
        $expected_relief_primitives ||
    [dict get $expected_region2_signature rows0_3_dsp] != 272 ||
    [dict get $expected_region2_signature rows4_7_dsp] != 272 ||
    [dict get $expected_region2_signature residual_dsp] != 0} {
    error "V5 board bound region2 signature is inconsistent"
}
foreach {label path} [list complete_input_sha $input_sha_manifest \
        recursive_source_sha $source_sha_manifest \
        ooc_route_authorization_sha $ooc_route_sha_manifest] {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label manifest: $path"
    }
    if {[catch {exec sha256sum --status -c --strict $path} message]} {
        error "$label manifest verification failed: $message"
    }
}
foreach {label path} [list \
        ooc_route_input_sha \
            [file join $ooc_route_artifact INPUT_SHA256SUMS] \
        ooc_route_output_sha \
            [file join $ooc_route_artifact OUTPUT_SHA256SUMS]] {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label manifest: $path"
    }
    set fh [open $path r]
    set row_count 0
    foreach row [split [read $fh] "\n"] {
        if {[string trim $row] ne ""} {incr row_count}
    }
    close $fh
    if {$label eq "ooc_route_input_sha" &&
        $row_count != $expected_ooc_route_input_count} {
        error "$label manifest cardinality mismatch: expected=$expected_ooc_route_input_count actual=$row_count"
    }
    if {$label eq "ooc_route_output_sha" && $row_count < 1} {
        error "$label manifest is empty"
    }
    if {[catch {exec sha256sum --status -c --strict $path} message]} {
        error "$label manifest verification failed: $message"
    }
}

# The routed producer archives every current nonempty top-level file except
# OUTPUT_SHA256SUMS itself.  Reconstruct that exact dynamic set here; the
# required authorization members are checked below as an additional semantic
# gate rather than serving as an incomplete fixed manifest.
set route_output_manifest [file join $ooc_route_artifact OUTPUT_SHA256SUMS]
set manifested_route_outputs [dict create]
set fh [open $route_output_manifest r]
foreach raw [split [read $fh] "\n"] {
    set row [string trim $raw]
    if {$row eq ""} {continue}
    if {![regexp {^[0-9a-f]{64}[[:space:]]+\*?(/.+)$} $row -> path]} {
        close $fh
        error "Malformed OOC route output manifest row: $row"
    }
    set path [file normalize $path]
    if {[dict exists $manifested_route_outputs $path]} {
        close $fh
        error "Duplicate OOC route output manifest path: $path"
    }
    dict set manifested_route_outputs $path 1
}
close $fh
set current_route_outputs [dict create]
foreach path [glob -nocomplain -directory $ooc_route_artifact *] {
    set path [file normalize $path]
    if {$path eq [file normalize $route_output_manifest] ||
        ![file isfile $path] || [file size $path] == 0} {continue}
    dict set current_route_outputs $path 1
}
if {[lsort -dictionary [dict keys $manifested_route_outputs]] ne
    [lsort -dictionary [dict keys $current_route_outputs]]} {
    error "OOC route output manifest is not the complete current nonempty file set"
}
foreach {name expected} [list \
    HAP_BOARD_INPUT_COUNT $expected_board_input_count \
    HAP_BOARD_IMMUTABLE_INPUT_COUNT $expected_board_immutable_input_count \
    HAP_BOARD_SOURCE_MANIFEST_COUNT 3 \
    HAP_BOARD_RTL_SOURCE_COUNT 87 \
    HAP_BOARD_SOURCE_CLOSURE_COUNT 90] {
    if {![info exists ::env($name)] || $::env($name) ne $expected} {
        set actual [expr {[info exists ::env($name)] ?
            $::env($name) : "MISSING"}]
        error "V5 board provenance count mismatch: $name expected=$expected actual=$actual"
    }
}
proc require_ooc_route_authorization_line {path literal} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing OOC route authorization evidence: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    set key [lindex [split $literal =] 0]
    set literal_count 0
    set key_count 0
    foreach line [split $text "\n"] {
        if {$line eq $literal} {incr literal_count}
        if {[string first "${key}=" $line] == 0} {incr key_count}
    }
    if {$literal_count != 1 || $key_count != 1} {
        error "OOC route authorization field failed: file=$path literal=$literal literal_count=$literal_count key_count=$key_count"
    }
}
set ooc_route_summary [file join $ooc_route_artifact summary.txt]
set ooc_route_selectors [file join $ooc_route_artifact selectors_post_route.txt]
set ooc_route_geometry [file join $ooc_route_artifact \
    attention_geometry_post_route.txt]
set ooc_route_geometry_placement [file join $ooc_route_artifact \
    attention_geometry_placement_post_route.txt]
set ooc_route_base_pblocks [file join $ooc_route_artifact \
    base_pblocks_post_route.txt]
set ooc_route_p5_plan [file join $ooc_route_artifact \
    p5_input_plan_post_route.txt]
set ooc_route_p5_pblocks [file join $ooc_route_artifact \
    p5_input_pblocks_post_route.txt]
set ooc_route_p9_postprocess_plan [file join $ooc_route_artifact \
    p9_postprocess_plan_post_route.txt]
set ooc_route_p9_postprocess_pblocks [file join $ooc_route_artifact \
    p9_postprocess_pblocks_post_route.txt]
set ooc_route_p9_quantizer3_plan [file join $ooc_route_artifact \
    p9_quantizer3_plan_post_route.txt]
set ooc_route_p9_quantizer3_pblock [file join $ooc_route_artifact \
    p9_quantizer3_pblock_post_route.txt]
set ooc_route_p14_relief_plan [file join $ooc_route_artifact \
    p14_region2_relief_plan_post_route.txt]
set ooc_route_p14_relief_pblock [file join $ooc_route_artifact \
    p14_region2_relief_pblock_post_route.txt]
set ooc_route_p8_parent_input [file join $ooc_route_artifact \
    p8_parent_ingress_boundary_input.txt]
set ooc_route_p8_parent_final [file join $ooc_route_artifact \
    p8_parent_ingress_boundary_post_route.txt]
set ooc_route_input_boundaries [file join $ooc_route_artifact \
    architecture_boundaries_input.txt]
set ooc_route_final_boundaries [file join $ooc_route_artifact \
    architecture_boundaries_post_route.txt]
set ooc_route_launcher [file join $ooc_route_artifact launcher_status.txt]
foreach literal {
    status=V5_P10_P14_PRODUCTION_OOC_POST_ROUTE_PASS
    evidence_class=P14_PRODUCTION_CORE_OOC_POST_ROUTE
    base_contract_variant=P2_COHORT16_COL2_12_2
    p5_contract=P5_INPUT_HALF_LOCAL_8_8
    p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6
    p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
    p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2
    uram288=752
    mlp_kernel_dsp48e2=3072
    metadata_local_write_protected_ff=970
    mlp_capture_leaf_instances=1632
    mlp_capture_leaf_lut1=1632
    architecture_boundary_ok=1
    pblock_count=26
    canonical_pblock_count=11
    geometry_pblock_count=10
    p5_added_pblock_count=2
    p9_postprocess_added_pblock_count=2
    p9_quantizer3_added_pblock_count=1
    p14_region2_relief_added_pblock_count=0
    p9_postprocess_center_wrong_slr=0
    p9_postprocess_outer_wrong_slr=0
    p9_slr0_row_primitives=16044
    p9_center_row_primitives=10696
    p9_slr2_row_primitives=16044
    p9_quantizer3_grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6
    p9_quantizer3_wrong_region=0
    p9_quantizer3_unplaced=0
    p14_region2_relief_base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9
    p14_region2_relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9
    p14_region2_expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9
    p14_region2_relief_wrong=0
    p14_region2_relief_unplaced=0
    parent_head_ff=6560
    parent_tail_ff=6560
    parent_count_ff=2
    parent_count_replica_equivalence_ok=1
    parent_pointer_ff=0
    local_clear_shared_upstream_ready_paths=0
    branch_credit_shared_upstream_ready_paths=0
    local_clear_gate_compute_ready_paths=0
    branch_credit_gate_compute_ready_paths=0
    local_clear_down_compute_ready_paths=0
    branch_credit_down_compute_ready_paths=0
    local_clear_input_cache_ready_paths=0
    branch_credit_input_cache_ready_paths=0
    completed_u8_ff=4096
    completed_meta_ff=352
    input_capture_ff=12288
    input_capture_controls=48
    cdc_critical=0
    congestion_level6_or_higher_windows=0
    route_clean=1
    timing_ok=1
    policy_ok=1
    bitstream_generated=0
} {
    require_ooc_route_authorization_line $ooc_route_summary $literal
}
require_ooc_route_authorization_line $ooc_route_summary \
    "route_input_manifest_entries=$expected_ooc_route_input_count"
foreach literal [list \
        "dsp48e2=$expected_total_dsp" \
        "slr0_dsp48e2=[lindex $expected_slr_dsp 0]" \
        "slr1_dsp48e2=[lindex $expected_slr_dsp 1]" \
        "slr2_dsp48e2=[lindex $expected_slr_dsp 2]" \
        "place_input_manifest_entries=$place_input_manifest_entries" \
        "p9_quantizer3_primitives=$expected_quantizer3_primitives" \
        "p14_region2_relief_primitives=$expected_relief_primitives" \
        "p14_region2_relief_placed=$expected_relief_primitives"] {
    require_ooc_route_authorization_line $ooc_route_summary $literal
}
if {$rtl_variant eq "P16_NOCLIP"} {
    foreach literal [list rtl_variant=P16_NOCLIP \
            rtl_resource_variant=P16_NOCLIP \
            "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$expected_p16_production_region2_summary_sha" \
            "p16_post_opt_summary=$p16_post_opt_summary" \
            "p16_post_opt_summary_sha256=$expected_p16_post_opt_summary_sha" \
            "p16_production_region2_summary=$p16_production_region2_summary" \
            "p16_production_region2_summary_sha256=$expected_p16_production_region2_summary_sha" \
            "p16_production_dcp_sha256=$expected_p16_production_dcp_sha"] {
        require_ooc_route_authorization_line $ooc_route_summary $literal
    }
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_SELECTORS_PASS
    contract_variant=P2_COHORT16_COL2_12_2
    total_uram=752
} {
    require_ooc_route_authorization_line $ooc_route_selectors $literal
}
require_ooc_route_authorization_line $ooc_route_selectors \
    "total_dsp=$expected_total_dsp"
if {$rtl_variant eq "P16_NOCLIP"} {
    require_ooc_route_authorization_line $ooc_route_selectors \
        rtl_resource_variant=P16_NOCLIP
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_GEOMETRY_PASS
    region0_input_primitives=3136
    region3_input_primitives=2112
    owner_region2_weight_primitives=2048
    center_region1_bisect_exact_cover=1
    center_region1_dsp_stripe_exact_cover=1
    center_region2_rows0_3_primitives_dsp48e2=272
    center_region2_rows4_7_primitives_dsp48e2=272
    center_region2_residual_primitives_dsp48e2=0
    center_region2_row_exact_cover=1
    owner_region0_input_exact_cover=1
    owner_region3_input_exact_cover=1
    owner_region2_weight_exact_cover=1
    region3_weight_owner_residency_ok=1
} {
    require_ooc_route_authorization_line $ooc_route_geometry $literal
}
foreach literal [list \
        "center_region2_rows0_3_primitives=$expected_region2_rows0_3_primitives" \
        "center_region2_rows4_7_primitives=$expected_region2_rows4_7_primitives" \
        "center_region2_residual_primitives=$expected_region2_residual_primitives"] {
    require_ooc_route_authorization_line $ooc_route_geometry $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_GEOMETRY_PLACEMENT_PASS
    wrong_total=0
    unplaced_total=0
    {slr_dsp=272 1696 272}
    ok=1
} {
    require_ooc_route_authorization_line \
        $ooc_route_geometry_placement $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_BASE_PBLOCKS_PASS
    ok=1
    require_placed=1
    contract_variant=P2_COHORT16_COL2_12_2
    pblock_count=11
    uram_coverage=752
    placed_wrong=0
} {
    require_ooc_route_authorization_line $ooc_route_base_pblocks $literal
}
require_ooc_route_authorization_line $ooc_route_base_pblocks \
    "dsp_coverage=$expected_total_dsp"
foreach literal {
    status=V5_P14_ROUTE_FINAL_INPUT_PLAN_PASS
    contract=P5_INPUT_HALF_LOCAL_8_8
    quantizer_count=4
    cache_count=2
    hadamard_count=1
    completed_u8_ff=4096
    completed_meta_ff=352
    input_capture_ff=12288
    capture_leaf_count=48
    center_canonical_overlap=8
} {
    require_ooc_route_authorization_line $ooc_route_p5_plan $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_INPUT_PBLOCKS_PASS
    ok=1
    require_placed=1
    pblock_count=2
    center_missing=0
    center_outer_overlap=0
    center_wrong=0
    outer_wrong=0
} {
    require_ooc_route_authorization_line $ooc_route_p5_pblocks $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_POSTPROCESS_PLAN_PASS
    contract=P9_POSTPROCESS_SPLIT_6_4_6
    row_bank_count=16
    all_row_primitives=42784
    slr0_row_primitives=16044
    center_row_primitives=10696
    slr2_row_primitives=16044
    per_row_primitives=2674
    per_row_lut=994
    per_row_ff=1536
} {
    require_ooc_route_authorization_line $ooc_route_p9_postprocess_plan $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_POSTPROCESS_PBLOCKS_PASS
    ok=1
    require_placed=1
    pblock_count=2
    center_missing=0
    center_outer_overlap=0
    center_wrong=0
    outer_wrong=0
    slr0_target=0
    slr0_missing=0
    slr0_wrong=0
    slr2_target=2
    slr2_missing=0
    slr2_wrong=0
} {
    require_ooc_route_authorization_line \
        $ooc_route_p9_postprocess_pblocks $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_QUANTIZER3_PLAN_PASS
    contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
    grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6
} {
    require_ooc_route_authorization_line $ooc_route_p9_quantizer3_plan $literal
}
require_ooc_route_authorization_line $ooc_route_p9_quantizer3_plan \
    "primitive_count=$expected_quantizer3_primitives"
foreach literal {
    status=V5_P14_ROUTE_FINAL_QUANTIZER3_PBLOCK_PASS
    ok=1
    require_placed=1
    contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
    missing=0
    extras=0
    wrong=0
    unplaced=0
} {
    require_ooc_route_authorization_line \
        $ooc_route_p9_quantizer3_pblock $literal
}
foreach literal [list "expected=$expected_quantizer3_primitives" \
        "members=$expected_quantizer3_primitives"] {
    require_ooc_route_authorization_line \
        $ooc_route_p9_quantizer3_pblock $literal
}
foreach literal {
    status=V5_P14_ROUTE_FINAL_REGION2_RELIEF_PLAN_PASS
    contract=P14_ATTN_REGION2_SHARED_X0_X2
    base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9
    relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9
    expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9
} {
    require_ooc_route_authorization_line $ooc_route_p14_relief_plan $literal
}
require_ooc_route_authorization_line $ooc_route_p14_relief_plan \
    "primitive_count=$expected_relief_primitives"
foreach literal {
    status=V5_P14_ROUTE_FINAL_REGION2_RELIEF_PBLOCK_PASS
    ok=1
    contract=P14_ATTN_REGION2_SHARED_X0_X2
    require_placed=1
    missing=0
    wrong=0
    unplaced=0
} {
    require_ooc_route_authorization_line $ooc_route_p14_relief_pblock $literal
}
require_ooc_route_authorization_line $ooc_route_p14_relief_pblock \
    "primitive_count=$expected_relief_primitives"
set relief_fh [open $ooc_route_p14_relief_pblock r]
set relief_text [read $relief_fh]
close $relief_fh
if {![regexp -line {^relief_placed=([0-9]+)$} $relief_text -> relief_placed] ||
    $relief_placed > $expected_relief_primitives} {
    error "OOC route P14 relief_placed is missing or invalid"
}
foreach {parent_file status} [list \
        $ooc_route_p8_parent_input \
            V5_P14_ROUTE_INPUT_PARENT_INGRESS_BOUNDARY_PASS \
        $ooc_route_p8_parent_final \
            V5_P14_ROUTE_FINAL_PARENT_INGRESS_BOUNDARY_PASS] {
    foreach literal [list status=$status ok=1 parent_head_ff=6560 \
            parent_tail_ff=6560 parent_count_ff=2 \
            parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
            local_clear_shared_upstream_ready_paths=0 \
            branch_credit_shared_upstream_ready_paths=0 \
            local_clear_gate_compute_ready_paths=0 \
            branch_credit_gate_compute_ready_paths=0 \
            local_clear_down_compute_ready_paths=0 \
            branch_credit_down_compute_ready_paths=0 \
            local_clear_input_cache_ready_paths=0 \
            branch_credit_input_cache_ready_paths=0] {
        require_ooc_route_authorization_line $parent_file $literal
    }
}
foreach boundary_file [list $ooc_route_input_boundaries \
        $ooc_route_final_boundaries] {
    foreach literal {
        mlp_local_clear_ff=2
        mlp_local_clear_protected_ff=2
        branch0_local_clear_ff=1
        branch1_local_clear_ff=1
        {branch0_local_clear_slr=1 0 0}
        {branch1_local_clear_slr=0 0 1}
        mlp_local_clear_wrong_slr=0
        mlp_central_clear_ff=1
        mlp_central_clear_branch_endpoints=2
        mlp_central_clear_direct_branch_state=0
        swiglu_local_clear_ff=8
        swiglu_local_clear_protected_ff=8
        swiglu_control_clear_ff=1
        swiglu_hadamard_clear_ff=1
        swiglu_quantizer_clear_ff=4
        swiglu_row_clear_ff=2
        swiglu_direct_clear_bypass_state=0
        metadata_leaf_instances=4
        metadata_local_wr_en_ff=4
        metadata_local_wr_addr_ff=70
        metadata_local_wr_data_ff=896
        metadata_local_write_protected_ff=970
        {metadata_local_write_leaf_counts=243 243 242 242}
        {metadata_local_write_leaf_slr_counts={243 0 0} {0 0 243} {0 242 0} {0 242 0}}
        metadata_local_write_wrong_slr=0
        mlp_capture_leaf_instances=1632
        mlp_capture_leaf_lut1=1632
        {mlp_capture_leaf_branch_instances=816 816}
        {mlp_capture_leaf_branch_lut1=816 816}
        {mlp_capture_leaf_branch_slr_counts={816 0 0} {0 0 816}}
        mlp_capture_leaf_wrong_slr=0
    } {
        require_ooc_route_authorization_line $boundary_file $literal
    }
}
require_ooc_route_authorization_line $ooc_route_input_boundaries \
    status=V5_P14_ROUTE_INPUT_BOUNDARIES_PASS
require_ooc_route_authorization_line $ooc_route_final_boundaries \
    status=V5_P14_ROUTE_FINAL_BOUNDARIES_PASS
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0 \
        vivado_invoked=1 route_input_sha_postcheck=1 \
        place_input_sha_postcheck=1 place_output_sha_postcheck=1 \
        route_input_manifest_sha_match=1 place_input_manifest_sha_match=1 \
        place_output_manifest_sha_match=1 bitstream_generated=0} {
    require_ooc_route_authorization_line $ooc_route_launcher $literal
}
if {$rtl_variant eq "P16_NOCLIP"} {
    require_ooc_route_authorization_line $ooc_route_launcher \
        rtl_variant=P16_NOCLIP
}
set ooc_route_summary_sha256 \
    [lindex [exec sha256sum $ooc_route_summary] 0]
set ooc_route_dcp [file join $ooc_route_artifact post_route.dcp]
set ooc_route_dcp_sha256 [lindex [exec sha256sum $ooc_route_dcp] 0]
if {![file exists $xdc_inventory] || ![file isfile $xdc_inventory] ||
    [file size $xdc_inventory] == 0} {puts "INFO: Active XDC inventory will be generated after project open"}

open_project $project_file
source [file join $script_dir write_attention_mlp_vcu118_v5_xdc_inventory.tcl]
set inventory [hap_v5_board_gate::parse_xdc_inventory $xdc_inventory]
if {[dict get $inventory user_false] != 0 ||
    [dict get $inventory user_datapath] != 0 ||
    [dict get $inventory unknown_false] != 0 ||
    [dict get $inventory unknown_datapath] != 0 ||
    [dict get $inventory vendor_core_selector_hits] != 0} {
    error "Active V5 XDC inventory rejected a forbidden exception"
}
file copy -force $xdc_inventory [file join $out XDC_ACTIVE_INVENTORY_PRE_SYNTH]
set expected_part xcvu9p-flga2104-2L-e
set expected_board xilinx.com:vcu118:part0:2.0
set expected_project attention_mlp_vcu118_v5_dual_ddr
set expected_top attention_mlp_vcu118_v5_bd_wrapper
set expected_bd attention_mlp_vcu118_v5_bd
if {[get_property NAME [current_project]] ne $expected_project} {
    error "Wrong V5 project identity: [get_property NAME [current_project]]"
}
if {[get_property PART [current_project]] ne $expected_part} {
    error "Wrong V5 board part: [get_property PART [current_project]]"
}
if {[get_property BOARD_PART [current_project]] ne $expected_board} {
    error "Wrong V5 board definition: [get_property BOARD_PART [current_project]]"
}
if {[get_property TOP [current_fileset]] ne $expected_top} {
    error "Wrong V5 board top: [get_property TOP [current_fileset]]"
}
set defines [get_property verilog_define [get_filesets sources_1]]
foreach required {HAP_BOARD_BUILD HAP_BOARD_V5
    HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46} {
    if {[lsearch -exact $defines $required] < 0} {
        error "V5 board define is missing: $required (actual=$defines)"
    }
}
foreach forbidden_define $defines {
    if {[string match "HAP_MLP_FULL_COMMAND_V5_MODULE=*" $forbidden_define] &&
        $forbidden_define ne
        "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46"} {
        error "Conflicting V5 MLP module-name define: $forbidden_define"
    }
}
foreach required_source {
    hap_a8w4_group32_lane2_s37.sv
    hap_a8w4_slice8x12_group_s37.sv
    hap_mlp_tile_accum_s37.sv
    hap_mlp_down_group_major_accum_s46.sv
    hap_mlp_shared_dual_slice16x12_s44_s46.sv
    hap_mlp_serial_ddr_command16_v5_s46.sv
    hap_mlp_full_command16_v5_s46.sv
    hap_attention_mlp_resource_top.sv
    hap_attention_mlp_production_core.sv
    hap_attention_mlp_board_core.sv
    vcu118_pcie_refclk_ibuf.v
    hap_v5_reset_gate_xpm.sv
    hap_v5_dual_async_ready_gate_xpm.sv
} {
    set hits [get_files -quiet -of_objects [get_filesets sources_1] \
        -filter "NAME =~ */$required_source"]
    if {[llength $hits] != 1} {
        error "V5 source identity is not unique: $required_source hits=$hits"
    }
}
foreach forbidden_source {
    hap_a8w4_slice8x16_group_s36.sv
    hap_mlp_shared_dual_slice16x16_s43_s45.sv
    hap_mlp_gate_up_external_scheduler16_q4.sv
    hap_mlp_down_activation_replay16.sv
    hap_mlp_serial_ddr_command16_s45.sv
    hap_mlp_full_command16_s45.sv
    hap_a8w4_group32_lane2_s36.sv
    hap_a8w4_slice8x12_group_s36.sv
    hap_mlp_tile_accum_s36.sv
    hap_mlp_down_group_major_accum_s45.sv
    hap_mlp_shared_dual_slice16x12_s43_s45.sv
    hap_mlp_serial_ddr_command16_v5_s45.sv
    hap_mlp_full_command16_v5_s45.sv
} {
    set hits [get_files -quiet -of_objects [get_filesets sources_1] \
        -filter "NAME =~ */$forbidden_source"]
    if {[llength $hits] != 0} {
        error "V4 source leaked into V5 full-board project: $forbidden_source hits=$hits"
    }
}
set bd_files [get_files -quiet "*/${expected_bd}.bd"]
if {[llength $bd_files] != 1} {
    error "V5 board BD is not unique: $bd_files"
}
open_bd_design [lindex $bd_files 0]
proc require_v5_bd_cfg {cell key expected} {
    set obj [get_bd_cells -quiet $cell]
    if {[llength $obj] != 1} {error "Missing V5 BD cell: $cell"}
    set actual [get_property CONFIG.$key $obj]
    if {$actual ne $expected} {
        error "$cell CONFIG.$key expected=$expected actual=$actual"
    }
}
proc require_v5_bd_cfg_number {cell key expected {tolerance 0.0}} {
    set obj [get_bd_cells -quiet $cell]
    if {[llength $obj] != 1} {error "Missing V5 BD cell: $cell"}
    set actual [get_property CONFIG.$key $obj]
    if {![string is double -strict $actual] ||
        abs(double($actual) - double($expected)) > double($tolerance)} {
        error "$cell CONFIG.$key expected=$expected actual=$actual"
    }
}
proc require_v5_same_bd_net {label objects} {
    set expected {}
    foreach obj $objects {
        if {[llength $obj] != 1} {error "$label object is not unique: $obj"}
        set nets [get_bd_nets -quiet -of_objects $obj]
        if {[llength $nets] != 1} {
            error "$label object is not on exactly one BD net: $obj nets=$nets"
        }
        set net [lindex $nets 0]
        if {$expected eq {}} {set expected $net}
        if {$net ne $expected} {
            error "$label net mismatch: expected=$expected actual=$net object=$obj"
        }
    }
}
proc require_v5_first_intf {cell names} {
    foreach name $names {
        set pin [get_bd_intf_pins -quiet $cell/$name]
        if {[llength $pin] == 1} {return $pin}
        if {[llength $pin] > 1} {
            error "V5 BD interface is not unique: $cell/$name pins=$pin"
        }
    }
    error "Missing V5 BD interface: cell=$cell candidates=$names"
}
proc v5_bd_address_number {label value} {
    if {[regexp -nocase {^([0-9]+)([KMG])$} $value -> count unit]} {
        set shift [dict get [dict create K 10 M 20 G 30] [string toupper $unit]]
        return [expr {wide($count) << $shift}]
    }
    if {[catch {expr {wide($value)}} number]} {
        error "$label is not an integer address value: $value"
    }
    return $number
}
proc require_v5_bd_address_mapping {label intf_pin target_token \
        expected_offset expected_range expected_count} {
    set spaces [get_bd_addr_spaces -quiet -of_objects $intf_pin]
    if {[llength $spaces] != 1} {
        error "$label must expose exactly one address space: pin=$intf_pin spaces=$spaces"
    }
    set segments [get_bd_addr_segs -quiet -of_objects [lindex $spaces 0]]
    if {[llength $segments] != $expected_count} {
        error "$label address-space segment count mismatch: expected=$expected_count actual=[llength $segments] segments=$segments"
    }
    set matches {}
    foreach segment $segments {
        if {[string match "*${target_token}*" $segment]} {
            lappend matches $segment
        }
    }
    if {[llength $matches] != 1} {
        error "$label target segment is not unique: token=$target_token matches=$matches all=$segments"
    }
    set segment [lindex $matches 0]
    set actual_offset [v5_bd_address_number "$label OFFSET" \
        [get_property OFFSET $segment]]
    set actual_range [v5_bd_address_number "$label RANGE" \
        [get_property RANGE $segment]]
    if {$actual_offset != [v5_bd_address_number "$label expected OFFSET" \
            $expected_offset] ||
        $actual_range != [v5_bd_address_number "$label expected RANGE" \
            $expected_range]} {
        error "$label address mismatch: expected=$expected_offset/$expected_range actual=[get_property OFFSET $segment]/[get_property RANGE $segment] segment=$segment"
    }
}
foreach {cell_name expected_ip} {
    ddr4_0 ddr4 ddr4_1 ddr4 xdma_0 xdma
} {
    set cell [get_bd_cells -quiet $cell_name]
    if {[llength $cell] != 1 ||
        ![string match "*:${expected_ip}:*" [get_property VLNV $cell]]} {
        error "V5 board IP identity mismatch: $cell_name $cell"
    }
}
foreach {key expected} {
    mode_selection Advanced
    axilite_master_en true
    axisten_if_enable_msg_route true
    PCIE_BOARD_INTERFACE pci_express_x8
    pl_link_cap_max_link_speed 8.0_GT/s
    axi_data_width 256_bit
    SYS_RST_N_BOARD_INTERFACE pcie_perstn
    pf0_device_id 9018
    pciebar2axibar_0 0x00000000
    pf0_bar0_enabled true
    pf0_bar0_scale Megabytes
    pf0_bar0_size 1
    pf0_bar2_enabled true
    pf0_bar2_scale Gigabytes
    pf0_bar2_size 4
    pf0_msix_enabled false
    pf0_msi_enabled true
    xdma_rnum_chnl 1
    xdma_wnum_chnl 1
} {require_v5_bd_cfg xdma_0 $key $expected}
foreach reset_cell {rst_core rst_ddr0 rst_ddr1} {
    require_v5_bd_cfg_number $reset_cell C_EXT_RESET_HIGH 0
}
# InputClockPeriod describes the VCU118 250 MHz external MIG reference
# (4000 ps), not c0_ddr4_ui_clk.  TimePeriod=833 selects the DDR rate and the
# live core-facing UI pins are separately required to run at 300 MHz below.
foreach mig {ddr4_0 ddr4_1} {
    require_v5_bd_cfg_number $mig C0.DDR4_AxiAddressWidth 31
    require_v5_bd_cfg_number $mig C0.DDR4_AxiDataWidth 512
    require_v5_bd_cfg_number $mig C0.DDR4_InputClockPeriod 4000
    require_v5_bd_cfg_number $mig C0.DDR4_TimePeriod 833
}
require_v5_bd_cfg ddr4_0 C0_CLOCK_BOARD_INTERFACE default_250mhz_clk1
require_v5_bd_cfg ddr4_0 C0_DDR4_BOARD_INTERFACE ddr4_sdram_c1
require_v5_bd_cfg ddr4_1 C0_CLOCK_BOARD_INTERFACE default_250mhz_clk2
require_v5_bd_cfg ddr4_1 C0_DDR4_BOARD_INTERFACE ddr4_sdram_c2
require_v5_bd_address_mapping "V5 XDMA DDR0" \
    [require_v5_first_intf xdma_0 {M_AXI M_AXI_MM}] ddr4_0 \
    0x00000000 0x80000000 2
require_v5_bd_address_mapping "V5 XDMA DDR1" \
    [require_v5_first_intf xdma_0 {M_AXI M_AXI_MM}] ddr4_1 \
    0x80000000 0x80000000 2
require_v5_bd_address_mapping "V5 core tensor DDR0" \
    [get_bd_intf_pins core/M_AXI_DATA] ddr4_0 \
    0x00000000 0x80000000 1
require_v5_bd_address_mapping "V5 core weight DDR0" \
    [get_bd_intf_pins core/M_AXI_WEIGHT_C0] ddr4_0 \
    0x00000000 0x80000000 1
require_v5_bd_address_mapping "V5 core weight DDR1" \
    [get_bd_intf_pins core/M_AXI_WEIGHT_C1] ddr4_1 \
    0x00000000 0x80000000 1
require_v5_bd_address_mapping "V5 XDMA control" \
    [require_v5_first_intf xdma_0 {M_AXI_LITE M_AXI_LITE_MASTER}] core \
    0x00000000 0x00001000 1
set core_cell [get_bd_cells -quiet core]
set core_clk_hz [get_property CONFIG.FREQ_HZ [get_bd_pins core/core_clk]]
set ddr0_clk_hz [get_property CONFIG.FREQ_HZ [get_bd_pins core/ddr0_clk]]
set ddr1_clk_hz [get_property CONFIG.FREQ_HZ [get_bd_pins core/ddr1_clk]]
if {$core_clk_hz eq ""} {set core_clk_hz \
    [get_property FREQ_HZ [get_bd_pins core/core_clk]]}
if {$ddr0_clk_hz eq ""} {set ddr0_clk_hz \
    [get_property FREQ_HZ [get_bd_pins core/ddr0_clk]]}
if {$ddr1_clk_hz eq ""} {set ddr1_clk_hz \
    [get_property FREQ_HZ [get_bd_pins core/ddr1_clk]]}
if {[llength $core_cell] != 1 ||
    $core_clk_hz != 100000000 || $ddr0_clk_hz != 300000000 ||
    $ddr1_clk_hz != 300000000} {
    error "V5 board core clock contract is not 100/300/300 MHz"
}
require_v5_same_bd_net "V5 core 100 MHz clock" [list \
    [get_bd_pins clk_core/clk_out1] [get_bd_pins core/core_clk] \
    [get_bd_pins core_gate/clk]]
require_v5_same_bd_net "V5 DDR0 300 MHz UI clock" [list \
    [get_bd_pins ddr4_0/c0_ddr4_ui_clk] [get_bd_pins core/ddr0_clk] \
    [get_bd_pins d0_gate/clk] [get_bd_pins d0_smc/aclk] \
    [get_bd_pins d0_mig_slice/aclk]]
require_v5_same_bd_net "V5 DDR1 300 MHz UI clock" [list \
    [get_bd_pins ddr4_1/c0_ddr4_ui_clk] [get_bd_pins core/ddr1_clk] \
    [get_bd_pins d1_gate/clk] [get_bd_pins d1_smc/aclk] \
    [get_bd_pins d1_mig_slice/aclk]]
foreach {cell ref} {
    core_gate hap_v5_dual_async_ready_gate_xpm
    d0_gate hap_v5_reset_gate_xpm
    d1_gate hap_v5_reset_gate_xpm
} {
    set bd_cell [get_bd_cells -quiet $cell]
    set actual_ref [get_property -quiet REF_NAME $bd_cell]
    if {$actual_ref eq ""} {set actual_ref [get_property -quiet CONFIG.MODREF $bd_cell]}
    if {[llength $bd_cell] != 1 ||
        $actual_ref ne $ref} {
        error "V5 XPM reset gate identity mismatch: $cell expected=$ref actual=$actual_ref"
    }
}
foreach {tag mig gate core_ready_pin} {
    ddr0 ddr4_0 d0_gate async_ready0
    ddr1 ddr4_1 d1_gate async_ready1
} {
    set inv ${tag}_ui_sync_rst_inv
    set ready ${tag}_ready_and
    require_v5_bd_cfg_number $inv C_SIZE 1
    require_v5_bd_cfg $inv C_OPERATION not
    require_v5_bd_cfg_number $ready C_SIZE 1
    require_v5_bd_cfg $ready C_OPERATION and
    require_v5_same_bd_net "V5 $tag UI-reset sense" [list \
        [get_bd_pins $mig/c0_ddr4_ui_clk_sync_rst] \
        [get_bd_pins $inv/Op1]]
    require_v5_same_bd_net "V5 $tag calibration sense" [list \
        [get_bd_pins $mig/c0_init_calib_complete] \
        [get_bd_pins $ready/Op1]]
    require_v5_same_bd_net "V5 $tag UI-reset inversion" [list \
        [get_bd_pins $inv/Res] [get_bd_pins $ready/Op2]]
    require_v5_same_bd_net "V5 $tag calibrated/not-reset release" [list \
        [get_bd_pins $ready/Res] [get_bd_pins $gate/async_ready] \
        [get_bd_pins core_gate/$core_ready_pin]]
}
require_v5_same_bd_net "V5 DDR0 downstream reset" [list \
    [get_bd_pins d0_gate/aresetn] [get_bd_pins core/ddr0_rst_n] \
    [get_bd_pins d0_smc/aresetn] [get_bd_pins d0_mig_slice/aresetn]]
require_v5_same_bd_net "V5 DDR1 downstream reset" [list \
    [get_bd_pins d1_gate/aresetn] [get_bd_pins core/ddr1_rst_n] \
    [get_bd_pins d1_smc/aresetn] [get_bd_pins d1_mig_slice/aresetn]]
require_v5_same_bd_net "V5 core downstream reset" [list \
    [get_bd_pins core_gate/aresetn] [get_bd_pins core/core_rst_n]]
foreach slice {d0_mig_slice d1_mig_slice} {
    set cell [get_bd_cells -quiet $slice]
    if {[llength $cell] != 1} {error "Missing MIG register slice: $slice"}
    foreach ch {AW AR W R B} {
        if {[get_property CONFIG.REG_$ch $cell] ne "15"} {
            error "$slice REG_$ch is not fully registered"
        }
        foreach side {MASTER SLAVE MIDDLE} {
            if {[get_property CONFIG.PIPELINES_${side}_$ch $cell] ne "1"} {
                error "$slice PIPELINES_${side}_$ch is not enabled"
            }
        }
    }
}
generate_target all $bd_files
update_compile_order -fileset sources_1

# Build a completely fresh top and fresh module-reference core.  MIG/XDMA IP
# targets may use their generated products, but neither a compute OOC DCP nor
# an old board implementation checkpoint is accepted as signoff evidence.
set core_runs [get_runs -quiet -filter \
    {NAME == attention_mlp_vcu118_v5_bd_core_0_synth_1}]
reset_run impl_1
reset_run synth_1
if {[llength $core_runs] == 1} {reset_run [lindex $core_runs 0]}
launch_runs synth_1 -jobs $jobs
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    error "V5 full-board synth_1 failed: [get_property STATUS [get_runs synth_1]]"
}
open_run synth_1
set syn_v5_serial [hap_v5_board_gate::module_cells \
    hap_mlp_serial_ddr_command16_v5_s46]
set syn_old_serial [hap_v5_board_gate::module_cells \
    hap_mlp_serial_ddr_command16_s45]
set syn_kernels [hap_v5_board_gate::module_cells \
    hap_a8w4_slice8x12_group_s37]
set syn_old_kernels [hap_v5_board_gate::module_cells \
    hap_a8w4_slice8x16_group_s36]
if {[llength $syn_v5_serial] != 1 || [llength $syn_old_serial] != 0 ||
    [llength $syn_kernels] != 2 || [llength $syn_old_kernels] != 0} {
    error "V5 full-board post-synth hierarchy identity failed"
}
report_utilization -file [file join $out utilization_post_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 14 -file \
    [file join $out utilization_hier_post_synth.rpt]
report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -file [file join $out timing_post_synth.rpt]
close_design

reset_run impl_1
set impl [get_runs impl_1]
set_property STEPS.OPT_DESIGN.ARGS.DIRECTIVE ExploreWithRemap $impl
set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE $place_directive $impl
set_property STEPS.PLACE_DESIGN.TCL.PRE \
    [file join $script_dir apply_attention_mlp_vcu118_v5_floorplan.tcl] $impl
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true $impl
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore $impl
set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE $route_directive $impl
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true $impl
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore $impl

# Stop before bitgen.  Bitstream creation is deliberately performed only
# after the routed in-memory design passes the strict production gate.
launch_runs impl_1 -to_step route_design -jobs $jobs
wait_on_run impl_1
set routed_dcp [file join [get_property DIRECTORY $impl] \
    ${expected_top}_routed.dcp]
if {![file exists $routed_dcp] || ![file isfile $routed_dcp] ||
    [file size $routed_dcp] == 0} {
    error "V5 board route did not create a non-empty routed DCP: $routed_dcp"
}
open_run impl_1
phys_opt_design -directive AggressiveExplore
# Re-export the actual post-route implementation constraints.  This catches
# any scoped IP XDC added during generated-target/OOC expansion.
source [file join $script_dir write_attention_mlp_vcu118_v5_xdc_inventory.tcl]
set initial [hap_v5_board_gate::audit $out $xdc_inventory]

set delivered_bit [file join $out attention_mlp_vcu118_v5.bit]
write_bitstream -force $delivered_bit
set delivered_dcp [file join $out attention_mlp_vcu118_v5_post_route.dcp]
write_checkpoint -force $delivered_dcp
set final [hap_v5_board_gate::audit $out $xdc_inventory $delivered_bit]

set bit_hash [dict get $final bitstream_sha256]
set dcp_hash [lindex [exec sha256sum $delivered_dcp] 0]
if {![regexp {^[0-9a-f]{64}$} $bit_hash] ||
    ![regexp {^[0-9a-f]{64}$} $dcp_hash]} {
    error "V5 board deliverable hash failed"
}

# Reverify every immutable input and every manifest's frozen self identity in
# the same process after implementation/bitgen.  Only the project .xpr is
# deliberately excluded because Vivado run management updates it.
set immutable_inputs_post [hap_board_verify_sha_manifest \
    $immutable_input_sha_manifest \
    $expected_immutable_input_manifest_sha \
    $expected_board_immutable_input_count \
    "immutable INPUT_SHA256SUMS post-build"]
hap_board_require_same_paths $immutable_paths $immutable_inputs_post \
    "immutable board input post-build"
foreach {label path expected_sha expected_count} [list \
        recursive_source $source_sha_manifest \
            $expected_recursive_source_manifest_sha 90 \
        ooc_route_authorization $ooc_route_sha_manifest \
            $expected_ooc_authorization_manifest_sha 22] {
    hap_board_verify_sha_manifest $path $expected_sha $expected_count \
        "$label SHA256SUMS post-build"
}
set fp [open [file join $out summary.txt] w]
dict for {key value} $final {
    if {$key eq "status"} {
        puts $fp "post_route_gate_status=$value"
    } else {
        puts $fp "$key=$value"
    }
}
puts $fp "checkpoint=$delivered_dcp"
puts $fp "jobs=$jobs"
puts $fp "checkpoint_size_bytes=[file size $delivered_dcp]"
puts $fp "checkpoint_sha256=$dcp_hash"
puts $fp "ooc_route_artifact=$ooc_route_artifact"
puts $fp "ooc_route_authorization_verified=1"
puts $fp "ooc_route_summary_sha256=$ooc_route_summary_sha256"
puts $fp "ooc_route_post_route_dcp_sha256=$ooc_route_dcp_sha256"
if {$rtl_variant eq "P16_NOCLIP"} {
    puts $fp "p16_post_opt_summary=$p16_post_opt_summary"
    puts $fp "p16_post_opt_summary_sha256=$expected_p16_post_opt_summary_sha"
    puts $fp "p16_production_region2_summary=$p16_production_region2_summary"
    puts $fp "p16_production_region2_summary_sha256=$expected_p16_production_region2_summary_sha"
    puts $fp "p16_production_dcp_sha256=$expected_p16_production_dcp_sha"
}
puts $fp "complete_input_sha_verified=1"
puts $fp "complete_input_count=$expected_board_input_count"
puts $fp "complete_input_manifest_sha256=$expected_input_manifest_sha"
puts $fp "immutable_input_count=$expected_board_immutable_input_count"
puts $fp "immutable_input_manifest_sha256=$expected_immutable_input_manifest_sha"
puts $fp "immutable_input_sha_verified=1"
puts $fp "recursive_source_sha_verified=1"
puts $fp "recursive_source_manifest_count=3"
puts $fp "recursive_rtl_source_count=87"
puts $fp "recursive_source_closure_count=90"
puts $fp "status=V5_BOARD_BITSTREAM_PASS"
close $fp
puts "V5_BOARD_BITSTREAM_PASS bitstream=$delivered_bit sha256=$bit_hash"
close_project
