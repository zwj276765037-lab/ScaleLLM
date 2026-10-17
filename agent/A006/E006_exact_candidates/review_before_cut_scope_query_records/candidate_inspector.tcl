# Derived pure query procedures only. No source-time native queries or physical policy writes.
source [file join [file dirname [file normalize [info script]]] property_alignment.tcl]
namespace eval slr2 {
    variable base scalellm_vcu118_f05_bd_i/core/inst/u_core/
    variable RAW [dict create];variable S [dict create];variable P [dict create]
    variable mapping [dict create];variable handles [dict create]
    variable physicalCache [dict create];variable cellInfo [dict create]
    variable spatialCache [dict create];variable domainCache [dict create]
    variable boundaryPins [dict create];variable siteSLR [dict create]
    variable candidateSets [dict create]
}
proc m002_put {path text} {set h [open $path {WRONLY CREAT EXCL}];puts $h $text;close $h}
proc m002_prop {object property} {get_property -quiet $property $object}
proc m002_exact {getter name} {
    if {$getter ne "get_cells"} {error "Only exact read-only cell resolution is admitted"}
    set objects [get_cells -quiet -hier -filter [format {NAME == "%s"} $name]]
    if {[llength $objects] != 1 || [get_property NAME $objects] ne $name} {error "Exact hierarchy/cell missing or nonunique: $name"}
    return $objects
}
proc slr2::prefix {name value} {expr {[string first $value $name] == 0}}
proc slr2::slr loc {
    variable siteSLR
    if {$loc eq ""} {return UNPLACED}
    if {[dict exists $siteSLR $loc]} {return [dict get $siteSLR $loc]}
    return UNKNOWN
}
proc slr2::physical {name ref} {
    variable physicalCache;variable handles;variable cellInfo
    if {[dict exists $physicalCache $name]} {return [dict get $physicalCache $name]}
    if {[prefix $ref DSP] && $ref ne "DSP48E2"} {
        set parent [file dirname $name]
        while {$parent ne "." && $parent ne "/"} {
            if {[dict exists $handles $parent]} {set object [dict get $handles $parent]} else {set object [m002_exact get_cells $parent]}
            if {[llength $object] == 1 && [m002_prop $object REF_NAME] eq "DSP48E2"} {
                dict set handles $parent $object
                dict set physicalCache $name [list $parent DSP48E2]
                return [dict get $physicalCache $name]
            }
            set parent [file dirname $parent]
        }
        return [list "" UNRESOLVED_DSP_PARENT]
    }
    dict set physicalCache $name [list $name $ref]
    return [dict get $physicalCache $name]
}
proc slr2::ensure_cells cells {
    variable cellInfo;variable handles
    set missing [list]
    foreach cell $cells {if {![dict exists $cellInfo $cell]} {lappend missing $cell}}
    for {set i 0} {$i < [llength $missing]} {incr i 16384} {
        set batch [lrange $missing $i [expr {$i+16383}]]
        set names [property_values $batch NAME 0 cell_cache]
        set columns [dict create]
        foreach property {REF_NAME LOC BEL} {
            set values [property_values $batch $property [expr {$property ne "REF_NAME"}] cell_cache]
            dict set columns $property $values
        }
        for {set j 0} {$j < [llength $batch]} {incr j} {
            set name [lindex $names $j];set values [dict create]
            dict for {property column} $columns {dict set values $property [lindex $column $j]}
            dict set cellInfo $name $values;dict set handles $name [lindex $batch $j]
        }
    }
}
proc slr2::property_values {objects property allow_empty context} {
    return [propertyalign::values $objects $property $allow_empty $context [file join $::m002_report_dir candidate_property_alignment.tsv]]
}
proc slr2::value {name property} {
    variable cellInfo
    if {![dict exists $cellInfo $name $property]} {ensure_cells [objects [list $name]]}
    return [dict get $cellInfo $name $property]
}
proc slr2::pin_columns pins {
    set result [dict create]
    if {![llength $pins]} {foreach property {NAME DIRECTION REF_PIN_NAME IS_CLOCK} {dict set result $property [list]};return $result}
    foreach property {NAME DIRECTION REF_PIN_NAME IS_CLOCK} {
        set values [property_values $pins $property [expr {$property eq "IS_CLOCK"}] pin_columns]
        dict set result $property $values
    }
    return $result
}
proc slr2::objects names {
    variable handles
    # Vivado object handles are preserved as a Tcl list, never re-evaluated/globbed.
    # Exact equality resolves literal array brackets.
    set result [list]
    foreach name $names {
        if {[dict exists $handles $name]} {set object [dict get $handles $name]} else {
            set object [m002_exact get_cells $name]
            if {[llength $object] != 1 || [get_property NAME $object] ne $name} {error "Nonunique exact object: $name"}
        }
        lappend result $object
    }
    return $result
}
proc slr2::pin_class {ref terminal clock} {
    if {$ref in {GND VCC}} {return CONSTANT}
    if {[prefix $ref DSP] && [regexp {^C(?:\[[0-9]+\])?$} $terminal]} {return DATA_ARITHMETIC}
    if {$clock in {1 true TRUE}} {return CLOCK_NATIVE_PIN}
    if {[regexp {^FD(RE|CE|PE)$} $ref]} {
        if {$terminal eq "C"} {return CLOCK_REF_PIN}
        if {$terminal in {R CLR PRE}} {return RESET_SET}
        if {$terminal eq "CE"} {return ENABLE_WRITE_CONTROL}
        if {$terminal in {D Q}} {return DATA_REGISTER}
    }
    if {[prefix $ref DSP]} {
        if {[regexp {^CLK$} $terminal]} {return CLOCK_REF_PIN}
        if {[regexp {^RST} $terminal]} {return RESET_SET}
        if {[regexp {^CE} $terminal]} {return ENABLE_WRITE_CONTROL}
        if {[regexp {^(A|B|C|D|P|ACIN|ACOUT|BCIN|BCOUT|PCIN|PCOUT)(\[[0-9]+\])?$} $terminal]} {return DATA_ARITHMETIC}
        return UNKNOWN_DSP_PIN
    }
    if {[regexp {^BU(FG|FH|FR|FIO|FMR|FCE)} $ref] && $terminal eq "O"} {return CLOCK_BUFFER_OUTPUT_REF}
    if {[regexp {^LUT[1-6]$} $ref]} {return LOGIC_PIN_FUNCTION_UNCLASSIFIED}
    if {$ref in {MUXF7 MUXF8} && $terminal eq "S"} {return SELECT_CONTROL}
    if {$ref in {MUXF7 MUXF8 CARRY8}} {return DATA_LOGIC_PRIMITIVE}
    return UNKNOWN_REF_PIN
}
proc slr2::cut point {
    variable RAW;variable S; variable P; variable mapping;variable cellInfo
    set objects [objects [lsort -unique [concat [dict keys $RAW] [dict keys $P]]]]
    set candidatePins [get_pins -quiet -of_objects $objects]
    set h [open [file join $::m002_report_dir candidate_pins_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tDIRECTION\tREF_PIN_NAME\traw_cell\tconnection_evidence"
    set columns [pin_columns $candidatePins]
    foreach pin [dict get $columns NAME] direction [dict get $columns DIRECTION] terminal [dict get $columns REF_PIN_NAME] {
        puts $h [join [list $pin $direction $terminal [file dirname $pin] CANONICAL_NET_EXPORT_AND_LEAF_ENDPOINTS] \t]
    }
    close $h
    set attached [get_nets -quiet -of_objects $candidatePins]
    clock_domains $point
    set ::slr2::boundaryPins [dict create]
    set timingScope [open [file join $::m002_report_dir candidate_boundary_timing_scope_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $timingScope "canonical_net\tcut_direction\tinside_boundary_pin\tpin_class\tclock_group"
    set visited [dict create]
    set nets [open [file join $::m002_report_dir candidate_nets_${point}.tsv] {WRONLY CREAT EXCL}]
    set segs [open [file join $::m002_report_dir candidate_segments_${point}.tsv] {WRONLY CREAT EXCL}]
    set ends [open [file join $::m002_report_dir candidate_endpoints_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $nets "canonical_net\tsegments\tleaf_pins\ttop_ports\tdrivers\tINOUT_count\tinside_endpoints\toutside_endpoints\tunknown_endpoints\tresolution\tboundary\tclasses\tactual_clocks"
    puts $segs "canonical_net\tsegment"
    puts $ends "canonical_net\tkind\tNAME\tDIRECTION\trole\traw_cell\tREF_NAME\tphysical_parent\tinside_RAW\tinside_S\tinside_P\tLOC\tSLR\tpin_class\tREF_PIN_NAME\tIS_CLOCK\tBEL\tnative_site\tnative_tile\tnative_clock_region\towner_root\tdetail_parent\tnative_clock_group\tunresolved_reason"
    foreach net $attached {
        if {[dict exists $visited $net]} {continue}
        set segments [lsort -unique [get_nets -quiet -segments $net]]
        if {![llength $segments]} {error "No canonical segments for attached net: $net"}
        set canonical [lindex $segments 0]
        foreach segment $segments {dict set visited $segment 1;puts $segs "$canonical\t$segment"}
        set pins [get_pins -quiet -leaf -of_objects $segments]
        set ports [get_ports -quiet -of_objects $segments]
        if {[llength $pins]} {ensure_cells [get_cells -quiet -of_objects $pins]}
        set columns [pin_columns $pins]
        set drivers 0;set inout 0;set inside 0;set outside 0;set unknown 0;set classes [dict create]
        set insideDriver 0;set localTiming [list]
        foreach pin [dict get $columns NAME] direction [dict get $columns DIRECTION] terminal [dict get $columns REF_PIN_NAME] clock [dict get $columns IS_CLOCK] {
            set role UNKNOWN
            if {$direction eq "OUT"} {set role DRIVER;incr drivers} elseif {$direction eq "IN"} {set role LOAD} elseif {$direction eq "INOUT"} {set role INOUT;incr inout} else {incr unknown}
            set raw [file dirname $pin];set parent "";set ref UNKNOWN;set loc ""
            if {[dict exists $cellInfo $raw]} {
                set ref [value $raw REF_NAME]
                lassign [physical $raw $ref] parent pref
                if {$parent ne ""} {
                    set loc [value $parent LOC]
                } else {incr unknown}
            } else {incr unknown}
            set sin [dict exists $S $raw];set pinP [dict exists $P $parent]
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
            if {$pinP} {
                if {$role eq "DRIVER"} {incr insideDriver}
                lappend localTiming [list $pin $cls $clockGroup]
            }
            puts $ends [join [list $canonical LEAF_PIN $pin $direction $role $raw $ref $parent [dict exists $RAW $raw] $sin $pinP $loc [slr $loc] $cls $terminal $clock $bel $site $tile $region [owner $raw] [file dirname $raw] $clockGroup $reason] \t]
        }
        set portNames [list];set portDirections [list]
        if {[llength $ports]} {set portNames [property_values $ports NAME 0 top_port_columns];set portDirections [property_values $ports DIRECTION 0 top_port_columns]}
        foreach port $portNames direction $portDirections {
            set role UNKNOWN
            if {$direction eq "IN"} {set role DRIVER;incr drivers} elseif {$direction eq "OUT"} {set role LOAD} elseif {$direction eq "INOUT"} {set role INOUT;incr inout} else {incr unknown}
            incr outside
            puts $ends [join [list $canonical TOP_PORT $port $direction $role TOP_PORT TOP_PORT TOP_PORT 0 0 0 "" TOP_PORT TOP_PORT "" NOT_APPLICABLE_TOP_PORT UNKNOWN TOP_PORT UNKNOWN UNKNOWN TOP_PORT TOP_PORT [get_clocks -quiet -of_objects $port] ""] \t]
        }
        set resolution [expr {$unknown ? "UNKNOWN_RETAINED" : ($inout ? "INOUT_RETAINED" : ($drivers == 1 ? "SINGLE_DRIVER" : ($drivers == 0 ? "NO_DRIVER" : "MULTIDRIVER_RETAINED")))}]
        set boundary [expr {$inside && $outside ? "CUT" : ($unknown ? "UNRESOLVED" : ($inside ? "INTERNAL" : "RAW_SCOPE_ONLY"))}]
        if {$boundary eq "CUT"} {
            set direction [expr {$resolution ne "SINGLE_DRIVER" ? "UNRESOLVED" : ($insideDriver ? "EGRESS" : "INGRESS")}]
            foreach spec $localTiming {
                lassign $spec pin cls clockGroup
                dict set ::slr2::boundaryPins $direction $pin 1
                puts $timingScope "$canonical\t$direction\t$pin\t$cls\t$clockGroup"
            }
        }
        puts $nets [join [list $canonical [llength $segments] [llength $pins] [llength $ports] $drivers $inout $inside $outside $unknown $resolution $boundary $classes [get_clocks -quiet -of_objects $segments]] \t]
    }
    close $nets;close $segs;close $ends;close $timingScope
    m002_put [file join $::m002_report_dir candidate_cut_${point}_closed.txt] "completed=1\ncoverage=all_candidate_RAW_S_P_attached_canonical_nets\nlogical_group=S_P_excludes_GND_VCC\nleaf_directions=IN_OUT_INOUT_unknown_retained\ntop_ports=included\nclock_reset_constant=included_separately\ncanonical_segments=[dict size $visited]"
    exec python3 $::env(E006_CANDIDATE_ADAPTER) cut $point $::m002_report_dir
    puts "E006_QUERY_COMPLETED complete_candidate_cut_$point canonical_segments=[dict size $visited]"
}
proc slr2::owner name {
    variable base
    foreach root [list ${base}u_compute/u_mlp ${base}u_compute/u_attention ${base}u_tensor scalellm_vcu118_f05_bd_i/ddr4_0 scalellm_vcu118_f05_bd_i/ddr4_1] {
        if {$name eq $root || [prefix $name ${root}/]} {return $root}
    }
    return [join [lrange [split $name /] 0 1] /]
}
proc slr2::spatial loc {
    variable spatialCache
    if {$loc eq ""} {return [list UNPLACED UNKNOWN UNKNOWN]}
    if {[dict exists $spatialCache $loc]} {return [dict get $spatialCache $loc]}
    set sites [get_sites -quiet $loc]
    set tile UNKNOWN;set region UNKNOWN
    if {[llength $sites] == 1 && [get_property NAME $sites] eq $loc} {
        if {![catch {set tiles [get_tiles -quiet -of_objects $sites]}] && [llength $tiles]==1} {set tile [get_property NAME $tiles]}
        if {![catch {set regions [get_clock_regions -quiet -of_objects $sites]}] && [llength $regions]==1} {set region [get_property NAME $regions]}
    } else {set loc UNKNOWN}
    dict set spatialCache $loc [list $loc $tile $region]
    return [dict get $spatialCache $loc]
}
proc slr2::clock_domains point {
    variable domainCache
    set domainCache [dict create]
    set h [open [file join $::m002_report_dir candidate_native_clock_domains_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "clock\tquery_code\tregister_cells\terror"
    foreach clock [get_clocks -quiet] {
        set registers [list]
        set code [catch {set registers [all_registers -clock $clock]} issue]
        puts $h "$clock\t$code\t[llength $registers]\t[string map [list \n { } \t { }] [expr {$code ? $issue : {}}]]"
        if {!$code && [llength $registers]} {
            foreach name [get_property NAME $registers] {dict lappend domainCache $name $clock}
        }
    }
    close $h
}
proc slr2::domains name {
    variable domainCache
    if {[dict exists $domainCache $name]} {return [dict get $domainCache $name]}
    return UNKNOWN_NATIVE_REGISTER_CLOCK_MAPPING
}
proc slr2::scoped_timing point {
    variable boundaryPins
    set h [open [file join $::m002_report_dir candidate_scoped_timing_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "direction\tdelay_type\tmax_paths\tqueried_boundary_pins\treturned_paths\tSTARTPOINT_PIN\tENDPOINT_PIN\tSTARTPOINT_CLOCK\tENDPOINT_CLOCK\tSLACK\tLOGIC_DELAY\tNET_DELAY\tDATAPATH_DELAY\tEXCEPTION"
    foreach direction {INGRESS EGRESS UNRESOLVED} {
        if {![dict exists $boundaryPins $direction]} {continue}
        set pins [dict keys [dict get $boundaryPins $direction]]
        foreach type {max min} {
            set paths [get_timing_paths -quiet -through $pins -delay_type $type -max_paths 16 -nworst 1]
            if {![llength $paths]} {puts $h "$direction\t$type\t16\t[llength $pins]\t0\tNO_PATH";continue}
            report_timing -of_objects $paths -nets -input_pins -file [file join $::m002_report_dir candidate_cut_timing_${point}_${direction}_${type}.rpt]
            foreach path $paths {
                set values [list $direction $type 16 [llength $pins] [llength $paths]]
                set supported [list_property $path]
                foreach property {STARTPOINT_PIN ENDPOINT_PIN STARTPOINT_CLOCK ENDPOINT_CLOCK SLACK LOGIC_DELAY NET_DELAY DATAPATH_DELAY EXCEPTION} {
                    lappend values [expr {$property in $supported ? [m002_prop $path $property] : {UNKNOWN_UNSUPPORTED_PROPERTY}}]
                }
                puts $h [join $values \t]
            }
        }
    };close $h
    m002_put [file join $::m002_report_dir candidate_scoped_timing_${point}_coverage.txt] "diagnostic_only=1\nselection=through_all_reconciled_P_boundary_pins_grouped_ingress_egress_unresolved\nmax_paths_per_direction_and_delay_type=16\nnworst=1\nfull_cut_path_enumeration=false\nfull_cut_TNS=NOT_MEASURED\ncomplete_global_timing_and_constraints=unchanged"
}

proc slr2::readonly_resolve {point root} {
    variable RAW;variable S;variable P;variable mapping;variable handles;variable cellInfo;variable candidateSets
    set RAW [dict create];set S [dict create];set P [dict create];set mapping [dict create]
    set root_object [m002_exact get_cells $root]
    if {[get_property NAME $root_object] ne $root || [get_property IS_PRIMITIVE $root_object]} {error "Expected exact nonprimitive candidate root: $root"}
    # Only the broad safe prefix is a glob. The final selector is a literal
    # starts-with comparison, including array brackets in g_row_branch[1].
    set broad $root
    set bracket [string first {[} $root]
    if {$bracket >= 0} {set broad [string range $root 0 [expr {$bracket-1}]]}
    set broad_cells [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && NAME =~ "%s*"} $broad]]
    set broad_names [property_values $broad_cells NAME 0 readonly_literal_selector]
    set cells [list]
    foreach cell $broad_cells name $broad_names {
        if {[string first ${root}/ $name] == 0} {lappend cells $cell}
    }
    if {![llength $cells]} {error "Exact candidate primitive descendants empty: $point/$root"}
    ensure_cells $cells
    set names [property_values $cells NAME 0 readonly_membership]
    set primitive [property_values $cells IS_PRIMITIVE 0 readonly_membership]
    if {[llength [lsort -unique $names]] != [llength $cells]} {error "Duplicate exact primitive membership: $point"}
    set unresolved [dict create];set mappingRefs [dict create]
    foreach name $names leaf $primitive {
        if {!$leaf || [string first ${root}/ $name] != 0} {error "Literal primitive selector mismatch: $point/$name"}
        set ref [value $name REF_NAME]
        dict set RAW $name $ref
        if {$ref ni {GND VCC}} {dict set S $name $ref}
        lassign [physical $name $ref] parent pref
        dict set mapping $name $parent
        dict set mappingRefs $name $pref
        if {$parent eq ""} {
            dict set unresolved $name UNRESOLVED_NATIVE_DSP_PHYSICAL_PARENT
        } elseif {$parent ne $root && [string first ${root}/ $parent] != 0} {
            dict set unresolved $name PHYSICAL_PARENT_OUTSIDE_EXACT_ROOT
        } elseif {$ref ni {GND VCC}} {dict set P $parent $pref}
    }
    set all [objects [lsort -unique [concat [dict keys $RAW] [dict keys $P]]]]
    ensure_cells $all
    set member_properties {IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH ORIG_CELL_NAME ORIG_REF_NAME}
    set member_names [property_values $all NAME 0 readonly_member_policy]
    set memberPblocks [dict create];set pblockFacts [dict create]
    foreach pb [get_pblocks -quiet -of_objects $all] {
        set props [dict create]
        foreach property [lsort [list_property $pb]] {dict set props $property [m002_prop $pb $property]}
        set pb_objects [get_cells -quiet -of_objects $pb]
        set pb_names [property_values $pb_objects NAME 0 readonly_PBLOCK_members]
        dict set pblockFacts $pb [list properties $props all_native_member_NAMES $pb_names]
        foreach name $pb_names {dict lappend memberPblocks $name $pb}
    }
    m002_put [file join $::m002_report_dir candidate_existing_pblocks_${point}.tcllist] $pblockFacts
    foreach property $member_properties {
        set values [property_values $all $property 1 readonly_member_policy]
        foreach name $member_names value $values {dict set cellInfo $name $property $value}
    }
    set support [open [file join $::m002_report_dir candidate_property_support_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $support "REF_NAME	actual_native_property_names"
    set seen [dict create]
    foreach object $all name $member_names {
        set ref [value $name REF_NAME]
        if {![dict exists $seen $ref]} {dict set seen $ref 1;puts $support "$ref	[list [list_property $object]]"}
    };close $support
    set h [open [file join $::m002_report_dir candidate_membership_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME	REF_NAME	selected_RAW	selected_S	physical_parent	physical_REF	selected_P	LOC	BEL	SLR	native_site	native_tile	native_clock_region	IS_LOC_FIXED	IS_BEL_FIXED	USER_SLR_ASSIGNMENT	RLOC	RLOC_ORIGIN	MACRO_NAME	DONT_TOUCH	ORIG_CELL_NAME	ORIG_REF_NAME	actual_PBLOCKS	mapping_reason"
    foreach name [lsort [dict keys $RAW]] {
        set parent [dict get $mapping $name];set loc [value $name LOC]
        set pref [dict get $mappingRefs $name];lassign [spatial $loc] site tile region
        set row [list $name [dict get $RAW $name] 1 [dict exists $S $name] $parent $pref [dict exists $P $parent] $loc [value $name BEL] [slr $loc] $site $tile $region]
        foreach property $member_properties {lappend row [value $name $property]}
        lappend row [expr {[dict exists $memberPblocks $name] ? [dict get $memberPblocks $name] : {}}]
        lappend row [expr {[dict exists $unresolved $name] ? [dict get $unresolved $name] : {ACTUAL_NATIVE_MAPPING}}]
        puts $h [join $row 	]
    };close $h
    set h [open [file join $::m002_report_dir candidate_physical_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME	REF_NAME	LOC	BEL	SLR	native_site	native_tile	native_clock_region"
    dict for {name ref} $P {
        set loc [value $name LOC];lassign [spatial $loc] site tile region
        puts $h [join [list $name $ref $loc [value $name BEL] [slr $loc] $site $tile $region] 	]
    };close $h
    foreach {tag members} [list RAW $RAW S $S P $P] {
        set h [open [file join $::m002_report_dir candidate_${tag}_${point}.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME	REF_NAME"
        foreach name [lsort [dict keys $members]] {puts $h "$name	[dict get $members $name]"}
        close $h
    }
    m002_put [file join $::m002_report_dir candidate_unresolved_mapping_${point}.tcllist] $unresolved
    dict set candidateSets $point [list RAW $RAW S $S P $P]
    if {[dict size $unresolved]} {error "Actual physical mapping incomplete; all RAW rows retained: $point/[dict size $unresolved]"}
    m002_put [file join $::m002_report_dir candidate_membership_${point}_closed.txt] "completed=1
root=$root
actual_exact_root=[get_property NAME $root_object]
RAW=[dict size $RAW]
S=[dict size $S]
P=[dict size $P]
selection=literal_NAME_starts_with_exact_root_slash
P_semantics=all_nonconstant_actual_members_with_actual_DSP_parent_normalization_no_optimization_policy_acceptance
unknown_REF_policy=retain_native_REF_no_old_input_allowlist
physical_policy_modified=false"
    return $root_object
}
