#!/usr/bin/env python3
"""Extract reviewed pure query procedures; add literal read-only membership."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'slr2_input_locality'


def adapt_queries(body):
    changes = [
        ('    set candidatePins [get_pins -quiet -of_objects $objects]',
         '    set candidatePinsRaw [get_pins -quiet -of_objects $objects]\n    set candidatePins [lsort -unique $candidatePinsRaw]'),
        ('    set attached [get_nets -quiet -of_objects $candidatePins]',
         '    set attachedRaw [get_nets -quiet -of_objects $candidatePins]\n    set attached [lsort -unique $attachedRaw]\n    set attachedAliasSkips 0;set canonicalCount 0'),
        ('        if {[dict exists $visited $net]} {continue}',
         '        if {[dict exists $visited $net]} {incr attachedAliasSkips;continue}\n        incr canonicalCount'),
        ('canonical_segments=[dict size $visited]"',
         'canonical_segments=[dict size $visited]\\ncandidate_pin_raw_records=[llength $candidatePinsRaw]\\ncandidate_pin_unique_records=[llength $candidatePins]\\nattached_raw_records=[llength $attachedRaw]\\nattached_unique_records=[llength $attached]\\nattached_alias_records_skipped=$attachedAliasSkips\\nunique_complete_canonical_nets=$canonicalCount"'),
        ('    puts $h "direction\\tdelay_type\\tmax_paths',
         '    set queries [open [file join $::m002_report_dir candidate_timing_queries_${point}.tcllist] {WRONLY CREAT EXCL}]\n    puts $h "direction\\tdelay_type\\tmax_paths'),
        ('            set paths [get_timing_paths -quiet -through $pins -delay_type $type -max_paths 16 -nworst 1]',
         '            set command [list get_timing_paths -quiet -through $pins -delay_type $type -max_paths 16 -nworst 1]\n            puts $queries [list direction $direction delay_type $type command $command];flush $queries\n            set paths [{*}$command]'),
        ('    };close $h\n    m002_put [file join $::m002_report_dir candidate_scoped_timing_',
         '    };close $h;close $queries\n    m002_put [file join $::m002_report_dir candidate_scoped_timing_'),
    ]
    for old, new in changes:
        assert body.count(old) == (2 if old.startswith('canonical_segments=') else 1), repr(old)
        body = body.replace(old, new, 1)
    return body


def main():
    helper = HERE / 'candidate_inspector.tcl'
    assert not helper.exists(), 'Never overwrite a prepared inspector'
    names = ['prefix', 'slr', 'physical', 'ensure_cells', 'property_values', 'value',
             'pin_columns', 'objects', 'pin_class', 'timing_boundary_selection', 'cut', 'owner', 'spatial',
             'clock_domains', 'domains', 'scoped_timing']
    stub = 'proc m002_live_pre_place_restore {} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    stub += 'proc m002_post {point} {exec python3 [file join $::m002_script_dir m002_physical_evidence.py]}\n'
    script = stub + 'source {' + str(SOURCE / 'candidate_hooks.tcl') + '}\n'
    script += 'foreach name {' + ' '.join(names) + '} {puts [list proc slr2::$name [info args slr2::$name] [info body slr2::$name]]}\n'
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True, check=True)
    body = result.stdout
    old = 'foreach property {REF_NAME LOC BEL IS_LOC_FIXED IS_BEL_FIXED ORIG_CELL_NAME ORIG_REF_NAME RLOC RLOC_ORIGIN MACRO_NAME DONT_TOUCH USER_SLR_ASSIGNMENT}'
    assert body.count(old) == 1
    body = body.replace(old, 'foreach property {REF_NAME LOC BEL}', 1)
    old = 'exec python3 $::env(SLR2_ADAPTER) cut $point $::m002_report_dir'
    assert body.count(old) == 1
    body = body.replace(old, 'exec python3 $::env(E006_CANDIDATE_ADAPTER) cut $point $::m002_report_dir', 1)
    body = body.replace('E007_QUERY_COMPLETED complete_candidate_cut_', 'E006_QUERY_COMPLETED complete_candidate_cut_')
    body = adapt_queries(body)
    prefix = '''# Derived pure query procedures only. No source-time native queries or physical policy writes.
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
'''
    resolve = r'''
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
    puts $h "NAME	REF_NAME	LOC	BEL	SLR	native_site	native_tile	native_clock_region	IS_LOC_FIXED	IS_BEL_FIXED	USER_SLR_ASSIGNMENT	RLOC	RLOC_ORIGIN	MACRO_NAME	DONT_TOUCH	ORIG_CELL_NAME	ORIG_REF_NAME	actual_PBLOCKS"
    dict for {name ref} $P {
        set loc [value $name LOC];lassign [spatial $loc] site tile region
        set row [list $name $ref $loc [value $name BEL] [slr $loc] $site $tile $region]
        foreach property $member_properties {lappend row [value $name $property]}
        lappend row [expr {[dict exists $memberPblocks $name] ? [dict get $memberPblocks $name] : {}}]
        puts $h [join $row 	]
    };close $h
    set locs [list]
    dict for {name ref} $P {set loc [value $name LOC];if {$loc ne ""} {lappend locs $loc}}
    set siteCells [list]
    if {[llength $locs]} {set siteCells [get_cells -quiet -of_objects [get_sites -quiet [lsort -unique $locs]] -filter {IS_PRIMITIVE == 1}]}
    ensure_cells $siteCells
    set h [open [file join $::m002_report_dir candidate_site_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME	REF_NAME	LOC	BEL	SLR	selected_RAW	selected_S	physical_parent	selected_P	owner_root	mapping_reason"
    foreach name [property_values $siteCells NAME 0 readonly_touched_site_members] {
        set ref [value $name REF_NAME];set loc [value $name LOC]
        lassign [physical $name $ref] parent pref
        set reason [expr {$parent eq "" ? "UNRESOLVED_NATIVE_PHYSICAL_PARENT" : "ACTUAL_NATIVE_MAPPING"}]
        puts $h [join [list $name $ref $loc [value $name BEL] [slr $loc] [dict exists $RAW $name] [dict exists $S $name] $parent [dict exists $P $parent] [owner $name] $reason] 	]
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
'''
    helper.write_text(prefix + body + resolve)
    shutil.copy2(SOURCE / 'property_alignment.tcl', HERE / 'property_alignment.tcl')
    def identity(path):
        return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    receipt = dict(EDA_executed=False, source_time_native_queries=False,
                   derived_pure_procedures=names,
                   source_files=[identity(SOURCE / name) for name in ['candidate_hooks.tcl', 'runtime_hooks.tcl', 'property_alignment.tcl']],
                   generated_inspector=identity(helper),
                   adaptations=['Query-only namespace and exact read helpers; no constrain/placement/Pblock mutation procedures',
                                'Generic cache limits external endpoints to REF/LOC/BEL; full optional policy is read only for selected member/physical objects',
                                'Cut CPU adapter redirects to independent R004 validator; actual IS_CLOCK retained in endpoint rows',
                                'Literal exact-root descendant membership; no old input/DSP/index/REF allowlist assumptions'])
    with (HERE / 'candidate_inspector_derivation.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(inspector=identity(helper), EDA_executed=False)))


if __name__ == '__main__':
    main()
