proc m003::original_address_members {} {
    variable core_meta_scope
    set members [dict create]
    set selected [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*meta_read_addr_r_reg*"} $core_meta_scope]]
    exact_count $selected [llength $selected] "original core address candidates"
    foreach cell $selected {
        set name [get_property NAME $cell]
        set ref [get_property REF_NAME $cell]
        if {![prefix $name $core_meta_scope]} {error "M003 foreign original core address scope: $name"}
        set relative [string range $name [expr {[string length $core_meta_scope]+1}] end]
        # AT016 measured these two combinational CARRY8 neighbors separately
        # from the complete 17 FDCE state bits. They are never address FFs.
        if {$relative in {{meta_read_addr_r_reg[16]_i_5} {meta_read_addr_r_reg[8]_i_2}}} {
            if {$ref ne "CARRY8"} {error "M003 original core address neighbor type changed: $name/$ref"}
            continue
        }
        if {![regexp {^meta_read_addr_r_reg\[(0|[1-9][0-9]*)\]$} $relative -> bit] ||
            $bit>=17 || $ref ni {FDRE FDCE FDSE FDPE} || [dict exists $members $bit]} {
            error "M003 original core address role unresolved: $name/$ref"
        }
        dict set members $bit $cell
    }
    if {[dict size $members]!=17} {error "M003 original core address17 missing"}
    for {set bit 0} {$bit<17} {incr bit} {
        if {![dict exists $members $bit]} {error "M003 original core address bit $bit missing"}
    }
    return $members
}
proc m003::resolve {} {
    variable parent_scope;variable meta_scope;variable core_meta_scope;variable c01_root
    variable resolved;variable groups
    set resolved [dict create]
    foreach root [list $parent_scope $meta_scope $core_meta_scope $c01_root] {one get_cells $root}
    set family_bits [payload_members];set buffers [dict create]
    foreach cell [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*u_ce_buffer"} $parent_scope]] {
        set name [get_property NAME $cell]
        if {![regexp {g_(head|tail)_ce\[([0-9]+)\].*u_ce_buffer$} $name -> family index]} {error "M003 buffer origin unknown: $name"}
        if {[get_property REF_NAME $cell] ne "LUT1" || ![yes [get_property DONT_TOUCH $cell]] || [init_value [get_property INIT $cell]] != 2 || [dict exists $buffers $family $index]} {error "M003 buffer primitive/protection mismatch: $cell"}
        dict set buffers $family $index $cell
    }
    foreach {family n} {head 42 tail 39} {
        if {![dict exists $buffers $family] || [dict size [dict get $buffers $family]] != $n} {error "M003 $family production buffer count mismatch"}
    }
    dict set resolved payload $family_bits;dict set resolved buffers $buffers
    dict set resolved core_address [original_address_members]
    set meta [primitive_scope $meta_scope];set memory [dict create];set addresses [dict create];set helpers [dict create]
    foreach cell $meta {
        set name [get_property NAME $cell];set ref [get_property REF_NAME $cell]
        if {[string match URAM* $ref]} {
            if {![regexp {g_slice\[([01])\]} $name -> index]} {error "M003 URAM not in selected slice: $name"}
            dict lappend memory $index $cell
        }
        if {[regexp {g_slice\[([01])\].*u_addr/} $name -> index]} {
            dict lappend helpers $index $cell
            if {[regexp {address_r_reg\[([0-9]+)\]$} $name -> bit]} {
                if {$ref ni {FDCE FDRE} || $bit>=17 || ![yes [get_property DONT_TOUCH $cell]] || [dict exists $addresses $index $bit]} {error "M003 address FF/protection/origin mismatch: $name"}
                dict set addresses $index $bit $cell
            }
        }
    }
    foreach index {0 1} {
        exact_count [dict get $memory $index] 40 "slice$index URAM"
        if {[dict size [dict get $addresses $index]] != 17} {error "M003 address state count mismatch: $index"}
        foreach {suffix ref value} {u_local_ce LUT3 254 u_local_increment LUT2 2} {
            set matches [list]
            foreach cell [dict get $helpers $index] {if {[file tail $cell] eq $suffix} {lappend matches $cell}}
            exact_count $matches 1 "slice$index/$suffix";set cell [lindex $matches 0]
            if {[get_property REF_NAME $cell] ne $ref || [init_value [get_property INIT $cell]] != $value || ![yes [get_property DONT_TOUCH $cell]]} {error "M003 local control primitive/protection mismatch: $cell"}
        }
    }
    dict set resolved meta_all $meta;dict set resolved memory $memory;dict set resolved addresses $addresses;dict set resolved helpers $helpers
    dict set resolved c01 [primitive_scope $c01_root]
    if {![llength [dict get $resolved c01]]} {error "M003 C01 physical membership empty"}
    return $resolved
}
