set dcp [file normalize $::env(HAP_DIAGNOSTIC_DCP)]
set out [file normalize $::env(HAP_DIAGNOSTIC_AUDIT_DIR)]
set expected_dcp_sha $::env(HAP_EXPECTED_DIAGNOSTIC_DCP_SHA256)
file mkdir $out

proc hap_slr_diag_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_slr_diag_counts {objects} {
    if {[llength $objects] == 0} {
        return {0 0 0 0}
    }
    set counts {0 0 0}
    set unplaced 0
    foreach value [get_property SLR_INDEX $objects] {
        if {[regexp {([0-2])$} $value -> index]} {
            lset counts $index [expr {[lindex $counts $index] + 1}]
        } else {
            incr unplaced
        }
    }
    return [list {*}$counts $unplaced]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {[llength [get_designs -quiet]] != 0} {
    error "SLR utilization diagnostic requires a fresh Vivado process"
}
if {[hap_slr_diag_sha256 $dcp] ne $expected_dcp_sha} {
    error "SLR utilization diagnostic DCP identity mismatch"
}
set_param general.maxThreads 32
open_checkpoint $dcp
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 4 \
    -file [file join $out utilization_hier_depth4_post_place.rpt]
set hierarchy_fp [open [file join $out hierarchy_slr_placement.txt] w]
foreach {label root} {
    mlp_input_frontend u_compute/u_mlp/u_input_frontend
    mlp_gate_scheduler u_compute/u_mlp/u_serial_command/u_gate_scheduler
    mlp_swiglu u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu
    mlp_down_scheduler u_compute/u_mlp/u_serial_command/u_down_scheduler
    mlp_branch0 u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch0
    mlp_branch1 u_compute/u_mlp/u_serial_command/u_shared_compute/u_branch1
    paired_weight u_paired_weight
    attention_center_region1 u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region1_cols4_7
} {
    set primitives [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${root}/* && IS_PRIMITIVE"]
    if {[llength $primitives] == 0} {
        error "SLR utilization diagnostic hierarchy is empty: $label $root"
    }
    puts $hierarchy_fp "${label}_root=$root"
    puts $hierarchy_fp "${label}_primitives=[hap_slr_diag_counts $primitives]"
    foreach {resource pattern} {
        lut LUT* ff FD* dsp DSP48E2 ramb36 RAMB36E2 ramb18 RAMB18E2
        uram URAM288
    } {
        set cells [get_cells -quiet -hierarchical -filter \
            "NAME =~ ${root}/* && REF_NAME =~ $pattern"]
        puts $hierarchy_fp \
            "${label}_${resource}=[hap_slr_diag_counts $cells]"
    }
}
puts $hierarchy_fp "status=PASS"
close $hierarchy_fp
set fp [open [file join $out summary.txt] w]
puts $fp "tool=[version -short]"
puts $fp "stage=V5_POST_PLACE_SLR_UTILIZATION_DIAGNOSTIC"
puts $fp "evidence_class=READ_ONLY_DIAGNOSTIC"
puts $fp "input_dcp=$dcp"
puts $fp "input_dcp_sha256=$expected_dcp_sha"
puts $fp "implementation_commands_run=0"
puts $fp "checkpoint_written=0"
puts $fp "route_eligible=0"
puts $fp "status=PASS"
close $fp
close_design
