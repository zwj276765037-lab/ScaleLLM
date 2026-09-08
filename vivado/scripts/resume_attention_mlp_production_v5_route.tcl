# V5-only production OOC route/resume flow.  The input is an independently
# accepted post-place checkpoint.  This flow never creates a bitstream: it
# preserves a routed DCP and diagnostics even when the final hard gate fails.

set hap_route_source_procs_only [expr {
    [info exists ::env(HAP_ROUTE_SOURCE_PROCS_ONLY)] &&
    $::env(HAP_ROUTE_SOURCE_PROCS_ONLY) eq "1"}]
set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
if {!$hap_route_source_procs_only} {
set in_dcp [file normalize $::env(HAP_POST_PLACE_DCP)]
set place_summary [file normalize $::env(HAP_PLACE_SUMMARY)]
set place_input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
set place_output_sha [file normalize $::env(HAP_PLACE_OUTPUT_SHA)]
set place_launcher_status [file normalize [file join \
    [file dirname $place_output_sha] launcher_status.txt]]
set place_dir [file dirname $place_output_sha]
set place_input_files [file normalize [file join $place_dir INPUT_FILES]]
set place_selectors [file normalize [file join \
    $place_dir selectors_post_place.txt]]
set place_pblocks [file normalize [file join \
    $place_dir pblocks_post_place.txt]]
set expected_place_input_manifest_sha \
    $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
set expected_place_output_manifest_sha \
    $::env(HAP_PLACE_OUTPUT_MANIFEST_SHA256)
set expected_route_input_manifest_sha \
    $::env(HAP_ROUTE_INPUT_MANIFEST_SHA256)
set route_input_sha [file normalize [file join \
    $::env(HAP_ROUTE_DIR) INPUT_SHA256SUMS]]
set out [file normalize $::env(HAP_ROUTE_DIR)]
set pre_physopt_directive [expr {
    [info exists ::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set route_directive [expr {[info exists ::env(HAP_ROUTE_DIRECTIVE)] ?
    $::env(HAP_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
set post_physopt_directive [expr {
    [info exists ::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_POST_ROUTE_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set expected_part xcvu9p-flga2104-2L-e
set expected_top hap_attention_mlp_production_core
set selector_lib [file join $script_dir v5_production_floorplan_selectors.tcl]
set geometry_lib [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
set geometry_prefix p3_
set io_audit [file join $script_dir \
    check_attention_mlp_production_io_selectors.tcl]
set clock_xdc [file join $root vivado constraints \
    attention_mlp_production_v5_ooc_clocks_100mhz.xdc]
file mkdir $out
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
set_param general.maxThreads $jobs
}

proc hap_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_write_text {path text} {
    set fh [open $path w]
    puts -nonewline $fh $text
    close $fh
}

proc hap_write_failure {out stage message} {
    set clean [string map [list "\n" " | " "\r" " "] $message]
    hap_write_text [file join $out failure.txt] \
        "stage=$stage\nmessage=$clean\nstatus=V5_PRODUCTION_OOC_ROUTE_FAIL\n"
}

proc hap_parse_summary {path {label "place summary"}} {
    set result [dict create]
    foreach raw [split [hap_read_nonempty $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([^=]+)=(.*)$} $line -> key value]} {
            error "Malformed $label row: $line"
        }
        set key [string trim $key]
        if {[dict exists $result $key]} {
            error "Duplicate $label key: $key"
        }
        dict set result $key $value
    }
    return $result
}

proc hap_require_summary {summary key expected} {
    if {![dict exists $summary $key]} {
        error "Place summary is missing '$key'"
    }
    set actual [dict get $summary $key]
    if {$actual ne $expected} {
        error "Place summary mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_require_plan_value {plan key expected} {
    if {![dict exists $plan $key]} {
        error "Fresh P2_COHORT16_COL2_12_2 live plan is missing '$key'"
    }
    set actual [dict get $plan $key]
    if {$actual ne $expected} {
        error "Fresh P2_COHORT16_COL2_12_2 live-plan mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_require_pblock_record_value {audit name key expected} {
    if {![dict exists $audit records $name $key]} {
        error "Fresh P2_COHORT16_COL2_12_2 pblock record is missing: $name/$key"
    }
    set actual [dict get $audit records $name $key]
    if {$actual ne $expected} {
        error "Fresh P2_COHORT16_COL2_12_2 pblock mismatch: $name/$key expected=$expected actual=$actual"
    }
}

proc hap_route_property_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc hap_route_cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}

proc hap_route_mlp_local_clear_audit {require_placed} {
    set branches [lsort -dictionary [hap_route_cells_of_module \
        hap_mlp_shared_local_slice8x12_s43_s45]]
    if {[llength $branches] != 2} {
        error "Route expected two MLP branches, got [llength $branches]"
    }
    set total 0
    set protected 0
    set branch_counts {}
    set branch_slr_counts {}
    set all_clear {}
    set wrong 0
    foreach branch $branches target {0 2} {
        set branch_name [get_property NAME $branch]
        set clear_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $clear_ff] != 1} {
            error "Route local-clear count mismatch: $branch_name"
        }
        foreach cell $clear_ff {
            if {![hap_route_property_true $cell DONT_TOUCH]} {
                error "Route local-clear FF lost DONT_TOUCH: $cell"
            }
            incr protected
        }
        incr total
        lappend branch_counts 1
        lappend all_clear {*}$clear_ff
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $clear_ff $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "Route local-clear FF has wrong/unresolved SLR: $branch_name"
            }
            lappend branch_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend branch_slr_counts {0 0 0}
        }
    }
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    if {[llength $central] != 1} {
        error "Route central maintenance-clear FF mismatch"
    }
    set q [get_pins -quiet -of_objects $central -filter {REF_PIN_NAME == Q}]
    if {[llength $q] != 1} {error "Route central clear Q mismatch"}
    set endpoint_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [all_fanout -flat -endpoints_only -from $q]]]
    set clear_endpoints {}
    foreach cell $all_clear {
        if {[lsearch -exact $endpoint_cells $cell] >= 0} {
            lappend clear_endpoints $cell
        }
    }
    set clear_endpoints [lsort -dictionary -unique $clear_endpoints]
    set all_clear [lsort -dictionary -unique $all_clear]
    if {[llength $clear_endpoints] != 2 || $clear_endpoints ne $all_clear} {
        error "Route central clear does not reach both local boundaries"
    }
    set central_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $q]]
    if {[llength $central_nets] != 1} {
        error "Route central clear net count mismatch"
    }
    set direct_sink_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [get_pins -quiet -leaf -of_objects $central_nets \
            -filter {DIRECTION == IN}]]]
    set direct_branch_state {}
    foreach branch $branches {
        set branch_name [get_property NAME $branch]
        foreach cell $direct_sink_cells {
            if {[string match "${branch_name}/*" [get_property NAME $cell]]} {
                lappend direct_branch_state $cell
            }
        }
    }
    set direct_branch_state [lsort -dictionary -unique $direct_branch_state]
    if {[llength $direct_branch_state] != 0} {
        error "Route central clear directly consumes branch state"
    }
    return [dict create total $total protected $protected \
        branch0 [lindex $branch_counts 0] branch1 [lindex $branch_counts 1] \
        branch0_slr [lindex $branch_slr_counts 0] \
        branch1_slr [lindex $branch_slr_counts 1] wrong $wrong \
        central [llength $central] \
        central_branch_endpoints [llength $clear_endpoints] \
        central_direct_branch_state [llength $direct_branch_state]]
}

