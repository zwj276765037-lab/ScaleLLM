# P5 input-frontend partition layered on the proven P3 21-pblock floorplan.
# The two completed eight-row halves follow their quantizers and BRAM caches
# to the outer SLRs.  The input capture, the unique folded Hadamard and all
# residual frontend control stay in the existing canonical SLR1 pblock.

namespace eval hap_v5_p5_input_partition {
    variable contract P5_INPUT_HALF_LOCAL_8_8
    variable half0_pblock pb_v5_p5_input_half0_slr0
    variable half1_pblock pb_v5_p5_input_half1_slr2
    variable center_pblock pb_v5_attention_projection_center12_slr1
}

proc hap_v5_p5_input_partition::require_count {label objects expected} {
    if {[llength $objects] != $expected} {
        error "P5 $label count mismatch: expected=$expected actual=[llength $objects]"
    }
}

proc hap_v5_p5_input_partition::module_children {root module_name} {
    set result {}
    foreach cell [hap_v5_floorplan::module_cells $module_name] {
        if {[hap_v5_floorplan::cell_is_below $cell $root]} {
            lappend result $cell
        }
    }
    return [lsort -dictionary -unique $result]
}

proc hap_v5_p5_input_partition::row_storage {root_primitives root_name row} {
    set selected {}
    set u8 0
    set meta 0
    set row_logic 0
    set storage_pattern [format \
        {^%s/(bundle_u8_bank_r_reg|bundle_meta_bank_r_reg)\[%d\]\[} \
        $root_name $row]
    set logic_pattern [format {^%s/g_bundle_row\[%d\]\.} $root_name $row]
    foreach cell $root_primitives {
        set name [get_property NAME $cell]
        if {[regexp -- $storage_pattern $name]} {
            lappend selected $cell
            if {[string first "/bundle_u8_bank_r_reg" $name] >= 0} {
                incr u8
            } else {
                incr meta
            }
        } elseif {[regexp -- $logic_pattern $name]} {
            lappend selected $cell
            incr row_logic
        }
    }
    if {$u8 < 256 || $meta < 22 || $row_logic < 2} {
        error "P5 completed-row signature mismatch: row=$row u8=$u8 meta=$meta logic=$row_logic"
    }
    return [dict create cells [lsort -dictionary -unique $selected] \
        u8 $u8 meta $meta logic $row_logic]
}

proc hap_v5_p5_input_partition::count_name_pattern {cells pattern} {
    set count 0
    foreach cell $cells {
        if {[regexp -- $pattern [get_property NAME $cell]]} {incr count}
    }
    return $count
}

proc hap_v5_p5_input_partition::hard_signature {cells} {
    return [dict create \
        dsp [hap_v5_floorplan::count_ref $cells DSP48E2] \
        uram [hap_v5_floorplan::count_ref $cells URAM288] \
        ramb36 [hap_v5_floorplan::count_ref $cells RAMB36E2] \
        ramb18 [hap_v5_floorplan::count_ref $cells RAMB18E2]]
}

proc hap_v5_p5_input_partition::require_hard_signature {label signature \
        dsp uram ramb36 ramb18} {
    foreach {key expected} [list dsp $dsp uram $uram ramb36 $ramb36 \
            ramb18 $ramb18] {
        if {[dict get $signature $key] != $expected} {
            error "P5 $label $key signature mismatch: expected=$expected actual=[dict get $signature $key]"
        }
    }
}

proc hap_v5_p5_input_partition::discover {base_plan} {
    variable contract
    if {[dict get $base_plan contract_variant] ne \
            "P2_COHORT16_COL2_12_2"} {
        error "P5 requires the P3 P2_COHORT16_COL2_12_2 base plan"
    }
    set rtl_variant [dict get $base_plan rtl_resource_variant]
    if {$rtl_variant ni {P14_LEGACY P16_NOCLIP}} {
        error "P5 unsupported RTL resource variant: $rtl_variant"
    }
    set expected_slr1_dsp [expr {
        $rtl_variant eq "P16_NOCLIP" ? 1777 : 1781}]
    set expected_total_dsp [expr {
        $rtl_variant eq "P16_NOCLIP" ? 5449 : 5453}]
    foreach {key expected} [list planned_slr0_dsp 1862 \
            planned_slr1_dsp $expected_slr1_dsp planned_slr2_dsp 1810 \
            total_dsp $expected_total_dsp total_uram 752] {
        if {[dict get $base_plan $key] != $expected} {
            error "P5 base-plan drift: $key expected=$expected actual=[dict get $base_plan $key]"
        }
    }

    set roots [hap_v5_floorplan::module_cells \
        hap_mlp_input_frontend16_compact_cache]
    hap_v5_p5_input_partition::require_count input_frontend $roots 1
    set root [lindex $roots 0]
    set root_name [get_property NAME $root]
    set root_primitives [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants $root]]
    if {[llength $root_primitives] == 0} {
        error "P5 input-frontend primitive selector is empty"
    }

    set quantizers [hap_v5_p5_input_partition::module_children $root \
        hap_robust_a8_quantizer]
    set caches [hap_v5_p5_input_partition::module_children $root \
        hap_activation_cache_8row]
    set hadamards [hap_v5_p5_input_partition::module_children $root \
        hap_mlp_hadamard32_s24_fold4]
    hap_v5_p5_input_partition::require_count input_quantizers $quantizers 4
    hap_v5_p5_input_partition::require_count input_caches $caches 2
    hap_v5_p5_input_partition::require_count input_hadamard $hadamards 1

    set quantizer_by_name [dict create]
    foreach quantizer $quantizers {
        dict set quantizer_by_name [get_property NAME $quantizer] $quantizer
    }
    set cache_by_name [dict create]
    foreach cache $caches {
        dict set cache_by_name [get_property NAME $cache] $cache
    }
    set ordered_quantizers {}
    for {set q 0} {$q < 4} {incr q} {
        set name [format {%s/g_quant[%d].u_quantizer} $root_name $q]
        if {![dict exists $quantizer_by_name $name]} {
            error "P5 exact input quantizer hierarchy is missing: $name"
        }
        lappend ordered_quantizers [dict get $quantizer_by_name $name]
    }
    set ordered_caches {}
    for {set cache 0} {$cache < 2} {incr cache} {
        set name [format {%s/u_cache%d} $root_name $cache]
        if {![dict exists $cache_by_name $name]} {
            error "P5 exact input cache hierarchy is missing: $name"
        }
        lappend ordered_caches [dict get $cache_by_name $name]
    }

    set quantizer_primitives {}
    foreach quantizer $ordered_quantizers {
        set cells [hap_v5_floorplan::pblockable_primitives \
            [hap_v5_floorplan::primitive_descendants $quantizer]]
        if {[llength $cells] == 0} {error "P5 input quantizer is empty"}
        lappend quantizer_primitives $cells
    }
    set cache_primitives {}
    foreach cache $ordered_caches {
        set cells [hap_v5_floorplan::pblockable_primitives \
            [hap_v5_floorplan::primitive_descendants $cache]]
        if {[llength $cells] == 0} {error "P5 input cache is empty"}
        lappend cache_primitives $cells
    }
    set hadamard_primitives [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants [lindex $hadamards 0]]]
    if {[llength $hadamard_primitives] == 0} {
        error "P5 input Hadamard primitive selector is empty"
    }

    set completed_rows {}
    set completed_u8 0
    set completed_meta 0
    set completed_logic 0
    for {set row 0} {$row < 16} {incr row} {
        set record [hap_v5_p5_input_partition::row_storage \
            $root_primitives $root_name $row]
        lappend completed_rows [dict get $record cells]
        incr completed_u8 [dict get $record u8]
        incr completed_meta [dict get $record meta]
        incr completed_logic [dict get $record logic]
    }

    set half0_completed {}
    set half1_completed {}
    for {set row 0} {$row < 8} {incr row} {
        set half0_completed [concat $half0_completed \
            [lindex $completed_rows $row]]
        set half1_completed [concat $half1_completed \
            [lindex $completed_rows [expr {$row + 8}]]]
    }
    set half0_completed [lsort -dictionary -unique $half0_completed]
    set half1_completed [lsort -dictionary -unique $half1_completed]

    set half0 [hap_v5_floorplan::list_union \
        [lindex $quantizer_primitives 0] [lindex $quantizer_primitives 1] \
        [lindex $cache_primitives 0] $half0_completed]
    set half1 [hap_v5_floorplan::list_union \
        [lindex $quantizer_primitives 2] [lindex $quantizer_primitives 3] \
        [lindex $cache_primitives 1] $half1_completed]
    if {[llength [hap_v5_floorplan::list_intersection $half0 $half1]] != 0} {
        error "P5 input half selectors overlap"
    }
    set outer [hap_v5_floorplan::list_union $half0 $half1]
    set center [hap_v5_floorplan::list_subtract $root_primitives $outer]
    if {[llength $center] == 0 ||
        [llength [hap_v5_floorplan::list_union $outer $center]] !=
            [llength $root_primitives]} {
        error "P5 input frontend partition is incomplete"
    }

    set input_capture_pattern [format \
        {^%s/input_buffer_row_r_reg\[[0-9]+\]\[} $root_name]
    set input_capture_ff [hap_v5_p5_input_partition::count_name_pattern \
        $center $input_capture_pattern]
    set capture_leaf_pattern [format \
        {^%s/g_input_capture\[[0-9]+\]\.u_input_capture_enable$} $root_name]
    set capture_leaf_count [hap_v5_p5_input_partition::count_name_pattern \
        $center $capture_leaf_pattern]
    if {$input_capture_ff < 12288 || $capture_leaf_count < 48} {
        error "P5 central capture signature mismatch: ff=$input_capture_ff leaves=$capture_leaf_count"
    }
    if {[llength [hap_v5_floorplan::list_intersection \
            $hadamard_primitives $center]] != [llength $hadamard_primitives]} {
        error "P5 unique input Hadamard is not wholly central"
    }

    set half0_hard [hap_v5_p5_input_partition::hard_signature $half0]
    set half1_hard [hap_v5_p5_input_partition::hard_signature $half1]
    set center_hard [hap_v5_p5_input_partition::hard_signature $center]
    set root_hard [hap_v5_p5_input_partition::hard_signature $root_primitives]
    hap_v5_p5_input_partition::require_hard_signature \
        input_half0 $half0_hard 0 0 31 4
    hap_v5_p5_input_partition::require_hard_signature \
        input_half1 $half1_hard 0 0 31 4
    hap_v5_p5_input_partition::require_hard_signature \
        input_center $center_hard 8 0 0 0
    hap_v5_p5_input_partition::require_hard_signature \
        input_frontend $root_hard 8 0 62 8

    set canonical_union {}
    foreach spec [hap_v5_floorplan::pblock_specs $base_plan \
            P2_COHORT16_COL2_12_2] {
        set canonical_union [hap_v5_floorplan::list_union $canonical_union \
            [hap_v5_floorplan::pblockable_primitives \
                [dict get $base_plan [dict get $spec key]]]]
    }
    if {[llength [hap_v5_floorplan::list_intersection \
            $outer $canonical_union]] != 0} {
        error "P5 outer input halves overlap the canonical P3 pblocks"
    }
    set center_canonical_overlap [hap_v5_floorplan::list_intersection \
        $center [dict get $base_plan center_primitives]]
    set center_base_extras [hap_v5_floorplan::list_subtract \
        $center [dict get $base_plan center_primitives]]
    if {[hap_v5_floorplan::count_ref $center_canonical_overlap DSP48E2] != 8 ||
        [llength $center_canonical_overlap] != 8} {
        error "P5 central/canonical overlap must be exactly the eight Hadamard DSPs"
    }

    return [dict create contract $contract root $root root_name $root_name \
        root_primitives $root_primitives quantizers $ordered_quantizers \
        caches $ordered_caches hadamard [lindex $hadamards 0] \
        quantizer_primitives $quantizer_primitives \
        cache_primitives $cache_primitives \
        hadamard_primitives $hadamard_primitives \
        completed_rows $completed_rows completed_u8_ff $completed_u8 \
        completed_meta_ff $completed_meta completed_logic $completed_logic \
        half0_completed $half0_completed half1_completed $half1_completed \
        half0_primitives $half0 half1_primitives $half1 \
        center_primitives $center input_capture_ff $input_capture_ff \
        capture_leaf_count $capture_leaf_count \
        center_canonical_overlap $center_canonical_overlap \
        center_base_extras $center_base_extras \
        half0_hard $half0_hard half1_hard $half1_hard \
        center_hard $center_hard root_hard $root_hard]
}

