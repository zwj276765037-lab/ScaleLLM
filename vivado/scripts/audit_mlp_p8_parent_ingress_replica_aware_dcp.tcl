# Read-only P8 parent-ingress audit for post-opt or implemented checkpoints.

set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_AUDIT_DIR)]
set input_sha [file normalize $::env(HAP_AUDIT_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_AUDIT_INPUT_MANIFEST_SHA256)
set boundary_lib [file normalize $::env(HAP_P8_BOUNDARY_LIB)]
set p10_proc_lib [file normalize $::env(HAP_P8_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_AUDIT_LAUNCHER)]
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

if {![string match "2025.2*" [version -short]]} {
    error "P8 replica-aware boundary audit requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P8 replica-aware boundary audit requires a fresh Vivado process"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P8 replica-aware boundary audit received malformed SHA256"
    }
}
set frozen [hap_p10_verify_manifest $input_sha 5 $expected_manifest_sha]
foreach required [list $dcp $boundary_lib $p10_proc_lib $audit_script \
        $expected_launcher] {
    if {![dict exists $frozen $required]} {
        error "P8 replica-aware boundary input absent from manifest: $required"
    }
}
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P8 replica-aware boundary DCP identity mismatch"
}

source $boundary_lib
open_checkpoint $dcp
set top [get_property TOP [current_design]]
set part [get_property PART [current_design]]
if {$top ne "hap_attention_mlp_production_core" ||
    $part ne "xcvu9p-flga2104-2L-e"} {
    error "P8 replica-aware boundary top/part mismatch: $top/$part"
}
set metrics [hap_mlp_p8_parent_boundary::audit]
hap_mlp_p8_parent_boundary::write_audit $metrics \
    [file join $out p8_parent_ingress_boundary.txt] \
    V5_P8_PARENT_INGRESS_REPLICA_AWARE_DCP_PASS

set summary [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage V5_P8_PARENT_INGRESS_REPLICA_AWARE_DCP_AUDIT \
        evidence_class READ_ONLY_DCP_REOPEN \
        input_dcp $dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 5 top $top part $part \
        parent_head_ff [dict get $metrics parent_head_ff] \
        parent_tail_ff [dict get $metrics parent_tail_ff] \
        parent_count_ff [dict get $metrics parent_count_ff] \
        parent_count_physical_ff \
            [dict get $metrics parent_count_physical_ff] \
        parent_count_replica_ff \
            [dict get $metrics parent_count_replica_ff] \
        parent_count_bit0_physical_ff \
            [dict get $metrics parent_count_bit0_physical_ff] \
        parent_count_bit1_physical_ff \
            [dict get $metrics parent_count_bit1_physical_ff] \
        parent_count_replica_equivalence_ok \
            [dict get $metrics parent_count_replica_equivalence_ok] \
        parent_pointer_ff [dict get $metrics parent_pointer_ff] \
        local_clear_ff [dict get $metrics local_clear_ff] \
        branch_ingress_count_ff [dict get $metrics branch_ingress_count_ff] \
        local_clear_shared_upstream_ready_paths \
            [dict get $metrics local_clear_shared_upstream_ready_paths] \
        branch_credit_shared_upstream_ready_paths \
            [dict get $metrics branch_credit_shared_upstream_ready_paths] \
        local_clear_gate_compute_ready_paths \
            [dict get $metrics local_clear_gate_compute_ready_paths] \
        branch_credit_gate_compute_ready_paths \
            [dict get $metrics branch_credit_gate_compute_ready_paths] \
        local_clear_down_compute_ready_paths \
            [dict get $metrics local_clear_down_compute_ready_paths] \
        branch_credit_down_compute_ready_paths \
            [dict get $metrics branch_credit_down_compute_ready_paths] \
        local_clear_input_cache_ready_paths \
            [dict get $metrics local_clear_input_cache_ready_paths] \
        branch_credit_input_cache_ready_paths \
            [dict get $metrics branch_credit_input_cache_ready_paths] \
        implementation_commands_run 0 checkpoint_written 0 route_eligible 0 \
        status V5_P8_PARENT_INGRESS_REPLICA_AWARE_DCP_AUDIT_PASS] {
    puts $summary "$key=$value"
}
close $summary
close_design

