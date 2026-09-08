# Read-only same-clock register-to-register diagnosis for rejected P13.
# Top-level input/output paths are explicitly removed from every result set.

set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_P13_R2R_DCP)]
set out [file normalize $::env(HAP_P13_R2R_DIR)]
set input_sha [file normalize $::env(HAP_P13_R2R_INPUT_SHA)]
set expected_input_sha $::env(HAP_P13_R2R_INPUT_MANIFEST_SHA256)
set expected_dcp_sha $::env(HAP_P13_R2R_DCP_SHA256)
set placement_output_sha [file normalize $::env(HAP_P13_R2R_PLACE_OUTPUT_SHA)]
set expected_placement_output_sha $::env(HAP_P13_R2R_PLACE_OUTPUT_SHA256)
set timing_output_sha [file normalize $::env(HAP_P13_R2R_TIMING_OUTPUT_SHA)]
set expected_timing_output_sha $::env(HAP_P13_R2R_TIMING_OUTPUT_SHA256)
set p10_proc_lib [file normalize $::env(HAP_P13_R2R_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_P13_R2R_LAUNCHER)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p13_r2r_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

proc hap_p13_r2r_category {name} {
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
    return integration_other
}

proc hap_p13_r2r_collect {clock_name delay_type} {
    set clocks [get_clocks -quiet $clock_name]
    if {[llength $clocks] != 1} {
        error "P13 internal timing clock is not unique: $clock_name"
    }
    # Use explicit same-clock register collections.  A clock-to-clock query can
    # return only OOC top-port hold paths even when thousands of candidates are
    # requested, so filtering that result after the query is not complete.
    set registers [all_registers -clock $clocks]
    if {[llength $registers] == 0} {
        error "P13 internal timing register set is empty: $clock_name"
    }
    set internal [get_timing_paths -quiet -delay_type $delay_type \
        -from $registers -to $registers -max_paths 100 -nworst 1]
    foreach path $internal {
        set startpoint [get_property STARTPOINT_PIN $path]
        set endpoint [get_property ENDPOINT_PIN $path]
        if {[llength [get_ports -quiet $startpoint]] != 0 ||
            [llength [get_ports -quiet $endpoint]] != 0} {
            error "P13 internal query selected a top-level path: $clock_name/$delay_type"
        }
        set start_cells [get_cells -quiet -of_objects \
            [get_pins -quiet $startpoint]]
        set end_cells [get_cells -quiet -of_objects \
            [get_pins -quiet $endpoint]]
        if {[llength $start_cells] != 1 || [llength $end_cells] != 1} {
            error "P13 internal query endpoint is not a cell pin: $clock_name/$delay_type"
        }
    }
    if {[llength $internal] == 0} {
        error "P13 internal path search returned no cell-to-cell path: $clock_name/$delay_type"
    }
    return [dict create registers $registers paths $internal]
}

proc hap_p13_r2r_write {clock_name delay_type result out} {
    set paths [dict get $result paths]
    set registers [dict get $result registers]
    set path [file join $out ${clock_name}_internal_${delay_type}.tsv]
    set fp [open $path w]
    puts $fp "rank\tslack_ns\tlogic_levels\tdatapath_delay_ns\tstart_category\tend_category\tstartpoint\tendpoint"
    set rank 0
    foreach timing_path $paths {
        incr rank
        set startpoint [get_property STARTPOINT_PIN $timing_path]
        set endpoint [get_property ENDPOINT_PIN $timing_path]
        puts $fp [join [list $rank [get_property SLACK $timing_path] \
            [get_property LOGIC_LEVELS $timing_path] \
            [get_property DATAPATH_DELAY $timing_path] \
            [hap_p13_r2r_category $startpoint] \
            [hap_p13_r2r_category $endpoint] $startpoint $endpoint] "\t"]
    }
    close $fp
    report_timing -delay_type $delay_type -from $registers -to $registers \
        -max_paths 20 -nworst 1 -path_type full_clock_expanded -input_pins \
        -file [file join $out ${clock_name}_internal_${delay_type}.rpt]
}

if {![string match "2025.2*" [version -short]]} {
    error "P13 internal timing diagnosis requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P13 internal timing diagnosis requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P13 internal timing diagnosis requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_placement_output_sha $expected_timing_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P13 internal timing diagnosis received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 6 $expected_input_sha]
foreach required [list $dcp $placement_output_sha $timing_output_sha \
        $p10_proc_lib $audit_script $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P13 internal timing input absent from manifest: $required"
    }
}

set placement_outputs [hap_p10_verify_manifest $placement_output_sha -1 \
    $expected_placement_output_sha]
set placement_dir [file dirname $placement_output_sha]
set placement_summary_path [file join $placement_dir summary.txt]
if {![dict exists $placement_outputs $dcp] ||
    ![dict exists $placement_outputs $placement_summary_path]} {
    error "Mission 0141 output lineage is incomplete"
}
set placement [hap_p10_parse_kv $placement_summary_path "Mission 0141 summary"]
foreach {key expected} {
    stage V5_P10_P13_POST_PLACE_FAST_GATE
    route_eligible 0
    diagnostic_checkpoint_written 1
    status FAIL
} {
    hap_p13_r2r_require_kv $placement $key $expected "Mission 0141 summary"
}

set timing_outputs [hap_p10_verify_manifest $timing_output_sha -1 \
    $expected_timing_output_sha]
set timing_dir [file dirname $timing_output_sha]
set timing_summary_path [file join $timing_dir summary.txt]
set timing_launcher_path [file join $timing_dir launcher_status.txt]
foreach required [list $timing_summary_path $timing_launcher_path] {
    if {![dict exists $timing_outputs $required]} {
        error "Mission 0143 output lineage is incomplete: $required"
    }
}
set timing [hap_p10_parse_kv $timing_summary_path "Mission 0143 summary"]
foreach {key expected} {
    stage V5_P10_P13_TIMING_ROOT_DIAGNOSIS
    source_lineage_verified 1
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P13_TIMING_ROOT_DIAGNOSIS_PASS
} {
    hap_p13_r2r_require_kv $timing $key $expected "Mission 0143 summary"
}
hap_p13_r2r_require_kv $timing input_dcp $dcp "Mission 0143 summary"

set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha ||
    [dict get $placement_outputs $dcp] ne $expected_dcp_sha ||
    [dict get $timing input_dcp_sha256] ne $expected_dcp_sha} {
    error "P13 internal timing DCP identity mismatch"
}

