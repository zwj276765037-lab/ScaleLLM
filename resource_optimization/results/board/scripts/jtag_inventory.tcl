open_hw_manager
connect_hw_server -url localhost:3121
set targets [get_hw_targets]
puts "BOARD_TEST_TARGET_COUNT=[llength $targets]"
foreach target $targets {
    puts "BOARD_TEST_TARGET=[list $target]"
    foreach property {IS_OPENED IS_LOCKED FREQUENCY NAME} {
        if {[lsearch -exact [list_property $target] $property] >= 0} {puts "TARGET_PROPERTY $property=[get_property $property $target]"}
    }
}
if {[llength $targets] != 1} {error {Expected one independently identified JTAG target}}
set target [lindex $targets 0]
current_hw_target $target
open_hw_target
foreach device [get_hw_devices] {
    puts "BOARD_TEST_DEVICE=[list $device]"
    foreach property {PART NAME IDCODE REGISTER.IR REGISTER.BYPASS IS_PROGRAMMED} {
        if {[lsearch -exact [list_property $device] $property] >= 0} {puts "DEVICE_PROPERTY $property=[get_property $property $device]"}
    }
}
close_hw_target
disconnect_hw_server
close_hw_manager
puts {BOARD_TEST_JTAG_INVENTORY_COMPLETE}
