set out [file dirname [file normalize [info script]]]
source [file join $out query_targets.tcl]
set_param general.maxThreads 8
set receipt [open [file join $out query_receipts.tsv] w]
puts $receipt "label\tcode\tstarted_epoch\tended_epoch\tmessage"
proc query {label script} {
    global receipt out
    set start [clock seconds]
    set code [catch {uplevel 1 $script} message options]
    puts $receipt "$label\t$code\t$start\t[clock seconds]\t[string map [list \n { } \t { }] [expr {$code ? $message : {OK}}]]"
    flush $receipt
    if {$code} {
        set h [open [file join $out error_${label}.txt] w]
        puts $h $message
        if {[dict exists $options -errorinfo]} {puts $h [dict get $options -errorinfo]}
        close $h
    }
    puts "E004_QUERY $label code=$code epoch=[clock seconds]"
    flush stdout
    return $code
}
foreach cmd {place_design phys_opt_design opt_design route_design report_utilization report_control_sets report_high_fanout_nets report_slr_crossing report_qor_suggestions report_design_analysis get_slrs get_sites get_tiles} {
    query help_$cmd {redirect -file [file join $out help_${cmd}.txt] [list help $cmd]}
}
if {[query open_checkpoint {open_checkpoint $::env(E004_CHECKPOINT)}]} {close $receipt; exit 1}
query identity {
    set h [open [file join $out restored_identity.tsv] w]
    puts $h "tool\t[version -short]"
    foreach prop {PART TOP NAME} {if {![catch {get_property $prop [current_design]} v]} {puts $h "$prop\t$v"}}
    puts $h "threads\t[get_param general.maxThreads]"
    puts $h "blackboxes\t[llength [get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]]"
    close $h
}
query hierarchical_utilization {report_utilization -hierarchical -hierarchical_depth 4 -file [file join $out utilization_hierarchy_depth4.rpt]}
query high_fanout {report_high_fanout_nets -max_nets 50 -file [file join $out high_fanout_top50.rpt]}
query slr_crossing {report_slr_crossing -max_nets 64 -file [file join $out slr_crossing_top64.rpt]}
foreach {tag scope} $scopes {
    query util_$tag {
        set hc [get_cells -quiet $scope]
        if {[llength $hc] != 1} {error "Target scope not unique: $scope"}
        report_utilization -cells $hc -file [file join $out utilization_${tag}.rpt]
    }
    query utilSLR_$tag {report_utilization -cells [get_cells -quiet $scope] -slr -file [file join $out utilization_SLR_${tag}.rpt]}
}
set siteSLR [dict create]
set siteType [dict create]
query build_site_topology {
    foreach slr [get_slrs] {
        set sn [get_property NAME $slr]
        set sites [get_sites -of_objects $slr]
        foreach n [get_property NAME $sites] t [get_property SITE_TYPE $sites] {
            dict set siteSLR $n $sn
            dict set siteType $n $t
        }
    }
    if {[dict size $siteSLR] == 0} {error "SLR/site topology empty"}
    set h [open [file join $out topology_summary.tsv] w]
    puts $h "mapped_sites\t[dict size $siteSLR]"
    foreach slr [get_slrs] {puts $h "SLR\t[get_property NAME $slr]\t[get_property SLR_INDEX $slr]"}
    close $h
}
proc placement_slr {loc} {
    global siteSLR
    if {[dict exists $siteSLR $loc]} {return [dict get $siteSLR $loc]}
    return UNKNOWN
}
query packing_and_module_primitives {
    set cells [get_cells -hier -filter {IS_PRIMITIVE == 1}]
    set names [get_property NAME $cells]
    set refs [get_property REF_NAME $cells]
    set locs [get_property LOC $cells]
    set bels [get_property BEL $cells]
    set touches [get_property DONT_TOUCH $cells]
    set counts [dict create]; set usedsites [dict create]; set attr [dict create]
    set clb [dict create]; set lutslots [dict create]; set ffslots [dict create]
    set unmatched [dict create]
    foreach n $names ref $refs loc $locs bel $bels touch $touches {
        set slr [placement_slr $loc]
        set tags [list GLOBAL]
        foreach {tag scope} $scopes {if {[string first "$scope/" $n] == 0} {lappend tags $tag}}
        foreach tag $tags {
            dict incr counts [list $tag $slr $ref]
            dict incr attr [list $tag DONT_TOUCH $touch]
            if {$loc ne ""} {dict set usedsites [list $tag $slr $loc] 1}
        }
        if {[string match SLICE_* $loc]} {
            dict set clb $loc 1
            if {[regexp {^([A-H])[56]LUT$} $bel -> slot]} {dict set lutslots [list $loc $slot] 1}
            if {[regexp {^[A-H]FF2?$} $bel]} {dict set ffslots [list $loc $bel] 1}
            if {$bel eq ""} {dict incr unmatched $ref}
        }
    }
    set h [open [file join $out module_primitive_counts.tsv] w]
    puts $h "scope\tslr\tREF_NAME\tprimitive_count"
    dict for {key count} $counts {puts $h "[join $key \t]\t$count"};close $h
    set ns [dict create]
    dict for {key unused} $usedsites {
        lassign $key tag slr loc
        set type [expr {[dict exists $siteType $loc] ? [dict get $siteType $loc] : {UNKNOWN}}]
        dict incr ns [list $tag $slr $type]
    }
    set h [open [file join $out module_used_sites.tsv] w]
    puts $h "scope\tslr\tsite_type\tdistinct_occupied_sites"
    dict for {key count} $ns {puts $h "[join $key \t]\t$count"};close $h
    set h [open [file join $out module_attribute_counts.tsv] w]
    puts $h "scope\tattribute\tvalue\tprimitive_count"
    dict for {key count} $attr {puts $h "[join $key \t]\t$count"};close $h
    set nl [dict create];set nf [dict create]
    dict for {key unused} $lutslots {dict incr nl [lindex $key 0]}
    dict for {key unused} $ffslots {dict incr nf [lindex $key 0]}
    set hist [dict create]
    dict for {loc unused} $clb {
        set l [expr {[dict exists $nl $loc] ? [dict get $nl $loc] : 0}]
        set f [expr {[dict exists $nf $loc] ? [dict get $nf $loc] : 0}]
        dict incr hist [list [placement_slr $loc] $l $f]
    }
    set h [open [file join $out global_CLB_BEL_packing_hist.tsv] w]
    puts $h "slr\tphysical_LUT_slots_with_mapped_cells\tFF_BELs_with_mapped_cells\toccupied_CLB_sites"
    dict for {key count} $hist {puts $h "[join $key \t]\t$count"};close $h
    set h [open [file join $out packing_scope_notes.txt] w]
    puts $h "primitive_cells=[llength $cells]\noccupied_SLICE_sites=[dict size $clb]\nphysical_LUT_slots=[dict size $lutslots]\nFF_BELs=[dict size $ffslots]\nempty_BEL_SLICE_primitives=$unmatched\nLUTslot_mapping=literal_A-H_5LUT_or_6LUT_BEL_unified_per_physical_letter\nFF_mapping=literal_A-H_FF_or_FF2\nScope_occupancy_sets_overlap_do_not_add_hierarchy_rows"
    close $h
}
query hierarchy_properties {
    set h [open [file join $out hierarchy_properties.tsv] w]
    puts $h "scope\tproperty\tvalue"
    foreach {tag scope} $scopes {
        set c [get_cells -quiet $scope]
        foreach prop {REF_NAME ORIG_REF_NAME DONT_TOUCH KEEP_HIERARCHY ASYNC_REG LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLL_REG} {
            set code [catch {get_property $prop $c} value]
            puts $h "$tag\t$prop\t[expr {$code ? {UNAVAILABLE} : $value}]"
        }
    };close $h
}
query sample_tile_properties {
    set h [open [file join $out sample_tile_properties.tsv] w]
    puts $h "tile\tproperty\tvalue"
    foreach name $sample_tiles {
        set obj [get_tiles -quiet $name]
        foreach prop [list_property $obj] {puts $h "$name\t$prop\t[get_property $prop $obj]"}
        foreach command {get_slrs get_clock_regions get_sites} {
            set code [catch {$command -of_objects $obj} value]
            puts $h "$name\t$command\t[expr {$code ? {UNAVAILABLE} : $value}]"
        }
    };close $h
}
set nets [list]
query select_target_nets {
    foreach pattern $exact_net_patterns {foreach net [get_nets -hier -quiet -regexp $pattern] {lappend nets $net}}
    foreach pattern {*u_attention*visibility* *u_attention*capture_index* *u_projection_repack*input_fire*} {
        set candidates [get_nets -hier -quiet -filter [format {NAME =~ "%s"} $pattern]]
        foreach net [lrange $candidates 0 23] {lappend nets $net}
    }
    set nets [lsort -unique $nets]
    set h [open [file join $out selected_target_nets.txt] w];puts $h [join $nets \n];close $h
}
query target_net_fanout {
    set h [open [file join $out target_net_fanout.tsv] w]
    puts $h "net\tFLAT_PIN_COUNT\tinput_leaf_pins\tload_cells\tdriver_pins\tdriver_LOCs\tload_SLR_cell_counts\tDONT_TOUCH\tKEEP\tMARK_DEBUG"
    foreach net $nets {
        set seg [get_nets -segments $net]
        set pins [get_pins -leaf -of_objects $seg -filter {DIRECTION == IN}]
        set loads [get_cells -of_objects $pins]
        set drivers [get_pins -leaf -of_objects $seg -filter {DIRECTION == OUT}]
        set dloc [get_property LOC [get_cells -of_objects $drivers]]
        set slrs [dict create]
        foreach loc [get_property LOC $loads] {dict incr slrs [placement_slr $loc]}
        set attrs [list]
        foreach prop {FLAT_PIN_COUNT DONT_TOUCH KEEP MARK_DEBUG} {
            set code [catch {get_property $prop $net} v]
            lappend attrs [expr {$code ? {UNAVAILABLE} : $v}]
        }
        puts $h "$net\t[lindex $attrs 0]\t[llength $pins]\t[llength $loads]\t$drivers\t$dloc\t$slrs\t[lindex $attrs 1]\t[lindex $attrs 2]\t[lindex $attrs 3]"
    };close $h
}
close_design
close $receipt
puts "E004_READONLY_DIAGNOSTICS_COMPLETED"
exit 0
