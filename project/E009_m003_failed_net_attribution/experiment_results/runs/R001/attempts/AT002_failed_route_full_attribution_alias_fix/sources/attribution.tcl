# SM013: read-only queries; no source/design/placement/routing mutation.
set_param general.maxThreads 8
set out $::env(M003_OUT)
source $::env(M003_TARGETS)
proc mark {text} {puts "SM013 [clock format [clock seconds] -gmt 1 -format {%Y-%m-%dT%H:%M:%SZ}] $text"; flush stdout}
proc chan {name header} {
    set c [open [file join $::out $name] {WRONLY CREAT EXCL}]
    fconfigure $c -buffering full -buffersize 1048576 -encoding utf-8 -translation lf
    puts $c [join $header "\t"];return $c
}
proc row {c xs} {
    foreach x $xs {if {[regexp {[\t\r\n]} $x]} {error "TSV unsupported field"}}
    puts $c [join $xs "\t"]
}
proc vals {objects prop {optional 0}} {
    if {![llength $objects]} {return [list]}
    set v [get_property -quiet $prop $objects]
    if {[llength $v] != [llength $objects]} {
        set v [list]
        foreach o $objects {lappend v [get_property -quiet $prop $o]}
        row $::align [list $prop [llength $objects] SCALAR_ALIGNMENT_FALLBACK]
    }
    if {[llength $v] != [llength $objects]} {error "native property alignment: $prop"}
    if {!$optional} {foreach x $v {if {$x eq ""} {error "required property empty: $prop"}}}
    return $v
}
proc exact {command name} {
    set escaped [string map [list "\\" "\\\\" "\"" "\\\""] $name]
    set x [$command -quiet -hier -filter [format {NAME == "%s"} $escaped]]
    if {[llength $x]!=1 || [get_property NAME $x] ne $name} {error "nonunique exact native $command: $name"}
    return $x
}
proc alias {net} {
    if {[dict exists $::aliases $net]} {return [dict get $::aliases $net]}
    set seg [lsort -unique [get_nets -quiet -segments $net]]
    if {![llength $seg]} {error "empty native alias closure: $net"}
    set names [vals $seg NAME]
    if {[llength $names] != [llength $seg]} {error "native segment NAME/handle cardinality"}
    set representationEqual [expr {$names eq $seg}]
    if {!$representationEqual} {incr ::aliasRepresentationDifferences}
    set index 0
    foreach handle $seg name $names {
        incr ::aliasIdentityPairs
        set identical [expr {$handle eq $name}]
        if {$::aliasIdentityPairs<=8 || !$identical} {
            row $::aliasIdentity [list $net $index $handle $name $identical $representationEqual]
        }
        if {!$identical} {
            flush $::aliasIdentity
            error "native segment NAME/handle element identity mismatch: $net index=$index"
        }
        incr index
    }
    set can [lindex [lsort $names] 0]
    foreach s $seg {
        if {[dict exists $::aliases $s] && [dict get $::aliases $s] ne $can} {error "alias closure inconsistency"}
        dict set ::aliases $s $can
        row $::aliasout [list $can $s]
    }
    dict set ::segments $can $seg
    return $can
}
proc flushpins {} {
    if {![llength $::batchpins]} {return}
    set ns [vals $::batchpins NAME];set ds [vals $::batchpins DIRECTION]
    set refs [vals $::batchpins REF_PIN_NAME];set clocks [vals $::batchpins IS_CLOCK 1]
    set leaves [vals $::batchpins IS_LEAF]
    foreach n $ns c $::batchcan d $ds r $refs k $clocks l $leaves {
        if {$l ni {1 true TRUE}} {error "nonleaf native pin: $n"}
        row $::ends [list $c LEAF_PIN $n $d $r $k [file dirname $n]]
    }
    set ::batchpins [list];set ::batchcan [list]
}
proc exportnet {can conflict tags} {
    set seg [dict get $::segments $can]
    set pins [lsort -unique [get_pins -quiet -leaf -of_objects $seg]]
    foreach p $pins {lappend ::batchpins $p;lappend ::batchcan $can}
    row $::netsout [list $can [llength $seg] $conflict [join [lsort -unique $tags] ,]]
    foreach s $seg {
        if {[dict exists $::portmap $s]} {
            foreach p [dict get $::portmap $s] {
                if {[dict exists $::portseen $can $p]} {continue}
                dict set ::portseen $can $p 1
                row $::ends [list $can TOP_PORT $p [get_property DIRECTION $p] TOP_PORT NOT_APPLICABLE_TOP_PORT TOP_PORT]
            }
        }
    }
    if {[llength $::batchpins]>=16384} {flushpins}
}
proc main {} {
    mark OPEN_CHECKPOINT_BEGIN
    open_checkpoint $::env(M003_DCP)
    mark OPEN_CHECKPOINT_COMPLETE
    if {[version -short] ne "2025.2"} {error "unqualified Vivado version"}
    report_route_status -file [file join $::out native_route_status.rpt]
    set schema [chan native_schema.tsv {class properties}]
    foreach c {net pin cell site tile} {row $schema [list $c [list_property -class $c]]};close $schema
    set enum [list_property_value ROUTE_STATUS -class net]
    set h [chan route_status_enum.tsv {values}];row $h [list $enum];close $h
    if {"CONFLICTS" ni $enum} {error "native ROUTE_STATUS CONFLICTS unavailable"}
    set ::align [chan property_alignment.tsv {property object_count path}]
    # Device object relationships, never LOC text or report-column guesses.
    set slrs [dict create];set regions [dict create]
    foreach s [get_slrs] {foreach site [vals [get_sites -quiet -of_objects $s] NAME] {dict set slrs $site [get_property NAME $s]}}
    foreach r [get_clock_regions] {foreach site [vals [get_sites -quiet -of_objects $r] NAME] {dict set regions $site [get_property NAME $r]}}
    set h [chan sites.tsv {site SLR clock_region}]
    foreach site [lsort [dict keys $slrs]] {row $h [list $site [dict get $slrs $site] [expr {[dict exists $regions $site]?[dict get $regions $site]:"UNKNOWN"}]]};close $h
    mark CELL_INVENTORY_BEGIN
    set objects [get_cells -quiet -hier]
    set h [chan cells.tsv {name REF_NAME LOC BEL IS_PRIMITIVE}]
    for {set i 0} {$i<[llength $objects]} {incr i 16384} {
        set b [lrange $objects $i [expr {$i+16383}]]
        set names [vals $b NAME];set refs [vals $b REF_NAME]
        set locs [vals $b LOC 1];set bels [vals $b BEL 1];set leaves [vals $b IS_PRIMITIVE]
        foreach n $names r $refs l $locs be $bels le $leaves {row $h [list $n $r $l $be $le]}
    }
    close $h;unset objects
    mark CELL_INVENTORY_COMPLETE
    set ::aliases [dict create];set ::segments [dict create]
    set ::aliasIdentityPairs 0;set ::aliasRepresentationDifferences 0
    set ::aliasIdentity [chan alias_identity_sample.tsv {query_net index native_handle property_NAME element_identical list_representation_equal}]
    set ::aliasout [chan aliases.tsv {canonical segment}]
    set ::ends [chan endpoints.tsv {canonical kind name DIRECTION REF_PIN_NAME IS_CLOCK owner}]
    set ::netsout [chan net_inventory.tsv {canonical aliases conflict seed_tags}]
    set ::portmap [dict create];set ::portseen [dict create]
    foreach port [get_ports -quiet] {foreach n [get_nets -quiet -of_objects $port] {dict lappend ::portmap $n $port}}
    set seedtags [dict create];set seedobs [chan seed_queries.tsv {tag matched_native_objects}]
    foreach spec $::net_seed_queries {
        lassign $spec tag regexp
        set found [get_nets -quiet -hier -regexp $regexp]
        row $seedobs [list $tag [llength $found]]
        foreach n $found {dict lappend seedtags [alias $n] $tag}
    }
    foreach {tag names} [list TOP10_LITERAL $::literal_net_seeds KNOWN_C01_CROSS_SLR $::known_cross_slr_net_seeds] {
        foreach n $names {
            if {[catch {exact get_nets $n} object]} {
                row $seedobs [list ${tag}_NOT_FOUND:$n NOT_MEASURED]
                continue
            }
            dict lappend seedtags [alias $object] $tag
        }
    }
    # Inspect each of the frozen 48+16+16 protection leaves. Only actual output
    # and input nets enter supplementary scope; no full-design fanin traversal.
    set protect [chan protection80.tsv {tag cell REF_NAME INIT DONT_TOUCH}]
    foreach spec $::protection_queries {
        lassign $spec tag regexp ref expected
        set cs [get_cells -quiet -hier -regexp $regexp]
        if {[llength $cs]!=$expected} {error "protection count $tag: [llength $cs] != $expected"}
        foreach c $cs {
            if {[get_property REF_NAME $c] ne $ref} {error "protection REF mismatch"}
            row $protect [list $tag $c $ref [get_property INIT $c] [get_property DONT_TOUCH $c]]
            foreach n [get_nets -quiet -of_objects [get_pins -quiet -of_objects $c]] {dict lappend seedtags [alias $n] PROTECTION80_$tag}
        }
    }
    close $protect;close $seedobs
    set conflicts [get_nets -quiet -hier -filter {ROUTE_STATUS == CONFLICTS}]
    set raw [chan raw_conflicts.tsv {native_net}]
    set canonical [dict create]
    foreach n $conflicts {row $raw [list [get_property NAME $n]];dict set canonical [alias $n] 1}
    close $raw;unset conflicts
    set h [chan alias_identity_summary.tsv {native_element_pairs list_representation_differences qualification}]
    row $h [list $::aliasIdentityPairs $::aliasRepresentationDifferences ALL_ELEMENTS_EXACT_MATCH]
    close $h;close $::aliasIdentity
    mark "CONFLICT_CANONICALIZATION_COMPLETE count=[dict size $canonical]"
    set ::batchpins [list];set ::batchcan [list];set count 0
    foreach can [lsort [dict keys $canonical]] {
        exportnet $can 1 [expr {[dict exists $seedtags $can]?[dict get $seedtags $can]:{}}]
        incr count
        if {$count % 4096==0} {flush $::ends;flush $::netsout;mark "FAILED_NET_EXPORT $count/[dict size $canonical]"}
    }
    dict for {can tags} $seedtags {if {![dict exists $canonical $can]} {exportnet $can 0 $tags}}
    flushpins
    foreach c [list $::aliasout $::ends $::netsout] {close $c}
    mark LIGHT_EXPORT_COMPLETE
    set aggregate [list /usr/bin/env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 $::env(M003_AGGREGATE) --out $::out --plan $::env(M003_PLAN)]
    puts [exec {*}$aggregate]
    source [file join $::out deep_targets.tcl]
    set deepcells [dict create];set grouppins [dict create]
    foreach net $deep_nets {
        set ps [get_pins -quiet -leaf -of_objects [dict get $::segments $net]]
        foreach c [get_cells -quiet -of_objects $ps] {dict set deepcells $c 1}
    }
    set h [chan deep_cells.tsv {name REF_NAME LOC BEL IS_LOC_FIXED IS_BEL_FIXED ORIG_CELL_NAME ORIG_REF_NAME RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH USER_SLR_ASSIGNMENT PARENT}]
    set cs [dict keys $deepcells];set supported [list_property -class cell]
    for {set i 0} {$i<[llength $cs]} {incr i 8192} {
        set b [lrange $cs $i [expr {$i+8191}]];set cols [list]
        foreach p {REF_NAME LOC BEL IS_LOC_FIXED IS_BEL_FIXED ORIG_CELL_NAME ORIG_REF_NAME RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH USER_SLR_ASSIGNMENT PARENT} {
            if {$p in $supported} {lappend cols [vals $b $p 1]} else {lappend cols [lrepeat [llength $b] NOT_MEASURED]}
        }
        for {set j 0} {$j<[llength $b]} {incr j} {set v [list [lindex $b $j]];foreach col $cols {lappend v [lindex $col $j]};row $h $v}
    };close $h
    set locs [lsort -unique [vals $cs LOC 1]]
    set h [chan deep_site_tiles.tsv {site tile GRID_POINT_X GRID_POINT_Y}]
    set tileprops [list_property -class tile]
    foreach loc $locs {
        if {$loc eq ""} {continue}
        set tiles [get_tiles -quiet -of_objects [get_sites -quiet $loc]]
        foreach t $tiles {
            set v [list $loc [get_property NAME $t]]
            foreach p {GRID_POINT_X GRID_POINT_Y} {lappend v [expr {$p in $tileprops?[get_property $p $t]:"NOT_MEASURED"}]}
            row $h $v
        }
    };close $h
    set h [chan timing_receipts.tsv {group delay_type native_code endpoints cap output_or_error}]
    dict for {tag ns} $timing_groups {
        set pins [list]
        foreach n $ns {foreach p [get_pins -quiet -leaf -of_objects [dict get $::segments $n] -filter {DIRECTION == IN}] {lappend pins $p}}
        set pins [lrange [lsort -unique $pins] 0 15]
        foreach delay {max min} {
            if {![llength $pins]} {row $h [list $tag $delay NOT_MEASURED 0 2 NO_LOAD_ENDPOINT];continue}
            set file [file join $::out timing_${tag}_${delay}.rpt]
            set code [catch {report_timing -through $pins -delay_type $delay -max_paths 2 -nworst 1 -file $file} err]
            row $h [list $tag $delay $code [llength $pins] 2 [expr {$code?$err:$file}]]
        }
        mark "BOUNDED_TIMING_GROUP_COMPLETE $tag"
    };close $h
    close $::align
    puts [exec {*}$aggregate --final]
    set h [open [file join $::out native_completed.txt] {WRONLY CREAT EXCL}]
    puts $h "scope_exhausted=1\nphysical_mutation=0\ncheckpoint_write=0\noverlap_node_complete_map=NOT_MEASURED";close $h
    mark SCOPE_EXHAUSTED
    close_design
}
if {[catch {main} result options]} {
    set h [open [file join $out native_error.tcllist] {WRONLY CREAT EXCL}]
    puts $h [list result $result options $options];close $h
    puts stderr $result
    exit 1
}
exit 0
