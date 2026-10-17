# Bounded new-peak mapping only, outside frozen production inputs; no physical commands.
set out $::env(E005_SUPPLEMENT_OUT)
file mkdir $out
set_param general.maxThreads 8
set failures [list]
set receipt [open [file join $out query_receipts.tsv] {WRONLY CREAT EXCL}]
puts $receipt "query\tnative_tcl_code\tstarted_epoch\tended_epoch\tresult"
proc query {name body} {
    global receipt failures out
    set start [clock seconds]
    set code [catch {uplevel 1 $body} result options]
    puts $receipt "$name\t$code\t$start\t[clock seconds]\t[list $result]";flush $receipt
    if {$code} {
        lappend failures $name
        set h [open [file join $out error_${name}.txt] {WRONLY CREAT EXCL}]
        puts $h [list result $result options $options];close $h
    }
    puts "E005_READONLY_QUERY $name native_tcl_code=$code"
    return $code
}
source $::env(E005_SUPPLEMENT_TARGETS)
if {[query open_checkpoint {open_checkpoint $::env(E005_SUPPLEMENT_DCP)}]} {
    close $receipt
    if {[info exists ::env(E005_SUPPLEMENT_NO_EXIT)]} {error "Read-only checkpoint open failed"}
    exit 1
}
query identity {
    set h [open [file join $out identity.tsv] {WRONLY CREAT EXCL}]
    puts $h "tool\t[version -short]"
    puts $h "checkpoint\t$::env(E005_SUPPLEMENT_DCP)"
    puts $h "phase\t$::env(E005_SUPPLEMENT_PHASE)"
    foreach key {PART NAME} {puts $h "$key\t[get_property $key [current_design]]"}
    puts $h "blackboxes\t[llength [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]]";close $h
}
query topology {
    set siteSLR [dict create]
    foreach slr [get_slrs] {
        foreach site [get_property NAME [get_sites -of_objects $slr]] {dict set siteSLR $site [get_property NAME $slr]}
    }
    if {![dict size $siteSLR]} {error "No actual SLR/site mapping"}
}
proc site_slr {loc} {
    global siteSLR
    if {$loc eq ""} {return UNPLACED}
    if {[dict exists $siteSLR $loc]} {return [dict get $siteSLR $loc]}
    return UNKNOWN
}
set phase $::env(E005_SUPPLEMENT_PHASE)
query target_scope {
    if {$phase ni {place physopt} || ![info exists new_worst_windows($phase)] || ![info exists source_rows($phase)] || [llength $new_worst_windows($phase)] != 10 || [llength $source_rows($phase)] != 48} {error "Wrong bounded new-peak phase targets"}
    set source_rows_out [open [file join $out source_congestion_rows.tsv] {WRONLY CREAT EXCL}]
    puts $source_rows_out "native_line\tdirection\ttype\treported_level\tnative_endpoint_1\tnative_endpoint_2\tselected_peak\tregion_id"
    set peak_count 0
    foreach row $source_rows($phase) {if {[llength $row] != 8} {error "Bad new report row"};if {[lindex $row 6]} {incr peak_count};puts $source_rows_out [join $row \t]}
    close $source_rows_out
    if {$peak_count != 12} {error "Expected12 selected peak rows"}
    set h [open [file join $out source_report_identity.tsv] {WRONLY CREAT EXCL}]
    puts $h "source_report_path\tbytes\tsha256"
    puts $h [join $source_report($phase) \t];close $h
}
query new_peak_native_regions {
    set h [open [file join $out new_peak_region_occupancy.tsv] {WRONLY CREAT EXCL}]
    puts $h "region_id\tnative_endpoint_1\tnative_endpoint_2\tactual_GRID_POINT_Xmin\tactual_GRID_POINT_Ymin\tactual_GRID_POINT_Xmax\tactual_GRID_POINT_Ymax\ttile_count\tsite_count\tprimitive_count\tsite_TYPE_capacity\toccupied_site_TYPE_counts\tprimitive_REF_counts\tSLR_site_counts\tcurrent_fixed_congestion_metric"
    set connections [open [file join $out new_peak_region_attached_connections.tsv] {WRONLY CREAT EXCL}]
    puts $connections "region_id\tprimitive_input_leaf_pins\tprimitive_output_leaf_pins\tattached_hierarchical_net_segments\tscope"
    foreach region $new_worst_windows($phase) {
        lassign $region region_id first last
        query region_$region_id {
        set endpoints [list [get_tiles -quiet $first] [get_tiles -quiet $last]]
        if {[llength [lindex $endpoints 0]] != 1 || [llength [lindex $endpoints 1]] != 1} {error "Unresolved native tile endpoints $region"}
        set xs [lsort -integer [list [get_property GRID_POINT_X [lindex $endpoints 0]] [get_property GRID_POINT_X [lindex $endpoints 1]]]]
        set ys [lsort -integer [list [get_property GRID_POINT_Y [lindex $endpoints 0]] [get_property GRID_POINT_Y [lindex $endpoints 1]]]]
        set filter [format {GRID_POINT_X >= %d && GRID_POINT_X <= %d && GRID_POINT_Y >= %d && GRID_POINT_Y <= %d} [lindex $xs 0] [lindex $xs 1] [lindex $ys 0] [lindex $ys 1]]
        set tiles [get_tiles -quiet -filter $filter];set sites [get_sites -quiet -of_objects $tiles]
        set cells [get_cells -quiet -of_objects $sites -filter {IS_PRIMITIVE == 1}]
        set cap [dict create];set used [dict create];set refs [dict create];set slrs [dict create];set occupied [dict create]
        foreach site $sites {dict incr cap [get_property SITE_TYPE $site];dict incr slrs [site_slr [get_property NAME $site]]}
        foreach cell $cells {dict incr refs [get_property REF_NAME $cell];dict set occupied [get_property LOC $cell] 1}
        dict for {loc unused} $occupied {dict incr used [get_property SITE_TYPE [get_sites -quiet $loc]]}
        set inputs [get_pins -quiet -of_objects $cells -filter {DIRECTION == IN}]
        set outputs [get_pins -quiet -of_objects $cells -filter {DIRECTION == OUT}]
        set attached [lsort -unique [get_nets -quiet -of_objects [concat $inputs $outputs]]]
        puts $connections "$region_id\t[llength $inputs]\t[llength $outputs]\t[llength $attached]\tattached_segments_only_not_boundary_crossings_or_congestion"
        puts $h "$region_id\t$first\t$last\t[lindex $xs 0]\t[lindex $ys 0]\t[lindex $xs 1]\t[lindex $ys 1]\t[llength $tiles]\t[llength $sites]\t[llength $cells]\t$cap\t$used\t$refs\t$slrs\tUNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API"
        set names [open [file join $out new_peak_${region_id}_actual_tiles.txt] {WRONLY CREAT EXCL}]
        puts $names [join [lsort [get_property NAME $tiles]] \n];close $names

        }
    };close $h;close $connections
}
close $receipt
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\ncheckpoint_mutated=false\nphysical_commands_executed=false\nnew_peak_scope=12_report_rows_to10unique_regions_per_own_phase\nfixed_window_metrics=resource_site_occupancy_only_not_congestion_level\nformal_signoff=false";close $h
close_design
set ::e005_supplement_design_closed 1
if {[llength $failures]} {
    if {[info exists ::env(E005_SUPPLEMENT_NO_EXIT)]} {error "Read-only phase failed queries: $failures"}
    exit 1
}
puts "E005_READONLY_NEW_PEAK_SUPPLEMENT_COMPLETED"
if {![info exists ::env(E005_SUPPLEMENT_NO_EXIT)]} {exit 0}