proc hap_route_swiglu_local_clear_audit {} {
    set frontends [hap_route_cells_of_module \
        hap_mlp_swiglu_product_frontend16_q4]
    set row_leaves [hap_route_cells_of_module hap_mlp_swiglu_row_stream8_q4]
    if {[llength $frontends] != 1 || [llength $row_leaves] != 2} {
        error "Route SwiGLU local-clear hierarchy mismatch"
    }
    set root_name [get_property NAME [lindex $frontends 0]]
    set control [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/control_clear_local_r_reg* && REF_NAME =~ FD*"]
    set hadamard [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/hadamard_clear_local_r_reg* && REF_NAME =~ FD*"]
    set quantizer [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/quantizer_clear_local_r_reg* && REF_NAME =~ FD*"]
    set row_clear {}
    foreach leaf $row_leaves {
        set leaf_name [get_property NAME $leaf]
        set row_clear [concat $row_clear [get_cells -quiet -hierarchical \
            -filter "NAME =~ ${leaf_name}/clear_local_r_reg* && REF_NAME =~ FD*"]]
    }
    set row_clear [lsort -dictionary -unique $row_clear]
    if {[llength $control] != 1 || [llength $hadamard] != 1 ||
        [llength $quantizer] != 4 || [llength $row_clear] != 2} {
        error "Route SwiGLU local-clear FF mismatch"
    }
    set all_clear [lsort -dictionary -unique \
        [concat $control $hadamard $quantizer $row_clear]]
    if {[llength $all_clear] != 8} {
        error "Route SwiGLU local-clear total mismatch"
    }
    set protected 0
    foreach cell $all_clear {
        if {![hap_route_property_true $cell DONT_TOUCH]} {
            error "Route SwiGLU local-clear FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    set d_pins [get_pins -quiet -of_objects $all_clear -filter \
        {REF_PIN_NAME == D}]
    if {[llength $d_pins] != 8} {
        error "Route SwiGLU local-clear D-pin mismatch"
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
        error "Route SwiGLU clear directly bypasses local FFs: $bypass"
    }
    return [dict create total 8 protected $protected control 1 hadamard 1 \
        quantizer 4 row 2 input_nets [llength $clear_nets] bypass 0]
}

proc hap_route_metadata_local_write_audit {require_placed} {
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_mlp_weight_meta_uram_leaf ||
        ORIG_REF_NAME == hap_mlp_weight_meta_uram_leaf}]
    if {[llength $leaves] != 4} {error "Route metadata leaf count mismatch"}
    set wr_en [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*}]
    set wr_addr [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*}]
    set wr_data [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*}]
    if {[llength $wr_en] != 4 || [llength $wr_addr] != 70 ||
        [llength $wr_data] != 896} {
        error "Route metadata write-boundary cardinality mismatch"
    }
    set protected 0
    foreach cell [concat $wr_en $wr_addr $wr_data] {
        if {![hap_route_property_true $cell DONT_TOUCH]} {
            error "Route metadata write FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 970} {error "Route metadata protected-FF mismatch"}
    set leaf_counts {}
    set leaf_slr_counts {}
    set wrong 0
    foreach {leaf_name expected target} {
        u_gate_bank0 243 0
        u_gate_bank1 243 2
        u_down_bank0 242 1
        u_down_bank1 242 1
    } {
        set local_ff [get_cells -quiet -hierarchical -filter \
            "NAME =~ */${leaf_name}/wr_*_local_r_reg* && REF_NAME =~ FD*"]
        if {[llength $local_ff] != $expected} {
            error "Route metadata leaf FF mismatch: $leaf_name expected=$expected actual=[llength $local_ff]"
        }
        lappend leaf_counts [llength $local_ff]
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $local_ff $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "Route metadata leaf has wrong/unresolved SLR: $leaf_name"
            }
            lappend leaf_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend leaf_slr_counts {0 0 0}
        }
    }
    return [dict create leaves 4 wr_en 4 wr_addr 70 wr_data 896 \
        protected $protected leaf_counts $leaf_counts \
        leaf_slr_counts $leaf_slr_counts wrong $wrong]
}

proc hap_route_mlp_capture_leaf_audit {require_placed} {
    set branches [lsort -dictionary [hap_route_cells_of_module \
        hap_mlp_shared_local_slice8x12_s43_s45]]
    if {[llength $branches] != 2} {
        error "Route expected two MLP capture-leaf branches"
    }
    set leaves [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_a8w4_ingress_capture_leaf ||
        ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf}]
    set leaf_lut [get_cells -quiet -hierarchical -filter {
        NAME =~ */u_leaf && REF_NAME == LUT1}]
    if {[llength $leaves] != 1632 || [llength $leaf_lut] != 1632} {
        error "Route MLP capture-leaf total mismatch"
    }
    set branch_leaf_counts {}
    set branch_lut_counts {}
    set branch_slr_counts {}
    set wrong 0
    foreach branch $branches target {0 2} {
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
            error "Route MLP capture-leaf branch mismatch: $root"
        }
        lappend branch_leaf_counts [llength $local_leaves]
        lappend branch_lut_counts [llength $local_lut]
        if {$require_placed} {
            set audit [hap_v5_floorplan::wrong_slr_audit $local_lut $target]
            if {[dict get $audit wrong] != 0 ||
                [dict get $audit direct_slr_empty] != 0} {
                error "Route MLP capture leaf has wrong/unresolved SLR: $root"
            }
            lappend branch_slr_counts [dict get $audit slr_counts]
            incr wrong [dict get $audit wrong]
        } else {
            lappend branch_slr_counts {0 0 0}
        }
    }
    return [dict create instances [llength $leaves] lut1 [llength $leaf_lut] \
        branch_instances $branch_leaf_counts branch_lut1 $branch_lut_counts \
        branch_slr_counts $branch_slr_counts wrong $wrong]
}

proc hap_route_require_boundary_contract {clear metadata capture label} {
    foreach {key expected} {
        total 2 protected 2 branch0 1 branch1 1
        branch0_slr {1 0 0} branch1_slr {0 0 1} wrong 0
        central 1 central_branch_endpoints 2 central_direct_branch_state 0
    } {
        if {[dict get $clear $key] ne $expected} {
            error "$label local-clear mismatch: $key expected=$expected actual=[dict get $clear $key]"
        }
    }
    set swiglu [hap_route_swiglu_local_clear_audit]
    foreach {key expected} {
        total 8 protected 8 control 1 hadamard 1 quantizer 4 row 2 bypass 0
    } {
        if {[dict get $swiglu $key] ne $expected} {
            error "$label SwiGLU local-clear mismatch: $key expected=$expected actual=[dict get $swiglu $key]"
        }
    }
    foreach {key expected} {
        leaves 4 wr_en 4 wr_addr 70 wr_data 896 protected 970
        leaf_counts {243 243 242 242}
        leaf_slr_counts {{243 0 0} {0 0 243} {0 242 0} {0 242 0}}
        wrong 0
    } {
        if {[dict get $metadata $key] ne $expected} {
            error "$label metadata-boundary mismatch: $key expected=$expected actual=[dict get $metadata $key]"
        }
    }
    foreach {key expected} {
        instances 1632 lut1 1632 branch_instances {816 816}
        branch_lut1 {816 816}
        branch_slr_counts {{816 0 0} {0 0 816}} wrong 0
    } {
        if {[dict get $capture $key] ne $expected} {
            error "$label capture-leaf mismatch: $key expected=$expected actual=[dict get $capture $key]"
        }
    }
}

proc hap_route_write_boundary_audit {path clear metadata capture status} {
    set swiglu [hap_route_swiglu_local_clear_audit]
    set fp [open $path w]
    foreach {key value} [list \
        mlp_local_clear_ff [dict get $clear total] \
        mlp_local_clear_protected_ff [dict get $clear protected] \
        branch0_local_clear_ff [dict get $clear branch0] \
        branch1_local_clear_ff [dict get $clear branch1] \
        branch0_local_clear_slr [dict get $clear branch0_slr] \
        branch1_local_clear_slr [dict get $clear branch1_slr] \
        mlp_local_clear_wrong_slr [dict get $clear wrong] \
        mlp_central_clear_ff [dict get $clear central] \
        mlp_central_clear_branch_endpoints \
            [dict get $clear central_branch_endpoints] \
        mlp_central_clear_direct_branch_state \
            [dict get $clear central_direct_branch_state] \
        swiglu_local_clear_ff [dict get $swiglu total] \
        swiglu_local_clear_protected_ff [dict get $swiglu protected] \
        swiglu_control_clear_ff [dict get $swiglu control] \
        swiglu_hadamard_clear_ff [dict get $swiglu hadamard] \
        swiglu_quantizer_clear_ff [dict get $swiglu quantizer] \
        swiglu_row_clear_ff [dict get $swiglu row] \
        swiglu_clear_input_nets [dict get $swiglu input_nets] \
        swiglu_direct_clear_bypass_state [dict get $swiglu bypass] \
        metadata_leaf_instances [dict get $metadata leaves] \
        metadata_local_wr_en_ff [dict get $metadata wr_en] \
        metadata_local_wr_addr_ff [dict get $metadata wr_addr] \
        metadata_local_wr_data_ff [dict get $metadata wr_data] \
        metadata_local_write_protected_ff [dict get $metadata protected] \
        metadata_local_write_leaf_counts [dict get $metadata leaf_counts] \
        metadata_local_write_leaf_slr_counts \
            [dict get $metadata leaf_slr_counts] \
        metadata_local_write_wrong_slr [dict get $metadata wrong] \
        mlp_capture_leaf_instances [dict get $capture instances] \
        mlp_capture_leaf_lut1 [dict get $capture lut1] \
        mlp_capture_leaf_branch_instances \
            [dict get $capture branch_instances] \
        mlp_capture_leaf_branch_lut1 [dict get $capture branch_lut1] \
        mlp_capture_leaf_branch_slr_counts \
            [dict get $capture branch_slr_counts] \
        mlp_capture_leaf_wrong_slr [dict get $capture wrong] \
        status $status] {
        puts $fp "$key=$value"
    }
    close $fp
}

