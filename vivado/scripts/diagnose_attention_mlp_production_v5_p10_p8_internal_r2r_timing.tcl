# Read-only register-to-register timing diagnosis for the rejected P8 placement.
# Explicit register collections exclude every top-level input and output path.

set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P8_INTERNAL_DCP)]
set out [file normalize $::env(HAP_P8_INTERNAL_DIR)]
set input_sha [file normalize $::env(HAP_P8_INTERNAL_INPUT_SHA)]
set expected_input_sha $::env(HAP_P8_INTERNAL_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P8_INTERNAL_DCP_SHA256)
set failed_output_sha [file normalize $::env(HAP_P8_INTERNAL_FAILED_OUTPUT_SHA)]
set expected_failed_output_sha $::env(HAP_P8_INTERNAL_FAILED_OUTPUT_SHA256)
set diagnosis_output_sha [file normalize \
    $::env(HAP_P8_INTERNAL_DIAGNOSIS_OUTPUT_SHA)]
set expected_diagnosis_output_sha \
    $::env(HAP_P8_INTERNAL_DIAGNOSIS_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P8_INTERNAL_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_P8_INTERNAL_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p8_internal_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p8_internal_metric {clock_name delay_type report_path} {
    set clocks [get_clocks -quiet $clock_name]
    if {[llength $clocks] != 1} {
        error "P8 internal timing clock is not unique: $clock_name"
    }
    set registers [all_registers -clock $clocks]
    if {[llength $registers] == 0} {
        error "P8 internal timing register set is empty: $clock_name"
    }
    set paths [get_timing_paths -quiet -delay_type $delay_type \
        -from $registers -to $registers -max_paths 1 -nworst 1]
    if {[llength $paths] != 1} {
        error "P8 internal timing path is missing: $clock_name/$delay_type"
    }
    set path [lindex $paths 0]
    set start_pin [get_property STARTPOINT_PIN $path]
    set end_pin [get_property ENDPOINT_PIN $path]
    if {[llength [get_ports -quiet $start_pin]] != 0 ||
        [llength [get_ports -quiet $end_pin]] != 0} {
        error "P8 internal query selected a top-level port path: $clock_name/$delay_type"
    }
    if {[llength [get_cells -quiet -of_objects [get_pins -quiet $start_pin]]] != 1 ||
        [llength [get_cells -quiet -of_objects [get_pins -quiet $end_pin]]] != 1} {
        error "P8 internal query endpoints are not cell pins: $clock_name/$delay_type"
    }
    report_timing -delay_type $delay_type -from $registers -to $registers \
        -max_paths 20 -nworst 4 -path_type full_clock_expanded \
        -input_pins -file $report_path
    return [dict create slack [get_property SLACK $path] \
        startpoint $start_pin endpoint $end_pin]
}

if {![string match "2025.2*" [version -short]]} {
    error "P8 internal timing diagnosis requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P8 internal timing diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P8 internal timing diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_failed_output_sha $expected_diagnosis_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P8 internal timing diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $failed_output_sha $diagnosis_output_sha \
        $p10_proc_lib $audit_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P8 internal timing input absent from manifest: $required"
    }
}

set failed_outputs [hap_p10_verify_manifest $failed_output_sha -1 \
    $expected_failed_output_sha]
set failed_dir [file dirname $failed_output_sha]
set failed_summary_path [file join $failed_dir summary.txt]
foreach required [list $dcp $failed_summary_path] {
    if {![dict exists $failed_outputs $required]} {
        error "Mission 0104 output lineage is incomplete: $required"
    }
}
set failed_summary [hap_p10_parse_kv $failed_summary_path \
    "Mission 0104 summary"]
foreach {key expected} {
    stage V5_P10_P8_POST_PLACE_REDISCOVERY
    failure_stage post_place_live_rediscovery
    route_eligible 0
    diagnostic_checkpoint_written 1
    status FAIL
} {
    hap_p8_internal_require_kv $failed_summary $key $expected \
        "Mission 0104 summary"
}

set diagnosis_outputs [hap_p10_verify_manifest $diagnosis_output_sha -1 \
    $expected_diagnosis_output_sha]
set diagnosis_dir [file dirname $diagnosis_output_sha]
set diagnosis_summary_path [file join $diagnosis_dir summary.txt]
set diagnosis_launcher_path [file join $diagnosis_dir launcher_status.txt]
foreach required [list $diagnosis_summary_path $diagnosis_launcher_path] {
    if {![dict exists $diagnosis_outputs $required]} {
        error "Mission 0114 output lineage is incomplete: $required"
    }
}
set diagnosis_summary [hap_p10_parse_kv $diagnosis_summary_path \
    "Mission 0114 summary"]
foreach {key expected} {
    stage V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS
    evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP
    source_lineage_verified 1
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P8_POST_PLACE_READ_ONLY_DIAGNOSIS_COMPLETE
} {
    hap_p8_internal_require_kv $diagnosis_summary $key $expected \
        "Mission 0114 summary"
}
hap_p8_internal_require_kv $diagnosis_summary input_dcp $dcp \
    "Mission 0114 summary"
set diagnosis_launcher [hap_p10_parse_kv $diagnosis_launcher_path \
    "Mission 0114 launcher"]
hap_p8_internal_require_kv $diagnosis_launcher status PASS \
    "Mission 0114 launcher"

set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha ||
    [dict get $failed_outputs $dcp] ne $expected_dcp_sha} {
    error "P8 internal timing DCP identity mismatch"
}

open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P8 internal timing top/part mismatch: $top/$part"
}

foreach {clock_name period} {
    core_clk 10.000
    ddr0_clk 3.333
    ddr1_clk 3.333
} {
    set clocks [get_clocks -quiet $clock_name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P8 internal timing clock contract mismatch: $clock_name"
    }
}

set metrics [dict create]
foreach clock_name {core_clk ddr0_clk ddr1_clk} {
    dict set metrics $clock_name setup [hap_p8_internal_metric \
        $clock_name max [file join $out ${clock_name}_internal_setup.rpt]]
    dict set metrics $clock_name hold [hap_p8_internal_metric \
        $clock_name min [file join $out ${clock_name}_internal_hold.rpt]]
}

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P8_INTERNAL_R2R_TIMING_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        top_level_port_paths_included 0] {
    puts $summary "$key=$value"
}
foreach clock_name {core_clk ddr0_clk ddr1_clk} {
    foreach check {setup hold} {
        set metric [dict get $metrics $clock_name $check]
        puts $summary "${clock_name}_internal_${check}_wns_ns=[dict get $metric slack]"
        puts $summary "${clock_name}_internal_${check}_startpoint=[dict get $metric startpoint]"
        puts $summary "${clock_name}_internal_${check}_endpoint=[dict get $metric endpoint]"
    }
}
foreach {key value} {
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P8_INTERNAL_R2R_TIMING_DIAGNOSIS_COMPLETE
} {
    puts $summary "$key=$value"
}
close $summary
close_design

exit=0
