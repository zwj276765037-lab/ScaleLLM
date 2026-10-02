# Final read-only, sample-only property probe for Run 0138 ordinary
# primitives whose direct SLR_INDEX is empty.  It records raw Vivado object
# relationships; it does not infer or accept a global wrong-SLR result.

set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set dcp [file normalize [file join $root vivado reports \
    production_v5_place_20260817_223533 post_place.dcp]]
set selector_lib [file join $script_dir v5_production_floorplan_selectors.tcl]
set out [file normalize $::env(HAP_SLR_PROBE_DIR)]
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
foreach path [list $dcp $selector_lib] {
    if {![file exists $path] || ![file isfile $path] ||
        [file size $path] == 0} {
        error "Missing probe input: $path"
    }
}
source $selector_lib
open_checkpoint $dcp

proc hap_probe_safe_property {property objects} {
    if {[llength $objects] == 0} {return ""}
    return [get_property $property $objects]
}

proc hap_probe_slr_detail {sites} {
    set records {}
    foreach site $sites {
        set slrs [get_slrs -quiet -of_objects $site]
        set slr_names {}
        set slr_indices {}
        foreach slr $slrs {
            lappend slr_names [get_property NAME $slr]
            lappend slr_indices [get_property SLR_INDEX $slr]
        }
        lappend records [dict create \
            site [get_property NAME $site] \
            site_slr_index [get_property SLR_INDEX $site] \
            slr_count [llength $slrs] slr_names $slr_names \
            slr_indices $slr_indices]
    }
    return $records
}

set roots [hap_v5_floorplan::module_cells \
    hap_mlp_shared_local_slice8x12_s44_s46]
hap_v5_floorplan::require_count v5_probe_branches $roots 2
set branch0 [lindex $roots 0]
set primitives [hap_v5_floorplan::primitive_descendants $branch0]
set invalid_by_ref [dict create]
set invalid_count 0
foreach cell $primitives {
    set direct [get_property SLR_INDEX $cell]
    if {[string is integer -strict $direct] &&
        $direct >= 0 && $direct <= 2} {
        continue
    }
    incr invalid_count
    set ref [get_property REF_NAME $cell]
    dict lappend invalid_by_ref $ref $cell
}
if {$invalid_count == 0 || [dict size $invalid_by_ref] == 0} {
    error "Sample probe found no direct-SLR-invalid ordinary primitives"
}

# Stratified deterministic sample: at least one cell from every REF_NAME,
# then round-robin additional cells up to 48.
set refs [lsort -dictionary [dict keys $invalid_by_ref]]
if {[llength $refs] > 48} {
    error "Cannot sample every invalid REF_NAME within 48 rows: refs=[llength $refs]"
}
set sample_cells {}
set offsets [dict create]
foreach ref $refs {
    set values [lsort -dictionary [dict get $invalid_by_ref $ref]]
    lappend sample_cells [lindex $values 0]
    dict set invalid_by_ref $ref $values
    dict set offsets $ref 1
}
set progress 1
while {[llength $sample_cells] < 48 && $progress} {
    set progress 0
    foreach ref $refs {
        if {[llength $sample_cells] >= 48} {break}
        set offset [dict get $offsets $ref]
        set values [dict get $invalid_by_ref $ref]
        if {$offset < [llength $values]} {
            lappend sample_cells [lindex $values $offset]
            dict incr offsets $ref
            set progress 1
        }
    }
}

