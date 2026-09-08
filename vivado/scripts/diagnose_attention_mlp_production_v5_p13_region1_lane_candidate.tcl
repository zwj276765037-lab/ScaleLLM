# Read-only selection of a capacity-proven P13 Attention region1 lane-logic
# subset for the P12 X5Y5 relief region.  No floorplan or implementation state
# is mutated and no checkpoint is written.

set candidate_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P13_CANDIDATE_DCP)]
set out [file normalize $::env(HAP_P13_CANDIDATE_DIR)]
set input_sha [file normalize $::env(HAP_P13_CANDIDATE_INPUT_SHA)]
set expected_input_sha $::env(HAP_P13_CANDIDATE_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P13_CANDIDATE_DCP_SHA256)
set placement_output_sha [file normalize \
    $::env(HAP_P13_CANDIDATE_PLACEMENT_OUTPUT_SHA)]
set expected_placement_output_sha \
    $::env(HAP_P13_CANDIDATE_PLACEMENT_OUTPUT_SHA256)
set level6_output_sha [file normalize \
    $::env(HAP_P13_CANDIDATE_LEVEL6_OUTPUT_SHA)]
set expected_level6_output_sha \
    $::env(HAP_P13_CANDIDATE_LEVEL6_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P13_CANDIDATE_P10_PROC_LIB)]
set selector_lib [file normalize $::env(HAP_P13_CANDIDATE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_P13_CANDIDATE_GEOMETRY_LIB)]
set expected_launcher [file normalize $::env(HAP_P13_CANDIDATE_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p13_candidate_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p13_candidate_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p13_candidate_signature {cells} {
    array set count {total 0 lut 0 ff 0 dsp 0 uram 0 bram 0}
    foreach ref [get_property REF_NAME $cells] {
        incr count(total)
        if {[string match LUT* $ref]} {incr count(lut)
        } elseif {[string match FD* $ref]} {incr count(ff)
        } elseif {$ref eq "DSP48E2"} {incr count(dsp)
        } elseif {$ref eq "URAM288"} {incr count(uram)
        } elseif {$ref in {RAMB36E2 RAMB18E2}} {incr count(bram)}
    }
    return [dict create total $count(total) lut $count(lut) ff $count(ff) \
        dsp $count(dsp) uram $count(uram) bram $count(bram)]
}

proc hap_p13_candidate_percent {used capacity} {
    if {$capacity == 0} {return [expr {$used == 0 ? "0.000" : "INF"}]}
    return [format %.3f [expr {100.0 * $used / $capacity}]]
}

proc hap_p13_candidate_window_cells {lower_name upper_name} {
    set lower [get_tiles -quiet $lower_name]
    set upper [get_tiles -quiet $upper_name]
    hap_p13_candidate_require_count "lower tile $lower_name" $lower 1
    hap_p13_candidate_require_count "upper tile $upper_name" $upper 1
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
    return [get_cells -quiet $names -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
        REF_NAME != GND && REF_NAME != VCC}]
}

if {![string match "2025.2*" [version -short]]} {
    error "P13 candidate map requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P13 candidate map requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P13 candidate map requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_placement_output_sha $expected_level6_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P13 candidate map received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 8 $expected_input_sha]
foreach required [list $dcp $placement_output_sha $level6_output_sha \
        $p10_proc_lib $selector_lib $geometry_lib $candidate_script \
        $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P13 candidate input absent from manifest: $required"
    }
}
set placement_outputs [hap_p10_verify_manifest $placement_output_sha -1 \
    $expected_placement_output_sha]
set placement_summary_path [file join [file dirname $placement_output_sha] \
    summary.txt]
if {![dict exists $placement_outputs \
        [file normalize $placement_summary_path]]} {
    error "Mission 0137 summary absent from output manifest"
}
set placement [hap_p10_parse_kv $placement_summary_path \
    "Mission 0137 summary"]
foreach {key expected} {
    stage V5_P10_P12_POST_PLACE_FAST_GATE
    route_eligible 0
    p12_region1_relief_placed 0
    dsp48e2 5453
    slr_dsp48e2 {1862 1781 1810}
    uram288 752
    unplaced_primitives 0
    wrong_slr_primitives 0
    congestion_level5_or_higher_windows 19
    congestion_level6_or_higher_windows 7
    status FAIL
} {
    hap_p13_candidate_require_kv $placement $key $expected \
        "Mission 0137 summary"
}
set level6_outputs [hap_p10_verify_manifest $level6_output_sha -1 \
    $expected_level6_output_sha]
set level6_summary_path [file join [file dirname $level6_output_sha] \
    summary.txt]
set level6_cr_path [file join [file dirname $level6_output_sha] \
    slr1_clock_region_utilization.tsv]
foreach required [list $level6_summary_path $level6_cr_path] {
    if {![dict exists $level6_outputs [file normalize $required]]} {
        error "Mission 0138 artifact absent from output manifest: $required"
    }
}
set level6 [hap_p10_parse_kv $level6_summary_path "Mission 0138 summary"]
foreach {key expected} {
    stage V5_P10_P12_LEVEL6_PHYSICAL_MAP
    source_lineage_verified 1
    slr1_clock_regions_profiled 30
    slr1_occupied_dsp 1781
    clock_region_dsp_accounting DIRECT_PLACED_CELL_SITE
    floorplan_mutated 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P12_LEVEL6_PHYSICAL_MAP_PASS
} {
    hap_p13_candidate_require_kv $level6 $key $expected \
        "Mission 0138 summary"
}
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha ||
    [dict get $level6 input_dcp_sha256] ne $actual_dcp_sha} {
    error "P13 candidate DCP identity mismatch"
}

