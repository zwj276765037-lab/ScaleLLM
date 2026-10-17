# Agent-owned exact-hotspot SLR2 hooks. Sourced only by a new isolated run.
# No E006 process control. API/range/membership assertions are runtime gates.
source [file join [file dirname [file normalize [info script]]] property_alignment.tcl]
namespace eval slr2 {
    variable base scalellm_vcu118_f05_bd_i/core/inst/u_core/
    variable root $::env(SLR2_CANDIDATE_ROOT)
    variable candidateID $::env(SLR2_CANDIDATE_ID)
    variable pblock m002_exact_hotspot_SLR2
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
    variable root
    return [expr {[prefix $name ${root}/] ? "EXACT_HOTSPOT_SELECTED" : "OUTSIDE_SELECTOR"}]
}
proc slr2::selected {name} {expr {[group $name] eq "EXACT_HOTSPOT_SELECTED"}}
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
    # Ledger inclusion only. Actual migration admissibility is a separate gate.
    return [expr {$ref ni {GND VCC}}]
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
    variable RAW;variable S;variable P;variable mapping;variable handles;variable physicalCache;variable cellInfo;variable cellPblocks;variable root
    set RAW [dict create];set S [dict create];set P [dict create];set mapping [dict create]
    set handles [dict create];set physicalCache [dict create];set cellInfo [dict create];set cellPblocks [dict create]
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
        puts $h [join $row "\t"]
    };close $h
    set h [open [file join $::m002_report_dir candidate_physical_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME	REF_NAME	LOC	BEL	SLR	native_site	native_tile	native_clock_region	IS_LOC_FIXED	IS_BEL_FIXED	USER_SLR_ASSIGNMENT	RLOC	RLOC_ORIGIN	MACRO_NAME	DONT_TOUCH	ORIG_CELL_NAME	ORIG_REF_NAME	actual_PBLOCKS"
    dict for {name ref} $P {
        set loc [value $name LOC];lassign [spatial $loc] site tile region
        set row [list $name $ref $loc [value $name BEL] [slr $loc] $site $tile $region]
        foreach property $member_properties {lappend row [value $name $property]}
        lappend row [expr {[dict exists $memberPblocks $name] ? [dict get $memberPblocks $name] : {}}]
        puts $h [join $row "\t"]
    };close $h
    set locs [list]
    dict for {name ref} $P {set loc [value $name LOC];if {$loc ne ""} {lappend locs $loc}}
    set siteCells [list]
    if {[llength $locs]} {set siteCells [get_cells -quiet -of_objects [get_sites -quiet [lsort -unique $locs]] -filter {IS_PRIMITIVE == 1}]}
    ensure_cells $siteCells
    set h [open [file join $::m002_report_dir candidate_literal_site_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME	REF_NAME	LOC	BEL	SLR	selected_RAW	selected_S	physical_parent	selected_P	owner_root	mapping_reason"
    foreach name [property_values $siteCells NAME 0 readonly_touched_site_members] {
        set ref [value $name REF_NAME];set loc [value $name LOC]
        lassign [physical $name $ref] parent pref
        set reason [expr {$parent eq "" ? "UNRESOLVED_NATIVE_PHYSICAL_PARENT" : "ACTUAL_NATIVE_MAPPING"}]
        puts $h [join [list $name $ref $loc [value $name BEL] [slr $loc] [dict exists $RAW $name] [dict exists $S $name] $parent [dict exists $P $parent] [owner $name] $reason] "\t"]
    };close $h
    foreach {tag members} [list RAW $RAW S $S P $P] {
        set h [open [file join $::m002_report_dir candidate_${tag}_${point}.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME	REF_NAME"
        foreach name [lsort [dict keys $members]] {puts $h "$name	[dict get $members $name]"}
        close $h
    }
    m002_put [file join $::m002_report_dir candidate_unresolved_mapping_${point}.tcllist] $unresolved
    set cellPblocks $memberPblocks
    set h [open [file join $::m002_report_dir candidate_physical_mapping_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "raw_NAME\tphysical_NAME"
    dict for {name parent} $mapping {puts $h "$name\t$parent"};close $h
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
    report_utilization -cells $root_object -slr -file [file join $::m002_report_dir utilization_candidate_${point}_SLR.rpt]
    exec python3 $::env(SLR2_ADAPTER) membership $point $::m002_report_dir
    return $root_object
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
    puts "E008_QUERY_COMPLETED hard_SLR2_pblock members=[dict size $P]"
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
proc slr2::timing_boundary_selection {resolution insideDriver insideLoads outsideLoads unresolvedPins} {
    if {$resolution ne "SINGLE_DRIVER"} {return [list UNRESOLVED $unresolvedPins UNRESOLVED_INSIDE_BOUNDARY_PINS]}
    if {$insideDriver} {return [list EGRESS $outsideLoads EGRESS_OUTSIDE_LOAD_ONLY]}
    return [list INGRESS $insideLoads INGRESS_INSIDE_LOAD_ONLY]
}
# Shared coverage_version=candidate_directed_cut_v1 collector is sourced below.
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
    puts "E008_STAGE_COMPLETED locality_$point"
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

source [file join [file dirname [file normalize [info script]]] directed_exporter.tcl]