# This is the exact resource/floorplan identity of the fresh 5453-DSP cohort16
# row-local checkpoint. It intentionally does not accept P1 or frozen Run0138.
proc hap_require_fresh_p2_contract {plan pblock_audit metrics} {
    foreach {key expected} {
        contract_variant P2_COHORT16_COL2_12_2
        total_dsp 5453
        total_uram 752
        history2_count 2
        generic_repack_count 0
        branch0_dsp 1536
        branch2_dsp 1536
        kernel_count 2
        kernel_dsp 3072
        swiglu_frontend_count 1
        row_leaf_count 2
        unique_hadamard_count 1
        fold2_count 0
        quantizer_count 4
        silu_count 2
        leaf0_dsp 2
        leaf1_dsp 2
        leaf0_ramb36 6
        leaf1_ramb36 6
        outer0_dsp 1538
        outer2_dsp 1538
        outer0_ramb36 102
        outer2_ramb36 102
        projection_lane_count 128
        projection_lane_dsp 17
        projection_weight_capture_audited 1
        projection_weight_capture_ok 1
        raw_weight_push_loads 37
        weight_data_capture_nets 32
        weight_data_capture_min 256
        weight_data_capture_max 256
        weight_meta_capture_nets 2
        weight_meta_capture_min 256
        weight_meta_capture_max 256
        weight_group_capture_nets 2
        weight_group_capture_min 7
        weight_group_capture_max 7
        move0 16
        center_lanes 96
        move2 16
        planned_slr0_dsp 1862
        planned_slr1_dsp 1781
        planned_slr2_dsp 1810
        attention_meta_uram 80
        attention_island_target 0
        attention_island_dsp 52
        attention_island_ramb36 88
        attention_island_ramb18 2
        attention_island_uram 0
        attention_island_quantizer_overlap 0
        attention_island_row_cache_overlap 0
    } {
        hap_require_plan_value $plan $key $expected
    }

    foreach {key expected} {
        ok 1
        require_placed 1
        contract_variant P2_COHORT16_COL2_12_2
        pblock_count 11
        dsp_coverage 5453
        uram_coverage 752
        placed_wrong 0
    } {
        if {![dict exists $pblock_audit $key] ||
            [dict get $pblock_audit $key] ne $expected} {
            set actual [expr {[dict exists $pblock_audit $key] ?
                [dict get $pblock_audit $key] : "MISSING"}]
            error "Fresh P2_COHORT16_COL2_12_2 pblock audit mismatch: $key expected=$expected actual=$actual"
        }
    }
    foreach name {pb_v5_mlp_branch_slr0 pb_v5_mlp_branch_slr2} {
        foreach {key expected} {
            dsp 1538
            uram 0
            ramb36 102
            ramb18 0
            missing 0
            placed_wrong 0
        } {
            hap_require_pblock_record_value $pblock_audit $name $key $expected
        }
    }
    foreach {name target dsp} {
        pb_v5_attention_projection_left2_slr0 0 272
        pb_v5_attention_projection_center12_slr1 1 1781
        pb_v5_attention_projection_right2_slr2 2 272
    } {
        foreach {key expected} [list \
                target $target dsp $dsp uram 0 missing 0 placed_wrong 0] {
            hap_require_pblock_record_value $pblock_audit $name $key $expected
        }
    }
    foreach {key expected} {
        dsp 52
        uram 0
        ramb36 88
        ramb18 2
        missing 0
        placed_wrong 0
    } {
        hap_require_pblock_record_value $pblock_audit \
            pb_v5_attention_row_kv_cache_slr0 $key $expected
    }

    if {[dict get $metrics slr_dsp] ne {1862 1781 1810} ||
        [dict get $metrics slr_uram] ne {224 224 304} ||
        [dict get $metrics unplaced] != 0 ||
        [dict get $metrics wrong_total] != 0} {
        error "Fresh P2_COHORT16_COL2_12_2 physical distribution mismatch: DSP=[dict get $metrics slr_dsp] URAM=[dict get $metrics slr_uram] unplaced=[dict get $metrics unplaced] wrong=[dict get $metrics wrong_total]"
    }
}

proc hap_require_p3_attention_geometry {plan pblock_audit metrics} {
    if {[dict get $pblock_audit pblock_count] != 10 ||
        [llength [get_pblocks -quiet]] != 21 ||
        [llength [dict get $plan region0_input_primitives]] != 3136 ||
        [llength [dict get $plan region3_input_primitives]] != 2112 ||
        [llength [dict get $plan owner_region2_weight_primitives]] != 2048 ||
        ![hap_projection_ooc_floorplan::region0_input_localization_ok $plan] ||
        ![hap_projection_ooc_floorplan::region3_input_localization_ok $plan] ||
        ![hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok $plan] ||
        ![dict get $metrics ok]} {
        error "P3 Attention geometry contract failed"
    }
}

proc hap_route_compute_clock_buffer_none {} {
    set nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
    if {[llength $nets] == 0} {
        error "Route compute-net selector is empty"
    }
    foreach net $nets {
        if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
            error "Route compute net lost CLOCK_BUFFER_TYPE NONE: $net"
        }
    }
    return [llength $nets]
}

# Cross-check every common place-summary field against the live plan reopened
# from post_place.dcp.  The live DCP is authoritative; a self-consistent but
# stale summary therefore cannot authorize route.
proc hap_require_place_matches_live {place plan pblock_audit metrics clear metadata \
        capture geometry_plan geometry_audit geometry_metrics} {
    foreach {summary_key plan_key} {
        dsp48e2 total_dsp
        uram288 total_uram
        mlp_kernel_dsp48e2 kernel_dsp
        history2_repack_instances history2_count
        generic_repack_instances generic_repack_count
        attention_island_target_slr attention_island_target
        attention_island_dsp48e2 attention_island_dsp
        attention_island_ramb36e2 attention_island_ramb36
        attention_island_ramb18e2 attention_island_ramb18
        attention_island_uram288 attention_island_uram
        attention_island_quantizer_overlap attention_island_quantizer_overlap
        attention_island_row_cache_overlap attention_island_row_cache_overlap
        moved_lanes_slr0 move0
        center_lanes_slr1 center_lanes
        moved_lanes_slr2 move2
        planned_slr0_dsp48e2 planned_slr0_dsp
        planned_slr1_dsp48e2 planned_slr1_dsp
        planned_slr2_dsp48e2 planned_slr2_dsp
    } {
        hap_require_summary $place $summary_key [dict get $plan $plan_key]
    }
    hap_require_summary $place pblock_contract_variant \
        [dict get $pblock_audit contract_variant]
    hap_require_summary $place post_place_pblock_count \
        [llength [get_pblocks -quiet]]
    hap_require_summary $place post_place_canonical_pblock_count \
        [dict get $pblock_audit pblock_count]
    hap_require_summary $place post_place_geometry_pblock_count \
        [dict get $geometry_audit pblock_count]
    hap_require_summary $place canonical_pblock_count \
        [dict get $pblock_audit pblock_count]
    hap_require_summary $place geometry_pblock_count \
        [dict get $geometry_audit pblock_count]
    hap_require_summary $place geometry_region0_input_primitives \
        [llength [dict get $geometry_plan region0_input_primitives]]
    hap_require_summary $place geometry_region3_input_primitives \
        [llength [dict get $geometry_plan region3_input_primitives]]
    hap_require_summary $place geometry_owner_region2_weight_primitives \
        [llength [dict get $geometry_plan owner_region2_weight_primitives]]
    hap_require_summary $place geometry_region0_input_ok 1
    hap_require_summary $place geometry_region3_input_ok 1
    hap_require_summary $place geometry_owner_region2_weight_ok 1
    hap_require_summary $place geometry_placement_ok \
        [dict get $geometry_metrics ok]
    hap_require_summary $place post_place_pblock_dsp_coverage \
        [dict get $pblock_audit dsp_coverage]
    hap_require_summary $place post_place_pblock_uram_coverage \
        [dict get $pblock_audit uram_coverage]
    hap_require_summary $place post_place_pblock_wrong_slr \
        [dict get $pblock_audit placed_wrong]
    set island [dict get $pblock_audit records \
        pb_v5_attention_row_kv_cache_slr0]
    foreach {summary_key record_key} {
        attention_island_pblock_dsp48e2 dsp
        attention_island_pblock_ramb36e2 ramb36
        attention_island_pblock_ramb18e2 ramb18
        attention_island_pblock_uram288 uram
    } {
        hap_require_summary $place $summary_key [dict get $island $record_key]
    }
    for {set index 0} {$index < 3} {incr index} {
        hap_require_summary $place slr${index}_dsp48e2 \
            [lindex [dict get $metrics slr_dsp] $index]
        hap_require_summary $place slr${index}_uram288 \
            [lindex [dict get $metrics slr_uram] $index]
    }
    foreach {summary_key value} [list \
        mlp_local_clear_ff [dict get $clear total] \
        mlp_local_clear_protected_ff [dict get $clear protected] \
        branch0_local_clear_ff [dict get $clear branch0] \
        branch1_local_clear_ff [dict get $clear branch1] \
        branch0_local_clear_slr [dict get $clear branch0_slr] \
        branch1_local_clear_slr [dict get $clear branch1_slr] \
        mlp_local_clear_wrong_slr [dict get $clear wrong] \
        mlp_central_clear_ff [dict get $clear central] \
        mlp_central_clear_branch_endpoints \
            [dict get $clear central_branch_endpoints] \
        mlp_central_clear_direct_branch_state \
            [dict get $clear central_direct_branch_state] \
        metadata_leaf_instances [dict get $metadata leaves] \
        metadata_local_wr_en_ff [dict get $metadata wr_en] \
        metadata_local_wr_addr_ff [dict get $metadata wr_addr] \
        metadata_local_wr_data_ff [dict get $metadata wr_data] \
        metadata_local_write_protected_ff [dict get $metadata protected] \
        metadata_local_write_leaf_counts [dict get $metadata leaf_counts] \
        metadata_local_write_leaf_slr_counts \
            [dict get $metadata leaf_slr_counts] \
        metadata_local_write_wrong_slr [dict get $metadata wrong] \
        mlp_capture_leaf_instances [dict get $capture instances] \
        mlp_capture_leaf_lut1 [dict get $capture lut1] \
        mlp_capture_leaf_branch_instances \
            [dict get $capture branch_instances] \
        mlp_capture_leaf_branch_lut1 [dict get $capture branch_lut1] \
        mlp_capture_leaf_branch_slr_counts \
            [dict get $capture branch_slr_counts] \
        mlp_capture_leaf_wrong_slr [dict get $capture wrong]] {
        hap_require_summary $place $summary_key $value
    }
}

