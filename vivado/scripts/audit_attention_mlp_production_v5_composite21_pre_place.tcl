# Strict in-memory pre-place qualification for the P9 central-island production
# floorplan. The flow consumes a PASS read-only capacity probe, creates the 21
# pblocks in memory, audits exact membership and runs pre-place DRC. It never
# runs implementation or writes a checkpoint.

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_COMPOSITE21_PREPLACE_DIR)]
set input_sha [file normalize $::env(HAP_COMPOSITE21_PREPLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_input_sha $::env(HAP_COMPOSITE21_PREPLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_COMPOSITE21_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_COMPOSITE21_FINE_LIB)]
set composite_lib [file normalize $::env(HAP_COMPOSITE21_LIB)]
set probe_output_sha [file normalize $::env(HAP_COMPOSITE21_PROBE_OUTPUT_SHA)]
set expected_probe_output_sha $::env(HAP_COMPOSITE21_PROBE_OUTPUT_SHA256)
set expected_launcher [file normalize $::env(HAP_COMPOSITE21_PREPLACE_LAUNCHER)]
set audit_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_composite21_require_nonempty_file {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
}

proc hap_composite21_read_nonempty {path label} {
    hap_composite21_require_nonempty_file $path $label
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_composite21_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_composite21_verify_manifest {path expected_count expected_sha label} {
    if {[hap_composite21_sha256 $path] ne $expected_sha} {
        error "$label manifest identity mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_composite21_read_nonempty $path $label] "\n"] {
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
        hap_composite21_require_nonempty_file $normalized "$label input"
        if {[hap_composite21_sha256 $normalized] ne $expected} {
            error "$label SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {$expected_count >= 0 && [dict size $entries] != $expected_count} {
        error "$label manifest cardinality mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_composite21_require_line {path literal} {
    set count 0
    foreach line [split [hap_composite21_read_nonempty $path evidence] "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "Composite21 evidence line mismatch: $path literal=$literal count=$count"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "Composite21 pre-place audit requires a fresh Vivado process"
}
if {![file exists $out] || ![file isdirectory $out]} {
    error "Missing Composite21 pre-place evidence directory: $out"
}
set_param general.maxThreads $jobs
set frozen [hap_composite21_verify_manifest $input_sha 7 \
    $expected_input_sha composite21_pre_place_input]
foreach path [list $dcp $selector_lib $fine_lib $composite_lib $probe_output_sha \
        $audit_script $expected_launcher] {
    if {![dict exists $frozen $path]} {
        error "Required Composite21 pre-place input absent from manifest: $path"
    }
}
if {[hap_composite21_sha256 $dcp] ne $expected_dcp_sha} {
    error "Composite21 pre-place DCP identity mismatch"
}
set probe_entries [hap_composite21_verify_manifest $probe_output_sha -1 \
    $expected_probe_output_sha composite21_probe_output]
set probe_dir [file dirname $probe_output_sha]
set probe_summary [file join $probe_dir summary.txt]
set probe_launcher_status [file join $probe_dir launcher_status.txt]
foreach path [list $probe_summary $probe_launcher_status] {
    if {![dict exists $probe_entries $path]} {
        error "Required Composite21 probe evidence absent from output manifest: $path"
    }
}
foreach literal [list status=PASS \
        composite21_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21 \
        composite21_pblock_spec_count=21 composite21_member_overlap=0 \
        composite21_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_central_island_count=197091 \
        composite21_central_island_dsp=80 \
        composite21_mlp_remaining_count=88785 \
        composite21_center_dsp_remaining=5 \
        composite21_central_partition_ok=1 \
        composite21_aggregate_capacity_ok=1 \
        composite21_attention_direct_constrained=0 \
        composite21_soft_pblock_count=0 \
        composite21_hard_capacity_ok=1 \
        composite21_flexible_outer_90pct_fit=1 \
        composite21_dsp_coverage=5453 composite21_uram_coverage=752 \
        composite21_resource_distribution_ok=1 \
        input_dcp=$dcp input_dcp_sha256=$expected_dcp_sha \
        floorplan_mutated=0 implementation_commands_run=0 \
        checkpoint_written=0] {
    hap_composite21_require_line $probe_summary $literal
}
foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1
        probe_gate_exit_code=0 floorplan_mutated=0
        implementation_commands_run=0 checkpoint_written=0} {
    hap_composite21_require_line $probe_launcher_status $literal
}

source $selector_lib
source $fine_lib
source $composite_lib
set flow_start_ms [clock milliseconds]
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
if {[llength [get_pblocks -quiet]] != 0} {
    error "Composite21 input checkpoint unexpectedly contains pblocks"
}
set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set fine_plan [hap_v5_fine19::discover $base_plan]
set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan]
set discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors_base.txt] V5_COMPOSITE21_BASE_SELECTORS_PASS
hap_v5_fine19::write_discovery $fine_plan \
    [file join $out selectors_fine19.txt] V5_COMPOSITE21_FINE19_SELECTORS_PASS
hap_v5_composite21::write_discovery $composite_plan \
    [file join $out selectors_composite21.txt] \
    V5_COMPOSITE21_SELECTORS_PASS

set phase_start_ms [clock milliseconds]
hap_v5_composite21::apply $base_plan $fine_plan $composite_plan
set apply_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set phase_start_ms [clock milliseconds]
set audit [hap_v5_composite21::audit \
    $base_plan $fine_plan $composite_plan 0]
set audit_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
hap_v5_composite21::write_audit $audit [file join $out pblocks.txt] \
    V5_COMPOSITE21_PRE_PLACE_PBLOCKS_PASS

set phase_start_ms [clock milliseconds]
report_drc -file [file join $out drc_pre_place.rpt]
set drc_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set pre_place_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
set status [expr {
    [dict get $composite_plan contract_variant] eq
        "P9_COHORT16_MLP_CENTRAL_X2X4_21" &&
    [dict get $composite_plan fine_member_count] == 1432847 &&
    [dict get $composite_plan mlp_residual_count] == 285796 &&
    [dict get $composite_plan attention_direct_count] == 71350 &&
    [dict get $composite_plan central_anchor_range] eq
        "CLOCKREGION_X2Y5:CLOCKREGION_X4Y9" &&
    [dict get $composite_plan central_island_count] == 197091 &&
    [dict get $composite_plan central_island_dsp] == 80 &&
    [dict get $composite_plan mlp_remaining_count] == 88785 &&
    [dict get $composite_plan center_dsp_remaining_dsp] == 5 &&
    [dict get $composite_plan central_partition_ok] == 1 &&
    [dict get $composite_plan owner_overlap] == 0 &&
    [dict get $composite_plan hard_resource_intrusion] == 0 &&
    [dict get $composite_plan exact_partition] == 1 &&
    [dict get $composite_plan attention_direct_constrained] == 0 &&
    [dict get $audit ok] == 1 && [dict get $audit pblock_count] == 21 &&
    [dict get $audit member_overlap] == 0 &&
    [dict get $audit optimizer_extra_count] == 0 &&
    [dict get $audit soft_pblock_count] == 0 &&
    [dict get $audit soft_outside] == 0 &&
    [dict get $audit dsp_coverage] == 5453 &&
    [dict get $audit uram_coverage] == 752 &&
    [dict get $audit placed_wrong] == 0 && $pre_place_drc_errors == 0 ?
    "V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_PRODUCTION_COMPOSITE21_PRE_PLACE_AUDIT \
        evidence_class IN_MEMORY_PRE_PLACE_PBLOCK_DRC \
        jobs $jobs input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_input_sha input_manifest_entries 7 \
        probe_output_manifest $probe_output_sha \
        probe_output_manifest_sha256 $expected_probe_output_sha \
        probe_output_entries [dict size $probe_entries] probe_verified 1 \
        contract_variant [dict get $composite_plan contract_variant] \
        fine_contract_variant [dict get $fine_plan contract_variant] \
        pblock_count [dict get $audit pblock_count] \
        member_count [dict get $audit member_count] \
        member_overlap [dict get $audit member_overlap] \
        optimizer_extra_count [dict get $audit optimizer_extra_count] \
        soft_pblock_count [dict get $audit soft_pblock_count] \
        soft_outside [dict get $audit soft_outside] \
        fine_member_count [dict get $composite_plan fine_member_count] \
        mlp_residual_count [dict get $composite_plan mlp_residual_count] \
        central_anchor_range [dict get $composite_plan central_anchor_range] \
        central_island_count [dict get $composite_plan central_island_count] \
        central_island_delta [dict get $composite_plan central_island_delta] \
        central_island_dsp [dict get $composite_plan central_island_dsp] \
        mlp_remaining_count [dict get $composite_plan mlp_remaining_count] \
        mlp_remaining_delta [dict get $composite_plan mlp_remaining_delta] \
        center_dsp_remaining_count \
            [dict get $composite_plan center_dsp_remaining_count] \
        center_dsp_remaining_dsp \
            [dict get $composite_plan center_dsp_remaining_dsp] \
        central_partition_ok [dict get $composite_plan central_partition_ok] \
        attention_direct_count [dict get $composite_plan attention_direct_count] \
        attention_direct_constrained \
            [dict get $composite_plan attention_direct_constrained] \
        owner_overlap [dict get $composite_plan owner_overlap] \
        hard_resource_intrusion [dict get $composite_plan hard_resource_intrusion] \
        exact_partition [dict get $composite_plan exact_partition] \
        pblock_dsp_coverage [dict get $audit dsp_coverage] \
        pblock_uram_coverage [dict get $audit uram_coverage] \
        pblock_wrong_slr [dict get $audit placed_wrong] \
        pre_place_drc_errors $pre_place_drc_errors \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        discovery_elapsed_ms $discovery_elapsed_ms \
        apply_elapsed_ms $apply_elapsed_ms audit_elapsed_ms $audit_elapsed_ms \
        drc_elapsed_ms $drc_elapsed_ms total_elapsed_ms $total_elapsed_ms \
        floorplan_mutated_in_memory 1 implementation_commands_run 0 \
        checkpoint_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "V5_PRODUCTION_COMPOSITE21_PRE_PLACE_COMPLETE STATUS=$status"
if {$status ne "V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS"} {
    error "V5 Composite21 pre-place audit failed"
}
close_design
