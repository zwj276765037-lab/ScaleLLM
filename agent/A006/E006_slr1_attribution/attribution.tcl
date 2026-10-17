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
query identity {
    set h [open [file join $out identity.tsv] {WRONLY CREAT EXCL}]
    puts $h "tool\t[version -short]\ncheckpoint\t$::env(E006_DCP)\nPART\t[get_property PART [current_design]]\nNAME\t[get_property NAME [current_design]]\nblackboxes\t[llength [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]]";close $h
}
query topology {
    set siteSLR [dict create];set siteType [dict create]
    foreach slr [get_slrs] {
        set sites [get_sites -of_objects $slr]
        foreach site $sites type [get_property SITE_TYPE $sites] {dict set siteSLR $site $slr;dict set siteType $site $type}
    }
    if {![dict size $siteSLR]} {error "Actual device site/SLR map empty"}
}
query complete_exclusive_ownership {
    set allCells [get_cells -quiet -hier -filter {IS_PRIMITIVE == 1}]
    set refs [get_property REF_NAME $allCells];set locs [get_property LOC $allCells];set bels [get_property BEL $allCells]
    if {[llength $refs] != [llength $allCells] || [llength $locs] != [llength $allCells] || [llength $bels] != [llength $allCells]} {error "Bulk primitive property alignment differs"}
    set cellData [dict create];set ownerCells [dict create];set ownerRefs [dict create];set siteOwners [dict create]
    set h [open [file join $out all_primitive_locations.tsv] {WRONLY CREAT EXCL}]
    puts $h "cell\tREF_NAME\tLOC\tBEL\tSLR\texclusive_owner\tdetail_hierarchy"
    foreach cell $allCells ref $refs loc $locs bel $bels {
        set owner [owner_of $cell];set slr [slr_for $loc];set detail [detail_of $cell $owner]
        dict set cellData $cell [list $owner $detail $ref $loc $bel $slr]
        dict lappend ownerCells $owner $cell;dict incr ownerRefs [list $owner $slr $ref]
        if {$loc ne ""} {dict set siteOwners $loc $owner 1}
        puts $h "$cell\t$ref\t$loc\t$bel\t$slr\t$owner\t$detail"
    };close $h
    set h [open [file join $out exclusive_owner_SLR_REF_counts.tsv] {WRONLY CREAT EXCL}]
    puts $h "exclusive_owner\tSLR\tprimitive_REF\tprimitive_count_not_native_resource_count"
    dict for {key count} $ownerRefs {puts $h "[join $key \t]\t$count"};close $h
    set h [open [file join $out site_owner_sets.tsv] {WRONLY CREAT EXCL}]
    puts $h "site\tSITE_TYPE\tSLR\texclusive_primitive_owners_sharing_site\towner_count_nonadditive_site"
    dict for {site owners} $siteOwners {puts $h "$site\t[site_type_for $site]\t[slr_for $site]\t[lsort [dict keys $owners]]\t[dict size $owners]"};close $h
    set h [open [file join $out ownership_coverage.tsv] {WRONLY CREAT EXCL}]
    puts $h "all_primitive_count\t[llength $allCells]\nclassified_unique_primitive_count\t[dict size $cellData]\nowner_count\t[dict size $ownerCells]\nsite_sets_nonadditive\t[dict size $siteOwners]";close $h
}
query native_global_SLR {report_utilization -slr -file [file join $out utilization_global_SLR.rpt]}
foreach spec $owner_roots {
    lassign $spec tag roots
    query native_owner_$tag {
        if {$tag eq "core_other"} {
            set cells [dict get $ownerCells $tag]
        } else {
            set cells [list];foreach root $roots {lappend cells {*}[exact_cell $root]}
        }
        report_utilization -cells $cells -slr -file [file join $out utilization_exclusive_${tag}_SLR.rpt]
    }
}
query native_remaining_global {
    set cells [dict get $ownerCells interconnect_other]
    report_utilization -cells $cells -slr -file [file join $out utilization_exclusive_interconnect_other_SLR.rpt]
}
set lookup [open [file join $out native_target_resolution.tsv] {WRONLY CREAT EXCL}]
puts $lookup "target_id\texact_hierarchy\trequired\texact_match_count\tactual_matches"
foreach target $native_targets {
    lassign $target tag path required
    query native_detail_$tag {
        set matches [get_cells -quiet -hier -filter [format {NAME == "%s"} $path]]
        puts $lookup "$tag\t$path\t$required\t[llength $matches]\t[list $matches]";flush $lookup
        if {[llength $matches] == 1 && [get_property NAME $matches] eq $path} {
            report_utilization -cells $matches -slr -file [file join $out utilization_total_${tag}_SLR.rpt]
        } elseif {$required} {error "Required detail root missing/nonunique: $path"}
    }
}
close $lookup
stage_done module_resources $start $before

