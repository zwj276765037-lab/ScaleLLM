namespace eval hap_mock {
    variable properties [dict create]
    variable pin_nets [dict create]
    variable net_drivers [dict create]
    variable net_loads [dict create]
    variable cells {}
}

proc hap_mock::reset {} {
    variable properties
    variable pin_nets
    variable net_drivers
    variable net_loads
    variable cells
    set properties [dict create]
    set pin_nets [dict create]
    set net_drivers [dict create]
    set net_loads [dict create]
    set cells {}
}

proc hap_mock::set_property {object property value} {
    variable properties
    dict set properties $object $property $value
}

proc hap_mock::add_fdre {name is_original original_name bit} {
    variable cells
    variable pin_nets
    variable net_drivers
    variable net_loads
    lappend cells $name
    foreach {property value} [list NAME $name IS_ORIG_CELL $is_original \
            ORIG_CELL_NAME $original_name REF_NAME FDRE ORIG_REF_NAME FDRE \
            INIT 1'b0] {
        set_property $name $property $value
    }
    foreach {pin net} [list D DATA_$bit C CORE_CLOCK CE ENABLE R RESET] {
        dict set pin_nets $name/$pin $net
    }
    set q_net Q_[string map {/ _ { } _ {[} _ {]} _} $name]
    dict set pin_nets $name/Q $q_net
    dict set net_drivers $q_net $name/Q
    dict set net_loads $q_net LOAD_[string map {/ _} $name]/D
}

proc hap_mock::baseline {} {
    reset
    set root ROOT
    set root_name TOP/SHARED
    set_property $root NAME $root_name
    set c0 [format {%s/parent_count_r_reg[%d]} $root_name 0]
    set c1 [format {%s/parent_count_r_reg[%d]} $root_name 1]
    set r0 ${c0}_replica_0
    set r1 ${c1}_replica_0
    add_fdre $c0 1 {} 0
    add_fdre $c1 1 {} 1
    add_fdre $r0 0 {parent_count_r_reg[0]} 0
    add_fdre $r1 0 {parent_count_r_reg[1]} 1
    return [dict create root $root c0 $c0 c1 $c1 r0 $r0 r1 $r1 \
        cells [list $c0 $c1 $r0 $r1]]
}

proc list_property {object} {
    variable ::hap_mock::properties
    if {![dict exists $properties $object]} {return {}}
    return [dict keys [dict get $properties $object]]
}

proc get_property {property objects} {
    variable ::hap_mock::properties
    set values {}
    foreach object $objects {
        if {![dict exists $properties $object $property]} {
            if {$property eq "NAME"} {
                lappend values $object
                continue
            }
            error "mock property is missing: $object/$property"
        }
        lappend values [dict get $properties $object $property]
    }
    if {[llength $values] == 1} {return [lindex $values 0]}
    return $values
}

proc get_cells {args} {
    variable ::hap_mock::cells
    set requested [lindex $args end]
    if {[lsearch -exact $cells $requested] >= 0} {return $requested}
    return {}
}

proc get_pins {args} {
    variable ::hap_mock::pin_nets
    variable ::hap_mock::net_drivers
    variable ::hap_mock::net_loads
    set object [lindex $args [expr {[lsearch -exact $args -of_objects] + 1}]]
    set filter [lindex $args [expr {[lsearch -exact $args -filter] + 1}]]
    if {[regexp {REF_PIN_NAME == ([A-Z]+)} $filter -> ref_pin]} {
        set pin $object/$ref_pin
        if {[dict exists $pin_nets $pin]} {return $pin}
        return {}
    }
    if {[regexp {DIRECTION == (OUT|IN)} $filter -> direction]} {
        if {$direction eq "OUT" && [dict exists $net_drivers $object]} {
            return [dict get $net_drivers $object]
        }
        if {$direction eq "IN" && [dict exists $net_loads $object]} {
            return [dict get $net_loads $object]
        }
        return {}
    }
    error "unexpected mock get_pins filter: $filter"
}

proc get_nets {args} {
    variable ::hap_mock::pin_nets
    set object [lindex $args [expr {[lsearch -exact $args -of_objects] + 1}]]
    if {[dict exists $pin_nets $object]} {return [dict get $pin_nets $object]}
    return {}
}

proc hap_mock::run_contract {fixture} {
    return [hap_mlp_p8_parent_boundary::parent_count_contract \
        [dict get $fixture root] [dict get $fixture cells]]
}

proc hap_mock::expect_error {label body expected_pattern} {
    set code [catch {uplevel 1 $body} message]
    if {$code == 0} {error "$label unexpectedly passed"}
    if {![string match $expected_pattern $message]} {
        error "$label wrong failure: expected=$expected_pattern actual=$message"
    }
    puts "$label=PASS"
}

source $::env(HAP_P8_REPLICA_AUDIT_LIB)

set fixture [hap_mock::baseline]
set metrics [hap_mock::run_contract $fixture]
foreach {key expected} {
    parent_count_ff 2
    parent_count_physical_ff 4
    parent_count_replica_ff 2
    parent_count_bit0_physical_ff 2
    parent_count_bit1_physical_ff 2
    parent_count_replica_equivalence_ok 1
} {
    if {[dict get $metrics $key] != $expected} {
        error "baseline metric mismatch: $key"
    }
}
puts baseline_equivalent_replicas=PASS

set fixture [hap_mock::baseline]
hap_mock::set_property [dict get $fixture r0] ORIG_CELL_NAME wrong_state_reg
hap_mock::expect_error wrong_orig_cell_name {
    hap_mock::run_contract $fixture
} {parent_count_accounted_ff count mismatch:*}

set fixture [hap_mock::baseline]
dict set ::hap_mock::pin_nets [dict get $fixture r0]/D BAD_DATA
hap_mock::expect_error mismatched_d {
    hap_mock::run_contract $fixture
} {parent count replica D mismatch:*}

foreach {label pin bad_net} {
    mismatched_clock C BAD_CLOCK
    mismatched_clock_enable CE BAD_ENABLE
    mismatched_reset R BAD_RESET
} {
    set fixture [hap_mock::baseline]
    dict set ::hap_mock::pin_nets [dict get $fixture r1]/$pin $bad_net
    hap_mock::expect_error $label {
        hap_mock::run_contract $fixture
    } "parent count replica $pin mismatch:*"
}

set fixture [hap_mock::baseline]
hap_mock::set_property [dict get $fixture r1] INIT 1'b1
hap_mock::expect_error mismatched_init {
    hap_mock::run_contract $fixture
} {parent count replica INIT mismatch:*}

set fixture [hap_mock::baseline]
set c2 [format {%s/parent_count_r_reg[%d]} TOP/SHARED 2]
hap_mock::add_fdre $c2 1 {} 2
dict lappend fixture cells $c2
hap_mock::expect_error unexpected_third_canonical_state_bit {
    hap_mock::run_contract $fixture
} {parent_count_canonical_ff count mismatch: expected=2 actual=3}

puts P8_PARENT_INGRESS_REPLICA_AWARE_NEGATIVE_MOCK_PASS
