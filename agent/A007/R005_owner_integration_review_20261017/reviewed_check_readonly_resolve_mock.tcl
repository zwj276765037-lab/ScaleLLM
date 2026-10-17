# Actual readonly_resolve integration; only native API responses are mocked.
# The actual slr2::owner procedure is never replaced or stubbed.
source [lindex $argv 0]
source [file join [file dirname [lindex $argv 0]] directed_exporter.tcl]
set ::m002_report_dir [lindex $argv 1]
file mkdir $::m002_report_dir
set base scalellm_vcu118_f05_bd_i/core/inst/u_core/
set root {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/branch[1]}
set peer ${base}u_tensor/peer
set ::props [dict create]
foreach {name ref primitive loc bel} [list $root test_hierarchy 0 {} {} $root/r FDRE 1 SLICE_X0Y0 AFF $root/gnd GND 1 {} {} $peer FDRE 1 SLICE_X0Y0 BFF] {
    set values [dict create NAME $name REF_NAME $ref IS_PRIMITIVE $primitive LOC $loc BEL $bel]
    foreach property {IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH ORIG_CELL_NAME ORIG_REF_NAME} {dict set values $property {}}
    dict set ::props $name $values
}
proc get_property args {
    if {[lindex $args 0] eq "-quiet"} {set args [lrange $args 1 end]}
    lassign $args property objects
    set result [list]
    foreach object $objects {
        if {$property eq "NAME" && $object in {SLICE_X0Y0 TILE_X0Y0 REGION0}} {lappend result $object;continue}
        if {![dict exists $::props $object $property]} {error "Unexpected mock property: $object/$property"}
        lappend result [dict get $::props $object $property]
    }
    if {[llength $objects]==1} {return [lindex $result 0]}
    return $result
}
proc list_property object {return [dict keys [dict get $::props $object]]}
proc get_cells args {
    set filter [lindex $args [expr {[lsearch -exact $args -filter]+1}]]
    if {[regexp {^NAME == "(.*)"$} $filter -> exact]} {
        if {[dict exists $::props $exact]} {return [list $exact]}
        return [list]
    }
    set siteMode [expr {[lsearch -exact $args -of_objects]>=0}]
    set result [list]
    dict for {name properties} $::props {
        if {![dict get $properties IS_PRIMITIVE]} {continue}
        if {!$siteMode || [dict get $properties LOC] eq "SLICE_X0Y0"} {lappend result $name}
    }
    return $result
}
proc get_pblocks args {return [list]}
proc get_sites args {return SLICE_X0Y0}
proc get_tiles args {return TILE_X0Y0}
proc get_clock_regions args {return REGION0}
set ::slr2::siteSLR [dict create SLICE_X0Y0 SLR1]
set actual [slr2::readonly_resolve test $root]
if {[get_property NAME $actual] ne $root} {error "Actual exact root differs"}
foreach tag {RAW S P} expected {2 1 1} {
    if {[dict size [set ::slr2::$tag]]!=$expected} {error "Actual mock $tag membership differs"}
}
set h [open [file join $::m002_report_dir candidate_site_members_test.tsv]]
set content [read $h];close $h
if {[string first "\t${base}u_tensor\t" $content]<0 || [string first "\t${base}u_compute/u_mlp\t" $content]<0} {error "Actual owner module/site export failed: $content"}
if {![file exists [file join $::m002_report_dir candidate_membership_test_closed.txt]]} {error "Actual readonly_resolve did not close"}
puts [list actual_readonly_resolve PASS actual_owner_not_stubbed true RAW 2 S 1 P 1 shared_site_rows 2 literal_brackets true constant_empty_LOC_retained true]
