set script_dir [file dirname [file normalize [info script]]]
set diagnostic_dcp [file normalize $::env(HAP_DIAGNOSTIC_DCP)]
set failed_dir [file normalize $::env(HAP_FAILED_PLACE_DIR)]
set out [file normalize $::env(HAP_DIAGNOSTIC_AUDIT_DIR)]
set input_sha [file normalize $::env(HAP_DIAGNOSTIC_INPUT_SHA)]
set expected_input_sha $::env(HAP_DIAGNOSTIC_INPUT_SHA256)
set expected_dcp_sha $::env(HAP_EXPECTED_DIAGNOSTIC_DCP_SHA256)
set expected_failed_input_sha $::env(HAP_EXPECTED_FAILED_INPUT_SHA256)
set expected_failed_output_sha $::env(HAP_EXPECTED_FAILED_OUTPUT_SHA256)
set selector_lib [file join $script_dir v5_production_floorplan_selectors.tcl]
set geometry_lib [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
set p10_script [file join $script_dir \
    place_attention_mlp_production_v5_p10_p2.tcl]
set failed_input_sha [file join $failed_dir INPUT_SHA256SUMS]
set failed_output_sha [file join $failed_dir OUTPUT_SHA256SUMS]
set failed_summary [file join $failed_dir summary.txt]
set failed_status [file join $failed_dir launcher_status.txt]
set contract_variant P2_COHORT16_COL2_12_2
set geometry_prefix p3_
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_script
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)
source $selector_lib
source $geometry_lib

proc hap_p3_diag_verify_failed_lineage {manifest} {
    set count 0
    foreach raw [split [hap_p10_read_nonempty $manifest \
            "failed placement input manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected source_path]} {
            error "Malformed failed placement input row: $line"
        }
        set source_path [file normalize [string trim $source_path]]
        hap_p10_read_nonempty $source_path "failed placement lineage input"
        set actual [hap_p10_sha256 $source_path]
        if {$actual ne $expected} {
            error "Failed placement lineage mismatch: path=$source_path expected=$expected actual=$actual"
        }
        incr count
    }
    if {$count != 8} {
        error "Failed placement lineage cardinality mismatch: rows=$count"
    }
}

proc hap_p3_diag_write_bufg {path} {
    set clock_bufg 0
    set data_bufg 0
    set fp [open $path w]
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter {
            DIRECTION == OUT}]
        set clocks [get_clocks -quiet -of_objects $outputs]
        set nets [get_nets -quiet -of_objects $outputs]
        set leaf_sinks [get_pins -quiet -leaf -of_objects $nets -filter {
            DIRECTION == IN}]
        if {[llength $clocks] != 0} {
            incr clock_bufg
            set class CLOCK
        } else {
            incr data_bufg
            set class DATA
        }
        puts $fp "class=$class cell=[get_property NAME $cell] ref=[get_property REF_NAME $cell] nets=[get_property NAME $nets] leaf_sinks=[llength $leaf_sinks]"
    }
    close $fp
    return [dict create clock $clock_bufg data $data_bufg]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P10 P3 diagnostic audit requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P10 P3 diagnostic audit requires HAP_JOBS=32"
}
foreach digest [list $expected_input_sha $expected_dcp_sha \
        $expected_failed_input_sha $expected_failed_output_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P10 P3 diagnostic audit received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 8 $expected_input_sha]
foreach required [list $diagnostic_dcp $failed_input_sha $failed_output_sha \
        $selector_lib $geometry_lib $p10_script \
        [file normalize [info script]]] {
    if {![dict exists $frozen $required]} {
        error "P10 P3 diagnostic input absent from manifest: $required"
    }
}
if {[hap_p10_sha256 $diagnostic_dcp] ne $expected_dcp_sha ||
    [hap_p10_sha256 $failed_input_sha] ne $expected_failed_input_sha ||
    [hap_p10_sha256 $failed_output_sha] ne $expected_failed_output_sha} {
    error "P10 P3 failed placement artifact identity mismatch"
}
hap_p3_diag_verify_failed_lineage $failed_input_sha
if {[catch {exec sha256sum -c --strict $failed_output_sha} verify_error]} {
    error "P10 P3 failed placement output manifest does not reverify: $verify_error"
}

