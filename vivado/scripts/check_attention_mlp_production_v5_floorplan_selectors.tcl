set script_dir [file dirname [file normalize [info script]]]
set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_SELECTOR_DIR)]
set selector_lib [file normalize $::env(HAP_SELECTOR_LIB)]
set expected_launcher [file normalize $::env(HAP_SELECTOR_LAUNCHER)]
set input_sha [file normalize $::env(HAP_SELECTOR_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_SELECTOR_INPUT_MANIFEST_SHA256)
set fixed_selector_lib [file normalize [file join $script_dir \
    v5_production_floorplan_selectors.tcl]]
set fixed_launcher [file normalize [file join $script_dir \
    run_attention_mlp_production_v5_floorplan_selector_check.sh]]

proc hap_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set handle [open $path r]
    set text [read $handle]
    close $handle
    return $text
}

proc hap_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 digest for $path: $digest"
    }
    return $digest
}

proc hap_verify_sha_manifest {path expected_count expected_manifest_sha} {
    set actual_manifest_sha [hap_sha256 $path]
    if {$actual_manifest_sha ne $expected_manifest_sha} {
        error "Selector input-manifest identity mismatch: expected=$expected_manifest_sha actual=$actual_manifest_sha"
    }
    set count 0
    set seen [dict create]
    foreach raw [split [hap_read_nonempty $path \
            "selector input SHA manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed selector input SHA row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $seen $normalized]} {
            error "Duplicate selector input SHA path: $normalized"
        }
        hap_read_nonempty $normalized "frozen selector input"
        set actual [hap_sha256 $normalized]
        if {$actual ne $expected} {
            error "Selector input SHA mismatch: file=$normalized expected=$expected actual=$actual"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "Selector input SHA cardinality mismatch: expected=$expected_count actual=$count"
    }
    return $seen
}

proc hap_require_plan_keys {plan keys} {
    foreach key $keys {
        if {![dict exists $plan $key]} {
            error "V5 P2 discovery is missing required key: $key"
        }
    }
}

proc hap_object_names {cells label} {
    set names {}
    foreach cell $cells {
        set name [get_property NAME $cell]
        if {$name eq ""} {
            error "V5 selector returned a nameless cell: $label"
        }
        lappend names $name
    }
    set unique [lsort -dictionary -unique $names]
    if {[llength $unique] != [llength $names]} {
        error "V5 selector contains duplicate cells: $label"
    }
    return $unique
}

proc hap_name_union {args} {
    set result {}
    foreach values $args {set result [concat $result $values]}
    return [lsort -dictionary -unique $result]
}

proc hap_name_intersection {left right} {
    set present [dict create]
    foreach value $right {dict set present $value 1}
    set result {}
    foreach value $left {
        if {[dict exists $present $value]} {lappend result $value}
    }
    return [lsort -dictionary -unique $result]
}

proc hap_require_primitive_collection {cells label} {
    if {[llength $cells] == 0} {
        error "V5 selector primitive collection is empty: $label"
    }
    foreach cell $cells {
        if {![get_property IS_PRIMITIVE $cell]} {
            error "V5 selector collection contains a non-primitive: label=$label cell=$cell"
        }
    }
}

proc hap_count_ref {cells ref_name} {
    set count 0
    foreach cell $cells {
        if {[get_property REF_NAME $cell] eq $ref_name} {incr count}
    }
    return $count
}

proc hap_ref_names {cells ref_name label} {
    set selected {}
    foreach cell $cells {
        if {[get_property REF_NAME $cell] eq $ref_name} {
            lappend selected $cell
        }
    }
    return [hap_object_names $selected $label]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 selector audit requires a fresh process with no open design"
}
if {![file exists $out] || ![file isdirectory $out]} {
    error "Missing selector evidence directory: $out"
}
if {$selector_lib ne $fixed_selector_lib ||
    $expected_launcher ne $fixed_launcher} {
    error "V5 selector audit received a non-canonical library or launcher path"
}
if {$input_sha ne [file normalize [file join $out INPUT_SHA256SUMS]]} {
    error "V5 selector input manifest is outside the fresh evidence directory"
}
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    ![regexp {^[0-9a-f]{64}$} $expected_manifest_sha]} {
    error "Malformed expected selector SHA256 identity"
}
hap_read_nonempty $dcp "V5 post-opt DCP"
set frozen [hap_verify_sha_manifest $input_sha 4 $expected_manifest_sha]
foreach required [list $dcp $selector_lib $audit_script \
        $expected_launcher] {
    if {![dict exists $frozen [file normalize $required]]} {
        error "Required selector input is absent from SHA manifest: $required"
    }
}
set actual_dcp_sha [hap_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "V5 selector DCP identity mismatch: expected=$expected_dcp_sha actual=$actual_dcp_sha"
}

