# Independent PREPARED lean candidate; never hot-edits AT001.
# E006 read-only current-physopt attribution. No physical/write-checkpoint commands.
set out $::env(E006_OUT)
file mkdir $out
set_param general.maxThreads 8
source $::env(E006_TARGETS)
source [file join [file dirname [info script]] property_alignment.tcl]
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
    global cellData out
    set missing [list]
    foreach object $objects {if {![dict exists $cellData $object]} {lappend missing $object}}
    if {![llength $missing]} {return}
    set names [propertyalign::values $missing NAME 0 E006_cell_cache [file join $out property_alignment_fallback.tsv]]
    set refs [propertyalign::values $missing REF_NAME 0 E006_cell_cache [file join $out property_alignment_fallback.tsv]]
    set locs [propertyalign::values $missing LOC 1 E006_cell_cache [file join $out property_alignment_fallback.tsv]]
    set bels [propertyalign::values $missing BEL 1 E006_cell_cache [file join $out property_alignment_fallback.tsv]]
    set primitive [propertyalign::values $missing IS_PRIMITIVE 0 E006_cell_cache [file join $out property_alignment_fallback.tsv]]
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
    global hotspotUnion cellData segmentExport
    set segments [lsort -unique [get_nets -segments $net]]
    set canonical [lindex $segments 0]
    foreach segment $segments {puts $segmentExport "$canonical\t$segment"}
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
query actual_failed_batch_property_diagnostics {
    set objects [list]
    foreach name $failed_alignment_objects {
        set object [get_cells -quiet -hier -filter [format {NAME == "%s"} $name]]
        if {[llength $object] != 1 || [get_property NAME $object] ne $name} {error "Failed-batch diagnostic object missing/nonunique: $name"}
        lappend objects [lindex $object 0]
    }
    set h [open [file join $out failed_batch_actual_property_columns.tsv] {WRONLY CREAT EXCL}]
    puts $h "property\texpected_objects\tnative_vector_list_length\tobject\tscalar_value\tscalar_is_empty"
    foreach property {NAME REF_NAME LOC BEL IS_PRIMITIVE} {
        set vector [get_property -quiet $property $objects]
        foreach object $objects {
            set value [get_property -quiet $property $object]
            puts $h "$property\t[llength $objects]\t[llength $vector]\t[list $object]\t[list $value]\t[expr {$value eq {}}]"
        }
    }
    close $h
}
if {[query reused_hotspot_union_membership {
    set h [open $reused_union_file r];gets $h header
    if {$header ne "cell\texclusive_owner\tdetail_hierarchy\tREF_NAME\tLOC\tBEL\tSLR"} {error "Reused UNION export header changed"}
    set names [list]
    while {[gets $h line] >= 0} {lappend names [lindex [split $line \t] 0]}
    close $h
    if {[lsort -unique $names] ne [lsort -unique $preparedHotspotCells]} {error "Current selected-site UNION differs from closed AT001 exact cell names"}
    set h [open [file join $out reused_hotspot_union_actual_membership.txt] {WRONLY CREAT EXCL}]
    puts $h "current_selected_site_primitive_cells=[llength $preparedHotspotCells]\nreused_union_primitive_cells=[llength $names]\nexact_sorted_NAME_sets_equal=true"
    close $h
}]} {close $receipt;close $stages;exit 1}
source [file join [file dirname [info script]] candidate_inspector.tcl]
set ::m002_report_dir $out
set ::slr2::siteSLR $siteSLR
set memberStatus [dict create]
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set code [query candidate_${point}_membership {slr2::readonly_resolve $point $root}]
    dict set memberStatus $point $code
    query candidate_${point}_exact_native_resources {
        set object [exact_cell $root]
        if {[get_property IS_PRIMITIVE $object]} {error "Exact candidate root is primitive: $root"}
        report_utilization -cells $object -slr -file [file join $out utilization_candidate_${point}_SLR.rpt]
    }
    stage_done candidate_${point}_membership_resources $start $before
}
query candidate_disjointness {
    set prior [dict create];set priorP [dict create];set overlaps [list]
    foreach spec $exact_candidate_targets {
        lassign $spec point root
        if {[dict get $memberStatus $point]} {error "Candidate membership did not close: $point"}
        set sets [dict get $::slr2::candidateSets $point]
        foreach name [dict keys [dict get $sets RAW]] {
            if {[dict exists $prior $name]} {lappend overlaps [list RAW $name [dict get $prior $name] $point]}
            dict set prior $name $point
        }
        foreach name [dict keys [dict get $sets P]] {
            if {[dict exists $priorP $name]} {lappend overlaps [list P $name [dict get $priorP $name] $point]}
            dict set priorP $name $point
        }
    }
    m002_put [file join $out candidate_disjointness.tcllist] [list actual_overlaps $overlaps separate_scopes true combined_migration_candidate false]
    if {[llength $overlaps]} {error "Exact candidate RAW/P scopes overlap"}
}
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set cutCode [query candidate_${point}_complete_cut {
        if {[dict get $memberStatus $point]} {error "Full cut not executed: exact candidate membership failed"}
        set sets [dict get $::slr2::candidateSets $point]
        foreach setname {RAW S P} {set ::slr2::$setname [dict get $sets $setname]}
        slr2::cut $point
    }]
    stage_done candidate_${point}_complete_cut $start $before
    set start [clock seconds];set before [llength $failures]
    query candidate_${point}_bounded_boundary_timing {
        if {$cutCode} {error "Bounded timing not executed: full cut did not close"}
        slr2::scoped_timing $point
    }
    stage_done candidate_${point}_bounded_timing $start $before
}
set start [clock seconds];set before [llength $failures]
query hotspot_union_connections {
    set segmentExport [open [file join $out hotspot_union_canonical_segments.tsv] {WRONLY CREAT EXCL}]
    puts $segmentExport "canonical_net\tsegment"
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
    };close $summary;close $endpoints;close $segmentExport
    set h [open [file join $out hotspot_union_module_SLR_edges.tsv] {WRONLY CREAT EXCL}]
    puts $h "metric\tsource_owner\tsource_SLR\tload_owner\tload_SLR\tterminal_category\tcount"
    dict for {key value} $edgeTotals {puts $h "[join $key \t]\t$value"};close $h
    set h [open [file join $out connection_coverage.tsv] {WRONLY CREAT EXCL}]
    puts $h "selected_hotspot_union_primitive_cells\t[dict size $hotspotUnion]\nattached_hierarchical_segments\t[llength $attached]\nunique_canonical_complete_nets\t$count\nresolved_segment_closure_entries\t[dict size $visited]\nselection\tALL nets attached to any primitive in10region deduplicated UNION; full leaf endpoints of each selected complete net, not all design nets\nterminal_categories\tPrimitive pin semantics only; OTHER_UNCLASSIFIED_PIN is not assumed data\nunits\tnets and leaf pins; not SLL or routed resource/traffic\nfixed_congestion\tUNAVAILABLE";close $h
}
stage_done hotspot_connections $start $before
close $receipt;close $stages
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\nphysical_commands_executed=false\ncheckpoint_write_executed=false\nsource_graph=E005_closed_physopt_not_failed_route\nfixed_congestion=UNAVAILABLE\nformal_signoff=false\nreused_closed_stages=failure_samples,hotspot_ownership,exact_hierarchy_resources"
close $h
close_design
if {[llength $failures]} {exit 1}
puts "E006_EXACT_CANDIDATE_COMPARISON_READONLY_COMPLETED"
exit 0
