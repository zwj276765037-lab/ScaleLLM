# Strict read-only pre-place audit for the frozen fresh V5 post-opt DCP.
# It creates the canonical P2 cohort16 column-shard pblocks in memory, proves
# membership
# and hard-resource coverage, then exits without implementation or checkpoint
# writes.  The launcher freezes every input and preserves PASS/FAIL evidence.

set script_dir [file dirname [file normalize [info script]]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PREPLACE_AUDIT_DIR)]
set input_sha [file normalize $::env(HAP_PREPLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PREPLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PREPLACE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_PREPLACE_GEOMETRY_LIB)]
set expected_launcher [file normalize $::env(HAP_PREPLACE_LAUNCHER)]
set audit_script [file normalize [info script]]

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
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_verify_manifest {path expected_count expected_sha} {
    if {[hap_sha256 $path] ne $expected_sha} {
        error "Pre-place input manifest identity mismatch"
    }
    set seen [dict create]
    set count 0
    foreach raw [split [hap_read_nonempty $path "input SHA manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed pre-place SHA row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $seen $normalized]} {
            error "Duplicate pre-place SHA path: $normalized"
        }
        hap_read_nonempty $normalized "frozen pre-place input"
        if {[hap_sha256 $normalized] ne $expected} {
            error "Pre-place input SHA mismatch: $normalized"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "Pre-place input SHA cardinality mismatch: $count"
    }
    return $seen
}

proc hap_create_hard_slr_pblock {name target cells} {
    if {[llength $cells] == 0} {
        error "V5 pre-place selector is empty: $name"
    }
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] $cells
    resize_pblock [get_pblocks $name] -add [list SLR${target}]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "Pre-place audit requires a fresh Vivado process"
}
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha]} {
    error "Malformed expected pre-place DCP SHA256: $expected_dcp_sha"
}
if {![regexp {^[0-9a-f]{64}$} $expected_manifest_sha]} {
    error "Malformed expected pre-place manifest SHA256: $expected_manifest_sha"
}
if {![file exists $out] || ![file isdirectory $out]} {
    error "Missing fresh pre-place audit directory: $out"
}
set frozen [hap_verify_manifest $input_sha 5 $expected_manifest_sha]
foreach path [list $dcp $selector_lib $geometry_lib $audit_script \
        $expected_launcher] {
    if {![dict exists $frozen $path]} {
        error "Required pre-place input absent from manifest: $path"
    }
}
set actual_dcp_sha [hap_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "Pre-place DCP identity mismatch"
}