set samples {}
set cell_site_nonempty 0
set loc_site_nonempty 0
set cell_bel_nonempty 0
set bel_site_nonempty 0
set any_site_nonempty 0
set any_unique_site_slr 0
foreach cell $sample_cells {
    set name [get_property NAME $cell]
    set ref [get_property REF_NAME $cell]
    set primitive [get_property IS_PRIMITIVE $cell]
    set direct_slr [get_property SLR_INDEX $cell]
    set direct_placed [get_property IS_PLACED $cell]
    set loc [get_property LOC $cell]
    set bel_property [get_property BEL $cell]

    set cell_sites [get_sites -quiet -of_objects $cell]
    if {[llength $cell_sites] != 0} {incr cell_site_nonempty}
    set loc_sites {}
    if {$loc ne ""} {set loc_sites [get_sites -quiet $loc]}
    if {[llength $loc_sites] != 0} {incr loc_site_nonempty}
    set cell_bels [get_bels -quiet -of_objects $cell]
    if {[llength $cell_bels] != 0} {incr cell_bel_nonempty}
    set bel_sites {}
    if {[llength $cell_bels] != 0} {
        set bel_sites [get_sites -quiet -of_objects $cell_bels]
    } elseif {$bel_property ne ""} {
        set property_bels [get_bels -quiet $bel_property]
        if {[llength $property_bels] != 0} {
            set bel_sites [get_sites -quiet -of_objects $property_bels]
        }
    }
    if {[llength $bel_sites] != 0} {incr bel_site_nonempty}

    set all_sites [lsort -dictionary -unique \
        [concat $cell_sites $loc_sites $bel_sites]]
    if {[llength $all_sites] != 0} {incr any_site_nonempty}
    set all_site_details [hap_probe_slr_detail $all_sites]
    set resolved_slrs {}
    foreach record $all_site_details {
        set resolved_slrs [concat $resolved_slrs \
            [dict get $record slr_names]]
    }
    set resolved_slrs [lsort -dictionary -unique $resolved_slrs]
    if {[llength $all_sites] == 1 && [llength $resolved_slrs] == 1} {
        incr any_unique_site_slr
    }

    lappend samples [dict create name $name ref $ref \
        is_primitive $primitive direct_slr_index $direct_slr \
        direct_is_placed $direct_placed loc $loc bel_property $bel_property \
        cell_site_count [llength $cell_sites] \
        cell_sites [hap_probe_safe_property NAME $cell_sites] \
        loc_site_count [llength $loc_sites] \
        loc_sites [hap_probe_safe_property NAME $loc_sites] \
        cell_bel_count [llength $cell_bels] \
        cell_bels [hap_probe_safe_property NAME $cell_bels] \
        bel_site_count [llength $bel_sites] \
        bel_sites [hap_probe_safe_property NAME $bel_sites] \
        all_site_count [llength $all_sites] \
        all_site_details $all_site_details resolved_slrs $resolved_slrs]
}

set fp [open [file join $out samples.txt] w]
set index 0
foreach sample $samples {
    puts $fp "sample=$index"
    foreach key {name ref is_primitive direct_slr_index direct_is_placed
        loc bel_property cell_site_count cell_sites loc_site_count loc_sites
        cell_bel_count cell_bels bel_site_count bel_sites all_site_count
        all_site_details resolved_slrs} {
        puts $fp "${key}=[dict get $sample $key]"
    }
    incr index
}
close $fp

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
    evidence_class V5_POST_PLACE_READ_ONLY_SLR_SAMPLE_PROBE \
    input_dcp $dcp branch0 $branch0 \
    branch0_primitives [llength $primitives] \
    direct_slr_invalid $invalid_count invalid_ref_classes [llength $refs] \
    samples [llength $samples] ref_classes_sampled [llength $refs] \
    sample_cell_site_nonempty $cell_site_nonempty \
    sample_loc_site_nonempty $loc_site_nonempty \
    sample_cell_bel_nonempty $cell_bel_nonempty \
    sample_bel_site_nonempty $bel_site_nonempty \
    sample_any_site_nonempty $any_site_nonempty \
    sample_any_unique_site_slr $any_unique_site_slr \
    global_physical_conclusion 0 checkpoint_written 0 \
    implementation_commands_run 0 \
    status V5_POST_PLACE_SLR_SAMPLE_PROBE_COMPLETE] {
    puts $fp "$key=$value"
}
foreach ref $refs {
    puts $fp "invalid_ref_${ref}=[llength [dict get $invalid_by_ref $ref]]"
}
close $fp

puts "V5_POST_PLACE_SLR_SAMPLE_PROBE INVALID=$invalid_count REFS=[llength $refs] SAMPLES=[llength $samples] CELL_SITE=$cell_site_nonempty LOC_SITE=$loc_site_nonempty CELL_BEL=$cell_bel_nonempty BEL_SITE=$bel_site_nonempty ANY_SITE=$any_site_nonempty UNIQUE_SITE_SLR=$any_unique_site_slr STATUS=COMPLETE"
close_design
