# Independent PREPARED lean candidate; never hot-edits AT001.
# E006 read-only current-physopt attribution. No physical/write-checkpoint commands.
set out $::env(E006_OUT)
file mkdir $out
set_param general.maxThreads 8
source $::env(E006_TARGETS)
set failures [list]
set receipt [open [file join $out query_receipts.tsv] {WRONLY CREAT EXCL}]
puts $receipt "query\tnative_tcl_code\tstarted_epoch\tended_epoch\tresult"
set stages [open [file join $out stage_receipts.tsv] {WRONLY CREAT EXCL}]
puts $stages "stage\tnative_tcl_code\tstarted_epoch\tended_epoch\tfailed_queries"
proc query {name body} {
    global receipt failures out
    set started [clock seconds]
    set code [catch {uplevel 1 $body} result options]
    if {$code} {
        lappend failures $name
        set h [open [file join $out error_${name}.txt] {WRONLY CREAT EXCL}]
        puts $h [list result $result options $options];close $h
    }
    if {[string length $result] > 1000 && !$code} {set result "SUCCESS_RESULT_LENGTH=[string length $result]; actual artifacts retained"}
    puts $receipt "$name\t$code\t$started\t[clock seconds]\t[list $result]";flush $receipt
    puts "E006_QUERY_COMPLETED $name native_tcl_code=$code"
    return $code
}
proc stage_done {name start before} {
    global failures stages out
    set failed [lrange $failures $before end]
    set code [expr {[llength $failed] ? 1 : 0}]
    set h [open [file join $out stage_${name}_closed.txt] {WRONLY CREAT EXCL}]
    puts $h "stage=$name\nnative_tcl_code=$code\nstarted_epoch=$start\nended_epoch=[clock seconds]\nfailed_queries=$failed\nphysical_commands_executed=false\ncheckpoint_write_executed=false";close $h
    puts $stages "$name\t$code\t$start\t[clock seconds]\t[list $failed]";flush $stages
    puts "E006_STAGE_COMPLETED $name native_tcl_code=$code"
}
proc exact_cell {path} {
    set cells [get_cells -quiet -hier -filter [format {NAME == "%s"} $path]]
    if {[llength $cells] != 1 || [get_property NAME $cells] ne $path} {error "Exact hierarchy missing/nonunique: $path"}
    return $cells
}
proc owner_of {cell} {
    global owner_roots
    foreach spec $owner_roots {
        lassign $spec tag roots
        foreach root $roots {
            if {$cell eq $root || [string first ${root}/ $cell] == 0} {return $tag}
        }
    }
    return interconnect_other
}
proc detail_of {cell owner} {
    global owner_roots
    foreach spec $owner_roots {
        lassign $spec tag roots
        if {$tag ne $owner} {continue}
        foreach root $roots {
            if {[string first ${root}/ $cell] == 0} {
                set relative [string range $cell [expr {[string length $root]+1}] end]
                set parts [split $relative /]
                return ${root}/[join [lrange $parts 0 [expr {min(2,[llength $parts]-2)}]] /]
            }
        }
    }
    return [lindex [split $cell /] 0]
}
proc slr_for {loc} {
    global siteSLR
    if {$loc eq ""} {return UNPLACED}
    if {[dict exists $siteSLR $loc]} {return [dict get $siteSLR $loc]}
    return UNKNOWN
}
proc site_type_for {loc} {
    global siteType
    if {[dict exists $siteType $loc]} {return [dict get $siteType $loc]}
    set site [get_sites -quiet $loc]
    if {[llength $site] == 1} {return [get_property SITE_TYPE $site]}
    return UNAVAILABLE_SITE_TYPE
}
set start [clock seconds];set before [llength $failures]
if {[query open_checkpoint {open_checkpoint $::env(E006_DCP)}]} {close $receipt;close $stages;exit 1}
if {[query identity {
    set h [open [file join $out identity.tsv] {WRONLY CREAT EXCL}]
    puts $h "tool\t[version -short]\ncheckpoint\t$::env(E006_DCP)\nPART\t[get_property PART [current_design]]\nNAME\t[get_property NAME [current_design]]\nblackboxes\t[llength [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]]";close $h
}]} {close $receipt;close $stages;exit 1}
if {[query topology {
    set siteSLR [dict create];set siteType [dict create]
    foreach slr [get_slrs] {
        set sites [get_sites -of_objects $slr]
        foreach site $sites type [get_property SITE_TYPE $sites] {dict set siteSLR $site $slr;dict set siteType $site $type}
    }
    if {![dict size $siteSLR]} {error "Actual device site/SLR map empty"}
}]} {close $receipt;close $stages;exit 1}
set cellData [dict create]
proc ensure_cell_data {objects} {
    global cellData
    set missing [list]
    foreach object $objects {if {![dict exists $cellData $object]} {lappend missing $object}}
    if {![llength $missing]} {return}
    set names [get_property NAME $missing]
    set refs [get_property REF_NAME $missing]
    set locs [get_property LOC $missing]
    set bels [get_property BEL $missing]
    set primitive [get_property IS_PRIMITIVE $missing]
    set count [llength $missing]
    foreach values [list $names $refs $locs $bels $primitive] {if {[llength $values] != $count} {error "Selected cell property alignment differs"}}
    foreach cell $names ref $refs loc $locs bel $bels leaf $primitive {
        if {!$leaf} {error "Nonprimitive selected from leaf endpoints/sites: $cell"}
        set owner [owner_of $cell]
        dict set cellData $cell [list $owner [detail_of $cell $owner] $ref $loc $bel [slr_for $loc]]
    }
}
proc pin_cell_data {pin} {
    global cellData
    set cell [string range $pin 0 [expr {[string last / $pin]-1}]]
    if {[dict exists $cellData $cell]} {return [linsert [dict get $cellData $cell] 0 $cell]}
    set cells [get_cells -quiet -of_objects $pin]
    if {[llength $cells] == 1} {
        ensure_cell_data $cells
        set cell [get_property NAME $cells]
        if {[dict exists $cellData $cell]} {return [linsert [dict get $cellData $cell] 0 $cell]}
    }
    return [list UNRESOLVED_PARENT_FROM_PIN:$cell UNKNOWN UNKNOWN UNKNOWN UNKNOWN UNKNOWN UNKNOWN]
}
proc pin_class {terminal} {
    if {$terminal in {CE GE WE WEA WEB WREN}} {return ENABLE_WRITE_CONTROL}
    if {$terminal in {R S CLR PRE RST RESET RSTRAMARSTRAM RSTRAMB RSTREGARSTREG RSTREGB}} {return RESET_SET_CONTROL}
    if {$terminal in {C CLK CLKA CLKB CLKARDCLK CLKBWRCLK ACLK BCLK}} {return CLOCK}
    if {$terminal in {D Q} || [regexp {^(DI|DO|DIN|DOUT|ADDR|A|B|P)[0-9]+$} $terminal]} {return DATA_ADDRESS_PIN}
    return OTHER_UNCLASSIFIED_PIN
}
proc net_record {net summary endpoints edges track_edges} {
    global hotspotUnion cellData
    set segments [lsort -unique [get_nets -segments $net]]
    set canonical [lindex $segments 0]
    set dp [lsort -unique [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]]
    set lp [lsort -unique [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == IN}]]
    set endpoints_for_cache [concat $dp $lp]
    if {[llength $endpoints_for_cache]} {ensure_cell_data [get_cells -quiet -of_objects $endpoints_for_cache]}
    set resolution [expr {[llength $dp] == 1 ? {SINGLE_PRIMITIVE_DRIVER} : ([llength $dp] == 0 ? {NO_PRIMITIVE_DRIVER} : {MULTIPLE_PRIMITIVE_DRIVERS})}]
    set sourceOwner UNKNOWN;set sourceSLR UNKNOWN;set sourceCells [list];set sourcePositions [list]
    foreach pin $dp {
        lassign [pin_cell_data $pin] cell owner detail ref loc bel slr
        lappend sourceCells $cell;lappend sourcePositions [list $pin $owner $detail $ref $loc $bel $slr]
        if {[llength $dp] == 1} {set sourceOwner $owner;set sourceSLR $slr}
        if {$endpoints ne ""} {puts $endpoints "$canonical\tDRIVER\t$pin\t$cell\t$owner\t$detail\t$ref\t$loc\t$bel\t$slr\t[get_property REF_PIN_NAME $pin]"}
    }
    set localEdges [dict create];set loadCells [dict create];set loadSLRs [dict create];set categories [dict create];set cross 0;set unknown 0;set inHotspot 0
    set terms [list]
    if {[llength $lp]} {set terms [get_property REF_PIN_NAME $lp]}
    if {[llength $terms] != [llength $lp]} {error "Leaf pin terminal alignment differs: $canonical"}
    foreach pin $lp terminal $terms {
        lassign [pin_cell_data $pin] cell owner detail ref loc bel slr
        dict set loadCells $cell 1;dict incr loadSLRs $slr;set category [pin_class $terminal];dict incr categories $category
        if {[dict exists $hotspotUnion $cell]} {incr inHotspot}
        if {$slr ni {SLR0 SLR1 SLR2}} {incr unknown} elseif {$sourceSLR in {SLR0 SLR1 SLR2} && $slr ne $sourceSLR} {incr cross}
        dict incr localEdges [list $sourceOwner $sourceSLR $owner $slr $category]
        if {$endpoints ne ""} {puts $endpoints "$canonical\tLOAD\t$pin\t$cell\t$owner\t$detail\t$ref\t$loc\t$bel\t$slr\t$terminal"}
    }
    if {$resolution ne "SINGLE_PRIMITIVE_DRIVER" || $sourceSLR ni {SLR0 SLR1 SLR2} || $unknown} {set cross UNAVAILABLE}
    puts $summary "$canonical\t[llength $segments]\t$resolution\t[llength $dp]\t[list $sourcePositions]\t[llength $lp]\t[dict size $loadCells]\t$loadSLRs\t$categories\t$cross\t$inHotspot"
    if {$track_edges} {
        upvar 1 $edges totals
        dict for {key pins} $localEdges {
            dict incr totals [linsert $key 0 leaf_pins] $pins
            dict incr totals [linsert $key 0 unique_canonical_nets] 1
        }
    }
    return $segments
}
if {[query prepare_regions_and_union_membership {
    set regionTileSets [dict create];set preparedUnionTiles [dict create]
    foreach region $regions {
        lassign $region name tiles_file
        set h [open $tiles_file r];set requested [split [string trim [read $h]] \n];close $h
        set tiles [get_tiles -quiet $requested]
        if {[lsort -unique [get_property NAME $tiles]] ne [lsort -unique $requested]} {error "Actual region tile names differ: $name"}
        foreach tile $requested {dict set regionTileSets $name $tile 1;dict set preparedUnionTiles $tile 1}
    }
    set preparedHotspotSites [get_sites -quiet -of_objects [get_tiles -quiet [dict keys $preparedUnionTiles]]]
    set preparedHotspotCells [get_cells -quiet -of_objects $preparedHotspotSites -filter {IS_PRIMITIVE == 1}]
    set hotspotUnion [dict create]
    foreach cell $preparedHotspotCells {dict set hotspotUnion $cell 1}
}]} {close $receipt;close $stages;exit 1}
set start [clock seconds];set before [llength $failures]
query failure_node_device_mapping {
    set h [open [file join $out failure_node_device_mapping.tsv] {WRONLY CREAT EXCL}]
    puts $h "sample_id\texact_tile\tnative_node_name_from_route_log\tactual_tile_count\tactual_GRID_POINT_X\tactual_GRID_POINT_Y\tactual_device_SLR\tSLR_query_status\tactual_NW_region_memberships"
    foreach spec $failure_nodes {
        lassign $spec id tile_name node_name
        set tile [get_tiles -quiet $tile_name]
        if {[llength $tile] != 1 || [get_property NAME $tile] ne $tile_name} {error "Failure sample device tile not exact: $tile_name"}
        set code [catch {get_slrs -of_objects $tile} slrs]
        if {$code} {set status UNAVAILABLE_NATIVE_SLR_QUERY} elseif {[llength $slrs] == 0} {
            set status UNAVAILABLE_EMPTY_NATIVE_SLR_QUERY
        } elseif {[llength $slrs] != 1 || [lsearch -exact [get_slrs] [lindex $slrs 0]] < 0} {
            set status AMBIGUOUS_NATIVE_SLR_QUERY
        } else {set status ACTUAL_NATIVE_DEVICE_QUERY}
        set membership [list]
        dict for {region tiles} $regionTileSets {if {[dict exists $tiles $tile_name]} {lappend membership $region}}
        puts $h "$id\t$tile_name\t$node_name\t1\t[get_property GRID_POINT_X $tile]\t[get_property GRID_POINT_Y $tile]\t[list $slrs]\t$status\t$membership"
    };close $h
}
query failure_samples {
    set h [open [file join $out failure_exact_net_resolution.tsv] {WRONLY CREAT EXCL}]
    puts $h "sample_id\texact_requested_net_name\texact_match_count\tactual_exact_matches\tstatus"
    set summary [open [file join $out failure_net_locations.tsv] {WRONLY CREAT EXCL}]
    puts $summary "canonical_net\tsegment_count\tdriver_resolution\tdriver_pin_count\tdriver_positions\tleaf_load_pins\tunique_load_cells\tload_SLR_pin_counts\tterminal_category_counts\tcross_SLR_leaf_load_pins\thotspot_union_leaf_load_pins"
    set endpoints [open [file join $out failure_net_endpoints.tsv] {WRONLY CREAT EXCL}]
    puts $endpoints "canonical_net\trole\tpin\tcell\towner\tdetail\tREF_NAME\tLOC\tBEL\tSLR\tREF_PIN_NAME"
    foreach item $failure_nets {
        lassign $item id name
        set matches [get_nets -quiet -hier -filter [format {NAME == "%s"} $name]]
        set count [llength $matches]
        if {$count == 1 && [get_property NAME $matches] ne $name} {error "Exact failure net name differs from requested literal: $name"}
        set status [expr {$count == 1 ? {EXACT_ONE} : ($count == 0 ? {NO_EXACT_NET_IN_THIS_PHYSOPT_GRAPH} : {MULTIPLE_EXACT_MATCHES})}]
        puts $h "$id\t$name\t$count\t[list $matches]\t$status"
        if {$count == 1} {net_record [lindex $matches 0] $summary $endpoints unused 0}
    };close $h;close $summary;close $endpoints
}
stage_done failure_samples $start $before

