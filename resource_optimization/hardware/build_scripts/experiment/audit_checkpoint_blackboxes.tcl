# SPDX-License-Identifier: Apache-2.0
# Independently inspect a preserved native checkpoint without modifying it.
foreach name {HAP_SOURCE_DCP HAP_SOURCE_DCP_SHA256 HAP_REPORT_DIR} {
    if {![info exists ::env($name)] || $::env($name) eq {}} {
        error "Missing $name"
    }
}
set dcp $::env(HAP_SOURCE_DCP)
set expected $::env(HAP_SOURCE_DCP_SHA256)
set out $::env(HAP_REPORT_DIR)
set_param general.maxThreads 4
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}
if {[lindex [exec sha256sum -- $dcp] 0] ne $expected} {
    error {Checkpoint hash changed before inspection}
}
open_checkpoint $dcp
puts "CHECKPOINT_PART=[get_property PART [current_design]]"
puts "CHECKPOINT_DESIGN_NAME=[get_property NAME [current_design]]"
if {[get_property PART [current_design]] ne {xcvu9p-flga2104-2L-e} ||
    [get_property NAME [current_design]] ne {scalellm_final_decode16_bd_wrapper}} {
    error {Checkpoint part or top differs}
}
set f [open [file join $out blackboxes.tsv] w]
puts $f "name\tref_name"
set cells [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}]
foreach cell $cells {
    puts $f "[get_property NAME $cell]\t[get_property REF_NAME $cell]"
}
close $f
set count [llength $cells]
close_design
if {$count != 0} {error "Checkpoint has $count blackboxes"}
puts {CHECKPOINT_BLACKBOX_PASS count=0}