set failed [hap_p10_parse_kv $failed_summary "failed placement summary"]
foreach {key value} {
    stage V5_P10_P2_POST_PLACE_REDISCOVERY
    failure_stage post_place_live_rediscovery
    acceptance_evidence 0
    route_eligible 0
    checkpoint_written 0
    diagnostic_checkpoint_written 1
    provenance_verified 1
    pre_place_verified 1
    status FAIL
} {
    hap_p10_require_kv $failed $key $value "failed placement summary"
}
hap_p10_require_kv $failed post_rediscovery_error \
    {P10 post-place compute net lost CLOCK_BUFFER_TYPE NONE: u_compute/u_attention/activation_wave_repN_alias} \
    "failed placement summary"
set launcher [hap_p10_parse_kv $failed_status "failed placement launcher"]
foreach {key value} {
    status FAIL
    acceptance_evidence 0
    route_eligible 0
    final_exit_code 1
    vivado_exit_code 1
    input_sha_recheck_exit_code 0
    input_manifest_sha_match 1
    preplace_output_sha_recheck_exit_code 0
    place_gate_exit_code 1
    checkpoint_written 0
    vivado_invoked 1
    implementation_commands_requested 1
    bitstream_generated 0
} {
    hap_p10_require_kv $launcher $key $value "failed placement launcher"
}

open_checkpoint $diagnostic_dcp
foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P10 P3 diagnostic clock contract mismatch: $name"
    }
}

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "P10 P3 diagnostic compute-net selector is empty"
}
set missing_clock_buffer_none {}
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        lappend missing_clock_buffer_none [get_property NAME $net]
    }
}

set plan [hap_v5_floorplan::discover $contract_variant]
set projection_root [file dirname \
    [get_property NAME [dict get $plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 0 $geometry_prefix 1]
set pblock_audit [hap_v5_floorplan::audit_pblock_contract \
    $plan 1 $contract_variant \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix]]
set geometry_placement \
    [hap_projection_ooc_floorplan::audit_placement $geometry_plan]
set physical [hap_v5_floorplan::physical_metrics $plan $pblock_audit]
set compact_input [hap_p10_cells_of_module \
    hap_mlp_input_frontend16_compact_cache]
set down_elastic [hap_p10_cells_of_module hap_mlp_down_branch_elastic2_s24]
set clear [hap_p10_mlp_local_clear_audit 1]
set metadata [hap_p10_metadata_local_write_audit 1]
set capture [hap_p10_mlp_capture_leaf_audit \
    [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s43_s45] 1]
hap_v5_floorplan::write_discovery $plan \
    [file join $out selectors_post_place.txt] \
    V5_P10_P3_DIAGNOSTIC_SELECTORS_PASS
hap_v5_floorplan::write_pblock_audit $pblock_audit \
    [file join $out pblocks_post_place.txt] \
    V5_P10_P3_DIAGNOSTIC_PBLOCKS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry_post_place.txt] \
    V5_P10_P3_DIAGNOSTIC_GEOMETRY_PASS
hap_projection_ooc_floorplan::write_placement $geometry_placement \
    [file join $out attention_geometry_placement.txt] \
    V5_P10_P3_DIAGNOSTIC_GEOMETRY_PLACEMENT_PASS

set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_p10_congestion_counts \
    [hap_p10_read_nonempty $congestion_path "diagnostic congestion report"]]