proc hap_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_verify_sha_manifest {path expected_count expected_manifest_sha} {
    if {[hap_sha256 $path] ne $expected_manifest_sha} {
        error "SHA256 manifest identity mismatch: $path"
    }
    set entries [dict create]
    set count 0
    foreach raw [split [hap_read_nonempty $path "SHA256 manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed SHA256 manifest row: $line"
        }
        set file_name [file normalize [string trim $file_name]]
        if {[dict exists $entries $file_name]} {
            error "Duplicate SHA256 manifest path: $file_name"
        }
        if {![file exists $file_name] || ![file isfile $file_name] ||
            [file size $file_name] == 0} {
            error "SHA256 manifest input is missing/empty: $file_name"
        }
        set actual [hap_sha256 $file_name]
        if {$actual ne $expected} {
            error "SHA256 mismatch: file=$file_name expected=$expected actual=$actual"
        }
        dict set entries $file_name $expected
        incr count
    }
    if {$expected_count >= 0 && $count != $expected_count} {
        error "SHA256 manifest cardinality mismatch: path=$path expected=$expected_count actual=$count"
    }
    return $entries
}

proc hap_require_complete_place_output_manifest {entries manifest_path} {
    set place_dir [file dirname $manifest_path]
    set expected [dict create]
    foreach path [glob -nocomplain -directory $place_dir *] {
        set normalized [file normalize $path]
        if {$normalized eq [file normalize $manifest_path] ||
            ![file isfile $normalized] || [file size $normalized] == 0} {
            continue
        }
        dict set expected $normalized 1
    }
    if {[lsort -dictionary [dict keys $entries]] ne
        [lsort -dictionary [dict keys $expected]]} {
        error "Place output SHA manifest is not the complete current nonempty file set"
    }
}

proc hap_require_manifest_path {manifest path label} {
    set normalized [file normalize $path]
    if {![dict exists $manifest $normalized]} {
        error "$label is absent from its frozen SHA256 manifest: $normalized"
    }
}

proc hap_require_exact_manifest_paths {manifest expected_paths label} {
    set expected [dict create]
    foreach path $expected_paths {
        set normalized [file normalize $path]
        if {[dict exists $expected $normalized]} {
            error "$label expected-path list contains a duplicate: $normalized"
        }
        dict set expected $normalized 1
    }
    set actual [lsort -dictionary [dict keys $manifest]]
    set wanted [lsort -dictionary [dict keys $expected]]
    if {$actual ne $wanted} {
        error "$label path set mismatch: expected=$wanted actual=$actual"
    }
}

proc hap_xdc_contract {path} {
    set text [hap_read_nonempty $path "production OOC clock XDC"]
    set code ""
    foreach line [split $text "\n"] {
        if {![regexp {^[[:space:]]*#} $line]} {append code $line "\n"}
    }
    set forbidden_false [join {set false path} _]
    set forbidden_datapath "-[join {datapath only} _]"
    if {[regexp -nocase -- [format {%s|%s} $forbidden_false \
            $forbidden_datapath] $code]} {
        error "Production OOC clock XDC contains a forbidden timing waiver"
    }
    foreach {label pattern expected} [list \
        create_clock {create_clock[[:space:]]} 3 \
        async_group {set_clock_groups[[:space:]]+-asynchronous} 1 \
        async_members {-group[[:space:]]+\[get_clocks} 3 \
        input_delay {set_input_delay[[:space:]]} 6 \
        output_delay {set_output_delay[[:space:]]} 6] {
        set actual [llength [regexp -all -inline -- $pattern $code]]
        if {$actual != $expected} {
            error "OOC XDC command mismatch: $label expected=$expected actual=$actual"
        }
    }
    foreach {command clock sense value} {
        set_input_delay core_clk max 1.000
        set_input_delay core_clk min 0.000
        set_output_delay core_clk max 1.000
        set_output_delay core_clk min 0.000
        set_input_delay ddr0_clk max 0.800
        set_input_delay ddr0_clk min 0.000
        set_output_delay ddr0_clk max 0.800
        set_output_delay ddr0_clk min 0.000
        set_input_delay ddr1_clk max 0.800
        set_input_delay ddr1_clk min 0.000
        set_output_delay ddr1_clk max 0.800
        set_output_delay ddr1_clk min 0.000
    } {
        set pattern [format \
            {%s[[:space:]]+-clock[[:space:]]+%s[[:space:]]+-%s[[:space:]]+%s} \
            $command $clock $sense $value]
        set actual [llength [regexp -all -inline -- $pattern $code]]
        if {$actual != 1} {
            error "OOC I/O budget mismatch: $command/$clock/$sense/$value count=$actual"
        }
    }
}

proc hap_clock_contract {} {
    foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
        set clocks [get_clocks -quiet $name]
        if {[llength $clocks] != 1} {
            error "Clock is not unique: $name -> $clocks"
        }
        set actual [get_property PERIOD $clocks]
        if {abs($actual - $period) > 0.001} {
            error "Clock period mismatch: $name expected=$period actual=$actual"
        }
    }
}

proc hap_first_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} {
        error "No $delay_type timing path was returned"
    }
    return [get_property SLACK [lindex $paths 0]]
}

proc hap_route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} \
                $line -> count]} {
            return $count
        }
    }
    if {$required} {error "Required route-status row is missing: $label"}
    return 0
}

proc hap_timing_count {text category} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $category]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "Timing coverage category is missing: $category"
    }
    return $count
}

proc hap_cdc_critical {path} {
    set text [hap_read_nonempty $path "post-route CDC report"]
    if {![regexp -line \
            {^[[:space:]]*ID[[:space:]]+Severity[[:space:]]+Count[[:space:]]+Description[[:space:]]*$} \
            $text]} {
        error "CDC report summary header is missing"
    }
    set count 0
    foreach {whole value} [regexp -all -inline -line -nocase \
            {^[^\n]*[[:space:]]Critical[[:space:]]+([1-9][0-9]*)[[:space:]]+[^\n]*$} \
            $text] {
        incr count $value
    }
    return $count
}

proc hap_drc_error_rows {path} {
    set text [hap_read_nonempty $path "post-route DRC report"]
    if {[string first "DRC Report" $text] < 0 &&
        [string first "Report DRC" $text] < 0} {
        error "Post-route DRC report header is missing"
    }
    set count 0
    foreach line [split $text "\n"] {
        if {[regexp -nocase \
                {^[[:space:]]*\|[^|]+\|[[:space:]]*Error[[:space:]]*\|} \
                $line] ||
            [regexp -nocase \
                {^[[:space:]]*[^#[:space:]]+#[0-9]+[[:space:]]+Error([[:space:]]|$)} \
                $line]} {
            incr count
        }
    }
    return $count
}

proc hap_global_long_level6 {path} {
    set text [hap_read_nonempty $path "post-route congestion report"]
    if {[string first "Placer Final Level Congestion Reporting" $text] < 0 ||
        [string first "Router Initial Congestion" $text] < 0} {
        error "Congestion report is missing its placer/router sections"
    }
    set canonical_header_count 0
    foreach line [split $text "\n"] {
        if {[regexp {^[[:space:]]*\|[[:space:]]*Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level[[:space:]]*\|[[:space:]]*Window[[:space:]]*\|} \
                $line]} {
            incr canonical_header_count
        }
    }
    if {$canonical_header_count < 1} {
        error "Congestion report canonical Direction/Type/Level/Window schema is missing"
    }
    set count 0
    set congestion_rows 0
    foreach line [split $text "\n"] {
        if {[regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
                $line -> direction type level]} {
            incr congestion_rows
            if {$level >= 6} {incr count}
        }
    }
    if {$congestion_rows == 0 &&
        [string first "No congestion windows are found above level 5" \
            $text] < 0 &&
        [string first \
            "No effective congestion windows are found above level 5" \
            $text] < 0} {
        error "Congestion report has neither Global/Long rows nor a clean marker"
    }
    return $count
}

proc hap_bufg_counts {} {
    set clock 0
    set data 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
            incr clock
        } else {
            incr data
        }
    }
    return [list $clock $data]
}

proc hap_safe_report {out label command} {
    if {[catch {uplevel 1 $command} message options]} {
        set clean [string map [list "\n" " | " "\r" " "] $message]
        hap_write_text [file join $out ${label}.error.txt] \
            "report=$label\nmessage=$clean\n"
        return 0
    }
    return 1
}

proc hap_utilization_totals {path} {
    set text [hap_read_nonempty $path "post-route utilization report"]
    if {[string first "Utilization Design Information" $text] < 0 &&
        [string first "Utilization Report" $text] < 0} {
        error "Post-route utilization report header is missing"
    }
    set result [dict create]
    set seen_section [dict create clb_lut 0 clb_register 0 \
        bram_tile 0 uram 0 dsp 0]
    foreach line [split $text "\n"] {
        set fields [split $line |]
        if {[llength $fields] < 3} {continue}
        set label [string trim [lindex $fields 1]]
        set used [string map {, {}} [string trim [lindex $fields 2]]]
        if {![string is integer -strict $used]} {continue}
        switch -- $label {
            "CLB LUTs" {set key clb_lut}
            "CLB Registers" {set key clb_register}
            "Block RAM Tile" {set key bram_tile}
            "URAM" {set key uram}
            "DSPs" {set key dsp}
            default {continue}
        }
        if {![dict get $seen_section $key]} {
            dict set result $key $used
            dict set seen_section $key 1
        }
    }
    foreach key {clb_lut clb_register bram_tile uram dsp} {
        if {![dict exists $result $key]} {
            error "Post-route utilization row is missing: $key"
        }
    }
    return $result
}

