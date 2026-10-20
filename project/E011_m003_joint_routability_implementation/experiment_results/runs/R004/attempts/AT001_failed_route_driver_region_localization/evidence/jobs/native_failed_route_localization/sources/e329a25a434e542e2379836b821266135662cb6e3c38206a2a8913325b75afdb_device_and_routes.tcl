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
    set h [chan final_hotspot_nodes.tsv {seed_tile seed_node native_nodes native_tiles SLRs clock_regions native_code error native_node_count native_tile_count unknown_mapping_count region_mapping_complete}]
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
        if {$code} {row $h [list $tile $leaf NOT_MEASURED NOT_MEASURED UNKNOWN UNKNOWN $code $err NOT_MEASURED NOT_MEASURED NOT_MEASURED 0]} else {
            set missing [expr {![llength $nodes] || ![llength $ts]}]
            set unknown $missing
            foreach s $ss r $rs {if {$s eq "UNKNOWN" || $r eq "UNKNOWN"} {incr unknown}}
            row $h [list $tile $leaf [expr {[llength $nodes]?[join [vals $nodes NAME] ,]:"NOT_MEASURED"}] [expr {[llength $ts]?[join $ts ,]:"NOT_MEASURED"}] [expr {[llength $ss]?[join [lsort -unique $ss] ,]:"UNKNOWN"}] [expr {[llength $rs]?[join [lsort -unique $rs] ,]:"UNKNOWN"}] 0 "" [llength $nodes] [llength $ts] $unknown [expr {!$unknown}]]
        }
    }
    close $h
    mark DEVICE_AND_FINAL_SEED_MAPPING_COMPLETE
}

proc capture_routes {nets} {
    set h [chan route_sample_receipts.tsv {canonical node_count node_export_cap complete_node_export native_code error selected_node_count exported_node_count node_rows unknown_mapping_node_count region_mapping_complete}]
    set nout [chan sampled_route_nodes.tsv {canonical node tile SLR clock_region}]
    foreach can $nets {
        set code [catch {get_nodes -quiet -of_objects [dict get $::segments $can]} nodes]
        if {$code} {row $h [list $can NOT_MEASURED 2048 0 $code $nodes NOT_MEASURED 0 0 NOT_MEASURED 0];continue}
        set nodes [lsort -unique $nodes]
        set selected [llength [lrange $nodes 0 2047]]
        set exported 0;set nodeRows 0;set unknownNodes 0
        foreach node [lrange $nodes 0 2047] {
            set ts [get_tiles -quiet -of_objects $node]
            set unknown 0
            if {![llength $ts]} {
                row $nout [list $can [get_property NAME $node] NOT_MEASURED UNKNOWN UNKNOWN]
                incr nodeRows
                set unknown 1
            }
            foreach tile $ts {
                set slr [expr {[dict exists $::tileSLR $tile]?[dict get $::tileSLR $tile]:"UNKNOWN"}]
                set region [expr {[dict exists $::tileCR $tile]?[dict get $::tileCR $tile]:"UNKNOWN"}]
                row $nout [list $can [get_property NAME $node] $tile $slr $region]
                incr nodeRows
                if {$slr eq "UNKNOWN" || $region eq "UNKNOWN"} {set unknown 1}
            }
            incr exported
            if {$unknown} {incr unknownNodes}
        }
        row $h [list $can [llength $nodes] 2048 [expr {[llength $nodes]<=2048 && $exported==$selected}] 0 "" $selected $exported $nodeRows $unknownNodes [expr {$selected>0 && !$unknownNodes}]]
    }
    close $h;close $nout
    mark BOUNDED_ACTUAL_ROUTE_SAMPLE_COMPLETE
}
