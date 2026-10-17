# Independent CPU-only integration of the actual collector with a finite graph.
# This is not native Vivado qualification. argv: source directory, output dir.
set sourceDir [lindex $argv 0]
set outputDir [lindex $argv 1]
source [file join $sourceDir candidate_inspector.tcl]
source [file join $sourceDir directed_exporter.tcl]
rename exec native_exec_disabled
proc exec args {lappend ::adapterCalls $args;return MOCK_ADAPTER_NOT_EXECUTED}
set ::env(E006_CANDIDATE_ADAPTER) MOCK_ADAPTER
proc check {condition message} {if {![uplevel 1 [list expr $condition]]} {error $message}}
proc version args {return 2025.2}
proc list_property args {
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
    if {[lsearch -exact $args -segments]>=0} {return {n0 n1}}
    set pin [argval $args -of_objects]
    if {$pin in $::disconnected} {return [list]}
    if {$pin in $::netPins || $pin eq "dsp/A"} {return n1}
    error "Unexpected local pin $pin"
}
proc get_ports args {return $::ports}
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
proc slr2::owner name {return MOCK_ROOT}
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
    foreach net {n0 n1} {dict set ::props $net [dict create NAME $net]}
    set ::netPins [list];set ::ports [list];set ::disconnected [list];set ::dspChildren [list]
    set ::roleQueries 0;set ::fullQueries 0;set ::adapterCalls [list]
    set ::forbidPeerRich [expr {$name in {ingress top_load top_driver constant_driver disconnected dsp_copy}}]
    foreach field {RAW S P mapping handles physicalCache cellInfo spatialCache domainCache boundaryPins} {set ::slr2::$field [dict create]}
    addcell candidate FDRE 1;addcell external BUFG 1;addcell peer FDRE 1
    dict set ::slr2::RAW candidate FDRE;dict set ::slr2::S candidate FDRE;dict set ::slr2::P candidate FDRE
    addpin candidate/D IN;addpin external/O OUT;addpin peer/D IN
    if {$name eq "top_load"} {
        dict set ::props TOP_OUT [dict create NAME TOP_OUT CLASS port DIRECTION OUT]
        set ::ports TOP_OUT
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
foreach name {ingress top_load top_driver egress multidriver inout unknown top_unknown no_driver role_error missing_local_nonload constant_driver disconnected dsp_copy bad_schema no_local_pins duplicate_top_driver} {
    setup $name
    set ::m002_report_dir [file join $outputDir $name]
    file mkdir $::m002_report_dir
    foreach tag {RAW S P} {
        set h [open [file join $::m002_report_dir candidate_${tag}_test.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME\tREF_NAME"
        dict for {member ref} [set ::slr2::$tag] {puts $h "$member\t$ref"}
        close $h
    }
    set caught [catch {slr2::cut test} value options]
    if {$name in {bad_schema no_local_pins duplicate_top_driver}} {
        check {$caught} "Invalid schema/local coverage unexpectedly qualified"
        check {![file exists [file join $::m002_report_dir candidate_cut_test_closed.txt]]} "Invalid coverage wrote completed marker"
        puts "CASE\t$name\tPASS\tEXPECTED_UNQUALIFIED\t$value"
        continue
    }
    if {$caught} {puts "CASE\t$name\tFAIL\t$value";puts [dict get $options -errorinfo];continue}
    set ok [catch {
        set nets [readtsv [file join $::m002_report_dir candidate_nets_test.tsv]]
        set endpoints [readtsv [file join $::m002_report_dir candidate_endpoints_test.tsv]]
        set local [readtsv [file join $::m002_report_dir candidate_pins_test.tsv]]
        set timing [readtsv [file join $::m002_report_dir candidate_boundary_timing_scope_test.tsv]]
        check {[llength $nets]==1} "Alias closure should produce one canonical net"
        set net [lindex $nets 0]
        check {[dict get $net exported_endpoint_rows]==[llength $endpoints]} "Exported count mismatch"
        check {$::roleQueries==1} "Expected exactly one native role query"
        if {$::forbidPeerRich} {
            check {$::fullQueries==0} "Ingress used full query"
            check {[dict get $net full_net_endpoint_coverage] eq "false"} "Wrong full-net flag"
            foreach row $endpoints {check {[dict get $row NAME] ne "peer/D"} "Peer survived pruning"}
        } else {check {$::fullQueries==1} "Fallback or egress did not query full scope"}
        if {$name eq "egress"} {
            set actual [lsort [dict keys [dict get $::slr2::boundaryPins EGRESS]]]
            check {$actual eq {external/O peer/D}} "Egress included inside LOAD or missed outside LOAD"
        } elseif {$name in {ingress top_load top_driver constant_driver disconnected}} {
            check {[dict keys [dict get $::slr2::boundaryPins INGRESS]] eq "candidate/D"} "Ingress query set changed"
        } elseif {$name eq "dsp_copy"} {
            check {[dict size $::slr2::directedI]==4} "DSP/origin-copy actual leaf coverage incomplete"
            check {![dict exists $::slr2::directedI dsp/A]} "Nonleaf DSP interface treated as leaf"
            check {[dict exists $::slr2::directedI origin_copy/D]} "Root-external P copy omitted"
        } else {check {[dict exists $::slr2::boundaryPins UNRESOLVED] || $name eq "role_error"} "Ambiguous net silently resolved"}
        if {$name eq "constant_driver"} {check {![dict exists $::slr2::directedI candidate_gnd/G]} "RAW-only GND migrated"}
        if {$name eq "disconnected"} {
            set found 0
            foreach row $local {if {[dict get $row NAME] eq "candidate/CE" && [dict get $row connection_status] eq "DISCONNECTED"} {set found 1}}
            check {$found} "Disconnected local pin omitted"
        }
        check {[llength $::adapterCalls]==1} "Expected post-export adapter call"
    } issue options]
    puts "CASE\t$name\t[expr {$ok ? {FAIL} : {PASS}}]\t$issue"
    if {$ok} {puts [dict get $options -errorinfo]}
}
