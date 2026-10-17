# Runtime checks required by the concentrated A007 review. No EDA at source time.
namespace eval slr2 {
    variable spatialCache [dict create]
    variable domainCache [dict create]
    variable boundaryPins [dict create]
}
proc slr2::resource_class {ref} {
    if {[regexp {^(BUFG|BUFH|BUFR|BUFIO|BUFMR|BUFCE|PLL|MMCM|IBUF|OBUF|IOBUF|GT|ISERDES|OSERDES|IDELAY|ODELAY|BITSLICE)} $ref]} {return DEDICATED_CLOCK_IO_REQUIRES_SEPARATE_PROOF}
    if {[regexp {^(LUT[1-6]|FD[A-Z0-9]+|LD[A-Z0-9]+|CARRY8|MUXF[789]|SRL16E|SRLC32E|RAM(32|64|128|256|512)[A-Z0-9_]*)$} $ref]} {return CLB_LOGIC_OR_DISTRIBUTED_MEMORY}
    if {$ref in {RAMB18E2 FIFO18E2}} {return RAMB18}
    if {$ref in {RAMB36E2 FIFO36E2}} {return RAMB36}
    if {[regexp {^URAM288(_BASE)?$} $ref]} {return URAM288}
    if {$ref eq "DSP48E2"} {return DSP48E2}
    if {$ref in {GND VCC}} {return CONSTANT_EXCLUDED_FROM_P}
    return UNKNOWN_RESOURCE_REQUIRES_EXPLANATION
}
proc slr2::resource_admissibility {objects} {
    variable RAW;variable P;variable siteSLR
    variable placementNativeSchemas;variable placementObjectSupport
    set placementNativeSchemas [dict create];set placementObjectSupport [dict create]
    set all [objects [lsort -unique [concat [dict keys $RAW] [dict keys $P]]]]
    set out [open [file join $::m002_report_dir candidate_resource_admissibility.tsv] {WRONLY CREAT EXCL}]
    puts $out "NAME\tREF_NAME\tactual_IS_PRIMITIVE\tin_RAW\tin_P\tresource_class\tactual_PRIMITIVE_TYPE\tactual_PRIMITIVE_GROUP\tactual_PRIMITIVE_SUBGROUP\tactual_native_property_support_id\tSLR2_supported_resource_sites"
    set supportOut [open [file join $::m002_report_dir candidate_resource_native_property_support.tsv] {WRONLY CREAT EXCL}]
    puts $supportOut "support_id\tactual_native_property_names"
    set supportIDs [dict create]
    set sites [dict create]
    dict for {site slr} $siteSLR {
        if {$slr ne "SLR2"} {continue}
        if {[regexp {^SLICE_} $site]} {dict incr sites CLB_LOGIC_OR_DISTRIBUTED_MEMORY}
        foreach family {DSP48E2 RAMB18 RAMB36 URAM288} {if {[prefix $site ${family}_]} {dict incr sites $family}}
    }
    set issues [list]
    foreach object $all name [property_values $all NAME 0 resource_admissibility] ref [property_values $all REF_NAME 0 resource_admissibility] primitive [property_values $all IS_PRIMITIVE 0 resource_admissibility] {
        # Every object is still natively queried. Only identical exported schemas
        # are deduplicated; this is not sampling by REF.
        set support [lsort [list_property $object]]
        if {![dict exists $supportIDs $support]} {
            set supportID [format SUPPORT_%05d [expr {[dict size $supportIDs]+1}]]
            dict set supportIDs $support $supportID
            dict set placementNativeSchemas $supportID $support
            puts $supportOut "$supportID\t[list $support]"
        }
        set supportID [dict get $supportIDs $support]
        dict set placementObjectSupport $name [list $ref $primitive $supportID]
        set row [list $name $ref $primitive [dict exists $RAW $name] [dict exists $P $name] [resource_class $ref]]
        foreach property {PRIMITIVE_TYPE PRIMITIVE_GROUP PRIMITIVE_SUBGROUP} {
            lappend row [expr {$property in $support ? [m002_prop $object $property] : {UNKNOWN_UNSUPPORTED_PROPERTY}}]
        }
        set cls [resource_class $ref]
        set capacity [expr {[dict exists $sites $cls] ? [dict get $sites $cls] : 0}]
        lappend row $supportID $capacity
        puts $out [join $row "\t"]
        if {[dict exists $RAW $name] && $primitive ni {1 true TRUE}} {lappend issues [list RAW_IS_NOT_NATIVE_PRIMITIVE $name $ref $primitive]}
        if {![dict exists $P $name]} {continue}
        if {$cls in {UNKNOWN_RESOURCE_REQUIRES_EXPLANATION DEDICATED_CLOCK_IO_REQUIRES_SEPARATE_PROOF CONSTANT_EXCLUDED_FROM_P}} {lappend issues [list UNQUALIFIED_RESOURCE $name $ref $cls]}
        if {$primitive ni {1 true TRUE} && $ref ne "DSP48E2"} {lappend issues [list NONPRIMITIVE_P_WITHOUT_DSP_PARENT_PROOF $name $ref]}
        if {$capacity == 0} {lappend issues [list NO_ACTUAL_SLR2_RESOURCE_SITES $name $ref $cls]}
    };close $out;close $supportOut
    m002_put [file join $::m002_report_dir candidate_resource_admissibility_conflicts.tcllist] $issues
    if {[llength $issues]} {error "Actual resource migration admissibility unproven; all ledger rows preserved"}
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
    variable placementNativeSchemas;variable placementObjectSupport
    set required {NAME REF_NAME IS_PRIMITIVE LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC MACRO_NAME DONT_TOUCH}
    set names [property_values $objects NAME 0 placement_policy]
    set refs [property_values $objects REF_NAME 0 placement_policy]
    set primitives [property_values $objects IS_PRIMITIVE 0 placement_policy]
    if {[llength [lsort -unique $names]] != [llength $objects]} {error "Placement-policy native names are not unique"}
    set support [open [file join $::m002_report_dir candidate_policy_support_${point}.tsv] {WRONLY CREAT EXCL}]
    set schemas [open [file join $::m002_report_dir candidate_policy_schemas_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $support "NAME\tREF_NAME\tactual_IS_PRIMITIVE\tsupport_id\tschema_source\tRLOC_ORIGIN_schema_state\tRLOC_ORIGIN_native_tcl_code\tRLOC_ORIGIN_native_value"
    puts $schemas "support_id\tactual_native_property_names"
    set seen [dict create];set policy [dict create];set supportedObjects [list];set supportedNames [list]
    foreach cell $objects name $names ref $refs primitive $primitives {
        # Reuse only the immediately preceding per-object native census, never
        # the first object sharing a REF. Ancestors and every after snapshot
        # receive fresh native schemas. No design mutation precedes this cache.
        set source FRESH_NATIVE_LIST_PROPERTY
        if {$point eq "before" && [info exists placementObjectSupport] && [dict exists $placementObjectSupport $name]} {
            lassign [dict get $placementObjectSupport $name] priorRef priorPrimitive priorID
            if {$priorRef ne $ref || $priorPrimitive ne $primitive} {error "Native resource/policy object identity changed: $name"}
            set props [dict get $placementNativeSchemas $priorID]
            set source RESOURCE_ADMISSIBILITY_PER_OBJECT_NATIVE
        } else {set props [lsort [list_property $cell]]}
        if {![dict exists $seen $props]} {
            set sid [format POLICY_SUPPORT_%05d [expr {[dict size $seen]+1}]]
            dict set seen $props $sid;puts $schemas "$sid\t[list $props]"
        }
        set sid [dict get $seen $props]
        foreach property $required {
            if {$property ni $props} {close $support;close $schemas;error "Cannot verify required native placement policy $name/$ref/$property"}
        }
        if {"RLOC_ORIGIN" in $props} {
            set state SUPPORTED_IN_ACTUAL_NATIVE_SCHEMA
            lappend supportedObjects $cell;lappend supportedNames $name
            puts $support "$name\t$ref\t$primitive\t$sid\t$source\t$state\tDEFERRED_TO_BOUND_NATIVE_COLUMN\tDEFERRED_TO_BOUND_NATIVE_COLUMN"
        } else {
            set state UNSUPPORTED_IN_ACTUAL_NATIVE_SCHEMA
            set code [catch {get_property RLOC_ORIGIN $cell} result options]
            puts $support "$name\t$ref\t$primitive\t$sid\t$source\t$state\t$code\t[list $result]";flush $support
            if {$code || $result ne ""} {
                m002_put [file join $::m002_report_dir candidate_policy_RLOC_ORIGIN_${point}_error.tcllist] [list NAME $name REF_NAME $ref IS_PRIMITIVE $primitive schema_state $state command [list get_property RLOC_ORIGIN $cell] native_tcl_code $code result $result options $options]
                close $support;close $schemas;error "Unsupported native RLOC_ORIGIN is not a successful empty read: $name"
            }
            # This is an observed native0 empty value with explicit unsupported
            # state, not an imputed blank. Original relative-macro/partner gates
            # still run before any Pblock is created.
            dict set policy $name RLOC_ORIGIN $result
        }
        dict set policy $name NATIVE_RLOC_ORIGIN_SUPPORT [list state $state native_tcl_code 0]
    }
    close $support;close $schemas
    if {[llength $supportedObjects]} {
        set values [property_values $supportedObjects RLOC_ORIGIN 1 placement_policy]
        foreach name $supportedNames value $values {dict set policy $name RLOC_ORIGIN $value}
    }
    foreach property $required {
        set values [property_values $objects $property [expr {$property ni {NAME REF_NAME IS_PRIMITIVE}}] placement_policy]
        foreach name $names value $values {dict set policy $name $property $value}
    }
    m002_put [file join $::m002_report_dir candidate_policy_${point}.tcllist] $policy
    return $policy
}
rename slr2::constrain slr2::constrain_region
proc slr2::constrain {} {
    variable P;variable root
    set objects [objects [dict keys $P]]
    # Check all selected physical parents, literal descendants and every real ancestor.
    set scope $objects
    set broad $root;set bracket [string first {[} $root]
    if {$bracket >= 0} {set broad [string range $root 0 [expr {$bracket-1}]]}
    foreach object [get_cells -quiet -hier -filter [format {NAME =~ "%s*"} $broad]] {
        set name [get_property NAME $object]
        if {$name eq $root || [prefix $name ${root}/]} {lappend scope $object}
    }
    set path $root
    while {$path ne "." && $path ne "/"} {
        set parent [m002_exact get_cells $path]
        if {[llength $parent] != 1} {error "Required actual ancestor unavailable: $path"}
        lappend scope $parent;set path [file dirname $path]
    }
    set scope [lsort -unique $scope]
    resource_admissibility $objects
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
    m002_put [file join $::m002_report_dir candidate_policy_preservation.txt] "verified=1\nscope=all_original_pblocks_and_exact_candidate_ancestors_cells\nnew_pblock_only=$::slr2::pblock\nexcluded_macro_partners=0\nunknown_policy=0"
}
proc slr2::reconcile {point} {
    variable P;variable originalP;variable root
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
    set broad $root;set bracket [string first {[} $root]
    if {$bracket >= 0} {set broad [string range $root 0 [expr {$bracket-1}]]}
    # Includes real DSP48E2 parents even when they are native nonprimitive cells.
    # Only native ORIG_CELL_NAME matches in originalP are admitted below.
    set query [format {ORIG_CELL_NAME =~ "%s*"} $broad]
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
    m002_system_python $::env(SLR2_ADAPTER) reconcile $point $::m002_report_dir
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
    m002_system_python $::env(SLR2_ADAPTER) directed-timing $point $::m002_report_dir
    m002_system_python $::env(SLR2_ADAPTER) compliance $point $::m002_report_dir
    puts "E008_STAGE_COMPLETED locality_$point"
}
proc slr2::scoped_timing point {
    variable boundaryPins
    set h [open [file join $::m002_report_dir candidate_scoped_timing_${point}.tsv] {WRONLY CREAT EXCL}]
    set queries [open [file join $::m002_report_dir candidate_timing_queries_${point}.tcllist] {WRONLY CREAT EXCL}]
    puts $h "direction\tdelay_type\tmax_paths\tqueried_boundary_pins\treturned_paths\tSTARTPOINT_PIN\tENDPOINT_PIN\tSTARTPOINT_CLOCK\tENDPOINT_CLOCK\tSLACK\tLOGIC_DELAY\tNET_DELAY\tDATAPATH_DELAY\tEXCEPTION"
    foreach direction {INGRESS EGRESS UNRESOLVED} {
        if {![dict exists $boundaryPins $direction]} {continue}
        set pins [dict keys [dict get $boundaryPins $direction]]
        foreach type {max min} {
            set command [list get_timing_paths -quiet -through $pins -delay_type $type -max_paths 16 -nworst 1]
            puts $queries [list direction $direction delay_type $type command $command];flush $queries
            puts [list DIRECTED_API operation BOUNDED_TIMING event BEGIN point $point direction $direction delay_type $type epoch_ms [clock milliseconds]];flush stdout
            set paths [{*}$command]
            puts [list DIRECTED_API operation BOUNDED_TIMING event END point $point direction $direction delay_type $type returned_paths [llength $paths] epoch_ms [clock milliseconds]];flush stdout
            if {![llength $paths]} {puts $h "$direction\t$type\t16\t[llength $pins]\t0\tNO_PATH";continue}
            report_timing -of_objects $paths -nets -input_pins -file [file join $::m002_report_dir candidate_cut_timing_${point}_${direction}_${type}.rpt]
            foreach path $paths {
                set values [list $direction $type 16 [llength $pins] [llength $paths]]
                set supported [list_property $path]
                foreach property {STARTPOINT_PIN ENDPOINT_PIN STARTPOINT_CLOCK ENDPOINT_CLOCK SLACK LOGIC_DELAY NET_DELAY DATAPATH_DELAY EXCEPTION} {
                    lappend values [expr {$property in $supported ? [m002_prop $path $property] : {UNKNOWN_UNSUPPORTED_PROPERTY}}]
                }
                puts $h [join $values "\t"]
            }
        }
    };close $h;close $queries
    m002_put [file join $::m002_report_dir candidate_scoped_timing_${point}_coverage.txt] "diagnostic_only=1\nselection=EGRESS_outside_LOAD_endpoints_INGRESS_inside_LOAD_endpoints_UNRESOLVED_inside_boundary_pins\nmax_paths_per_direction_and_delay_type=16\nnworst=1\nfull_cut_path_enumeration=false\nfull_cut_TNS=NOT_MEASURED\ncomplete_global_timing_and_constraints=unchanged"
}