source $selector_lib
source $geometry_lib
open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P13 candidate top/part mismatch: $top/$part"
}
hap_p13_candidate_require_count pblocks [get_pblocks -quiet] 26
set all_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
hap_p13_candidate_require_count dsp48e2 \
    [filter $all_primitives {REF_NAME == DSP48E2}] 5453
hap_p13_candidate_require_count uram288 \
    [filter $all_primitives {REF_NAME == URAM288}] 752

set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set projection_root [file dirname \
    [get_property NAME [dict get $base_plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover \
    $projection_root 1]
set lane_roots [dict get $geometry_plan center_region1_lane_roots]
hap_p13_candidate_require_count region1_lane_roots $lane_roots 32
set parent_pblock [get_pblocks -quiet \
    p3_pb_projection_center_region1_logic_residual_cr_x2y5_x4y9]
hap_p13_candidate_require_count region1_logic_parent_pblock $parent_pblock 1
set parent_members [hap_v5_floorplan::pblockable_primitives \
    [hap_v5_floorplan::expanded_pblock_primitives $parent_pblock]]

set windows {
    north_global CLEM_X25Y391 BRAM_X55Y450
    south_global CLEM_X14Y459 CLEM_X44Y522
    north_long CLEM_X25Y390 BRAM_X55Y450
    south_long CLEM_X16Y461 CLEM_X46Y524
    west_long CLEL_R_X12Y478 CLEL_R_X41Y541
    east_short CLEL_R_X35Y467 CLEL_R_X65Y530
    west_short CLEM_X14Y472 CLEM_X44Y535
}
set window_sets [dict create]
foreach {label lower upper} $windows {
    set names [dict create]
    foreach name [get_property NAME \
            [hap_p13_candidate_window_cells $lower $upper]] {
        dict set names $name 1
    }
    dict set window_sets $label $names
}

set x5y5 [get_clock_regions -quiet X5Y5]
hap_p13_candidate_require_count x5y5_clock_region $x5y5 1
set x5_sites [get_sites -quiet -of_objects $x5y5]
array set x5_capacity {lut 0 ff 0 dsp 0 uram 0 bram 0}
foreach site_type [get_property SITE_TYPE $x5_sites] {
    if {[string match SLICE* $site_type]} {
        incr x5_capacity(lut) 8
        incr x5_capacity(ff) 16
    } elseif {$site_type eq "DSP48E2"} {incr x5_capacity(dsp)
    } elseif {$site_type eq "URAM288"} {incr x5_capacity(uram)
    } elseif {[string match RAMB18* $site_type]} {incr x5_capacity(bram)}
}
array set x5_occupied {total 0 lut 0 ff 0 dsp 0 uram 0 bram 0}
set cr_fp [open $level6_cr_path r]
set cr_lines [split [string trim [read $cr_fp]] "\n"]
close $cr_fp
set cr_header [split [lindex $cr_lines 0] "\t"]
set cr_columns [dict create]
set column_index 0
foreach column $cr_header {
    dict set cr_columns $column $column_index
    incr column_index
}
foreach required {clock_region occupied_total occupied_lut occupied_ff
        occupied_dsp occupied_uram occupied_bram} {
    if {![dict exists $cr_columns $required]} {
        error "Mission 0138 clock-region table is missing column: $required"
    }
}
set x5_rows 0
foreach line [lrange $cr_lines 1 end] {
    set fields [split $line "\t"]
    if {[lindex $fields [dict get $cr_columns clock_region]] ne "X5Y5"} {
        continue
    }
    incr x5_rows
    foreach key {total lut ff dsp uram bram} {
        set x5_occupied($key) [lindex $fields \
            [dict get $cr_columns occupied_$key]]
    }
}
if {$x5_rows != 1} {
    error "Mission 0138 X5Y5 row mismatch: expected=1 actual=$x5_rows"
}

set lane_metrics [dict create]
set lane_labels {}
set lane_handle [open [file join $out region1_lane_logic.tsv] w]
puts $lane_handle [join {
    lane row local_col logical_col primitives lut ff dsp uram bram
    current_x5y5_primitives north_global south_global north_long south_long
    west_long east_short west_short weighted_level6_score
} "\t"]
foreach root [lsort -dictionary $lane_roots] {
    set root_name [get_property NAME $root]
    if {![regexp {g_row\[([0-7])\]\.g_col\[([0-3])\]\.u_lane$} \
            $root_name -> row local_col]} {
        error "P13 candidate unexpected region1 lane root: $root_name"
    }
    set label r${row}c${local_col}
    set lane_primitives [hap_v5_floorplan::pblockable_primitives \
        [hap_v5_floorplan::primitive_descendants $root]]
    set lane_logic [filter $lane_primitives {REF_NAME != DSP48E2}]
    set missing [hap_v5_floorplan::list_subtract $lane_logic $parent_members]
    if {[llength $lane_logic] == 0 || [llength $missing] != 0} {
        error "P13 candidate lane parent membership mismatch: $label"
    }
    set signature [hap_p13_candidate_signature $lane_logic]
    foreach key {dsp uram bram} {
        if {[dict get $signature $key] != 0} {
            error "P13 candidate lane is not logic-only: $label $key"
        }
    }
    set current_x5 0
    set window_counts [dict create]
    foreach {window lower upper} $windows {dict set window_counts $window 0}
    foreach cell $lane_logic name [get_property NAME $lane_logic] {
        set sites [get_sites -quiet -of_objects $cell]
        if {[llength $sites] == 1} {
            set regions [get_clock_regions -quiet -of_objects $sites]
            if {[llength $regions] == 1 &&
                [get_property NAME $regions] eq "X5Y5"} {incr current_x5}
        }
        foreach {window lower upper} $windows {
            if {[dict exists [dict get $window_sets $window] $name]} {
                dict incr window_counts $window
            }
        }
    }
    set weighted [expr {
        4 * [dict get $window_counts east_short] +
        2 * ([dict get $window_counts north_global] +
             [dict get $window_counts north_long]) +
        [dict get $window_counts south_global] +
        [dict get $window_counts south_long] +
        [dict get $window_counts west_long] +
        [dict get $window_counts west_short]}]
    dict set lane_metrics $label [dict merge $signature $window_counts \
        [dict create current_x5 $current_x5 weighted $weighted \
            row $row local_col $local_col]]
    lappend lane_labels $label
    puts $lane_handle [join [list $label $row $local_col \
        [expr {$local_col + 4}] [dict get $signature total] \
        [dict get $signature lut] [dict get $signature ff] \
        [dict get $signature dsp] [dict get $signature uram] \
        [dict get $signature bram] $current_x5 \
        [dict get $window_counts north_global] \
        [dict get $window_counts south_global] \
        [dict get $window_counts north_long] \
        [dict get $window_counts south_long] \
        [dict get $window_counts west_long] \
        [dict get $window_counts east_short] \
        [dict get $window_counts west_short] $weighted] "\t"]
}
close $lane_handle
set lane_labels [lsort -dictionary $lane_labels]
hap_p13_candidate_require_count lane_metric_rows $lane_labels 32

set combo_handle [open [file join $out region1_lane_triples.tsv] w]
puts $combo_handle [join {
    lanes primitives lut ff projected_x5y5_lut projected_x5y5_ff
    projected_x5y5_lut_percent projected_x5y5_ff_percent north_global_removed
    south_global_removed north_long_removed south_long_removed west_long_removed
    east_short_removed west_short_removed weighted_level6_score capacity_ok
} "\t"]
set combo_count 0
set feasible_count 0
set best_lanes ""
set best_weighted -1
set best_east -1
set best_projected_lut 0
set lane_count [llength $lane_labels]
for {set i 0} {$i < $lane_count - 2} {incr i} {
    for {set j [expr {$i + 1}]} {$j < $lane_count - 1} {incr j} {
        for {set k [expr {$j + 1}]} {$k < $lane_count} {incr k} {
            incr combo_count
            set labels [list [lindex $lane_labels $i] \
                [lindex $lane_labels $j] [lindex $lane_labels $k]]
            array set sum {total 0 lut 0 ff 0 current_x5 0
                north_global 0 south_global 0 north_long 0 south_long 0
                west_long 0 east_short 0 west_short 0 weighted 0}
            foreach label $labels {
                set metric [dict get $lane_metrics $label]
                foreach key [array names sum] {
                    incr sum($key) [dict get $metric $key]
                }
            }
            set projected_lut [expr {$x5_occupied(lut) + $sum(lut)}]
            set projected_ff [expr {$x5_occupied(ff) + $sum(ff)}]
            set projected_lut_pct [hap_p13_candidate_percent \
                $projected_lut $x5_capacity(lut)]
            set projected_ff_pct [hap_p13_candidate_percent \
                $projected_ff $x5_capacity(ff)]
            set capacity_ok [expr {$sum(current_x5) == 0 &&
                $projected_lut_pct <= 90.0 && $projected_ff_pct <= 75.0}]
            if {$capacity_ok} {
                incr feasible_count
                if {$sum(weighted) > $best_weighted ||
                    ($sum(weighted) == $best_weighted &&
                     $sum(east_short) > $best_east) ||
                    ($sum(weighted) == $best_weighted &&
                     $sum(east_short) == $best_east &&
                     $projected_lut < $best_projected_lut)} {
                    set best_lanes $labels
                    set best_weighted $sum(weighted)
                    set best_east $sum(east_short)
                    set best_projected_lut $projected_lut
                }
            }
            puts $combo_handle [join [list [join $labels ,] $sum(total) \
                $sum(lut) $sum(ff) $projected_lut $projected_ff \
                $projected_lut_pct $projected_ff_pct $sum(north_global) \
                $sum(south_global) $sum(north_long) $sum(south_long) \
                $sum(west_long) $sum(east_short) $sum(west_short) \
                $sum(weighted) $capacity_ok] "\t"]
        }
    }
}
close $combo_handle
if {$combo_count != 4960 || $feasible_count == 0 || $best_lanes eq ""} {
    error "P13 candidate triple selection failed: total=$combo_count feasible=$feasible_count"
}

set best_metric [dict create]
foreach key {total lut ff current_x5 north_global south_global north_long
        south_long west_long east_short west_short weighted} {
    dict set best_metric $key 0
    foreach label $best_lanes {
        dict incr best_metric $key [dict get $lane_metrics $label $key]
    }
}
set best_projected_ff [expr {$x5_occupied(ff) +
    [dict get $best_metric ff]}]
set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P13_REGION1_LANE_CANDIDATE \
        evidence_class READ_ONLY_REJECTED_P12_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        pblock_count [llength [get_pblocks -quiet]] dsp48e2 5453 uram288 752 \
        region1_lane_roots [llength $lane_roots] \
        candidate_triples $combo_count feasible_triples $feasible_count \
        x5y5_lut_capacity $x5_capacity(lut) \
        x5y5_ff_capacity $x5_capacity(ff) \
        x5y5_dsp_capacity $x5_capacity(dsp) \
        x5y5_occupied_lut $x5_occupied(lut) \
        x5y5_occupied_ff $x5_occupied(ff) \
        x5y5_occupied_dsp $x5_occupied(dsp) \
        candidate_lut_limit_percent 90.0 \
        candidate_ff_limit_percent 75.0 \
        selected_lanes $best_lanes \
        selected_primitives [dict get $best_metric total] \
        selected_lut [dict get $best_metric lut] \
        selected_ff [dict get $best_metric ff] \
        selected_current_x5y5_primitives [dict get $best_metric current_x5] \
        selected_east_short_removed [dict get $best_metric east_short] \
        selected_weighted_level6_score [dict get $best_metric weighted] \
        projected_x5y5_lut $best_projected_lut \
        projected_x5y5_ff $best_projected_ff \
        projected_x5y5_lut_percent [hap_p13_candidate_percent \
            $best_projected_lut $x5_capacity(lut)] \
        projected_x5y5_ff_percent [hap_p13_candidate_percent \
            $best_projected_ff $x5_capacity(ff)] \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 route_eligible 0 \
        status V5_P13_REGION1_LANE_CANDIDATE_PASS] {
    puts $summary "$key=$value"
}
close $summary
close_design

exit 0
