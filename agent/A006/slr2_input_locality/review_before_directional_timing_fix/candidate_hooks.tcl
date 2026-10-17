# Agent-owned SLR2 input-locality hooks. Sourced only by a new isolated run.
# No E006 process control. API/range/membership assertions are runtime gates.
source [file join [file dirname [file normalize [info script]]] property_alignment.tcl]
namespace eval slr2 {
    variable base scalellm_vcu118_f05_bd_i/core/inst/u_core/
    variable front ${base}u_compute/u_mlp/u_input_frontend/
    variable tensor ${base}u_tensor/
    variable pblock m002_input_locality_SLR2
    variable originalP [dict create]
    variable siteSLR [dict create]
    variable S [dict create]
    variable RAW [dict create]
    variable P [dict create]
    variable mapping [dict create]
    variable handles [dict create]
    variable physicalCache [dict create]
    variable cellInfo [dict create]
    variable cellPblocks [dict create]
}
proc slr2::prefix {name value} {expr {[string first $value $name] == 0}}
proc slr2::group {name} {
    variable front; variable tensor
    if {[prefix $name $front]} {
        set tail [string range $name [string length $front] end]
        foreach item {u_cache0/ u_cache1/ bundle_u8_bank_r bundle_meta_bank_r {g_bundle_row[}} {
            if {[prefix $tail $item]} {return EXCLUDED_FRONTEND}
        }
        return FRONTEND_SELECTED
    }
    if {[prefix $name $tensor]} {
        set tail [string range $name [string length $tensor] end]
        foreach item {{g_input_beat_bank[} input_beat_r input_group_r input_group_valid_r input_beat_count input_group_count} {
            if {[prefix $tail $item]} {return TENSOR_SELECTED}
        }
        return EXCLUDED_TENSOR
    }
    return OUTSIDE_SELECTOR
}
proc slr2::selected {name} {expr {[group $name] in {FRONTEND_SELECTED TENSOR_SELECTED}}}
proc slr2::topology {} {
    variable siteSLR
    set siteSLR [dict create]
    foreach slr [get_slrs -quiet] {
        foreach site [get_sites -quiet -of_objects $slr] {dict set siteSLR [get_property NAME $site] [get_property NAME $slr]}
    }
    if {![dict size $siteSLR]} {error "Empty device SLR/site map"}
}
proc slr2::slr {loc} {
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
proc slr2::bindable {ref} {
    if {$ref in {GND VCC}} {return 0}
    if {$ref ni {LUT1 LUT2 LUT3 LUT4 LUT5 LUT6 FDRE FDCE FDPE CARRY8 MUXF7 MUXF8 DSP48E2}} {error "Unexpected selected physical REF: $ref"}
    return 1
}
proc slr2::property_values {objects property allow_empty context} {
    return [propertyalign::values $objects $property $allow_empty $context [file join $::m002_report_dir candidate_property_alignment.tsv]]
}
proc slr2::ensure_cells {cells} {
    variable cellInfo;variable handles
    set missing [list]
    foreach cell $cells {if {![dict exists $cellInfo $cell]} {lappend missing $cell}}
    for {set i 0} {$i < [llength $missing]} {incr i 16384} {
        set batch [lrange $missing $i [expr {$i+16383}]]
        set names [property_values $batch NAME 0 cell_cache]
        set columns [dict create]
        foreach property {REF_NAME LOC BEL IS_LOC_FIXED IS_BEL_FIXED ORIG_CELL_NAME ORIG_REF_NAME RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH USER_SLR_ASSIGNMENT} {
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
proc slr2::value {name property} {
    variable cellInfo
    if {![dict exists $cellInfo $name $property]} {ensure_cells [objects [list $name]]}
    return [dict get $cellInfo $name $property]
}
proc slr2::pin_columns {pins} {
    set result [dict create]
    if {![llength $pins]} {foreach property {NAME DIRECTION REF_PIN_NAME IS_CLOCK} {dict set result $property [list]};return $result}
    foreach property {NAME DIRECTION REF_PIN_NAME IS_CLOCK} {
        set values [property_values $pins $property [expr {$property eq "IS_CLOCK"}] pin_columns]
        dict set result $property $values
    }
    return $result
}
proc slr2::resolve {point} {
    variable front; variable tensor; variable RAW;variable S; variable P; variable mapping;variable handles;variable physicalCache;variable cellInfo;variable cellPblocks
    set RAW [dict create];set S [dict create]; set P [dict create]; set mapping [dict create]
    set handles [dict create];set physicalCache [dict create]
    set cellInfo [dict create];set cellPblocks [dict create]
    foreach root [list [string trimright $front /] [string trimright $tensor /]] {
        set object [m002_exact get_cells $root]
        if {[llength $object] != 1 || [get_property NAME $object] ne $root} {error "Missing exact selector root: $root"}
    }
    set cells [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && (NAME =~ "%s*" || NAME =~ "%s*")} $front $tensor]]
    ensure_cells $cells
    foreach pb [get_pblocks -quiet -of_objects $cells] {
        foreach name [get_property NAME [get_cells -quiet -of_objects $pb]] {dict lappend cellPblocks $name $pb}
    }
    set out [open [file join $::m002_report_dir candidate_membership_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $out "NAME\tREF_NAME\tgroup\tselected_RAW\tselected_S\tphysical_parent\tphysical_REF\tbindable_P\tLOC\tBEL\tSLR\tIS_LOC_FIXED\tIS_BEL_FIXED\tPBLOCKS\tORIG_CELL_NAME\tORIG_REF_NAME"
    foreach cell $cells name [get_property NAME $cells] ref [get_property REF_NAME $cells] {
        dict set handles $name $cell
        set selected [selected $name];set semantic [expr {$selected && $ref ni {GND VCC}}]; set parent ""; set pref ""; set bind 0
        if {$selected} {
            if {[prefix $ref DSP] && $ref ni {DSP48E2 DSP_ALU DSP_A_B_DATA DSP_C_DATA DSP_MULTIPLIER DSP_M_DATA DSP_OUTPUT DSP_PREADD_DATA DSP_PREADD}} {error "Unexpected selected raw DSP REF: $ref"}
            dict set RAW $name $ref
            if {$semantic} {dict set S $name $ref}
            lassign [physical $name $ref] parent pref
            if {$parent eq ""} {error "Unresolved physical parent: $name $ref"}
            if {[prefix $ref DSP] && (![prefix $parent ${front}u_hadamard/] || $pref ne "DSP48E2")} {error "Selected DSP outside intended Hadamard: $name -> $parent $pref"}
            set bind [bindable $pref]
            dict set mapping $name $parent
            if {$bind} {dict set P $parent $pref}
        }
        set loc [value $name LOC];set prior [list]
        if {[dict exists $cellPblocks $name]} {set prior [dict get $cellPblocks $name]}
        puts $out [join [list $name $ref [group $name] $selected $semantic $parent $pref $bind $loc [value $name BEL] [slr $loc] [value $name IS_LOC_FIXED] [value $name IS_BEL_FIXED] $prior [value $name ORIG_CELL_NAME] [value $name ORIG_REF_NAME]] \t]
    }
    close $out
    foreach {tag members} [list RAW $RAW S $S P $P] {
        set h [open [file join $::m002_report_dir candidate_${tag}_${point}.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME\tREF_NAME"
        foreach name [lsort [dict keys $members]] {puts $h "$name\t[dict get $members $name]"}
        close $h
    }
    set h [open [file join $::m002_report_dir candidate_physical_mapping_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "raw_NAME\tphysical_NAME"
    dict for {name parent} $mapping {puts $h "$name\t$parent"}; close $h
    if {![dict size $S] || ![dict size $P]} {error "Empty semantic/placeable candidate"}
    exec python3 $::env(SLR2_ADAPTER) membership $point $::m002_report_dir
    puts "E007_QUERY_COMPLETED selector_$point RAW=[dict size $RAW] S=[dict size $S] P=[dict size $P]"
}
proc slr2::objects {names} {
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
proc slr2::region_token {name} {
    if {![regexp {^(?:CLOCKREGION_)?(X[0-9]+Y[0-9]+)$} $name -> coordinate]} {error "Unexpected actual clock region: $name"}
    return CLOCKREGION_$coordinate
}
proc slr2::constrain {} {
    variable P; variable originalP; variable pblock; variable siteSLR;variable cellPblocks
    set originalP $P
    set target [get_slrs -quiet -filter {NAME == SLR2}]
    if {[llength $target] != 1 || [get_property NAME $target] ne "SLR2"} {error "Actual SLR2 unavailable/ambiguous"}
    set regions [lsort [get_clock_regions -quiet -of_objects $target]]
    if {![llength $regions]} {error "No actual SLR2 clock regions"}
    if {[llength [get_pblocks -quiet $pblock]]} {error "Candidate Pblock already exists; do not modify existing constraints"}
    set objects [objects [dict keys $P]]
    set h [open [file join $::m002_report_dir candidate_existing_constraints.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tLOC\tIS_LOC_FIXED\tIS_BEL_FIXED\tPBLOCK\tGRID_RANGES\tSLR2_intersection_sites\tRLOC\tRLOC_ORIGIN\tMACRO_NAME\tDONT_TOUCH"
    set conflicts [list]
    set priorInfo [dict create]
    dict for {name pbs} $cellPblocks {
        foreach pb $pbs {
            if {[dict exists $priorInfo $pb]} {continue}
            set intersection 0
            foreach site [get_sites -quiet -of_objects $pb] {if {[slr [get_property NAME $site]] eq "SLR2"} {incr intersection}}
            dict set priorInfo $pb [list [m002_prop $pb GRID_RANGES] [m002_prop $pb IS_SOFT] $intersection]
        }
    }
    foreach cell $objects {
        set loc [value $cell LOC]
        if {$loc ne "" && [slr $loc] ne "SLR2"} {lappend conflicts [list EXISTING_LOC $cell $loc [slr $loc]]}
        set prior [list];if {[dict exists $cellPblocks $cell]} {set prior [dict get $cellPblocks $cell]}
        set macro [list [value $cell RLOC] [value $cell RLOC_ORIGIN] [value $cell MACRO_NAME] [value $cell DONT_TOUCH]]
        if {![llength $prior]} {puts $h "$cell\t$loc\t[value $cell IS_LOC_FIXED]\t[value $cell IS_BEL_FIXED]\tNONE\t\t\t[join $macro \t]"}
        foreach pb $prior {
            lassign [dict get $priorInfo $pb] ranges soft intersection
            puts $h "$cell\t$loc\t[value $cell IS_LOC_FIXED]\t[value $cell IS_BEL_FIXED]\t$pb\t$ranges\t$intersection\t[join $macro \t]"
            if {$intersection == 0 && $soft in {0 false FALSE}} {lappend conflicts [list DISJOINT_HARD_PBLOCK $cell $pb]}
        }
    }
    close $h
    m002_put [file join $::m002_report_dir candidate_constraint_conflicts.txt] $conflicts
    if {[llength $conflicts]} {error "Existing candidate constraints conflict; no constraints cleared"}
    set pb [create_pblock $pblock]
    set h [open [file join $::m002_report_dir candidate_actual_SLR2_ranges.tsv] {WRONLY CREAT EXCL}]
    puts $h "source_SLR\tactual_clock_region\tadded_range"
    foreach region $regions {
        set name [get_property NAME $region]
        set token [region_token $name]
        resize_pblock $pb -add ${token}:${token}
        puts $h "SLR2\t$name\t${token}:${token}"
    }
    close $h
    set_property IS_SOFT false $pb
    set_property EXCLUDE_PLACEMENT false $pb
    set_property CONTAIN_ROUTING false $pb
    add_cells_to_pblock $pb $objects
    set actual [lsort [get_property NAME [get_cells -quiet -of_objects $pb]]]
    if {$actual ne [lsort [dict keys $P]]} {error "Pblock cell readback differs from normalized P"}
    set seen [dict create]
    foreach site [get_sites -quiet -of_objects $pb] {
        set name [get_property NAME $site]
        if {[slr $name] ne "SLR2"} {error "Pblock range extends outside actual SLR2: $name"}
        dict set seen $name 1
    }
    # Full clock-region SLR coverage is checked against actual candidate resource sites.
    dict for {name slr} $siteSLR {
        if {$slr eq "SLR2" && [regexp {^(SLICE|DSP48E2|RAMB18|RAMB36|URAM288)_} $name] && ![dict exists $seen $name]} {error "SLR2 resource site absent from Pblock: $name"}
    }
    set h [open [file join $::m002_report_dir candidate_pblock_readback.txt] {WRONLY CREAT EXCL}]
    foreach property {NAME GRID_RANGES IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {puts $h "$property=[m002_prop $pb $property]"}
    puts $h "placeable_members=[dict size $P]\nactual_site_count=[dict size $seen]";close $h
    foreach property {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {if {[m002_prop $pb $property] ni {0 false FALSE}} {error "Pblock policy readback failed: $property"}}
    write_xdc -constraints physical [file join $::m002_report_dir candidate_effective_physical.xdc]
    puts "E007_QUERY_COMPLETED hard_SLR2_pblock members=[dict size $P]"
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
proc slr2::cut {point} {
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
    exec python3 $::env(SLR2_ADAPTER) cut $point $::m002_report_dir
    puts "E007_QUERY_COMPLETED complete_candidate_cut_$point canonical_segments=[dict size $visited]"
}
proc slr2::phase {point} {
    variable P;variable originalP
    resolve $point
    set h [open [file join $::m002_report_dir candidate_compliance_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tlineage\tLOC\tSLR\tSLR2_compliant\tORIG_CELL_NAME\tORIG_REF_NAME"
    dict for {name ref} $P {
        set cell [objects [list $name]];set loc [value $name LOC]
        set ancestry [expr {[dict exists $originalP $name] ? "ORIGINAL_SURVIVING" : "NEW_SELECTED_LINEAGE_UNPROVEN"}]
        puts $h "$name\t$ref\t$ancestry\t$loc\t[slr $loc]\t[expr {[slr $loc] eq {SLR2}}]\t[value $name ORIG_CELL_NAME]\t[value $name ORIG_REF_NAME]"
    }
    dict for {name ref} $originalP {if {![dict exists $P $name]} {puts $h "$name\t$ref\tORIGINAL_MISSING\t\tUNKNOWN\t0\t\t"}}
    close $h
    set all [open [file join $::m002_report_dir candidate_pblock_actual_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $all "NAME\tREF_NAME\tLOC\tSLR\tselector_P\tORIG_CELL_NAME\tORIG_REF_NAME"
    set actualPB [get_cells -quiet -of_objects [get_pblocks $::slr2::pblock]]
    ensure_cells $actualPB
    foreach name [get_property NAME $actualPB] {
        set loc [value $name LOC]
        puts $all "$name\t[value $name REF_NAME]\t$loc\t[slr $loc]\t[dict exists $P $name]\t[value $name ORIG_CELL_NAME]\t[value $name ORIG_REF_NAME]"
    }
    close $all
    set h [open [file join $::m002_report_dir candidate_site_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tLOC\tBEL\tSLR\tselected_P"
    set locs [list]
    foreach name [dict keys $P] {set loc [value $name LOC];if {$loc ne ""} {lappend locs $loc}}
    if {[llength $locs]} {
        set atSites [get_cells -quiet -of_objects [get_sites -quiet [lsort -unique $locs]] -filter {IS_PRIMITIVE == 1}]
        ensure_cells $atSites
        foreach name [get_property NAME $atSites] {
            set loc [value $name LOC]
            puts $h "$name\t[value $name REF_NAME]\t$loc\t[value $name BEL]\t[slr $loc]\t[dict exists $P $name]"
        }
    }
    close $h
    cut $point
    exec python3 $::env(SLR2_ADAPTER) compliance $point $::m002_report_dir
    puts "E007_STAGE_COMPLETED locality_$point"
}
proc slr2::post_phase {point} {
    # Preserve the original POST error while still closing available locality evidence.
    set started [clock seconds]
    set post_code [catch {m002_post $point} post_result post_options]
    set locality_code [catch {phase $point} locality_result locality_options]
    m002_put [file join $::m002_report_dir candidate_phase_${point}_receipt.tcllist] [list post_code $post_code post_result $post_result post_options $post_options locality_code $locality_code locality_result $locality_result locality_options $locality_options]
    m002_put [file join $::m002_report_dir candidate_phase_${point}_status.txt] "post_code=$post_code\nlocality_code=$locality_code\nstarted_epoch=$started\nended_epoch=[clock seconds]"
    if {$post_code} {return -options $post_options $post_result}
    if {$locality_code} {return -options $locality_options $locality_result}
}

# Reuse existing native probes, changing only their isolated evidence adapter.
foreach name {m002_live_pre_place_restore m002_post} {
    set body [info body $name]
    set needle {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}
    if {[string first $needle $body] < 0} {error "Reused diagnostic hook changed: $name"}
    proc $name [info args $name] [string map [list $needle {exec python3 $::env(SLR2_ADAPTER)}] $body]
}
source [file join [file dirname [file normalize [info script]]] runtime_hooks.tcl]