# This is the selector audit's sole source command.  The launcher statically
# permits exactly this line, and the path is bound above to the four-row frozen
# input manifest and the canonical library beside this script.
source $selector_lib
open_checkpoint $dcp

set plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
hap_require_plan_keys $plan {
    contract_variant part top total_dsp total_uram kernel_dsp
    attention_board_variant attention_dsp center_projection_dsp
    center_nonprojection_dsp
    history2_count generic_repack_count swiglu_frontend_count
    row_leaf_count unique_hadamard_count fold2_count quantizer_count
    silu_count leaf0 leaf1 leaf0_primitives leaf1_primitives
    leaf0_dsp leaf1_dsp leaf0_ramb36 leaf1_ramb36
    branch0_primitives branch2_primitives branch0_dsp branch2_dsp
    outer0_primitives outer2_primitives outer0_dsp outer2_dsp
    outer0_ramb36 outer2_ramb36 attention_island_target
    attention_island_dsp attention_island_ramb36
    attention_island_ramb18 attention_island_uram
    attention_island_primitives lane0_primitives lane2_primitives
    attention_island_quantizer_overlap attention_island_row_cache_overlap
    projection_lane_count projection_lane_dsp attention_meta_uram
    move0 center_lanes move2 lanes_slr0 lanes_slr1 lanes_slr2
    center_primitives planned_slr0_dsp planned_slr1_dsp planned_slr2_dsp
    slr_dsp_limit slr_dsp_target
}
if {[dict get $plan contract_variant] ne "P2_COHORT16_COL2_12_2"} {
    error "V5 selector discovery returned the wrong contract variant"
}
if {[dict get $plan part] ne "xcvu9p-flga2104-2L-e" ||
    [dict get $plan top] ne "hap_attention_mlp_production_core" ||
    [dict get $plan attention_board_variant] ne "cohort16"} {
    error "Unexpected V5 selector design identity"
}

foreach {key expected} {
    total_dsp 5453 total_uram 752 kernel_dsp 3072 attention_dsp 2296
    center_projection_dsp 1632 center_nonprojection_dsp 149
    history2_count 2 generic_repack_count 0
    swiglu_frontend_count 1 row_leaf_count 2
    unique_hadamard_count 1 fold2_count 0 quantizer_count 4 silu_count 2
    leaf0_dsp 2 leaf1_dsp 2 leaf0_ramb36 6 leaf1_ramb36 6
    branch0_dsp 1536 branch2_dsp 1536
    outer0_dsp 1538 outer2_dsp 1538
    outer0_ramb36 102 outer2_ramb36 102
    attention_island_target 0 attention_island_dsp 52
    attention_island_ramb36 88 attention_island_ramb18 2
    attention_island_uram 0 attention_island_quantizer_overlap 0
    attention_island_row_cache_overlap 0 projection_lane_count 128
    projection_lane_dsp 17 attention_meta_uram 80 slr_dsp_limit 1900
} {
    if {[dict get $plan $key] != $expected} {
        error "V5 P2 selector contract mismatch: key=$key expected=$expected actual=[dict get $plan $key]"
    }
}
if {[llength [dict get $plan leaf0]] != 1 ||
    [llength [dict get $plan leaf1]] != 1} {
    error "V5 P2 row-leaf roots are not unique"
}