if {$hap_route_source_procs_only} {return}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 route requires a fresh Vivado process with no open design"
}
foreach {label value} [list pre_route_physopt $pre_physopt_directive \
        route $route_directive post_route_physopt $post_physopt_directive] {
    if {![regexp {^[A-Za-z][A-Za-z0-9_]*$} $value]} {
        error "Illegal $label directive: $value"
    }
}
foreach {label path} [list post_place_dcp $in_dcp \
        place_summary $place_summary place_input_sha $place_input_sha \
        place_output_sha $place_output_sha \
        place_launcher_status $place_launcher_status \
        selector_library $selector_lib geometry_library $geometry_lib \
        io_selector_audit $io_audit clock_xdc $clock_xdc] {
    hap_read_nonempty $path $label
}
foreach {label digest} [list place_input_manifest \
        $expected_place_input_manifest_sha place_output_manifest \
        $expected_place_output_manifest_sha route_input_manifest \
        $expected_route_input_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed expected $label SHA256: $digest"
    }
}

# Verify both frozen placement manifests inside Vivado as well as in the
# launcher.  The output manifest is authoritative for this exact post_place
# DCP; the seven-entry input manifest also freezes the independent pre-place
# output manifest used to authorize this placement.
set frozen_inputs [hap_verify_sha_manifest $place_input_sha 8 \
    $expected_place_input_manifest_sha]
set frozen_outputs [hap_verify_sha_manifest $place_output_sha -1 \
    $expected_place_output_manifest_sha]
set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 13 \
    $expected_route_input_manifest_sha]
hap_require_complete_place_output_manifest $frozen_outputs $place_output_sha
hap_require_manifest_path $frozen_outputs $place_launcher_status \
    place_launcher_status
foreach required [list $in_dcp $place_summary $place_input_sha \
        $place_output_sha $selector_lib $io_audit $clock_xdc \
        [file normalize [info script]]] {
    hap_require_manifest_path $frozen_route_inputs $required route_input
}
hap_require_exact_manifest_paths $frozen_route_inputs [list \
    $in_dcp $place_summary $place_input_sha $place_output_sha \
    $place_input_files $place_launcher_status $place_selectors \
    $place_pblocks $selector_lib $io_audit $clock_xdc \
    [file normalize [info script]] \
    [file normalize [file join $script_dir \
        run_attention_mlp_production_v5_route.sh]]] route_input
hap_require_manifest_path $frozen_inputs $selector_lib selector_library
hap_require_manifest_path $frozen_inputs $geometry_lib geometry_library
hap_require_manifest_path $frozen_inputs $clock_xdc clock_xdc
hap_require_manifest_path $frozen_outputs $in_dcp post_place_dcp
hap_require_manifest_path $frozen_outputs $place_summary place_summary

set place_launcher [hap_parse_summary $place_launcher_status \
    "place launcher status"]
foreach {key value} {
    status PASS
    flow_mode accept
    acceptance_evidence 1
    route_eligible 1
    final_exit_code 0
    vivado_exit_code 0
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    place_gate_exit_code 0
    checkpoint_written 1
    vivado_invoked 1
    implementation_commands_requested 1
    bitstream_generated 0
} {
    hap_require_summary $place_launcher $key $value
}

set place [hap_parse_summary $place_summary]
foreach {key value} {
    status V5_PRODUCTION_PLACE_PASS
    flow_mode accept
    acceptance_evidence 1
    route_eligible 1
    checkpoint_written 1
    input_manifest_entries 8
    pre_place_verified 1
    part xcvu9p-flga2104-2L-e
    top hap_attention_mlp_production_core
    core_clock_mhz 100
    ddr0_clock_mhz 300
    ddr1_clock_mhz 300
    mlp_kernel_dsp48e2 3072
    uram288 752
    history2_repack_instances 2
    generic_repack_instances 0
    raw_weight_push_loads 37
    weight_data_capture_contract 32x256
    weight_data_capture_nets 32
    weight_data_capture_loads 256/256
    weight_meta_capture_contract 2x256
    weight_meta_capture_nets 2
    weight_meta_capture_loads 256/256
    weight_group_capture_contract 2x7
    weight_group_capture_nets 2
    weight_group_capture_loads 7/7
    projection_weight_capture_ok 1
    slr0_uram288 224
    slr1_uram288 224
    slr2_uram288 304
    unplaced_primitives 0
    wrong_slr_primitives 0
    pre_place_pblock_contract_ok 1
    post_place_live_rediscovery_ok 1
    post_place_pblock_contract_ok 1
    pblock_contract_variant P2_COHORT16_COL2_12_2
    attention_row_instances 1
    kv_cache_instances 1
    kv_quantizer4_instances 1
    attention_island_target_slr 0
    attention_island_dsp48e2 52
    attention_island_ramb36e2 88
    attention_island_ramb18e2 2
    attention_island_uram288 0
    attention_island_quantizer_overlap 0
    attention_island_row_cache_overlap 0
    attention_island_pblock_dsp48e2 52
    attention_island_pblock_ramb36e2 88
    attention_island_pblock_ramb18e2 2
    attention_island_pblock_uram288 0
    dsp48e2 5453
    moved_lanes_slr0 16
    center_lanes_slr1 96
    moved_lanes_slr2 16
    planned_slr0_dsp48e2 1862
    planned_slr1_dsp48e2 1781
    planned_slr2_dsp48e2 1810
    slr0_dsp48e2 1862
    slr1_dsp48e2 1781
    slr2_dsp48e2 1810
    compute_clock_buffer_none_ok 1
    geometry_pblock_prefix p3_
    canonical_pblock_count 11
    geometry_pblock_count 10
    geometry_region0_input_primitives 3136
    geometry_region3_input_primitives 2112
    geometry_owner_region2_weight_primitives 2048
    geometry_region0_input_ok 1
    geometry_region3_input_ok 1
    geometry_owner_region2_weight_ok 1
    geometry_placement_ok 1
    post_place_pblock_count 21
    post_place_canonical_pblock_count 11
    post_place_geometry_pblock_count 10
    post_place_pblock_dsp_coverage 5453
    post_place_pblock_uram_coverage 752
    post_place_pblock_wrong_slr 0
    mlp_local_clear_ff 2
    mlp_local_clear_protected_ff 2
    branch0_local_clear_ff 1
    branch1_local_clear_ff 1
    branch0_local_clear_slr {1 0 0}
    branch1_local_clear_slr {0 0 1}
    mlp_local_clear_wrong_slr 0
    mlp_central_clear_ff 1
    mlp_central_clear_branch_endpoints 2
    mlp_central_clear_direct_branch_state 0
    metadata_leaf_instances 4
    metadata_local_wr_en_ff 4
    metadata_local_wr_addr_ff 70
    metadata_local_wr_data_ff 896
    metadata_local_write_protected_ff 970
    metadata_local_write_leaf_counts {243 243 242 242}
    metadata_local_write_leaf_slr_counts {{243 0 0} {0 0 243} {0 242 0} {0 242 0}}
    metadata_local_write_wrong_slr 0
    mlp_capture_leaf_instances 1632
    mlp_capture_leaf_lut1 1632
    mlp_capture_leaf_branch_instances {816 816}
    mlp_capture_leaf_branch_lut1 {816 816}
    mlp_capture_leaf_branch_slr_counts {{816 0 0} {0 0 816}}
    mlp_capture_leaf_wrong_slr 0
    pre_place_drc_errors 0
    post_place_drc_errors 0
    false_path_exception_rows 0
    datapath_only_exception_rows 0
    no_clock_endpoints 0
    unconstrained_paths 0
    no_input_delay_ports 3
    no_output_delay_ports 0
    partial_input_delay_ports 0
    partial_output_delay_ports 0
    timing_coverage_ok 1
    cdc_critical 0
    data_bufg 0
    fast_gate_ok 1
    congestion_level6_or_higher_windows 0
    resource_ok 1
    placement_ok 1
    uram_distribution_ok 1
    policy_ok 1
    level6_congestion_ok 1
} {
    hap_require_summary $place $key $value
}
hap_xdc_contract $clock_xdc

source $selector_lib
source $geometry_lib
open_checkpoint $in_dcp
set actual_part [get_property PART [current_design]]
set actual_top [get_property TOP [current_design]]
if {$actual_part ne $expected_part || $actual_top ne $expected_top} {
    hap_write_failure $out input_identity \
        "expected=$expected_part/$expected_top actual=$actual_part/$actual_top"
    error "Illegal V5 route input identity"
}
hap_clock_contract
source $io_audit
set input_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set input_projection_root [file dirname \
    [get_property NAME [dict get $input_plan projection_array]]]
set input_geometry_plan \
    [hap_projection_ooc_floorplan::discover $input_projection_root 1]
