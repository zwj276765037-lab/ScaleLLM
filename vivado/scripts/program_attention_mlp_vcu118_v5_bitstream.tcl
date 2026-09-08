foreach required {
    HAP_BITSTREAM HAP_EXPECTED_BITSTREAM_SHA256 HAP_PROGRAM_REPORT
    HAP_HW_SERVER_URL HAP_HW_TARGET_INDEX HAP_HW_DEVICE_FILTER
} {
    if {![info exists ::env($required)] || $::env($required) eq ""} {
        error "$required is required"
    }
}

set bitstream [file normalize $::env(HAP_BITSTREAM)]
set expected_sha $::env(HAP_EXPECTED_BITSTREAM_SHA256)
set report [file normalize $::env(HAP_PROGRAM_REPORT)]
set server $::env(HAP_HW_SERVER_URL)
set target_index $::env(HAP_HW_TARGET_INDEX)
set device_filter $::env(HAP_HW_DEVICE_FILTER)

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
if {![file exists $bitstream] || ![file isfile $bitstream] ||
    [file size $bitstream] == 0} {
    error "Missing or empty V5 bitstream: $bitstream"
}
if {![regexp {^[0-9a-f]{64}$} $expected_sha]} {
    error "Malformed expected V5 bitstream SHA256"
}
proc bitstream_sha256 {path} {
    set digest [lindex [exec sha256sum -- $path] 0]
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "Could not compute bitstream SHA256: $path"
    }
    return $digest
}
if {[bitstream_sha256 $bitstream] ne $expected_sha} {
    error "V5 bitstream SHA256 disagrees with independently audited evidence"
}
if {![string is integer -strict $target_index] || $target_index < 0} {
    error "HAP_HW_TARGET_INDEX must be a nonnegative integer"
}

file mkdir [file dirname $report]
open_hw_manager
connect_hw_server -url $server
set targets [get_hw_targets *]
if {$target_index >= [llength $targets]} {
    error "Hardware target index $target_index is unavailable: $targets"
}
set target [lindex $targets $target_index]
current_hw_target $target
open_hw_target

set matches {}
foreach device [get_hw_devices *] {
    set name [get_property NAME $device]
    set part ""
    catch {set part [get_property PART $device]}
    puts "Detected hw device: name=$name part=$part"
    if {[string match -nocase "*$device_filter*" $name] ||
        [string match -nocase "*$device_filter*" $part]} {
        lappend matches $device
    }
}
if {[llength $matches] != 1} {
    error "Expected exactly one '$device_filter' device, got: $matches"
}
set device [lindex $matches 0]
set part [get_property PART $device]
if {![string match -nocase "*xcvu9p*" $part]} {
    error "Selected hardware is not a VCU118 VU9P: $part"
}

current_hw_device $device
set_property PROGRAM.FILE $bitstream $device
program_hw_devices $device
refresh_hw_device $device
set programmed_file [file normalize [get_property PROGRAM.FILE $device]]
if {$programmed_file ne $bitstream} {
    error "Hardware manager programmed a different bitstream: $programmed_file"
}
set final_sha [bitstream_sha256 $bitstream]
if {$final_sha ne $expected_sha} {
    error "V5 bitstream changed during programming"
}

set fh [open $report w]
puts $fh "status=V5_VCU118_PROGRAM_PASS"
puts $fh "tool=[version -short]"
puts $fh "hw_server_url=$server"
puts $fh "hw_target=$target"
puts $fh "device=[get_property NAME $device]"
puts $fh "part=$part"
puts $fh "program_file=$programmed_file"
puts $fh "bitstream_size_bytes=[file size $bitstream]"
puts $fh "bitstream_sha256=$final_sha"
puts $fh "program_done=1"
close $fh
puts "V5_VCU118_PROGRAM_PASS device=$device sha256=$final_sha"
close_hw_manager
exit 0