foreach key {leaf0_primitives leaf1_primitives branch0_primitives
        branch2_primitives outer0_primitives outer2_primitives
        lane0_primitives lane2_primitives attention_island_primitives
        center_primitives} {
    hap_require_primitive_collection [dict get $plan $key] $key
}
set leaf0_names [hap_object_names [dict get $plan leaf0_primitives] leaf0]
set leaf1_names [hap_object_names [dict get $plan leaf1_primitives] leaf1]
set branch0_names [hap_object_names \
    [dict get $plan branch0_primitives] branch0]
set branch2_names [hap_object_names \
    [dict get $plan branch2_primitives] branch2]
set outer0_names [hap_object_names [dict get $plan outer0_primitives] outer0]
set outer2_names [hap_object_names [dict get $plan outer2_primitives] outer2]
set expected_outer0 [hap_name_union $branch0_names $leaf0_names]
set expected_outer2 [hap_name_union $branch2_names $leaf1_names]
if {$outer0_names ne $expected_outer0 || $outer2_names ne $expected_outer2} {
    error "V5 P2 outer selector is not branch-plus-row-leaf complete"
}
set selected_overlap 0
foreach {left right} [list \
        $branch0_names $leaf0_names $branch2_names $leaf1_names \
        $leaf0_names $leaf1_names $outer0_names $outer2_names] {
    incr selected_overlap [llength [hap_name_intersection $left $right]]
}
if {$selected_overlap != 0} {
    error "V5 P2 outer/leaf selector sets overlap: $selected_overlap"
}
foreach {label key dsp ramb36} {
    leaf0 leaf0_primitives 2 6
    leaf1 leaf1_primitives 2 6
    outer0 outer0_primitives 1538 102
    outer2 outer2_primitives 1538 102
} {
    set cells [dict get $plan $key]
    if {[hap_count_ref $cells DSP48E2] != $dsp ||
        [hap_count_ref $cells RAMB36E2] != $ramb36 ||
        [hap_count_ref $cells RAMB18E2] != 0 ||
        [hap_count_ref $cells URAM288] != 0} {
        error "V5 P2 live primitive signature mismatch: $label"
    }
}

# The six physical DSP ownership classes must be pairwise disjoint and cover
# every live DSP in the exact frozen DCP.  This proves more than an arithmetic
# plan: no row-leaf, Attention lane, P0 island, or central DSP can silently be
# omitted or assigned to two SLR owners.
set dsp_partition [dict create \
    outer0 [hap_ref_names [dict get $plan outer0_primitives] \
        DSP48E2 outer0_dsp] \
    outer2 [hap_ref_names [dict get $plan outer2_primitives] \
        DSP48E2 outer2_dsp] \
    lane0 [hap_ref_names [dict get $plan lane0_primitives] \
        DSP48E2 lane0_dsp] \
    lane2 [hap_ref_names [dict get $plan lane2_primitives] \
        DSP48E2 lane2_dsp] \
    attention_island [hap_ref_names \
        [dict get $plan attention_island_primitives] \
        DSP48E2 attention_island_dsp] \
    center [hap_ref_names [dict get $plan center_primitives] DSP48E2 center_dsp]]
set dsp_labels [dict keys $dsp_partition]
set dsp_selector_overlap 0
for {set left_index 0} {$left_index < [llength $dsp_labels]} \
        {incr left_index} {
    for {set right_index [expr {$left_index + 1}]} \
            {$right_index < [llength $dsp_labels]} {incr right_index} {
        set left [dict get $dsp_partition [lindex $dsp_labels $left_index]]
        set right [dict get $dsp_partition [lindex $dsp_labels $right_index]]
        incr dsp_selector_overlap \
            [llength [hap_name_intersection $left $right]]
    }
}
set covered_dsp [hap_name_union \
    [dict get $dsp_partition outer0] \
    [dict get $dsp_partition outer2] \
    [dict get $dsp_partition lane0] \
    [dict get $dsp_partition lane2] \
    [dict get $dsp_partition attention_island] \
    [dict get $dsp_partition center]]
