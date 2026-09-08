# Tcl-only negative regression for the full-board BUFG/BUFG_GT_SYNC gate.
# It mocks the small read-only Vivado object-query surface used by
# hap_v5_board_gate::bufg_topology, so it must never start Vivado.

namespace eval mock {
    variable cell_ref
    variable cell_name
    variable cell_pins
    variable pin_ref
    variable pin_dir
    variable pin_cell
    variable pin_net
    variable pin_clocks
    variable net_loads
}

proc mock::reset {} {
    foreach name {cell_ref cell_name cell_pins pin_ref pin_dir pin_cell
            pin_net pin_clocks net_loads} {
        variable $name
        array unset $name
    }
    variable cell_name
    set cell_name(core) top/bd/core/inst
}

proc mock::add_cell {cell ref name} {
    variable cell_ref
    variable cell_name
    variable cell_pins
    set cell_ref($cell) $ref
    set cell_name($cell) $name
    set cell_pins($cell) {}
}

proc mock::add_pin {cell pin ref direction} {
    variable cell_pins
    variable pin_ref
    variable pin_dir
    variable pin_cell
    lappend cell_pins($cell) $pin
    set pin_ref($pin) $ref
    set pin_dir($pin) $direction
    set pin_cell($pin) $cell
}

proc mock::baseline {} {
    mock::reset
    mock::add_cell ce BUFGCE top/bd/clk_core/bufg
    mock::add_pin ce ce_o O OUT
    mock::add_cell gt BUFG_GT top/bd/xdma/gt_buf
    foreach {pin ref direction} {
        gt_o O OUT gt_ce CE IN gt_clr CLR IN
    } {mock::add_pin gt $pin $ref $direction}
    mock::add_cell sync BUFG_GT_SYNC top/bd/xdma/gt_sync
    foreach {pin ref direction} {
        sync_ce CE IN sync_clk CLK IN sync_clr CLR IN
        sync_cesync CESYNC OUT sync_clrsync CLRSYNC OUT
    } {mock::add_pin sync $pin $ref $direction}

    variable pin_net
    variable pin_clocks
    variable net_loads
    foreach pin {sync_ce sync_clk sync_clr sync_cesync sync_clrsync} {
        set pin_net($pin) net_$pin
    }
    set pin_clocks(ce_o) clk_core
    set pin_clocks(gt_o) clk_gt
    set pin_clocks(sync_clk) clk_gt_source
    set net_loads(net_sync_cesync) {gt_ce}
    set net_loads(net_sync_clrsync) {gt_clr}
}

proc mock::option_value {args option} {
    set index [lsearch -exact $args $option]
    if {$index < 0 || $index + 1 >= [llength $args]} {return {}}
    return [lindex $args [expr {$index + 1}]]
}

proc get_cells {args} {
    variable mock::cell_ref
    variable mock::pin_cell
    if {[lsearch -exact $args -hierarchical] >= 0} {
        set result {}
        foreach cell [array names cell_ref] {
            if {[string match "BUFG*" $cell_ref($cell)]} {lappend result $cell}
        }
        return $result
    }
    set objects [mock::option_value $args -of_objects]
    set result {}
    foreach object $objects {
        if {[info exists pin_cell($object)]} {lappend result $pin_cell($object)}
    }
    return [lsort -dictionary -unique $result]
}

proc get_pins {args} {
    variable mock::cell_pins
    variable mock::pin_ref
    variable mock::pin_dir
    variable mock::net_loads
    set objects [mock::option_value $args -of_objects]
    set filter [mock::option_value $args -filter]
    set result {}
    if {[lsearch -exact $args -leaf] >= 0} {
        foreach net $objects {
            if {[info exists net_loads($net)]} {
                set result [concat $result $net_loads($net)]
            }
        }
    } else {
        foreach cell $objects {
            if {[info exists cell_pins($cell)]} {
                set result [concat $result $cell_pins($cell)]
            }
        }
    }
    if {$filter ne {}} {
        set wanted_ref *
        set wanted_dir *
        regexp {REF_PIN_NAME == ([^ ]+)} $filter -> wanted_ref
        regexp {DIRECTION == ([^ ]+)} $filter -> wanted_dir
        set filtered {}
        foreach pin $result {
            if {[info exists pin_ref($pin)] && [info exists pin_dir($pin)] &&
                [string match $wanted_ref $pin_ref($pin)] &&
                [string match $wanted_dir $pin_dir($pin)]} {
                lappend filtered $pin
            }
        }
        set result $filtered
    }
    return [lsort -dictionary -unique $result]
}

