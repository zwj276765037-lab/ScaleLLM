# Read-only timing-root diagnosis for the terminal P9 placement. This flow
# extracts actionable setup/hold endpoint clusters without changing the design.

set dcp [file normalize $::env(HAP_P9_TIMING_DCP)]
set out [file normalize $::env(HAP_P9_TIMING_DIR)]
set input_sha [file normalize $::env(HAP_P9_TIMING_INPUT_SHA)]
set expected_input_sha $::env(HAP_P9_TIMING_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P9_TIMING_DCP_SHA256)
set recovery_output_sha [file normalize \
    $::env(HAP_P9_TIMING_RECOVERY_OUTPUT_SHA)]
set expected_recovery_output_sha \
    $::env(HAP_P9_TIMING_RECOVERY_OUTPUT_SHA256)
set expected_launcher [file normalize $::env(HAP_P9_TIMING_LAUNCHER)]
set diagnosis_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_p9_timing_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_p9_timing_read {path label} {
    hap_p9_timing_nonempty $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p9_timing_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p9_timing_manifest {path expected_count expected_sha label} {
    if {[hap_p9_timing_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_p9_timing_read $path $label] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed $label manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate $label manifest path: $normalized"
        }
        hap_p9_timing_nonempty $normalized "$label member"
        if {[hap_p9_timing_sha256 $normalized] ne $expected} {
            error "$label member SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "$label manifest cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_p9_timing_require_line {path literal} {
    set count 0
    foreach line [split [hap_p9_timing_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P9 timing evidence mismatch: path=$path literal=$literal count=$count"
    }
}

proc hap_p9_timing_pin_cell_name {pin_name} {
    set pins [get_pins -quiet $pin_name]
    if {[llength $pins] != 1} {return UNRESOLVED}
    set cells [get_cells -quiet -of_objects $pins]
    if {[llength $cells] != 1} {return UNRESOLVED}
    return [get_property NAME $cells]
}

proc hap_p9_timing_cell_slr {cell_name} {
    if {$cell_name eq "UNRESOLVED"} {return UNRESOLVED}
    set cells [get_cells -quiet $cell_name]
    if {[llength $cells] != 1} {return UNRESOLVED}
    set index [get_property SLR_INDEX $cells]
    if {![string is integer -strict $index] || $index < 0 || $index > 2} {
        return UNRESOLVED
    }
    return SLR$index
}

proc hap_p9_timing_category {cell_name} {
    if {[string match *u_attention*u_projection*u_center12*u_region2_cols8_11* \
            $cell_name]} {return attention_projection_region2}
    if {[string match *u_attention*u_projection*u_center12*u_region3_cols12_13* \
            $cell_name]} {return attention_projection_region3}
    if {[string match *u_attention*u_projection*u_center12*u_region1_cols4_7* \
            $cell_name]} {return attention_projection_region1}
    if {[string match *u_attention*u_projection* $cell_name]} {
        return attention_projection_other
    }
    if {[string match *u_attention*u_postprocess_store* $cell_name]} {
        return attention_postprocess_store
    }
    if {[string match *u_attention*u_kv_quantizer4* $cell_name]} {
        return attention_kv_quantizer
    }
    if {[string match *u_attention* $cell_name]} {return attention_other}
    if {[string match *u_mlp*u_input_frontend*g_quant* $cell_name]} {
        return mlp_input_quantizer
    }
    if {[string match *u_mlp*u_input_frontend*u_hadamard* $cell_name]} {
        return mlp_input_hadamard
    }
    if {[string match *u_mlp*u_gate_scheduler*u_swiglu* $cell_name]} {
        return mlp_swiglu
    }
    if {[string match *u_mlp* $cell_name]} {return mlp_other}
    return shell_or_other
}

proc hap_p9_timing_write_paths {paths path cross_var unresolved_var pairs_var} {
    upvar 1 $cross_var cross_count
    upvar 1 $unresolved_var unresolved_count
    upvar 1 $pairs_var pair_counts
    set cross_count 0
    set unresolved_count 0
    set pair_counts [dict create]
    set fp [open $path w]
    puts $fp "rank\tslack_ns\tstart_slr\tend_slr\tcross_slr\tstart_category\tend_category\tstart_pin\tend_pin\tstart_cell\tend_cell"
    set rank 0
    foreach timing_path $paths {
        incr rank
        set slack [get_property SLACK $timing_path]
        set start_pin [get_property STARTPOINT_PIN $timing_path]
        set end_pin [get_property ENDPOINT_PIN $timing_path]
        set start_cell [hap_p9_timing_pin_cell_name $start_pin]
        set end_cell [hap_p9_timing_pin_cell_name $end_pin]
        set start_slr [hap_p9_timing_cell_slr $start_cell]
        set end_slr [hap_p9_timing_cell_slr $end_cell]
        set cross 0
        if {$start_slr eq "UNRESOLVED" || $end_slr eq "UNRESOLVED"} {
            incr unresolved_count
        } elseif {$start_slr ne $end_slr} {
            set cross 1
            incr cross_count
        }
        set start_category [hap_p9_timing_category $start_cell]
        set end_category [hap_p9_timing_category $end_cell]
        dict incr pair_counts ${start_category}->${end_category}
        puts $fp [join [list $rank $slack $start_slr $end_slr $cross \
            $start_category $end_category $start_pin $end_pin $start_cell \
            $end_cell] "\t"]
    }
    close $fp
}

proc hap_p9_timing_write_pairs {pairs path marker} {
    set fp [open $path w]
    puts $fp "status=$marker"
    foreach pair [lsort -dictionary [dict keys $pairs]] {
        puts $fp "$pair=[dict get $pairs $pair]"
    }
    close $fp
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P9 timing diagnosis requires HAP_JOBS=32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P9 timing diagnosis requires a fresh Vivado process"
}
if {![file exists $out] || ![file isdirectory $out]} {
    error "Missing P9 timing evidence directory: $out"
}
set_param general.maxThreads $jobs

set frozen [hap_p9_timing_manifest $input_sha 4 $expected_input_sha \
    p9_timing_input]
foreach required [list $dcp $recovery_output_sha $diagnosis_script \
        $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "Required P9 timing input absent from manifest: $required"
    }
}
if {[hap_p9_timing_sha256 $dcp] ne $expected_dcp_sha} {
    error "P9 timing DCP identity mismatch"
}

set recovery_entries [hap_p9_timing_manifest $recovery_output_sha -1 \
    $expected_recovery_output_sha p9_recovery_output]
set recovery_dir [file dirname $recovery_output_sha]
set recovery_summary [file join $recovery_dir summary.txt]
set recovery_launcher [file join $recovery_dir launcher_status.txt]
set recovery_congestion [file join $recovery_dir congestion_post_place.rpt]
foreach required [list $recovery_summary $recovery_launcher \
        $recovery_congestion] {
    if {![dict exists $recovery_entries $required]} {
        error "Required P9 recovery evidence absent from manifest: $required"
    }
}
foreach literal [list status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS \
        input_dcp=$dcp input_dcp_sha256=$expected_dcp_sha \
        congestion_level5_or_higher_windows=24 \
        congestion_level6_or_higher_windows=12 fast_gate_ok=0 \
        acceptance_evidence=0 route_eligible=0 \
        implementation_commands_run=0 checkpoint_written=0] {
    hap_p9_timing_require_line $recovery_summary $literal
}
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0
        input_sha_recheck_exit_code=0 failed_place_recheck_exit_code=0
        input_manifest_sha_match=1 diagnosis_gate_exit_code=0
        floorplan_mutated=0 implementation_commands_run=0
        checkpoint_written=0 route_eligible=0} {
    hap_p9_timing_require_line $recovery_launcher $literal
}

set flow_start_ms [clock milliseconds]
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[llength [get_pblocks -quiet]] != 21} {
    error "P9 timing checkpoint must contain exactly 21 pblocks"
}

set phase_start_ms [clock milliseconds]
set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 500 \
    -nworst 20]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 500 \
    -nworst 20]