set all_dsp_names [hap_object_names \
    [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}] \
    all_dsp]
if {$dsp_selector_overlap != 0 || $covered_dsp ne $all_dsp_names ||
    [llength $covered_dsp] != 5453} {
    error "V5 P2 DSP selector partition failed: overlap=$dsp_selector_overlap coverage=[llength $covered_dsp] all=[llength $all_dsp_names]"
}

foreach key {move0 center_lanes move2 planned_slr0_dsp
        planned_slr1_dsp planned_slr2_dsp} {
    if {![string is integer -strict [dict get $plan $key]] ||
        [dict get $plan $key] < 0} {
        error "V5 P2 plan field is not a nonnegative integer: $key"
    }
}
set move0 [dict get $plan move0]
set move2 [dict get $plan move2]
set center_lanes [dict get $plan center_lanes]
set lane_dsp [dict get $plan projection_lane_dsp]
set planned0 [dict get $plan planned_slr0_dsp]
set planned1 [dict get $plan planned_slr1_dsp]
set planned2 [dict get $plan planned_slr2_dsp]
set equation0 [expr {[dict get $plan outer0_dsp] +
    [dict get $plan attention_island_dsp] + $move0 * $lane_dsp}]
set equation2 [expr {[dict get $plan outer2_dsp] + $move2 * $lane_dsp}]
set equation1 [expr {[dict get $plan total_dsp] - $equation0 - $equation2}]
if {$move0 + $center_lanes + $move2 != 128 ||
    $move0 != 16 || $center_lanes != 96 || $move2 != 16 ||
    [llength [dict get $plan lanes_slr0]] != $move0 ||
    [llength [dict get $plan lanes_slr1]] != $center_lanes ||
    [llength [dict get $plan lanes_slr2]] != $move2 ||
    $planned0 != $equation0 || $planned1 != $equation1 ||
    $planned2 != $equation2 || $planned0 != 1862 ||
    $planned1 != 1781 || $planned2 != 1810 ||
    [hap_count_ref [dict get $plan center_primitives] DSP48E2] != $planned1 ||
    $planned0 + $planned1 + $planned2 != [dict get $plan total_dsp] ||
    [dict get $plan projection_weight_capture_ok] != 1 ||
    $planned0 > 1900 || $planned1 > 1900 || $planned2 > 1900} {
    error "V5 P2 cohort16 column-shard/DSP planning equation failed"
}

hap_v5_floorplan::write_discovery $plan \
    [file join $out selectors.txt] V5_FLOORPLAN_SELECTORS_PASS

