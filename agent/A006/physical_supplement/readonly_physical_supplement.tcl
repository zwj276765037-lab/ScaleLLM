# Draft, outside frozen production inputs. Execute only on an identified closed DCP.
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
if {[info exists placed_driver_sites]} {
    query placed_driver_device_mapping {
        if {[get_property PART [current_design]] ne $reference_part} {error "Device mapping part differs from placed reference"}
        set h [open [file join $out placed_reference_site_SLR_mapping.tsv] {WRONLY CREAT EXCL}]
        puts $h "placed_reference_LOC\tactual_site_NAME\tactual_site_TYPE\tdevice_SLR\tphase_context\tscope"
        foreach loc $placed_driver_sites {
            set sites [get_sites -quiet $loc]
            if {[llength $sites] != 1 || [get_property NAME $sites] ne $loc || ![dict exists $siteSLR $loc]} {error "Unresolved placed device site: $loc"}
            puts $h "$loc\t[get_property NAME $sites]\t[get_property SITE_TYPE $sites]\t[dict get $siteSLR $loc]\t$::env(E005_SUPPLEMENT_PHASE)\tdevice_mapping_of_original_placed_LOC_not_replaced_by_current_driver_LOC"
        };close $h
    }
}
proc canonical_net {net} {return [lindex [lsort -unique [get_nets -segments $net]] 0]}
query select_targets {
    set selected [dict create];set boundaryRows [list]
    set h [open [file join $out boundary_drivers.tsv] {WRONLY CREAT EXCL}]
    puts $h "scope\tcell\tREF_NAME\tINIT\tDONT_TOUCH\tLOC\tBEL\tSLR\toutput_pins\tnets"
    foreach target $targets {
        lassign $target tag hierarchy pattern ref count width
        set cells [get_cells -hier -quiet -filter [format {NAME =~ "%s" && REF_NAME == "%s"} $pattern $ref]]
        if {[llength $cells] != $count} {error "$tag actual boundary count [llength $cells], expected $count"}
        foreach cell $cells {
            set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
            set nets [get_nets -quiet -of_objects $outputs]
            puts $h "$tag\t$cell\t[get_property REF_NAME $cell]\t[get_property INIT $cell]\t[get_property DONT_TOUCH $cell]\t[get_property LOC $cell]\t[get_property BEL $cell]\t[site_slr [get_property LOC $cell]]\t$outputs\t$nets"
            foreach net $nets {dict lappend selected [canonical_net $net] boundary:$tag:$cell}
            foreach input [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}] {
                foreach net [get_nets -quiet -of_objects $input] {dict lappend selected [canonical_net $net] upstream}
            }
        }
    };close $h
}
query target_net_loads {
    set h [open [file join $out target_net_loads.tsv] {WRONLY CREAT EXCL}]
    puts $h "net\troles\tdriver_pins\tdriver_cells\tdriver_REF_NAMEs\tdriver_LOCs\tdriver_SLRs\tsource_resolution\tleaf_load_pin_count\tunique_load_cell_count\tload_REF_pin_counts\tload_REF_unique_cell_counts\tload_terminal_counts\tload_SLR_pin_counts\tsource_relative_cross_SLR_pin_count"
    set positions [open [file join $out target_net_position_envelopes.tsv] {WRONLY CREAT EXCL}]
    puts $positions "net\tSLR\tleaf_load_pins\tSLICE_pins\tnonSLICE_or_unplaced_pins\tSLICE_Xmin\tSLICE_Ymin\tSLICE_Xmax\tSLICE_Ymax"
    dict for {net roles} $selected {
        set segments [get_nets -segments $net]
        set pins [lsort -unique [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == IN}]]
        set dp [lsort -unique [get_pins -quiet -leaf -of_objects $segments -filter {DIRECTION == OUT}]]
        set dc [lsort -unique [get_cells -quiet -of_objects $dp]]
        set dloc [get_property LOC $dc];set dslr [list]
        foreach loc $dloc {lappend dslr [site_slr $loc]}
        set resolution [expr {[llength $dp] == 1 && [llength $dc] == 1 && [llength $dslr] == 1 && [string match SLR* [lindex $dslr 0]] ? {SINGLE_PLACED_DRIVER} : {UNAVAILABLE_UNKNOWN_UNPLACED_OR_MULTIPLE_DRIVER}}]
        set refs [dict create];set uniqueRefs [dict create];set terminals [dict create];set slrs [dict create];set uniqueCells [dict create];set xy [dict create];set sliceCounts [dict create]
        foreach pin $pins {
            set cell [get_cells -quiet -of_objects $pin]
            set ref [get_property REF_NAME $cell];set loc [get_property LOC $cell];set slr [site_slr $loc]
            dict incr refs $ref;dict incr terminals [get_property REF_PIN_NAME $pin];dict incr slrs $slr
            if {![dict exists $uniqueCells $cell]} {dict set uniqueCells $cell 1;dict incr uniqueRefs $ref}
            if {[regexp {^SLICE_X([0-9]+)Y([0-9]+)$} $loc -> x y]} {
                dict incr sliceCounts $slr;dict lappend xy [list $slr x] $x;dict lappend xy [list $slr y] $y
            }
        }
        set cross UNAVAILABLE
        if {$resolution eq "SINGLE_PLACED_DRIVER" && ![dict exists $slrs UNKNOWN] && ![dict exists $slrs UNPLACED]} {
            set same [expr {[dict exists $slrs [lindex $dslr 0]] ? [dict get $slrs [lindex $dslr 0]] : 0}]
            set cross [expr {[llength $pins]-$same}]
        }
        puts $h "$net\t[lsort -unique $roles]\t$dp\t$dc\t[get_property REF_NAME $dc]\t$dloc\t$dslr\t$resolution\t[llength $pins]\t[dict size $uniqueCells]\t$refs\t$uniqueRefs\t$terminals\t$slrs\t$cross"
        dict for {slr n} $slrs {
            set sc [expr {[dict exists $sliceCounts $slr] ? [dict get $sliceCounts $slr] : 0}]
            set bounds [list NA NA NA NA]
            if {$sc} {set xs [lsort -integer [dict get $xy [list $slr x]]];set ys [lsort -integer [dict get $xy [list $slr y]]];set bounds [list [lindex $xs 0] [lindex $ys 0] [lindex $xs end] [lindex $ys end]]}
            puts $positions "$net\t$slr\t$n\t$sc\t[expr {$n-$sc}]\t[join $bounds \t]"
        }
    };close $h;close $positions
}
query hierarchical_utilization {report_utilization -hierarchical -hierarchical_depth 7 -file [file join $out utilization_hierarchy_depth7.rpt]}
query fixed_congestion_api_help {help report_design_analysis}
foreach target $targets {
    lassign $target tag hierarchy pattern ref count width
    query utilization_$tag {
        set roots [get_cells -quiet $hierarchy]
        if {[llength $roots] != 1 || [get_property NAME $roots] ne $hierarchy} {error "Target hierarchy is missing/nonunique: $hierarchy"}
        report_utilization -cells $roots -hierarchical -hierarchical_depth 3 -file [file join $out utilization_hierarchy_${tag}.rpt]
    }
}
query fixed_native_windows {
    set h [open [file join $out fixed_window_occupancy.tsv] {WRONLY CREAT EXCL}]
    puts $h "reference_row\tdirection\ttype\told_level\tnative_endpoint_1\tnative_endpoint_2\tactual_GRID_POINT_Xmin\tactual_GRID_POINT_Ymin\tactual_GRID_POINT_Xmax\tactual_GRID_POINT_Ymax\ttile_count\tsite_count\tprimitive_count\tsite_TYPE_capacity\toccupied_site_TYPE_counts\tprimitive_REF_counts\tSLR_site_counts\tcurrent_fixed_congestion_metric"
    set connections [open [file join $out fixed_window_attached_connections.tsv] {WRONLY CREAT EXCL}]
    puts $connections "reference_row\tprimitive_input_leaf_pins\tprimitive_output_leaf_pins\tattached_hierarchical_net_segments\tscope"
    set index 0
    foreach window $windows {
        query fixed_native_window_$index {
        lassign $window direction type level first last
        set endpoints [list [get_tiles -quiet $first] [get_tiles -quiet $last]]
        if {[llength [lindex $endpoints 0]] != 1 || [llength [lindex $endpoints 1]] != 1} {error "Unresolved native tile endpoints $window"}
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
        puts $connections "$index\t[llength $inputs]\t[llength $outputs]\t[llength $attached]\tattached_segments_only_not_boundary_crossings_or_congestion"
        puts $h "$index\t$direction\t$type\t$level\t$first\t$last\t[lindex $xs 0]\t[lindex $ys 0]\t[lindex $xs 1]\t[lindex $ys 1]\t[llength $tiles]\t[llength $sites]\t[llength $cells]\t$cap\t$used\t$refs\t$slrs\tUNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API"
        set names [open [file join $out fixed_window_${index}_actual_tiles.txt] {WRONLY CREAT EXCL}]
        puts $names [join [lsort [get_property NAME $tiles]] \n];close $names
        }
        incr index
    };close $h;close $connections
}
close $receipt
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\ncheckpoint_mutated=false\nphysical_commands_executed=false\nfixed_window_metrics=resource_site_occupancy_only_not_congestion_level\nformal_signoff=false";close $h
close_design
set ::e005_supplement_design_closed 1
if {[llength $failures]} {
    if {[info exists ::env(E005_SUPPLEMENT_NO_EXIT)]} {error "Read-only phase failed queries: $failures"}
    exit 1
}
puts "E005_READONLY_PHYSICAL_SUPPLEMENT_COMPLETED"
if {![info exists ::env(E005_SUPPLEMENT_NO_EXIT)]} {exit 0}
