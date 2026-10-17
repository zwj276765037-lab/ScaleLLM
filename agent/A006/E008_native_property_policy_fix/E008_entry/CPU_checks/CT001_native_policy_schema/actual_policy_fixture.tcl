
set ::caseName $caseName
set ::point before
set ::overlayCreated 0
set ::regionCalls 0
set ::schemaCalls [dict create]
set ::required {NAME REF_NAME IS_PRIMITIVE LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC MACRO_NAME DONT_TOUCH}
set ::data [dict create]
foreach name {top top/a top/a/p0 top/a/p1 outside} {
    set primitive [expr {[string match */p? $name] || $name eq "outside"}]
    set ref [expr {$primitive ? "LUT1" : "hierarchy_ref"}]
    set values [dict create NAME $name REF_NAME $ref IS_PRIMITIVE $primitive LOC "" BEL "" IS_LOC_FIXED 0 IS_BEL_FIXED 0 USER_SLR_ASSIGNMENT "" RLOC "" RLOC_ORIGIN "" MACRO_NAME "" DONT_TOUCH 0]
    dict set ::data $name $values
}
namespace eval slr2 {
    variable root top/a
    variable P [dict create top/a/p0 LUT1 top/a/p1 LUT1]
    variable RAW $P
    variable siteSLR [dict create SLICE_X0Y0 SLR2]
    variable pblock CPU_NEW_PBLOCK
}
proc native_value {object property} {
    if {$::caseName eq "supported_nonempty" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return X0Y0}
    if {$::caseName eq "unsupported_nonempty" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return X0Y0}
    if {$::caseName eq "unsupported_error" && $object eq "top/a/p0" && $property eq "RLOC_ORIGIN"} {return -code error -errorcode CPU_NATIVE_ORIGIN_ERROR NATIVE_READ_FAILED}
    if {$::caseName eq "RLOC_nonempty" && $object eq "top/a" && $property eq "RLOC"} {return X1Y1}
    if {$::caseName eq "MACRO_NAME_nonempty" && $object eq "top/a/p0" && $property eq "MACRO_NAME"} {return ACTUAL_MACRO}
    if {$::caseName eq "conflicting_SLR" && $object eq "top" && $property eq "USER_SLR_ASSIGNMENT"} {return SLR1}
    if {$::caseName eq "after_value_change" && $::point eq "after" && $object eq "top/a/p0" && $property eq "LOC"} {return SLICE_X0Y0}
    return [dict get $::data $object $property]
}
proc list_property object {
    dict incr ::schemaCalls $object
    set props $::required
    if {$::caseName in {supported_empty supported_nonempty} || ($::caseName eq "same_REF_mixed_support" && $object eq "top/a/p1") || ($::caseName eq "after_support_change" && $::point eq "after" && $object eq "top/a/p0")} {lappend props RLOC_ORIGIN}
    if {[string match missing_* $::caseName] && $object eq "top/a/p1"} {
        set missing [string range $::caseName 8 end]
        set i [lsearch -exact $props $missing];if {$i>=0} {set props [lreplace $props $i $i]}
    }
    return $props
}
proc get_property {property objects} {
    if {[llength $objects]==1} {return [native_value [lindex $objects 0] $property]}
    set out [list];foreach object $objects {lappend out [native_value $object $property]};return $out
}
proc m002_prop {object property} {return [native_value $object $property]}
proc m002_exact {command name} {if {[dict exists $::data $name]} {return $name};return [list]}
proc slr2::property_values {objects property allow_empty context} {
    set values [list];foreach object $objects {lappend values [native_value $object $property]};return $values
}
proc slr2::objects names {return $names}
proc slr2::pblock_snapshot {} {
    set old [dict create OLD_PBLOCK [list [dict create IS_SOFT false] [list outside]]]
    if {$::overlayCreated} {dict set old $::slr2::pblock [list [dict create IS_SOFT false] [list top/a/p0 top/a/p1]]}
    return $old
}
proc slr2::constrain_region {} {incr ::regionCalls;set ::overlayCreated 1;set ::point after}
proc get_cells args {
    if {"-hier" in $args} {return [list top/a top/a/p0 top/a/p1]}
    if {"-of_objects" in $args} {
        if {$::caseName eq "macro_partners_error"} {error NATIVE_MACRO_PARTNERS_FAILED}
        return [list top/a/p0 outside]
    }
    return [list]
}
proc get_macros args {
    if {$::caseName eq "macro_enumeration_error"} {error NATIVE_MACROS_FAILED}
    if {$::caseName in {excluded_macro_partner macro_partners_error}} {return [list MACRO1]}
    return [list]
}
if {$::caseName eq "macro_api_missing"} {rename get_macros {}}
set ::actualCode [catch {slr2::constrain} ::actualResult ::actualOptions]
