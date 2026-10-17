# Shared pure procedure library; no native queries at source time.
# coverage_version=candidate_directed_cut_v1. Native class/local gates run first.
namespace eval slr2 {
    variable directedI [dict create]
    variable directedLocal [dict create]
    variable directedGroups [dict create]
    variable directedSegmentCanonical [dict create]
    variable directedRawPins [dict create]
    variable directedLocalDirections [dict create]
}
proc slr2::directed_trace {operation event args} {
    puts [list DIRECTED_API operation $operation event $event epoch_ms [clock milliseconds] detail $args]
}
proc slr2::directed_role {kind direction} {
    if {$direction eq "INOUT"} {return INOUT}
    if {$kind eq "LEAF_PIN"} {
        if {$direction eq "OUT"} {return DRIVER}
        if {$direction eq "IN"} {return LOAD}
    } else {
        if {$direction eq "IN"} {return DRIVER}
        if {$direction eq "OUT"} {return LOAD}
    }
    return UNKNOWN
}
proc slr2::directed_schema_gate {point} {
    directed_trace CLASS_SCHEMA BEGIN $point
    set commands [list [list list_property -class pin] [list list_property_value DIRECTION -class pin]]
    set rows [list];set valid 1;set values [list]
    foreach command $commands {
        set code [catch {uplevel #0 $command} result options]
        lappend rows [list command $command native_tcl_code $code result $result options $options]
        if {$code} {set valid 0}
        lappend values [expr {$code ? {} : $result}]
    }
    lassign $values properties enums
    foreach property {NAME DIRECTION IS_LEAF} {if {$property ni $properties} {set valid 0}}
    foreach direction {IN OUT INOUT} {if {$direction ni $enums} {set valid 0}}
    if {![llength $enums] || [version -short] ne "2025.2"} {set valid 0}
    m002_put [file join $::m002_report_dir candidate_directed_class_schema_${point}.tcllist] [list coverage_version candidate_directed_cut_v1 native_tool [version -short] qualified $valid responses $rows]
    directed_trace CLASS_SCHEMA END $point qualified $valid
    if {!$valid} {error "UNQUALIFIED: native pin class DIRECTION/IS_LEAF schema guarantee unavailable; no global leaf fallback is automatically requested"}
    return 1
}
proc slr2::directed_pin_columns {pins} {
    set result [dict create]
    foreach property {NAME DIRECTION REF_PIN_NAME IS_CLOCK IS_LEAF} {
        set values [list]
        if {[llength $pins]} {set values [property_values $pins $property [expr {$property ni {NAME IS_LEAF}}] directed_retained_pin_columns]}
        dict set result $property $values
    }
    foreach leaf [dict get $result IS_LEAF] {if {$leaf ni {1 true TRUE}} {error "Nonleaf pin returned by native leaf scope"}}
    return $result
}
proc slr2::directed_alias {net} {
    variable directedGroups;variable directedSegmentCanonical
    set name [get_property NAME $net]
    if {[dict exists $directedSegmentCanonical $name]} {return [dict get $directedSegmentCanonical $name]}
    set segments [lsort -unique [get_nets -segments $net]]
    if {![llength $segments]} {error "Native alias closure is empty: $name"}
    set names [property_values $segments NAME 0 directed_alias]
    if {[llength [lsort -unique $names]] != [llength $segments]} {error "Duplicate/ambiguous native alias NAME"}
    set canonical [lindex [lsort $names] 0]
    foreach segment $names {
        if {[dict exists $directedSegmentCanonical $segment] && [dict get $directedSegmentCanonical $segment] ne $canonical} {error "Inconsistent native alias closure"}
        dict set directedSegmentCanonical $segment $canonical
    }
    dict set directedGroups $canonical $segments
    return $canonical
}
proc slr2::directed_local_scope {point} {
    variable RAW;variable S;variable P;variable directedI;variable directedLocal
    variable directedGroups;variable directedSegmentCanonical;variable directedRawPins;variable directedLocalDirections
    set directedI [dict create];set directedLocal [dict create];set directedGroups [dict create]
    set directedSegmentCanonical [dict create];set directedRawPins [dict create];set directedLocalDirections [dict create]
    set all [objects [lsort -unique [concat [dict keys $RAW] [dict keys $P]]]]
    ensure_cells $all
    set owners [dict create]
    foreach object $all name [property_values $all NAME 0 directed_local_owner] leaf [property_values $all IS_PRIMITIVE 0 directed_local_owner] {
        set ref [value $name REF_NAME]
        if {$leaf in {1 true TRUE}} {dict set owners $name $object}
        if {[dict exists $P $name] && $ref eq "DSP48E2"} {
            set broad $name;set bracket [string first {[} $name]
            if {$bracket >= 0} {set broad [string range $name 0 [expr {$bracket-1}]]}
            set broadChildren [get_cells -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s*"} $broad]]
            set descendants [list]
            foreach child $broadChildren childName [property_values $broadChildren NAME 0 directed_DSP_literal_children] {
                if {[prefix $childName ${name}/]} {lappend descendants $child}
            }
            ensure_cells $descendants
            foreach child $descendants childName [property_values $descendants NAME 0 directed_DSP_children] {
                lassign [physical $childName [value $childName REF_NAME]] parent pref
                if {$parent ne $name || $pref ne "DSP48E2"} {error "Unproven DSP native child/physical parent: $childName -> $parent"}
                dict set owners $childName $child
            }
        } elseif {[dict exists $P $name] && $leaf ni {1 true TRUE}} {error "Unexplained nonprimitive P leaf-owner expansion: $name/$ref"}
    }
    # Parent interfaces remain in the original RAW/P pin ledger even when nonleaf.
    foreach object $all name [property_values $all NAME 0 directed_local_parent_interfaces] {dict set owners $name $object}
    set output [open [file join $::m002_report_dir candidate_pins_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $output "NAME\tDIRECTION\tIS_LEAF\traw_cell\tREF_NAME\tphysical_parent\tinside_RAW\tinside_S\tinside_P\tinside_candidate_leaf\tconnection_status\tcanonical_net"
    set mapping [open [file join $::m002_report_dir candidate_local_pin_net_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $mapping "pin\tnative_net_segment\tcanonical_net"
    set pCoverage [dict create];set issues [list];set ownerCount 0
    dict for {owner object} $owners {
        incr ownerCount
        if {$ownerCount % 128 == 0} {directed_trace LOCAL_OWNER_MAPPING PROGRESS $point owners $ownerCount total [dict size $owners]}
        set pins [get_pins -of_objects $object]
        set names [property_values $pins NAME 0 directed_local_pins]
        set directions [property_values $pins DIRECTION 1 directed_local_pins]
        set leaves [property_values $pins IS_LEAF 0 directed_local_pins]
        foreach pin $pins name $names direction $directions leaf $leaves {
            if {[file dirname $name] ne $owner} {lappend issues [list ACTUAL_PIN_OWNER_IDENTITY_MISMATCH $name $owner]}
            if {[dict exists $directedRawPins $name]} {
                if {[dict get $directedRawPins $name] ne $pin} {lappend issues [list DUPLICATE_NATIVE_PIN_NAME $name]}
                continue
            }
            dict set directedRawPins $name $pin
            dict set directedLocalDirections $name $direction
            set ref [value $owner REF_NAME];lassign [physical $owner $ref] parent pref
            set sin [dict exists $S $owner];set pinP [dict exists $P $parent]
            if {$leaf ni {1 true TRUE 0 false FALSE}} {lappend issues [list UNKNOWN_NATIVE_IS_LEAF $name $leaf]}
            set inside [expr {$leaf in {1 true TRUE} && ($sin || $pinP)}]
            if {$inside} {
                dict set directedI $name $pin
                dict set pCoverage $parent 1
            }
            set groups [dict create]
            foreach net [get_nets -of_objects $pin] {
                set canonical [directed_alias $net]
                dict set groups $canonical 1
                puts $mapping [join [list $name [get_property NAME $net] $canonical] "\t"]
            }
            set status [expr {![dict size $groups] ? "DISCONNECTED" : ([dict size $groups] == 1 ? "CONNECTED" : "UNRESOLVED_MULTIPLE_CANONICAL_GROUPS")}]
            if {[dict size $groups] > 1} {lappend issues [list MULTIPLE_CANONICAL_GROUPS $name [dict keys $groups]]}
            foreach canonical [dict keys $groups] {
                if {$leaf in {1 true TRUE}} {dict set directedLocal $canonical $name [list $pin $direction $inside $owner $parent]}
            }
            puts $output [join [list $name $direction $leaf $owner $ref $parent [dict exists $RAW $owner] $sin $pinP $inside $status [dict keys $groups]] "\t"]
        }
    }
    close $output;close $mapping
    dict for {name ref} $P {if {![dict exists $pCoverage $name]} {lappend issues [list ACTUAL_P_HAS_NO_PROVEN_NATIVE_LEAF_PINS $name $ref]}}
    set segmentsOut [open [file join $::m002_report_dir candidate_segments_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $segmentsOut "canonical_net\tsegment"
    dict for {canonical segments} $directedGroups {foreach name [property_values $segments NAME 0 directed_alias_export] {puts $segmentsOut "$canonical\t$name"}}
    close $segmentsOut
    m002_put [file join $::m002_report_dir candidate_local_scope_${point}.tcllist] [list coverage_version candidate_directed_cut_v1 candidate_leaf_pins [dict keys $directedI] raw_pin_records [dict size $directedRawPins] canonical_nets [dict size $directedGroups] issues $issues]
    if {[llength $issues] || ![dict size $directedI]} {error "UNQUALIFIED: candidate native leaf/owner/alias coverage incomplete; original ledgers retained"}
    return [dict size $directedI]
}
proc slr2::directed_choose_scope {roleRows portRows localRows roleQueryOK} {
    set drivers [dict create];set reasons [list]
    if {!$roleQueryOK} {lappend reasons NATIVE_NONLOAD_ROLE_QUERY_FAILED}
    set roleNames [dict create]
    foreach row $roleRows {
        lassign $row name direction inside
        set role [directed_role LEAF_PIN $direction]
        if {[dict exists $roleNames $name] && [dict get $roleNames $name] ne $direction} {lappend reasons SAME_NAME_CONFLICTING_DIRECTIONS}
        dict set roleNames $name $direction
        if {$role eq "LOAD"} {lappend reasons NATIVE_NONLOAD_FILTER_RETURNED_IN}
        if {$role in {INOUT UNKNOWN}} {lappend reasons UNRESOLVED_LEAF_DIRECTION}
        if {$role eq "DRIVER"} {dict set drivers LEAF_PIN/$name $inside}
    }
    foreach row $portRows {
        lassign $row name direction
        set role [directed_role TOP_PORT $direction]
        if {$role in {INOUT UNKNOWN}} {lappend reasons UNRESOLVED_TOP_DIRECTION}
        if {$role eq "DRIVER"} {dict set drivers TOP_PORT/$name 0}
    }
    foreach row $localRows {
        lassign $row name direction inside
        if {$direction ne "IN" && (![dict exists $roleNames $name] || [dict get $roleNames $name] ne $direction)} {lappend reasons LOCAL_NONLOAD_MISSING_FROM_NATIVE_ROLE_CENSUS}
        if {[directed_role LEAF_PIN $direction] in {INOUT UNKNOWN}} {lappend reasons LOCAL_UNKNOWN_DIRECTION}
    }
    if {[dict size $drivers] != 1} {lappend reasons NO_OR_MULTIPLE_NATIVE_DRIVERS}
    if {![llength $reasons] && [lindex [dict values $drivers] 0]} {return [dict create mode FULL_ENUMERATION_CANDIDATE_DRIVER reason ACTUAL_UNIQUE_CANDIDATE_DRIVER native_role_gate_qualified 1]}
    if {[llength $reasons]} {return [dict create mode FULL_ENUMERATION_FALLBACK reason [lsort -unique $reasons] native_role_gate_qualified 0]}
    return [dict create mode RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT reason ACTUAL_UNIQUE_EXTERNAL_DRIVER_LOCAL_LEAF_COMPLETE native_role_gate_qualified 1]
}
proc slr2::retained_reason {pin raw role mode} {
    variable directedI;variable RAW
    if {[dict exists $directedI $pin]} {return CANDIDATE_NATIVE_LEAF}
    if {[dict exists $RAW $raw]} {return RAW_ONLY_NATIVE_LEAF}
    if {$role eq "DRIVER"} {return ACTUAL_NATIVE_DRIVER}
    if {$mode eq "RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT"} {error "Unexpected outside peer retained in reduced scope: $pin/$role"}
    return $mode
}
proc slr2::cut {point} {
    variable RAW;variable S;variable P;variable mapping;variable cellInfo
    variable directedI;variable directedLocal;variable directedGroups;variable directedRawPins
    directed_schema_gate $point
    directed_trace LOCAL_PIN_NET_MAPPING BEGIN $point
    directed_local_scope $point
    directed_trace LOCAL_PIN_NET_MAPPING END $point
    set I $directedI
    directed_trace NATIVE_CLOCK_DOMAINS BEGIN $point
    clock_domains $point
    directed_trace NATIVE_CLOCK_DOMAINS END $point
    set ::slr2::boundaryPins [dict create]
    set timingScope [open [file join $::m002_report_dir candidate_boundary_timing_scope_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $timingScope "canonical_net\tcut_direction\tquery_endpoint_kind\tquery_endpoint_NAME\tDIRECTION\trole\tpin_class\tclock_group\tselection_basis"
    set nets [open [file join $::m002_report_dir candidate_nets_${point}.tsv] {WRONLY CREAT EXCL}]
    set ends [open [file join $::m002_report_dir candidate_endpoints_${point}.tsv] {WRONLY CREAT EXCL}]
    set roleQueries [open [file join $::m002_report_dir candidate_native_role_queries_${point}.tcllist] {WRONLY CREAT EXCL}]
    puts $nets "canonical_net\tsegments\tscope_mode\tscope_reason\texported_leaf_pin_rows\texported_top_port_rows\tretained_drivers\tretained_INOUT\tretained_inside_endpoints\tretained_outside_endpoints\tretained_unknown_observations\tresolution\tboundary\tretained_classes\tactual_clocks\toutside_peer_leaf_loads\tfull_native_leaf_count\texported_endpoint_rows\tfull_net_endpoint_coverage\tdirected_boundary_complete\tcandidate_leaf_coverage_complete\tnative_role_gate_qualified\tcoverage_version"
    puts $ends "canonical_net\tkind\tNAME\tDIRECTION\trole\traw_cell\tREF_NAME\tphysical_parent\tinside_RAW\tinside_S\tinside_P\tLOC\tSLR\tpin_class\tREF_PIN_NAME\tIS_CLOCK\tBEL\tnative_site\tnative_tile\tnative_clock_region\towner_root\tdetail_parent\tnative_clock_group\tunresolved_reason\tretained_reason"
    set complete 0;set reduced 0;set count 0
    dict for {canonical segments} $directedGroups {
        incr count
        set roleCommand [list get_pins -leaf -of_objects $segments -filter {DIRECTION != IN}]
        directed_trace NONLOAD_LEAF BEGIN $point $canonical
        set roleCode [catch {
            set rolePins [uplevel #0 $roleCommand]
            set roleNames [property_values $rolePins NAME 0 directed_native_nonload]
            set roleDirections [property_values $rolePins DIRECTION 1 directed_native_nonload]
            set roleLeaves [property_values $rolePins IS_LEAF 0 directed_native_nonload]
            foreach leaf $roleLeaves {if {$leaf ni {1 true TRUE}} {error "Native nonload -leaf query returned nonleaf"}}
        } roleResult roleOptions]
        directed_trace NONLOAD_LEAF END $point $canonical code $roleCode
        if {$roleCode} {set rolePins [list];set roleNames [list];set roleDirections [list]}
        puts $roleQueries [list canonical_net $canonical query_kind NONLOAD_LEAF command $roleCommand actual_segment_NAMES [property_values $segments NAME 0 directed_role_segments] native_tcl_code $roleCode result [expr {$roleCode ? $roleResult : {}}] raw_objects [llength $rolePins] actual_NAMES $roleNames actual_DIRECTIONS $roleDirections];flush $roleQueries
        set portCommand [list get_ports -of_objects $segments]
        set portCode [catch {
            set ports [uplevel #0 $portCommand]
            set portNames [property_values $ports NAME 0 directed_all_top_ports]
            set portDirections [property_values $ports DIRECTION 1 directed_all_top_ports]
            if {[llength [lsort -unique $portNames]] != [llength $ports]} {error "Duplicate native top port identities"}
        } portResult portOptions]
        puts $roleQueries [list canonical_net $canonical query_kind ALL_TOP_PORTS command $portCommand native_tcl_code $portCode result [expr {$portCode ? $portResult : {}}] actual_segment_NAMES [property_values $segments NAME 0 directed_role_segments] raw_objects [expr {$portCode ? 0 : [llength $ports]}] actual_NAMES [expr {$portCode ? {} : $portNames}] actual_DIRECTIONS [expr {$portCode ? {} : $portDirections}]];flush $roleQueries
        if {$portCode} {error "UNQUALIFIED: complete native top-port inventory failed: $portResult"}
        set roleRows [list]
        foreach pin $roleNames direction $roleDirections {lappend roleRows [list $pin $direction [dict exists $I $pin]]}
        set portRows [list];foreach name $portNames direction $portDirections {lappend portRows [list $name $direction]}
        set localRows [list];set localHandles [dict create]
        if {[dict exists $directedLocal $canonical]} {
            dict for {name spec} [dict get $directedLocal $canonical] {
                lassign $spec pin direction inside owner parent
                lappend localRows [list $name $direction $inside];dict set localHandles $name $pin
            }
        }
        set decision [directed_choose_scope $roleRows $portRows $localRows [expr {!$roleCode}]]
        set mode [dict get $decision mode]
        if {$mode eq "RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT"} {
            # This branch MUST NOT issue an unfiltered all-segment leaf query.
            set keep $localHandles
            foreach pin $rolePins name $roleNames {dict set keep $name $pin}
            set pins [dict values $keep]
            set externalPeers NOT_ENUMERATED;set fullLeafCount NOT_MEASURED;set fullCoverage false
            incr reduced
        } else {
            set fullCommand [list get_pins -leaf -of_objects $segments]
            directed_trace FULL_LEAF_FALLBACK BEGIN $point $canonical
            set pins [uplevel #0 $fullCommand]
            directed_trace FULL_LEAF_FALLBACK END $point $canonical raw_objects [llength $pins]
            set fullNames [property_values $pins NAME 0 directed_full_fallback]
            set keep [dict create];foreach pin $pins name $fullNames {dict set keep $name $pin}
            set pins [dict values $keep]
            dict for {name pin} $localHandles {if {![dict exists $keep $name]} {error "Full native fallback omitted a proven local leaf: $name"}}
            puts $roleQueries [list canonical_net $canonical query_kind FULL_LEAF command $fullCommand actual_segment_NAMES [property_values $segments NAME 0 directed_role_segments] native_tcl_code 0 raw_objects [llength $fullNames] unique_objects [llength $pins] actual_NAMES $fullNames];flush $roleQueries
            set externalPeers ENUMERATED_IN_FULL_NATIVE_SCOPE;set fullLeafCount [llength $pins];set fullCoverage true
            incr complete
        }
        # Rich cell/pin/spatial properties are read only AFTER local/role selection.
        if {[llength $pins]} {ensure_cells [get_cells -of_objects $pins]}
        set columns [directed_pin_columns $pins]
        set drivers 0;set inout 0;set inside 0;set outside 0;set unknown 0;set roleUnknown 0;set classes [dict create]
        set insideDriver 0;set localTiming [list];set insideLoads [list];set outsideLoads [list]
        foreach pin [dict get $columns NAME] direction [dict get $columns DIRECTION] terminal [dict get $columns REF_PIN_NAME] clock [dict get $columns IS_CLOCK] {
            set role UNKNOWN
            if {$direction eq "OUT"} {set role DRIVER;incr drivers} elseif {$direction eq "IN"} {set role LOAD} elseif {$direction eq "INOUT"} {set role INOUT;incr inout} else {incr unknown;incr roleUnknown}
            set raw [file dirname $pin];set parent "";set ref UNKNOWN;set loc ""
            if {[dict exists $cellInfo $raw]} {
                set ref [value $raw REF_NAME]
                lassign [physical $raw $ref] parent pref
                if {$parent ne ""} {
                    set loc [value $parent LOC]
                } else {incr unknown}
            } else {incr unknown}
            set sin [dict exists $S $raw];set pinP [dict exists $P $parent]
            if {[dict exists $I $pin] != ($sin || $pinP)} {error "Native local leaf ownership and endpoint physical mapping disagree: $pin"}
            if {$sin || $pinP} {incr inside} else {incr outside}
            set cls [pin_class $ref $terminal $clock]
            if {$ref in {GND VCC}} {set cls CONSTANT}
            dict incr classes $cls
            set bel UNKNOWN;set reason ""
            if {$parent ne ""} {set bel [value $parent BEL]} else {set reason UNRESOLVED_PHYSICAL_PARENT}
            lassign [spatial $loc] site tile region
            set clockGroup [domains $raw]
            if {$tile eq "UNKNOWN" || $region eq "UNKNOWN"} {lappend reason UNKNOWN_NATIVE_SPATIAL_MAPPING}
            if {$clockGroup eq "UNKNOWN_NATIVE_REGISTER_CLOCK_MAPPING"} {lappend reason UNKNOWN_NATIVE_CLOCK_MAPPING}
            set timingSpec [list LEAF_PIN $pin $direction $role $cls $clockGroup]
            if {$sin || $pinP} {
                if {$role eq "DRIVER"} {incr insideDriver}
                lappend localTiming $timingSpec
                if {$role eq "LOAD"} {lappend insideLoads $timingSpec}
            } elseif {$role eq "LOAD"} {lappend outsideLoads $timingSpec}
            puts $ends [join [list $canonical LEAF_PIN $pin $direction $role $raw $ref $parent [dict exists $RAW $raw] $sin $pinP $loc [slr $loc] $cls $terminal $clock $bel $site $tile $region [owner $raw] [file dirname $raw] $clockGroup $reason [retained_reason $pin $raw $role $mode]] "\t"]
        }
        set portNames [list];set portDirections [list]
        if {[llength $ports]} {set portNames [property_values $ports NAME 0 top_port_columns];set portDirections [property_values $ports DIRECTION 1 top_port_columns]}
        foreach port $portNames direction $portDirections {
            set role UNKNOWN
            if {$direction eq "IN"} {set role DRIVER;incr drivers} elseif {$direction eq "OUT"} {set role LOAD} elseif {$direction eq "INOUT"} {set role INOUT;incr inout} else {incr unknown;incr roleUnknown}
            incr outside
            if {$role eq "LOAD"} {lappend outsideLoads [list TOP_PORT $port $direction $role TOP_PORT [get_clocks -quiet -of_objects $port]]}
            puts $ends [join [list $canonical TOP_PORT $port $direction $role TOP_PORT TOP_PORT TOP_PORT 0 0 0 "" TOP_PORT TOP_PORT "" NOT_APPLICABLE_TOP_PORT UNKNOWN TOP_PORT UNKNOWN UNKNOWN TOP_PORT TOP_PORT [get_clocks -quiet -of_objects $port] "" ALL_NATIVE_TOP_PORTS] "\t"]
        }
        set resolution [expr {$roleUnknown ? "UNKNOWN_RETAINED" : ($inout ? "INOUT_RETAINED" : ($drivers == 1 ? "SINGLE_DRIVER" : ($drivers == 0 ? "NO_DRIVER" : "MULTIDRIVER_RETAINED")))}]
        set boundary [expr {$inside && $outside ? "CUT" : ($unknown ? "UNRESOLVED" : ($inside ? "INTERNAL" : "RAW_SCOPE_ONLY"))}]
        if {$boundary eq "CUT"} {
            lassign [timing_boundary_selection $resolution $insideDriver $insideLoads $outsideLoads $localTiming] direction selectedTiming selectionBasis
            foreach spec $selectedTiming {
                lassign $spec kind pin pinDirection role cls clockGroup
                dict set ::slr2::boundaryPins $direction $pin 1
                puts $timingScope [join [list $canonical $direction $kind $pin $pinDirection $role $cls $clockGroup $selectionBasis] "\t"]
            }
        }
        puts $nets [join [list $canonical [llength $segments] $mode [dict get $decision reason] [llength $pins] [llength $ports] $drivers $inout $inside $outside $unknown $resolution $boundary $classes [get_clocks -quiet -of_objects $segments] $externalPeers $fullLeafCount [expr {[llength $pins]+[llength $ports]}] $fullCoverage true true [dict get $decision native_role_gate_qualified] candidate_directed_cut_v1] "\t"]
        if {$count % 100 == 0} {flush $nets;flush $ends;puts "DIRECTED_CUT_PROGRESS point=$point closed_nets=$count reduced=$reduced full=$complete"}
    }
    close $nets;close $ends;close $timingScope;close $roleQueries
    m002_put [file join $::m002_report_dir candidate_cut_${point}_closed.txt] "completed=1\ncoverage_version=candidate_directed_cut_v1\ndirected_boundary_complete=true\ncandidate_leaf_coverage_complete=true\nnative_pin_class_schema_qualified=true\nreduced_ingress_nets=$reduced\nfull_enumeration_nets=$complete\ncanonical_nets=$count\nfull_cut_TNS=NOT_MEASURED\nwhole_attached_net_endpoint_coverage=NOT_CLAIMED"
    if {[info exists ::env(SLR2_ADAPTER)]} {set adapter $::env(SLR2_ADAPTER)} else {set adapter $::env(E006_CANDIDATE_ADAPTER)}
    exec python3 $adapter cut $point $::m002_report_dir
    puts "DIRECTED_CUT_COMPLETED point=$point coverage_version=candidate_directed_cut_v1"
}