set input_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $input_geometry_plan 0 $geometry_prefix 1]
set input_geometry_metrics \
    [hap_projection_ooc_floorplan::audit_placement $input_geometry_plan]
set input_compute_clock_buffer_none_count \
    [hap_route_compute_clock_buffer_none]
set input_pblock_audit \
    [hap_v5_floorplan::audit_pblock_contract \
        $input_plan 1 P2_COHORT16_COL2_12_2 \
        [hap_projection_ooc_floorplan::specs \
            $input_geometry_plan p3_]]
hap_v5_floorplan::write_discovery $input_plan \
    [file join $out selectors_input.txt] V5_ROUTE_INPUT_SELECTORS_PASS
hap_v5_floorplan::write_pblock_audit $input_pblock_audit \
    [file join $out pblocks_input.txt] V5_ROUTE_INPUT_PBLOCKS_PASS
set input_metrics [hap_v5_floorplan::physical_metrics \
    $input_plan $input_pblock_audit]
set input_local_clear [hap_route_mlp_local_clear_audit 1]
set input_metadata [hap_route_metadata_local_write_audit 1]
set input_capture [hap_route_mlp_capture_leaf_audit 1]
hap_route_require_boundary_contract $input_local_clear $input_metadata \
    $input_capture input_post_place
hap_route_write_boundary_audit \
    [file join $out architecture_boundaries_input.txt] \
    $input_local_clear $input_metadata $input_capture \
    V5_ROUTE_INPUT_ARCHITECTURE_BOUNDARIES_PASS
hap_require_fresh_p2_contract $input_plan $input_pblock_audit $input_metrics
hap_require_p3_attention_geometry $input_geometry_plan \
    $input_geometry_audit $input_geometry_metrics
hap_require_place_matches_live \
    $place $input_plan $input_pblock_audit $input_metrics \
    $input_local_clear $input_metadata $input_capture \
    $input_geometry_plan $input_geometry_audit $input_geometry_metrics
if {![hap_v5_floorplan::physical_ok $input_plan $input_metrics] ||
    ![dict get $input_pblock_audit ok] ||
    [dict get $input_pblock_audit placed_wrong] != 0} {
    hap_write_failure $out input_physical_contract \
        "metrics=$input_metrics"
    error "V5 post-place input violates its physical contract"
}

set operation_ok 1
set operation_stage pre_route_phys_opt
set operation_message ""
if {[catch {phys_opt_design -directive $pre_physopt_directive} \
        operation_message operation_options]} {
    set operation_ok 0
}
set post_phys_opt_written 0
if {[catch {write_checkpoint -force \
        [file join $out post_phys_opt.dcp]} checkpoint_message]} {
    if {$operation_ok} {
        set operation_ok 0
        set operation_stage write_post_phys_opt
        set operation_message $checkpoint_message
    } else {
        append operation_message \
            " | post_phys_opt checkpoint: $checkpoint_message"
    }
} else {
    set post_phys_opt_written 1
}
if {$operation_ok} {
    if {![hap_safe_report $out timing_post_phys_opt [list \
        report_timing_summary -delay_type min_max -max_paths 100 \
        -report_unconstrained -file \
        [file join $out timing_post_phys_opt.rpt]]]} {
        set operation_ok 0
        set operation_stage report_timing_post_phys_opt
        set operation_message "post-phys-opt timing report failed"
    } else {
        set operation_stage route_design
        if {[catch {route_design -directive $route_directive} \
                operation_message operation_options]} {
            set operation_ok 0
        }
    }
}

# Post-route optimization is automatic only when measured setup/hold slack is
# negative.  It does not alter clock constraints.  Each change is followed by
# a preserve reroute, and the final clean-route/timing gates remain absolute.
set post_setup_physopt_applied 0
set post_hold_physopt_applied 0
if {$operation_ok} {
    if {[catch {set preliminary_wns [hap_first_slack max]
            set preliminary_whs [hap_first_slack min]} \
            operation_message operation_options]} {
        set operation_ok 0
        set operation_stage preliminary_timing_query
    }
}
if {$operation_ok && $preliminary_wns < 0.0} {
    set post_setup_physopt_applied 1
    set operation_stage post_route_setup_phys_opt
    if {[catch {phys_opt_design -directive $post_physopt_directive
            route_design -preserve} operation_message operation_options]} {
        set operation_ok 0
    }
}
if {$operation_ok} {
    if {[catch {set after_setup_whs [hap_first_slack min]} \
            operation_message operation_options]} {
        set operation_ok 0
        set operation_stage post_setup_timing_query
    }
}
if {$operation_ok && $after_setup_whs < 0.0} {
    set post_hold_physopt_applied 1
    set operation_stage post_route_hold_phys_opt
    if {[catch {phys_opt_design -hold_fix
            route_design -preserve} operation_message operation_options]} {
        set operation_ok 0
    }
}

# Preserve the best available design state even when route/phys_opt failed.
if {[catch {write_checkpoint -force [file join $out post_route.dcp]} \
        checkpoint_message]} {
    set operation_ok 0
    append operation_message " | post_route checkpoint: $checkpoint_message"
    set operation_stage write_post_route
}

set report_ok 1
foreach {label command} [list \
    utilization_post_route [list report_utilization -file \
        [file join $out utilization_post_route.rpt]] \
    utilization_hier_post_route [list report_utilization -hierarchical \
        -hierarchical_depth 12 -file \
        [file join $out utilization_hier_post_route.rpt]] \
    utilization_slr_post_route [list report_utilization -slr -file \
        [file join $out utilization_slr_post_route.rpt]] \
    timing_setup_worst100_post_route [list report_timing -delay_type max \
        -max_paths 100 -path_type full_clock_expanded -file \
        [file join $out timing_setup_worst100_post_route.rpt]] \
    timing_hold_worst100_post_route [list report_timing -delay_type min \
        -max_paths 100 -path_type full_clock_expanded -file \
        [file join $out timing_hold_worst100_post_route.rpt]] \
    drc_post_route [list report_drc -file \
        [file join $out drc_post_route.rpt]] \
    cdc_post_route [list report_cdc -details -file \
        [file join $out cdc_post_route.rpt]] \
    clock_interaction_post_route [list report_clock_interaction \
        -delay_type min_max -file \
        [file join $out clock_interaction_post_route.rpt]] \
    clock_utilization_post_route [list report_clock_utilization -file \
        [file join $out clock_utilization_post_route.rpt]] \
    congestion_post_route [list report_design_analysis -congestion -file \
        [file join $out congestion_post_route.rpt]] \
    exceptions_coverage_post_route [list report_exceptions -coverage -file \
        [file join $out exceptions_coverage_post_route.rpt]]] {
    if {![hap_safe_report $out $label $command]} {set report_ok 0}
}

set timing_text ""
if {[catch {set timing_text [report_timing_summary -delay_type min_max \
        -max_paths 100 -report_unconstrained -warn_on_violation \
        -return_string]} timing_message]} {
    set report_ok 0
    hap_write_text [file join $out timing_post_route.error.txt] \
        "message=$timing_message\n"
} else {
    hap_write_text [file join $out timing_post_route.rpt] $timing_text
}
set route_text ""
if {[catch {set route_text [report_route_status -return_string]} \
        route_report_message]} {
    set report_ok 0
    hap_write_text [file join $out route_status_post_route.error.txt] \
        "message=$route_report_message\n"
} else {
    hap_write_text [file join $out route_status_post_route.rpt] $route_text
}

