# Read-only reopen audit for the frozen Run 0138 V5 post-place checkpoint.
# This script only opens the checkpoint and queries live hierarchy, pblocks,
# primitive placement and resource distribution.  All output is external to
# the checkpoint artifact.

set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set fixed_dcp [file normalize [file join $root vivado reports \
    production_v5_place_20260817_223533 post_place.dcp]]
set selector_lib [file join $script_dir \
    v5_production_floorplan_selectors.tcl]
set out [file normalize $::env(HAP_REOPEN_AUDIT_DIR)]
set input_sha [file normalize $::env(HAP_REOPEN_INPUT_SHA)]
set expected_dcp_sha \
    63aa1417c862419edb102e85da15e28cfc1b52bec2136ad8ae72a1084a450b7a
file mkdir $out

proc hap_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing or empty $label: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_verify_sha_manifest {path expected_count} {
    set count 0
    set seen [dict create]
    foreach raw [split [hap_read_nonempty $path "input SHA manifest"] "\n"] {
        set line [string trim $raw]
        if {$line eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(.+)$} \
                $line -> expected file_name]} {
            error "Malformed input SHA row: $line"
        }
        set normalized [file normalize [string trim $file_name]]
        if {[dict exists $seen $normalized]} {
            error "Duplicate input SHA path: $normalized"
        }
        hap_read_nonempty $normalized "frozen audit input"
        set actual [lindex [exec sha256sum $normalized] 0]
        if {$actual ne $expected} {
            error "Input SHA mismatch: file=$normalized expected=$expected actual=$actual"
        }
        dict set seen $normalized $expected
        incr count
    }
    if {$count != $expected_count} {
        error "Input SHA cardinality mismatch: expected=$expected_count actual=$count"
    }
    return $seen
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "V5 reopen audit requires a fresh process with no open design"
}
hap_read_nonempty $fixed_dcp "fixed Run 0138 post-place DCP"
hap_read_nonempty $selector_lib "V5 selector library"
set frozen [hap_verify_sha_manifest $input_sha 4]
foreach path [list $fixed_dcp $selector_lib [file normalize [info script]]] {
    if {![dict exists $frozen [file normalize $path]]} {
        error "Required reopen input is absent from SHA manifest: $path"
    }
}
set actual_dcp_sha [lindex [exec sha256sum $fixed_dcp] 0]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "Run 0138 DCP identity mismatch: expected=$expected_dcp_sha actual=$actual_dcp_sha"
}

source $selector_lib
open_checkpoint $fixed_dcp

# Every collection below is discovered after reopening the placed checkpoint;
# no object handle from the original placement process is available here.
set live_plan [hap_v5_floorplan::discover legacy10]
hap_v5_floorplan::write_discovery $live_plan \
    [file join $out selectors_live_reopen.txt] \
    V5_POST_PLACE_LIVE_REOPEN_SELECTORS_PASS
set pblock_audit \
    [hap_v5_floorplan::audit_pblock_contract $live_plan 1 legacy10]
hap_v5_floorplan::write_pblock_audit $pblock_audit \
    [file join $out pblocks_live_reopen.txt] \
    V5_POST_PLACE_LIVE_REOPEN_PBLOCKS_PASS
set metrics [hap_v5_floorplan::physical_metrics \
    $live_plan $pblock_audit]