source $selector_lib
source $geometry_lib
open_checkpoint $dcp
set contract_variant P2_COHORT16_COL2_12_2
set plan [hap_v5_floorplan::discover $contract_variant]
set projection_root [file dirname \
    [get_property NAME [dict get $plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set geometry_prefix p3_

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "V5 pre-place compute-net selector is empty"
}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
set compute_clock_buffer_none_count 0
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "V5 pre-place compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
    incr compute_clock_buffer_none_count
}

# These two V5 timing/resource repairs are intentionally rediscovered from the
# opened checkpoint instead of being inferred from its total resource count.
# A resource-compatible checkpoint containing the superseded frontend or no
# branch-local queues must never enter placement.
proc hap_preplace_cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}
proc hap_preplace_property_is_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}
proc hap_preplace_metadata_local_write_audit {} {
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_mlp_weight_meta_uram_leaf ||
        ORIG_REF_NAME == hap_mlp_weight_meta_uram_leaf}]
    if {[llength $leaves] != 4} {
        error "Metadata leaf count mismatch: [llength $leaves]"
    }
    set wr_en [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*}]
    set wr_addr [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*}]
    set wr_data [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*}]
    if {[llength $wr_en] != 4 || [llength $wr_addr] != 70 ||
        [llength $wr_data] != 896} {
        error "Metadata local write boundary mismatch: en=[llength $wr_en] addr=[llength $wr_addr] data=[llength $wr_data]"
    }
    set protected 0
    foreach cell [concat $wr_en $wr_addr $wr_data] {
        if {![hap_preplace_property_is_true $cell DONT_TOUCH]} {
            error "Metadata local write FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 970} {
        error "Metadata protected local write FF mismatch: $protected"
    }
    return [list [llength $leaves] [llength $wr_en] [llength $wr_addr] \
        [llength $wr_data] $protected]
}
proc hap_preplace_mlp_capture_leaf_audit {branches} {
    if {[llength $branches] != 2} {
        error "Expected two MLP capture-leaf branches, got [llength $branches]"
    }
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_a8w4_ingress_capture_leaf ||
        ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf}]
    set leaf_lut [get_cells -quiet -hierarchical -filter {
        NAME =~ */u_leaf && REF_NAME == LUT1}]
    if {[llength $leaves] != 1632 || [llength $leaf_lut] != 1632} {
        error "MLP capture-leaf total mismatch: instances=[llength $leaves] lut1=[llength $leaf_lut]"
    }
    set branch_leaf_counts {}
    set branch_lut_counts {}
    foreach branch [lsort -dictionary $branches] {
        set root [get_property NAME $branch]
        set local_leaves {}
        set local_lut {}
        foreach cell $leaves {
            if {[string match "${root}/*" [get_property NAME $cell]]} {
                lappend local_leaves $cell
            }
        }
        foreach cell $leaf_lut {
            if {[string match "${root}/*" [get_property NAME $cell]]} {
                lappend local_lut $cell
            }
        }
        if {[llength $local_leaves] != 816 || [llength $local_lut] != 816} {
            error "MLP capture-leaf branch mismatch: branch=$root instances=[llength $local_leaves] lut1=[llength $local_lut]"
        }
        lappend branch_leaf_counts [llength $local_leaves]
        lappend branch_lut_counts [llength $local_lut]
    }
    return [list [llength $leaves] [llength $leaf_lut] \
        [lindex $branch_leaf_counts 0] [lindex $branch_leaf_counts 1] \
        [lindex $branch_lut_counts 0] [lindex $branch_lut_counts 1]]
}
proc hap_preplace_mlp_local_clear_audit {branches} {
    if {[llength $branches] != 2} {
        error "Expected two MLP local branches, got [llength $branches]"
    }
    set total 0
    set protected 0
    set branch_counts {}
    foreach branch [lsort -dictionary $branches] {
        set branch_name [get_property NAME $branch]
        set clear_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $clear_ff] != 1} {
            error "MLP branch local-clear count mismatch: branch=$branch_name count=[llength $clear_ff]"
        }
        lappend branch_counts [llength $clear_ff]
        incr total [llength $clear_ff]
        foreach cell $clear_ff {
            if {![hap_preplace_property_is_true $cell DONT_TOUCH]} {
                error "MLP local clear FF lost DONT_TOUCH: $cell"
            }
            incr protected
        }
    }
    return [list $total $protected \
        [lindex $branch_counts 0] [lindex $branch_counts 1]]
}
proc hap_preplace_swiglu_local_clear_audit {} {
    set frontends [hap_preplace_cells_of_module \
        hap_mlp_swiglu_product_frontend16_q4]
    set row_leaves [hap_preplace_cells_of_module \
        hap_mlp_swiglu_row_stream8_q4]
    if {[llength $frontends] != 1 || [llength $row_leaves] != 2} {
        error "SwiGLU local-clear hierarchy mismatch: frontends=[llength $frontends] rows=[llength $row_leaves]"
    }
    set root_name [get_property NAME [lindex $frontends 0]]
    set control [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/control_clear_local_r_reg* && REF_NAME =~ FD*"]
    set hadamard [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/hadamard_clear_local_r_reg* && REF_NAME =~ FD*"]
    set quantizer [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/quantizer_clear_local_r_reg* && REF_NAME =~ FD*"]
    set row_candidates [get_cells -quiet -hierarchical -filter {
        NAME =~ */clear_local_r_reg* && REF_NAME =~ FD*}]
    set row_clear {}
    foreach leaf [lsort -dictionary $row_leaves] {
        set prefix "[get_property NAME $leaf]/"
        set local {}
        foreach cell $row_candidates {
            if {[string first $prefix [get_property NAME $cell]] == 0} {
                lappend local $cell
            }
        }
        if {[llength $local] != 1} {
            error "SwiGLU row local-clear count mismatch: leaf=$leaf count=[llength $local]"
        }
        set row_clear [concat $row_clear $local]
    }
    set row_clear [lsort -dictionary -unique $row_clear]
    if {[llength $control] != 1 || [llength $hadamard] != 1 ||
        [llength $quantizer] != 4 || [llength $row_clear] != 2} {
        error "SwiGLU local-clear FF mismatch: control=[llength $control] hadamard=[llength $hadamard] quantizer=[llength $quantizer] row=[llength $row_clear]"
    }
    set all_clear [lsort -dictionary -unique \
        [concat $control $hadamard $quantizer $row_clear]]
    if {[llength $all_clear] != 8} {
        error "SwiGLU local-clear total mismatch: [llength $all_clear]"
    }
    set protected 0
    foreach cell $all_clear {
        if {![hap_preplace_property_is_true $cell DONT_TOUCH]} {
            error "SwiGLU local-clear FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    set d_pins [get_pins -quiet -of_objects $all_clear -filter \
        {REF_PIN_NAME == D}]
    if {[llength $d_pins] != 8} {
        error "SwiGLU local-clear D-pin mismatch: [llength $d_pins]"
    }
    set clear_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $d_pins]]
    set direct_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [get_pins -quiet -leaf -of_objects $clear_nets \
            -filter {DIRECTION == IN}]]]
    set bypass {}
    foreach cell $direct_cells {
        set cell_name [get_property NAME $cell]
        if {[string match "${root_name}/*" $cell_name] &&
            [lsearch -exact $all_clear $cell] < 0} {
            lappend bypass $cell
        }
    }
    set bypass [lsort -dictionary -unique $bypass]
    if {[llength $bypass] != 0} {
        error "SwiGLU clear directly bypasses local FFs: $bypass"
    }
    return [dict create total 8 protected $protected control 1 hadamard 1 \
        quantizer 4 row 2 input_nets [llength $clear_nets] bypass 0]
}
proc hap_preplace_mlp_clear_boundary_audit {branches} {
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    if {[llength $central] != 1} {
        error "Expected one central MLP maintenance clear FF, got [llength $central]"
    }
    set q [get_pins -quiet -of_objects $central -filter \
        {REF_PIN_NAME == Q}]
    if {[llength $q] != 1} {
        error "Central MLP maintenance clear Q-pin count mismatch"
    }
    set endpoint_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [all_fanout -flat -endpoints_only -from $q]]]
    set clear_ff {}
    foreach branch $branches {
        set branch_name [get_property NAME $branch]
        set clear_ff [concat $clear_ff [get_cells -quiet -hierarchical \
            -filter "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]]
    }
    set clear_ff [lsort -dictionary -unique $clear_ff]
    set clear_endpoints {}
    foreach cell $clear_ff {
        if {[lsearch -exact $endpoint_cells $cell] >= 0} {
            lappend clear_endpoints $cell
        }
    }
    set clear_endpoints [lsort -dictionary -unique $clear_endpoints]
    if {[llength $clear_endpoints] != 2} {
        error "Central MLP clear does not reach both local boundaries: $clear_endpoints"
    }
    set central_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $q]]
    if {[llength $central_nets] != 1} {
        error "Central MLP maintenance clear net count mismatch"
    }
    set direct_sink_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [get_pins -quiet -leaf -of_objects $central_nets \
            -filter {DIRECTION == IN}]]]
    set direct_branch_state {}
    foreach branch $branches {
        set branch_name [get_property NAME $branch]
        foreach cell $direct_sink_cells {
            if {[string match "${branch_name}/*" \
                    [get_property NAME $cell]]} {
                lappend direct_branch_state $cell
            }
        }
    }
    set direct_branch_state [lsort -dictionary -unique $direct_branch_state]
    if {[llength $direct_branch_state] != 0} {
        error "Central MLP clear directly consumes branch state: $direct_branch_state"
    }
    return [list [llength $central] [llength $clear_endpoints] \
        [llength $direct_branch_state]]
}
set compact_input_frontend [hap_preplace_cells_of_module \
    hap_mlp_input_frontend16_compact_cache]
