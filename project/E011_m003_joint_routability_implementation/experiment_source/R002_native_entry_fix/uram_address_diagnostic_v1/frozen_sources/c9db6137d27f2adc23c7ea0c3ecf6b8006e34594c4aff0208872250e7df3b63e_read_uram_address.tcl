# Read only the original fresh core's selected URAM address connectivity.
# No production helpers, constraints, synthesis, or checkpoint writes.
namespace eval m003_uram_diag {
    variable expected_per_slice 40
    variable expected_pins 92
    variable expected_mode_pins 2
    variable max_auxiliary_pins 1024
    variable max_collection 131072
    variable scope {inst/u_core/u_compute/u_attention/u_meta/}
}
proc m003_uram_diag::quote {value} {
    set out {"}
    foreach ch [split $value {}] {
        scan $ch %c code
        if {$ch eq "\""} {append out {\"}} elseif {$ch eq "\\"} {append out {\\}} elseif {$code < 32} {append out [format {\u%04x} $code]} else {append out $ch}
    }
    append out {"};return $out
}
proc m003_uram_diag::array {values} {
    set rows {};foreach value $values {lappend rows [quote $value]}
    return "\[[join $rows ,]\]"
}
proc m003_uram_diag::event {kind args} {
    variable progress
    set pairs [list "\"event\":[quote $kind]" "\"clock_ms\":[clock milliseconds]"]
    foreach {key value} $args {lappend pairs "[quote $key]:[quote $value]"}
    puts $progress "\{[join $pairs ,]\}";flush $progress
    if {$kind ne {pin_begin}} {puts "M003_URAM_DIAG $kind $args";flush stdout}
}
proc m003_uram_diag::bounded {objects label {required 0}} {
    variable max_collection
    set n [llength $objects]
    if {$n > $max_collection || ($required && !$n) || [llength [lsort -unique $objects]] != $n} {error "Invalid bounded collection $label: $n"}
    return $objects
}
proc m003_uram_diag::names {objects} {
    if {![llength $objects]} {return [list]}
    return [get_property NAME $objects]
}
proc m003_uram_diag::run {report} {
    variable expected_per_slice;variable expected_pins;variable expected_mode_pins;variable max_auxiliary_pins;variable scope;variable progress
    set progress [open [file join $report diagnostic_progress.jsonl] {WRONLY CREAT EXCL}]
    event diagnostic_begin constraint_apply_requested 0 new_synthesis_launched 0
    set filter [format {IS_PRIMITIVE == 1 && REF_NAME =~ "URAM*" && NAME =~ "%s*"} $scope]
    set cells [bounded [get_cells -quiet -hier -filter $filter] selected_URAM 1]
    if {[llength $cells] != 2*$expected_per_slice} {error "Selected URAM count differs: [llength $cells]"}
    set slices [dict create 0 0 1 0];set identities [dict create]
    foreach cell $cells {
        set name [get_property NAME $cell];set ref [get_property REF_NAME $cell]
        if {[string first $scope $name] != 0 || ![regexp {g_slice\[([01])\]} $name -> slice] || ![string match URAM* $ref] || [dict exists $identities $name]} {error "Selected URAM identity differs: $name/$ref"}
        dict set identities $name [list $slice $ref];dict incr slices $slice
    }
    foreach slice {0 1} {if {[dict get $slices $slice] != $expected_per_slice} {error "URAM slice count differs: $slice"}}
    event cells_resolved count [llength $cells] filter $filter
    set partial [file join $report uram_address_pins.jsonl.partial]
    set h [open $partial {WRONLY CREAT EXCL}]
    set config_partial [file join $report uram_configs.jsonl.partial]
    set config_h [open $config_partial {WRONLY CREAT EXCL}]
    set mode_partial [file join $report uram_mode_pins.jsonl.partial]
    set mode_h [open $mode_partial {WRONLY CREAT EXCL}]
    set aux_partial [file join $report uram_auxiliary_pins.jsonl.partial]
    set aux_h [open $aux_partial {WRONLY CREAT EXCL}]
    set rows 0;set empty 0;set constant_empty 0;set dynamic 0;set auxiliary_rows 0
    foreach cell $cells {
        set name [get_property NAME $cell];lassign [dict get $identities $name] slice ref
        event cell_begin cell $name slice $slice
        set properties [list "\"cell\":[quote $name]" "\"slice\":$slice"]
        foreach property [lsort [list_property $cell]] {
            if {[string match CONFIG.* $property] || [regexp {CAS|SELF|ADDR|MASK|OREG|IREG|WRITE|READ|BWE|CLOCK} $property]} {
                lappend properties "[quote $property]:[quote [get_property $property $cell]]"
            }
        }
        puts $config_h "\{[join $properties ,]\}";flush $config_h
        set modes [bounded [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN && (REF_PIN_NAME == RDB_WR_A || REF_PIN_NAME == RDB_WR_B)}] mode_pins]
        if {[llength $modes] != $expected_mode_pins} {error "Physical mode pin count differs: $name/[llength $modes]"}
        set mode_names [dict create]
        foreach mode $modes {
            set terminal [get_property REF_PIN_NAME $mode]
            if {$terminal ni {RDB_WR_A RDB_WR_B} || [dict exists $mode_names $terminal]} {error "Physical mode terminal differs: $name/$terminal"}
            dict set mode_names $terminal 1
            set mode_nets [bounded [get_nets -quiet -segments -of_objects $mode] mode_nets 1]
            set mode_drivers [bounded [get_pins -quiet -leaf -of_objects $mode_nets -filter {DIRECTION == OUT}] mode_drivers]
            set mode_refs {}
            foreach driver $mode_drivers {
                set owner [bounded [get_cells -quiet -of_objects $driver] mode_owner 1]
                if {[llength $owner] != 1} {error "Mode driver owner is not singleton: $driver"}
                lappend mode_refs [get_property REF_NAME $owner]
            }
            set values [list "\"cell\":[quote $name]" "\"slice\":$slice" "\"pin\":[quote $terminal]" "\"nets\":[array [names $mode_nets]]" "\"drivers\":[array [names $mode_drivers]]" "\"driver_refs\":[array $mode_refs]"]
            puts $mode_h "\{[join $values ,]\}";flush $mode_h
        }
        set auxiliary_count 0
        foreach aux [bounded [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}] all_memory_inputs] {
            set terminal [get_property REF_PIN_NAME $aux]
            if {[string match *ADDR* $terminal] || $terminal in {RDB_WR_A RDB_WR_B}} {continue}
            if {![string match *EN* $terminal] && ![string match *WE* $terminal] && ![string match *CLK* $terminal] && ![string match *RDB_WR* $terminal] && ![string match CAS* $terminal]} {continue}
            incr auxiliary_count
            if {$auxiliary_count > $max_auxiliary_pins} {error "Auxiliary input bound exceeded: $name/$auxiliary_count"}
            set aux_nets [bounded [get_nets -quiet -segments -of_objects $aux] auxiliary_nets]
            set aux_drivers [list]
            if {[llength $aux_nets]} {set aux_drivers [bounded [get_pins -quiet -leaf -of_objects $aux_nets -filter {DIRECTION == OUT}] auxiliary_drivers]}
            set aux_refs {};set aux_owners {}
            foreach driver $aux_drivers {
                set owner [bounded [get_cells -quiet -of_objects $driver] auxiliary_owner 1]
                if {[llength $owner] != 1} {error "Auxiliary driver owner is not singleton: $driver"}
                lappend aux_refs [get_property REF_NAME $owner];lappend aux_owners [get_property NAME $owner]
            }
            set values [list "\"cell\":[quote $name]" "\"slice\":$slice" "\"pin\":[quote $terminal]" "\"pin_name\":[quote [get_property NAME $aux]]" "\"nets\":[array [names $aux_nets]]" "\"drivers\":[array [names $aux_drivers]]" "\"driver_cells\":[array $aux_owners]" "\"driver_refs\":[array $aux_refs]"]
            puts $aux_h "\{[join $values ,]\}";flush $aux_h;incr auxiliary_rows
        }
        set pins [bounded [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN && REF_PIN_NAME =~ "*ADDR*"}] address_pins 1]
        if {[llength $pins] != $expected_pins} {error "Physical address pin count differs: $name/[llength $pins]"}
        set terminals [dict create]
        foreach pin $pins {
            set pinname [get_property NAME $pin];set terminal [get_property REF_PIN_NAME $pin]
            if {![regexp {^(CAS_IN_)?ADDR_[AB]\[(\d+)\]$} $terminal -> cascade bit] || $bit > 22 || [dict exists $terminals $terminal]} {error "Physical address terminal differs: $name/$terminal"}
            dict set terminals $terminal 1;event pin_begin cell $name pin $terminal
            set begin [clock milliseconds]
            set nets [bounded [get_nets -quiet -segments -of_objects $pin] address_nets]
            set drivers [list]
            if {[llength $nets]} {set drivers [bounded [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}] direct_drivers]}
            set refs {};set ownernames {}
            foreach driver $drivers {
                set owner [bounded [get_cells -quiet -of_objects $driver] driver_owner 1]
                if {[llength $owner] != 1} {error "Driver owner is not singleton: $driver"}
                lappend refs [get_property REF_NAME $owner];lappend ownernames [get_property NAME $owner]
            }
            set fanin_begin [clock milliseconds]
            set points [bounded [all_fanin -quiet -flat -startpoints_only -to $pin] native_startpoints]
            set fanin_ms [expr {[clock milliseconds]-$fanin_begin}]
            set isconstant [expr {[llength $refs] == 1 && [lindex $refs 0] in {GND VCC}}]
            set constant_value null
            if {$isconstant} {set constant_value [expr {[lindex $refs 0] eq {VCC} ? 1 : 0}]}
            if {![llength $points]} {incr empty;if {$isconstant} {incr constant_empty}} else {incr dynamic}
            set values [list "\"slice\":$slice" "\"cell\":[quote $name]" "\"ref\":[quote $ref]" "\"pin\":[quote $terminal]" "\"pin_name\":[quote $pinname]" "\"nets\":[array [names $nets]]" "\"drivers\":[array [names $drivers]]" "\"driver_cells\":[array $ownernames]" "\"driver_refs\":[array $refs]" "\"startpoints\":[array [names $points]]" "\"native_startpoint_count\":[llength $points]" "\"single_constant_driver\":$isconstant" "\"constant_value_from_single_driver_ref\":$constant_value" "\"fanin_ms\":$fanin_ms" "\"row_ms\":[expr {[clock milliseconds]-$begin}]"]
            puts $h "\{[join $values ,]\}";flush $h;incr rows
        }
        event cell_closed cell $name address_pins [dict size $terminals] total_rows $rows
    }
    close $h;file rename $partial [file join $report uram_address_pins.jsonl]
    close $config_h;file rename $config_partial [file join $report uram_configs.jsonl]
    close $mode_h;file rename $mode_partial [file join $report uram_mode_pins.jsonl]
    close $aux_h;file rename $aux_partial [file join $report uram_auxiliary_pins.jsonl]
    set complete [open [file join $report diagnostic_complete.json] {WRONLY CREAT EXCL}]
    puts $complete "\{\"execution\":\"completed\",\"cells\":[llength $cells],\"rows\":$rows,\"auxiliary_rows\":$auxiliary_rows,\"zero_startpoint_rows\":$empty,\"zero_startpoint_single_constant_driver_rows\":$constant_empty,\"nonempty_startpoint_rows\":$dynamic,\"constraint_apply_requested\":false,\"new_synthesis_launched\":false,\"G4\":false\}";close $complete
    event diagnostic_complete rows $rows;close $progress
}
if {![info exists ::env(M003_URAM_ADDRESS_LIBRARY_ONLY)]} {
    set_param general.maxThreads 8
    open_checkpoint [lindex $argv 0]
    if {[catch {m003_uram_diag::run $::env(HAP_REPORT_DIR)} message options]} {
        set h [open [file join $::env(HAP_REPORT_DIR) diagnostic_error_info.txt] {WRONLY CREAT EXCL}]
        puts $h [dict get $options -errorinfo];close $h
        return -options $options $message
    }
    close_design
    puts M003_FRESH_CORE_URAM_ADDRESS_DIAGNOSTIC_COMPLETED;flush stdout
}
