# Vivado 2022.2: -mode batch -source probe_jtag.tcl -tclargs HOST:PORT ?EXACT_TARGET?
# Enumerates the JTAG chain only. No reset/program/flash/AXI transactions.
source [file join [file dirname [info script]] hw_common.tcl]
if {$argc < 1 || $argc > 2} { error "Usage: SERVER_URL ?EXACT_TARGET_NAME?" }
set server [lindex $argv 0]
set code [catch {
    open_hw_manager
    connect_hw_server -url $server
    set targets [get_hw_targets]
    foreach target $targets { puts "BOARD_PREFLIGHT_TARGET [list $target]" }
    if {$argc == 2} {
        set selected [exact_object $targets [lindex $argv 1] target]
        current_hw_target $selected
        open_hw_target
        foreach device [get_hw_devices] {
            puts "BOARD_PREFLIGHT_DEVICE [list $device] PART [list [device_part $device]]"
            report_property $device
        }
    }
    puts "BOARD_PREFLIGHT_PROBE_COMPLETE"
} problem options]
hw_cleanup
if {$code} { return -options $options $problem }
