# Independent CPU-only integration of the actual collector with a finite graph.
# This is not native Vivado qualification. argv: source directory, output dir.
set sourceDir [lindex $argv 0]
set outputDir [lindex $argv 1]
source [file join $sourceDir candidate_inspector.tcl]
source [file join $sourceDir directed_exporter.tcl]
rename exec native_exec_disabled
proc exec args {lappend ::adapterCalls $args;return MOCK_ADAPTER_NOT_EXECUTED}
set ::env(E006_CANDIDATE_ADAPTER) MOCK_ADAPTER
set ::env(HAP_RECOVERY_CHECKPOINT) [file join $outputDir CPU_INPUT_NOT_DCP.txt]
file mkdir $outputDir
set h [open $::env(HAP_RECOVERY_CHECKPOINT) {WRONLY CREAT EXCL}];puts $h CPU_FIXTURE_NOT_A_NATIVE_DESIGN;close $h
proc m002_system_python {adapter args} {
    if {[file tail $adapter] eq "top_port_evidence.py"} {
        return [native_exec_disabled /usr/bin/python3 $adapter {*}$args]
    }
    lappend ::adapterCalls [list $adapter {*}$args]
    return MOCK_ADAPTER_NOT_EXECUTED
}
proc current_design args {return fixture_design}
proc current_instance args {if {$args ne {.}} {error READ_ONLY_CURRENT_INSTANCE_DOT_REQUIRED};return ""}
proc check {condition message} {if {![uplevel 1 [list expr $condition]]} {error $message}}
proc version args {return 2025.2}
proc list_property args {
    if {[lindex $args end] eq "port"} {return {NAME CLASS DIRECTION BUS_NAME BUS_START BUS_STOP BUS_WIDTH BUS_DIRECTION UNCONNECTED}}
    if {$::case eq "bad_schema"} {return {NAME IS_LEAF}}
    return {NAME DIRECTION IS_LEAF REF_PIN_NAME IS_CLOCK}
}
proc list_property_value args {return {IN OUT INOUT}}
proc get_property args {
    set a $args
    if {[lindex $a 0] eq "-quiet"} {set a [lrange $a 1 end]}
    lassign $a prop objects
    set values [list]
    foreach object $objects {
        if {![dict exists $::props $object $prop]} {error "Missing mock property $object/$prop"}
        if {$::forbidPeerRich && $object eq "peer/D" && $prop ni {NAME DIRECTION IS_LEAF}} {error "Pruned peer rich property queried: $prop"}
        lappend values [dict get $::props $object $prop]
    }
    return $values
}
proc argval {args key} {set index [lsearch -exact $args $key];return [lindex $args [expr {$index+1}]]}
proc get_pins args {
    set objects [argval $args -of_objects]
    set filter [expr {[lsearch -exact $args -filter]>=0}]
    if {[lsearch -exact $args -leaf]>=0} {
        if {$filter} {
            incr ::roleQueries
            if {$::case eq "role_error"} {error MOCK_NATIVE_ROLE_FAILURE}
            set result [list]
            foreach pin $::netPins {
                if {[dict get $::props $pin DIRECTION] ne "IN"} {
                    if {$::case eq "missing_local_nonload" && $pin eq "candidate/Q"} {continue}
                    lappend result $pin
                }
            }
            return $result
        }
        incr ::fullQueries
        if {$::forbidPeerRich} {error "Forbidden unfiltered full-net leaf query"}
        return $::netPins
    }
    if {[llength $objects]!=1} {error "Mock requires per-local-owner pin query"}
    set result [list]
    dict for {name props} $::props {
        if {[dict exists $props CLASS] && [dict get $props CLASS] eq "pin" && [file dirname $name] eq $objects} {lappend result $name}
    }
    return $result
}
proc get_nets args {
    if {[lsearch -exact $args -segments]>=0} {return [expr {[lindex $args end] in {n0 n1} ? "n0 n1" : "q0 q1"}]}
    set pin [argval $args -of_objects]
    if {[dict exists $::portNets $pin]} {return [dict get $::portNets $pin]}
    if {$pin in $::disconnected} {return [list]}
    if {$pin in $::netPins || $pin eq "dsp/A"} {return n1}
    error "Unexpected local pin $pin"
}
proc get_ports args {
    if {![llength $args]} {return $::ports}
    if {[lrange $args 0 0] ne {-of_objects}} {error UNEXPECTED_PORT_ARGUMENTS}
    set segments [lindex $args 1];set result [list]
    foreach port $::ports {
        set found 0
        foreach direct [dict get $::portNets $port] {
            set aliases [expr {$direct in {n0 n1} ? "n0 n1" : "q0 q1"}]
            foreach alias $aliases {if {$alias in $segments} {set found 1}}
        }
        if {$found} {lappend result $port}
    }
    return $result
}
proc get_cells args {
    if {[lsearch -exact $args -of_objects]>=0} {
        set result [list]
        foreach pin [argval $args -of_objects] {lappend result [file dirname $pin]}
        return [lsort -unique $result]
    }
    # Only exercised by the DSP expansion, with a finite complete primitive set.
    return $::dspChildren
}
proc get_clocks args {return [list]}
proc slr2::clock_domains point {set ::slr2::domainCache [dict create]}
proc slr2::spatial loc {return [list $loc TILE REGION]}
proc slr2::slr loc {
    if {$loc eq ""} {return UNPLACED}
    return SLR1
}
proc addcell {name ref primitive} {
    dict set ::props $name [dict create NAME $name CLASS cell REF_NAME $ref IS_PRIMITIVE $primitive LOC LOC_$name BEL BEL_$name]
    dict set ::slr2::handles $name $name
}
proc addpin {name direction {leaf 1}} {
    set owner [file dirname $name]
    dict set ::props $name [dict create NAME $name CLASS pin DIRECTION $direction REF_PIN_NAME [file tail $name] IS_CLOCK 0 IS_LEAF $leaf]
    if {$leaf} {lappend ::netPins $name}
}
proc setup {name} {
    set ::case $name
    set ::props [dict create]
    foreach net {n0 n1 q0 q1} {dict set ::props $net [dict create NAME $net]}
    dict set ::props fixture_design [dict create NAME fixture_design]
    set ::portNets [dict create]
    set ::netPins [list];set ::ports [list];set ::disconnected [list];set ::dspChildren [list]
    set ::roleQueries 0;set ::fullQueries 0;set ::adapterCalls [list]
    set ::forbidPeerRich [expr {$name in {ingress top_load top_driver constant_driver disconnected dsp_copy}}]
    foreach field {RAW S P mapping handles physicalCache cellInfo spatialCache domainCache boundaryPins} {set ::slr2::$field [dict create]}
    addcell candidate FDRE 1;addcell external BUFG 1;addcell peer FDRE 1
    dict set ::slr2::RAW candidate FDRE;dict set ::slr2::S candidate FDRE;dict set ::slr2::P candidate FDRE
    addpin candidate/D IN;addpin external/O OUT;addpin peer/D IN
    if {$name eq "index_universe"} {
        foreach {port direction nets} {{data[0]} IN q0 {data[1]} OUT n1 secondary/path OUT {n0 q0} UNKNOWN_PORT UNKNOWN n1 DISCONNECTED IN {}} {
            lappend ::ports $port
            dict set ::props $port [dict create NAME $port CLASS port DIRECTION $direction]
            dict set ::portNets $port $nets
        }
    }
    if {$name in {top_load egress_top_load}} {
        dict set ::props TOP_OUT [dict create NAME TOP_OUT CLASS port DIRECTION OUT]
        set ::ports TOP_OUT
        if {$name eq "egress_top_load"} {dict set ::props external/O DIRECTION IN;addpin candidate/Q OUT}
    } elseif {$name in {top_driver duplicate_top_driver}} {
        dict set ::props external/O DIRECTION IN
        dict set ::props TOP_IN [dict create NAME TOP_IN CLASS port DIRECTION IN]
        set ::ports TOP_IN
        if {$name eq "duplicate_top_driver"} {set ::ports {TOP_IN TOP_IN}}
    } elseif {$name eq "top_unknown"} {
        dict set ::props TOP_UNKNOWN [dict create NAME TOP_UNKNOWN CLASS port DIRECTION {}]
        set ::ports TOP_UNKNOWN
    } elseif {$name eq "no_driver"} {
        dict set ::props external/O DIRECTION IN
    } elseif {$name eq "egress"} {
        dict set ::props external/O DIRECTION IN
        addpin candidate/Q OUT
    } elseif {$name eq "multidriver"} {
        addcell second LUT1 1;addpin second/O OUT
    } elseif {$name eq "inout"} {
        dict set ::props peer/D DIRECTION INOUT
    } elseif {$name eq "unknown"} {
        dict set ::props peer/D DIRECTION ""
    } elseif {$name eq "missing_local_nonload"} {
        addpin candidate/Q OUT
    } elseif {$name eq "constant_driver"} {
        dict unset ::props external/O
        set ::netPins [lsearch -all -inline -not -exact $::netPins external/O]
        addcell candidate_gnd GND 1;addpin candidate_gnd/G OUT
        dict set ::slr2::RAW candidate_gnd GND
    } elseif {$name eq "disconnected"} {
        addpin candidate/CE IN
        set ::netPins [lsearch -all -inline -not -exact $::netPins candidate/CE]
        set ::disconnected candidate/CE
    } elseif {$name eq "dsp_copy"} {
        addcell dsp DSP48E2 0;addcell dsp/alu DSP_ALU 1;addcell dsp/mult DSP_MULTIPLIER 1
        addpin dsp/A IN 0;addpin dsp/alu/A IN;addpin dsp/mult/A IN
        dict set ::slr2::P dsp DSP48E2
        set ::dspChildren {dsp/alu dsp/mult}
        # A reconciled physical member outside the original literal RAW/S root.
        addcell origin_copy FDRE 1;addpin origin_copy/D IN
        dict set ::slr2::P origin_copy FDRE
    } elseif {$name eq "no_local_pins"} {
        dict unset ::props candidate/D
        set ::netPins [lsearch -all -inline -not -exact $::netPins candidate/D]
    }
    foreach port $::ports {
        if {![dict exists $::portNets $port]} {dict set ::portNets $port n1}
        foreach {property value} {BUS_NAME {} BUS_START {} BUS_STOP {} BUS_WIDTH {} BUS_DIRECTION {} UNCONNECTED 0} {dict set ::props $port $property $value}
        if {![llength [dict get $::portNets $port]]} {dict set ::props $port UNCONNECTED 1}
        if {$port in {{data[0]} {data[1]}}} {
            foreach {property value} {BUS_NAME data BUS_START 0 BUS_STOP 1 BUS_WIDTH 2 BUS_DIRECTION ASCENDING} {dict set ::props $port $property $value}
        }
    }

}
proc readtsv path {
    set h [open $path];gets $h header;set columns [split $header "\t"];set rows [list]
    while {[gets $h line]>=0} {
        set values [split $line "\t"]
        check {[llength $columns]==[llength $values]} "TSV column misalignment at $path: $line"
        set row [dict create];foreach column $columns value $values {dict set row $column $value};lappend rows $row
    }
    close $h;return $rows
}

