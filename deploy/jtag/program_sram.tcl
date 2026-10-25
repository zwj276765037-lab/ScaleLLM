# PREPARED ONLY: programs volatile FPGA SRAM when explicitly executed.
# -tclargs SERVER_URL EXACT_TARGET EXACT_DEVICE FULL_BIT_PATH
# No first-device selection, flash programming, reset, or PCIe write is included.
source [file join [file dirname [info script]] hw_common.tcl]
if {$argc != 4} { error "Usage: SERVER_URL EXACT_TARGET_NAME EXACT_DEVICE_NAME FULL_BIT_PATH" }
lassign $argv server target_name device_name bit_arg
set bit [verify_engineering_bit $bit_arg]
set code [catch {
    open_hw_manager
    connect_hw_server -url $server
    set target [exact_object [get_hw_targets] $target_name target]
    current_hw_target $target
    open_hw_target
    set device [require_unique_vu9p [get_hw_devices] $device_name]
    puts "BOARD_PROGRAM_IDENTITY server=[list $server] target=[list $target] device=[list $device] part=[list [device_part $device]] bit=[list $bit]"
    set_property PROGRAM.FILE $bit $device
    program_hw_devices $device
    puts "BOARD_PROGRAM_COMMAND_COMPLETED"
} problem options]
hw_cleanup
if {$code} { return -options $options $problem }
