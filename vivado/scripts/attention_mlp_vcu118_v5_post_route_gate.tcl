# Shared fail-closed V5 full-board post-route gate.  This file defines
# procedures only.  The build flow calls it before bitgen; the independent
# audit calls it again after reopening the delivered DCP in a fresh process.

set hap_v5_board_gate_script_dir \
    [file dirname [file normalize [info script]]]
set hap_v5_board_gate_rtl_variant [expr {
    [info exists ::env(HAP_BOARD_RTL_VARIANT)] ?
    $::env(HAP_BOARD_RTL_VARIANT) : "P14_LEGACY"}]
set hap_v5_board_gate_quantizer3_primitives 11178
set hap_v5_board_gate_relief_primitives 68799
set hap_v5_board_gate_total_dsp 5453
set hap_v5_board_gate_slr_dsp {1862 1781 1810}
if {$hap_v5_board_gate_rtl_variant eq "P16_NOCLIP"} {
    foreach variable {HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES
            HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES HAP_P16_POST_OPT_SUMMARY
            HAP_P16_POST_OPT_SUMMARY_SHA256
            HAP_P16_PRODUCTION_REGION2_SUMMARY
            HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
            HAP_P16_PRODUCTION_DCP_SHA256} {
        if {![info exists ::env($variable)] || $::env($variable) eq ""} {
            error "P16 no-clip board gate requires $variable"
        }
    }
    set hap_v5_board_gate_quantizer3_primitives \
        $::env(HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES)
    set hap_v5_board_gate_relief_primitives \
        $::env(HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES)
    set hap_v5_board_gate_total_dsp 5449
    set hap_v5_board_gate_slr_dsp {1862 1777 1810}
}
if {$hap_v5_board_gate_rtl_variant ni {P14_LEGACY P16_NOCLIP} ||
    ![string is integer -strict $hap_v5_board_gate_quantizer3_primitives] ||
    $hap_v5_board_gate_quantizer3_primitives <= 0 ||
    ![string is integer -strict $hap_v5_board_gate_relief_primitives] ||
    $hap_v5_board_gate_relief_primitives <= 0} {
    error "invalid V5 board gate RTL variant or primitive contract"
}
source [file join $hap_v5_board_gate_script_dir \
    v5_production_floorplan_selectors.tcl]
if {$hap_v5_board_gate_rtl_variant eq "P16_NOCLIP"} {
    source [file join $hap_v5_board_gate_script_dir \
        projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl]
} else {
    source [file join $hap_v5_board_gate_script_dir \
        projection_core16x16_w8_reuse_ooc_floorplan.tcl]
}
source [file join $hap_v5_board_gate_script_dir \
    v5_production_p5_input_partition_floorplan.tcl]
source [file join $hap_v5_board_gate_script_dir \
    v5_production_p9_postprocess_partition_floorplan.tcl]
if {$hap_v5_board_gate_rtl_variant eq "P16_NOCLIP"} {
    source [file join $hap_v5_board_gate_script_dir \
        v5_production_p16_noclip_quantizer3_locality_floorplan.tcl]
    source [file join $hap_v5_board_gate_script_dir \
        v5_production_p16_noclip_region2_x2_relief_floorplan.tcl]
} else {
    source [file join $hap_v5_board_gate_script_dir \
        v5_production_p9_quantizer3_locality_floorplan.tcl]
    source [file join $hap_v5_board_gate_script_dir \
        v5_production_p14_region2_x2_relief_floorplan.tcl]
}
source [file join $hap_v5_board_gate_script_dir \
    audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl]
unset hap_v5_board_gate_script_dir

namespace eval hap_v5_board_gate {
    variable expected_part xcvu9p-flga2104-2L-e
    variable expected_top attention_mlp_vcu118_v5_bd_wrapper
}
set ::hap_v5_board_gate::rtl_variant $hap_v5_board_gate_rtl_variant
set ::hap_v5_board_gate::expected_quantizer3_primitives \
    $hap_v5_board_gate_quantizer3_primitives
set ::hap_v5_board_gate::expected_relief_primitives \
    $hap_v5_board_gate_relief_primitives
set ::hap_v5_board_gate::expected_total_dsp $hap_v5_board_gate_total_dsp
set ::hap_v5_board_gate::expected_slr_dsp $hap_v5_board_gate_slr_dsp
unset hap_v5_board_gate_rtl_variant
unset hap_v5_board_gate_quantizer3_primitives
unset hap_v5_board_gate_relief_primitives
unset hap_v5_board_gate_total_dsp
unset hap_v5_board_gate_slr_dsp

proc hap_v5_board_gate::module_cells {module_name} {
    return [lsort -dictionary [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc hap_v5_board_gate::descendants_of_ref {roots ref_name} {
    set result {}
    foreach root $roots {
        set prefix "[get_property NAME $root]/*"
        set result [concat $result [get_cells -quiet -hierarchical -filter \
            "REF_NAME == $ref_name && NAME =~ $prefix"]]
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_board_gate::require_count {label values expected} {
    set actual [llength $values]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_v5_board_gate::timing_count {text category} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $category]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "V5 board timing coverage category is missing: $category"
    }
    return $count
}

proc hap_v5_board_gate::property_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc hap_v5_board_gate::mlp_local_clear_audit {} {
    set branches [hap_v5_board_gate::module_cells \
        hap_mlp_shared_local_slice8x12_s44_s46]
    hap_v5_board_gate::require_count mlp_local_clear_branches $branches 2
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
        hap_v5_board_gate::require_count branch_local_clear $clear_ff 1
        foreach cell $clear_ff {
            if {![hap_v5_board_gate::property_true $cell DONT_TOUCH]} {
                error "V5 board local-clear FF lost DONT_TOUCH: $cell"
            }
            incr protected
        }
        incr total
        lappend branch_counts 1
        lappend all_clear {*}$clear_ff
        set audit [hap_v5_floorplan::wrong_slr_audit $clear_ff $target]
        if {[dict get $audit wrong] != 0 ||
            [dict get $audit direct_slr_empty] != 0} {
            error "V5 board local-clear FF has wrong/unresolved SLR: $branch_name"
        }
        lappend branch_slr_counts [dict get $audit slr_counts]
        incr wrong [dict get $audit wrong]
    }
    set central [get_cells -quiet -hierarchical -filter {
        NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
    hap_v5_board_gate::require_count central_maintenance_clear $central 1
    set q [get_pins -quiet -of_objects $central -filter {REF_PIN_NAME == Q}]
    hap_v5_board_gate::require_count central_maintenance_clear_q $q 1
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
        error "V5 board central clear does not reach both local boundaries"
    }
    set central_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $q]]
    hap_v5_board_gate::require_count central_clear_nets $central_nets 1
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
        error "V5 board central clear directly consumes branch state"
    }
    return [dict create total $total protected $protected \
        branch0 [lindex $branch_counts 0] branch1 [lindex $branch_counts 1] \
        branch0_slr [lindex $branch_slr_counts 0] \
        branch1_slr [lindex $branch_slr_counts 1] wrong $wrong \
        central [llength $central] \
        central_branch_endpoints [llength $clear_endpoints] \
        central_direct_branch_state [llength $direct_branch_state]]
}