rename get_property fixture_get_property
proc get_property args {
    set prop [lindex $args 0];set objects [lindex $args 1]
    if {$::review_mode eq "metadata_query_error" && $prop eq "BUS_WIDTH"} {error NATIVE_METADATA_FAILURE}
    set value [fixture_get_property {*}$args]
    if {$::review_mode eq "scalar_fallback"} {
        if {[llength $objects]==1} {return [lindex $value 0]}
        return [lsearch -all -inline -not -exact $value ""]
    }
    return $value
}
rename list_property fixture_list_property
proc list_property args {
    if {$::review_mode eq "optional_unsupported" && [lindex $args end] eq "port"} {return {NAME CLASS DIRECTION}}
    return [fixture_list_property {*}$args]
}
rename current_instance fixture_current_instance
proc current_instance args {
    if {$::review_mode eq "nonroot_context"} {return subinstance}
    return [fixture_current_instance {*}$args]
}
rename get_nets fixture_get_nets
proc get_nets args {
    if {$::review_mode eq "adjacency_error" && $args eq {-of_objects {data[0]}}} {error "NATIVE_ADJACENCY_FAILURE\nretained detail"}
    if {$::review_mode eq "unequal_aliases" && $args eq {-segments q0}} {return {n0 q0 q1}}
    return [fixture_get_nets {*}$args]
}
rename get_ports fixture_get_ports
proc get_ports args {
    set value [fixture_get_ports {*}$args]
    if {[llength $args]} {
        if {$::review_mode eq "reciprocal_missing"} {return [lsearch -all -inline -not -exact $value secondary/path]}
        if {$::review_mode eq "reciprocal_extra"} {return [concat $value DISCONNECTED]}
    }
    return $value
}
foreach mode {control optional_unsupported scalar_fallback literal_mixed_inout nonroot_context adjacency_error unequal_aliases reciprocal_missing reciprocal_extra metadata_query_error disconnected_contradiction} {
    set ::review_mode $mode
    setup index_universe
    if {$mode eq "literal_mixed_inout"} {
        dict set ::props UNKNOWN_PORT DIRECTION MIXED
        dict set ::props {data[1]} DIRECTION INOUT
    }
    if {$mode eq "disconnected_contradiction"} {dict set ::props DISCONNECTED UNCONNECTED 0}
    set ::m002_report_dir [file join $outputDir $mode];file mkdir $::m002_report_dir
    foreach tag {RAW S P} {
        set h [open [file join $::m002_report_dir candidate_${tag}_test.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME\tREF_NAME";dict for {member ref} [set ::slr2::$tag] {puts $h "$member\t$ref"};close $h
    }
    set code [catch {slr2::cut test} value options]
    set successExpected [expr {$mode in {control optional_unsupported scalar_fallback literal_mixed_inout}}]
    check {($code==0)==$successExpected} "Unexpected actual collector result $mode: $code/$value"
    set marker [file join $::m002_report_dir candidate_cut_test_closed.txt]
    check {[file exists $marker]==$successExpected} "Incorrect closed cut marker for $mode"
    puts [list A007_NATIVE_CASE mode $mode successExpected $successExpected caught_code $code result $value]
}
