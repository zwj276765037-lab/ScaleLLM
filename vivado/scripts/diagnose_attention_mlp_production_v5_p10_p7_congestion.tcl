# Read-only diagnosis for the rejected Mission 0095 P7 placement.

set dcp [file normalize $::env(HAP_P7_DIAG_DCP)]
set out [file normalize $::env(HAP_P7_DIAG_DIR)]
set input_sha [file normalize $::env(HAP_P7_DIAG_INPUT_SHA)]
set expected_input_sha $::env(HAP_P7_DIAG_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P7_DIAG_DCP_SHA256)
set failed_output_sha [file normalize $::env(HAP_P7_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P7_FAILED_OUTPUT_SHA256)
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

proc hap_p7_diag_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_p7_diag_read {path label} {
    hap_p7_diag_nonempty $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p7_diag_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p7_diag_manifest {path expected_count expected_sha label} {
    if {[hap_p7_diag_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_p7_diag_read $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed $label row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate $label path: $normalized"
        }
        hap_p7_diag_nonempty $normalized "$label member"
        if {[hap_p7_diag_sha256 $normalized] ne $expected} {
            error "$label member SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {[dict size $entries] != $expected_count} {
        error "$label count mismatch: expected=$expected_count actual=[dict size $entries]"
    }
    return $entries
}

proc hap_p7_diag_require_line {path literal} {
    set count 0
    foreach line [split [hap_p7_diag_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P7 evidence mismatch: path=$path literal=$literal count=$count"
    }
}

proc hap_p7_diag_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p7_diag_primitives {root_name} {
    hap_p7_diag_require_count "root $root_name" [get_cells -quiet $root_name] 1
    set cells [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/* && IS_PRIMITIVE && \
         PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND && REF_NAME != VCC"]
    if {[llength $cells] == 0} {error "Empty hierarchy root: $root_name"}
    return $cells
}

proc hap_p7_diag_region2_rows {root_name min_row max_row} {
    set selected {}
    foreach cell [hap_p7_diag_primitives $root_name] {
        set name [get_property NAME $cell]
        if {[regexp {/g_row\[([0-9]+)\]\.g_col\[[0-9]+\]\.u_lane/} \
                $name -> row] && $row >= $min_row && $row <= $max_row} {
            lappend selected $cell
        }
    }
    if {[llength $selected] == 0} {error "Empty region2 rows $min_row..$max_row"}
    return $selected
}

proc hap_p7_diag_slr_index {value} {
    if {[regexp {([0-2])$} $value -> index]} {return $index}
    return 3
}

proc hap_p7_diag_bbox {cells} {
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

proc hap_p7_diag_geometry_row {handle label cells} {
    if {[llength $cells] == 0} {error "Empty geometry group: $label"}
    set total {0 0 0 0}
    set lut {0 0 0 0}
    set ff {0 0 0 0}
    set dsp {0 0 0 0}
    set uram {0 0 0 0}
    set bram {0 0 0 0}
    foreach ref [get_property REF_NAME $cells] slr_value [get_property SLR_INDEX $cells] {
        set slr [hap_p7_diag_slr_index $slr_value]
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
        [hap_p7_diag_bbox $cells]] "\t"]
}

proc hap_p7_diag_object_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -dictionary -unique [get_property NAME $objects]]
}

proc hap_p7_diag_window_cells {lower_name upper_name} {
    set lower [get_tiles -quiet $lower_name]
    set upper [get_tiles -quiet $upper_name]
    hap_p7_diag_require_count "lower tile $lower_name" $lower 1
    hap_p7_diag_require_count "upper tile $upper_name" $upper 1
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
    set via_bels [get_cells -quiet -of_objects [get_bels -quiet -of_objects $sites]]
    set names [lsort -dictionary -unique [concat \
        [hap_p7_diag_object_names $direct] [hap_p7_diag_object_names $via_bels]]]
    set cells [get_cells -quiet $names -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
        REF_NAME != GND && REF_NAME != VCC}]
    if {[llength $cells] == 0} {error "Empty congestion window $lower_name:$upper_name"}
    return $cells
}

proc hap_p7_diag_category {name} {
    if {[regexp {/u_postprocess_store/g_row_bank\[([0-9]+)\]\.u_bank/} \
            $name -> bank]} {
        if {$bank < 4} {return post_outer_slr0}
        if {$bank < 12} {return post_center_slr1}
        return post_outer_slr2
    }
    if {[string match */u_postprocess_store/* $name]} {return post_other}
    if {[string match */u_center12/u_region0_cols2_3/* $name]} {return attn_region0}
    if {[string match */u_center12/u_region1_cols4_7/* $name]} {return attn_region1}
    if {[regexp {/u_region2_cols8_11/g_row\[([0-9]+)\]\.g_col\[[0-9]+\]\.u_lane/} \
            $name -> row]} {
        return [expr {$row < 4 ? "attn_region2_rows0_3" : "attn_region2_rows4_7"}]
    }
    if {[string match */u_center12/u_region2_cols8_11/* $name]} {
        return attn_region2_residual
    }
    if {[string match */u_center12/u_region3_cols12_13/* $name]} {return attn_region3}
    if {[string match */g_projection_rtl.u_projection/u_frontend/* $name]} {
        return attn_frontend
    }
    if {[string match */g_projection_rtl.u_projection/* $name]} {return attn_owner}
    if {[string match */u_gate_scheduler/u_gather/* $name]} {return mlp_gate_gather}
    if {[string match */u_gate_scheduler/u_projection_repack/* $name]} {
        return mlp_gate_repack
    }
    if {[string match */u_down_scheduler/u_weight_repack/* $name]} {
        return mlp_down_repack
    }
    if {[string match */u_gate_scheduler/u_swiglu/g_quantizer* $name]} {
        return mlp_swiglu_quantizer
    }
    if {[string match */u_gate_scheduler/u_swiglu/* $name]} {return mlp_swiglu}
    if {[string match */u_shared_compute/u_branch0/* $name]} {return mlp_branch0}
    if {[string match */u_shared_compute/u_branch1/* $name]} {return mlp_branch1}
    if {[string match */u_mlp/u_input_frontend/* $name]} {return mlp_input}
    if {[string match */u_mlp/* $name]} {return mlp_other}
    if {[string match */u_attention/* $name]} {return attention_other}
    return top_other
}

proc hap_p7_diag_worst_slack {delay clock_name} {
    set clock [get_clocks -quiet $clock_name]
    if {[llength $clock] != 1} {return NA}
    set path [lindex [get_timing_paths -quiet -delay_type $delay \
        -from $clock -max_paths 1] 0]
    if {$path eq ""} {return NA}
    return [get_property SLACK $path]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {error "P7 diagnosis requires fresh Vivado"}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P7 diagnosis requires HAP_JOBS=32"
}
set_param general.maxThreads $jobs

set frozen [hap_p7_diag_manifest $input_sha 4 $expected_input_sha p7_diag_input]
set failed_entries [hap_p7_diag_manifest $failed_output_sha 29 \
    $expected_failed_output_sha p7_failed_output]
foreach required [list $dcp $failed_output_sha [file normalize [info script]] \
        [file normalize $::env(HAP_P7_DIAG_LAUNCHER)]] {
    if {![dict exists $frozen $required]} {error "Missing frozen input: $required"}
}
set failed_dir [file dirname $failed_output_sha]
set failed_summary [file join $failed_dir summary.txt]
set failed_launcher [file join $failed_dir launcher_status.txt]
foreach required [list $dcp $failed_summary $failed_launcher \
        [file join $failed_dir congestion_post_place.rpt]] {
    if {![dict exists $failed_entries $required]} {error "Missing failed evidence: $required"}
}
foreach literal [list status=FAIL route_eligible=0 acceptance_evidence=0 \
        checkpoint_written=0 diagnostic_checkpoint_written=1 dsp48e2=5453 \
        uram288=752 p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8 \
        congestion_level5_or_higher_windows=19 \
        congestion_level6_or_higher_windows=8] {
    hap_p7_diag_require_line $failed_summary $literal
}
foreach literal {status=FAIL route_eligible=0 acceptance_evidence=0
        checkpoint_written=0 bitstream_generated=0 final_exit_code=1} {
    hap_p7_diag_require_line $failed_launcher $literal
}
if {[hap_p7_diag_sha256 $dcp] ne $expected_dcp_sha} {
    error "P7 diagnostic DCP identity mismatch"
}

set open_start [clock milliseconds]
open_checkpoint $dcp
set open_elapsed [expr {[clock milliseconds] - $open_start}]
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e"} {
    error "P7 diagnostic part mismatch"
}
if {[get_property TOP [current_design]] ne "hap_attention_mlp_production_core"} {
    error "P7 diagnostic top mismatch"
}
hap_p7_diag_require_count pblocks [get_pblocks -quiet] 27

set all_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set all_dsp [filter $all_primitives {REF_NAME == DSP48E2}]
set all_uram [filter $all_primitives {REF_NAME == URAM288}]
hap_p7_diag_require_count dsp48e2 $all_dsp 5453
hap_p7_diag_require_count uram288 $all_uram 752

set region2_root \
    u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11
set rows0_3 [hap_p7_diag_region2_rows $region2_root 0 3]
set rows4_7 [hap_p7_diag_region2_rows $region2_root 4 7]
hap_p7_diag_require_count region2_rows0_3 $rows0_3 26800
hap_p7_diag_require_count region2_rows4_7 $rows4_7 26800

set pblock_fh [open [file join $out pblock_ranges.tsv] w]
puts $pblock_fh "pblock\tmember_count\tgrid_ranges"
foreach pblock [lsort -dictionary [get_pblocks -quiet]] {
    puts $pblock_fh [join [list [get_property NAME $pblock] \
        [llength [get_cells -quiet -of_objects $pblock]] \
        [get_property GRID_RANGES $pblock]] "\t"]
}
close $pblock_fh

set groups [list \
    attn_region0 [hap_p7_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region0_cols2_3] \
    attn_region1 [hap_p7_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7] \
    attn_region2 [hap_p7_diag_primitives $region2_root] \
    attn_region2_rows0_3 $rows0_3 attn_region2_rows4_7 $rows4_7 \
    attn_region3 [hap_p7_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region3_cols12_13] \
    postprocess [hap_p7_diag_primitives u_compute/u_attention/u_compute/u_postprocess_store] \
    mlp_gather [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_gather] \
    mlp_gate_repack [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack] \
    mlp_down_repack [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_down_scheduler/u_weight_repack] \
    mlp_swiglu [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu] \
    mlp_branch0 [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch0] \
    mlp_branch1 [hap_p7_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch1]]
set geometry_fh [open [file join $out hierarchy_geometry.tsv] w]
puts $geometry_fh \
    "group\ttotal_slr0_1_2_unknown\tlut_slr0_1_2_unknown\tff_slr0_1_2_unknown\tdsp_slr0_1_2_unknown\turam_slr0_1_2_unknown\tbram_slr0_1_2_unknown\ttile_bbox_x0_y0_x1_y1"
foreach {label cells} $groups {hap_p7_diag_geometry_row $geometry_fh $label $cells}
close $geometry_fh

set windows {
    north_global CLEM_X28Y387 CLEL_R_X57Y450
    south_global CLEM_X23Y475 BRAM_X53Y535
    west_global CLEM_X14Y490 CLEM_X44Y553
    north_long CLEL_R_X27Y390 CLEM_X57Y453
    south_long CLEM_X20Y478 LAG_LAG_X49Y541
    west_long CLEM_X14Y492 CLEM_X44Y555
    north_short CLEL_R_X30Y390 DSP_X59Y450
    west_short CLEL_R_X26Y391 CLEM_X56Y454
}
set window_fh [open [file join $out window_category_counts.tsv] w]
set ref_fh [open [file join $out window_reference_counts.tsv] w]
puts $window_fh "window\tlower_tile\tupper_tile\tcategory\tprimitive_count"
puts $ref_fh "window\tcategory\tref_name\tprimitive_count"
set window_count 0
set window_rows 0
foreach {label lower upper} $windows {
    incr window_count
    set category_counts [dict create]
    set reference_counts [dict create]
    set cells [hap_p7_diag_window_cells $lower $upper]
    foreach name [get_property NAME $cells] ref [get_property REF_NAME $cells] {
        set category [hap_p7_diag_category $name]
        dict incr category_counts $category
        dict incr reference_counts "$category\t$ref"
    }
    foreach category [lsort -dictionary [dict keys $category_counts]] {
        puts $window_fh "$label\t$lower\t$upper\t$category\t[dict get $category_counts $category]"
        incr window_rows
    }
    foreach key [lsort -dictionary [dict keys $reference_counts]] {
        puts $ref_fh "$label\t$key\t[dict get $reference_counts $key]"
    }
}
close $window_fh
close $ref_fh

report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 5 \
    -file [file join $out utilization_hier_post_place.rpt]
report_timing_summary -delay_type min_max -max_paths 100 \
    -file [file join $out timing_post_place.rpt]
report_timing -delay_type max -max_paths 100 -nworst 1 \
    -file [file join $out timing_setup_paths.rpt]
report_timing -delay_type min -max_paths 100 -nworst 1 \
    -file [file join $out timing_hold_paths.rpt]

set setup_path [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {error "P7 timing paths are empty"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]

set slr_dsp {0 0 0 0}
set slr_uram {0 0 0 0}
foreach slr_value [get_property SLR_INDEX $all_dsp] {
    set index [hap_p7_diag_slr_index $slr_value]
    lset slr_dsp $index [expr {[lindex $slr_dsp $index] + 1}]
}
foreach slr_value [get_property SLR_INDEX $all_uram] {
    set index [hap_p7_diag_slr_index $slr_value]
    lset slr_uram $index [expr {[lindex $slr_uram $index] + 1}]
}
set status [expr {$slr_dsp eq {1862 1781 1810 0} &&
    $slr_uram eq {224 224 304 0} && $window_count == 8 && $window_rows > 0 ?
    "V5_P10_P7_CONGESTION_DIAGNOSIS_PASS" : "FAIL"}]
set summary_fh [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P7_CONGESTION_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_P7_PLACEMENT \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 4 \
        failed_output_manifest_sha256 $expected_failed_output_sha \
        failed_output_entries 29 failed_placement_verified 1 jobs $jobs \
        pblock_count 27 dsp48e2 5453 uram288 752 \
        mlp_kernel_dsp48e2 3072 slr_dsp48e2 [lrange $slr_dsp 0 2] \
        slr_uram288 [lrange $slr_uram 0 2] \
        region2_rows0_3_primitives [llength $rows0_3] \
        region2_rows4_7_primitives [llength $rows4_7] \
        level6_windows_profiled $window_count window_category_rows $window_rows \
        post_place_wns_ns $wns post_place_whs_ns $whs \
        core_setup_wns_ns [hap_p7_diag_worst_slack max core_clk] \
        ddr0_setup_wns_ns [hap_p7_diag_worst_slack max ddr0_clk] \
        ddr1_setup_wns_ns [hap_p7_diag_worst_slack max ddr1_clk] \
        open_checkpoint_elapsed_ms $open_elapsed floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 \
        route_eligible 0 status $status] {
    puts $summary_fh "$key=$value"
}
close $summary_fh
close_design
if {$status eq "FAIL"} {error "P7 congestion diagnosis gate failed"}
puts "P7_CONGESTION_DIAGNOSIS_PASS"
