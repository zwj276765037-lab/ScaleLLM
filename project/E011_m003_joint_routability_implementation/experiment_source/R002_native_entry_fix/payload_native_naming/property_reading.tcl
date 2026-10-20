# Per-object support reused only inside one read-only function invocation.
proc m003::supported_prop {object name supported} {
    if {$name ni $supported} {return NOT_SUPPORTED}
    return [get_property -quiet $name $object]
}
proc m003::hard_pblock {name sites cells} {
    variable ancestor_pblocks
    # Refuse unknown fixed or macro restrictions before assigning new bounds.
    foreach cell $cells {
        set supported [list_property $cell]
        foreach property {IS_LOC_FIXED IS_BEL_FIXED} {
            set value [supported_prop $cell $property $supported]
            if {$value eq "NOT_SUPPORTED"} {error "M003 unknown fixed-resource policy: $cell/$property"}
        }
        set macro [supported_prop $cell MACRO_NAME $supported]
        if {$macro ni {{} NOT_SUPPORTED}} {error "M003 native macro requires explicit compatibility qualification: $cell/$macro"}
        foreach relative {RLOC RLOC_ORIGIN} {
            set restriction [supported_prop $cell $relative $supported]
            if {$restriction ni {{} NOT_SUPPORTED}} {error "M003 relative placement restriction requires explicit qualification: $cell/$relative=$restriction"}
        }
        set existing [get_pblocks -quiet -of_objects $cell]
        set ancestor [file dirname $cell]
        while {$ancestor ni {. /}} {
            if {![dict exists $ancestor_pblocks $ancestor]} {
                set object [one get_cells $ancestor]
                dict set ancestor_pblocks $ancestor [get_pblocks -quiet -of_objects $object]
            }
            set existing [concat $existing [dict get $ancestor_pblocks $ancestor]]
            set ancestor [file dirname $ancestor]
        }
        foreach other $existing {
            if {$other ne $name && ![yes [prop $other IS_SOFT]]} {
                error "M003 incompatible pre-existing hard pblock: $cell/$other versus $name"
            }
        }
        if {[yes [supported_prop $cell IS_LOC_FIXED $supported]]} {
            set loc [supported_prop $cell LOC $supported]
            set allowed [get_sites -quiet $sites]
            if {[get_sites -quiet $loc] ni $allowed} {error "M003 fixed LOC outside target pool: $cell/$loc"}
        }
    }
    set pb [get_pblocks -quiet $name]
    if {[llength $pb] > 1} {error "M003 duplicate pblock: $name"}
    if {![llength $pb]} {create_pblock $name;set pb [get_pblocks $name]}
    foreach property {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {set_property $property 0 $pb}
    resize_pblock $pb -add $sites
    add_cells_to_pblock $pb $cells
    return $pb
}
proc m003::cell_row {cell role extra} {
    set d [dict create role $role NAME [get_property NAME $cell] REF_NAME [get_property REF_NAME $cell]]
    set supported [list_property $cell]
    foreach p {LOC BEL IS_LOC_FIXED IS_BEL_FIXED RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH ORIG_CELL_NAME ORIG_REF_NAME USER_SLR_ASSIGNMENT} {dict set d $p [supported_prop $cell $p $supported]}
    dict set d PBLOCKS [get_property NAME [get_pblocks -quiet -of_objects $cell]]
    set loc [dict get $d LOC]
    if {$loc ne "" && $loc ne "NOT_SUPPORTED"} {
        set site [get_sites -quiet $loc]
        dict set d SLR [get_property NAME [get_slrs -quiet -of_objects $site]]
        dict set d clock_region [get_property NAME [get_clock_regions -quiet -of_objects $site]]
    } else {dict set d SLR UNPLACED;dict set d clock_region UNPLACED}
    return [dict merge $d $extra]
}
