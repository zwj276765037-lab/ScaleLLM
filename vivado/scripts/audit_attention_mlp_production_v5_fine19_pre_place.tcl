# In-memory pre-place audit for the P3 fine19 production floorplan.  Pblocks
# are the only design mutation; no constraints or implementation command is
# legal in this evidence flow.

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_FINE19_PREPLACE_DIR)]
set input_sha [file normalize $::env(HAP_FINE19_PREPLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_FINE19_PREPLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_FINE19_PREPLACE_SELECTOR_LIB)]
set fine_lib [file normalize $::env(HAP_FINE19_PREPLACE_FINE_LIB)]
set launcher [file normalize $::env(HAP_FINE19_PREPLACE_LAUNCHER)]
set upstream_manifest [file normalize $::env(HAP_FINE19_PROBE_OUTPUT_SHA)]
set expected_upstream_sha $::env(HAP_FINE19_PROBE_OUTPUT_SHA256)
set audit_script [file normalize [info script]]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]

proc hap_fine19_pre_read {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_fine19_pre_sha {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_fine19_pre_manifest {path expected_count expected_sha} {
    if {[hap_fine19_pre_sha $path] ne $expected_sha} {
        error "V5 fine19 pre-place input-manifest digest mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_fine19_pre_read $path input_manifest] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed V5 fine19 pre-place manifest row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $entries $normalized]} {
            error "Duplicate V5 fine19 pre-place input: $normalized"
        }
        hap_fine19_pre_read $normalized frozen_input
        if {[hap_fine19_pre_sha $normalized] ne $expected} {
            error "V5 fine19 pre-place input SHA mismatch: $normalized"
        }
        dict set entries $normalized $expected
    }
    if {[dict size $entries] != $expected_count} {
        error "V5 fine19 pre-place input count mismatch: [dict size $entries]"
    }
    return $entries
}

proc hap_fine19_pre_exact_line {text literal} {
    set count 0
    foreach line [split $text "\n"] {
        if {$line eq $literal} {incr count}
    }
    if {$count != 1} {
        error "V5 fine19 upstream probe field mismatch: $literal count=$count"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 fine19 pre-place audit requires a fresh Vivado process"
}
set_param general.maxThreads $jobs
set frozen [hap_fine19_pre_manifest $input_sha 6 $expected_manifest_sha]
foreach required [list $dcp $selector_lib $fine_lib $audit_script $launcher \
        $upstream_manifest] {
    if {![dict exists $frozen $required]} {
        error "V5 fine19 pre-place required input absent from manifest: $required"
    }
}
if {[hap_fine19_pre_sha $dcp] ne $expected_dcp_sha ||
    [hap_fine19_pre_sha $upstream_manifest] ne $expected_upstream_sha} {
    error "V5 fine19 pre-place DCP or upstream identity mismatch"
}
if {[catch {exec sha256sum -c --strict $upstream_manifest} verify_text]} {
    error "V5 fine19 upstream probe manifest does not verify: $verify_text"
}
set upstream_summary_path [file join [file dirname $upstream_manifest] summary.txt]
set upstream_summary [hap_fine19_pre_read $upstream_summary_path upstream_summary]
foreach literal [list status=PASS \
        stage=V5_PRODUCTION_FINE19_FLOORPLAN_PROBE \
        contract_variant=P3_COHORT16_OOC10_19 \
        input_dcp=$dcp input_dcp_sha256=$expected_dcp_sha \
        pblock_spec_count=19 member_overlap=0 raw_capacity_ok=1 \
        pblock_dsp_coverage=5453 pblock_uram_coverage=752 \
        floorplan_mutated=0 implementation_commands_run=0 \
        checkpoint_written=0] {
    hap_fine19_pre_exact_line $upstream_summary $literal
}

set flow_start_ms [clock milliseconds]
source $selector_lib
source $fine_lib
set phase_start_ms [clock milliseconds]
open_checkpoint $dcp
set open_checkpoint_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE open_checkpoint elapsed_ms=$open_checkpoint_elapsed_ms"
set phase_start_ms [clock milliseconds]
set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set base_discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE base_discovery elapsed_ms=$base_discovery_elapsed_ms"
set phase_start_ms [clock milliseconds]
set fine_plan [hap_v5_fine19::discover $base_plan]
set fine_discovery_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE fine_discovery elapsed_ms=$fine_discovery_elapsed_ms"
set phase_start_ms [clock milliseconds]
hap_v5_fine19::apply $base_plan $fine_plan
set pblock_apply_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE pblock_apply elapsed_ms=$pblock_apply_elapsed_ms"
set phase_start_ms [clock milliseconds]
set audit [hap_v5_fine19::audit $base_plan $fine_plan 0]
set pblock_audit_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
puts "HAP_FINE19_PHASE pblock_audit elapsed_ms=$pblock_audit_elapsed_ms"
hap_v5_fine19::write_discovery $fine_plan \
    [file join $out selectors.txt] V5_FINE19_PRE_PLACE_SELECTORS_PASS
hap_v5_fine19::write_audit $audit \
    [file join $out pblocks.txt] V5_FINE19_PRE_PLACE_PBLOCKS_PASS
set phase_start_ms [clock milliseconds]
report_drc -file [file join $out drc_pre_place.rpt]
set pre_place_drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set pre_place_drc_elapsed_ms [expr {[clock milliseconds] - $phase_start_ms}]
set total_elapsed_ms [expr {[clock milliseconds] - $flow_start_ms}]
puts "HAP_FINE19_PHASE pre_place_drc elapsed_ms=$pre_place_drc_elapsed_ms"
puts "HAP_FINE19_PHASE total elapsed_ms=$total_elapsed_ms"

set status [expr {[dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    [dict get $base_plan projection_weight_capture_ok] == 1 &&
    [dict get $fine_plan projection_exact_cover] == 1 &&
    [dict get $fine_plan region1_exact_cover] == 1 &&
    [dict get $fine_plan owner_exact_cover] == 1 &&
    [dict get $fine_plan weight_owner_residency_ok] == 1 &&
    [dict get $audit pblock_count] == 19 &&
    [dict get $audit member_overlap] == 0 &&
    [dict get $audit dsp_coverage] == 5453 &&
    [dict get $audit uram_coverage] == 752 &&
    [dict get $audit placed_wrong] == 0 &&
    $pre_place_drc_errors == 0 ?
    "V5_FINE19_PRE_PLACE_CONTRACT_AUDIT_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_FINE19_PRE_PLACE_CONTRACT_AUDIT \
        evidence_class V5_FINE19_IN_MEMORY_PBLOCK_DRC \
        contract_variant [dict get $fine_plan contract_variant] jobs $jobs \
        input_dcp $dcp input_dcp_sha256 $expected_dcp_sha \
        input_manifest_sha256 $expected_manifest_sha input_manifest_entries 6 \
        provenance_verified 1 upstream_probe_manifest $upstream_manifest \
        upstream_probe_manifest_sha256 $expected_upstream_sha \
        upstream_probe_verified 1 \
        open_checkpoint_elapsed_ms $open_checkpoint_elapsed_ms \
        base_discovery_elapsed_ms $base_discovery_elapsed_ms \
        fine_discovery_elapsed_ms $fine_discovery_elapsed_ms \
        pblock_apply_elapsed_ms $pblock_apply_elapsed_ms \
        pblock_audit_elapsed_ms $pblock_audit_elapsed_ms \
        pre_place_drc_elapsed_ms $pre_place_drc_elapsed_ms \
        total_elapsed_ms $total_elapsed_ms \
        dsp48e2 [dict get $base_plan total_dsp] \
        uram288 [dict get $base_plan total_uram] \
        mlp_kernel_dsp48e2 [dict get $base_plan kernel_dsp] \
        raw_weight_push_loads [dict get $base_plan raw_weight_push_loads] \
        projection_weight_capture_ok \
            [dict get $base_plan projection_weight_capture_ok] \
        projection_primitives \
            [llength [dict get $fine_plan projection_primitives]] \
        projection_dsp48e2 [hap_v5_floorplan::count_ref \
            [dict get $fine_plan projection_primitives] DSP48E2] \
        center_region1_logic_primitives [llength [dict get $fine_plan \
            center_region1_logic_residual_primitives]] \
        center_region1_cols4_5_dsp48e2 [llength [dict get $fine_plan \
            center_region1_cols4_5_dsp_primitives]] \
        center_region1_cols6_7_dsp48e2 [llength [dict get $fine_plan \
            center_region1_cols6_7_dsp_primitives]] \
        region3_input_primitives \
            [llength [dict get $fine_plan region3_input_primitives]] \
        owner_region2_weight_primitives \
            [llength [dict get $fine_plan owner_region2_weight_primitives]] \
        nonprojection_center_dsp48e2 \
            [llength [dict get $fine_plan nonprojection_center_dsp]] \
        projection_exact_cover [dict get $fine_plan projection_exact_cover] \
        region1_exact_cover [dict get $fine_plan region1_exact_cover] \
        owner_exact_cover [dict get $fine_plan owner_exact_cover] \
        weight_owner_residency_ok \
            [dict get $fine_plan weight_owner_residency_ok] \
        planned_slr0_dsp48e2 1862 planned_slr1_dsp48e2 1781 \
        planned_slr2_dsp48e2 1810 planned_slr0_uram288 224 \
        planned_slr1_uram288 224 planned_slr2_uram288 304 \
        pblock_count [dict get $audit pblock_count] \
        pblock_member_count [dict get $audit member_count] \
        pblock_overlap [dict get $audit member_overlap] \
        pblock_optimizer_extras [dict get $audit optimizer_extra_count] \
        pblock_dsp_coverage [dict get $audit dsp_coverage] \
        pblock_uram_coverage [dict get $audit uram_coverage] \
        pblock_wrong_slr [dict get $audit placed_wrong] \
        pre_place_drc_errors $pre_place_drc_errors \
        checkpoint_written 0 implementation_commands_run 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "V5_FINE19_PRE_PLACE_CONTRACT_AUDIT_PASS"} {
    error "V5 fine19 pre-place contract audit failed"
}
close_design
