
set ::exports [list];set ::ranges [list];set ::assigned [dict create];set ::members [list];set ::created 0
namespace eval slr2 {
 variable P [dict create top/a/p0 LUT1 top/a/p1 DSP48E2]
 variable originalP [dict create]
 variable pblock CPU_C01_SLR2
 variable cellPblocks [dict create]
 variable siteSLR [dict create SLICE_X0Y0 SLR2 DSP48E2_X0Y0 SLR2 RAMB36_X0Y0 SLR2 SLICE_X9Y9 SLR1]
}
proc get_slrs args {return SLR2}
proc get_clock_regions args {return [list X0Y4 X1Y4]}
proc get_pblocks args {if {$::caseName eq "existing_pblock"} {return CPU_C01_SLR2};return [list]}
proc get_property {property objects} {if {$property ne "NAME"} {error BAD_PROPERTY};return $objects}
proc slr2::objects names {return $names}
proc slr2::value {name property} {
 if {$::caseName eq "conflicting_LOC" && $property eq "LOC" && $name eq "top/a/p0"} {return SLICE_X9Y9}
 if {$property in {IS_LOC_FIXED IS_BEL_FIXED DONT_TOUCH}} {return 0};return ""
}
proc slr2::slr site {return [dict get $::slr2::siteSLR $site]}
proc m002_prop {object property} {
 if {$property eq "NAME"} {return $object}
 if {$property eq "GRID_RANGES"} {return $::ranges}
 if {$::caseName eq "soft_readback" && $property eq "IS_SOFT"} {return true}
 return [dict get $::assigned $property]
}
proc create_pblock name {set ::created 1;return $name}
proc resize_pblock {pb option token} {if {$option ne "-add"} {error BAD_RESIZE};lappend ::ranges $token}
proc set_property {property value object} {dict set ::assigned $property $value}
proc add_cells_to_pblock {pb objects} {set ::members $objects}
proc get_cells args {
 if {$::caseName eq "member_readback"} {return [list top/a/p0]};return $::members
}
proc get_sites args {
 if {$::caseName eq "outside_site"} {return [list SLICE_X0Y0 DSP48E2_X0Y0 RAMB36_X0Y0 SLICE_X9Y9]}
 if {$::caseName eq "missing_site"} {return [list SLICE_X0Y0 DSP48E2_X0Y0]}
 return [list SLICE_X0Y0 DSP48E2_X0Y0 RAMB36_X0Y0]
}
proc write_xdc args {
 lappend ::exports $args
 if {[lindex $args 0] eq "-constraints"} {return -code error -errorcode CPU_INVALID_CONSTRAINTS INVALID_CONSTRAINTS_PHYSICAL}
 if {[llength $args] != 3 || [lrange $args 0 1] ne [list -type physical]} {error UNEXPECTED_EXPORT_OPTIONS}
 if {$::caseName eq "native_export_error"} {return -code error -errorcode CPU_XDC_NATIVE_ERROR ACTUAL_EXPORT_ERROR}
 set h [open [lindex $args 2] {WRONLY CREAT EXCL}];puts $h FIXTURE_EXPORT_ONLY;close $h
}
set ::actualCode [catch {slr2::constrain_region} ::actualResult ::actualOptions]