set summary [file join $out summary.txt]
set handle [open $summary w]
foreach {key value} [list \
    tool [version -short] \
    evidence_class V5_FLOORPLAN_SELECTOR_READ_ONLY_REOPEN \
    dcp $dcp input_dcp_sha256 $actual_dcp_sha \
    input_selector_library_sha256 [hap_sha256 $selector_lib] \
    input_selector_tcl_sha256 [hap_sha256 $audit_script] \
    input_launcher_sha256 [hap_sha256 $expected_launcher] \
    input_manifest_sha256 [hap_sha256 $input_sha] \
    input_sha_inprocess_verified 1 part [dict get $plan part] \
    top [dict get $plan top] contract_variant [dict get $plan contract_variant] \
    pblock_contract_variant [dict get $plan contract_variant] \
    dsp48e2 [dict get $plan total_dsp] uram288 [dict get $plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $plan kernel_dsp] \
    attention_board_variant [dict get $plan attention_board_variant] \
    attention_dsp48e2 [dict get $plan attention_dsp] \
    center_projection_dsp48e2 [dict get $plan center_projection_dsp] \
    center_nonprojection_dsp48e2 \
        [dict get $plan center_nonprojection_dsp] \
    history2_repack_instances [dict get $plan history2_count] \
    generic_repack_instances [dict get $plan generic_repack_count] \
    swiglu_frontend_instances [dict get $plan swiglu_frontend_count] \
    swiglu_row_leaf_instances [dict get $plan row_leaf_count] \
    swiglu_unique_hadamard_instances \
        [dict get $plan unique_hadamard_count] \
    swiglu_fold2_hadamard_instances [dict get $plan fold2_count] \
    swiglu_quantizer_instances [dict get $plan quantizer_count] \
    swiglu_silu_instances [dict get $plan silu_count] \
    leaf0_dsp48e2 [dict get $plan leaf0_dsp] \
    leaf1_dsp48e2 [dict get $plan leaf1_dsp] \
    leaf0_ramb36e2 [dict get $plan leaf0_ramb36] \
    leaf1_ramb36e2 [dict get $plan leaf1_ramb36] \
    branch0_dsp48e2 [dict get $plan branch0_dsp] \
    branch2_dsp48e2 [dict get $plan branch2_dsp] \
    outer0_dsp48e2 [dict get $plan outer0_dsp] \
    outer2_dsp48e2 [dict get $plan outer2_dsp] \
    outer0_ramb36e2 [dict get $plan outer0_ramb36] \
    outer2_ramb36e2 [dict get $plan outer2_ramb36] \
    outer_set_equation_ok 1 selected_set_overlap $selected_overlap \
    dsp_selector_overlap $dsp_selector_overlap \
    dsp_selector_coverage [llength $covered_dsp] \
    attention_row_instances 1 kv_cache_instances 1 \
    kv_quantizer4_instances 1 \
    attention_island_target_slr [dict get $plan attention_island_target] \
    attention_island_dsp48e2 [dict get $plan attention_island_dsp] \
    attention_island_ramb36e2 [dict get $plan attention_island_ramb36] \
    attention_island_ramb18e2 [dict get $plan attention_island_ramb18] \
    attention_island_uram288 [dict get $plan attention_island_uram] \
    attention_island_quantizer_overlap \
        [dict get $plan attention_island_quantizer_overlap] \
    attention_island_row_cache_overlap \
        [dict get $plan attention_island_row_cache_overlap] \
    projection_lane_instances [dict get $plan projection_lane_count] \
    projection_lane_dsp48e2 [dict get $plan projection_lane_dsp] \
    raw_weight_push_loads [dict get $plan raw_weight_push_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_nets [dict get $plan weight_data_capture_nets] \
    weight_data_capture_loads \
        [dict get $plan weight_data_capture_min]/[dict get $plan weight_data_capture_max] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_nets [dict get $plan weight_meta_capture_nets] \
    weight_meta_capture_loads \
        [dict get $plan weight_meta_capture_min]/[dict get $plan weight_meta_capture_max] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_nets [dict get $plan weight_group_capture_nets] \
    weight_group_capture_loads \
        [dict get $plan weight_group_capture_min]/[dict get $plan weight_group_capture_max] \
    projection_weight_capture_ok [dict get $plan projection_weight_capture_ok] \
    attention_metadata_uram288 [dict get $plan attention_meta_uram] \
    moved_lanes_slr0 $move0 center_lanes_slr1 $center_lanes \
    moved_lanes_slr2 $move2 planned_slr0_dsp48e2 $planned0 \
    planned_slr1_dsp48e2 $planned1 planned_slr2_dsp48e2 $planned2 \
    per_slr_dsp_limit [dict get $plan slr_dsp_limit] \
    center_slr_dsp_target [dict get $plan slr_dsp_target] \
    dsp_plan_equation_ok 1 checkpoint_written 0 \
    implementation_commands_run 0 status V5_FLOORPLAN_SELECTORS_PASS] {
    puts $handle "$key=$value"
}
close $handle

puts "V5_FLOORPLAN_SELECTORS VARIANT=[dict get $plan contract_variant] DSP=[dict get $plan total_dsp] OUTER=[dict get $plan outer0_dsp]/[dict get $plan outer2_dsp] PLAN=$planned0/$planned1/$planned2 LANES=$move0/$center_lanes/$move2 STATUS=PASS"
close_design