proc hap_v5_board_gate::swiglu_local_clear_audit {} {
    set frontends [hap_v5_board_gate::module_cells \
        hap_mlp_swiglu_product_frontend16_q4]
    set row_leaves [hap_v5_board_gate::module_cells \
        hap_mlp_swiglu_row_stream8_q4]
    hap_v5_board_gate::require_count swiglu_clear_frontend $frontends 1
    hap_v5_board_gate::require_count swiglu_clear_row_leaves $row_leaves 2
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
    hap_v5_board_gate::require_count swiglu_control_clear_ff $control 1
    hap_v5_board_gate::require_count swiglu_hadamard_clear_ff $hadamard 1
    hap_v5_board_gate::require_count swiglu_quantizer_clear_ff $quantizer 4
    hap_v5_board_gate::require_count swiglu_row_clear_ff $row_clear 2
    set all_clear [lsort -dictionary -unique \
        [concat $control $hadamard $quantizer $row_clear]]
    hap_v5_board_gate::require_count swiglu_local_clear_ff $all_clear 8
    set protected 0
    foreach cell $all_clear {
        if {![hap_v5_board_gate::property_true $cell DONT_TOUCH]} {
            error "V5 board SwiGLU local-clear FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    set d_pins [get_pins -quiet -of_objects $all_clear -filter \
        {REF_PIN_NAME == D}]
    hap_v5_board_gate::require_count swiglu_local_clear_d_pins $d_pins 8
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
    hap_v5_board_gate::require_count swiglu_direct_clear_bypass_state $bypass 0
    return [dict create total 8 protected $protected control 1 hadamard 1 \
        quantizer 4 row 2 input_nets [llength $clear_nets] bypass 0]
}

proc hap_v5_board_gate::metadata_local_write_audit {} {
    set leaves [hap_v5_board_gate::module_cells hap_mlp_weight_meta_uram_leaf]
    hap_v5_board_gate::require_count metadata_uram_leaves $leaves 4
    set wr_en [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_en_local_r_reg* && REF_NAME =~ FD*}]
    set wr_addr [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_addr_local_r_reg* && REF_NAME =~ FD*}]
    set wr_data [get_cells -quiet -hierarchical -filter {
        NAME =~ */wr_data_local_r_reg* && REF_NAME =~ FD*}]
    hap_v5_board_gate::require_count metadata_local_wr_en_ff $wr_en 4
    hap_v5_board_gate::require_count metadata_local_wr_addr_ff $wr_addr 70
    hap_v5_board_gate::require_count metadata_local_wr_data_ff $wr_data 896
    set protected 0
    foreach cell [concat $wr_en $wr_addr $wr_data] {
        if {![hap_v5_board_gate::property_true $cell DONT_TOUCH]} {
            error "V5 board metadata write FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    if {$protected != 970} {error "V5 board metadata protected-FF mismatch"}
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
        hap_v5_board_gate::require_count \
            "metadata_${leaf_name}_local_ff" $local_ff $expected
        set audit [hap_v5_floorplan::wrong_slr_audit $local_ff $target]
        if {[dict get $audit wrong] != 0 ||
            [dict get $audit direct_slr_empty] != 0} {
            error "V5 board metadata leaf has wrong/unresolved SLR: $leaf_name"
        }
        lappend leaf_counts [llength $local_ff]
        lappend leaf_slr_counts [dict get $audit slr_counts]
        incr wrong [dict get $audit wrong]
    }
    return [dict create leaves [llength $leaves] wr_en [llength $wr_en] \
        wr_addr [llength $wr_addr] wr_data [llength $wr_data] \
        protected $protected leaf_counts $leaf_counts \
        leaf_slr_counts $leaf_slr_counts wrong $wrong]
}

proc hap_v5_board_gate::mlp_capture_leaf_audit {} {
    set branches [hap_v5_board_gate::module_cells \
        hap_mlp_shared_local_slice8x12_s44_s46]
    hap_v5_board_gate::require_count mlp_capture_leaf_branches $branches 2
    set leaves [hap_v5_board_gate::module_cells hap_a8w4_ingress_capture_leaf]
    set leaf_lut [get_cells -quiet -hierarchical -filter {
        NAME =~ */u_leaf && REF_NAME == LUT1}]
    hap_v5_board_gate::require_count mlp_capture_leaf_instances $leaves 1632
    hap_v5_board_gate::require_count mlp_capture_leaf_lut1 $leaf_lut 1632
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
        hap_v5_board_gate::require_count \
            "capture_leaf_instances_${root}" $local_leaves 816
        hap_v5_board_gate::require_count \
            "capture_leaf_lut1_${root}" $local_lut 816
        set audit [hap_v5_floorplan::wrong_slr_audit $local_lut $target]
        if {[dict get $audit wrong] != 0 ||
            [dict get $audit direct_slr_empty] != 0} {
            error "V5 board MLP capture leaf has wrong/unresolved SLR: $root"
        }
        lappend branch_leaf_counts [llength $local_leaves]
        lappend branch_lut_counts [llength $local_lut]
        lappend branch_slr_counts [dict get $audit slr_counts]
        incr wrong [dict get $audit wrong]
    }
    return [dict create instances [llength $leaves] lut1 [llength $leaf_lut] \
        branch_instances $branch_leaf_counts branch_lut1 $branch_lut_counts \
        branch_slr_counts $branch_slr_counts wrong $wrong]
}

proc hap_v5_board_gate::require_architecture_boundaries {clear swiglu metadata capture} {
    foreach {key expected} {
        total 2 protected 2 branch0 1 branch1 1
        branch0_slr {1 0 0} branch1_slr {0 0 1} wrong 0
        central 1 central_branch_endpoints 2 central_direct_branch_state 0
    } {
        if {[dict get $clear $key] ne $expected} {
            error "V5 board local-clear mismatch: $key"
        }
    }
    foreach {key expected} {
        total 8 protected 8 control 1 hadamard 1 quantizer 4 row 2 bypass 0
    } {
        if {[dict get $swiglu $key] ne $expected} {
            error "V5 board SwiGLU local-clear mismatch: $key"
        }
    }
    foreach {key expected} {
        leaves 4 wr_en 4 wr_addr 70 wr_data 896 protected 970
        leaf_counts {243 243 242 242}
        leaf_slr_counts {{243 0 0} {0 0 243} {0 242 0} {0 242 0}}
        wrong 0
    } {
        if {[dict get $metadata $key] ne $expected} {
            error "V5 board metadata-boundary mismatch: $key"
        }
    }
    foreach {key expected} {
        instances 1632 lut1 1632 branch_instances {816 816}
        branch_lut1 {816 816}
        branch_slr_counts {{816 0 0} {0 0 816}} wrong 0
    } {
        if {[dict get $capture $key] ne $expected} {
            error "V5 board capture-leaf mismatch: $key"
        }
    }
}

proc hap_v5_board_gate::route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    if {$required} {error "Missing route-status row: $label"}
    return 0
}

proc hap_v5_board_gate::read_file {path} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty audit input: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_v5_board_gate::parse_xdc_inventory {path} {
    set text [hap_v5_board_gate::read_file $path]
    set user_false 0
    set user_datapath 0
    set unknown_false 0
    set unknown_datapath 0
    set vendor_false 0
    set vendor_datapath 0
    set vendor_core_selector_hits 0
    set rows 0
    foreach line [split $text "\n"] {
        set line [string trim $line]
        if {$line eq "" || [string match "class|*" $line]} {continue}
        set fields [split $line |]
        if {[llength $fields] != 12} {
            error "Malformed XDC inventory row: $line"
        }
        lassign $fields class file_name sha false_count datapath_count \
            scoped_ref scoped_cells scoped_ref_values scoped_cell_values \
            core_hits scope_safe active
        foreach value [list $false_count $datapath_count $scoped_ref \
                $scoped_cells $core_hits $scope_safe $active] {
            if {![string is integer -strict $value] || $value < 0} {
                error "Malformed XDC inventory count: $line"
            }
        }
        if {![regexp {^[0-9a-f]{64}$} $sha]} {
            error "Malformed XDC inventory SHA256: $line"
        }
        if {$active != 1 || $scope_safe != 1} {
            error "XDC inventory contains an inactive/unsafe source: $line"
        }
        foreach selector {
            hap_attention_mlp_board_core
            hap_attention_mlp_production_core
            hap_mlp_serial_ddr_command16_v5_s46
            hap_mlp_shared_dual_slice16x12_s44_s46
            hap_mlp_shared_local_slice8x12_s44_s46
            hap_a8w4_slice8x12_group_s37
        } {
            if {[string first $selector $scoped_ref_values] >= 0 ||
                [string first $selector $scoped_cell_values] >= 0} {
                error "Vendor/user XDC scope reaches the V5 production core: $line"
            }
        }
        incr rows
        switch -- $class {
            USER {
                incr user_false $false_count
                incr user_datapath $datapath_count
            }
            VENDOR_IP {
                incr vendor_false $false_count
                incr vendor_datapath $datapath_count
                incr vendor_core_selector_hits $core_hits
            }
            UNKNOWN {
                incr unknown_false $false_count
                incr unknown_datapath $datapath_count
            }
            default {error "Unknown XDC source class '$class'"}
        }
    }
    if {$rows == 0} {error "XDC source inventory has no rows"}
    return [dict create rows $rows user_false $user_false \
        user_datapath $user_datapath unknown_false $unknown_false \
        unknown_datapath $unknown_datapath vendor_false $vendor_false \
        vendor_datapath $vendor_datapath \
        vendor_core_selector_hits $vendor_core_selector_hits]
}

proc hap_v5_board_gate::exception_commands {path core_names} {
    set text [hap_v5_board_gate::read_file $path]
    set command ""
    set false_count 0
    set datapath_count 0
    set core_hits 0
    foreach raw [split $text "\n"] {
        set line [string trim $raw]
        if {$command eq "" && ($line eq "" || [string index $line 0] eq "#")} {
            continue
        }
        append command $raw "\n"
        if {![info complete $command]} {continue}
        set flat [string map [list "\n" " "] $command]
        set forbidden 0
        if {[regexp -nocase {(^|[;[:space:]])set_false_path([;[:space:]]|$)} \
                $flat]} {
            incr false_count
            set forbidden 1
        }
        if {[regexp -nocase -- {-datapath_only([;[:space:]]|$)} $flat]} {
            incr datapath_count
            set forbidden 1
        }
        if {$forbidden} {
            foreach core_name $core_names {
                if {[string first $core_name $flat] >= 0} {
                    incr core_hits
                    break
                }
            }
        }
        set command ""
    }
    if {[string trim $command] ne ""} {
        error "Incomplete command in exception export: $path"
    }
    return [dict create false $false_count datapath $datapath_count \
        core_hits $core_hits]
}

