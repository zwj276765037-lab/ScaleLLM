# Read-only evidence for the fixed final routed checkpoint and exact bus-skew endpoints.
set out $::env(AUDIT_OUT)
set dcp $::env(AUDIT_DCP)
set digest $::env(AUDIT_DCP_SHA256)
if {[lindex [exec sha256sum -- $dcp] 0] ne $digest} {error {Final checkpoint hash mismatch}}
set_param general.maxThreads 32
source [file join $::env(HAP_HW_ROOT) vivado scripts release_reports.tcl]
open_checkpoint $dcp
set original_failed [catch {require_design_identity} original_message]
set design [current_design]
set loaded_top [get_property TOP $design]
set loaded_name [get_property NAME $design]
set loaded_part [get_property PART $design]
set stream [open [file join $out loaded_identity.txt] w]
puts $stream "TOP=$loaded_top\nNAME=$loaded_name\nPART=$loaded_part\nVERSION=[version -short]\nORIGINAL_GUARD_FAILED=$original_failed\nORIGINAL_GUARD_MESSAGE=$original_message"
close $stream
if {[version -short] ne {2025.2} || $loaded_part ne {xcvu9p-flga2104-2L-e}} {error {Loaded tool or part mismatch}}
if {$loaded_top ne {scalellm_final_decode16_bd_wrapper}} {error {Loaded netlist TOP mismatch}}
foreach {pin expected} {core_clk 12.5 ddr0_clk 5.0 ddr1_clk 5.0} {
    set pins [get_pins -quiet scalellm_final_decode16_bd_i/core/inst/$pin]
    set clocks [get_clocks -quiet -of_objects $pins]
    if {[llength $pins] != 1 || [llength $clocks] != 1} {error "Missing unique clock at $pin"}
    if {abs(double([get_property PERIOD $clocks])-$expected)>0.001} {error "Clock period mismatch at $pin"}
}
if {$original_failed && $original_message ne {Top mismatch}} {error $original_message}
set blackboxes [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}]
if {[llength $blackboxes]} {error {Final checkpoint contains blackboxes}}
if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {error {Bus-skew audit requires full error-free routing}}
report_bus_skew -file [file join $out bus_skew.rpt]

proc relevant_properties {object} {
    set available [list_property $object]
    set result {}
    foreach property {NAME CLASS TYPE REF_NAME ORIG_REF_NAME INIT DIRECTION REF_PIN_NAME IS_CONSTANT CONSTANT_VALUE IS_TIED_TO_GROUND IS_TIED_TO_VCC IS_GND IS_VCC IS_GLOBAL IS_CLOCK IS_PRIMITIVE} {
        if {[lsearch -exact $available $property] >= 0} {
            lappend result "$property=[get_property $property $object]"
        }
    }
    return [join $result { | }]
}
set stream [open $::env(AUDIT_PIN_LIST) r]
set pin_names [split [string trim [read $stream]] "\n"]
close $stream
set stream [open [file join $out endpoint_identity.tsv] w]
puts $stream "requested_pin\tpin_match_count\tcell_match_count\tobject_kind\tobject_name\tproperties"
foreach pin_name $pin_names {
    # Exact NAME equality treats generated-array brackets as literal text.
    set pins [get_pins -hierarchical -quiet -filter "NAME == \"$pin_name\""]
    set cell_name [file dirname $pin_name]
    set cells [get_cells -hierarchical -quiet -filter "NAME == \"$cell_name\""]
    puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tQUERY\t$pin_name\t"
    foreach cell $cells {puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tCELL\t[get_property NAME $cell]\t[relevant_properties $cell]"}
    foreach pin $pins {
        puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tPIN\t[get_property NAME $pin]\t[relevant_properties $pin]"
        set current_nets [get_nets -quiet -of_objects $pin]
        set segments [get_nets -quiet -segments -of_objects $pin]
        set nets [lsort -unique [concat $current_nets $segments]]
        puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tNET_COUNTS\t\tcurrent=[llength $current_nets] segments=[llength $segments] unique=[llength $nets]"
        foreach net $nets {
            set kind [expr {[lsearch -exact $current_nets $net] >= 0 ? {CURRENT_NET} : {NET_SEGMENT}}]
            puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\t$kind\t[get_property NAME $net]\t[relevant_properties $net]"
        }
        set drivers {}
        if {[llength $nets]} {set drivers [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == OUT}]}
        foreach driver [lsort -unique $drivers] {
            puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tDRIVER_PIN\t[get_property NAME $driver]\t[relevant_properties $driver]"
            foreach driver_cell [get_cells -quiet -of_objects $driver] {
                puts $stream "$pin_name\t[llength $pins]\t[llength $cells]\tDRIVER_CELL\t[get_property NAME $driver_cell]\t[relevant_properties $driver_cell]"
            }
        }
    }
}
close $stream
if {[lindex [exec sha256sum -- $dcp] 0] ne $digest} {error {Read-only source checkpoint changed}}
close_design
puts {FINAL_BUS_SKEW_AUDIT_CAPTURED}
