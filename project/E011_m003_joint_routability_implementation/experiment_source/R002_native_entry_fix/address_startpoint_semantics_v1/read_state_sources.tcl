# Preserve raw all_fanin semantics and actual Q membership for helper D inputs.
# The sibling library is pinned as an input, loaded without its native entry.
set ::env(M003_URAM_ADDRESS_LIBRARY_ONLY) 1
source [file join [file dirname [file normalize [info script]]] ../uram_address_diagnostic_v1/read_uram_address.tcl]
namespace eval m003_state_diag {
    variable expected_helpers_per_slice 17
    variable expected_memories 80
    variable scope {inst/u_core/u_compute/u_attention/u_meta/}
}
interp alias {} m003_state_diag::q {} m003_uram_diag::quote
interp alias {} m003_state_diag::arr {} m003_uram_diag::array
interp alias {} m003_state_diag::bounded {} m003_uram_diag::bounded
interp alias {} m003_state_diag::names {} m003_uram_diag::names
interp alias {} m003_state_diag::event {} m003_uram_diag::event
proc m003_state_diag::one_pin {cell terminal} {
    set pins [get_pins -quiet -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $terminal]]
    if {[llength $pins] != 1} {error "Non-singleton required pin: $cell/$terminal"}
    return [lindex $pins 0]
}
proc m003_state_diag::run {report} {
    variable expected_helpers_per_slice;variable expected_memories;variable scope
    set ::m003_uram_diag::progress [open [file join $report diagnostic_progress.jsonl] {WRONLY CREAT EXCL}]
    event diagnostic_begin constraint_apply_requested 0 new_synthesis_launched 0
    set ff_filter [format {IS_PRIMITIVE == 1 && (REF_NAME == FDCE || REF_NAME == FDRE) && NAME =~ "%s*u_addr/address_r_reg*"} $scope]
    set cells [bounded [get_cells -quiet -hier -filter $ff_filter] helper_state 1]
    if {[llength $cells] != 2*$expected_helpers_per_slice} {error "Helper state count differs: [llength $cells]"}
    set identities [dict create];set slices [dict create 0 0 1 0]
    foreach cell $cells {
        set name [get_property NAME $cell];set ref [get_property REF_NAME $cell]
        if {[string first $scope $name] != 0 || ![regexp {g_slice\[([01])\].*u_addr/address_r_reg\[(\d+)\]$} $name -> slice bit] || $bit >= $expected_helpers_per_slice || $ref ni {FDCE FDRE} || [dict exists $identities $slice,$bit]} {error "Helper state identity differs: $name/$ref"}
        dict set identities $slice,$bit $name;dict incr slices $slice
    }
    foreach slice {0 1} {if {[dict get $slices $slice] != $expected_helpers_per_slice} {error "Helper slice count differs: $slice"}}
    set partial [file join $report helper_D_sources.jsonl.partial]
    set h [open $partial {WRONLY CREAT EXCL}];set count 0
    foreach cell $cells {
        set name [get_property NAME $cell]
        regexp {g_slice\[([01])\].*u_addr/address_r_reg\[(\d+)\]$} $name -> slice bit
        event helper_begin cell $name
        set dp [one_pin $cell D];set qp [one_pin $cell Q]
        set points [bounded [all_fanin -quiet -flat -startpoints_only -to $dp] raw_startpoints]
        set cone [bounded [all_fanin -quiet -flat -to $dp] full_fanin]
        set only_cells [bounded [all_fanin -quiet -flat -startpoints_only -only_cells -to $dp] raw_startpoint_cells]
        set cone_names [names $cone];set cone_set [dict create]
        foreach value $cone_names {dict set cone_set $value 1}
        set source_rows [list]
        foreach point $points {
            set raw [get_property NAME $point];set class [get_property CLASS $point]
            set owners [list];set q_names [list];set owner_names [list];set owner_refs [list];set q_in_cone [list]
            if {[string tolower $class] eq "pin"} {
                set owners [bounded [get_cells -quiet -of_objects $point] source_pin_owner 1]
                if {[llength $owners] != 1} {error "Non-singleton startpoint owner: $raw"}
                set owner_names [names $owners];set owner_refs [get_property REF_NAME $owners]
                set qs [bounded [get_pins -quiet -of_objects $owners -filter {REF_PIN_NAME == Q}] source_owner_Q]
                foreach qpin $qs {
                    set qname [get_property NAME $qpin];lappend q_names $qname
                    lappend q_in_cone [expr {[dict exists $cone_set $qname] ? 1 : 0}]
                }
            }
            lappend source_rows "\{\"raw_name\":[q $raw],\"class\":[q $class],\"owner_names\":[arr $owner_names],\"owner_refs\":[arr $owner_refs],\"owner_Q_pins\":[arr $q_names],\"owner_Q_in_full_fanin\":[arr $q_in_cone]\}"
        }
        set only_cell_refs [list]
        foreach source $only_cells {lappend only_cell_refs [get_property REF_NAME $source]}
        set qname [get_property NAME $qp]
        set fields [list "\"cell\":[q $name]" "\"slice\":$slice" "\"bit\":$bit" "\"D_pin\":[q [get_property NAME $dp]]" "\"own_Q_pin\":[q $qname]" "\"own_Q_in_full_fanin\":[expr {[dict exists $cone_set $qname] ? 1 : 0}]" "\"raw_startpoints\":[arr [names $points]]" "\"raw_full_fanin\":[arr $cone_names]" "\"raw_startpoint_only_cells\":[arr [names $only_cells]]" "\"raw_startpoint_only_cell_refs\":[arr $only_cell_refs]" "\"actual_source_owner_facts\":\[[join $source_rows ,]\]"]
        puts $h "\{[join $fields ,]\}";flush $h;incr count
        event helper_closed cell $name rows $count
    }
    close $h;file rename $partial [file join $report helper_D_sources.jsonl]
    set memories [bounded [get_cells -quiet -hier -filter [format {IS_PRIMITIVE == 1 && REF_NAME =~ "URAM*" && NAME =~ "%s*"} $scope]] selected_URAM 1]
    if {[llength $memories] != $expected_memories} {error "URAM clock inventory differs: [llength $memories]"}
    set partial [file join $report uram_clock_sources.jsonl.partial]
    set h [open $partial {WRONLY CREAT EXCL}];set clocks 0
    foreach cell $memories {
        set pin [one_pin $cell CLK]
        set nets [bounded [get_nets -quiet -segments -of_objects $pin] clock_nets]
        set drivers [list];set ports [list]
        if {[llength $nets]} {
            set drivers [bounded [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}] clock_drivers]
            set ports [bounded [get_ports -quiet -of_objects $nets] clock_primary_ports]
        }
        set dirs [list];foreach port $ports {lappend dirs [get_property DIRECTION $port]}
        set fields [list "\"cell\":[q [get_property NAME $cell]]" "\"CLK_pin\":[q [get_property NAME $pin]]" "\"nets\":[arr [names $nets]]" "\"leaf_drivers\":[arr [names $drivers]]" "\"primary_ports\":[arr [names $ports]]" "\"primary_port_directions\":[arr $dirs]"]
        puts $h "\{[join $fields ,]\}";flush $h;incr clocks
    }
    close $h;file rename $partial [file join $report uram_clock_sources.jsonl]
    set h [open [file join $report diagnostic_complete.json] {WRONLY CREAT EXCL}]
    puts $h "\{\"execution\":\"completed\",\"helper_D_rows\":$count,\"URAM_clock_rows\":$clocks,\"constraint_apply_requested\":false,\"new_synthesis_launched\":false,\"raw_values_rewritten\":false,\"G4\":false\}";close $h
    event diagnostic_complete helper_rows $count clock_rows $clocks
    close $::m003_uram_diag::progress
}
if {![info exists ::env(M003_STATE_SOURCE_LIBRARY_ONLY)]} {
    set_param general.maxThreads 8
    open_checkpoint [lindex $argv 0]
    if {[catch {m003_state_diag::run $::env(HAP_REPORT_DIR)} message options]} {
        set h [open [file join $::env(HAP_REPORT_DIR) diagnostic_error_info.txt] {WRONLY CREAT EXCL}]
        puts $h [dict get $options -errorinfo];close $h
        return -options $options $message
    }
    close_design
    puts M003_FRESH_CORE_STATE_SOURCE_DIAGNOSTIC_COMPLETED;flush stdout
}
