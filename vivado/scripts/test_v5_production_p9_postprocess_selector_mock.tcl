namespace eval hap_v5_floorplan {}
namespace eval hap_v5_p5_input_partition {}

proc hap_v5_floorplan::module_cells {module_name} {return ROOT}
proc hap_v5_p5_input_partition::require_count {label objects expected} {
    if {[llength $objects] != $expected} {error "$label count mismatch"}
}
proc hap_v5_p5_input_partition::module_children {root module_name} {
    set rows {}
    for {set index 0} {$index < 16} {incr index} {lappend rows R$index}
    return $rows
}
proc get_property {property objects} {
    set out {}
    foreach object $objects {
        if {$property eq "NAME"} {
            if {$object eq "ROOT"} {
                set value TOP/STORE
            } elseif {[regexp {^R([0-9]+)$} $object -> row]} {
                set value [format {TOP/STORE/g_row_bank[%d].u_bank} $row]
            } else {
                set value $object
            }
        } elseif {$property eq "REF_NAME"} {
            if {[string match *:L* $object]} {
                set value LUT6
            } elseif {[string match *:F* $object]} {
                set value FDRE
            } else {
                set value CARRY8
            }
        } else {
            error "unexpected property: $property"
        }
        lappend out $value
    }
    if {[llength $out] == 1} {return [lindex $out 0]}
    return $out
}
proc hap_v5_floorplan::primitive_descendants {row} {return $row}
proc hap_v5_floorplan::pblockable_primitives {row} {
    if {![regexp {^R([0-9]+)$} $row -> index]} {error "bad row: $row"}
    set cells {}
    for {set i 0} {$i < 994} {incr i} {lappend cells $index:L$i}
    for {set i 0} {$i < 1536} {incr i} {lappend cells $index:F$i}
    for {set i 0} {$i < 144} {incr i} {lappend cells $index:O$i}
    return $cells
}
proc hap_v5_p5_input_partition::hard_signature {cells} {
    return [dict create dsp 0 uram 0 ramb36 0 ramb18 0]
}
proc hap_v5_floorplan::list_union {args} {
    return [lsort -unique [concat {*}$args]]
}
proc hap_v5_floorplan::list_intersection {left right} {
    set present [dict create]
    foreach item $left {dict set present $item 1}
    set result {}
    foreach item $right {
        if {[dict exists $present $item]} {lappend result $item}
    }
    return [lsort -unique $result]
}

source $::env(HAP_P9_SELECTOR_LIB)
set base [dict create contract_variant P2_COHORT16_COL2_12_2]
set p5 [dict create contract P5_INPUT_HALF_LOCAL_8_8 \
    half0_primitives P5A half1_primitives P5B center_primitives P5C]
set plan [hap_v5_p9_postprocess_partition::discover $base $p5]
foreach {key expected} {
    all_rows 42784 slr0_rows 16044 center_rows 10696 slr2_rows 16044
} {
    if {[llength [dict get $plan $key]] != $expected} {
        error "P9 mock partition mismatch: $key"
    }
}
if {[dict get $plan contract] ne "P9_POSTPROCESS_SPLIT_6_4_6"} {
    error "P9 mock partition contract mismatch"
}
puts P9_SELECTOR_MOCK_DISCOVERY_PASS