proc hap_v5_p5_input_partition::create_hard_pblock {name target cells} {
    if {[llength $cells] == 0} {error "P5 pblock is empty: $name"}
    if {[llength [get_pblocks -quiet $name]] != 0} {
        error "P5 pblock already exists: $name"
    }
    create_pblock $name
    add_cells_to_pblock [get_pblocks $name] $cells
    resize_pblock [get_pblocks $name] -add [list SLR${target}]
    set_property IS_SOFT false [get_pblocks $name]
    set_property CONTAIN_ROUTING false [get_pblocks $name]
    set_property EXCLUDE_PLACEMENT false [get_pblocks $name]
}

proc hap_v5_p5_input_partition::apply {plan} {
    variable half0_pblock
    variable half1_pblock
    variable center_pblock
    if {[dict get $plan contract] ne "P5_INPUT_HALF_LOCAL_8_8"} {
        error "P5 input plan contract mismatch"
    }
    set center [get_pblocks -quiet $center_pblock]
    if {[llength $center] != 1} {
        error "P5 canonical center pblock is not unique: $center_pblock"
    }
    hap_v5_p5_input_partition::create_hard_pblock $half0_pblock 0 \
        [dict get $plan half0_primitives]
    hap_v5_p5_input_partition::create_hard_pblock $half1_pblock 2 \
        [dict get $plan half1_primitives]
    add_cells_to_pblock $center [dict get $plan center_primitives]
}

