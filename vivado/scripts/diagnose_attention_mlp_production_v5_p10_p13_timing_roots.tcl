# Read-only timing-root diagnosis for the rejected P13 placement.

set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P13_TIMING_DCP)]
set out [file normalize $::env(HAP_P13_TIMING_DIR)]
set input_sha [file normalize $::env(HAP_P13_TIMING_INPUT_SHA)]
set expected_input_sha $::env(HAP_P13_TIMING_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P13_TIMING_DCP_SHA256)
set placement_output_sha [file normalize \
    $::env(HAP_P13_TIMING_PLACE_OUTPUT_SHA)]
set expected_placement_output_sha \
    $::env(HAP_P13_TIMING_PLACE_OUTPUT_SHA256)
set map_output_sha [file normalize $::env(HAP_P13_TIMING_MAP_OUTPUT_SHA)]
set expected_map_output_sha $::env(HAP_P13_TIMING_MAP_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P13_TIMING_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_P13_TIMING_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p13_timing_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p13_timing_category {name} {
    if {[string match */u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region0_cols2_3/* $name]} {return attn_region0}
    if {[string match */u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7/* $name]} {return attn_region1}
    if {[string match */u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/* $name]} {return attn_region2}
    if {[string match */u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region3_cols12_13/* $name]} {return attn_region3}
    if {[string match */u_attention/u_compute/g_projection_rtl.u_projection/* $name]} {return attn_projection}
    if {[string match */u_attention/* $name]} {return attention_other}
    if {[string match */u_mlp/*/u_swiglu/u_hadamard/* $name]} {return swiglu_hadamard}
    if {[string match */u_mlp/*/u_swiglu/* $name]} {return swiglu_other}
    if {[string match */u_mlp/*/u_gather/* $name]} {return mlp_gather}
    if {[string match */u_mlp/*/u_down_scheduler/* $name]} {return mlp_down_scheduler}
    if {[string match */u_mlp/* $name]} {return mlp_other}
    return top_or_io
}

proc hap_p13_timing_write_paths {paths path} {
    set fp [open $path w]
    puts $fp "rank\tslack_ns\tstart_category\tend_category\tstartpoint\tendpoint"
    set pairs [dict create]
    set rank 0
    set top_level_count 0
    foreach timing_path $paths {
        incr rank
        set slack [get_property SLACK $timing_path]
        set startpoint [get_property STARTPOINT_PIN $timing_path]
        set endpoint [get_property ENDPOINT_PIN $timing_path]
        set start_category [hap_p13_timing_category $startpoint]
        set end_category [hap_p13_timing_category $endpoint]
        dict incr pairs "${start_category}->${end_category}"
        if {[llength [get_ports -quiet $startpoint]] != 0 ||
            [llength [get_ports -quiet $endpoint]] != 0} {
            incr top_level_count
        }
        puts $fp [join [list $rank $slack $start_category $end_category \
            $startpoint $endpoint] "\t"]
    }
    close $fp
    return [dict create path_count $rank top_level_count $top_level_count \
        pairs $pairs]
}

if {![string match "2025.2*" [version -short]]} {
    error "P13 timing diagnosis requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P13 timing diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P13 timing diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_placement_output_sha $expected_map_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P13 timing diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $placement_output_sha $map_output_sha \
        $p10_proc_lib $audit_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P13 timing input absent from manifest: $required"
    }
}

set placement_outputs [hap_p10_verify_manifest $placement_output_sha -1 \
    $expected_placement_output_sha]
set placement_dir [file dirname $placement_output_sha]
set placement_summary_path [file join $placement_dir summary.txt]
set placement_launcher_path [file join $placement_dir launcher_status.txt]
foreach required [list $dcp $placement_summary_path $placement_launcher_path] {
    if {![dict exists $placement_outputs [file normalize $required]]} {
        error "Mission 0141 output manifest is incomplete: $required"
    }
}
set placement [hap_p10_parse_kv $placement_summary_path \
    "Mission 0141 summary"]
foreach {key expected} {
    stage V5_P10_P13_POST_PLACE_FAST_GATE
    congestion_level5_or_higher_windows 21
    congestion_level6_or_higher_windows 9
    post_place_drc_errors 0
    unplaced_primitives 0
    wrong_slr_primitives 0
    route_eligible 0
    diagnostic_checkpoint_written 1
    status FAIL
} {
    hap_p13_timing_require_kv $placement $key $expected \
        "Mission 0141 summary"
}
set placement_launcher [hap_p10_parse_kv $placement_launcher_path \
    "Mission 0141 launcher"]
foreach {key expected} {
    status FAIL
    vivado_exit_code 1
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    route_eligible 0
    checkpoint_written 0
} {
    hap_p13_timing_require_kv $placement_launcher $key $expected \
        "Mission 0141 launcher"
}

set map_outputs [hap_p10_verify_manifest $map_output_sha -1 \
    $expected_map_output_sha]
set map_dir [file dirname $map_output_sha]
set map_summary_path [file join $map_dir summary.txt]
set map_launcher_path [file join $map_dir launcher_status.txt]
foreach required [list $map_summary_path $map_launcher_path] {
    if {![dict exists $map_outputs [file normalize $required]]} {
        error "Mission 0142 output manifest is incomplete: $required"
    }
}
set map_summary [hap_p10_parse_kv $map_summary_path "Mission 0142 summary"]
foreach {key expected} {
    stage V5_P10_P13_LEVEL6_PHYSICAL_MAP
    source_lineage_verified 1
    level6_windows_profiled 9
    floorplan_mutated 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P13_LEVEL6_PHYSICAL_MAP_PASS
} {
    hap_p13_timing_require_kv $map_summary $key $expected \
        "Mission 0142 summary"
}
hap_p13_timing_require_kv $map_summary input_dcp $dcp \
    "Mission 0142 summary"
set map_launcher [hap_p10_parse_kv $map_launcher_path \
    "Mission 0142 launcher"]
hap_p13_timing_require_kv $map_launcher status PASS "Mission 0142 launcher"

set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha ||
    [dict get $placement_outputs $dcp] ne $expected_dcp_sha ||
    [dict get $map_summary input_dcp_sha256] ne $expected_dcp_sha} {
    error "P13 timing DCP identity mismatch"
}

open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P13 timing top/part mismatch: $top/$part"
}
foreach {clock_name period} {
    core_clk 10.000
    ddr0_clk 3.333
    ddr1_clk 3.333
} {
    set clocks [get_clocks -quiet $clock_name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P13 timing clock contract mismatch: $clock_name"
    }
}

set setup_paths [get_timing_paths -quiet -delay_type max \
    -max_paths 200 -nworst 20]
set hold_paths [get_timing_paths -quiet -delay_type min \
    -max_paths 50 -nworst 10]
if {[llength $setup_paths] == 0 || [llength $hold_paths] == 0} {
    error "P13 timing path collection is empty"
}
set setup_metrics [hap_p13_timing_write_paths $setup_paths \
    [file join $out setup_paths.tsv]]
set hold_metrics [hap_p13_timing_write_paths $hold_paths \
    [file join $out hold_paths.tsv]]
report_timing -delay_type max -max_paths 100 -nworst 20 \
    -path_type full_clock_expanded -input_pins \
    -file [file join $out timing_setup.rpt]
report_timing -delay_type min -max_paths 50 -nworst 10 \
    -path_type full_clock_expanded -input_pins \
    -file [file join $out timing_hold.rpt]
report_timing_summary -delay_type min_max -report_unconstrained \
    -file [file join $out timing_summary.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]

set worst_setup [lindex $setup_paths 0]
set worst_hold [lindex $hold_paths 0]
set pair_handle [open [file join $out setup_category_pairs.tsv] w]
puts $pair_handle "category_pair\tpath_count"
foreach pair [lsort -dictionary [dict keys [dict get $setup_metrics pairs]]] {
    puts $pair_handle "$pair\t[dict get $setup_metrics pairs $pair]"
}
close $pair_handle

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P13_TIMING_ROOT_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        setup_paths_profiled [dict get $setup_metrics path_count] \
        setup_top_level_paths [dict get $setup_metrics top_level_count] \
        hold_paths_profiled [dict get $hold_metrics path_count] \
        hold_top_level_paths [dict get $hold_metrics top_level_count] \
        setup_wns_ns [get_property SLACK $worst_setup] \
        setup_worst_startpoint [get_property STARTPOINT_PIN $worst_setup] \
        setup_worst_endpoint [get_property ENDPOINT_PIN $worst_setup] \
        setup_worst_start_category [hap_p13_timing_category \
            [get_property STARTPOINT_PIN $worst_setup]] \
        setup_worst_end_category [hap_p13_timing_category \
            [get_property ENDPOINT_PIN $worst_setup]] \
        hold_whs_ns [get_property SLACK $worst_hold] \
        hold_worst_startpoint [get_property STARTPOINT_PIN $worst_hold] \
        hold_worst_endpoint [get_property ENDPOINT_PIN $worst_hold] \
        floorplan_mutated 0 implementation_commands_run 0 \
        checkpoint_written 0 route_eligible 0 \
        status V5_P10_P13_TIMING_ROOT_DIAGNOSIS_PASS] {
    puts $summary "$key=$value"
}
close $summary
close_design
exit 0