set down_elastic2 [hap_preplace_cells_of_module \
    hap_mlp_down_branch_elastic2_s24]
set mlp_local_branches [hap_preplace_cells_of_module \
    hap_mlp_shared_local_slice8x12_s43_s45]
lassign [hap_preplace_mlp_local_clear_audit $mlp_local_branches] \
    mlp_local_clear_ff mlp_local_clear_protected_ff \
    branch0_local_clear_ff branch1_local_clear_ff
set swiglu_clear [hap_preplace_swiglu_local_clear_audit]
lassign [hap_preplace_mlp_clear_boundary_audit $mlp_local_branches] \
    mlp_central_clear_ff mlp_central_clear_branch_endpoints \
    mlp_central_clear_direct_branch_state
lassign [hap_preplace_metadata_local_write_audit] \
    metadata_leaf_instances metadata_local_wr_en_ff \
    metadata_local_wr_addr_ff metadata_local_wr_data_ff \
    metadata_local_write_protected_ff
lassign [hap_preplace_mlp_capture_leaf_audit $mlp_local_branches] \
    mlp_capture_leaf_instances mlp_capture_leaf_lut1 \
    branch0_capture_leaf_instances branch1_capture_leaf_instances \
    branch0_capture_leaf_lut1 branch1_capture_leaf_lut1
