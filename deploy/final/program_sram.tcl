# Explicit volatile SRAM programming of the released final 80 MHz image.
# -tclargs SERVER_URL EXACT_TARGET EXACT_DEVICE FULL_BIT_PATH ?PROFILE?
source [file join [file dirname [info script]] program_common.tcl]
if {$argc ni {4 5}} {error {Usage: SERVER_URL EXACT_TARGET EXACT_DEVICE FULL_BIT_PATH ?all-dsp|legacy?}}
lassign $argv server target_name device_name bit_arg profile
if {$argc == 4} {set profile all-dsp}
set identity [deployment_profile $profile]
set bit [verify_final_bit $bit_arg $profile]
set code [catch {
    open_hw_manager
    connect_hw_server -url $server
    set target [exact_object [get_hw_targets] $target_name target]
    current_hw_target $target
    open_hw_target
    set device [require_unique_vu9p [get_hw_devices] $device_name]
    puts "FINAL_PROGRAM_IDENTITY profile=[list $profile] sha256=[dict get $identity sha256] server=[list $server] target=[list $target] device=[list $device] part=[list [device_part $device]] bit=[list $bit]"
    set_property PROGRAM.FILE $bit $device
    program_hw_devices $device
    refresh_hw_device -update_hw_probes false $device
    puts {FINAL_SRAM_PROGRAM_COMPLETED; READ_ONLY_FINAL_ABI_PREFLIGHT_REQUIRED}
} problem options]
hw_cleanup
if {$code} {return -options $options $problem}
