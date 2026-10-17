# Runtime checks required by the concentrated A007 review. No EDA at source time.
namespace eval slr2 {
    variable spatialCache [dict create]
    variable domainCache [dict create]
    variable boundaryPins [dict create]
}
proc slr2::owner {name} {
    variable base
    foreach root [list ${base}u_compute/u_mlp ${base}u_compute/u_attention ${base}u_tensor scalellm_vcu118_f05_bd_i/ddr4_0 scalellm_vcu118_f05_bd_i/ddr4_1] {
        if {$name eq $root || [prefix $name ${root}/]} {return $root}
    }
    return [join [lrange [split $name /] 0 1] /]
}
proc slr2::spatial {loc} {
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
proc slr2::clock_domains {point} {
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
proc slr2::domains {name} {
    variable domainCache
    if {[dict exists $domainCache $name]} {return [dict get $domainCache $name]}
    return UNKNOWN_NATIVE_REGISTER_CLOCK_MAPPING
}
proc slr2::pblock_snapshot {} {
    set result [dict create]
    foreach pb [get_pblocks -quiet] {
        set properties [dict create]
        foreach property [lsort [list_property $pb]] {dict set properties $property [m002_prop $pb $property]}
        set cells [get_cells -quiet -of_objects $pb]
        set names [list];if {[llength $cells]} {set names [lsort [get_property NAME $cells]]}
        dict set result $pb [list $properties $names]
    }
    return $result
}
proc slr2::placement_policy {point objects} {
    set required {IS_PRIMITIVE LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC RLOC_ORIGIN}
    set seen [dict create]
    set support [open [file join $::m002_report_dir candidate_policy_support_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $support "REF_NAME\tactual_property_names"
    foreach cell $objects ref [property_values $objects REF_NAME 0 placement_policy] {
        if {[dict exists $seen $ref]} {continue}
        dict set seen $ref 1
        set props [list_property $cell]
        puts $support "$ref\t$props"
        foreach property $required {if {$property ni $props} {close $support;error "Cannot verify required native placement policy $ref/$property"}}
    }
    close $support
    set policy [dict create]
    set names [property_values $objects NAME 0 placement_policy]
    foreach property [concat $required {MACRO_NAME DONT_TOUCH}] {
        set values [property_values $objects $property [expr {$property ne "IS_PRIMITIVE"}] placement_policy]
        foreach name $names value $values {dict set policy $name $property $value}
    }
    m002_put [file join $::m002_report_dir candidate_policy_${point}.tcllist] $policy
    return $policy
}
rename slr2::constrain slr2::constrain_region
proc slr2::constrain {} {
    variable P;variable front;variable tensor
    set objects [objects [dict keys $P]]
    # Also preserve retained frontend/tensor objects and their hierarchy policies.
    set scope [get_cells -quiet -hier -filter [format {NAME =~ "%s*" || NAME =~ "%s*"} $front $tensor]]
    foreach path [concat [list [string trimright $front /] [string trimright $tensor /]] {scalellm_vcu118_f05_bd_i scalellm_vcu118_f05_bd_i/core scalellm_vcu118_f05_bd_i/core/inst scalellm_vcu118_f05_bd_i/core/inst/u_core scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp}] {
        set parent [m002_exact get_cells $path]
        if {[llength $parent]==1} {lappend scope $parent}
    }
    set before [placement_policy before $scope]
    set issues [list]
    dict for {name properties} $before {
        # All relevant ancestors are included: inherited assignments cannot hide
        # behind an empty leaf property. Conservatively reject relative macros
        # until a complete native partner proof is supplied in a local repair.
        set relevant [expr {[dict exists $P $name] || [dict get $properties IS_PRIMITIVE] in {0 false FALSE}}]
        if {!$relevant} {continue}
        set slr [dict get $properties USER_SLR_ASSIGNMENT]
        if {$slr ne "" && $slr ne "SLR2"} {lappend issues [list EXISTING_SLR_ASSIGNMENT $name $slr]}
        foreach property {RLOC RLOC_ORIGIN MACRO_NAME} {
            if {[dict get $properties $property] ne ""} {lappend issues [list RELATIVE_MACRO_PARTNERS_UNVERIFIED $name $property [dict get $properties $property]]}
        }
    }
    if {![llength [info commands get_macros]]} {lappend issues MACRO_ENUMERATION_API_UNAVAILABLE} else {
        if {[catch {set macros [get_macros -quiet]} issue]} {lappend issues [list MACRO_ENUMERATION_UNAVAILABLE $issue]} elseif {[llength $macros]} {
            foreach macro $macros {
                if {[catch {set partners [get_cells -quiet -of_objects $macro]} issue]} {lappend issues [list MACRO_PARTNERS_UNAVAILABLE $macro $issue];continue}
                set relevant 0
                foreach partner $partners {if {[dict exists $P [get_property NAME $partner]]} {set relevant 1;break}}
                if {!$relevant} {continue}
                foreach partner $partners {if {![dict exists $P [get_property NAME $partner]]} {lappend issues [list MACRO_REQUIRES_EXCLUDED_PARTNER $macro $partner]}}
            }
        }
    }
    m002_put [file join $::m002_report_dir candidate_policy_conflicts.tcllist] $issues
    if {[llength $issues]} {error "Native placement-policy compatibility unproven; original constraints retained"}
    set pbs_before [pblock_snapshot]
    m002_put [file join $::m002_report_dir candidate_existing_pblocks_before.tcllist] $pbs_before
    constrain_region
    set after [placement_policy after $scope]
    if {$before ne $after} {error "Adding candidate Pblock changed existing cell placement policy"}
    set pbs_after [pblock_snapshot]
    m002_put [file join $::m002_report_dir candidate_existing_pblocks_after.tcllist] $pbs_after
    dict for {name definition} $pbs_before {
        if {![dict exists $pbs_after $name] || [dict get $pbs_after $name] ne $definition} {error "Existing Pblock policy/member set changed: $name"}
    }
    if {[lsort [dict keys $pbs_after]] ne [lsort [concat [dict keys $pbs_before] [list $::slr2::pblock]]]} {error "Unexpected Pblock created/removed"}
    m002_put [file join $::m002_report_dir candidate_policy_preservation.txt] "verified=1\nscope=all_original_pblocks_and_frontend_tensor_ancestors_cells\nnew_pblock_only=$::slr2::pblock\nexcluded_macro_partners=0\nunknown_policy=0"
}
proc slr2::reconcile {point} {
    variable P;variable originalP;variable front;variable tensor
    set pb [get_pblocks -quiet $::slr2::pblock]
    if {[llength $pb]!=1} {error "Actual candidate Pblock missing/ambiguous"}
    set actual [get_cells -quiet -of_objects $pb]
    ensure_cells $actual
    set physical [dict create]
    foreach name [get_property NAME $actual] {
        lassign [physical $name [value $name REF_NAME]] parent ref
        if {$parent eq "" || ![bindable $ref]} {error "Unexpected actual Pblock object: $name"}
        dict set physical $parent $ref
    }
    ensure_cells [objects [dict keys $physical]]
    set h [open [file join $::m002_report_dir candidate_pblock_physical_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "physical_NAME\tREF_NAME\tLOC\tSLR\tORIG_CELL_NAME\tORIG_REF_NAME"
    dict for {name ref} $physical {set loc [value $name LOC];puts $h "$name\t$ref\t$loc\t[slr $loc]\t[value $name ORIG_CELL_NAME]\t[value $name ORIG_REF_NAME]"};close $h
    set h [open [file join $::m002_report_dir candidate_native_origin_objects_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tLOC\tSLR\tORIG_CELL_NAME\tORIG_REF_NAME"
    set query [format {IS_PRIMITIVE == 1 && (ORIG_CELL_NAME =~ "%s*" || ORIG_CELL_NAME =~ "%s*")} $front $tensor]
    set origin_supported 1;set checked_refs [dict create];set unsupported [list]
    foreach cell $actual ref [get_property REF_NAME $actual] {
        if {[dict exists $checked_refs $ref]} {continue}
        dict set checked_refs $ref 1
        if {"ORIG_CELL_NAME" ni [list_property $cell]} {set origin_supported 0;lappend unsupported $ref}
    }
    set query_executed 0
    if {$origin_supported && [llength $actual]} {
        set query_executed 1
        set query_code [catch {set originated [get_cells -quiet -hier -filter $query]} issue]
    } else {set query_code 1;set issue "Required ORIG_CELL_NAME property unavailable/empty scope: $unsupported"}
    if {!$query_code && [llength $originated]} {
        ensure_cells $originated
        foreach name [get_property NAME $originated] {
            set origin [value $name ORIG_CELL_NAME]
            if {![dict exists $originalP $origin]} {continue}
            lassign [physical $name [value $name REF_NAME]] parent ref
            if {$parent ne $name} {continue}
            set loc [value $name LOC]
            puts $h "$name\t$ref\t$loc\t[slr $loc]\t$origin\t[value $name ORIG_REF_NAME]"
        }
    }
    close $h
    m002_put [file join $::m002_report_dir candidate_native_origin_query_${point}.txt] "native_tcl_code=$query_code\nquery_executed=$query_executed\nrequired_origin_property_verified=$origin_supported\nrule=global_native_ORIG_CELL_NAME_correspondence\nissue=[string map [list \n { } \r { } \t { }] [expr {$query_code ? $issue : {}}]]"
    if {$query_code || !$origin_supported} {error "Native global origin correspondence query unavailable/failed; reconciliation forbidden: $issue"}
    exec python3 $::env(SLR2_ADAPTER) reconcile $point $::m002_report_dir
    source [file join $::m002_report_dir candidate_reconciled_P_${point}.tcl]
    set h [open [file join $::m002_report_dir candidate_effective_pblock_${point}.txt] {WRONLY CREAT EXCL}]
    foreach property {NAME GRID_RANGES IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {puts $h "$property=[m002_prop $pb $property]"}
    puts $h "physical_members=[dict size $physical]";close $h
    foreach property {IS_SOFT EXCLUDE_PLACEMENT CONTAIN_ROUTING} {if {[m002_prop $pb $property] ni {0 false FALSE}} {error "Effective Pblock policy changed: $property"}}
}
proc slr2::phase {point} {
    variable P
    resolve $point
    reconcile $point
    # Actual P (including native-origin copies) is settled before endpoint queries.
    set h [open [file join $::m002_report_dir candidate_compliance_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tlineage\tLOC\tSLR\tSLR2_compliant\tORIG_CELL_NAME\tORIG_REF_NAME"
    set source [open [file join $::m002_report_dir candidate_reconciliation_${point}.tsv] r];gets $source header
    while {[gets $source row]>=0} {
        lassign [split $row \t] name ref lineage loc slr origin origref
        puts $h "$name\t$ref\t$lineage\t$loc\t$slr\t[expr {$slr eq {SLR2}}]\t$origin\t$origref"
    };close $source;close $h
    set h [open [file join $::m002_report_dir candidate_pblock_actual_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tLOC\tSLR\tselector_P\tORIG_CELL_NAME\tORIG_REF_NAME"
    dict for {name ref} $P {set loc [value $name LOC];puts $h "$name\t$ref\t$loc\t[slr $loc]\t1\t[value $name ORIG_CELL_NAME]\t[value $name ORIG_REF_NAME]"};close $h
    set locs [list]
    foreach name [dict keys $P] {set loc [value $name LOC];if {$loc ne ""} {lappend locs $loc}}
    set h [open [file join $::m002_report_dir candidate_site_members_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "NAME\tREF_NAME\tLOC\tBEL\tSLR\tselected_P"
    if {[llength $locs]} {
        set atSites [get_cells -quiet -of_objects [get_sites -quiet [lsort -unique $locs]] -filter {IS_PRIMITIVE == 1}]
        ensure_cells $atSites
        foreach name [get_property NAME $atSites] {
            set loc [value $name LOC];set ref [value $name REF_NAME]
            lassign [physical $name $ref] parent pref
            puts $h "$name\t$ref\t$loc\t[value $name BEL]\t[slr $loc]\t[dict exists $P $parent]"
        }
    };close $h
    cut $point
    scoped_timing $point
    exec python3 $::env(SLR2_ADAPTER) compliance $point $::m002_report_dir
    puts "E007_STAGE_COMPLETED locality_$point"
}
proc slr2::scoped_timing {point} {
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
