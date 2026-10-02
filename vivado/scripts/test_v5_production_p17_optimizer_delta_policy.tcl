set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir v5_production_p17_optimizer_delta_policy.tcl]

proc expect_fail {label script} {
    if {![catch {uplevel 1 $script} message]} {
        error "$label unexpectedly passed"
    }
    return $message
}

set expected [hap_v5_p17_optimizer_delta::expected_names]
if {[llength $expected] != 2} {error "expected whitelist cardinality mismatch"}
set keep keep_residual_lut
set records [dict create]
foreach name $expected {
    dict set records $name [dict create ref_name LUT5 orig_ref_name LUT5 \
        init {32'h00A20000}]
}
dict set records $keep [dict create ref_name LUT6 orig_ref_name LUT6 init 64'h0]

set pass [hap_v5_p17_optimizer_delta::validate $records \
    [concat $expected [list $keep]] [list $keep] 2]
if {![dict get $pass ok] || [dict get $pass removed_count] != 2 ||
    [dict get $pass added_count] != 0} {
    error "positive policy result mismatch"
}

expect_fail one_removal [list hap_v5_p17_optimizer_delta::validate \
    $records [concat $expected [list $keep]] \
    [list [lindex $expected 1] $keep] 1]
expect_fail unexpected_add [list hap_v5_p17_optimizer_delta::validate \
    $records [concat $expected [list $keep]] [list $keep unexpected] 2]

set wrong_init $records
dict set wrong_init [lindex $expected 0] init {32'h00A20001}
expect_fail wrong_init [list hap_v5_p17_optimizer_delta::validate \
    $wrong_init [concat $expected [list $keep]] [list $keep] 2]

set wrong_ref $records
dict set wrong_ref [lindex $expected 1] ref_name LUT4
expect_fail wrong_ref [list hap_v5_p17_optimizer_delta::validate \
    $wrong_ref [concat $expected [list $keep]] [list $keep] 2]

set wrong_name_records $records
dict set wrong_name_records unexpected_removed \
    [dict create ref_name LUT5 orig_ref_name LUT5 init {32'h00A20000}]
expect_fail wrong_name [list hap_v5_p17_optimizer_delta::validate \
    $wrong_name_records [concat $expected [list unexpected_removed $keep]] \
    [list $keep] 2]

puts P17_OPTIMIZER_DELTA_POLICY_TEST_PASS