set start [clock seconds];set before [llength $failures]
set hotspotUnion [dict create];set regionCells [dict create];set regionTileSets [dict create]
foreach region $regions {
    lassign $region name tiles_file
    query hotspot_$name {
        set h [open $tiles_file r];set requested [split [string trim [read $h]] \n];close $h
        set tiles [get_tiles -quiet $requested]
        if {[lsort -unique [get_property NAME $tiles]] ne [lsort -unique $requested]} {error "Actual region tile names differ: $name"}
        foreach tile $requested {dict set regionTileSets $name $tile 1}
        set sites [get_sites -quiet -of_objects $tiles];set cells [get_cells -quiet -of_objects $sites -filter {IS_PRIMITIVE == 1}]
        dict set regionCells $name $cells
        foreach cell $cells {dict set hotspotUnion $cell 1}
        set h [open [file join $out hotspot_${name}_cells.tsv] {WRONLY CREAT EXCL}]
        puts $h "cell\texclusive_owner\tdetail_hierarchy\tREF_NAME\tLOC\tBEL\tSLR"
        foreach cell $cells {puts $h "$cell\t[join [dict get $cellData $cell] \t]"};close $h
        report_utilization -cells $cells -slr -file [file join $out utilization_hotspot_${name}_SLR.rpt]
    }
}
query hotspot_union {
    set unionCells [dict keys $hotspotUnion];dict set regionCells UNION $unionCells
    set h [open [file join $out hotspot_UNION_cells.tsv] {WRONLY CREAT EXCL}]
    puts $h "cell\texclusive_owner\tdetail_hierarchy\tREF_NAME\tLOC\tBEL\tSLR"
    foreach cell $unionCells {puts $h "$cell\t[join [dict get $cellData $cell] \t]"};close $h
    report_utilization -cells $unionCells -slr -file [file join $out utilization_hotspot_UNION_SLR.rpt]
    set h [open [file join $out hotspot_scope.tsv] {WRONLY CREAT EXCL}]
    puts $h "scope\tunique_primitive_cells"
    dict for {name cells} $regionCells {puts $h "$name\t[llength $cells]"};close $h
}
stage_done hotspot_ownership $start $before

proc pin_cell_data {pin} {
    global cellData
    set cell [string range $pin 0 [expr {[string last / $pin]-1}]]
    if {[dict exists $cellData $cell]} {return [linsert [dict get $cellData $cell] 0 $cell]}
    set cells [get_cells -quiet -of_objects $pin]
    if {[llength $cells] == 1 && [dict exists $cellData [lindex $cells 0]]} {set cell [lindex $cells 0];return [linsert [dict get $cellData $cell] 0 $cell]}
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
set start [clock seconds];set before [llength $failures]
query failure_node_device_mapping {
    set h [open [file join $out failure_node_device_mapping.tsv] {WRONLY CREAT EXCL}]
    puts $h "sample_id\texact_tile\tnative_node_name_from_route_log\tactual_tile_count\tactual_GRID_POINT_X\tactual_GRID_POINT_Y\tactual_device_SLR\tSLR_query_status\tactual_NW_region_memberships"
    foreach spec $failure_nodes {
        lassign $spec id tile_name node_name
        set tile [get_tiles -quiet $tile_name]
        if {[llength $tile] != 1 || [get_property NAME $tile] ne $tile_name} {error "Failure sample device tile not exact: $tile_name"}
        set code [catch {get_slrs -of_objects $tile} slrs]
        set status [expr {$code ? {UNAVAILABLE_NATIVE_SLR_QUERY} : {ACTUAL_NATIVE_DEVICE_QUERY}}]
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
        set count [llength $matches];set status [expr {$count == 1 ? {EXACT_ONE} : ($count == 0 ? {NO_EXACT_NET_IN_THIS_PHYSOPT_GRAPH} : {MULTIPLE_EXACT_MATCHES})}]
        puts $h "$id\t$name\t$count\t[list $matches]\t$status"
        if {$count == 1} {net_record [lindex $matches 0] $summary $endpoints unused 0}
    };close $h;close $summary;close $endpoints
}
stage_done failure_samples $start $before

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
close $receipt;close $stages
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\nphysical_commands_executed=false\ncheckpoint_write_executed=false\nsource_graph=E005_closed_physopt_not_failed_route\nfixed_congestion=UNAVAILABLE\nformal_signoff=false";close $h
close_design
if {[llength $failures]} {exit 1}
puts "E006_ATTRIBUTION_READONLY_COMPLETED"
exit 0
