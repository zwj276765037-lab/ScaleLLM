namespace eval hap_v5_floorplan {}
namespace eval hap_v5_p5_input_partition {}

proc hap_v5_floorplan::module_cells {module_name} {return {Q0 Q1 Q2 Q3}}
proc hap_v5_p5_input_partition::require_count {label objects expected} {
    if {[llength $objects] != $expected} {
        error "$label count mismatch: expected=$expected actual=[llength $objects]"
    }
}
proc get_property {property objects} {
    set result {}
    foreach object $objects {
        if {$property eq "NAME"} {
            if {[regexp {^Q([0-3])$} $object -> index]} {
                set value "TOP/u_swiglu/g_quantizer\[$index\].u_quantizer"
            } else {
                set value $object
            }
        } elseif {$property eq "REF_NAME"} {
            if {[string match Q3:L* $object]} {
                set value LUT6
            } elseif {[string match Q3:F* $object]} {
                set value FDRE
            } elseif {$object eq "Q3:DSP"} {
                set value DSP48E2
            } else {
                set value CARRY8
            }
        } else {
            error "unexpected property: $property"
        }
        lappend result $value
    }
    if {[llength $result] == 1} {return [lindex $result 0]}
    return $result
}
proc hap_v5_floorplan::primitive_descendants {root} {
    if {$root ne "Q3"} {return $root}
    set cells {}
    for {set i 0} {$i < 6731} {incr i} {lappend cells Q3:L$i}
    for {set i 0} {$i < 3955} {incr i} {lappend cells Q3:F$i}
    lappend cells Q3:DSP
    for {set i 0} {$i < 491} {incr i} {lappend cells Q3:O$i}
    return $cells
}
proc hap_v5_floorplan::pblockable_primitives {cells} {return $cells}
proc hap_v5_p5_input_partition::hard_signature {cells} {
    return [dict create dsp 1 uram 0 ramb36 0 ramb18 0]
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

source $::env(HAP_P10_QUANTIZER3_LIB)
set base [dict create contract_variant P2_COHORT16_COL2_12_2]
set p5 [dict create contract P5_INPUT_HALF_LOCAL_8_8 \
    half0_primitives P5A half1_primitives P5B center_primitives P5C]
set post [dict create contract P9_POSTPROCESS_SPLIT_6_4_6 \
    all_rows POST]
set plan [hap_v5_p10_quantizer3_locality::discover $base $p5 $post]
foreach {key expected} {
    contract P10_SWIGLU_QUANTIZER3_CR_X0Y5_X2Y5
    primitive_count 11178
    lut 6731
    ff 3955
    grid_range CLOCKREGION_X0Y5:CLOCKREGION_X2Y5
    allowed_regions {X0Y5 X1Y5 X2Y5}
} {
    if {[dict get $plan $key] ne $expected} {
        error "P10 quantizer3 mock mismatch: $key"
    }
}
puts P10_QUANTIZER3_SELECTOR_MOCK_DISCOVERY_PASS