set bufg [hap_p3_diag_write_bufg [file join $out bufg_topology.txt]]
report_drc -file [file join $out drc_post_place.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -check_timing_verbose \
    -file [file join $out timing_post_place.rpt]
report_timing -delay_type max -max_paths 100 -nworst 1 \
    -file [file join $out setup_paths_post_place.rpt]
report_timing -delay_type min -max_paths 100 -nworst 1 \
    -file [file join $out hold_paths_post_place.rpt]
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "P10 P3 diagnostic timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]

set slr_dsp [dict get $physical slr_dsp]
set slr_uram [dict get $physical slr_uram]
set resource_ok [expr {[dict get $plan total_dsp] == 5453 &&
    [dict get $plan total_uram] == 752 &&
    [dict get $plan kernel_dsp] == 3072 &&
    [dict get $plan history2_count] == 2 &&
    [dict get $plan generic_repack_count] == 0 &&
    [dict get $plan projection_weight_capture_ok] == 1}]
set structure_ok [expr {[llength $compact_input] == 1 &&
    [llength $down_elastic] == 2 &&
    [dict get $clear total] == 2 && [dict get $clear protected] == 2 &&
    [dict get $clear branch0_slr] eq {1 0 0} &&
    [dict get $clear branch1_slr] eq {0 0 1} &&
    [dict get $clear wrong] == 0 &&
    [dict get $metadata protected] == 970 &&
    [dict get $metadata leaf_counts] eq {243 243 242 242} &&
    [dict get $metadata leaf_slr_counts] eq \
        {{243 0 0} {0 0 243} {0 242 0} {0 242 0}} &&
    [dict get $metadata wrong] == 0 &&
    [dict get $capture instances] == 1632 &&
    [dict get $capture lut1] == 1632 &&
    [dict get $capture branch_instances] eq {816 816} &&
    [dict get $capture branch_slr_counts] eq {{816 0 0} {0 0 816}} &&
    [dict get $capture wrong] == 0}]
set placement_ok [expr {[hap_v5_floorplan::physical_ok $plan $physical] &&
    [dict get $pblock_audit ok] &&
    [dict get $pblock_audit pblock_count] == 11 &&
    [dict get $pblock_audit placed_wrong] == 0 &&
    [dict get $physical wrong_total] == 0 &&
    [dict get $physical unplaced] == 0 &&
    $slr_dsp eq {1862 1781 1810} && $slr_uram eq {224 224 304} &&
    [dict get $geometry_audit pblock_count] == 10 &&
    [dict get $geometry_placement ok]}]
set diagnostic_ok [expr {$resource_ok && $structure_ok && $placement_ok &&
    $drc_errors == 0 && [dict get $congestion schema_ok]}]

hap_p10_write_summary $out [list tool [version -short] \
    stage V5_P10_P3_POST_PLACE_DIAGNOSTIC_REOPEN \
    evidence_class READ_ONLY_RECOVERY_DIAGNOSTIC \
    source_place_status FAIL acceptance_evidence 0 route_eligible 0 \
    checkpoint_written 0 implementation_commands_run 0 \
    input_dcp $diagnostic_dcp input_dcp_sha256 $expected_dcp_sha \
    failed_input_manifest_sha256 $expected_failed_input_sha \
    failed_output_manifest_sha256 $expected_failed_output_sha \
    failed_lineage_verified 1 jobs $jobs core_clock_mhz 100 \
    ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    contract_variant $contract_variant geometry_prefix $geometry_prefix \
    dsp48e2 [dict get $plan total_dsp] uram288 [dict get $plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $plan kernel_dsp] \
    slr0_dsp48e2 [lindex $slr_dsp 0] slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] \
    slr0_uram288 [lindex $slr_uram 0] slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    pblock_count [dict get $pblock_audit pblock_count] \
    geometry_pblock_count [dict get $geometry_audit pblock_count] \
    pblock_dsp_coverage [dict get $pblock_audit dsp_coverage] \
    pblock_uram_coverage [dict get $pblock_audit uram_coverage] \
    pblock_wrong_slr [dict get $pblock_audit placed_wrong] \
    geometry_wrong_slr [dict get $geometry_placement wrong_total] \
    unplaced_primitives [dict get $physical unplaced] \
    wrong_slr_primitives [dict get $physical wrong_total] \
    mlp_local_clear_ff [dict get $clear total] \
    metadata_local_write_protected_ff [dict get $metadata protected] \
    mlp_capture_leaf_instances [dict get $capture instances] \
    compute_nets [llength $compute_nets] \
    compute_clock_buffer_none_missing [llength $missing_clock_buffer_none] \
    compute_clock_buffer_none_missing_names $missing_clock_buffer_none \
    clock_bufg [dict get $bufg clock] data_bufg [dict get $bufg data] \
    drc_errors $drc_errors \
    congestion_level5_or_higher_windows [dict get $congestion level5] \
    congestion_level6_or_higher_windows [dict get $congestion level6] \
    congestion_schema_ok [dict get $congestion schema_ok] \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok diagnostic_ok $diagnostic_ok \
    status [expr {$diagnostic_ok ? \
        "V5_P10_P3_POST_PLACE_DIAGNOSTIC_COMPLETE" : "FAIL"}]]

puts "V5_P10_P3_DIAGNOSTIC DSP=$slr_dsp URAM=$slr_uram DATA_BUFG=[dict get $bufg data] DRC=$drc_errors L5=[dict get $congestion level5] L6=[dict get $congestion level6] WNS=$wns WHS=$whs CBT_MISSING=[llength $missing_clock_buffer_none] STATUS=$diagnostic_ok"
close_design
if {!$diagnostic_ok} {
    error "P10 P3 post-place diagnostic structural gate failed"
}