set start [clock seconds];set before [llength $failures]
set hotspotUnion [dict create];set regionCells [dict create];set regionTileSets [dict create]
query actual_tile_site_mapping {
    set h [open [file join $out actual_hotspot_site_tile_SLR.tsv] {WRONLY CREAT EXCL}]
    puts $h "site\tSITE_TYPE\tactual_device_SLR\texact_tile\tactual_GRID_POINT_X\tactual_GRID_POINT_Y"
    foreach site $preparedHotspotSites {
        set tile [get_tiles -quiet -of_objects $site]
        if {[llength $tile] != 1 || ![dict exists $preparedUnionTiles [get_property NAME $tile]]} {error "Site has no unique tile in the selected union: $site"}
        puts $h "$site\t[site_type_for $site]\t[slr_for $site]\t[get_property NAME $tile]\t[get_property GRID_POINT_X $tile]\t[get_property GRID_POINT_Y $tile]"
    };close $h
}
foreach region $regions {
    lassign $region name tiles_file
    query hotspot_$name {
        set h [open $tiles_file r];set requested [split [string trim [read $h]] \n];close $h
        set tiles [get_tiles -quiet $requested]
        if {[lsort -unique [get_property NAME $tiles]] ne [lsort -unique $requested]} {error "Actual region tile names differ: $name"}
        foreach tile $requested {dict set regionTileSets $name $tile 1}
        set sites [get_sites -quiet -of_objects $tiles];set cells [get_cells -quiet -of_objects $sites -filter {IS_PRIMITIVE == 1}]
        ensure_cell_data $cells
        dict set regionCells $name $cells
        foreach cell $cells {dict set hotspotUnion $cell 1}
        set h [open [file join $out hotspot_${name}_cells.tsv] {WRONLY CREAT EXCL}]
        puts $h "cell\texclusive_owner\tdetail_hierarchy\tREF_NAME\tLOC\tBEL\tSLR"
        foreach cell $cells {puts $h "$cell\t[join [dict get $cellData $cell] \t]"};close $h
    }
}
query hotspot_union {
    set unionCells [dict keys $hotspotUnion];dict set regionCells UNION $unionCells
    set h [open [file join $out hotspot_UNION_cells.tsv] {WRONLY CREAT EXCL}]
    puts $h "cell\texclusive_owner\tdetail_hierarchy\tREF_NAME\tLOC\tBEL\tSLR"
    foreach cell $unionCells {puts $h "$cell\t[join [dict get $cellData $cell] \t]"};close $h
    set h [open [file join $out hotspot_scope.tsv] {WRONLY CREAT EXCL}]
    puts $h "scope\tunique_primitive_cells"
    dict for {name cells} $regionCells {puts $h "$name\t[llength $cells]"};close $h
}
query hotspot_primitive_union_coverage {
    if {[lsort -unique [dict keys $hotspotUnion]] ne [lsort -unique $preparedHotspotCells]} {error "Per-region exact union differs from direct selected-site primitive union"}
    set h [open [file join $out hotspot_native_resource_limits.txt] {WRONLY CREAT EXCL}]
    puts $h "native_hotspot_resource_utilization=NOT_QUERIED
reason=avoid_large_primitive_list_report_utilization
primitive_site_BEL_occupation_is_not_native_LUT_resource_or_congestion
fixed_congestion=UNAVAILABLE";close $h
}
stage_done hotspot_ownership $start $before