proc hap_v5_board_gate::exception_scope_audit {path production_prefixes
        vendor_prefixes} {
    set text [hap_v5_board_gate::read_file $path]
    set command ""
    set false_count 0
    set datapath_count 0
    set production_hits 0
    set unclassified_hits 0
    set safe_vendor_hits 0
    foreach raw [split $text "\n"] {
        set line [string trim $raw]
        if {$command eq "" && ($line eq "" || [string index $line 0] eq "#")} {
            continue
        }
        append command $raw "\n"
        if {![info complete $command]} {continue}
        set flat [string map [list "\n" " "] $command]
        set forbidden 0
        if {[regexp -nocase {(^|[;[:space:]])set_false_path([;[:space:]]|$)} \
                $flat]} {
            incr false_count
            set forbidden 1
        }
        if {[regexp -nocase -- {-datapath_only([;[:space:]]|$)} $flat]} {
            incr datapath_count
            set forbidden 1
        }
        if {$forbidden} {
            set is_production 0
            foreach prefix $production_prefixes {
                if {[string first $prefix $flat] >= 0} {
                    set is_production 1
                    break
                }
            }
            if {$is_production} {
                incr production_hits
            } else {
                set is_vendor 0
                foreach prefix $vendor_prefixes {
                    if {[string first $prefix $flat] >= 0} {
                        set is_vendor 1
                        break
                    }
                }
                if {$is_vendor} {
                    incr safe_vendor_hits
                } elseif {[regexp -nocase {
                        (get_clocks|get_ports|get_pins|get_cells|get_nets)} \
                        $flat]} {
                    # A selector-bearing exception which matches neither the
                    # production core nor a recognized vendor hierarchy is
                    # fail-closed.
                    incr unclassified_hits
                } else {
                    # report_exceptions can export canonical clock-domain
                    # groups without retaining the original hierarchy text.
                    # These are recorded separately; the source inventory and
                    # explicit production-selector audit remain authoritative.
                    incr safe_vendor_hits
                }
            }
        }
        set command ""
    }
    if {[string trim $command] ne ""} {
        error "Incomplete command in merged exception export: $path"
    }
    return [dict create false $false_count datapath $datapath_count \
        production_hits $production_hits safe_vendor_hits $safe_vendor_hits \
        unclassified_hits $unclassified_hits]
}

proc hap_v5_board_gate::clock_period {root pin_name label expected} {
    set root_name [get_property NAME $root]
    set candidates [get_pins -quiet [list "${root_name}/$pin_name" \
        "${root_name}/inst/$pin_name"]]
    set pin {}
    foreach candidate $candidates {
        if {[lsearch -exact $pin $candidate] < 0} {lappend pin $candidate}
    }
    if {[llength $pin] != 1} {
        error "$label clock boundary pin is not unique below $root_name: $pin"
    }
    set clocks [get_clocks -quiet -of_objects $pin]
    if {[llength $clocks] != 1} {
        error "$label clock is not unique at $pin: $clocks"
    }
    set period [get_property PERIOD $clocks]
    if {abs($period - $expected) > 0.002} {
        error "$label clock period mismatch: expected=$expected actual=$period"
    }
    return $period
}

proc hap_v5_board_gate::slr_counts {ref_name} {
    set result {0 0 0}
    foreach cell [get_cells -quiet -hierarchical -filter \
            "REF_NAME == $ref_name"] {
        set slr [get_property SLR_INDEX $cell]
        if {![string is integer -strict $slr] || $slr < 0 || $slr > 2} {
            error "$ref_name is not legally placed: $cell SLR_INDEX=$slr"
        }
        lset result $slr [expr {[lindex $result $slr] + 1}]
    }
    return $result
}

