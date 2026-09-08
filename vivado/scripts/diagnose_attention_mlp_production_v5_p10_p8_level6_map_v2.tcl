# Read-only map of the seven Level-6 windows in the rejected P8 placement.

set map_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P8_LEVEL6_DCP)]
set out [file normalize $::env(HAP_P8_LEVEL6_DIR)]
set input_sha [file normalize $::env(HAP_P8_LEVEL6_INPUT_SHA)]
set expected_input_sha $::env(HAP_P8_LEVEL6_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P8_LEVEL6_DCP_SHA256)
set diagnosis_output_sha [file normalize $::env(HAP_P8_LEVEL6_DIAG_OUTPUT_SHA)]
set expected_diagnosis_output_sha $::env(HAP_P8_LEVEL6_DIAG_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P8_LEVEL6_P10_PROC_LIB)]
set selector_lib [file normalize $::env(HAP_P8_LEVEL6_SELECTOR_LIB)]
set expected_launcher [file normalize $::env(HAP_P8_LEVEL6_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p8_level6_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p8_level6_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p8_level6_slr_index {value} {
    if {[regexp {([0-2])$} $value -> index]} {return $index}
    return 3
}

proc hap_p8_level6_bbox {cells} {
    set sites [get_sites -quiet -of_objects $cells]
    set tiles [get_tiles -quiet -of_objects $sites]
    if {[llength $tiles] == 0} {return {NA NA NA NA}}
    set xs [get_property GRID_POINT_X $tiles]
    set ys [get_property GRID_POINT_Y $tiles]
    set min_x [lindex $xs 0]
    set max_x $min_x
    set min_y [lindex $ys 0]
    set max_y $min_y
    foreach x $xs y $ys {
        if {$x < $min_x} {set min_x $x}
        if {$x > $max_x} {set max_x $x}
        if {$y < $min_y} {set min_y $y}
        if {$y > $max_y} {set max_y $y}
    }
    return [list $min_x $min_y $max_x $max_y]
}

proc hap_p8_level6_resource_row {handle label cells} {
    if {[llength $cells] == 0} {error "empty P8 Level-6 group: $label"}
    set total {0 0 0 0}
    set lut {0 0 0 0}
    set ff {0 0 0 0}
    set dsp {0 0 0 0}
    set uram {0 0 0 0}
    set bram {0 0 0 0}
    foreach ref [get_property REF_NAME $cells] \
            slr_value [get_property SLR_INDEX $cells] {
        set slr [hap_p8_level6_slr_index $slr_value]
        lset total $slr [expr {[lindex $total $slr] + 1}]
        if {[string match LUT* $ref]} {
            lset lut $slr [expr {[lindex $lut $slr] + 1}]
        } elseif {[string match FD* $ref]} {
            lset ff $slr [expr {[lindex $ff $slr] + 1}]
        } elseif {$ref eq "DSP48E2"} {
            lset dsp $slr [expr {[lindex $dsp $slr] + 1}]
        } elseif {$ref eq "URAM288"} {
            lset uram $slr [expr {[lindex $uram $slr] + 1}]
        } elseif {$ref in {RAMB36E2 RAMB18E2}} {
            lset bram $slr [expr {[lindex $bram $slr] + 1}]
        }
    }
    puts $handle [join [list $label $total $lut $ff $dsp $uram $bram \
        [hap_p8_level6_bbox $cells]] "\t"]
}

proc hap_p8_level6_window_cells {lower_name upper_name} {
    set lower [get_tiles -quiet $lower_name]
    set upper [get_tiles -quiet $upper_name]
    hap_p8_level6_require_count "lower tile $lower_name" $lower 1
    hap_p8_level6_require_count "upper tile $upper_name" $upper 1
    set x0 [get_property GRID_POINT_X $lower]
    set y0 [get_property GRID_POINT_Y $lower]
    set x1 [get_property GRID_POINT_X $upper]
    set y1 [get_property GRID_POINT_Y $upper]
    set tiles [get_tiles -quiet -filter [format \
        {GRID_POINT_X >= %d && GRID_POINT_X <= %d && GRID_POINT_Y >= %d && GRID_POINT_Y <= %d} \
        [expr {min($x0,$x1)}] [expr {max($x0,$x1)}] \
        [expr {min($y0,$y1)}] [expr {max($y0,$y1)}]]]
    set sites [get_sites -quiet -of_objects $tiles]
    set direct [get_cells -quiet -of_objects $sites]
    set via_bels [get_cells -quiet -of_objects \
        [get_bels -quiet -of_objects $sites]]
    set names [lsort -dictionary -unique [concat \
        [get_property NAME $direct] [get_property NAME $via_bels]]]
    set cells [get_cells -quiet $names -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
        REF_NAME != GND && REF_NAME != VCC}]
    if {[llength $cells] == 0} {
        error "empty P8 Level-6 window: $lower_name:$upper_name"
    }
    return $cells
}

proc hap_p8_level6_category {name} {
    if {[regexp {/u_postprocess_store/g_row_bank\[([0-9]+)\]\.u_bank/} \
            $name -> bank]} {
        if {$bank < 6} {return post_candidate_slr0}
        if {$bank < 10} {return post_candidate_center}
        return post_candidate_slr2
    }
    if {[string match */u_postprocess_store/* $name]} {return post_other}
    if {[regexp {/u_swiglu/g_quantizer\[([0-3])\]\.u_quantizer/} \
            $name -> quantizer]} {
        return swiglu_quantizer$quantizer
    }
    if {[string match */u_swiglu/u_hadamard/* $name]} {return swiglu_hadamard}
    if {[string match */u_swiglu/* $name]} {return swiglu_other}
    if {[string match */u_center12/u_region0_cols2_3/* $name]} {return attn_region0}
    if {[string match */u_center12/u_region1_cols4_7/* $name]} {return attn_region1}
    if {[string match */u_center12/u_region2_cols8_11/* $name]} {return attn_region2}
    if {[string match */u_center12/u_region3_cols12_13/* $name]} {return attn_region3}
    if {[string match */g_projection_rtl.u_projection/u_frontend/* $name]} {
        return attn_frontend
    }
    if {[string match */g_projection_rtl.u_projection/* $name]} {return attn_owner}
    if {[string match */u_gate_scheduler/u_gather/* $name]} {return mlp_gate_gather}
    if {[string match */u_down_scheduler/* $name]} {return mlp_down_scheduler}
    if {[string match */u_mlp/* $name]} {return mlp_other}
    if {[string match */u_attention/* $name]} {return attention_other}
    return top_other
}

if {![string match "2025.2*" [version -short]]} {
    error "P8 Level-6 map requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P8 Level-6 map requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P8 Level-6 map requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_diagnosis_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P8 Level-6 map received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $diagnosis_output_sha $p10_proc_lib \
        $selector_lib $map_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P8 Level-6 input absent from manifest: $required"
    }
}
set diagnosis_outputs [hap_p10_verify_manifest $diagnosis_output_sha -1 \
    $expected_diagnosis_output_sha]
set diagnosis_summary_path [file join [file dirname $diagnosis_output_sha] \
    summary.txt]
if {![dict exists $diagnosis_outputs $diagnosis_summary_path]} {
    error "Mission 0114 summary is absent from its output manifest"
}
set diagnosis [hap_p10_parse_kv $diagnosis_summary_path \
    "Mission 0114 summary"]
foreach {key expected} {
    stage V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS
    congestion_level5_or_higher_windows 17
    congestion_level6_or_higher_windows 7
    post_place_drc_errors 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS_COMPLETE
} {
    hap_p8_level6_require_kv $diagnosis $key $expected "Mission 0114 summary"
}
hap_p8_level6_require_kv $diagnosis input_dcp $dcp "Mission 0114 summary"
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P8 Level-6 DCP identity mismatch"
}

open_checkpoint $dcp
source $selector_lib
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P8 Level-6 top/part mismatch: $top/$part"
}
hap_p8_level6_require_count pblocks [get_pblocks -quiet] 25
set all_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
hap_p8_level6_require_count dsp48e2 \
    [filter $all_primitives {REF_NAME == DSP48E2}] 5453
hap_p8_level6_require_count uram288 \
    [filter $all_primitives {REF_NAME == URAM288}] 752

set post_roots [hap_v5_floorplan::module_cells \
    hap_attention_cohort16_postprocess_store]
set row_roots [hap_v5_floorplan::module_cells \
    hap_attention_cohort16_postprocess_row_bank]
set quantizer_roots [hap_v5_floorplan::module_cells \
    hap_mlp_robust_a8_quantizer_s35]
set hadamard_roots [hap_v5_floorplan::module_cells \
    hap_mlp_hadamard32_s32_norm_stream]
hap_p8_level6_require_count postprocess_roots $post_roots 1
hap_p8_level6_require_count postprocess_row_roots $row_roots 16
hap_p8_level6_require_count swiglu_quantizer_roots $quantizer_roots 4
hap_p8_level6_require_count swiglu_hadamard_roots $hadamard_roots 1

set geometry [open [file join $out hierarchy_geometry.tsv] w]
puts $geometry \
    "group\ttotal_slr0_1_2_unknown\tlut_slr0_1_2_unknown\tff_slr0_1_2_unknown\tdsp_slr0_1_2_unknown\turam_slr0_1_2_unknown\tbram_slr0_1_2_unknown\ttile_bbox_x0_y0_x1_y1"
foreach {label root_name} {
    attn_region1 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7
    attn_region2 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11
    attn_region3 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region3_cols12_13
    mlp_gate_gather u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_gather
    mlp_down_scheduler u_compute/u_mlp/u_serial_command/u_down_scheduler
} {
    set roots [get_cells -quiet -hierarchical -filter "NAME == $root_name"]
    hap_p8_level6_require_count $label $roots 1
    hap_p8_level6_resource_row $geometry $label \
        [hap_v5_floorplan::primitive_descendants [lindex $roots 0]]
}
hap_p8_level6_resource_row $geometry postprocess \
    [hap_v5_floorplan::primitive_descendants [lindex $post_roots 0]]
hap_p8_level6_resource_row $geometry swiglu_hadamard \
    [hap_v5_floorplan::primitive_descendants [lindex $hadamard_roots 0]]
foreach root [lsort -dictionary $quantizer_roots] {
    set name [get_property NAME $root]
    if {![regexp {/g_quantizer\[([0-3])\]\.u_quantizer$} $name -> index]} {
        error "unexpected P8 SwiGLU quantizer hierarchy: $name"
    }
    hap_p8_level6_resource_row $geometry swiglu_quantizer$index \
        [hap_v5_floorplan::primitive_descendants $root]
}
foreach root [lsort -dictionary $row_roots] {
    set name [get_property NAME $root]
    if {![regexp {/g_row_bank\[([0-9]+)\]\.u_bank$} $name -> index]} {
        error "unexpected P8 postprocess row hierarchy: $name"
    }
    hap_p8_level6_resource_row $geometry postprocess_row$index \
        [hap_v5_floorplan::primitive_descendants $root]
}
close $geometry

set pblock_handle [open [file join $out pblock_ranges.tsv] w]
puts $pblock_handle "pblock\tdirect_members\tgrid_ranges"
foreach pblock [lsort -dictionary [get_pblocks -quiet]] {
    puts $pblock_handle [join [list [get_property NAME $pblock] \
        [llength [get_cells -quiet -of_objects $pblock]] \
        [get_property GRID_RANGES $pblock]] "\t"]
}
close $pblock_handle

set windows {
    north_global CLEL_R_X12Y384 CLEL_R_X41Y447
    south_global CLEM_X25Y470 BRAM_X55Y530
    west_global CLEM_X11Y383 CLEL_R_X40Y446
    north_long CLEL_R_X12Y383 CLEL_R_X41Y446
    south_long CLEM_X25Y473 BRAM_X55Y535
    west_long CLEL_R_X10Y383 CLEM_X40Y446
    west_short CLEL_R_X4Y382 CLEM_X35Y445
}
set category_handle [open [file join $out window_category_counts.tsv] w]
puts $category_handle "window\tlower_tile\tupper_tile\tcategory\tprimitive_count"
set window_name_labels [dict create]
set window_cells_by_label [dict create]
set window_count 0
foreach {label lower upper} $windows {
    incr window_count
    set cells [hap_p8_level6_window_cells $lower $upper]
    dict set window_cells_by_label $label $cells
    set counts [dict create]
    foreach name [get_property NAME $cells] {
        dict incr counts [hap_p8_level6_category $name]
        dict lappend window_name_labels $name $label
    }
    foreach category [lsort -dictionary [dict keys $counts]] {
        puts $category_handle "$label\t$lower\t$upper\t$category\t[dict get $counts $category]"
    }
}
close $category_handle
if {$window_count != 7} {
    error "level6_windows count mismatch: expected=7 actual=$window_count"
}

set pblock_counts [dict create]
foreach pblock [lsort -dictionary [get_pblocks -quiet]] {
    set pblock_name [get_property NAME $pblock]
    set members [hap_v5_floorplan::expanded_pblock_primitives $pblock]
    foreach name [get_property NAME $members] {
        if {![dict exists $window_name_labels $name]} {continue}
        foreach label [lsort -unique [dict get $window_name_labels $name]] {
            dict incr pblock_counts "$label\t$pblock_name"
        }
    }
}
set overlap_handle [open [file join $out window_pblock_counts.tsv] w]
puts $overlap_handle "window\tpblock\tprimitive_count"
foreach key [lsort -dictionary [dict keys $pblock_counts]] {
    puts $overlap_handle "$key\t[dict get $pblock_counts $key]"
}
close $overlap_handle

set cr_handle [open [file join $out slr1_clock_region_utilization.tsv] w]
puts $cr_handle "clock_region\ttotal\tlut\tff\tdsp\turam\tbram"
set clock_region_count 0
for {set x 0} {$x <= 5} {incr x} {
    for {set y 5} {$y <= 9} {incr y} {
        set name CLOCKREGION_X${x}Y${y}
        set region [get_clock_regions -quiet $name]
        if {[llength $region] != 1} {continue}
        incr clock_region_count
        set sites [get_sites -quiet -of_objects $region]
        set direct [get_cells -quiet -of_objects $sites]
        set via_bels [get_cells -quiet -of_objects \
            [get_bels -quiet -of_objects $sites]]
        set names [lsort -dictionary -unique [concat \
            [get_property NAME $direct] [get_property NAME $via_bels]]]
        set cells [get_cells -quiet $names -filter {
            IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
            REF_NAME != GND && REF_NAME != VCC}]
        set lut 0
        set ff 0
        set dsp 0
        set uram 0
        set bram 0
        foreach ref [get_property REF_NAME $cells] {
            if {[string match LUT* $ref]} {incr lut
            } elseif {[string match FD* $ref]} {incr ff
            } elseif {$ref eq "DSP48E2"} {incr dsp
            } elseif {$ref eq "URAM288"} {incr uram
            } elseif {$ref in {RAMB36E2 RAMB18E2}} {incr bram}
        }
        puts $cr_handle "$name\t[llength $cells]\t$lut\t$ff\t$dsp\t$uram\t$bram"
    }
}
close $cr_handle

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P8_LEVEL6_PHYSICAL_MAP \
        evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        pblock_count [llength [get_pblocks -quiet]] dsp48e2 5453 uram288 752 \
        level6_windows_profiled $window_count \
        swiglu_quantizer_roots [llength $quantizer_roots] \
        postprocess_row_roots [llength $row_roots] \
        slr1_clock_regions_profiled $clock_region_count \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 route_eligible 0 \
        status V5_P10_P8_LEVEL6_PHYSICAL_MAP_PASS] {
    puts $summary "$key=$value"
}
close $summary
close_design

exit=0
