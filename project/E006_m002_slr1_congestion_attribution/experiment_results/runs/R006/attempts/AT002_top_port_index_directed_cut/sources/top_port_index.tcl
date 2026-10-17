# Read-only complete native top-port incidence transpose. No native work at source.
namespace eval slr2 {
    variable topIndexLibrarySource [file normalize [info script]]
    variable topIndex [dict create]
    variable topCallChannel ""
    variable topCallSerial 0
    variable topPoint ""
    variable directedGroupNames [dict create]
}
proc slr2::top_native {operation command} {
    variable topCallChannel;variable topCallSerial;variable topPoint
    set id [incr topCallSerial]
    directed_trace $operation BEGIN $topPoint call_id $id
    set started [clock milliseconds]
    set code [catch {uplevel #0 $command} result options]
    set ended [clock milliseconds]
    puts $topCallChannel [list call_id $id operation $operation command $command native_tcl_code $code started_epoch_ms $started ended_epoch_ms $ended result $result options $options]
    flush $topCallChannel
    directed_trace $operation END $topPoint call_id $id native_tcl_code $code
    if {$code} {return -options $options $result}
    return $result
}
proc slr2::top_values {objects property allowEmpty} {
    if {![llength $objects]} {return [list]}
    set values [top_native TOP_PROPERTY_${property} [list get_property $property $objects]]
    if {[llength $values] != [llength $objects]} {
        set values [list]
        foreach object $objects {
            set name [top_native TOP_SCALAR_NAME [list get_property NAME $object]]
            if {$name eq "" || $name ne $object} {error "UNQUALIFIED: native top-index object identity ambiguous"}
            lappend values [top_native TOP_SCALAR_${property} [list get_property $property $object]]
        }
    }
    if {[llength $values] != [llength $objects]} {error "UNQUALIFIED: top-index metadata alignment"}
    if {!$allowEmpty} {foreach value $values {if {$value eq ""} {error "UNQUALIFIED: required top-index property empty: $property"}}}
    return $values
}
proc slr2::top_index_build {point} {
    variable topIndex;variable topCallChannel;variable topCallSerial;variable topPoint
    variable topIndexLibrarySource
    set topPoint $point;set topCallSerial 0;set topIndex [dict create]
    set callPath [file join $::m002_report_dir candidate_top_port_native_calls_${point}.tcllist]
    set topCallChannel [open $callPath {WRONLY CREAT EXCL}]
    set code [catch {
        set design [top_native TOP_CURRENT_DESIGN [list current_design]]
        set nativeTool [top_native TOP_NATIVE_TOOL [list version -short]]
        set designName [lindex [top_values [list $design] NAME 0] 0]
        set context [top_native TOP_CURRENT_INSTANCE [list current_instance .]]
        if {$context ne ""} {error "UNQUALIFIED: top-port census is not at design root: $context"}
        set properties [top_native TOP_CLASS_SCHEMA [list list_property -class port]]
        set directionEnum [top_native TOP_DIRECTION_ENUM [list list_property_value DIRECTION -class port]]
        foreach property {NAME CLASS DIRECTION} {if {$property ni $properties} {error "UNQUALIFIED: missing native port schema: $property"}}
        set ports [top_native TOP_PORT_UNIVERSE [list get_ports]]
        set names [top_values $ports NAME 0]
        set classes [top_values $ports CLASS 0]
        set directions [top_values $ports DIRECTION 1]
        if {[llength [lsort -unique $names]] != [llength $ports]} {error "UNQUALIFIED: duplicate native port NAME"}
        foreach object $ports name $names class $classes {
            if {$object ne $name || $class ne "port"} {error "UNQUALIFIED: actual top-port object universe ambiguous"}
        }
        set metadata [dict create]
        foreach property {BUS_NAME BUS_WIDTH BUS_START BUS_STOP BUS_DIRECTION UNCONNECTED} {
            if {$property in $properties} {dict set metadata $property [top_values $ports $property 1]}
        }
        set portRows [dict create];set groups [dict create];set aliasToGroup [dict create]
        set netCache [dict create]
        foreach port $ports name $names direction $directions {
            set netObjects [top_native TOP_PORT_DIRECT_NETS [list get_nets -of_objects $port]]
            set netNames [top_values $netObjects NAME 0]
            if {[llength [lsort -unique $netNames]] != [llength $netObjects]} {error "UNQUALIFIED: duplicate direct net identity"}
            set memberGroups [dict create]
            foreach net $netObjects netName $netNames {
                if {$net ne $netName} {error "UNQUALIFIED: direct net handle/NAME mismatch"}
                if {[dict exists $netCache $netName]} {
                    set canonical [dict get $netCache $netName]
                } else {
                    set segments [top_native TOP_NET_SEGMENTS [list get_nets -segments $net]]
                    set aliases [top_values $segments NAME 0]
                    if {![llength $aliases] || [llength [lsort -unique $aliases]] != [llength $segments] || $netName ni $aliases} {error "UNQUALIFIED: incomplete/ambiguous top-port alias closure"}
                    foreach handle $segments alias $aliases {if {$handle ne $alias} {error "UNQUALIFIED: native segment handle/NAME mismatch"}}
                    set canonical [lindex [lsort $aliases] 0]
                    if {[dict exists $groups $canonical] && [lsort [dict get $groups $canonical aliases]] ne [lsort $aliases]} {error "UNQUALIFIED: conflicting complete alias groups"}
                    foreach alias $aliases {
                        if {[dict exists $aliasToGroup $alias] && [dict get $aliasToGroup $alias] ne $canonical} {error "UNQUALIFIED: overlapping unequal alias closures"}
                        dict set aliasToGroup $alias $canonical;dict set netCache $alias $canonical
                    }
                    if {![dict exists $groups $canonical]} {dict set groups $canonical [dict create handles $segments aliases $aliases ports [dict create]]}
                }
                dict set memberGroups $canonical 1
                dict set groups $canonical ports $name $port
            }
            set extra [dict create]
            set extraStatus [dict create]
            set ordinal [llength [dict keys $portRows]]
            dict for {property values} $metadata {dict set extra $property [lindex $values $ordinal]}
            foreach property {BUS_NAME BUS_WIDTH BUS_START BUS_STOP BUS_DIRECTION UNCONNECTED} {
                dict set extraStatus $property [expr {![dict exists $extra $property] ? "UNSUPPORTED" : ([dict get $extra $property] eq "" ? "EMPTY" : "VALUE")}]
            }
            set connected [expr {[llength $netNames] > 0}]
            if {[dict exists $extra UNCONNECTED]} {
                set flag [dict get $extra UNCONNECTED]
                if {$flag ni {"" 0 1 false true FALSE TRUE}} {error "UNQUALIFIED: unknown native UNCONNECTED value"}
                if {$flag ne "" && ($flag in {1 true TRUE}) == $connected} {error "UNQUALIFIED: native UNCONNECTED contradicts complete direct net census"}
            }
            dict set portRows $name [dict create handle $port NAME $name CLASS port DIRECTION $direction metadata $extra metadata_status $extraStatus direct_net_handles $netObjects direct_net_NAMES $netNames canonical_groups [dict keys $memberGroups] connection_status [expr {!$connected ? "DISCONNECTED" : ([dict size $memberGroups] > 1 ? "MULTIPLE_CANONICAL_GROUPS" : "CONNECTED")}]]
        }
        # Exhaustive native reciprocal qualification of every port-attached group.
        # This resolves bus/secondary object-universe ambiguity without scanning
        # candidate nets which provably have no top-port incidence.
        dict for {canonical row} $groups {
            set forward [top_native TOP_GROUP_FORWARD_PORTS [list get_ports -of_objects [dict get $row handles]]]
            set forwardNames [top_values $forward NAME 0]
            set forwardClasses [top_values $forward CLASS 0]
            set forwardDirections [top_values $forward DIRECTION 1]
            if {[llength [lsort -unique $forwardNames]] != [llength $forward]} {error "UNQUALIFIED: duplicate native forward port identity"}
            if {[lsort $forwardNames] ne [lsort [dict keys [dict get $row ports]]]} {error "UNQUALIFIED: full native reciprocal port group mismatch"}
            foreach handle $forward name $forwardNames class $forwardClasses direction $forwardDirections {
                if {![dict exists $portRows $name] || $handle ne $name || $class ne "port" || $direction ne [dict get $portRows $name DIRECTION]} {error "UNQUALIFIED: bus/secondary/native port identity or direction mismatch"}
            }
            dict set groups $canonical native_forward_port_handles $forward
            dict set groups $canonical native_forward_port_NAMES $forwardNames
        }
        set endContext [top_native TOP_CURRENT_INSTANCE_END [list current_instance .]]
        set endDesign [top_native TOP_CURRENT_DESIGN_END [list current_design]]
        if {$endContext ne $context || $endDesign ne $design} {error "UNQUALIFIED: design/current-instance epoch changed"}
        if {[info exists ::env(E006_DCP)]} {set inputPath $::env(E006_DCP);set stage E006_readonly_attribution} elseif {[info exists ::env(HAP_RECOVERY_CHECKPOINT)]} {set inputPath $::env(HAP_RECOVERY_CHECKPOINT);set stage E008_$point} else {error "UNQUALIFIED: actual input identity unavailable"}
        set epoch [list $point [clock microseconds] $design $inputPath]
        set topIndex [dict create schema_version top_port_reverse_index_v1 acquisition_mode NATIVE_PORT_REVERSE_INDEX_V1 mode complete_native_port_incidence_transpose_v1 native_tool $nativeTool input_path [file normalize $inputPath] source_paths [list $topIndexLibrarySource] stage $stage epoch_id $epoch point $point design_handle $design design_NAME $designName current_instance $context schema $properties direction_enum $directionEnum metadata_supported [dict keys $metadata] native_port_handles $ports native_port_NAMES $names ports $portRows groups $groups alias_to_group $aliasToGroup native_reciprocal_all_groups_qualified 1 native_calls [file tail $callPath] native_call_count $topCallSerial qualified 1]
        m002_put [file join $::m002_report_dir candidate_top_port_index_${point}.tcllist] $topIndex
    } result options]
    close $topCallChannel;set topCallChannel ""
    if {$code} {return -options $options $result}
    # All native evidence files are closed before CPU publishes the bound
    # INDEX_CLOSED receipt. A failed validation stops this cut before any join.
    m002_system_python [file join [file dirname $topIndexLibrarySource] top_port_evidence.py] close $point $::m002_report_dir
    return $topIndex
}
proc slr2::top_index_join {point canonical aliases} {
    variable topIndex
    if {![dict exists $topIndex qualified] || ![dict get $topIndex qualified] || [dict get $topIndex point] ne $point} {error "UNQUALIFIED: top-port index absent/wrong stage"}
    set matched [dict create]
    foreach alias $aliases {
        if {[dict exists $topIndex alias_to_group $alias]} {dict set matched [dict get $topIndex alias_to_group $alias] 1}
    }
    if {[dict size $matched] > 1} {error "UNQUALIFIED: candidate intersects multiple complete port groups"}
    if {![dict size $matched]} {return [dict create handles [list] names [list] directions [list] intersected_group NONE]}
    set group [lindex [dict keys $matched] 0]
    if {$canonical ne $group || [lsort $aliases] ne [lsort [dict get $topIndex groups $group aliases]]} {error "UNQUALIFIED: candidate/top-port intersecting alias closures differ"}
    set names [dict keys [dict get $topIndex groups $group ports]]
    set handles [list];set directions [list]
    foreach name $names {lappend handles [dict get $topIndex ports $name handle];lappend directions [dict get $topIndex ports $name DIRECTION]}
    return [dict create handles $handles names $names directions $directions intersected_group $group]
}
