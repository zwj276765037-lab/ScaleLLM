set script_dir [file dirname [file normalize [info script]]]
set dcp [file normalize $::env(HAP_DCP)]
set bitstream [file normalize $::env(HAP_BITSTREAM)]
set out [file normalize $::env(HAP_AUDIT_DIR)]
set xdc_inventory [file normalize $::env(HAP_XDC_INVENTORY)]
set input_files [file normalize [file join $out INPUT_FILES]]
set input_sha [file normalize [file join $out INPUT_SHA256SUMS]]
set expected_input_manifest_sha $::env(HAP_AUDIT_INPUT_MANIFEST_SHA256)
set audit_tcl [file normalize [info script]]
set gate_tcl [file normalize [file join $script_dir \
    attention_mlp_vcu118_v5_post_route_gate.tcl]]
set selector_tcl [file normalize [file join $script_dir \
    v5_production_floorplan_selectors.tcl]]
set geometry_tcl [file normalize [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]]
set p5_tcl [file normalize [file join $script_dir \
    v5_production_p5_input_partition_floorplan.tcl]]
set p6_tcl [file normalize [file join $script_dir \
    v5_production_p6_postprocess_partition_floorplan.tcl]]
set launcher [file normalize [file join $script_dir \
    run_attention_mlp_vcu118_v5_post_route_audit.sh]]
file mkdir $out

proc hap_audit_read_nonempty {path label} {
    if {![file exists $path] || ![file isfile $path] || [file size $path] == 0} {
        error "Missing or empty V5 board audit $label: $path"
    }
    set fh [open $path r]
    set text [read $fh]
    close $fh
    return $text
}

proc hap_audit_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Malformed SHA256 for $path: $digest"
    }
    return $digest
}

proc hap_audit_exact_path_list {path expected} {
    set seen [dict create]
    foreach raw [split [hap_audit_read_nonempty $path "INPUT_FILES"] "\n"] {
        set row [string trim $raw]
        if {$row eq ""} {continue}
        set normalized [file normalize $row]
        if {$row ne $normalized || [file pathtype $row] ne "absolute"} {
            error "Noncanonical INPUT_FILES row: $row"
        }
        if {[dict exists $seen $normalized]} {
            error "Duplicate INPUT_FILES row: $normalized"
        }
        dict set seen $normalized 1
    }
    set wanted [lsort -dictionary $expected]
    set actual [lsort -dictionary [dict keys $seen]]
    if {$actual ne $wanted} {
        error "INPUT_FILES exact path mismatch: expected=$wanted actual=$actual"
    }
}

proc hap_audit_verify_inputs {manifest expected_manifest_sha expected} {
    if {![regexp {^[0-9a-f]{64}$} $expected_manifest_sha]} {
        error "Malformed expected audit INPUT_SHA256SUMS SHA256"
    }
    if {[hap_audit_sha256 $manifest] ne $expected_manifest_sha} {
        error "Audit INPUT_SHA256SUMS self-SHA mismatch"
    }
    set entries [dict create]
    foreach raw [split [hap_audit_read_nonempty $manifest \
            "INPUT_SHA256SUMS"] "\n"] {
        set row [string trim $raw]
        if {$row eq ""} {continue}
        if {![regexp {^([0-9a-f]{64})[[:space:]]+\*?(/.+)$} \
                $row -> expected_sha path]} {
            error "Malformed audit INPUT_SHA256SUMS row: $row"
        }
        set normalized [file normalize $path]
        if {$path ne $normalized || [dict exists $entries $normalized]} {
            error "Noncanonical or duplicate audit input path: $path"
        }
        hap_audit_read_nonempty $normalized "frozen input"
        set actual_sha [hap_audit_sha256 $normalized]
        if {$actual_sha ne $expected_sha} {
            error "Audit frozen-input SHA mismatch: $normalized"
        }
        dict set entries $normalized $actual_sha
    }
    set wanted [lsort -dictionary $expected]
    set actual [lsort -dictionary [dict keys $entries]]
    if {[dict size $entries] != 10 || $actual ne $wanted} {
        error "Audit input-manifest exact path mismatch: expected=$wanted actual=$actual"
    }
    return $entries
}

set exact_inputs [list $dcp $bitstream $xdc_inventory $audit_tcl \
    $gate_tcl $selector_tcl $geometry_tcl $p5_tcl $p6_tcl $launcher]
hap_audit_exact_path_list $input_files $exact_inputs
set frozen_inputs [hap_audit_verify_inputs $input_sha \
    $expected_input_manifest_sha $exact_inputs]

# No checkpoint is opened and no gate library is sourced until all ten
# absolute paths, their file digests and the manifest's own digest agree.
source $gate_tcl
open_checkpoint $dcp
set result [hap_v5_board_gate::audit $out $xdc_inventory $bitstream]
hap_audit_exact_path_list $input_files $exact_inputs
set frozen_inputs_post [hap_audit_verify_inputs $input_sha \
    $expected_input_manifest_sha $exact_inputs]
if {$frozen_inputs_post ne $frozen_inputs} {
    error "Audit frozen-input set changed during the Vivado process"
}
set dcp_hash [lindex [exec sha256sum $dcp] 0]
set bit_hash [dict get $result bitstream_sha256]
set fp [open [file join $out summary.txt] w]
dict for {key value} $result {
    if {$key eq "status"} {
        puts $fp "post_route_gate_status=$value"
    } else {
        puts $fp "$key=$value"
    }
}
puts $fp "checkpoint=$dcp"
puts $fp "checkpoint_size_bytes=[file size $dcp]"
puts $fp "checkpoint_sha256=$dcp_hash"
puts $fp "audit_input_manifest_entries=[dict size $frozen_inputs]"
puts $fp "audit_input_manifest_sha256=$expected_input_manifest_sha"
puts $fp "audit_input_manifests_verified=1"
puts $fp "status=V5_BOARD_INDEPENDENT_AUDIT_PASS"
close $fp
puts "V5_BOARD_INDEPENDENT_AUDIT_PASS DCP=$dcp_hash BIT=$bit_hash"
close_design