proc hap_v5_p5_input_partition::pblock_target_ok {pblock target} {
    set target_name SLR${target}
    set target_seen 0
    set foreign_seen 0
    foreach range [get_property GRID_RANGES $pblock] {
        foreach slr [regexp -all -inline {SLR[0-2]} $range] {
            if {$slr eq $target_name} {
                set target_seen 1
            } else {
                set foreign_seen 1
            }
        }
    }
    return [expr {$target_seen && !$foreign_seen}]
}

proc hap_v5_p5_input_partition::audit_outer {name target expected \
        require_placed} {
    set pblock [get_pblocks -quiet $name]
    if {[llength $pblock] != 1} {error "P5 outer pblock is not unique: $name"}
    set pblock [lindex $pblock 0]
    if {![hap_v5_floorplan::property_is_false $pblock IS_SOFT] ||
        ![hap_v5_floorplan::property_is_false $pblock CONTAIN_ROUTING] ||
        ![hap_v5_floorplan::property_is_false $pblock EXCLUDE_PLACEMENT] ||
        ![hap_v5_p5_input_partition::pblock_target_ok $pblock $target]} {
        error "P5 outer pblock property/target mismatch: $name"
    }
    set members [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::expanded_pblock_primitives $pblock]]
    set missing [hap_v5_floorplan::list_subtract $expected $members]
    set extras [hap_v5_floorplan::list_subtract $members $expected]
    if {[llength $missing] != 0 || (!$require_placed && [llength $extras] != 0)} {
        error "P5 outer pblock membership mismatch: $name missing=[llength $missing] extras=[llength $extras]"
    }
    set expected_hard [hap_v5_p5_input_partition::hard_signature $expected]
    set member_hard [hap_v5_p5_input_partition::hard_signature $members]
    foreach key {dsp uram ramb36 ramb18} {
        if {[dict get $expected_hard $key] != [dict get $member_hard $key]} {
            error "P5 outer pblock hard-resource drift: $name key=$key"
        }
    }
    set wrong 0
    if {$require_placed} {
        set placement [hap_v5_floorplan::wrong_slr_audit $members $target]
        set wrong [dict get $placement wrong]
        if {$wrong != 0 || [dict get $placement direct_slr_empty] != 0} {
            error "P5 outer pblock has wrong/unresolved placement: $name"
        }
    }
    return [dict create name $name target $target \
        expected [llength $expected] members [llength $members] \
        missing [llength $missing] extras [llength $extras] wrong $wrong \
        hard $member_hard]
}

