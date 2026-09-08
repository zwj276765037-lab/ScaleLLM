# Read-only P9 physical map for the P12 Hadamard-locality decision.  This
# script does not alter pblocks, run implementation, or write a checkpoint.

set map_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P12_MAP_DCP)]
set out [file normalize $::env(HAP_P12_MAP_DIR)]
set input_sha [file normalize $::env(HAP_P12_MAP_INPUT_SHA)]
set expected_input_sha $::env(HAP_P12_MAP_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P12_MAP_DCP_SHA256)
set placement_output_sha [file normalize $::env(HAP_P12_MAP_PLACE_OUTPUT_SHA)]
set expected_placement_output_sha $::env(HAP_P12_MAP_PLACE_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P12_MAP_P10_PROC_LIB)]
set selector_lib [file normalize $::env(HAP_P12_MAP_SELECTOR_LIB)]
set expected_launcher [file normalize $::env(HAP_P12_MAP_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p12_map_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p12_map_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p12_map_name_set {cells} {
    set result [dict create]
    foreach name [get_property NAME $cells] {dict set result $name 1}
    return $result
}

proc hap_p12_map_increment_signature {array_name prefix ref} {
    upvar 1 $array_name counts
    incr counts(${prefix}_total)
    if {[string match LUT* $ref]} {incr counts(${prefix}_lut)
    } elseif {[string match FD* $ref]} {incr counts(${prefix}_ff)
    } elseif {$ref eq "DSP48E2"} {incr counts(${prefix}_dsp)
    } elseif {$ref eq "URAM288"} {incr counts(${prefix}_uram)
    } elseif {$ref in {RAMB36E2 RAMB18E2}} {incr counts(${prefix}_bram)}
}

proc hap_p12_map_signature {cells} {
    array set counts {total 0 lut 0 ff 0 dsp 0 uram 0 bram 0}
    foreach ref [get_property REF_NAME $cells] {
        incr counts(total)
        if {[string match LUT* $ref]} {incr counts(lut)
        } elseif {[string match FD* $ref]} {incr counts(ff)
        } elseif {$ref eq "DSP48E2"} {incr counts(dsp)
        } elseif {$ref eq "URAM288"} {incr counts(uram)
        } elseif {$ref in {RAMB36E2 RAMB18E2}} {incr counts(bram)}
    }
    return [dict create total $counts(total) lut $counts(lut) \
        ff $counts(ff) dsp $counts(dsp) uram $counts(uram) \
        bram $counts(bram)]
}

proc hap_p12_map_percent {used capacity} {
    if {$capacity == 0} {
        return [expr {$used == 0 ? "0.000" : "INF"}]
    }
    return [format %.3f [expr {100.0 * $used / $capacity}]]
}

if {![string match "2025.2*" [version -short]]} {
    error "P12 capacity map requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P12 capacity map requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P12 capacity map requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_placement_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P12 capacity map received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $placement_output_sha $p10_proc_lib \
        $selector_lib $map_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P12 capacity input absent from manifest: $required"
    }
}
set placement_outputs [hap_p10_verify_manifest $placement_output_sha -1 \
    $expected_placement_output_sha]
set placement_dir [file dirname $placement_output_sha]
set placement_summary_path [file join $placement_dir summary.txt]
set placement_launcher_path [file join $placement_dir launcher_status.txt]
foreach required [list $placement_summary_path $placement_launcher_path $dcp] {
    if {![dict exists $placement_outputs [file normalize $required]]} {
        error "Mission 0124 output manifest is incomplete: $required"
    }
}
set placement [hap_p10_parse_kv $placement_summary_path \
    "Mission 0124 summary"]
foreach {key expected} {
    stage V5_P10_P9_POST_PLACE_FAST_GATE
    failure_stage post_place_fast_gate
    acceptance_evidence 0
    route_eligible 0
    diagnostic_checkpoint_written 1
    provenance_verified 1
    pre_place_verified 1
    p9_quantizer3_contract P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
    dsp48e2 5453
    uram288 752
    unplaced_primitives 0
    wrong_slr_primitives 0
    pre_place_drc_errors 0
    post_place_drc_errors 0
    congestion_level5_or_higher_windows 16
    congestion_level6_or_higher_windows 5
    resource_ok 1
    structure_ok 1
    placement_ok 1
    optimizer_extras_ok 1
    status FAIL
} {
    hap_p12_map_require_kv $placement $key $expected \
        "Mission 0124 summary"
}
set placement_launcher [hap_p10_parse_kv $placement_launcher_path \
    "Mission 0124 launcher"]
foreach {key expected} {
    status FAIL
    acceptance_evidence 0
    route_eligible 0
    final_exit_code 1
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    checkpoint_written 0
    implementation_commands_requested 1
    bitstream_generated 0
} {
    hap_p12_map_require_kv $placement_launcher $key $expected \
        "Mission 0124 launcher"
}
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P12 capacity source DCP identity mismatch"
}