foreach spec [hap_v5_floorplan::pblock_specs $plan $contract_variant] {
    hap_create_hard_slr_pblock [dict get $spec name] \
        [dict get $spec target] [dict get $plan [dict get $spec key]]
}
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0
set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1]
set audit [hap_v5_floorplan::audit_pblock_contract $plan 0 $contract_variant \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix]]
set total_pblock_count [llength [get_pblocks -quiet]]
hap_v5_floorplan::write_discovery $plan \
    [file join $out selectors.txt] V5_PRE_PLACE_SELECTORS_PASS
hap_v5_floorplan::write_pblock_audit $audit \
    [file join $out pblocks.txt] V5_PRE_PLACE_PBLOCKS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry.txt] \
    V5_PRE_PLACE_ATTENTION_GEOMETRY_PASS
report_drc -file [file join $out drc_pre_place.rpt]
set pre_place_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]

set status [expr {
    [dict get $plan total_dsp] == 5453 &&
    [dict get $plan total_uram] == 752 &&
    [dict get $plan kernel_dsp] == 3072 &&
    [dict get $plan row_leaf_count] == 2 &&
    [dict get $plan leaf0_dsp] == 2 &&
    [dict get $plan leaf1_dsp] == 2 &&
    [dict get $plan outer0_dsp] == 1538 &&
    [dict get $plan outer2_dsp] == 1538 &&
    [dict get $plan outer0_ramb36] == 102 &&
    [dict get $plan outer2_ramb36] == 102 &&
    [dict get $plan move0] == 16 &&
    [dict get $plan center_lanes] == 96 &&
    [dict get $plan move2] == 16 &&
    [dict get $plan planned_slr0_dsp] == 1862 &&
    [dict get $plan planned_slr1_dsp] == 1781 &&
    [dict get $plan planned_slr2_dsp] == 1810 &&
    [dict get $plan projection_weight_capture_ok] == 1 &&
    [llength $compact_input_frontend] == 1 &&
    [llength $down_elastic2] == 2 &&
    $mlp_local_clear_ff == 2 && $mlp_local_clear_protected_ff == 2 &&
    $branch0_local_clear_ff == 1 && $branch1_local_clear_ff == 1 &&
    [dict get $swiglu_clear total] == 8 &&
    [dict get $swiglu_clear protected] == 8 &&
    [dict get $swiglu_clear control] == 1 &&
    [dict get $swiglu_clear hadamard] == 1 &&
    [dict get $swiglu_clear quantizer] == 4 &&
    [dict get $swiglu_clear row] == 2 &&
    [dict get $swiglu_clear bypass] == 0 &&
    $mlp_central_clear_ff == 1 &&
    $mlp_central_clear_branch_endpoints == 2 &&
    $mlp_central_clear_direct_branch_state == 0 &&
    $metadata_leaf_instances == 4 && $metadata_local_wr_en_ff == 4 &&
    $metadata_local_wr_addr_ff == 70 && $metadata_local_wr_data_ff == 896 &&
    $metadata_local_write_protected_ff == 970 &&
    $mlp_capture_leaf_instances == 1632 && $mlp_capture_leaf_lut1 == 1632 &&
    $branch0_capture_leaf_instances == 816 &&
    $branch1_capture_leaf_instances == 816 &&
    $branch0_capture_leaf_lut1 == 816 && $branch1_capture_leaf_lut1 == 816 &&
    $compute_clock_buffer_none_count > 0 &&
    [dict get $audit ok] == 1 &&
    [dict get $audit pblock_count] == 11 &&
    [dict get $geometry_audit pblock_count] == 10 &&
    $total_pblock_count == 21 &&
    [hap_projection_ooc_floorplan::region0_input_localization_ok \
        $geometry_plan] &&
    [hap_projection_ooc_floorplan::region3_input_localization_ok \
        $geometry_plan] &&
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
        $geometry_plan] &&
    [dict get $audit dsp_coverage] == 5453 &&
    [dict get $audit uram_coverage] == 752 &&
    [dict get $audit placed_wrong] == 0 &&
    $pre_place_drc_errors == 0 ?
    "V5_PRE_PLACE_CONTRACT_AUDIT_PASS" : "FAIL"
}]
set handle [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] evidence_class V5_PRE_PLACE_READ_ONLY_CONTRACT \
    input_dcp $dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_sha256 $input_sha] \
    input_manifest_entries 5 provenance_verified 1 \
    contract_variant [dict get $plan contract_variant] \
    dsp48e2 [dict get $plan total_dsp] uram288 [dict get $plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $plan kernel_dsp] \
    swiglu_structure 1/2/1/0/4/2 \
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
    leaf0_dsp48e2 [dict get $plan leaf0_dsp] \
    leaf1_dsp48e2 [dict get $plan leaf1_dsp] \
    leaf0_ramb36e2 [dict get $plan leaf0_ramb36] \
    leaf1_ramb36e2 [dict get $plan leaf1_ramb36] \
    outer0_dsp48e2 [dict get $plan outer0_dsp] \
    outer2_dsp48e2 [dict get $plan outer2_dsp] \
    outer0_ramb36e2 [dict get $plan outer0_ramb36] \
    outer2_ramb36e2 [dict get $plan outer2_ramb36] \
    moved_lanes_slr0 [dict get $plan move0] \
    center_lanes_slr1 [dict get $plan center_lanes] \
    moved_lanes_slr2 [dict get $plan move2] \
    planned_slr0_dsp48e2 [dict get $plan planned_slr0_dsp] \
    planned_slr1_dsp48e2 [dict get $plan planned_slr1_dsp] \
    planned_slr2_dsp48e2 [dict get $plan planned_slr2_dsp] \
    compact_input_frontend_instances [llength $compact_input_frontend] \
    down_elastic2_instances [llength $down_elastic2] \
    mlp_local_clear_ff $mlp_local_clear_ff \
    mlp_local_clear_protected_ff $mlp_local_clear_protected_ff \
    branch0_local_clear_ff $branch0_local_clear_ff \
    branch1_local_clear_ff $branch1_local_clear_ff \
    swiglu_local_clear_ff [dict get $swiglu_clear total] \
    swiglu_local_clear_protected_ff [dict get $swiglu_clear protected] \
    swiglu_control_clear_ff [dict get $swiglu_clear control] \
    swiglu_hadamard_clear_ff [dict get $swiglu_clear hadamard] \
    swiglu_quantizer_clear_ff [dict get $swiglu_clear quantizer] \
    swiglu_row_clear_ff [dict get $swiglu_clear row] \
    swiglu_clear_input_nets [dict get $swiglu_clear input_nets] \
    swiglu_direct_clear_bypass_state [dict get $swiglu_clear bypass] \
    mlp_central_clear_ff $mlp_central_clear_ff \
    mlp_central_clear_branch_endpoints \
        $mlp_central_clear_branch_endpoints \
    mlp_central_clear_direct_branch_state \
        $mlp_central_clear_direct_branch_state \
    metadata_leaf_instances $metadata_leaf_instances \
    metadata_local_wr_en_ff $metadata_local_wr_en_ff \
    metadata_local_wr_addr_ff $metadata_local_wr_addr_ff \
    metadata_local_wr_data_ff $metadata_local_wr_data_ff \
    metadata_local_write_protected_ff $metadata_local_write_protected_ff \
    mlp_capture_leaf_instances $mlp_capture_leaf_instances \
    mlp_capture_leaf_lut1 $mlp_capture_leaf_lut1 \
    branch0_capture_leaf_instances $branch0_capture_leaf_instances \
    branch1_capture_leaf_instances $branch1_capture_leaf_instances \
    branch0_capture_leaf_lut1 $branch0_capture_leaf_lut1 \
    branch1_capture_leaf_lut1 $branch1_capture_leaf_lut1 \
    compute_clock_buffer_none_nets $compute_clock_buffer_none_count \
    compute_clock_buffer_none_ok 1 \
    projection_geometry_root $projection_root \
    geometry_pblock_prefix $geometry_prefix \
    canonical_pblock_count [dict get $audit pblock_count] \
    geometry_pblock_count [dict get $geometry_audit pblock_count] \
    geometry_region0_input_primitives \
        [llength [dict get $geometry_plan region0_input_primitives]] \
    geometry_region3_input_primitives \
        [llength [dict get $geometry_plan region3_input_primitives]] \
    geometry_owner_region2_weight_primitives \
        [llength [dict get $geometry_plan owner_region2_weight_primitives]] \
    geometry_region0_input_ok \
        [hap_projection_ooc_floorplan::region0_input_localization_ok \
            $geometry_plan] \
    geometry_region3_input_ok \
        [hap_projection_ooc_floorplan::region3_input_localization_ok \
            $geometry_plan] \
    geometry_owner_region2_weight_ok \
        [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $geometry_plan] \
    pblock_count $total_pblock_count \
    pblock_dsp_coverage [dict get $audit dsp_coverage] \
    pblock_uram_coverage [dict get $audit uram_coverage] \
    pblock_overlap 0 pblock_wrong_slr [dict get $audit placed_wrong] \
    pre_place_drc_errors $pre_place_drc_errors \
    checkpoint_written 0 implementation_commands_run 0 status $status] {
    puts $handle "$key=$value"
}
close $handle
if {$status ne "V5_PRE_PLACE_CONTRACT_AUDIT_PASS"} {
    error "V5 pre-place contract audit failed"
}
close_design
