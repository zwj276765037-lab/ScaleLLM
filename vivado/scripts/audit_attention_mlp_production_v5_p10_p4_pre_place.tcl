# Strict in-memory pre-place audit for the P4 physical 4/8/4 candidate.

set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PREPLACE_AUDIT_DIR)]
set input_sha [file normalize $::env(HAP_PREPLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PREPLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PREPLACE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_PREPLACE_GEOMETRY_LIB)]
set pblock_lib [file normalize $::env(HAP_PREPLACE_PBLOCK_LIB)]
set physical_lib [file normalize $::env(HAP_PREPLACE_PHYSICAL_LIB)]
set expected_launcher [file normalize $::env(HAP_PREPLACE_LAUNCHER)]
set audit_script [file normalize [info script]]

proc hap_p4_read_nonempty {path label} {
    if {![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fp [open $path r]
    set text [read $fp]
    close $fp
    return $text
}

proc hap_p4_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path"
    }
    return $digest
}

proc hap_p4_verify_manifest {path expected_count expected_sha} {
    if {[hap_p4_sha256 $path] ne $expected_sha} {
        error "P4 input manifest identity mismatch"
    }
    set seen [dict create]
    set count 0
    foreach raw [split [hap_p4_read_nonempty $path "P4 input manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected name]} {
            error "Malformed P4 manifest row: $line"
        }
        set normalized [file normalize [string trim $name]]
        if {[dict exists $seen $normalized] ||
            [hap_p4_sha256 $normalized] ne $expected} {
            error "P4 manifest member mismatch: $normalized"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "P4 manifest count mismatch: expected=$expected_count actual=$count"
    }
    return $seen
}

if {![string match "2025.2*" [version -short]] ||
    [llength [get_designs -quiet]] != 0} {
    error "P4 pre-place audit requires fresh Vivado 2025.2"
}
if {![file isdirectory $out]} {
    error "Missing P4 audit output directory: $out"
}
set frozen [hap_p4_verify_manifest $input_sha 7 $expected_manifest_sha]
foreach path [list $dcp $selector_lib $geometry_lib $pblock_lib $physical_lib \
        $audit_script $expected_launcher] {
    if {![dict exists $frozen $path]} {
        error "P4 required input absent from manifest: $path"
    }
}
set actual_dcp_sha [hap_p4_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P4 DCP identity mismatch"
}

source $selector_lib
source $geometry_lib
source $pblock_lib
source $physical_lib
set_param general.maxThreads 32
open_checkpoint $dcp

set base_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]
set projection_root [file dirname \
    [get_property NAME [dict get $base_plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set physical_plan [hap_v5_physical448::discover $base_plan $geometry_plan]

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "P4 compute-net selector is empty"
}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "P4 compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
}

hap_v5_physical448::apply $physical_plan
set audit [hap_v5_physical448::audit $physical_plan 0]
set pblock_count [llength [get_pblocks -quiet]]
hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors.txt] V5_P10_P4_BASE_SELECTORS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry.txt] V5_P10_P4_GEOMETRY_PASS
hap_v5_physical448::write_plan $physical_plan \
    [file join $out physical448_plan.txt] V5_P10_P4_PHYSICAL_PLAN_PASS
hap_v5_fine19::write_audit $audit \
    [file join $out pblocks.txt] V5_P10_P4_PBLOCK_AUDIT_PASS
report_drc -file [file join $out drc_pre_place.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
report_utilization -file [file join $out utilization_pre_place.rpt]

set status [expr {
    [dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    [dict get $base_plan history2_count] == 2 &&
    [dict get $base_plan generic_repack_count] == 0 &&
    [dict get $base_plan projection_weight_capture_ok] == 1 &&
    [dict get $physical_plan projected_slr_dsp] eq {2198 1173 2082} &&
    [dict get $physical_plan projected_slr_uram] eq {224 224 304} &&
    [dict get $physical_plan member_overlap] == 0 &&
    [dict get $audit ok] && [dict get $audit pblock_count] == 19 &&
    [dict get $audit dsp_coverage] == 5453 &&
    [dict get $audit uram_coverage] == 752 &&
    $pblock_count == 19 && $drc_errors == 0 ?
    "V5_P10_P4_PRE_PLACE_PASS" : "FAIL"
}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        evidence_class V5_P10_P4_READ_ONLY_PRE_PLACE \
        input_dcp $dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p4_sha256 $input_sha] \
        input_manifest_entries 7 provenance_verified 1 \
        base_contract_variant [dict get $base_plan contract_variant] \
        physical_contract_variant [dict get $physical_plan contract_variant] \
        dsp48e2 [dict get $base_plan total_dsp] \
        uram288 [dict get $base_plan total_uram] \
        mlp_kernel_dsp48e2 [dict get $base_plan kernel_dsp] \
        history2_repack_instances [dict get $base_plan history2_count] \
        generic_repack_instances [dict get $base_plan generic_repack_count] \
        projection_weight_capture_ok \
            [dict get $base_plan projection_weight_capture_ok] \
        pblock_count $pblock_count \
        pblock_member_count [dict get $audit member_count] \
        pblock_overlap [dict get $audit member_overlap] \
        pblock_dsp_coverage [dict get $audit dsp_coverage] \
        pblock_uram_coverage [dict get $audit uram_coverage] \
        center_extra_dsp48e2 [dict get $physical_plan center_extra_dsp] \
        moved_projection_frontend_dsp48e2 \
            [dict get $physical_plan moved_frontend_dsp] \
        center_residual_dsp48e2 \
            [dict get $physical_plan center_residual_dsp] \
        projected_slr_dsp48e2 [dict get $physical_plan projected_slr_dsp] \
        projected_slr_uram288 [dict get $physical_plan projected_slr_uram] \
        region0_target_slr [dict get $physical_plan region0_target] \
        region3_target_slr [dict get $physical_plan region3_target] \
        compute_clock_buffer_none_count [llength $compute_nets] \
        pre_place_drc_errors $drc_errors implementation_commands_run 0 \
        checkpoint_written 0 route_eligible 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
close_design
if {$status ne "V5_P10_P4_PRE_PLACE_PASS"} {
    error "P4 strict pre-place gate failed"
}