proc get_nets {args} {
    variable mock::pin_net
    set result {}
    foreach pin [mock::option_value $args -of_objects] {
        if {[info exists pin_net($pin)]} {lappend result $pin_net($pin)}
    }
    return [lsort -dictionary -unique $result]
}

proc get_clocks {args} {
    variable mock::pin_clocks
    set result {}
    foreach pin [mock::option_value $args -of_objects] {
        if {[info exists pin_clocks($pin)]} {
            lappend result $pin_clocks($pin)
        }
    }
    return [lsort -dictionary -unique $result]
}

proc get_property {property object} {
    variable mock::cell_ref
    variable mock::cell_name
    variable mock::pin_ref
    switch -- $property {
        NAME {
            if {[info exists cell_name($object)]} {return $cell_name($object)}
            return $object
        }
        REF_NAME {
            if {[info exists cell_ref($object)]} {return $cell_ref($object)}
            return {}
        }
        REF_PIN_NAME {
            if {[info exists pin_ref($object)]} {return $pin_ref($object)}
            return {}
        }
        default {error "mock get_property does not support $property"}
    }
}

set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir attention_mlp_vcu118_v5_post_route_gate.tcl]

proc require_field {result key expected label} {
    if {![dict exists $result $key] || [dict get $result $key] ne $expected} {
        error "$label expected $key=$expected actual=[dict get $result $key]"
    }
}

proc require_rejected {label key} {
    set result [hap_v5_board_gate::bufg_topology core]
    require_field $result bufg_topology_ok 0 $label
    if {![dict exists $result $key] || [dict get $result $key] == 0} {
        error "$label did not set rejection metric $key"
    }
}

mock::baseline
set good [hap_v5_board_gate::bufg_topology core]
foreach {key value} {
    bufg_family_total 3 real_bufg_total 2 clock_bufg 2 data_bufg 0
    real_bufg_bad_connections 0 bufg_gt_total 1 bufg_gt_clock 1
    bufg_gt_data 0 bufg_gt_sync_total 1
    bufg_gt_sync_clk_without_clock 0
    bufg_gt_sync_cesync_leaf_loads 1
    bufg_gt_sync_clrsync_leaf_loads 1
    bufg_gt_sync_bad_connections 0 production_core_bufg_gt_sync 0
    bufg_partition_ok 1 bufg_gt_sync_topology_ok 1 bufg_topology_ok 1
} {require_field $good $key $value positive}

mock::baseline
unset mock::pin_clocks(gt_o)
require_rejected bufg_gt_without_o_clock bufg_gt_data

mock::baseline
set mock::net_loads(net_sync_cesync) {gt_clr}
require_rejected cesync_to_wrong_leaf bufg_gt_sync_bad_connections

mock::baseline
set mock::net_loads(net_sync_clrsync) {}
require_rejected clrsync_without_leaf bufg_gt_sync_bad_connections

mock::baseline
unset mock::pin_clocks(sync_clk)
require_rejected gt_sync_clk_without_clock bufg_gt_sync_clk_without_clock

mock::baseline
set mock::cell_name(sync) top/bd/core/inst/hidden_gt_sync
require_rejected production_core_gt_sync production_core_bufg_gt_sync

mock::baseline
mock::add_pin sync sync_unknown UNKNOWN OUT
require_rejected gt_sync_unknown_pin bufg_gt_sync_bad_connections

mock::baseline
set mock::cell_ref(sync) BUFG_GT_SYNC_FAKE
require_rejected similar_name_is_not_excluded real_bufg_bad_connections

mock::baseline
set mock::cell_ref(sync) LUT1
set missing_sync [hap_v5_board_gate::bufg_topology core]
require_field $missing_sync bufg_topology_ok 0 missing_gt_sync
require_field $missing_sync bufg_gt_sync_total 0 missing_gt_sync
require_field $missing_sync bufg_gt_sync_topology_ok 0 missing_gt_sync

puts V5_BOARD_BUFG_TOPOLOGY_STATIC_TEST_PASS
puts negative_cases=8