open_checkpoint $dcp
source $selector_lib
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P12 capacity top/part mismatch: $top/$part"
}
hap_p12_map_require_count pblocks [get_pblocks -quiet] 26
set all_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
hap_p12_map_require_count dsp48e2 \
    [filter $all_primitives {REF_NAME == DSP48E2}] 5453
hap_p12_map_require_count uram288 \
    [filter $all_primitives {REF_NAME == URAM288}] 752

set hadamard_roots [hap_v5_floorplan::module_cells \
    hap_mlp_hadamard32_s32_norm_stream]
hap_p12_map_require_count swiglu_hadamard_roots $hadamard_roots 1
set hadamard_cells [hap_v5_floorplan::pblockable_primitives \
    [hap_v5_floorplan::primitive_descendants [lindex $hadamard_roots 0]]]

set gather_roots [get_cells -quiet -hierarchical -filter {
    NAME == u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_gather}]
hap_p12_map_require_count mlp_gate_gather_roots $gather_roots 1
set gather_cells [hap_v5_floorplan::pblockable_primitives \
    [hap_v5_floorplan::primitive_descendants [lindex $gather_roots 0]]]

set group_cells [dict create hadamard $hadamard_cells gather $gather_cells]
foreach {label root_name} {
    attn_r1 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7
    attn_r2 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11
} {
    set roots [get_cells -quiet -hierarchical -filter "NAME == $root_name"]
    hap_p12_map_require_count $label $roots 1
    dict set group_cells $label [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants [lindex $roots 0]]]
}
set quantizer_roots [lsort -dictionary [hap_v5_floorplan::module_cells \
    hap_mlp_robust_a8_quantizer_s35]]
hap_p12_map_require_count swiglu_quantizer_roots $quantizer_roots 4
foreach root $quantizer_roots {
    set name [get_property NAME $root]
    if {![regexp {/g_quantizer\[([0-3])\]\.u_quantizer$} $name -> index]} {
        error "unexpected P12 quantizer hierarchy: $name"
    }
    dict set group_cells q$index [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants $root]]
}

set groups {hadamard gather q0 q1 q2 q3 attn_r1 attn_r2}
set group_sets [dict create]
set signatures [dict create]
set signature_handle [open [file join $out group_signatures.tsv] w]
puts $signature_handle "group\ttotal\tlut\tff\tdsp\turam\tbram"
foreach group $groups {
    set cells [dict get $group_cells $group]
    set signature [hap_p12_map_signature $cells]
    dict set signatures $group $signature
    dict set group_sets $group [hap_p12_map_name_set $cells]
    puts $signature_handle [join [list $group \
        [dict get $signature total] [dict get $signature lut] \
        [dict get $signature ff] [dict get $signature dsp] \
        [dict get $signature uram] [dict get $signature bram]] "\t"]
}
close $signature_handle

# DSP cells are not returned by get_cells -of_objects on every UltraScale+
# DSP site in this placed checkpoint.  Build their clock-region ownership
# directly from each placed DSP so candidate capacity does not undercount the
# existing 1,781 SLR1 DSPs.
set direct_dsp_counts [dict create]
foreach cell [filter $all_primitives {REF_NAME == DSP48E2}] {
    set sites [get_sites -quiet -of_objects $cell]
    if {[llength $sites] != 1} {
        error "P12 capacity map found unplaced DSP: [get_property NAME $cell]"
    }
    set regions [get_clock_regions -quiet -of_objects $sites]
    if {[llength $regions] != 1} {
        error "P12 capacity map found ambiguous DSP clock region: [get_property NAME $cell]"
    }
    set region_name [get_property NAME $regions]
    if {![regexp {^X[0-5]Y[5-9]$} $region_name]} {continue}
    dict incr direct_dsp_counts "$region_name|occupied"
    set cell_name [get_property NAME $cell]
    foreach group $groups {
        if {[dict exists [dict get $group_sets $group] $cell_name]} {
            dict incr direct_dsp_counts "$region_name|$group"
        }
    }
}

