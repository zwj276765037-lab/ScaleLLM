# SPDX-License-Identifier: Apache-2.0
# Diagnostic only: find the Vivado property that carries the loaded DCP top.
foreach name {HAP_SOURCE_DCP HAP_SOURCE_DCP_SHA256} {
    if {![info exists ::env($name)] || $::env($name) eq {}} {error "Missing $name"}
}
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}
set dcp $::env(HAP_SOURCE_DCP)
if {[lindex [exec sha256sum -- $dcp] 0] ne $::env(HAP_SOURCE_DCP_SHA256)} {
    error {Checkpoint hash changed}
}
set_param general.maxThreads 32
open_checkpoint $dcp
set design [current_design]
foreach prop [lsort [list_property $design]] {
    if {[string match {*TOP*} $prop] || [string match {*REF*} $prop] ||
        [string match {*NAME*} $prop] || [string match {*DESIGN*} $prop] ||
        $prop eq {PART}} {
        if {![catch {get_property $prop $design} value]} {
            puts "DESIGN_PROPERTY $prop=$value"
        }
    }
}
close_design
puts {CHECKPOINT_IDENTITY_PROBE_COMPLETE}
