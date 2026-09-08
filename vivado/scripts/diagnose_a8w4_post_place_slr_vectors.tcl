set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set out [file normalize $::env(HAP_REPORT_DIR)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
set actual_dcp_sha [lindex [exec sha256sum -- $input_dcp] 0]
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    $actual_dcp_sha ne $expected_dcp_sha} {
    error "post-place diagnostic DCP SHA256 mismatch"
}

proc audit_slr_vector {cells label expected_slr} {
    set total [llength $cells]
    set values [get_property SLR_INDEX $cells]
    if {$total == 0 || [llength $values] != $total} {
        error "$label SLR vector length mismatch"
    }
    set expected 0
    set other 0
    set unplaced 0
    set invalid 0
    foreach value $values {
        if {$value eq ""} {
            incr unplaced
        } elseif {![regexp {([0-2])$} $value -> index]} {
            incr invalid
        } elseif {$index == $expected_slr} {
            incr expected
        } else {
            incr other
        }
    }
    return [dict create total $total expected $expected other $other \
        unplaced $unplaced invalid $invalid]
}

open_checkpoint $input_dcp
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e"} {
    error "post-place diagnostic part mismatch"
}
set primitives [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND &&
    REF_NAME != VCC && REF_NAME !~ BUFG*}]
set dsps [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]
set primitive_audit [audit_slr_vector $primitives primitives 0]
set dsp_audit [audit_slr_vector $dsps dsp48e2 0]
set status [expr {
    [dict get $primitive_audit total] == 429191 &&
    [dict get $primitive_audit expected] == 429191 &&
    [dict get $primitive_audit other] == 0 &&
    [dict get $primitive_audit unplaced] == 0 &&
    [dict get $primitive_audit invalid] == 0 &&
    [dict get $dsp_audit total] == 1536 &&
    [dict get $dsp_audit expected] == 1536 &&
    [dict get $dsp_audit other] == 0 &&
    [dict get $dsp_audit unplaced] == 0 &&
    [dict get $dsp_audit invalid] == 0 ? "PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
        stage READ_ONLY_POST_PLACE_SLR_VECTOR_DIAG input_dcp $input_dcp \
        input_dcp_sha256 $actual_dcp_sha \
        primitive_total [dict get $primitive_audit total] \
        primitive_slr0 [dict get $primitive_audit expected] \
        primitive_other_slr [dict get $primitive_audit other] \
        primitive_unplaced [dict get $primitive_audit unplaced] \
        primitive_invalid_slr [dict get $primitive_audit invalid] \
        dsp_total [dict get $dsp_audit total] \
        dsp_slr0 [dict get $dsp_audit expected] \
        dsp_other_slr [dict get $dsp_audit other] \
        dsp_unplaced [dict get $dsp_audit unplaced] \
        dsp_invalid_slr [dict get $dsp_audit invalid] \
        implementation_commands 0 checkpoints_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
close_design
if {$status ne "PASS"} {error "post-place SLR vector diagnostic failed"}
