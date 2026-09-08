# Read-only recovery diagnosis for a completed P9 placement whose original
# process failed in the metrics adapter after writing a diagnostic checkpoint.

set dcp [file normalize $::env(HAP_P9_RECOVERY_DCP)]
set out [file normalize $::env(HAP_P9_RECOVERY_DIR)]
set input_sha [file normalize $::env(HAP_P9_RECOVERY_INPUT_SHA)]
set expected_input_sha $::env(HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P9_RECOVERY_DCP_SHA256)
set failed_output_sha [file normalize \
    $::env(HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA)]
set expected_failed_output_sha \
    $::env(HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA256)
set selector_lib [file normalize $::env(HAP_P9_RECOVERY_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_P9_RECOVERY_FINE_LIB)]
set composite_lib [file normalize $::env(HAP_P9_RECOVERY_COMPOSITE_LIB)]
set expected_launcher [file normalize $::env(HAP_P9_RECOVERY_LAUNCHER)]
set diagnosis_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_p9_recovery_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_p9_recovery_read {path label} {
    hap_p9_recovery_nonempty $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p9_recovery_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_p9_recovery_manifest {path expected_count expected_sha label} {
    if {[hap_p9_recovery_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_p9_recovery_read $path $label] "\n"] {
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
        hap_p9_recovery_nonempty $normalized "$label member"
        if {[hap_p9_recovery_sha256 $normalized] ne $expected} {
            error "$label member SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "$label manifest cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_p9_recovery_require_line {path literal} {
    set count 0
    foreach line [split [hap_p9_recovery_read $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "P9 recovery evidence mismatch: path=$path literal=$literal count=$count"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P9 recovery diagnosis requires HAP_JOBS=32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P9 recovery diagnosis requires a fresh Vivado process"
}
if {![file exists $out] || ![file isdirectory $out]} {
    error "Missing P9 recovery evidence directory: $out"
}
set_param general.maxThreads $jobs

set frozen [hap_p9_recovery_manifest $input_sha 7 $expected_input_sha \
    p9_recovery_input]
foreach required [list $dcp $failed_output_sha $selector_lib $fine_lib \
        $composite_lib $diagnosis_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "Required P9 recovery input absent from manifest: $required"
    }
}
if {[hap_p9_recovery_sha256 $dcp] ne $expected_dcp_sha} {
    error "P9 recovery DCP identity mismatch"
}

set failed_entries [hap_p9_recovery_manifest $failed_output_sha -1 \
    $expected_failed_output_sha failed_p9_place_output]
set failed_dir [file dirname $failed_output_sha]
set failed_summary [file join $failed_dir summary.txt]
set failed_launcher [file join $failed_dir launcher_status.txt]
foreach required [list $dcp $failed_summary $failed_launcher] {
    if {![dict exists $failed_entries $required]} {
        error "Required failed-placement evidence absent from output manifest: $required"
    }
}
foreach literal [list failure_stage=post_place_live_rediscovery \
        place_design_completed=1 diagnostic_checkpoint_written=1 \
        acceptance_evidence=0 route_eligible=0 checkpoint_written=0 \
        post_rediscovery_error=V5\ fine19\ physical\ metrics\ are\ missing\ pblock\ record:\ pb_v5_center_nonprojection_dsp_slr1 \
        status=FAIL] {
    hap_p9_recovery_require_line $failed_summary $literal
}
foreach literal {status=FAIL flow_mode=accept acceptance_evidence=0
        route_eligible=0 final_exit_code=1 vivado_exit_code=1
        input_sha_recheck_exit_code=0
        composite21_pre_place_recheck_exit_code=0
        input_manifest_sha_match=1 place_gate_exit_code=1
        checkpoint_written=0 bitstream_generated=0} {
    hap_p9_recovery_require_line $failed_launcher $literal
}

source $selector_lib
source $fine_lib
source $composite_lib
set flow_start_ms [clock milliseconds]
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[llength [get_pblocks -quiet]] != 21} {
    error "P9 recovery checkpoint must contain exactly 21 pblocks"
}

set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set fine_plan [hap_v5_fine19::discover $base_plan 1]
set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan 1]
set discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors_base.txt] P9_RECOVERY_BASE_SELECTORS_PASS
hap_v5_fine19::write_discovery $fine_plan \
    [file join $out selectors_fine19.txt] P9_RECOVERY_FINE19_SELECTORS_PASS
hap_v5_composite21::write_discovery $composite_plan \
    [file join $out selectors_composite21.txt] P9_RECOVERY_COMPOSITE21_SELECTORS_PASS

set phase_start_ms [clock milliseconds]
set pblock_audit [hap_v5_composite21::audit \
    $base_plan $fine_plan $composite_plan 1]
hap_v5_composite21::write_audit $pblock_audit \
    [file join $out pblocks.txt] P9_RECOVERY_PBLOCKS_PASS
set metrics [hap_v5_composite21::physical_metrics $pblock_audit]
set audit_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]

set attention_direct_audit [hap_v5_floorplan::physical_slr_audit_for_cells \
    [dict get $composite_plan attention_direct_primitives]]
set attention_direct_slr_counts [dict get $attention_direct_audit slr_counts]
set attention_direct_placement_ok [expr {
    [dict get $attention_direct_audit total] ==
        [dict get $composite_plan attention_direct_count] &&
    [dict get $attention_direct_audit direct_slr_empty] == 0}]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set phase_start_ms [clock milliseconds]
set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set congestion_text [hap_p9_recovery_read $congestion_path congestion]
set congestion_schema_header_count 0
set congestion_data_row_count 0
set congestion_level5_count 0
set congestion_level6_count 0
foreach line [split $congestion_text "\n"] {
    if {[regexp {^[[:space:]]*\|[[:space:]]*Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level[[:space:]]*\|[[:space:]]*Window[[:space:]]*\|} \
            $line]} {
        incr congestion_schema_header_count
        continue
    }
    if {![regexp {^[[:space:]]*\|[[:space:]]*(North|South|East|West)[[:space:]]*\|[[:space:]]*(Global|Long|Short)[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|[[:space:]]*\([^|]+\)[[:space:]]*\|} \
            $line -> direction type level]} {
        continue
    }
    incr congestion_data_row_count
    if {$level >= 5} {incr congestion_level5_count}
    if {$level >= 6} {incr congestion_level6_count}
}
set congestion_clean_marker [expr {
    [string first "No congestion windows are found above level 5" \
        $congestion_text] >= 0 ||
    [string first "No effective congestion windows are found above level 5" \
        $congestion_text] >= 0}]
set congestion_schema_ok [expr {$congestion_schema_header_count == 1 &&
    ($congestion_data_row_count >= 1 || $congestion_clean_marker)}]
if {!$congestion_schema_ok} {
    error "P9 recovery congestion report schema is unrecognized"
}

set worst_setup [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set worst_hold [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {[llength $worst_setup] == 0 || [llength $worst_hold] == 0} {
    error "P9 recovery timing queries returned no paths"
}
set wns [get_property SLACK $worst_setup]
set whs [get_property SLACK $worst_hold]

set slr_dsp [dict get $metrics slr_dsp]
set slr_uram [dict get $metrics slr_uram]
set resource_ok [expr {
    [dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    $slr_dsp eq {1862 1781 1810} && $slr_uram eq {224 224 304}}]
set selector_deltas_ok [expr {
    abs([dict get $composite_plan fine_member_delta]) <= 65536 &&
    abs([dict get $composite_plan mlp_residual_delta]) <= 65536 &&
    abs([dict get $composite_plan central_island_delta]) <= 65536 &&
    abs([dict get $composite_plan mlp_remaining_delta]) <= 65536 &&
    abs([dict get $composite_plan attention_direct_delta]) <= 65536}]
set placement_ok [expr {
    [hap_v5_composite21::physical_ok $metrics] &&
    [dict get $pblock_audit ok] == 1 &&
    [dict get $pblock_audit pblock_count] == 21 &&
    [dict get $pblock_audit placed_wrong] == 0 &&
    [dict get $pblock_audit optimizer_extra_count] <= 4096 &&
    $attention_direct_placement_ok}]
set no_level6 [expr {$congestion_level6_count == 0}]
set level5_screen_ok [expr {$congestion_level5_count <= 1}]
set fast_gate_ok [expr {$resource_ok && $selector_deltas_ok && $placement_ok &&
    $data_bufg == 0 && $no_level6 && $level5_screen_ok}]
set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set status P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        evidence_class READ_ONLY_P9_POST_PLACE_RECOVERY \
        jobs $jobs input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 7 \
        failed_place_output_manifest $failed_output_sha \
        failed_place_output_manifest_sha256 $expected_failed_output_sha \
        failed_place_output_entries [dict size $failed_entries] \
        failed_place_verified 1 place_design_completed_upstream 1 \
        contract_variant [dict get $composite_plan contract_variant] \
        fine_contract_variant [dict get $fine_plan contract_variant] \
        pblock_count [dict get $pblock_audit pblock_count] \
        pblock_member_count [dict get $pblock_audit member_count] \
        pblock_member_overlap [dict get $pblock_audit member_overlap] \
        pblock_optimizer_extras [dict get $pblock_audit optimizer_extra_count] \
        pblock_dsp_coverage [dict get $pblock_audit dsp_coverage] \
        pblock_uram_coverage [dict get $pblock_audit uram_coverage] \
        pblock_wrong_slr [dict get $pblock_audit placed_wrong] \
        fine_member_delta [dict get $composite_plan fine_member_delta] \
        mlp_residual_delta [dict get $composite_plan mlp_residual_delta] \
        central_anchor_range [dict get $composite_plan central_anchor_range] \
        central_island_count [dict get $composite_plan central_island_count] \
        central_island_delta [dict get $composite_plan central_island_delta] \
        central_island_dsp [dict get $composite_plan central_island_dsp] \
        mlp_remaining_count [dict get $composite_plan mlp_remaining_count] \
        mlp_remaining_delta [dict get $composite_plan mlp_remaining_delta] \
        center_dsp_remaining [dict get $composite_plan center_dsp_remaining_dsp] \
        central_partition_ok [dict get $composite_plan central_partition_ok] \
        attention_direct_count [dict get $composite_plan attention_direct_count] \
        attention_direct_delta [dict get $composite_plan attention_direct_delta] \
        attention_direct_slr0 [lindex $attention_direct_slr_counts 0] \
        attention_direct_slr1 [lindex $attention_direct_slr_counts 1] \
        attention_direct_slr2 [lindex $attention_direct_slr_counts 2] \
        attention_direct_unresolved \
            [dict get $attention_direct_audit direct_slr_empty] \
        attention_direct_placement_ok $attention_direct_placement_ok \
        dsp48e2 [dict get $base_plan total_dsp] \
        uram288 [dict get $base_plan total_uram] \
        mlp_kernel_dsp48e2 [dict get $base_plan kernel_dsp] \
        slr0_dsp48e2 [lindex $slr_dsp 0] \
        slr1_dsp48e2 [lindex $slr_dsp 1] \
        slr2_dsp48e2 [lindex $slr_dsp 2] \
        slr0_uram288 [lindex $slr_uram 0] \
        slr1_uram288 [lindex $slr_uram 1] \
        slr2_uram288 [lindex $slr_uram 2] \
        unplaced_primitives [dict get $metrics unplaced] \
        wrong_slr_primitives [dict get $metrics wrong_total] \
        p9_central_island_wrong_slr [dict get $metrics central_island_wrong] \
        p9_center_dsp_remaining_wrong_slr \
            [dict get $metrics center_dsp_remaining_wrong] \
        p9_mlp_remaining_wrong_slr [dict get $metrics mlp_remaining_wrong] \
        additional_wrong_slr [dict get $metrics additional_wrong] \
        clock_bufg $clock_bufg data_bufg $data_bufg \
        congestion_level5_or_higher_windows $congestion_level5_count \
        congestion_level6_or_higher_windows $congestion_level6_count \
        congestion_schema_header_count $congestion_schema_header_count \
        congestion_data_rows_recognized $congestion_data_row_count \
        congestion_schema_ok $congestion_schema_ok \
        post_place_wns_ns $wns post_place_whs_ns $whs \
        resource_ok $resource_ok selector_deltas_ok $selector_deltas_ok \
        placement_ok $placement_ok level5_screen_ok $level5_screen_ok \
        level6_congestion_ok $no_level6 fast_gate_ok $fast_gate_ok \
        acceptance_evidence 0 route_eligible 0 floorplan_mutated 0 \
        implementation_commands_run 0 checkpoint_written 0 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        discovery_elapsed_ms $discovery_elapsed_ms \
        audit_elapsed_ms $audit_elapsed_ms \
        congestion_elapsed_ms $congestion_elapsed_ms \
        total_elapsed_ms $total_elapsed_ms status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "P9_POST_PLACE_RECOVERY WNS=$wns WHS=$whs LEVEL5=$congestion_level5_count LEVEL6=$congestion_level6_count FAST_GATE=$fast_gate_ok"
close_design
