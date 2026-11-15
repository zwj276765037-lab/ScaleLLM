# SPDX-License-Identifier: Apache-2.0
# Inspect the original, immutable synthesized checkpoint after the known
# synthesis-only debug-hub placeholder stopped the first report gate.
set dcp $::env(HAP_SOURCE_DCP)
set out $::env(HAP_REPORT_DIR)
set_param general.maxThreads 4
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}
if {[lindex [exec sha256sum -- $dcp] 0] ne $::env(HAP_SOURCE_DCP_SHA256)} {
    error {Original synthesized checkpoint changed}
}
open_checkpoint $dcp

set f [open [file join $out blackboxes.tsv] w]
puts $f "name\tref_name"
foreach cell [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}] {
    puts $f "[get_property NAME $cell]\t[get_property REF_NAME $cell]"
}
close $f

set f [open [file join $out debug_cores.tsv] w]
puts $f "name\tref_name\tipdef"
if {[catch {get_debug_cores -quiet} cores]} {
    puts $f "QUERY_ERROR\t$cores\t"
} else {
    foreach core $cores {
        set name [get_property NAME $core]
        set ref ""
        set ipdef ""
        catch {set ref [get_property REF_NAME $core]}
        catch {set ipdef [get_property IPDEF $core]}
        puts $f "$name\t$ref\t$ipdef"
    }
}
close $f

set dbg [get_cells -quiet dbg_hub]
set f [open [file join $out dbg_hub_properties.tsv] w]
puts $f "property\tvalue"
if {[llength $dbg] == 1} {
    foreach property [lsort [list_property $dbg]] {
        if {[catch {get_property $property $dbg} value]} {continue}
        puts $f "$property\t$value"
    }
}
close $f
close_design
puts {SYNTH_DCP_PROBE_COMPLETE}