proc hap_v5_board_gate::congestion_level6_count {path} {
    set text [hap_v5_board_gate::read_file $path]
    if {[string first "Placer Final Level Congestion Reporting" $text] < 0} {
        error "Congestion report is missing its placer section"
    }
    set count 0
    set congestion_rows 0
    foreach line [split $text "\n"] {
        set fields [split $line |]
        if {[llength $fields] < 5} {continue}
        set type [string trim [lindex $fields 2]]
        set level [string trim [lindex $fields 3]]
        if {$type eq "Global" || $type eq "Long"} {
            if {![string is integer -strict $level]} {
                error "Malformed Global/Long congestion row: $line"
            }
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

# Keep the full-board CDC acceptance parser byte-for-byte equivalent in
# semantics to the production OOC post-route parser.  Requiring the report's
# summary header makes a missing, empty, or format-drifted report fail closed;
# a report with no Critical summary row is the only representation of zero.
proc hap_v5_board_gate::cdc_critical {path} {
    set text [hap_v5_board_gate::read_file $path]
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

# BUFG_GT_SYNC is not a clock buffer: it synchronizes the CE/CLR controls
# consumed by a BUFG_GT and has CESYNC/CLRSYNC data outputs.  It therefore
# must not be counted as a data-promoted BUFG.  Keep that exclusion exact --
# every other BUFG* primitive, including BUFG_GT itself, is still required to
# have a clock associated with its exact O pin.
proc hap_v5_board_gate::pins_by_ref {cell ref_pin direction} {
    return [lsort -dictionary -unique [get_pins -quiet -of_objects \
        [list $cell] -filter \
        "REF_PIN_NAME == $ref_pin && DIRECTION == $direction"]]
}

proc hap_v5_board_gate::clocks_through_pin {pin} {
    set clocks [lsort -dictionary -unique \
        [get_clocks -quiet -of_objects [list $pin]]]
    if {[llength $clocks] != 0} {return $clocks}
    set nets [lsort -dictionary -unique \
        [get_nets -quiet -segments -of_objects [list $pin]]]
    if {[llength $nets] == 0} {return {}}
    return [lsort -dictionary -unique \
        [get_clocks -quiet -of_objects $nets]]
}

proc hap_v5_board_gate::bufg_topology {production_core} {
    set family [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter {REF_NAME =~ BUFG*}]]
    set production_name [get_property NAME $production_core]
    set production_prefix "${production_name}/"
    set real_bufg_total 0
    set clock_bufg 0
    set data_bufg 0
    set real_bufg_bad_connections 0
    set bufg_gt_total 0
    set bufg_gt_clock 0
    set bufg_gt_data 0
    set bufg_gt_sync_total 0
    set bufg_gt_sync_clk_without_clock 0
    set bufg_gt_sync_cesync_leaf_loads 0
    set bufg_gt_sync_clrsync_leaf_loads 0
    set bufg_gt_sync_bad_connections 0
    set production_core_bufg_gt_sync 0
    set details {}

    foreach cell $family {
        set cell_name [get_property NAME $cell]
        set ref [get_property REF_NAME $cell]
        if {$ref eq "BUFG_GT_SYNC"} {
            incr bufg_gt_sync_total
            if {[string first $production_prefix $cell_name] == 0} {
                incr production_core_bufg_gt_sync
                incr bufg_gt_sync_bad_connections
                lappend details \
                    "BAD production_core_gt_sync cell=$cell_name"
            }

            # A preserved vendor instance or historical routed DCP can have a
            # very deep hierarchy.  Query primitive pins by the cell object
            # plus exact REF_PIN_NAME; never infer connectivity from names.
            set pin_signature_bad 0
            set primitive_pins [lsort -dictionary -unique \
                [get_pins -quiet -of_objects [list $cell]]]
            if {[llength $primitive_pins] != 5} {
                incr bufg_gt_sync_bad_connections
                set pin_signature_bad 1
                lappend details \
                    "BAD gt_sync_pin_total cell=$cell_name expected=5 actual=[llength $primitive_pins]"
            }
            foreach {pin_name direction} {
                CE IN CLK IN CLR IN CESYNC OUT CLRSYNC OUT
            } {
                set pins [hap_v5_board_gate::pins_by_ref \
                    $cell $pin_name $direction]
                if {[llength $pins] != 1} {
                    incr bufg_gt_sync_bad_connections
                    set pin_signature_bad 1
                    lappend details \
                        "BAD gt_sync_pin cell=$cell_name pin=$pin_name direction=$direction count=[llength $pins]"
                }
            }
            if {$pin_signature_bad} {
                # Missing/ambiguous primitive pins make all following
                # connectivity inference unsafe.  The failures above remain
                # individually counted and the cell is rejected fail-closed.
                continue
            }

            foreach input_name {CE CLK CLR} {
                set input_pin [lindex [hap_v5_board_gate::pins_by_ref \
                    $cell $input_name IN] 0]
                set input_nets [lsort -dictionary -unique \
                    [get_nets -quiet -segments -of_objects [list $input_pin]]]
                if {[llength $input_nets] == 0} {
                    incr bufg_gt_sync_bad_connections
                    lappend details \
                        "BAD gt_sync_input_without_net cell=$cell_name input=$input_name"
                }
            }

            set clk_pin [lindex [hap_v5_board_gate::pins_by_ref \
                $cell CLK IN] 0]
            set clk_objects [hap_v5_board_gate::clocks_through_pin $clk_pin]
            if {[llength $clk_objects] == 0} {
                incr bufg_gt_sync_clk_without_clock
                incr bufg_gt_sync_bad_connections
                lappend details \
                    "BAD gt_sync_clk_without_clock cell=$cell_name pin=[get_property NAME $clk_pin]"
            }

            foreach output_name {CESYNC CLRSYNC} {
                set expected_load_pin [expr {$output_name eq "CESYNC" ?
                    "CE" : "CLR"}]
                set output_pin [lindex [hap_v5_board_gate::pins_by_ref \
                    $cell $output_name OUT] 0]
                # -segments crosses preserved IP hierarchy boundaries while
                # -leaf returns the actual primitive consumers.  Both queries
                # remain rooted at the exact output pin object.
                set output_nets [lsort -dictionary -unique \
                    [get_nets -quiet -segments -of_objects [list $output_pin]]]
                if {[llength $output_nets] == 0} {
                    incr bufg_gt_sync_bad_connections
                    lappend details \
                        "BAD gt_sync_output_without_net cell=$cell_name output=$output_name"
                    continue
                }
                set loads [lsort -dictionary -unique [get_pins -quiet -leaf \
                    -of_objects $output_nets -filter {DIRECTION == IN}]]
                if {[llength $loads] == 0} {
                    incr bufg_gt_sync_bad_connections
                    lappend details \
                        "BAD gt_sync_output_without_leaf_load cell=$cell_name output=$output_name"
                    continue
                }
                if {$output_name eq "CESYNC"} {
                    incr bufg_gt_sync_cesync_leaf_loads [llength $loads]
                } else {
                    incr bufg_gt_sync_clrsync_leaf_loads [llength $loads]
                }
                foreach load $loads {
                    set load_cells [lsort -dictionary -unique \
                        [get_cells -quiet -of_objects [list $load]]]
                    set load_ref_pin [get_property REF_PIN_NAME $load]
                    if {[llength $load_cells] != 1} {
                        incr bufg_gt_sync_bad_connections
                        lappend details \
                            "BAD gt_sync_leaf_cell cell=$cell_name output=$output_name load=[get_property NAME $load] cell_count=[llength $load_cells]"
                        continue
                    }
                    set load_cell [lindex $load_cells 0]
                    set load_ref [get_property REF_NAME $load_cell]
                    if {$load_ref ne "BUFG_GT" ||
                        $load_ref_pin ne $expected_load_pin} {
                        incr bufg_gt_sync_bad_connections
                        lappend details \
                            "BAD gt_sync_leaf_type cell=$cell_name output=$output_name load=[get_property NAME $load] ref=$load_ref ref_pin=$load_ref_pin expected=BUFG_GT/$expected_load_pin"
                    }
                }
            }
            continue
        }

        # This is intentionally the only BUFG-family exclusion above.  A
        # BUFG_GT is processed here exactly like every real clock buffer and
        # must expose an unambiguous O pin associated with at least one clock.
        incr real_bufg_total
        if {$ref eq "BUFG_GT"} {incr bufg_gt_total}
        set outputs [hap_v5_board_gate::pins_by_ref $cell O OUT]
        if {[llength $outputs] != 1} {
            incr real_bufg_bad_connections
            lappend details \
                "BAD real_bufg_o_pin cell=$cell_name ref=$ref count=[llength $outputs]"
            continue
        }
        set clocks [hap_v5_board_gate::clocks_through_pin \
            [lindex $outputs 0]]
        if {[llength $clocks] == 0} {
            incr data_bufg
            if {$ref eq "BUFG_GT"} {incr bufg_gt_data}
            lappend details "BAD data_bufg cell=$cell_name ref=$ref"
        } else {
            incr clock_bufg
            if {$ref eq "BUFG_GT"} {incr bufg_gt_clock}
        }
    }

    set bufg_family_total [llength $family]
    set bufg_partition_ok [expr {$bufg_family_total ==
        $real_bufg_total + $bufg_gt_sync_total}]
    set bufg_gt_sync_topology_ok [expr {$bufg_gt_sync_total > 0 &&
        $bufg_gt_sync_bad_connections == 0 &&
        $production_core_bufg_gt_sync == 0}]
    set bufg_topology_ok [expr {$bufg_partition_ok &&
        $real_bufg_bad_connections == 0 && $data_bufg == 0 &&
        $bufg_gt_clock == $bufg_gt_total && $bufg_gt_data == 0 &&
        $bufg_gt_sync_topology_ok}]
    return [dict create bufg_family_total $bufg_family_total \
        real_bufg_total $real_bufg_total clock_bufg $clock_bufg \
        data_bufg $data_bufg \
        real_bufg_bad_connections $real_bufg_bad_connections \
        bufg_gt_total $bufg_gt_total bufg_gt_clock $bufg_gt_clock \
        bufg_gt_data $bufg_gt_data \
        bufg_gt_sync_total $bufg_gt_sync_total \
        bufg_gt_sync_clk_without_clock $bufg_gt_sync_clk_without_clock \
        bufg_gt_sync_cesync_leaf_loads $bufg_gt_sync_cesync_leaf_loads \
        bufg_gt_sync_clrsync_leaf_loads $bufg_gt_sync_clrsync_leaf_loads \
        bufg_gt_sync_bad_connections $bufg_gt_sync_bad_connections \
        production_core_bufg_gt_sync $production_core_bufg_gt_sync \
        bufg_partition_ok $bufg_partition_ok \
        bufg_gt_sync_topology_ok $bufg_gt_sync_topology_ok \
        bufg_topology_ok $bufg_topology_ok details $details]
}

proc hap_v5_board_gate::audit {out xdc_inventory {bitstream ""}} {
    variable expected_part
    variable expected_top
    variable rtl_variant
    variable expected_quantizer3_primitives
    variable expected_relief_primitives
    variable expected_total_dsp
    variable expected_slr_dsp
    file mkdir $out

    if {![string match "2025.2*" [version -short]]} {
        error "Vivado 2025.2 required, got [version -short]"
    }
    set part [get_property PART [current_design]]
    set top [get_property TOP [current_design]]
    if {$part ne $expected_part || $top ne $expected_top} {
        error "V5 board identity mismatch: part=$part top=$top"
    }

    set board_cores [hap_v5_board_gate::module_cells \
        hap_attention_mlp_board_core]
    set production_cores [hap_v5_board_gate::module_cells \
        hap_attention_mlp_production_core]
    set v5_serial [hap_v5_board_gate::module_cells \
        hap_mlp_serial_ddr_command16_v5_s46]
    set old_serial [hap_v5_board_gate::module_cells \
        hap_mlp_serial_ddr_command16_s45]
    set v5_shared [hap_v5_board_gate::module_cells \
        hap_mlp_shared_dual_slice16x12_s44_s46]
    set v5_branches [hap_v5_board_gate::module_cells \
        hap_mlp_shared_local_slice8x12_s44_s46]
    set v5_kernels [hap_v5_board_gate::module_cells \
        hap_a8w4_slice8x12_group_s37]
    set v4_kernels [hap_v5_board_gate::module_cells \
        hap_a8w4_slice8x16_group_s36]
    set history2 [hap_v5_board_gate::module_cells \
        hap_mlp_projection_repack12_to16_s24_history2]
    set generic_repack [hap_v5_board_gate::module_cells \
        hap_mlp_projection_repack12_to16_s24]

    hap_v5_board_gate::require_count board_core $board_cores 1
    hap_v5_board_gate::require_count production_core $production_cores 1
    hap_v5_board_gate::require_count v5_serial $v5_serial 1
    hap_v5_board_gate::require_count old_serial $old_serial 0
    hap_v5_board_gate::require_count v5_shared $v5_shared 1
    hap_v5_board_gate::require_count v5_branches $v5_branches 2
    hap_v5_board_gate::require_count v5_kernels $v5_kernels 2
    hap_v5_board_gate::require_count v4_kernels $v4_kernels 0
    hap_v5_board_gate::require_count history2 $history2 2
    hap_v5_board_gate::require_count generic_repack $generic_repack 0

    set xdma_roots [get_cells -quiet -hierarchical -filter \
        {NAME =~ */xdma_0/inst}]
    set ddr0_roots [get_cells -quiet -hierarchical -filter \
        {NAME =~ */ddr4_0/inst}]
    set ddr1_roots [get_cells -quiet -hierarchical -filter \
        {NAME =~ */ddr4_1/inst}]
    hap_v5_board_gate::require_count xdma_endpoint $xdma_roots 1
    hap_v5_board_gate::require_count ddr0_mig $ddr0_roots 1
    hap_v5_board_gate::require_count ddr1_mig $ddr1_roots 1

    set board_core [lindex $board_cores 0]
    set production_core [lindex $production_cores 0]
    set core_period [hap_v5_board_gate::clock_period \
        $board_core core_clk core 10.000]
    set ddr0_period [hap_v5_board_gate::clock_period \
        $board_core ddr0_clk ddr0 3.333]
    set ddr1_period [hap_v5_board_gate::clock_period \
        $board_core ddr1_clk ddr1 3.333]

    set all_dsp [get_cells -quiet -hierarchical -filter \
        {REF_NAME == DSP48E2}]
    set all_uram [get_cells -quiet -hierarchical -filter \
        {REF_NAME == URAM288}]
    set kernel_dsp [hap_v5_board_gate::descendants_of_ref \
        $v5_kernels DSP48E2]
    set branch_dsp_counts {}
    foreach branch $v5_branches {
        lappend branch_dsp_counts [llength \
            [hap_v5_board_gate::descendants_of_ref [list $branch] DSP48E2]]
    }
    set dsp [llength $all_dsp]
    set uram [llength $all_uram]
    set kernel_dsp_count [llength $kernel_dsp]
    if {$dsp != $expected_total_dsp || $uram != 752 ||
        $kernel_dsp_count != 3072 ||
        $branch_dsp_counts ne {1536 1536}} {
        error "V5 board hard-resource mismatch: DSP=$dsp URAM=$uram kernel=$kernel_dsp_count branches=$branch_dsp_counts"
    }

    # Route/phys_opt may replace live cell handles. Rediscover every selector
    # from this routed full-board design and prove the exact P14 contract used
    # by the accepted OOC route. No pre-route collection is reused.
    set ::hap_v5_floorplan::expected_top $expected_top
    if {$rtl_variant eq "P16_NOCLIP" &&
        [hap_projection_ooc_floorplan::get_region2_signature_source] ne
            "P16_PRODUCTION_POST_OPT_SHA256:$::env(HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256)"} {
        error "P16 no-clip board gate signature provenance mismatch"
    }
    set floorplan_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
    set projection_root [file dirname \
        [get_property NAME [dict get $floorplan_plan projection_array]]]
    set geometry_plan \
        [hap_projection_ooc_floorplan::discover $projection_root 1]
    set p5_plan [hap_v5_p5_input_partition::discover $floorplan_plan]
    set p9_postprocess_plan [hap_v5_p9_postprocess_partition::discover \
        $floorplan_plan $p5_plan]
    set p9_quantizer3_plan [hap_v5_p9_quantizer3_locality::discover \
        $floorplan_plan $p5_plan $p9_postprocess_plan]
    set p14_relief_plan \
        [hap_v5_p14_region2_relief::discover $geometry_plan]
    set p8_parent_audit [hap_mlp_p8_parent_boundary::audit]
    set projection_weight_capture_ok \
        [dict get $floorplan_plan projection_weight_capture_ok]
    hap_v5_floorplan::write_discovery $floorplan_plan \
        [file join $out selectors_post_route.txt] \
        V5_BOARD_POST_ROUTE_SELECTORS_PASS
    set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
        $geometry_plan 0 p3_ 1 shared \
        [hap_v5_p14_region2_relief::range_overrides $p14_relief_plan]]
    set geometry_placement \
        [hap_projection_ooc_floorplan::audit_placement $geometry_plan]
    set base_delegate_specs [concat \
        [hap_projection_ooc_floorplan::specs $geometry_plan p3_] \
        [list [dict create name [dict get $p9_quantizer3_plan pblock_name] \
            target 1]]]
    set base_pblock_audit [hap_v5_floorplan::audit_pblock_contract \
        $floorplan_plan 1 P2_COHORT16_COL2_12_2 $base_delegate_specs]
    set p5_pblock_audit [hap_v5_p5_input_partition::audit $p5_plan 1]
    set p9_postprocess_audit \
        [hap_v5_p9_postprocess_partition::audit $p9_postprocess_plan 1]
    set p9_quantizer3_audit \
        [hap_v5_p9_quantizer3_locality::audit $p9_quantizer3_plan 1]
    set p14_relief_audit \
        [hap_v5_p14_region2_relief::audit $p14_relief_plan 1]
    hap_projection_ooc_floorplan::write_plan $geometry_plan \
        [file join $out attention_geometry_post_route.txt] \
        V5_BOARD_POST_ROUTE_GEOMETRY_PASS
    hap_projection_ooc_floorplan::write_placement $geometry_placement \
        [file join $out attention_geometry_placement_post_route.txt] \
        V5_BOARD_POST_ROUTE_GEOMETRY_PLACEMENT_PASS
    hap_v5_floorplan::write_pblock_audit $base_pblock_audit \
        [file join $out base_pblocks_post_route.txt] \
        V5_BOARD_POST_ROUTE_BASE_PBLOCKS_PASS
    hap_v5_p5_input_partition::write_plan $p5_plan \
        [file join $out p5_input_plan_post_route.txt] \
        V5_BOARD_POST_ROUTE_P5_INPUT_PLAN_PASS
    hap_v5_p5_input_partition::write_audit $p5_pblock_audit \
        [file join $out p5_input_pblocks_post_route.txt] \
        V5_BOARD_POST_ROUTE_P5_INPUT_PBLOCKS_PASS
    hap_v5_p9_postprocess_partition::write_plan $p9_postprocess_plan \
        [file join $out p9_postprocess_plan_post_route.txt] \
        V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PLAN_PASS
    hap_v5_p9_postprocess_partition::write_audit $p9_postprocess_audit \
        [file join $out p9_postprocess_pblocks_post_route.txt] \
        V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PBLOCKS_PASS
    hap_v5_p9_quantizer3_locality::write_plan $p9_quantizer3_plan \
        [file join $out p9_quantizer3_plan_post_route.txt] \
        V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PLAN_PASS
    hap_v5_p9_quantizer3_locality::write_audit $p9_quantizer3_audit \
        [file join $out p9_quantizer3_pblock_post_route.txt] \
        V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PBLOCK_PASS
    hap_v5_p14_region2_relief::write_plan $p14_relief_plan \
        [file join $out p14_region2_relief_plan_post_route.txt] \
        V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PLAN_PASS
    hap_v5_p14_region2_relief::write_audit $p14_relief_audit \
        [file join $out p14_region2_relief_pblock_post_route.txt] \
        V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PBLOCK_PASS
    hap_mlp_p8_parent_boundary::write_audit $p8_parent_audit \
        [file join $out p8_parent_ingress_boundary_post_route.txt] \
        V5_BOARD_POST_ROUTE_P8_PARENT_INGRESS_BOUNDARY_PASS
    set floorplan_metrics [hap_v5_floorplan::physical_metrics \
        $floorplan_plan $base_pblock_audit]
    set physical_ok \
        [hap_v5_floorplan::physical_ok $floorplan_plan $floorplan_metrics]
    set expected_center_extras [expr {
        [llength [dict get $p5_plan center_base_extras]] +
        [llength [dict get $p9_postprocess_plan center_rows]]}]
    set base_optimizer_extra_delta [expr {
        [dict get $base_pblock_audit optimizer_extra_count] -
        $expected_center_extras}]
    set compute_nets [get_nets -quiet -hierarchical -filter {
        NAME =~ u_compute/* || NAME =~ */u_compute/*}]
    if {[llength $compute_nets] == 0} {
        error "V5 board post-route compute-net selector is empty"
    }
    foreach net $compute_nets {
        if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
            error "V5 board post-route compute net lost CLOCK_BUFFER_TYPE NONE: $net"
        }
    }
    set floorplan_contract_ok [expr {
        [dict get $floorplan_plan contract_variant] eq
            "P2_COHORT16_COL2_12_2" &&
        [dict get $floorplan_plan rtl_resource_variant] eq $rtl_variant &&
        [dict get $floorplan_plan total_dsp] == $expected_total_dsp &&
        [dict get $floorplan_plan total_uram] == 752 &&
        [dict get $floorplan_plan kernel_dsp] == 3072 &&
        [dict get $floorplan_plan branch0_dsp] == 1536 &&
        [dict get $floorplan_plan branch2_dsp] == 1536 &&
        [dict get $floorplan_plan outer0_dsp] == 1538 &&
        [dict get $floorplan_plan outer2_dsp] == 1538 &&
        [dict get $floorplan_plan outer0_ramb36] == 102 &&
        [dict get $floorplan_plan outer2_ramb36] == 102 &&
        $projection_weight_capture_ok == 1 &&
        [dict get $floorplan_plan raw_weight_push_loads] == 37 &&
        [dict get $floorplan_plan weight_data_capture_nets] == 32 &&
        [dict get $floorplan_plan weight_data_capture_min] == 256 &&
        [dict get $floorplan_plan weight_data_capture_max] == 256 &&
        [dict get $floorplan_plan weight_meta_capture_nets] == 2 &&
        [dict get $floorplan_plan weight_meta_capture_min] == 256 &&
        [dict get $floorplan_plan weight_meta_capture_max] == 256 &&
        [dict get $floorplan_plan weight_group_capture_nets] == 2 &&
        [dict get $floorplan_plan weight_group_capture_min] == 7 &&
        [dict get $floorplan_plan weight_group_capture_max] == 7 &&
        [dict get $p5_plan contract] eq "P5_INPUT_HALF_LOCAL_8_8" &&
        [dict get $p5_plan completed_u8_ff] == 4096 &&
        [dict get $p5_plan completed_meta_ff] == 352 &&
        [dict get $p5_plan input_capture_ff] == 12288 &&
        [dict get $p5_plan capture_leaf_count] == 48 &&
        [dict get $p9_postprocess_plan contract] eq
            "P9_POSTPROCESS_SPLIT_6_4_6" &&
        [llength [dict get $p9_postprocess_plan slr0_rows]] == 16044 &&
        [llength [dict get $p9_postprocess_plan center_rows]] == 10696 &&
        [llength [dict get $p9_postprocess_plan slr2_rows]] == 16044 &&
        [dict get $p9_quantizer3_plan contract] eq
            "P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6" &&
        [dict get $p9_quantizer3_plan primitive_count] ==
            $expected_quantizer3_primitives &&
        [dict get $p9_quantizer3_plan grid_range] eq
            "CLOCKREGION_X2Y5:CLOCKREGION_X3Y6" &&
        [dict get $p14_relief_plan contract] eq
            "P14_ATTN_REGION2_SHARED_X0_X2" &&
        [dict get $p14_relief_plan primitive_count] ==
            $expected_relief_primitives &&
        [dict get $p14_relief_plan base_range] eq
            "CLOCKREGION_X0Y5:CLOCKREGION_X1Y9" &&
        [dict get $p14_relief_plan relief_range] eq
            "CLOCKREGION_X2Y5:CLOCKREGION_X2Y9" &&
        [dict get $p14_relief_plan expected_range] eq
            "CLOCKREGION_X0Y5:CLOCKREGION_X2Y9" &&
        [dict get $geometry_audit pblock_count] == 10 &&
        [dict get $geometry_placement ok] == 1 &&
        [dict get $base_pblock_audit ok] == 1 &&
        [dict get $base_pblock_audit require_placed] == 1 &&
        [dict get $base_pblock_audit contract_variant] eq
            "P2_COHORT16_COL2_12_2" &&
        [dict get $base_pblock_audit pblock_count] == 11 &&
        $base_optimizer_extra_delta >= 0 &&
        $base_optimizer_extra_delta <= 4096 &&
        [dict get $p5_pblock_audit ok] == 1 &&
        [dict get $p5_pblock_audit require_placed] == 1 &&
        [dict get $p5_pblock_audit pblock_count] == 2 &&
        [dict get $p5_pblock_audit center_wrong] == 0 &&
        [dict get $p5_pblock_audit outer_wrong] == 0 &&
        [dict get $p5_pblock_audit outer_extras] <= 4096 &&
        [dict get $p9_postprocess_audit ok] == 1 &&
        [dict get $p9_postprocess_audit require_placed] == 1 &&
        [dict get $p9_postprocess_audit pblock_count] == 2 &&
        [dict get $p9_postprocess_audit center_wrong] == 0 &&
        [dict get $p9_postprocess_audit outer_wrong] == 0 &&
        [dict get $p9_postprocess_audit outer_extras] <= 4096 &&
        [dict get $p9_quantizer3_audit ok] == 1 &&
        [dict get $p9_quantizer3_audit wrong] == 0 &&
        [dict get $p9_quantizer3_audit unplaced] == 0 &&
        [dict get $p14_relief_audit ok] == 1 &&
        [dict get $p14_relief_audit missing] == 0 &&
        [dict get $p14_relief_audit wrong] == 0 &&
        [dict get $p14_relief_audit unplaced] == 0 &&
        [dict get $p8_parent_audit ok] == 1 &&
        [dict get $p8_parent_audit parent_head_ff] == 6560 &&
        [dict get $p8_parent_audit parent_tail_ff] == 6560 &&
        [dict get $p8_parent_audit parent_count_ff] == 2 &&
        [dict get $p8_parent_audit parent_count_replica_equivalence_ok] == 1 &&
        [dict get $p8_parent_audit parent_pointer_ff] == 0 &&
        [dict get $p8_parent_audit local_clear_shared_upstream_ready_paths] == 0 &&
        [dict get $p8_parent_audit branch_credit_shared_upstream_ready_paths] == 0 &&
        [dict get $p8_parent_audit local_clear_gate_compute_ready_paths] == 0 &&
        [dict get $p8_parent_audit branch_credit_gate_compute_ready_paths] == 0 &&
        [dict get $p8_parent_audit local_clear_down_compute_ready_paths] == 0 &&
        [dict get $p8_parent_audit branch_credit_down_compute_ready_paths] == 0 &&
        [dict get $p8_parent_audit local_clear_input_cache_ready_paths] == 0 &&
        [dict get $p8_parent_audit branch_credit_input_cache_ready_paths] == 0 &&
        [llength [get_pblocks -quiet]] == 26 &&
        [llength [dict get $geometry_plan region0_input_primitives]] == 3136 &&
        [llength [dict get $geometry_plan region3_input_primitives]] == 2112 &&
        [llength [dict get $geometry_plan owner_region2_weight_primitives]] == 2048 &&
        [hap_projection_ooc_floorplan::region0_input_localization_ok \
            $geometry_plan] &&
        [hap_projection_ooc_floorplan::region3_input_localization_ok \
            $geometry_plan] &&
        [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
            $geometry_plan] &&
        [dict get $base_pblock_audit dsp_coverage] == $expected_total_dsp &&
        [dict get $base_pblock_audit uram_coverage] == 752 &&
        [dict get $base_pblock_audit placed_wrong] == 0 &&
        $physical_ok
    }]
    if {!$floorplan_contract_ok} {
        error "V5 board P14 post-route physical contract failed"
    }

    set slr_dsp [dict get $floorplan_metrics slr_dsp]
    set slr_uram [dict get $floorplan_metrics slr_uram]
    if {$slr_dsp ne $expected_slr_dsp} {
        error "V5 board DSP locality mismatch: expected=$expected_slr_dsp actual=$slr_dsp"
    }
    if {$slr_uram ne {224 224 304}} {
        error "V5 board URAM locality mismatch: expected=224/224/304 actual=$slr_uram"
    }

    set unplaced [dict get $floorplan_metrics unplaced]
    if {$unplaced != 0} {error "V5 board has $unplaced unplaced primitives"}
    set wrong_slr [dict get $floorplan_metrics wrong_total]
    if {$wrong_slr != 0} {
        error "V5 board has $wrong_slr canonical primitives in the wrong SLR"
    }

    set local_clear [hap_v5_board_gate::mlp_local_clear_audit]
    set swiglu_clear [hap_v5_board_gate::swiglu_local_clear_audit]
    set metadata_boundary [hap_v5_board_gate::metadata_local_write_audit]
    set capture_boundary [hap_v5_board_gate::mlp_capture_leaf_audit]
    hap_v5_board_gate::require_architecture_boundaries \
        $local_clear $swiglu_clear $metadata_boundary $capture_boundary
    set architecture_boundary_ok 1
    set boundary_fh [open \
        [file join $out architecture_boundaries_post_route.txt] w]
    foreach {key value} [list \
        mlp_local_clear_ff [dict get $local_clear total] \
        mlp_local_clear_protected_ff [dict get $local_clear protected] \
        branch0_local_clear_ff [dict get $local_clear branch0] \
        branch1_local_clear_ff [dict get $local_clear branch1] \
        branch0_local_clear_slr [dict get $local_clear branch0_slr] \
        branch1_local_clear_slr [dict get $local_clear branch1_slr] \
        mlp_local_clear_wrong_slr [dict get $local_clear wrong] \
        mlp_central_clear_ff [dict get $local_clear central] \
        mlp_central_clear_branch_endpoints \
            [dict get $local_clear central_branch_endpoints] \
        mlp_central_clear_direct_branch_state \
            [dict get $local_clear central_direct_branch_state] \
        swiglu_local_clear_ff [dict get $swiglu_clear total] \
        swiglu_local_clear_protected_ff [dict get $swiglu_clear protected] \
        swiglu_control_clear_ff [dict get $swiglu_clear control] \
        swiglu_hadamard_clear_ff [dict get $swiglu_clear hadamard] \
        swiglu_quantizer_clear_ff [dict get $swiglu_clear quantizer] \
        swiglu_row_clear_ff [dict get $swiglu_clear row] \
        swiglu_clear_input_nets [dict get $swiglu_clear input_nets] \
        swiglu_direct_clear_bypass_state [dict get $swiglu_clear bypass] \
        metadata_leaf_instances [dict get $metadata_boundary leaves] \
        metadata_local_wr_en_ff [dict get $metadata_boundary wr_en] \
        metadata_local_wr_addr_ff [dict get $metadata_boundary wr_addr] \
        metadata_local_wr_data_ff [dict get $metadata_boundary wr_data] \
        metadata_local_write_protected_ff \
            [dict get $metadata_boundary protected] \
        metadata_local_write_leaf_counts \
            [dict get $metadata_boundary leaf_counts] \
        metadata_local_write_leaf_slr_counts \
            [dict get $metadata_boundary leaf_slr_counts] \
        metadata_local_write_wrong_slr [dict get $metadata_boundary wrong] \
        mlp_capture_leaf_instances [dict get $capture_boundary instances] \
        mlp_capture_leaf_lut1 [dict get $capture_boundary lut1] \
        mlp_capture_leaf_branch_instances \
            [dict get $capture_boundary branch_instances] \
        mlp_capture_leaf_branch_lut1 \
            [dict get $capture_boundary branch_lut1] \
        mlp_capture_leaf_branch_slr_counts \
            [dict get $capture_boundary branch_slr_counts] \
        mlp_capture_leaf_wrong_slr [dict get $capture_boundary wrong] \
        architecture_boundary_ok $architecture_boundary_ok \
        status V5_BOARD_ARCHITECTURE_BOUNDARIES_PASS] {
        puts $boundary_fh "$key=$value"
    }
    close $boundary_fh

    set bufg_audit [hap_v5_board_gate::bufg_topology $production_core]
    set bufg_details [dict get $bufg_audit details]
    set bufg_fh [open [file join $out bufg_topology_post_route.txt] w]
    foreach line $bufg_details {puts $bufg_fh $line}
    foreach key [lsort -dictionary [dict keys $bufg_audit]] {
        if {$key ne "details"} {
            puts $bufg_fh "$key=[dict get $bufg_audit $key]"
        }
    }
    close $bufg_fh
    set bufg_topology_ok [dict get $bufg_audit bufg_topology_ok]

    set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
        -report_unconstrained -warn_on_violation -return_string]
    set timing_fh [open [file join $out timing_post_route.rpt] w]
    puts -nonewline $timing_fh $timing_text
    close $timing_fh
    set no_clock_endpoints [hap_v5_board_gate::timing_count \
        $timing_text no_clock]
    set unconstrained_paths [hap_v5_board_gate::timing_count \
        $timing_text unconstrained_internal_endpoints]
    set timing_coverage_ok [expr {$no_clock_endpoints == 0 &&
        $unconstrained_paths == 0}]
    set setup_path [lindex [get_timing_paths -quiet -delay_type max \
        -max_paths 1] 0]
    set hold_path [lindex [get_timing_paths -quiet -delay_type min \
        -max_paths 1] 0]
    if {[llength $setup_path] == 0 || [llength $hold_path] == 0} {
        error "V5 board timing queries returned no setup/hold path"
    }
    set wns [get_property SLACK $setup_path]
    set whs [get_property SLACK $hold_path]

    set route_text [report_route_status -return_string]
    set route_fh [open [file join $out route_status_post_route.rpt] w]
    puts -nonewline $route_fh $route_text
    close $route_fh
    set route_errors [hap_v5_board_gate::route_row \
        $route_text "# of nets with routing errors" 1]
    set explicit_gaps [hap_v5_board_gate::route_row \
        $route_text "# of nets with explicit gaps"]
    set unrouted_rows [hap_v5_board_gate::route_row \
        $route_text "# of unrouted nets"]
    set unrouted_pins [hap_v5_board_gate::route_row \
        $route_text "# of nets with some unrouted pins"]
    set resource_conflicts [hap_v5_board_gate::route_row \
        $route_text "# of nets with resource conflicts"]
    set antennas [hap_v5_board_gate::route_row \
        $route_text "# of nets with antennas/islands"]
    set partial [llength [get_nets -quiet -hierarchical -filter {
        ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
        ROUTE_STATUS == UNROUTED || ROUTE_STATUS == HIERPORT
    }]]
    set conflicts [llength [get_nets -quiet -hierarchical -filter \
        {ROUTE_STATUS == CONFLICTS}]]
    set route_clean [expr {$route_errors == 0 && $explicit_gaps == 0 &&
        $unrouted_rows == 0 && $unrouted_pins == 0 &&
        $resource_conflicts == 0 && $antennas == 0 &&
        $partial == 0 && $conflicts == 0}]

    report_drc -file [file join $out drc_post_route.rpt]
    set drc_errors [llength [get_drc_violations -quiet -filter \
        {SEVERITY == Error}]]
    set cdc_path [file join $out cdc_post_route.rpt]
    report_cdc -details -file $cdc_path
    set cdc_critical [hap_v5_board_gate::cdc_critical $cdc_path]
    report_clock_interaction -delay_type min_max -file \
        [file join $out clock_interaction_post_route.rpt]
    report_clock_utilization -file \
        [file join $out clock_utilization_post_route.rpt]
    report_utilization -file [file join $out utilization_post_route.rpt]
    report_utilization -hierarchical -hierarchical_depth 14 -file \
        [file join $out utilization_hier_post_route.rpt]
    report_utilization -slr -file \
        [file join $out utilization_slr_post_route.rpt]
    set congestion_path [file join $out congestion_post_route.rpt]
    report_design_analysis -congestion -file $congestion_path
    set level6 [hap_v5_board_gate::congestion_level6_count $congestion_path]

    set exceptions_path [file join $out exceptions_coverage_post_route.rpt]
    set valid_path [file join $out exceptions_valid_post_route.xdc]
    set merged_path [file join $out exceptions_merged_post_route.xdc]
    report_exceptions -coverage -file $exceptions_path
    report_exceptions -write_valid_exceptions -file $valid_path
    report_exceptions -write_merged_exceptions -file $merged_path
    set inventory [hap_v5_board_gate::parse_xdc_inventory $xdc_inventory]
    set core_names [list [get_property NAME $board_core] \
        [get_property NAME $production_core] "/core/inst/" \
        "hap_attention_mlp_board_core" "hap_attention_mlp_production_core"]
    set valid_commands [hap_v5_board_gate::exception_commands \
        $valid_path $core_names]
    set merged_commands [hap_v5_board_gate::exception_commands \
        $merged_path $core_names]
    set production_prefixes [list [get_property NAME $board_core] \
        [get_property NAME $production_core] "/core/inst/" \
        "hap_attention_mlp_board_core" "hap_attention_mlp_production_core"]
    set vendor_prefixes {}
    foreach root [concat $xdma_roots $ddr0_roots $ddr1_roots \
        [get_cells -quiet -hierarchical -filter {
            NAME =~ */host_split/inst || NAME =~ */d0_smc/inst ||
            NAME =~ */d1_smc/inst || NAME =~ */ctrl_smc/inst ||
            NAME =~ */d0_mig_slice/inst || NAME =~ */d1_mig_slice/inst ||
            NAME =~ */rst_core/inst || NAME =~ */rst_ddr0/inst ||
            NAME =~ */rst_ddr1/inst || NAME =~ */clk_core/inst
        }]] {
        lappend vendor_prefixes [get_property NAME $root]
    }
    set merged_scope [hap_v5_board_gate::exception_scope_audit \
        $merged_path $production_prefixes $vendor_prefixes]
    set exception_policy_ok [expr {
        [dict get $inventory user_false] == 0 &&
        [dict get $inventory user_datapath] == 0 &&
        [dict get $inventory unknown_false] == 0 &&
        [dict get $inventory unknown_datapath] == 0 &&
        [dict get $inventory vendor_core_selector_hits] == 0 &&
        [dict get $valid_commands core_hits] == 0 &&
        [dict get $merged_commands core_hits] == 0 &&
        [dict get $merged_scope production_hits] == 0 &&
        [dict get $merged_scope unclassified_hits] == 0}]

    set bitstream_size 0
    set bitstream_sha256 NOT_PROVIDED
    if {$bitstream ne ""} {
        if {![file exists $bitstream] || ![file isfile $bitstream] ||
            [file size $bitstream] == 0} {
            error "Missing or empty V5 board bitstream: $bitstream"
        }
        set bitstream_size [file size $bitstream]
        set bitstream_sha256 [lindex [exec sha256sum $bitstream] 0]
        if {![regexp {^[0-9a-f]{64}$} $bitstream_sha256]} {
            error "Invalid V5 board bitstream SHA256: $bitstream_sha256"
        }
    }

    set status [expr {$wns >= 0.0 && $whs >= 0.0 && $timing_coverage_ok &&
        $route_clean &&
        $drc_errors == 0 && $level6 == 0 && $bufg_topology_ok &&
        $cdc_critical == 0 && $floorplan_contract_ok &&
        $projection_weight_capture_ok && $architecture_boundary_ok &&
        $exception_policy_ok ?
        "V5_BOARD_POST_ROUTE_PASS" : "FAIL"}]
    set result [dict create tool [version -short] part $part top $top \
        evidence_class FULL_VCU118_BOARD_POST_ROUTE \
        rtl_variant $rtl_variant \
        rtl_resource_variant [dict get $floorplan_plan rtl_resource_variant] \
        region2_signature_source \
            [hap_projection_ooc_floorplan::get_region2_signature_source] \
        core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
        core_period_ns $core_period ddr0_period_ns $ddr0_period \
        ddr1_period_ns $ddr1_period xdma_endpoint_count 1 \
        dual_ddr_mig_count 2 board_core_instances 1 production_core_instances 1 \
        v5_serial_instances 1 old_serial_instances 0 \
        v5_shared_instances 1 v5_branch_instances 2 \
        v5_kernel12_instances 2 v4_kernel16_instances 0 \
        history2_repack_instances 2 generic_repack_instances 0 \
        raw_weight_push_loads \
            [dict get $floorplan_plan raw_weight_push_loads] \
        weight_data_capture_contract 32x256 \
        weight_data_capture_nets \
            [dict get $floorplan_plan weight_data_capture_nets] \
        weight_data_capture_loads \
            [dict get $floorplan_plan weight_data_capture_min]/[dict get $floorplan_plan weight_data_capture_max] \
        weight_meta_capture_contract 2x256 \
        weight_meta_capture_nets \
            [dict get $floorplan_plan weight_meta_capture_nets] \
        weight_meta_capture_loads \
            [dict get $floorplan_plan weight_meta_capture_min]/[dict get $floorplan_plan weight_meta_capture_max] \
        weight_group_capture_contract 2x7 \
        weight_group_capture_nets \
            [dict get $floorplan_plan weight_group_capture_nets] \
        weight_group_capture_loads \
            [dict get $floorplan_plan weight_group_capture_min]/[dict get $floorplan_plan weight_group_capture_max] \
        projection_weight_capture_ok $projection_weight_capture_ok \
        mlp_kernel_dsp48e2 $kernel_dsp_count branch_dsp48e2 $branch_dsp_counts \
        outer0_dsp48e2 [dict get $floorplan_plan outer0_dsp] \
        outer2_dsp48e2 [dict get $floorplan_plan outer2_dsp] \
        outer0_ramb36e2 [dict get $floorplan_plan outer0_ramb36] \
        outer2_ramb36e2 [dict get $floorplan_plan outer2_ramb36] \
        mlp_local_clear_ff [dict get $local_clear total] \
        mlp_local_clear_protected_ff [dict get $local_clear protected] \
        branch0_local_clear_ff [dict get $local_clear branch0] \
        branch1_local_clear_ff [dict get $local_clear branch1] \
        branch0_local_clear_slr [dict get $local_clear branch0_slr] \
        branch1_local_clear_slr [dict get $local_clear branch1_slr] \
        mlp_local_clear_wrong_slr [dict get $local_clear wrong] \
        mlp_central_clear_ff [dict get $local_clear central] \
        mlp_central_clear_branch_endpoints \
            [dict get $local_clear central_branch_endpoints] \
        mlp_central_clear_direct_branch_state \
            [dict get $local_clear central_direct_branch_state] \
        swiglu_local_clear_ff [dict get $swiglu_clear total] \
        swiglu_local_clear_protected_ff [dict get $swiglu_clear protected] \
        swiglu_control_clear_ff [dict get $swiglu_clear control] \
        swiglu_hadamard_clear_ff [dict get $swiglu_clear hadamard] \
        swiglu_quantizer_clear_ff [dict get $swiglu_clear quantizer] \
        swiglu_row_clear_ff [dict get $swiglu_clear row] \
        swiglu_clear_input_nets [dict get $swiglu_clear input_nets] \
        swiglu_direct_clear_bypass_state [dict get $swiglu_clear bypass] \
        metadata_leaf_instances [dict get $metadata_boundary leaves] \
        metadata_local_wr_en_ff [dict get $metadata_boundary wr_en] \
        metadata_local_wr_addr_ff [dict get $metadata_boundary wr_addr] \
        metadata_local_wr_data_ff [dict get $metadata_boundary wr_data] \
        metadata_local_write_protected_ff \
            [dict get $metadata_boundary protected] \
        metadata_local_write_leaf_counts \
            [dict get $metadata_boundary leaf_counts] \
        metadata_local_write_leaf_slr_counts \
            [dict get $metadata_boundary leaf_slr_counts] \
        metadata_local_write_wrong_slr [dict get $metadata_boundary wrong] \
        mlp_capture_leaf_instances [dict get $capture_boundary instances] \
        mlp_capture_leaf_lut1 [dict get $capture_boundary lut1] \
        mlp_capture_leaf_branch_instances \
            [dict get $capture_boundary branch_instances] \
        mlp_capture_leaf_branch_lut1 \
            [dict get $capture_boundary branch_lut1] \
        mlp_capture_leaf_branch_slr_counts \
            [dict get $capture_boundary branch_slr_counts] \
        mlp_capture_leaf_wrong_slr [dict get $capture_boundary wrong] \
        architecture_boundary_ok $architecture_boundary_ok \
        base_contract_variant [dict get $floorplan_plan contract_variant] \
        p5_contract [dict get $p5_plan contract] \
        p9_postprocess_contract [dict get $p9_postprocess_plan contract] \
        p9_quantizer3_contract [dict get $p9_quantizer3_plan contract] \
        p14_region2_relief_contract [dict get $p14_relief_plan contract] \
        canonical_pblock_count [dict get $base_pblock_audit pblock_count] \
        geometry_pblock_count [dict get $geometry_audit pblock_count] \
        p5_added_pblock_count [dict get $p5_pblock_audit pblock_count] \
        p9_postprocess_added_pblock_count \
            [dict get $p9_postprocess_audit pblock_count] \
        p9_quantizer3_added_pblock_count 1 \
        p14_region2_relief_added_pblock_count 0 \
        total_pblock_count [llength [get_pblocks -quiet]] \
        completed_u8_ff [dict get $p5_plan completed_u8_ff] \
        completed_meta_ff [dict get $p5_plan completed_meta_ff] \
        input_capture_ff [dict get $p5_plan input_capture_ff] \
        input_capture_controls [dict get $p5_plan capture_leaf_count] \
        p5_center_wrong_slr [dict get $p5_pblock_audit center_wrong] \
        p5_outer_wrong_slr [dict get $p5_pblock_audit outer_wrong] \
        p5_outer_optimizer_extras [dict get $p5_pblock_audit outer_extras] \
        p9_postprocess_center_wrong_slr \
            [dict get $p9_postprocess_audit center_wrong] \
        p9_postprocess_outer_wrong_slr \
            [dict get $p9_postprocess_audit outer_wrong] \
        p9_postprocess_outer_optimizer_extras \
            [dict get $p9_postprocess_audit outer_extras] \
        p9_slr0_row_primitives \
            [llength [dict get $p9_postprocess_plan slr0_rows]] \
        p9_center_row_primitives \
            [llength [dict get $p9_postprocess_plan center_rows]] \
        p9_slr2_row_primitives \
            [llength [dict get $p9_postprocess_plan slr2_rows]] \
        p9_quantizer3_primitives \
            [dict get $p9_quantizer3_plan primitive_count] \
        p9_quantizer3_grid_range \
            [dict get $p9_quantizer3_plan grid_range] \
        p9_quantizer3_wrong_region [dict get $p9_quantizer3_audit wrong] \
        p9_quantizer3_unplaced [dict get $p9_quantizer3_audit unplaced] \
        p14_region2_relief_primitives \
            [dict get $p14_relief_plan primitive_count] \
        p14_region2_relief_base_range [dict get $p14_relief_plan base_range] \
        p14_region2_relief_range [dict get $p14_relief_plan relief_range] \
        p14_region2_expected_range [dict get $p14_relief_plan expected_range] \
        p14_region2_relief_placed [dict get $p14_relief_audit relief_placed] \
        p14_region2_relief_wrong [dict get $p14_relief_audit wrong] \
        p14_region2_relief_unplaced [dict get $p14_relief_audit unplaced] \
        parent_head_ff [dict get $p8_parent_audit parent_head_ff] \
        parent_tail_ff [dict get $p8_parent_audit parent_tail_ff] \
        parent_count_ff [dict get $p8_parent_audit parent_count_ff] \
        parent_count_physical_ff \
            [dict get $p8_parent_audit parent_count_physical_ff] \
        parent_count_replica_ff \
            [dict get $p8_parent_audit parent_count_replica_ff] \
        parent_count_replica_equivalence_ok \
            [dict get $p8_parent_audit parent_count_replica_equivalence_ok] \
        parent_pointer_ff [dict get $p8_parent_audit parent_pointer_ff] \
        local_clear_shared_upstream_ready_paths \
            [dict get $p8_parent_audit local_clear_shared_upstream_ready_paths] \
        branch_credit_shared_upstream_ready_paths \
            [dict get $p8_parent_audit branch_credit_shared_upstream_ready_paths] \
        local_clear_gate_compute_ready_paths \
            [dict get $p8_parent_audit local_clear_gate_compute_ready_paths] \
        branch_credit_gate_compute_ready_paths \
            [dict get $p8_parent_audit branch_credit_gate_compute_ready_paths] \
        local_clear_down_compute_ready_paths \
            [dict get $p8_parent_audit local_clear_down_compute_ready_paths] \
        branch_credit_down_compute_ready_paths \
            [dict get $p8_parent_audit branch_credit_down_compute_ready_paths] \
        local_clear_input_cache_ready_paths \
            [dict get $p8_parent_audit local_clear_input_cache_ready_paths] \
        branch_credit_input_cache_ready_paths \
            [dict get $p8_parent_audit branch_credit_input_cache_ready_paths] \
        projected_slr_dsp48e2 $expected_slr_dsp \
        projected_slr_uram288 {224 224 304} \
        dsp48e2 $dsp dsp_required $expected_total_dsp dsp_limit 5500 \
        uram288 $uram uram_required 752 \
        slr0_dsp48e2 [lindex $slr_dsp 0] \
        slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] per_slr_dsp_limit 2280 \
        slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] \
        slr2_uram288 [lindex $slr_uram 2] \
        unplaced_primitives $unplaced wrong_slr_primitives $wrong_slr \
        live_post_route_rediscovery_ok 1 \
        pblock_contract_variant [dict get $base_pblock_audit contract_variant] \
        pblock_contract_ok [dict get $base_pblock_audit ok] \
        pblock_require_placed [dict get $base_pblock_audit require_placed] \
        pblock_count [llength [get_pblocks -quiet]] \
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
        physical_placement_ok $physical_ok \
        compute_clock_buffer_none_nets [llength $compute_nets] \
        compute_clock_buffer_none_ok 1 \
        pblock_members [dict get $base_pblock_audit member_count] \
        pblock_optimizer_extra_count \
            [dict get $base_pblock_audit optimizer_extra_count] \
        base_optimizer_extra_delta $base_optimizer_extra_delta \
        pblock_dsp_coverage [dict get $base_pblock_audit dsp_coverage] \
        pblock_uram_coverage [dict get $base_pblock_audit uram_coverage] \
        pblock_wrong_slr [dict get $base_pblock_audit placed_wrong] \
        physical_ok $physical_ok floorplan_contract_ok $floorplan_contract_ok \
        wns_ns $wns whs_ns $whs \
        no_clock_endpoints $no_clock_endpoints \
        unconstrained_paths $unconstrained_paths \
        timing_coverage_ok $timing_coverage_ok \
        route_error_nets $route_errors \
        explicit_gap_nets $explicit_gaps unrouted_nets $unrouted_rows \
        some_unrouted_pin_nets $unrouted_pins \
        resource_conflict_nets $resource_conflicts \
        antenna_island_nets $antennas route_status_partial $partial \
        route_status_conflicts $conflicts route_clean $route_clean \
        drc_errors $drc_errors cdc_critical $cdc_critical \
        congestion_level6_or_higher_windows $level6 \
        xdc_inventory_rows [dict get $inventory rows] \
        user_xdc_false_path_commands [dict get $inventory user_false] \
        user_xdc_datapath_only_commands [dict get $inventory user_datapath] \
        unknown_xdc_false_path_commands [dict get $inventory unknown_false] \
        unknown_xdc_datapath_only_commands [dict get $inventory unknown_datapath] \
        vendor_xdc_false_path_commands [dict get $inventory vendor_false] \
        vendor_xdc_datapath_only_commands [dict get $inventory vendor_datapath] \
        vendor_xdc_core_selector_hits \
            [dict get $inventory vendor_core_selector_hits] \
        valid_exception_false_path_commands [dict get $valid_commands false] \
        valid_exception_datapath_only_commands [dict get $valid_commands datapath] \
        valid_exception_core_hits [dict get $valid_commands core_hits] \
        merged_exception_false_path_commands [dict get $merged_commands false] \
        merged_exception_datapath_only_commands [dict get $merged_commands datapath] \
        merged_exception_core_hits [dict get $merged_commands core_hits] \
        merged_exception_safe_vendor_commands [dict get $merged_scope safe_vendor_hits] \
        merged_exception_unclassified_commands \
            [dict get $merged_scope unclassified_hits] \
        merged_exception_production_core_commands \
            [dict get $merged_scope production_hits] \
        exception_scope_policy_ok $exception_policy_ok \
        bitstream $bitstream bitstream_size_bytes $bitstream_size \
        bitstream_sha256 $bitstream_sha256 status $status]
    dict for {key value} [dict remove $bufg_audit details] {
        dict set result $key $value
    }

    set fp [open [file join $out post_route_gate_summary.txt] w]
    dict for {key value} $result {puts $fp "$key=$value"}
    close $fp
    if {$status ne "V5_BOARD_POST_ROUTE_PASS"} {
        error "V5 full-board post-route gate failed"
    }
    return $result
}