if {[llength $setup_paths] < 100 || [llength $hold_paths] < 100} {
    error "P9 timing diagnosis returned too few paths: setup=[llength $setup_paths] hold=[llength $hold_paths]"
}
set path_query_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]

set worst_setup [lindex $setup_paths 0]
set worst_hold [lindex $hold_paths 0]
set wns [get_property SLACK $worst_setup]
set whs [get_property SLACK $worst_hold]
set setup_cross_slr 0
set setup_unresolved 0
set setup_pairs [dict create]
hap_p9_timing_write_paths $setup_paths [file join $out setup_paths.tsv] \
    setup_cross_slr setup_unresolved setup_pairs
set hold_cross_slr 0
set hold_unresolved 0
set hold_pairs [dict create]
hap_p9_timing_write_paths $hold_paths [file join $out hold_paths.tsv] \
    hold_cross_slr hold_unresolved hold_pairs
hap_p9_timing_write_pairs $setup_pairs [file join $out setup_category_pairs.txt] \
    P9_TIMING_SETUP_CATEGORY_PAIRS_PASS
hap_p9_timing_write_pairs $hold_pairs [file join $out hold_category_pairs.txt] \
    P9_TIMING_HOLD_CATEGORY_PAIRS_PASS

set phase_start_ms [clock milliseconds]
report_timing_summary -delay_type min_max -max_paths 500 -nworst 20 \
    -report_unconstrained -file [file join $out timing_summary_post_place.rpt]
report_timing -delay_type max -max_paths 500 -nworst 20 \
    -file [file join $out timing_setup_post_place.rpt]
report_timing -delay_type min -max_paths 500 -nworst 20 \
    -file [file join $out timing_hold_post_place.rpt]
report_high_fanout_nets -timing -load_types -max_nets 300 \
    -file [file join $out high_fanout_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_place.rpt]
set report_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]

set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        evidence_class READ_ONLY_P9_TIMING_ROOT_DIAGNOSIS jobs $jobs \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 4 \
        recovery_output_manifest $recovery_output_sha \
        recovery_output_manifest_sha256 $expected_recovery_output_sha \
        recovery_output_entries [dict size $recovery_entries] \
        recovery_terminal_fail_verified 1 pblock_count 21 \
        setup_path_count [llength $setup_paths] \
        hold_path_count [llength $hold_paths] \
        setup_cross_slr_count $setup_cross_slr \
        hold_cross_slr_count $hold_cross_slr \
        setup_unresolved_endpoint_count $setup_unresolved \
        hold_unresolved_endpoint_count $hold_unresolved \
        setup_category_pair_count [dict size $setup_pairs] \
        hold_category_pair_count [dict size $hold_pairs] \
        post_place_wns_ns $wns post_place_whs_ns $whs \
        source_congestion_level5_or_higher_windows 24 \
        source_congestion_level6_or_higher_windows 12 \
        acceptance_evidence 0 route_eligible 0 floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        path_query_elapsed_ms $path_query_elapsed_ms \
        report_elapsed_ms $report_elapsed_ms total_elapsed_ms $total_elapsed_ms \
        status P9_TIMING_ROOT_DIAGNOSIS_PASS] {
    puts $fp "$key=$value"
}
close $fp
puts "P9_TIMING_ROOT_DIAGNOSIS WNS=$wns WHS=$whs SETUP_CROSS_SLR=$setup_cross_slr HOLD_CROSS_SLR=$hold_cross_slr"
close_design
