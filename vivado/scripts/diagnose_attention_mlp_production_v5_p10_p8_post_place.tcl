# Read-only physical diagnosis for the rejected Mission 0104 P8 placement.

set diag_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P8_DIAG_DCP)]
set out [file normalize $::env(HAP_P8_DIAG_DIR)]
set input_sha [file normalize $::env(HAP_P8_DIAG_INPUT_SHA)]
set expected_input_sha $::env(HAP_P8_DIAG_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P8_DIAG_DCP_SHA256)
set failed_output_sha [file normalize $::env(HAP_P8_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P8_FAILED_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P8_DIAG_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_P8_DIAG_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p8_diag_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "P8 post-place diagnosis requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P8 post-place diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P8 post-place diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_failed_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P8 post-place diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $failed_output_sha $p10_proc_lib $diag_script \
        $expected_launcher [file join [file dirname $failed_output_sha] \
            INPUT_SHA256SUMS]] {
    if {![dict exists $frozen $required]} {
        error "P8 diagnostic input absent from manifest: $required"
    }
}
set failed_outputs [hap_p10_verify_manifest $failed_output_sha -1 \
    $expected_failed_output_sha]
set failed_dir [file dirname $failed_output_sha]
set failed_summary_path [file join $failed_dir summary.txt]
set failed_launcher_path [file join $failed_dir launcher_status.txt]
set failed_input_sha [file join $failed_dir INPUT_SHA256SUMS]
foreach required [list $dcp $failed_summary_path $failed_launcher_path \
        $failed_input_sha] {
    if {![dict exists $failed_outputs $required]} {
        error "Mission 0104 output manifest is incomplete: $required"
    }
}
set failed_inputs [hap_p10_verify_manifest $failed_input_sha 12 \
    [dict get $failed_outputs $failed_input_sha]]
if {[dict size $failed_inputs] != 12} {
    error "Mission 0104 input lineage count mismatch"
}
set failed_summary [hap_p10_parse_kv $failed_summary_path \
    "Mission 0104 summary"]
foreach {key expected} {
    stage V5_P10_P8_POST_PLACE_REDISCOVERY
    flow_mode accept
    failure_stage post_place_live_rediscovery
    acceptance_evidence 0
    route_eligible 0
    checkpoint_written 0
    diagnostic_checkpoint_written 1
    pre_place_verified 1
    status FAIL
} {
    hap_p8_diag_require_kv $failed_summary $key $expected \
        "Mission 0104 summary"
}
set failed_launcher [hap_p10_parse_kv $failed_launcher_path \
    "Mission 0104 launcher"]
foreach {key expected} {
    status FAIL
    flow_mode accept
    acceptance_evidence 0
    route_eligible 0
    final_exit_code 1
    vivado_exit_code 1
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    place_gate_exit_code 1
    checkpoint_written 0
    implementation_commands_requested 1
    bitstream_generated 0
} {
    hap_p8_diag_require_kv $failed_launcher $key $expected \
        "Mission 0104 launcher"
}
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha ||
    [dict get $failed_outputs $dcp] ne $expected_dcp_sha} {
    error "P8 diagnostic DCP identity mismatch"
}

open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P8 diagnostic top/part mismatch: $top/$part"
}

set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_p10_congestion_counts \
    [hap_p10_read_nonempty $congestion_path "P8 congestion report"]]
set level5 [dict get $congestion level5]
set level6 [dict get $congestion level6]

set drc_path [file join $out drc_post_place.rpt]
report_drc -file $drc_path
set drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set timing_handle [open [file join $out timing_post_place.rpt] w]
puts $timing_handle $timing_text
close $timing_handle
report_timing -delay_type max -max_paths 100 -nworst 10 \
    -path_type full_clock_expanded -input_pins -file \
    [file join $out timing_setup_100.rpt]
report_timing -delay_type min -max_paths 100 -nworst 10 \
    -path_type full_clock_expanded -input_pins -file \
    [file join $out timing_hold_100.rpt]
report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]

set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "P8 diagnostic timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]
set setup_start [get_property STARTPOINT_PIN [lindex $setup_path 0]]
set setup_end [get_property ENDPOINT_PIN [lindex $setup_path 0]]
set hold_start [get_property STARTPOINT_PIN [lindex $hold_path 0]]
set hold_end [get_property ENDPOINT_PIN [lindex $hold_path 0]]

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_failure_stage post_place_live_rediscovery \
        source_output_manifest $failed_output_sha \
        source_output_manifest_sha256 $expected_failed_output_sha \
        source_input_manifest $failed_input_sha \
        source_input_manifest_sha256 \
            [dict get $failed_outputs $failed_input_sha] \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        pblock_count [llength [get_pblocks -quiet]] \
        post_place_drc_errors $drc_errors \
        congestion_level5_or_higher_windows $level5 \
        congestion_level6_or_higher_windows $level6 \
        post_place_wns_ns $wns post_place_whs_ns $whs \
        worst_setup_startpoint $setup_start worst_setup_endpoint $setup_end \
        worst_hold_startpoint $hold_start worst_hold_endpoint $hold_end \
        implementation_commands_run 0 checkpoint_written 0 route_eligible 0 \
        status V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS_COMPLETE] {
    puts $summary "$key=$value"
}
close $summary
close_design