set slr_dsp [dict get $metrics slr_dsp]
set slr_uram [dict get $metrics slr_uram]
set slr_ramb36 [dict get $metrics slr_ramb36]
set exact_resource_ok [expr {
    [dict get $live_plan total_dsp] == 5469 &&
    [dict get $live_plan total_uram] == 752 &&
    [dict get $live_plan kernel_dsp] == 3072 &&
    [dict get $live_plan branch0_dsp] == 1536 &&
    [dict get $live_plan branch2_dsp] == 1536 &&
    [dict get $live_plan history2_count] == 2 &&
    [dict get $live_plan generic_repack_count] == 0
}]
set exact_distribution_ok [expr {
    $slr_dsp eq {1791 1870 1808} &&
    $slr_uram eq {224 224 304}
}]
set exact_pblock_ok [expr {
    [dict get $pblock_audit ok] == 1 &&
    [dict get $pblock_audit contract_variant] eq "legacy10" &&
    [dict get $pblock_audit pblock_count] == 10 &&
    [dict get $pblock_audit dsp_coverage] == 5469 &&
    [dict get $pblock_audit uram_coverage] == 752 &&
    [dict get $pblock_audit placed_wrong] == 0
}]
set exact_placement_ok [expr {
    [hap_v5_floorplan::physical_ok $live_plan $metrics] &&
    [dict get $metrics unplaced] == 0 &&
    [dict get $metrics wrong_total] == 0
}]
set status [expr {$exact_resource_ok && $exact_distribution_ok &&
    $exact_pblock_ok && $exact_placement_ok ?
    "V5_POST_PLACE_LIVE_REOPEN_AUDIT_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] evidence_class V5_POST_PLACE_READ_ONLY_REOPEN \
    input_dcp $fixed_dcp input_dcp_sha256 $actual_dcp_sha \
    part [dict get $live_plan part] top [dict get $live_plan top] \
    live_rediscovery 1 pblock_contract_variant \
        [dict get $pblock_audit contract_variant] \
    pblock_count [dict get $pblock_audit pblock_count] \
    pblock_members [dict get $pblock_audit member_count] \
    pblock_optimizer_extras \
        [dict get $pblock_audit optimizer_extra_count] \
    pblock_dsp_coverage [dict get $pblock_audit dsp_coverage] \
    pblock_uram_coverage [dict get $pblock_audit uram_coverage] \
    pblock_wrong_slr [dict get $pblock_audit placed_wrong] \
    global_virtual_gnd [dict get $metrics global_virtual_gnd] \
    global_virtual_vcc [dict get $metrics global_virtual_vcc] \
    global_virtual_total [dict get $metrics global_virtual_total] \
    global_physical_primitives [dict get $metrics global_physical_count] \
    global_direct_slr_empty [dict get $metrics global_direct_slr_empty] \
    global_is_placed_empty [dict get $metrics global_is_placed_empty] \
    dsp48e2 [dict get $live_plan total_dsp] \
    mlp_kernel_dsp48e2 [dict get $live_plan kernel_dsp] \
    branch0_dsp48e2 [dict get $live_plan branch0_dsp] \
    branch2_dsp48e2 [dict get $live_plan branch2_dsp] \
    uram288 [dict get $live_plan total_uram] \
    slr0_dsp48e2 [lindex $slr_dsp 0] \
    slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] per_slr_dsp_limit 1900 \
    slr0_uram288 [lindex $slr_uram 0] \
    slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    slr0_ramb36e2 [lindex $slr_ramb36 0] \
    slr1_ramb36e2 [lindex $slr_ramb36 1] \
    slr2_ramb36e2 [lindex $slr_ramb36 2] \
    unplaced_primitives [dict get $metrics unplaced] \
    wrong_slr_primitives [dict get $metrics wrong_total] \
    branch0_wrong_slr [dict get $metrics branch0_wrong] \
    branch2_wrong_slr [dict get $metrics branch2_wrong] \
    attention_lane0_wrong_slr [dict get $metrics lane0_wrong] \
    attention_lane2_wrong_slr [dict get $metrics lane2_wrong] \
    center_dsp_wrong_slr [dict get $metrics center_wrong] \
    metadata_gate0_wrong_slr [dict get $metrics gate0_wrong] \
    metadata_gate2_wrong_slr [dict get $metrics gate2_wrong] \
    metadata_down0_wrong_slr [dict get $metrics down0_wrong] \
    metadata_down1_wrong_slr [dict get $metrics down1_wrong] \
    attention_metadata_wrong_slr \
        [dict get $metrics attention_meta_wrong] \
    exact_resource_ok $exact_resource_ok \
    exact_distribution_ok $exact_distribution_ok \
    exact_pblock_ok $exact_pblock_ok \
    exact_placement_ok $exact_placement_ok checkpoint_written 0 \
    implementation_commands_run 0 status $status] {
    puts $fp "$key=$value"
}
foreach label [lsort -dictionary \
        [dict keys [dict get $metrics collection_audits]]] {
    set audit [dict get $metrics collection_audits $label]
    foreach key {physical_count virtual_gnd virtual_vcc virtual_total
        direct_slr_empty is_placed_empty target wrong} {
        puts $fp "${label}_${key}=[dict get $audit $key]"
    }
}
close $fp

puts "V5_POST_PLACE_LIVE_REOPEN DSP=$slr_dsp URAM=$slr_uram PBLOCKS=[dict get $pblock_audit pblock_count] COVERAGE=[dict get $pblock_audit dsp_coverage]/[dict get $pblock_audit uram_coverage] UNPLACED=[dict get $metrics unplaced] WRONG_SLR=[dict get $metrics wrong_total] STATUS=$status"
close_design
if {$status ne "V5_POST_PLACE_LIVE_REOPEN_AUDIT_PASS"} {
    error "V5 post-place live reopen physical audit failed"
}