proc hap_v5_p5_input_partition::audit {plan require_placed} {
    variable half0_pblock
    variable half1_pblock
    variable center_pblock
    if {$require_placed != 0 && $require_placed != 1} {
        error "P5 require_placed must be 0 or 1"
    }
    set half0 [hap_v5_p5_input_partition::audit_outer $half0_pblock 0 \
        [dict get $plan half0_primitives] $require_placed]
    set half1 [hap_v5_p5_input_partition::audit_outer $half1_pblock 2 \
        [dict get $plan half1_primitives] $require_placed]

    set center_pb [get_pblocks -quiet $center_pblock]
    if {[llength $center_pb] != 1 ||
        ![hap_v5_p5_input_partition::pblock_target_ok \
            [lindex $center_pb 0] 1]} {
        error "P5 canonical center pblock target mismatch"
    }
    set center_members [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::expanded_pblock_primitives [lindex $center_pb 0]]]
    set center_missing [hap_v5_floorplan::list_subtract \
        [dict get $plan center_primitives] $center_members]
    set center_outer_overlap [hap_v5_floorplan::list_intersection \
        $center_members [hap_v5_floorplan::list_union \
            [dict get $plan half0_primitives] \
            [dict get $plan half1_primitives]]]
    if {[llength $center_missing] != 0 ||
        [llength $center_outer_overlap] != 0} {
        error "P5 center membership mismatch: missing=[llength $center_missing] outer_overlap=[llength $center_outer_overlap]"
    }
    set center_wrong 0
    if {$require_placed} {
        set placement [hap_v5_floorplan::wrong_slr_audit \
            [dict get $plan center_primitives] 1]
        set center_wrong [dict get $placement wrong]
        if {$center_wrong != 0 || [dict get $placement direct_slr_empty] != 0} {
            error "P5 central input partition has wrong/unresolved placement"
        }
    }
    return [dict create ok 1 require_placed $require_placed \
        pblock_count 2 center_pblock $center_pblock half0 $half0 half1 $half1 \
        center_expected [llength [dict get $plan center_primitives]] \
        center_missing [llength $center_missing] \
        center_outer_overlap [llength $center_outer_overlap] \
        center_wrong $center_wrong outer_wrong \
        [expr {[dict get $half0 wrong] + [dict get $half1 wrong]}] \
        outer_extras [expr {[dict get $half0 extras] + \
            [dict get $half1 extras]}]]
}