set hadamard_signature [dict get $signatures hadamard]
foreach {key expected} {
    lut 9263
    ff 4656
    dsp 64
    uram 0
    bram 0
} {
    if {[dict get $hadamard_signature $key] != $expected} {
        error "P12 Hadamard signature mismatch: $key expected=$expected actual=[dict get $hadamard_signature $key]"
    }
}
set gather_signature [dict get $signatures gather]
foreach {key expected} {lut 6403 dsp 0 uram 0 bram 96} {
    if {[dict get $gather_signature $key] != $expected} {
        error "P12 gather signature mismatch: $key expected=$expected actual=[dict get $gather_signature $key]"
    }
}

set slr1 [get_slrs -quiet SLR1]
hap_p12_map_require_count slr1 $slr1 1
set slr1_clock_regions [lsort -dictionary -unique \
    [get_clock_regions -quiet -of_objects $slr1]]
if {[llength $slr1_clock_regions] == 0} {
    foreach region [get_clock_regions -quiet] {
        set region_slrs [get_slrs -quiet -of_objects \
            [get_sites -quiet -of_objects $region]]
        if {[llength $region_slrs] == 1 &&
            [get_property NAME $region_slrs] eq "SLR1"} {
            lappend slr1_clock_regions $region
        }
    }
    set slr1_clock_regions [lsort -dictionary -unique $slr1_clock_regions]
}
hap_p12_map_require_count slr1_clock_regions $slr1_clock_regions 30

set columns {total lut ff dsp uram bram}
set report_groups [concat occupied $groups]
set cr_values [dict create]
set cr_handle [open [file join $out clock_region_groups.tsv] w]
set header {clock_region slice_sites lut_capacity ff_capacity dsp_sites uram_sites bram18_sites}
foreach group $report_groups {
    foreach column $columns {lappend header ${group}_${column}}
}
puts $cr_handle [join $header "\t"]
foreach region $slr1_clock_regions {
    set region_name [get_property NAME $region]
    set sites [get_sites -quiet -of_objects $region]
    array set capacity {slice 0 lut 0 ff 0 dsp 0 uram 0 bram 0}
    foreach site_type [get_property SITE_TYPE $sites] {
        if {[string match SLICE* $site_type]} {incr capacity(slice)
        } elseif {$site_type eq "DSP48E2"} {incr capacity(dsp)
        } elseif {$site_type eq "URAM288"} {incr capacity(uram)
        } elseif {[string match RAMB18* $site_type]} {incr capacity(bram)}
    }
    set capacity(lut) [expr {$capacity(slice) * 8}]
    set capacity(ff) [expr {$capacity(slice) * 16}]
    foreach key {lut ff dsp uram bram} {
        dict set cr_values $region_name capacity_$key $capacity($key)
    }

    set direct [get_cells -quiet -of_objects $sites]
    set via_bels [get_cells -quiet -of_objects \
        [get_bels -quiet -of_objects $sites]]
    set names [lsort -dictionary -unique [concat \
        [get_property NAME $direct] [get_property NAME $via_bels]]]
    set cells [get_cells -quiet $names -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
        REF_NAME != GND && REF_NAME != VCC}]
    unset -nocomplain counts
    foreach group $report_groups {
        foreach column $columns {set counts(${group}_${column}) 0}
    }
    foreach name [get_property NAME $cells] ref [get_property REF_NAME $cells] {
        hap_p12_map_increment_signature counts occupied $ref
        foreach group $groups {
            if {[dict exists [dict get $group_sets $group] $name]} {
                hap_p12_map_increment_signature counts $group $ref
            }
        }
    }
    foreach group $report_groups {
        set counts(${group}_dsp) 0
        if {[dict exists $direct_dsp_counts "$region_name|$group"]} {
            set counts(${group}_dsp) \
                [dict get $direct_dsp_counts "$region_name|$group"]
        }
    }
    set row [list $region_name $capacity(slice) $capacity(lut) \
        $capacity(ff) $capacity(dsp) $capacity(uram) $capacity(bram)]
    foreach group $report_groups {
        foreach column $columns {
            lappend row $counts(${group}_${column})
            dict set cr_values $region_name ${group}_$column \
                $counts(${group}_${column})
        }
    }
    puts $cr_handle [join $row "\t"]
}
close $cr_handle