open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P13 internal timing top/part mismatch: $top/$part"
}
foreach {clock_name period} {
    core_clk 10.000
    ddr0_clk 3.333
    ddr1_clk 3.333
} {
    set clocks [get_clocks -quiet $clock_name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P13 internal timing clock contract mismatch: $clock_name"
    }
}

set metrics [dict create]
foreach clock_name {core_clk ddr0_clk ddr1_clk} {
    foreach delay_type {max min} {
        set result [hap_p13_r2r_collect $clock_name $delay_type]
        dict set metrics $clock_name $delay_type $result
        hap_p13_r2r_write $clock_name $delay_type $result $out
    }
}

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P10_P13_INTERNAL_R2R_TIMING_DIAGNOSIS \
        evidence_class READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified 1 input_dcp $dcp \
        input_dcp_sha256 $actual_dcp_sha top $top part $part jobs $jobs \
        top_level_port_paths_included 0] {
    puts $summary "$key=$value"
}
foreach clock_name {core_clk ddr0_clk ddr1_clk} {
    foreach {delay_type label} {max setup min hold} {
        set result [dict get $metrics $clock_name $delay_type]
        set paths [dict get $result paths]
        set worst [lindex $paths 0]
        puts $summary "${clock_name}_${label}_registers=[llength [dict get $result registers]]"
        puts $summary "${clock_name}_reported_internal_${label}_paths=[llength $paths]"
        puts $summary "${clock_name}_internal_${label}_wns_ns=[get_property SLACK $worst]"
        puts $summary "${clock_name}_internal_${label}_startpoint=[get_property STARTPOINT_PIN $worst]"
        puts $summary "${clock_name}_internal_${label}_endpoint=[get_property ENDPOINT_PIN $worst]"
    }
}
foreach {key value} {
    floorplan_mutated 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    status V5_P10_P13_INTERNAL_R2R_TIMING_DIAGNOSIS_PASS
} {
    puts $summary "$key=$value"
}
close $summary
close_design
exit 0
