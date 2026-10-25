# Shared Hardware Manager helpers. No hardware action is performed by sourcing.
proc exact_object {objects expected kind} {
    set matches {}
    foreach obj $objects { if {"$obj" eq $expected} { lappend matches $obj } }
    if {[llength $matches] != 1} { error "Expected one exact $kind '$expected'; available: $objects" }
    return [lindex $matches 0]
}
proc device_part {device} {
    if {[lsearch -exact [list_property $device] PART] >= 0} { return [get_property PART $device] }
    return [get_property NAME $device]
}
proc require_unique_vu9p {devices expected} {
    set vu9p {}
    foreach device $devices {
        if {[string match -nocase *xcvu9p* [device_part $device]]} { lappend vu9p $device }
    }
    if {[llength $vu9p] != 1} { error "Expected one xcvu9p on selected target, found: $vu9p" }
    return [exact_object $vu9p $expected device]
}
proc verify_engineering_bit {filename} {
    set bit [file normalize $filename]
    if {![file isfile $bit]} { error "Bitstream is not a regular file: $bit" }
    if {[file tail $bit] ne "ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit"} { error "Unexpected bitstream filename" }
    if {[file size $bit] != 80159259} { error "Bitstream byte count mismatch" }
    set expected 66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47
    if {$::tcl_platform(platform) eq "windows"} {
        set output [exec certutil.exe -hashfile $bit SHA256]
    } else {
        set output [exec sha256sum -- $bit]
    }
    if {![regexp -nocase "\\m${expected}\\M" $output]} { error "Bitstream SHA256 mismatch: $output" }
    return $bit
}
proc hw_cleanup {} {
    catch {close_hw_target}
    catch {disconnect_hw_server}
    catch {close_hw_manager}
}
