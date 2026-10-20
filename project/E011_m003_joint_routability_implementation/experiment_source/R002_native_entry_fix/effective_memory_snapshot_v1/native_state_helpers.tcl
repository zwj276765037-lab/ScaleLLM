# Preserve raw timing startpoints and independently query actual source state.
proc m003::address_state_evidence {cell} {
    set dp [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
    exact_count $dp 1 "address D $cell"
    set points [all_fanin -quiet -flat -startpoints_only -to $dp]
    set cone [all_fanin -quiet -flat -to $dp]
    set only [all_fanin -quiet -flat -startpoints_only -only_cells -to $dp]
    set cone_names [collection_property NAME $cone];set cone_set [dict create]
    foreach name $cone_names {dict set cone_set $name 1}
    set facts [list]
    foreach point $points {
        set name [get_property NAME $point];set class [get_property CLASS $point]
        set owner_names [list];set refs [list];set qnames [list];set members [list]
        if {[string tolower $class] eq "pin"} {
            set owners [get_cells -quiet -of_objects $point]
            exact_count $owners 1 "address startpoint actual owner $name"
            set owner_names [collection_property NAME $owners];set refs [collection_property REF_NAME $owners]
            set qs [get_pins -quiet -of_objects $owners -filter {REF_PIN_NAME == Q}]
            foreach qp $qs {
                set qname [get_property NAME $qp];lappend qnames $qname
                lappend members [expr {[dict exists $cone_set $qname] ? 1 : 0}]
            }
        }
        lappend facts [dict create raw_name $name class $class owner_names $owner_names owner_refs $refs owner_Q_pins $qnames owner_Q_in_full_fanin $members]
    }
    return [dict create D_startpoints [collection_property NAME $points] D_full_fanin $cone_names D_startpoint_cells [collection_property NAME $only] D_startpoint_cell_refs [collection_property REF_NAME $only] D_source_facts [jarray $facts]]
}

proc m003::memory_pin_row {index cell pin} {
    set terminal [get_property REF_PIN_NAME $pin]
    set nets [get_nets -quiet -segments -of_objects $pin]
    set drivers [list];set owners [list];set refs [list];set ports [list];set dirs [list]
    if {[llength $nets]} {
        set drivers [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]
    }
    foreach driver $drivers {
        set owner [get_cells -quiet -of_objects $driver]
        exact_count $owner 1 "memory driver owner $cell/$terminal"
        lappend owners [get_property NAME $owner];lappend refs [get_property REF_NAME $owner]
    }
    set points [list]
    if {[string match ADDR* $terminal] || [string match CAS_IN_ADDR* $terminal]} {
        set points [all_fanin -quiet -flat -startpoints_only -to $pin]
    }
    if {$terminal eq "CLK" && [llength $nets] && ![llength $drivers]} {
        set ports [get_ports -quiet -of_objects $nets]
        foreach port $ports {lappend dirs [get_property DIRECTION $port]}
    }
    return [dict create slice $index cell $cell pin $terminal drivers [collection_property NAME $drivers] driver_cells $owners driver_refs $refs startpoints [memory_startpoint_names $terminal $points] nets [collection_property NAME $nets] primary_ports [collection_property NAME $ports] primary_port_directions $dirs]
}