set start [clock seconds];set before [llength $failures]
query hotspot_union_connections {
    set pins [get_pins -quiet -of_objects [dict keys $hotspotUnion]]
    set attached [lsort -unique [get_nets -quiet -of_objects $pins]]
    set summary [open [file join $out hotspot_union_canonical_net_locations.tsv] {WRONLY CREAT EXCL}]
    puts $summary "canonical_net\tsegment_count\tdriver_resolution\tdriver_pin_count\tdriver_positions\tleaf_load_pins\tunique_load_cells\tload_SLR_pin_counts\tterminal_category_counts\tcross_SLR_leaf_load_pins\thotspot_union_leaf_load_pins"
    set endpoints [open [file join $out hotspot_union_canonical_net_endpoints.tsv] {WRONLY CREAT EXCL}]
    puts $endpoints "canonical_net\trole\tpin\tcell\towner\tdetail\tREF_NAME\tLOC\tBEL\tSLR\tREF_PIN_NAME"
    set visited [dict create];set edgeTotals [dict create];set count 0
    foreach net $attached {
        if {[dict exists $visited $net]} {continue}
        set segments [net_record $net $summary $endpoints edgeTotals 1]
        foreach segment $segments {dict set visited $segment 1}
        incr count
        if {$count % 1000 == 0} {flush $summary;puts "E006_CONNECTION_PROGRESS canonical_nets=$count attached_segments=[llength $attached]"}
    };close $summary;close $endpoints
    set h [open [file join $out hotspot_union_module_SLR_edges.tsv] {WRONLY CREAT EXCL}]
    puts $h "metric\tsource_owner\tsource_SLR\tload_owner\tload_SLR\tterminal_category\tcount"
    dict for {key value} $edgeTotals {puts $h "[join $key \t]\t$value"};close $h
    set h [open [file join $out connection_coverage.tsv] {WRONLY CREAT EXCL}]
    puts $h "selected_hotspot_union_primitive_cells\t[dict size $hotspotUnion]\nattached_hierarchical_segments\t[llength $attached]\nunique_canonical_complete_nets\t$count\nresolved_segment_closure_entries\t[dict size $visited]\nselection\tALL nets attached to any primitive in10region deduplicated UNION; full leaf endpoints of each selected complete net, not all design nets\nterminal_categories\tPrimitive pin semantics only; OTHER_UNCLASSIFIED_PIN is not assumed data\nunits\tnets and leaf pins; not SLL or routed resource/traffic\nfixed_congestion\tUNAVAILABLE";close $h
}
stage_done hotspot_connections $start $before
set start [clock seconds];set before [llength $failures]
set hierarchy_scope [open [file join $out lean_exact_hierarchy_scope.tsv] {WRONLY CREAT EXCL}]
puts $hierarchy_scope "owner_context\texact_hierarchy\treport_name\tscope"
foreach spec $owner_roots {
    lassign $spec owner roots
    if {$owner ni {core_other ddr0 ddr1 pcie debug}} {continue}
    set index 0
    foreach root $roots {
        incr index
        set tag ${owner}_${index}
        query native_exact_hierarchy_$tag {
            set cells [exact_cell $root]
            if {[llength $cells] != 1 || [get_property IS_PRIMITIVE $cells]} {error "Expected exactly one hierarchy object: $root"}
            puts $hierarchy_scope "$owner\t$root\tutilization_total_${tag}_SLR.rpt\tinclusive_exact_hierarchy_not_exclusive_primitive_remainder";flush $hierarchy_scope
            report_utilization -cells $cells -slr -file [file join $out utilization_total_${tag}_SLR.rpt]
        }
    }
}
close $hierarchy_scope
stage_done exact_hierarchy_resources $start $before
close $receipt;close $stages
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\nphysical_commands_executed=false\ncheckpoint_write_executed=false\nsource_graph=E005_closed_physopt_not_failed_route\nfixed_congestion=UNAVAILABLE\nformal_signoff=false";close $h
close_design
if {[llength $failures]} {exit 1}
puts "E006_LEAN_ATTRIBUTION_READONLY_COMPLETED"
exit 0