set audit_ok 1
set audit_message ""
if {[catch {
    # Route/phys_opt commands can replace physical cell objects.  Rebuild the
    # hierarchy-root descendants from the live routed design before auditing
    # SLR placement; never reuse input_plan collections here.
    set final_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
    set final_projection_root [file dirname \
        [get_property NAME [dict get $final_plan projection_array]]]
    set final_geometry_plan \
        [hap_projection_ooc_floorplan::discover $final_projection_root 1]
    set final_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
        $final_geometry_plan 0 $geometry_prefix 1]
    set final_geometry_metrics \
        [hap_projection_ooc_floorplan::audit_placement $final_geometry_plan]
    set final_compute_clock_buffer_none_count \
        [hap_route_compute_clock_buffer_none]
    set final_pblock_audit \
        [hap_v5_floorplan::audit_pblock_contract \
            $final_plan 1 P2_COHORT16_COL2_12_2 \
            [hap_projection_ooc_floorplan::specs \
                $final_geometry_plan p3_]]
    hap_v5_floorplan::write_discovery $final_plan \
        [file join $out selectors_post_route.txt] \
        V5_ROUTE_FINAL_SELECTORS_PASS
    hap_v5_floorplan::write_pblock_audit $final_pblock_audit \
        [file join $out pblocks_post_route.txt] \
        V5_ROUTE_FINAL_PBLOCKS_PASS
    set final_metrics [hap_v5_floorplan::physical_metrics \
        $final_plan $final_pblock_audit]
    set final_local_clear [hap_route_mlp_local_clear_audit 1]
    set final_metadata [hap_route_metadata_local_write_audit 1]
    set final_capture [hap_route_mlp_capture_leaf_audit 1]
    hap_route_require_boundary_contract $final_local_clear $final_metadata \
        $final_capture final_post_route
    hap_route_write_boundary_audit \
        [file join $out architecture_boundaries_post_route.txt] \
        $final_local_clear $final_metadata $final_capture \
        V5_ROUTE_FINAL_ARCHITECTURE_BOUNDARIES_PASS
    hap_require_fresh_p2_contract \
        $final_plan $final_pblock_audit $final_metrics
    hap_require_p3_attention_geometry $final_geometry_plan \
        $final_geometry_audit $final_geometry_metrics
    set attention_island_record [dict get $final_pblock_audit records \
        pb_v5_attention_row_kv_cache_slr0]
    set utilization [hap_utilization_totals \
        [file join $out utilization_post_route.rpt]]
    set clb_lut [dict get $utilization clb_lut]
    set clb_register [dict get $utilization clb_register]
    set bram_tile [dict get $utilization bram_tile]
    set physical_ok [expr {
        [hap_v5_floorplan::physical_ok $final_plan $final_metrics] &&
        [dict get $final_pblock_audit ok] &&
        [dict get $final_pblock_audit placed_wrong] == 0 &&
        [dict get $final_geometry_metrics ok]}]
    set architecture_boundary_ok 1
    set resource_ok [expr {[dict get $final_plan total_dsp] == 5453 &&
        [dict get $final_plan total_uram] == 752 &&
        [dict get $utilization dsp] == [dict get $final_plan total_dsp] &&
        [dict get $utilization uram] == [dict get $final_plan total_uram] &&
        [dict get $final_plan kernel_dsp] == 3072 &&
        [dict get $final_plan history2_count] == 2 &&
        [dict get $final_plan generic_repack_count] == 0 &&
        [dict get $final_plan projection_weight_capture_ok] == 1}]
    hap_clock_contract
    set wns [hap_first_slack max]
    set whs [hap_first_slack min]

    set route_errors [hap_route_row $route_text \
        "# of nets with routing errors" 1]
    set explicit_gaps [hap_route_row $route_text \
        "# of nets with explicit gaps"]
    set unrouted_rows [hap_route_row $route_text "# of unrouted nets"]
    set unrouted_pins [hap_route_row $route_text \
        "# of nets with some unrouted pins"]
    set resource_conflicts [hap_route_row $route_text \
        "# of nets with resource conflicts"]
    set antennas [hap_route_row $route_text \
        "# of nets with antennas/islands"]
    set partial_nets [llength [get_nets -quiet -hierarchical -filter {
        ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
        ROUTE_STATUS == UNROUTED || ROUTE_STATUS == HIERPORT
    }]]
    set conflict_nets [llength [get_nets -quiet -hierarchical -filter \
        {ROUTE_STATUS == CONFLICTS}]]
    set route_clean [expr {$route_errors == 0 && $explicit_gaps == 0 &&
        $unrouted_rows == 0 && $unrouted_pins == 0 &&
        $resource_conflicts == 0 && $antennas == 0 &&
        $partial_nets == 0 && $conflict_nets == 0}]

    set no_clock [hap_timing_count $timing_text no_clock]
    set unconstrained [hap_timing_count $timing_text \
        unconstrained_internal_endpoints]
    set no_input_delay [hap_timing_count $timing_text no_input_delay]
    set no_output_delay [hap_timing_count $timing_text no_output_delay]
    set partial_input_delay [hap_timing_count $timing_text \
        partial_input_delay]
    set partial_output_delay [hap_timing_count $timing_text \
        partial_output_delay]
    set timing_coverage_ok [expr {$no_clock == 0 &&
        $unconstrained == 0 && $no_input_delay == 3 &&
        $no_output_delay == 0 && $partial_input_delay == 0 &&
        $partial_output_delay == 0}]

    set drc_errors [llength [get_drc_violations -quiet -filter \
        {SEVERITY == Error}]]
    set drc_report_error_rows [hap_drc_error_rows \
        [file join $out drc_post_route.rpt]]
    set cdc_critical [hap_cdc_critical \
        [file join $out cdc_post_route.rpt]]
    set congestion_level6 [hap_global_long_level6 \
        [file join $out congestion_post_route.rpt]]
    lassign [hap_bufg_counts] clock_bufg data_bufg
    set exceptions_text [hap_read_nonempty \
        [file join $out exceptions_coverage_post_route.rpt] \
        "post-route exception coverage report"]
    if {[string first "Exceptions Report" $exceptions_text] < 0} {
        error "Post-route exception report header is missing"
    }
    set false_path_rows [regexp -all -line \
        {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} \
        $exceptions_text]
    set datapath_only_rows [regexp -all -line \
        {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} \
        $exceptions_text]
    set policy_ok [expr {$drc_errors == 0 && $drc_report_error_rows == 0 &&
        $cdc_critical == 0 &&
        $data_bufg == 0 && $false_path_rows == 0 &&
        $datapath_only_rows == 0 && $timing_coverage_ok &&
        $congestion_level6 == 0}]

    # Rebind all three manifest identities and contents inside the same
    # Vivado process immediately before a PASS summary can be emitted.  The
    # launcher independently repeats these checks after Vivado exits.
    set frozen_inputs_post [hap_verify_sha_manifest $place_input_sha 7 \
        $expected_place_input_manifest_sha]
    set frozen_outputs_post [hap_verify_sha_manifest $place_output_sha -1 \
        $expected_place_output_manifest_sha]
    set frozen_route_inputs_post [hap_verify_sha_manifest $route_input_sha 13 \
        $expected_route_input_manifest_sha]
    hap_require_complete_place_output_manifest \
        $frozen_outputs_post $place_output_sha
    hap_require_exact_manifest_paths $frozen_route_inputs_post [list \
        $in_dcp $place_summary $place_input_sha $place_output_sha \
        $place_input_files $place_launcher_status $place_selectors \
        $place_pblocks $selector_lib $io_audit $clock_xdc \
        [file normalize [info script]] \
        [file normalize [file join $script_dir \
            run_attention_mlp_production_v5_route.sh]]] route_input_post
    if {$frozen_inputs_post ne $frozen_inputs ||
        $frozen_outputs_post ne $frozen_outputs ||
        $frozen_route_inputs_post ne $frozen_route_inputs} {
        error "Frozen V5 route input set changed within the Vivado process"
    }
} audit_message audit_options]} {
    set audit_ok 0
}

if {!$audit_ok} {
    hap_write_failure $out final_audit $audit_message
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list tool [version -short] part $actual_part \
            top $actual_top input_dcp $in_dcp operation_ok $operation_ok \
            report_ok $report_ok audit_ok 0 audit_error \
            [string map [list "\n" " | " "\r" " "] $audit_message] \
            status V5_PRODUCTION_OOC_ROUTE_FAIL] {
        puts $fp "$key=$value"
    }
    close $fp
    close_design
    error "V5 production OOC route final audit failed: $audit_message"
}

set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set status [expr {$operation_ok && $report_ok && $resource_ok &&
    $physical_ok && $architecture_boundary_ok && $timing_ok &&
    $route_clean && $policy_ok ?
    "V5_PRODUCTION_OOC_POST_ROUTE_PASS" :
    "V5_PRODUCTION_OOC_ROUTE_FAIL"}]
