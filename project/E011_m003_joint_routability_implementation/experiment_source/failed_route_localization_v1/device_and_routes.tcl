# Only native device relationships; no region inference from names or numbers.
proc device_inventory {} {
    set ::tileSLR [dict create];set ::tileCR [dict create]
    set h [chan device_relation_receipts.tsv {relation object native_code count error}]
    foreach spec [list [list SLR [get_slrs]] [list CLOCK_REGION [get_clock_regions]]] {
        lassign $spec kind objects
        foreach object $objects {
            set code [catch {get_tiles -quiet -of_objects $object} ts]
            row $h [list $kind $object $code [expr {$code?0:[llength $ts]}] [expr {$code?$ts:""}]]
            if {!$code} {
                foreach tile $ts {
                    if {$kind eq "SLR"} {dict set ::tileSLR $tile $object} else {dict set ::tileCR $tile $object}
                }
            }
        }
    }
    close $h
    set h [chan device_tiles.tsv {tile GRID_POINT_X GRID_POINT_Y SLR clock_region}]
    set tiles [get_tiles -quiet]
    for {set i 0} {$i<[llength $tiles]} {incr i 16384} {
        set b [lrange $tiles $i [expr {$i+16383}]]
        set ns [vals $b NAME];set xs [vals $b GRID_POINT_X 1];set ys [vals $b GRID_POINT_Y 1]
        foreach n $ns x $xs y $ys {
            row $h [list $n $x $y [expr {[dict exists $::tileSLR $n]?[dict get $::tileSLR $n]:"UNKNOWN"}] [expr {[dict exists $::tileCR $n]?[dict get $::tileCR $n]:"UNKNOWN"}]]
        }
    }
    close $h
    set h [chan site_tiles.tsv {site tile native_property}]
    set siteprops [list_property -class site]
    set objects [get_sites -quiet]
    if {"TILE" in $siteprops} {
        for {set i 0} {$i<[llength $objects]} {incr i 16384} {
            set b [lrange $objects $i [expr {$i+16383}]]
            foreach n [vals $b NAME] t [vals $b TILE 1] {row $h [list $n $t TILE]}
        }
    } else {
        # Retain explicit missing linkage; final seed/deep routes still have
        # exact tile relationships. Do not manufacture all-chip site positions.
        row $h [list NOT_MEASURED NOT_MEASURED SITE_TILE_PROPERTY_UNSUPPORTED]
    }
    close $h
    set h [chan final_hotspot_nodes.tsv {seed_tile seed_node native_nodes native_tiles SLRs clock_regions native_code error}]
    foreach spec $::hotspot_nodes {
        lassign $spec tile leaf
        set code [catch {
            set nodes [get_nodes -quiet [format {%s/%s} $tile $leaf]]
            set ts [get_tiles -quiet -of_objects $nodes]
            set ss {};set rs {}
            foreach t $ts {
                lappend ss [expr {[dict exists $::tileSLR $t]?[dict get $::tileSLR $t]:"UNKNOWN"}]
                lappend rs [expr {[dict exists $::tileCR $t]?[dict get $::tileCR $t]:"UNKNOWN"}]
            }
        } err]
        if {$code} {row $h [list $tile $leaf NOT_MEASURED NOT_MEASURED UNKNOWN UNKNOWN $code $err]} else {
            row $h [list $tile $leaf [join [vals $nodes NAME] ,] [join $ts ,] [join [lsort -unique $ss] ,] [join [lsort -unique $rs] ,] 0 ""]
        }
    }
    close $h
    mark DEVICE_AND_FINAL_SEED_MAPPING_COMPLETE
}

proc capture_routes {nets} {
    set h [chan route_sample_receipts.tsv {canonical node_count node_export_cap complete_node_export native_code error}]
    set nout [chan sampled_route_nodes.tsv {canonical node tile SLR clock_region}]
    foreach can $nets {
        set code [catch {get_nodes -quiet -of_objects [dict get $::segments $can]} nodes]
        if {$code} {row $h [list $can NOT_MEASURED 2048 0 $code $nodes];continue}
        set nodes [lsort -unique $nodes]
        row $h [list $can [llength $nodes] 2048 [expr {[llength $nodes]<=2048}] 0 ""]
        foreach node [lrange $nodes 0 2047] {
            set ts [get_tiles -quiet -of_objects $node]
            foreach tile $ts {
                row $nout [list $can [get_property NAME $node] $tile [expr {[dict exists $::tileSLR $tile]?[dict get $::tileSLR $tile]:"UNKNOWN"}] [expr {[dict exists $::tileCR $tile]?[dict get $::tileCR $tile]:"UNKNOWN"}]]
            }
        }
    }
    close $h;close $nout
    mark BOUNDED_ACTUAL_ROUTE_SAMPLE_COMPLETE
}