proc hap_v5_p5_input_partition::write_plan {plan path status} {
    set fp [open $path w]
    foreach {key value} [list contract [dict get $plan contract] \
        root_name [dict get $plan root_name] \
        root_primitives [llength [dict get $plan root_primitives]] \
        quantizer_count [llength [dict get $plan quantizers]] \
        cache_count [llength [dict get $plan caches]] hadamard_count 1 \
        completed_u8_ff [dict get $plan completed_u8_ff] \
        completed_meta_ff [dict get $plan completed_meta_ff] \
        completed_logic [dict get $plan completed_logic] \
        input_capture_ff [dict get $plan input_capture_ff] \
        capture_leaf_count [dict get $plan capture_leaf_count] \
        half0_primitives [llength [dict get $plan half0_primitives]] \
        half1_primitives [llength [dict get $plan half1_primitives]] \
        center_primitives [llength [dict get $plan center_primitives]] \
        center_base_extras [llength [dict get $plan center_base_extras]] \
        center_canonical_overlap \
            [llength [dict get $plan center_canonical_overlap]] \
        half0_hard [dict get $plan half0_hard] \
        half1_hard [dict get $plan half1_hard] \
        center_hard [dict get $plan center_hard] \
        root_hard [dict get $plan root_hard] status $status] {
        puts $fp "$key=$value"
    }
    close $fp
}

proc hap_v5_p5_input_partition::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok require_placed pblock_count center_pblock center_expected
            center_missing center_outer_overlap center_wrong outer_wrong
            outer_extras} {
        puts $fp "$key=[dict get $audit $key]"
    }
    foreach half {half0 half1} {
        set record [dict get $audit $half]
        foreach key {name target expected members missing extras wrong hard} {
            puts $fp "${half}_${key}=[dict get $record $key]"
        }
    }
    puts $fp "status=$status"
    close $fp
}