set slr_dsp [dict get $final_metrics slr_dsp]
set slr_uram [dict get $final_metrics slr_uram]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $actual_part top $actual_top \
    evidence_class PRODUCTION_CORE_OOC_POST_ROUTE jobs $jobs \
    input_dcp $in_dcp input_place_summary $place_summary \
    input_place_sha256 [lindex [exec sha256sum $in_dcp] 0] \
    pre_route_physopt_directive $pre_physopt_directive \
    route_directive $route_directive \
    post_route_physopt_directive $post_physopt_directive \
    post_phys_opt_checkpoint_written $post_phys_opt_written \
    post_setup_physopt_applied $post_setup_physopt_applied \
    post_hold_physopt_applied $post_hold_physopt_applied \
    core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    core_period_ns 10.000 ddr0_period_ns 3.333 ddr1_period_ns 3.333 \
    core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
    input_sha_manifests_verified 1 place_input_manifest_entries 8 \
    place_input_manifest_sha256 $expected_place_input_manifest_sha \
    place_output_manifest_entries [dict size $frozen_outputs] \
    place_output_manifest_sha256 $expected_place_output_manifest_sha \
    route_input_manifest_entries 13 \
    route_input_manifest_sha256 $expected_route_input_manifest_sha \
    v5_serial_instances 1 old_serial_instances 0 \
    v5_shared_instances 1 v5_branch_instances 2 \
    v5_kernel12_instances 2 v4_kernel16_instances 0 \
    history2_repack_instances [dict get $final_plan history2_count] \
    generic_repack_instances [dict get $final_plan generic_repack_count] \
    raw_weight_push_loads [dict get $final_plan raw_weight_push_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_nets [dict get $final_plan weight_data_capture_nets] \
    weight_data_capture_loads \
        [dict get $final_plan weight_data_capture_min]/[dict get $final_plan weight_data_capture_max] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_nets [dict get $final_plan weight_meta_capture_nets] \
    weight_meta_capture_loads \
        [dict get $final_plan weight_meta_capture_min]/[dict get $final_plan weight_meta_capture_max] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_nets [dict get $final_plan weight_group_capture_nets] \
    weight_group_capture_loads \
        [dict get $final_plan weight_group_capture_min]/[dict get $final_plan weight_group_capture_max] \
    projection_weight_capture_ok \
        [dict get $final_plan projection_weight_capture_ok] \
    pblock_contract_variant \
        [dict get $final_pblock_audit contract_variant] \
    attention_row_instances 1 kv_cache_instances 1 \
    kv_quantizer4_instances 1 \
    attention_island_target_slr \
        [dict get $final_plan attention_island_target] \
    attention_island_dsp48e2 \
        [dict get $final_plan attention_island_dsp] \
    attention_island_ramb36e2 \
        [dict get $final_plan attention_island_ramb36] \
    attention_island_ramb18e2 \
        [dict get $final_plan attention_island_ramb18] \
    attention_island_uram288 \
        [dict get $final_plan attention_island_uram] \
    attention_island_quantizer_overlap \
        [dict get $final_plan attention_island_quantizer_overlap] \
    attention_island_row_cache_overlap \
        [dict get $final_plan attention_island_row_cache_overlap] \
    attention_island_pblock_dsp48e2 \
        [dict get $attention_island_record dsp] \
    attention_island_pblock_ramb36e2 \
        [dict get $attention_island_record ramb36] \
    attention_island_pblock_ramb18e2 \
        [dict get $attention_island_record ramb18] \
    attention_island_pblock_uram288 \
        [dict get $attention_island_record uram] \
    mlp_kernel_dsp48e2 [dict get $final_plan kernel_dsp] \
    branch0_dsp48e2 [dict get $final_plan branch0_dsp] \
    branch2_dsp48e2 [dict get $final_plan branch2_dsp] \
    row_leaf0_dsp48e2 [dict get $final_plan leaf0_dsp] \
    row_leaf1_dsp48e2 [dict get $final_plan leaf1_dsp] \
    row_leaf0_ramb36e2 [dict get $final_plan leaf0_ramb36] \
    row_leaf1_ramb36e2 [dict get $final_plan leaf1_ramb36] \
    outer0_dsp48e2 [dict get $final_plan outer0_dsp] \
    outer2_dsp48e2 [dict get $final_plan outer2_dsp] \
    outer0_ramb36e2 [dict get $final_plan outer0_ramb36] \
    outer2_ramb36e2 [dict get $final_plan outer2_ramb36] \
    mlp_local_clear_ff [dict get $final_local_clear total] \
    mlp_local_clear_protected_ff [dict get $final_local_clear protected] \
    branch0_local_clear_ff [dict get $final_local_clear branch0] \
    branch1_local_clear_ff [dict get $final_local_clear branch1] \
    branch0_local_clear_slr [dict get $final_local_clear branch0_slr] \
    branch1_local_clear_slr [dict get $final_local_clear branch1_slr] \
    mlp_local_clear_wrong_slr [dict get $final_local_clear wrong] \
    mlp_central_clear_ff [dict get $final_local_clear central] \
    mlp_central_clear_branch_endpoints \
        [dict get $final_local_clear central_branch_endpoints] \
    mlp_central_clear_direct_branch_state \
        [dict get $final_local_clear central_direct_branch_state] \
    metadata_leaf_instances [dict get $final_metadata leaves] \
    metadata_local_wr_en_ff [dict get $final_metadata wr_en] \
    metadata_local_wr_addr_ff [dict get $final_metadata wr_addr] \
    metadata_local_wr_data_ff [dict get $final_metadata wr_data] \
    metadata_local_write_protected_ff [dict get $final_metadata protected] \
    metadata_local_write_leaf_counts [dict get $final_metadata leaf_counts] \
    metadata_local_write_leaf_slr_counts \
        [dict get $final_metadata leaf_slr_counts] \
    metadata_local_write_wrong_slr [dict get $final_metadata wrong] \
    mlp_capture_leaf_instances [dict get $final_capture instances] \
    mlp_capture_leaf_lut1 [dict get $final_capture lut1] \
    mlp_capture_leaf_branch_instances \
        [dict get $final_capture branch_instances] \
    mlp_capture_leaf_branch_lut1 [dict get $final_capture branch_lut1] \
    mlp_capture_leaf_branch_slr_counts \
        [dict get $final_capture branch_slr_counts] \
    mlp_capture_leaf_wrong_slr [dict get $final_capture wrong] \
    moved_lanes_slr0 [dict get $final_plan move0] \
    center_lanes_slr1 [dict get $final_plan center_lanes] \
    moved_lanes_slr2 [dict get $final_plan move2] \
    planned_slr0_dsp48e2 [dict get $final_plan planned_slr0_dsp] \
    planned_slr1_dsp48e2 [dict get $final_plan planned_slr1_dsp] \
    planned_slr2_dsp48e2 [dict get $final_plan planned_slr2_dsp] \
    dsp48e2 [dict get $final_plan total_dsp] dsp_limit 5500 \
    uram288 [dict get $final_plan total_uram] \
    clb_lut $clb_lut clb_register $clb_register bram_tile $bram_tile \
    slr0_dsp48e2 [lindex $slr_dsp 0] \
    slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] per_slr_dsp_limit 1900 \
    slr0_uram288 [lindex $slr_uram 0] \
    slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    unplaced_primitives [dict get $final_metrics unplaced] \
    wrong_slr_primitives [dict get $final_metrics wrong_total] \
    branch0_wrong_slr [dict get $final_metrics branch0_wrong] \
    branch2_wrong_slr [dict get $final_metrics branch2_wrong] \
    attention_lane0_wrong_slr [dict get $final_metrics lane0_wrong] \
    attention_lane2_wrong_slr [dict get $final_metrics lane2_wrong] \
    center_dsp_wrong_slr [dict get $final_metrics center_wrong] \
    metadata_gate0_wrong_slr [dict get $final_metrics gate0_wrong] \
    metadata_gate2_wrong_slr [dict get $final_metrics gate2_wrong] \
    metadata_down0_wrong_slr [dict get $final_metrics down0_wrong] \
    metadata_down1_wrong_slr [dict get $final_metrics down1_wrong] \
    attention_metadata_wrong_slr \
        [dict get $final_metrics attention_meta_wrong] \
    attention_island_wrong_slr \
        [dict get $final_metrics attention_island_wrong] \
    live_post_route_rediscovery_ok 1 \
    pblock_contract_ok [dict get $final_pblock_audit ok] \
    pblock_count [llength [get_pblocks -quiet]] \
    canonical_pblock_count [dict get $final_pblock_audit pblock_count] \
    geometry_pblock_count [dict get $final_geometry_audit pblock_count] \
    geometry_region0_input_primitives \
        [llength [dict get $final_geometry_plan region0_input_primitives]] \
    geometry_region3_input_primitives \
        [llength [dict get $final_geometry_plan region3_input_primitives]] \
    geometry_owner_region2_weight_primitives \
        [llength [dict get $final_geometry_plan owner_region2_weight_primitives]] \
    geometry_region0_input_ok \
        [hap_projection_ooc_floorplan::region0_input_localization_ok \
            $final_geometry_plan] \
    geometry_region3_input_ok \
        [hap_projection_ooc_floorplan::region3_input_localization_ok \
            $final_geometry_plan] \
    geometry_owner_region2_weight_ok \
        [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $final_geometry_plan] \
    geometry_placement_ok [dict get $final_geometry_metrics ok] \
    compute_clock_buffer_none_nets \
        $final_compute_clock_buffer_none_count \
    compute_clock_buffer_none_ok 1 \
    pblock_dsp_coverage [dict get $final_pblock_audit dsp_coverage] \
    pblock_uram_coverage [dict get $final_pblock_audit uram_coverage] \
    pblock_wrong_slr [dict get $final_pblock_audit placed_wrong] \
    global_virtual_gnd [dict get $final_metrics global_virtual_gnd] \
    global_virtual_vcc [dict get $final_metrics global_virtual_vcc] \
    global_virtual_total [dict get $final_metrics global_virtual_total] \
    global_physical_primitives [dict get $final_metrics global_physical_count] \
    global_direct_slr_empty [dict get $final_metrics global_direct_slr_empty] \
    global_is_placed_empty [dict get $final_metrics global_is_placed_empty] \
    wns_ns $wns whs_ns $whs \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows \
    some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts \
    antenna_island_nets $antennas route_status_partial $partial_nets \
    route_status_conflicts $conflict_nets route_clean $route_clean \
    drc_errors $drc_errors drc_report_error_rows $drc_report_error_rows \
    no_clock_endpoints $no_clock \
    unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay \
    no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    congestion_global_long_level6_or_higher_windows $congestion_level6 \
    operation_ok $operation_ok report_ok $report_ok resource_ok $resource_ok \
    physical_ok $physical_ok architecture_boundary_ok $architecture_boundary_ok \
    timing_ok $timing_ok policy_ok $policy_ok \
    bitstream_generated 0 status $status] {
    puts $fp "$key=$value"
}
close $fp

if {!$operation_ok} {
    hap_write_failure $out $operation_stage $operation_message
}
puts "V5_PRODUCTION_OOC_ROUTE DSP=$slr_dsp URAM=$slr_uram WNS=$wns WHS=$whs ROUTE_CLEAN=$route_clean DRC=$drc_errors CDC_CRITICAL=$cdc_critical DATA_BUFG=$data_bufg GLOBAL_LONG_L6=$congestion_level6 STATUS=$status"
close_design
if {$status ne "V5_PRODUCTION_OOC_POST_ROUTE_PASS"} {
    error "V5 production OOC post-route acceptance failed"
}
