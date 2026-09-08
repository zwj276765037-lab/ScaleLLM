# Read-only diagnosis of the rejected P5 production placement.  The report
# binds the failed evidence and measures the actual occupants of every Level-6
# placement window without changing constraints, placement, or routing.

set dcp [file normalize $::env(HAP_P5_DIAG_DCP)]
set out [file normalize $::env(HAP_P5_DIAG_DIR)]
set input_sha [file normalize $::env(HAP_P5_DIAG_INPUT_SHA)]
set expected_input_sha $::env(HAP_P5_DIAG_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P5_DIAG_DCP_SHA256)
set failed_output_sha [file normalize $::env(HAP_P5_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P5_FAILED_OUTPUT_SHA256)
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

proc hap_p5_diag_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_p5_diag_read {path label} {
    hap_p5_diag_nonempty $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p5_diag_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p5_diag_manifest {path expected_count expected_sha label} {
    if {[hap_p5_diag_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_p5_diag_read $path $label] "\n"] {
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
        hap_p5_diag_nonempty $normalized "$label member"
        if {[hap_p5_diag_sha256 $normalized] ne $expected} {
            error "$label member SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {[dict size $entries] != $expected_count} {
        error "$label cardinality mismatch: expected=$expected_count actual=[dict size $entries]"
    }
    return $entries
}

proc hap_p5_diag_require_line {path literal} {
    set count 0
    foreach line [split [hap_p5_diag_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P5 evidence mismatch: path=$path literal=$literal count=$count"
    }
}

proc hap_p5_diag_require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc hap_p5_diag_object_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -dictionary -unique [get_property NAME $objects]]
}

proc hap_p5_diag_primitives {root_name} {
    set root [get_cells -quiet $root_name]
    hap_p5_diag_require_count "hierarchy root $root_name" $root 1
    set cells [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root_name}/* && IS_PRIMITIVE && \
         PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND && REF_NAME != VCC"]
    if {[llength $cells] == 0} {error "Empty hierarchy root: $root_name"}
    return $cells
}

proc hap_p5_diag_slr_index {value} {
    if {[regexp {([0-2])$} $value -> index]} {return $index}
    return 3
}

proc hap_p5_diag_bbox {cells} {
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

proc hap_p5_diag_resource_row {handle label cells} {
    if {[llength $cells] == 0} {error "Empty resource group: $label"}
    set totals [dict create total {0 0 0 0} lut {0 0 0 0} \
        ff {0 0 0 0} dsp {0 0 0 0} uram {0 0 0 0} \
        ramb36 {0 0 0 0} ramb18 {0 0 0 0}]
    set refs [get_property REF_NAME $cells]
    set slrs [get_property SLR_INDEX $cells]
    foreach ref $refs slr_value $slrs {
        set slr [hap_p5_diag_slr_index $slr_value]
        set row [dict get $totals total]
        lset row $slr [expr {[lindex $row $slr] + 1}]
        dict set totals total $row
        set type ""
        if {[string match LUT* $ref]} {set type lut}
        if {[string match FD* $ref]} {set type ff}
        if {$ref eq "DSP48E2"} {set type dsp}
        if {$ref eq "URAM288"} {set type uram}
        if {$ref eq "RAMB36E2"} {set type ramb36}
        if {$ref eq "RAMB18E2"} {set type ramb18}
        if {$type ne ""} {
            set row [dict get $totals $type]
            lset row $slr [expr {[lindex $row $slr] + 1}]
            dict set totals $type $row
        }
    }
    puts $handle [join [list $label [dict get $totals total] \
        [dict get $totals lut] [dict get $totals ff] [dict get $totals dsp] \
        [dict get $totals uram] [dict get $totals ramb36] \
        [dict get $totals ramb18] [hap_p5_diag_bbox $cells]] "\t"]
}

proc hap_p5_diag_category {name} {
    if {[regexp {/u_postprocess_store/g_row_bank\[([0-9]+)\]\.u_bank/} \
            $name -> bank]} {
        return [expr {$bank < 8 ? "post_bank0_7" : "post_bank8_15"}]
    }
    if {[string match */u_postprocess_store/* $name]} {return post_other}
    if {[string match */u_center12/u_region0_cols2_3/* $name]} {return attn_region0}
    if {[string match */u_center12/u_region1_cols4_7/* $name]} {return attn_region1}
    if {[string match */u_center12/u_region2_cols8_11/* $name]} {return attn_region2}
    if {[string match */u_center12/u_region3_cols12_13/* $name]} {return attn_region3}
    if {[string match */g_projection_rtl.u_projection/u_frontend/* $name]} {
        return attn_projection_frontend
    }
    if {[string match */g_projection_rtl.u_projection/* $name]} {
        return attn_projection_owner
    }
    if {[string match */u_mlp/u_input_frontend/g_half0* $name] ||
        [string match */u_mlp/u_input_frontend/u_half0/* $name]} {
        return mlp_input_half0
    }
    if {[string match */u_mlp/u_input_frontend/g_half1* $name] ||
        [string match */u_mlp/u_input_frontend/u_half1/* $name]} {
        return mlp_input_half1
    }
    if {[string match */u_mlp/u_input_frontend/* $name]} {return mlp_input_center}
    if {[string match */u_gate_scheduler/u_gather/* $name]} {return mlp_gather}
    if {[string match */u_gate_scheduler/u_projection_repack/* $name]} {
        return mlp_repack
    }
    if {[string match */u_gate_scheduler/u_swiglu/* $name]} {return mlp_swiglu}
    if {[string match */u_shared_compute/u_branch0/* $name]} {return mlp_branch0}
    if {[string match */u_shared_compute/u_branch1/* $name]} {return mlp_branch1}
    if {[string match */u_paired_weight/* $name]} {return paired_weight}
    if {[string match */u_attention/* $name]} {return attention_other}
    if {[string match */u_mlp/* $name]} {return mlp_other}
    return top_other
}

proc hap_p5_diag_window_cells {lower_name upper_name} {
    set lower [get_tiles -quiet $lower_name]
    set upper [get_tiles -quiet $upper_name]
    hap_p5_diag_require_count "lower tile $lower_name" $lower 1
    hap_p5_diag_require_count "upper tile $upper_name" $upper 1
    set x0 [get_property GRID_POINT_X $lower]
    set y0 [get_property GRID_POINT_Y $lower]
    set x1 [get_property GRID_POINT_X $upper]
    set y1 [get_property GRID_POINT_Y $upper]
    set min_x [expr {min($x0, $x1)}]
    set max_x [expr {max($x0, $x1)}]
    set min_y [expr {min($y0, $y1)}]
    set max_y [expr {max($y0, $y1)}]
    set tiles [get_tiles -quiet -filter [format \
        {GRID_POINT_X >= %d && GRID_POINT_X <= %d && GRID_POINT_Y >= %d && GRID_POINT_Y <= %d} \
        $min_x $max_x $min_y $max_y]]
    set sites [get_sites -quiet -of_objects $tiles]
    set direct [get_cells -quiet -of_objects $sites]
    set bels [get_bels -quiet -of_objects $sites]
    set via_bels [get_cells -quiet -of_objects $bels]
    set names [lsort -dictionary -unique [concat \
        [hap_p5_diag_object_names $direct] [hap_p5_diag_object_names $via_bels]]]
    set cells [get_cells -quiet $names -filter {
        IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
        REF_NAME != GND && REF_NAME != VCC}]
    if {[llength $cells] == 0} {error "Empty congestion window $lower_name:$upper_name"}
    return $cells
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P5 diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P5 diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_failed_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P5 diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p5_diag_manifest $input_sha 4 $expected_input_sha p5_diag_input]
foreach required [list $dcp $failed_output_sha [file normalize [info script]] \
        [file normalize $::env(HAP_P5_DIAG_LAUNCHER)]] {
    if {![dict exists $frozen $required]} {
        error "Required P5 diagnosis input is absent: $required"
    }
}
set failed_entries [hap_p5_diag_manifest $failed_output_sha 25 \
    $expected_failed_output_sha p5_failed_output]
if {[hap_p5_diag_sha256 $dcp] ne $expected_dcp_sha} {
    error "P5 diagnostic DCP identity mismatch"
}
set failed_dir [file dirname $failed_output_sha]
set failed_summary [file join $failed_dir summary.txt]
set failed_launcher [file join $failed_dir launcher_status.txt]
foreach required [list $dcp $failed_summary $failed_launcher \
        [file join $failed_dir congestion_post_place.rpt]] {
    if {![dict exists $failed_entries $required]} {
        error "Required failed-placement evidence is absent: $required"
    }
}
foreach literal [list status=FAIL route_eligible=0 acceptance_evidence=0 \
        checkpoint_written=0 diagnostic_checkpoint_written=1 dsp48e2=5453 \
        uram288=752 slr_dsp48e2=1862\ 1781\ 1810 \
        slr_uram288=224\ 224\ 304 post_place_drc_errors=0 data_bufg=0 \
        congestion_level5_or_higher_windows=20 \
        congestion_level6_or_higher_windows=8] {
    hap_p5_diag_require_line $failed_summary $literal
}
foreach literal {status=FAIL route_eligible=0 acceptance_evidence=0
        checkpoint_written=0 bitstream_generated=0 final_exit_code=1} {
    hap_p5_diag_require_line $failed_launcher $literal
}

set open_start [clock milliseconds]
open_checkpoint $dcp
set open_elapsed [expr {[clock milliseconds] - $open_start}]
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e"} {
    error "P5 diagnostic part mismatch"
}
if {[get_property TOP [current_design]] ne "hap_attention_mlp_production_core"} {
    error "P5 diagnostic top mismatch"
}
hap_p5_diag_require_count pblocks [get_pblocks -quiet] 23

set all_primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set all_dsp [filter $all_primitives {REF_NAME == DSP48E2}]
set all_uram [filter $all_primitives {REF_NAME == URAM288}]
hap_p5_diag_require_count dsp48e2 $all_dsp 5453
hap_p5_diag_require_count uram288 $all_uram 752

set pblock_fh [open [file join $out pblock_ranges.tsv] w]
puts $pblock_fh "pblock\tmember_count\tgrid_ranges"
foreach pblock [lsort -dictionary [get_pblocks -quiet]] {
    puts $pblock_fh [join [list [get_property NAME $pblock] \
        [llength [get_cells -quiet -of_objects $pblock]] \
        [get_property GRID_RANGES $pblock]] "\t"]
}
close $pblock_fh

set groups [list \
    attn_region0 [hap_p5_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region0_cols2_3] \
    attn_region1 [hap_p5_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7] \
    attn_region2 [hap_p5_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11] \
    attn_region3 [hap_p5_diag_primitives \
        u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region3_cols12_13] \
    postprocess [hap_p5_diag_primitives \
        u_compute/u_attention/u_compute/u_postprocess_store] \
    mlp_input [hap_p5_diag_primitives u_compute/u_mlp/u_input_frontend] \
    mlp_gather [hap_p5_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_gather] \
    mlp_repack [hap_p5_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_projection_repack] \
    mlp_swiglu [hap_p5_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu] \
    mlp_branch0 [hap_p5_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch0] \
    mlp_branch1 [hap_p5_diag_primitives \
        u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch1] \
    paired_weight [hap_p5_diag_primitives u_paired_weight]]
set resource_fh [open [file join $out hierarchy_resources.tsv] w]
puts $resource_fh \
    "group\ttotal_slr0_1_2_unknown\tlut_slr0_1_2_unknown\tff_slr0_1_2_unknown\tdsp_slr0_1_2_unknown\turam_slr0_1_2_unknown\tramb36_slr0_1_2_unknown\tramb18_slr0_1_2_unknown\ttile_bbox_x0_y0_x1_y1"
foreach {label cells} $groups {
    hap_p5_diag_resource_row $resource_fh $label $cells
}
close $resource_fh

set bank_fh [open [file join $out postprocess_bank_resources.tsv] w]
puts $bank_fh \
    "group\ttotal_slr0_1_2_unknown\tlut_slr0_1_2_unknown\tff_slr0_1_2_unknown\tdsp_slr0_1_2_unknown\turam_slr0_1_2_unknown\tramb36_slr0_1_2_unknown\tramb18_slr0_1_2_unknown\ttile_bbox_x0_y0_x1_y1"
for {set bank 0} {$bank < 16} {incr bank} {
    set name "u_compute/u_attention/u_compute/u_postprocess_store/g_row_bank\[$bank\].u_bank"
    hap_p5_diag_resource_row $bank_fh post_bank${bank} \
        [hap_p5_diag_primitives $name]
}
close $bank_fh

set windows {
    north_global CLEM_X14Y384 CLEM_X44Y447
    south_global CLEL_R_X10Y456 CLEM_X40Y519
    north_long CLEL_R_X13Y375 CLEL_R_X43Y438
    south_long CLEL_R_X12Y453 CLEL_R_X41Y516
    east_long CLEL_R_X12Y451 CLEL_R_X41Y514
    west_long CLEL_R_X12Y384 CLEL_R_X41Y447
    east_short CLEL_R_X35Y437 CLEL_R_X65Y500
    west_short CLEL_R_X9Y476 CLEM_X39Y539
}
set window_fh [open [file join $out window_category_counts.tsv] w]
set ref_fh [open [file join $out window_reference_counts.tsv] w]
puts $window_fh "window\tlower_tile\tupper_tile\tcategory\tprimitive_count"
puts $ref_fh "window\tcategory\tref_name\tprimitive_count"
set window_count 0
foreach {label lower upper} $windows {
    incr window_count
    set cells [hap_p5_diag_window_cells $lower $upper]
    set category_counts [dict create]
    set reference_counts [dict create]
    foreach name [get_property NAME $cells] ref [get_property REF_NAME $cells] {
        set category [hap_p5_diag_category $name]
        dict incr category_counts $category
        dict incr reference_counts "$category\t$ref"
    }
    foreach category [lsort -dictionary [dict keys $category_counts]] {
        puts $window_fh "$label\t$lower\t$upper\t$category\t[dict get $category_counts $category]"
    }
    foreach key [lsort -dictionary [dict keys $reference_counts]] {
        puts $ref_fh "$label\t$key\t[dict get $reference_counts $key]"
    }
}
close $window_fh
close $ref_fh

report_timing_summary -delay_type min_max -max_paths 100 \
    -file [file join $out timing_post_place.rpt]
report_timing -delay_type max -max_paths 50 -nworst 1 \
    -file [file join $out timing_setup_paths.rpt]
report_timing -delay_type min -max_paths 50 -nworst 1 \
    -file [file join $out timing_hold_paths.rpt]
set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {error "P5 timing paths are empty"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]

set slr_dsp {0 0 0 0}
set slr_uram {0 0 0 0}
foreach cell $all_dsp slr_value [get_property SLR_INDEX $all_dsp] {
    set index [hap_p5_diag_slr_index $slr_value]
    lset slr_dsp $index [expr {[lindex $slr_dsp $index] + 1}]
}
foreach cell $all_uram slr_value [get_property SLR_INDEX $all_uram] {
    set index [hap_p5_diag_slr_index $slr_value]
    lset slr_uram $index [expr {[lindex $slr_uram $index] + 1}]
}
set status [expr {$slr_dsp eq {1862 1781 1810 0} &&
    $slr_uram eq {224 224 304 0} && $window_count == 8 ?
    "V5_P10_P5_CONGESTION_DIAGNOSIS_PASS" : "FAIL"}]
set summary_fh [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P5_CONGESTION_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_P5_PLACEMENT \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 4 \
        failed_output_manifest_sha256 $expected_failed_output_sha \
        failed_output_entries 25 failed_placement_verified 1 jobs $jobs \
        pblock_count 23 dsp48e2 5453 uram288 752 \
        slr_dsp48e2 [lrange $slr_dsp 0 2] \
        slr_uram288 [lrange $slr_uram 0 2] level6_windows_profiled $window_count \
        post_place_wns_ns $wns post_place_whs_ns $whs \
        open_checkpoint_elapsed_ms $open_elapsed floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 \
        route_eligible 0 status $status] {
    puts $summary_fh "$key=$value"
}
close $summary_fh
close_design
if {$status eq "FAIL"} {error "P5 congestion diagnosis gate failed"}
puts "P5_CONGESTION_DIAGNOSIS_PASS"
