# Mission 0195 policy for the only legal Region2 post-place optimizer delta.
# The policy is deliberately pure Tcl so its positive and negative cases can
# be tested without opening Vivado.

namespace eval hap_v5_p17_optimizer_delta {
    variable contract P17_EXACT_TWO_ATTN_S42_LUT5_REMOVALS
    variable expected_ref_name LUT5
    variable expected_orig_ref_name LUT5
    variable expected_init {32'h00A20000}
    variable expected_removed_names [lsort -dictionary [list \
        {u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/g_dual_accumulator.u_accumulator/g_physical_split.g_buffered_input/lower_head_guard_s42_r[364]_i_3} \
        {u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/g_dual_accumulator.u_accumulator/g_physical_split.g_buffered_input/lower_head_guard_s42_r[608]_i_3}]]
}

proc hap_v5_p17_optimizer_delta::sorted_unique {names label} {
    set sorted [lsort -dictionary $names]
    set unique [lsort -dictionary -unique $names]
    if {[llength $sorted] != [llength $unique]} {
        error "$label contains duplicate names"
    }
    return $sorted
}

proc hap_v5_p17_optimizer_delta::list_subtract {left right} {
    set right_set [dict create]
    foreach name $right {dict set right_set $name 1}
    set result {}
    foreach name $left {
        if {![dict exists $right_set $name]} {lappend result $name}
    }
    return [lsort -dictionary $result]
}

proc hap_v5_p17_optimizer_delta::expected_names {} {
    variable expected_removed_names
    return $expected_removed_names
}

proc hap_v5_p17_optimizer_delta::capture_records {cells} {
    set records [dict create]
    foreach cell $cells {
        set name [get_property NAME $cell]
        if {[dict exists $records $name]} {
            error "duplicate pre-place residual primitive: $name"
        }
        dict set records $name [dict create \
            ref_name [get_property REF_NAME $cell] \
            orig_ref_name [get_property ORIG_REF_NAME $cell] \
            init [get_property INIT $cell]]
    }
    return $records
}

proc hap_v5_p17_optimizer_delta::validate {
        pre_records pre_names post_names reported_removed_lut} {
    variable contract
    variable expected_ref_name
    variable expected_orig_ref_name
    variable expected_init
    variable expected_removed_names

    set pre [sorted_unique $pre_names pre_names]
    set post [sorted_unique $post_names post_names]
    set removed [list_subtract $pre $post]
    set added [list_subtract $post $pre]

    if {$removed ne $expected_removed_names} {
        error "optimizer removed an unapproved identity: expected=$expected_removed_names actual=$removed"
    }
    if {[llength $added] != 0} {
        error "optimizer added residual primitives: $added"
    }
    if {![string is integer -strict $reported_removed_lut] ||
        $reported_removed_lut != 2} {
        error "rediscovery removal count mismatch: expected=2 actual=$reported_removed_lut"
    }

    foreach name $expected_removed_names {
        if {![dict exists $pre_records $name]} {
            error "missing pre-place identity record: $name"
        }
        set record [dict get $pre_records $name]
        foreach {key expected} [list ref_name $expected_ref_name \
                orig_ref_name $expected_orig_ref_name init $expected_init] {
            if {![dict exists $record $key] ||
                [dict get $record $key] ne $expected} {
                set actual [expr {[dict exists $record $key] ?
                    [dict get $record $key] : "<missing>"}]
                error "removed primitive property mismatch: name=$name property=$key expected=$expected actual=$actual"
            }
        }
    }

    return [dict create ok 1 contract $contract removed_names $removed \
        removed_count 2 removed_lut 2 removed_non_lut 0 added_count 0]
}

proc hap_v5_p17_optimizer_delta::write_audit {audit path status} {
    set fp [open $path w]
    foreach key {ok contract removed_count removed_lut removed_non_lut
            added_count removed_names} {
        puts $fp "$key=[dict get $audit $key]"
    }
    puts $fp "status=$status"
    close $fp
}