set candidates {
    west_lower 0 1 5 6
    west_upper 0 1 7 9
    west_full 0 1 5 9
    center_lower 2 3 5 6
    center_upper 2 3 7 9
    center_full 2 3 5 9
    east_lower 4 5 5 6
    east_upper 4 5 7 9
    east_full 4 5 5 9
}
set candidate_handle [open [file join $out hadamard_candidates.tsv] w]
puts $candidate_handle [join {
    candidate grid_range region_count lut_capacity ff_capacity dsp_capacity
    occupied_lut occupied_ff occupied_dsp existing_hadamard_lut
    existing_hadamard_ff existing_hadamard_dsp projected_lut projected_ff
    projected_dsp projected_lut_percent projected_ff_percent
    projected_dsp_percent gather_lut q012_lut q3_lut attn_r1_lut attn_r2_lut
} "\t"]
set candidate_count 0
foreach {label x0 x1 y0 y1} $candidates {
    incr candidate_count
    array set sums {
        capacity_lut 0 capacity_ff 0 capacity_dsp 0
        occupied_lut 0 occupied_ff 0 occupied_dsp 0
        hadamard_lut 0 hadamard_ff 0 hadamard_dsp 0
        gather_lut 0 q0_lut 0 q1_lut 0 q2_lut 0 q3_lut 0
        attn_r1_lut 0 attn_r2_lut 0
    }
    set region_count 0
    for {set x $x0} {$x <= $x1} {incr x} {
        for {set y $y0} {$y <= $y1} {incr y} {
            incr region_count
            set region X${x}Y${y}
            if {![dict exists $cr_values $region]} {
                error "P12 candidate references missing clock region: $region"
            }
            foreach key [array names sums] {
                if {[dict exists $cr_values $region $key]} {
                    incr sums($key) [dict get $cr_values $region $key]
                }
            }
        }
    }
    set projected_lut [expr {$sums(occupied_lut) -
        $sums(hadamard_lut) + [dict get $hadamard_signature lut]}]
    set projected_ff [expr {$sums(occupied_ff) -
        $sums(hadamard_ff) + [dict get $hadamard_signature ff]}]
    set projected_dsp [expr {$sums(occupied_dsp) -
        $sums(hadamard_dsp) + [dict get $hadamard_signature dsp]}]
    set grid_range CLOCKREGION_X${x0}Y${y0}:CLOCKREGION_X${x1}Y${y1}
    puts $candidate_handle [join [list $label $grid_range $region_count \
        $sums(capacity_lut) $sums(capacity_ff) $sums(capacity_dsp) \
        $sums(occupied_lut) $sums(occupied_ff) $sums(occupied_dsp) \
        $sums(hadamard_lut) $sums(hadamard_ff) $sums(hadamard_dsp) \
        $projected_lut $projected_ff $projected_dsp \
        [hap_p12_map_percent $projected_lut $sums(capacity_lut)] \
        [hap_p12_map_percent $projected_ff $sums(capacity_ff)] \
        [hap_p12_map_percent $projected_dsp $sums(capacity_dsp)] \
        $sums(gather_lut) \
        [expr {$sums(q0_lut) + $sums(q1_lut) + $sums(q2_lut)}] \
        $sums(q3_lut) $sums(attn_r1_lut) $sums(attn_r2_lut)] "\t"]
}
close $candidate_handle

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P12_HADAMARD_CAPACITY_MAP \
        evidence_class READ_ONLY_REJECTED_P9_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        pblock_count [llength [get_pblocks -quiet]] dsp48e2 5453 uram288 752 \
        source_level5_or_higher_windows 16 \
        source_level6_or_higher_windows 5 \
        slr1_clock_regions_profiled [llength $slr1_clock_regions] \
        candidate_rectangles_profiled $candidate_count \
        hadamard_primitives [dict get $hadamard_signature total] \
        hadamard_lut [dict get $hadamard_signature lut] \
        hadamard_ff [dict get $hadamard_signature ff] \
        hadamard_dsp [dict get $hadamard_signature dsp] \
        gather_primitives [dict get $gather_signature total] \
        gather_lut [dict get $gather_signature lut] \
        gather_ff [dict get $gather_signature ff] \
        gather_bram [dict get $gather_signature bram] \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 route_eligible 0 \
        status V5_P12_HADAMARD_CAPACITY_MAP_PASS] {
    puts $summary "$key=$value"
}
close $summary
close_design

exit 0
