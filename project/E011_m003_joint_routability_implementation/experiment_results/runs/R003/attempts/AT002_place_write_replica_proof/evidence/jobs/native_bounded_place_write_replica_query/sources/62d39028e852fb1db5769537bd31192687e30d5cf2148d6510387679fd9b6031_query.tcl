# Read only the saved successful place checkpoint and explicitly selected cells.
set here [file dirname [file normalize [info script]]]
set scripts [file normalize [file join $here ../../../hardware/vivado/scripts]]
source [file join $scripts m003_joint_checks.tcl]
source [file join $here targets.tcl]
set_param general.maxThreads 8
set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1
set ::m003_restore_registry_verified 1
set before $::m003::apply_attempts
open_checkpoint $::env(HAP_QUERY_CHECKPOINT)
if {$::m003::apply_attempts != $before} {error "Read-only proof reapplied constraints"}
set out $::env(HAP_REPORT_DIR)
set h [open [file join $out selected_state_and_root_pins.jsonl] {WRONLY CREAT EXCL}]
proc proof_fields {object properties} {
    set row [dict create]
    foreach property $properties {dict set row $property [m003::prop $object $property]}
    return $row
}
proc proof_pin {cell terminal kind} {
    set object [m003::one get_cells $cell]
    set pin [get_pins -quiet -of_objects $object -filter [format {REF_PIN_NAME == "%s"} $terminal]]
    m003::exact_count $pin 1 "bounded proof $cell/$terminal"
    if {[get_property NAME $pin] ne "$cell/$terminal"} {error "Proof pin identity differs"}
    set nets [get_nets -quiet -segments -of_objects $pin]
    if {![llength $nets]} {error "Proof pin disconnected $pin"}
    set drivers [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]
    set owners {};set refs {}
    foreach driver $drivers {
        set owner [get_cells -quiet -of_objects $driver]
        m003::exact_count $owner 1 "proof actual leaf driver owner"
        lappend owners [get_property NAME $owner]
        lappend refs [get_property REF_NAME $owner]
    }
    set ports [get_ports -quiet -of_objects $nets]
    set row [dict merge [dict create kind $kind cell $cell terminal $terminal pin [get_property NAME $pin] nets [lsort -unique [get_property NAME $nets]] drivers [get_property NAME $drivers] driver_cells $owners driver_refs $refs primary_ports [get_property NAME $ports] primary_port_directions [get_property DIRECTION $ports]] [proof_fields $pin {DIRECTION REF_PIN_NAME IS_INVERTED}]]
    puts $::h [m003::jobject $row]
    if {$kind eq "state_pin" && $terminal eq "C"} {
        set clocks [get_clocks -quiet -of_objects $pin]
        m003::exact_count $clocks 1 "selected state actual clock"
        foreach clock $clocks {
            puts $::h [m003::jobject [dict merge [dict create kind state_clock cell $cell clock [get_property NAME $clock]] [proof_fields $clock {NAME PERIOD WAVEFORM IS_GENERATED MASTER_CLOCK SOURCE_PINS}]]]
        }
    }
}
foreach cell $proof_cells {
    set object [m003::one get_cells $cell]
    puts $h [m003::jobject [dict merge [dict create kind cell NAME $cell] [proof_fields $object {REF_NAME INIT IS_C_INVERTED IS_CLR_INVERTED IS_D_INVERTED IS_CE_INVERTED ORIG_CELL_NAME ORIG_REF_NAME IS_REPLICATED IS_SEQUENTIAL IS_PRIMITIVE DONT_TOUCH LOC BEL}]]]
    set parent [m003::one get_cells [file dirname $cell]]
    puts $h [m003::jobject [dict merge [dict create kind parent cell $cell] [proof_fields $parent {NAME REF_NAME DONT_TOUCH}]]]
    foreach terminal {D C CE CLR} {proof_pin $cell $terminal state_pin}
}
foreach target $proof_root_pins {
    lassign $target cell terminal
    proof_pin $cell $terminal memory_root_pin
}
close $h
set h [open [file join $out read_only_complete.json] {WRONLY CREAT EXCL}]
puts $h [m003::jobject [dict create completed true actual_selected_cells [llength $proof_cells] actual_selected_root_pins [llength $proof_root_pins] before_apply $before after_apply $::m003::apply_attempts checkpoint $::env(HAP_QUERY_CHECKPOINT) new_place false physopt false route false]]
close $h
close_design
puts "M003_BOUNDED_PLACED_WRITE_REPLICA_QUERY_COMPLETED"
