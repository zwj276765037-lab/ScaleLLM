# SPDX-License-Identifier: Apache-2.0
# Re-report an immutable post-physopt checkpoint after a launcher STATUS typo.
foreach name {HAP_HW_ROOT HAP_SOURCE_DCP HAP_SOURCE_DCP_SHA256 HAP_REPORT_DIR HAP_JOBS} {
    if {![info exists ::env($name)] || $::env($name) eq {}} {error "Missing $name"}
}
if {[version -short] ne {2025.2}} {error {Vivado 2025.2 required}}
set out $::env(HAP_REPORT_DIR)
set dcp $::env(HAP_SOURCE_DCP)
if {![file isfile $dcp] || [lindex [exec sha256sum -- $dcp] 0] ne $::env(HAP_SOURCE_DCP_SHA256)} {
    error {Preserved post-physopt checkpoint changed}
}
set_param general.maxThreads $::env(HAP_JOBS)
source [file join $::env(HAP_HW_ROOT) vivado scripts release_reports.tcl]
open_checkpoint $dcp
puts "CHECKPOINT_PART=[get_property PART [current_design]]"
puts "CHECKPOINT_DESIGN_NAME=[get_property NAME [current_design]]"
require_design_identity
report_scene $out
report_utilization -hierarchical -file [file join $out utilization_hierarchical.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
if {[catch {report_design_analysis -congestion -file [file join $out congestion.rpt]} message]} {
    set f [open [file join $out congestion_command_error.txt] w]
    puts $f $message
    close $f
}
if {[catch {report_high_fanout_nets -file [file join $out high_fanout_nets.rpt]} message]} {
    set f [open [file join $out high_fanout_command_error.txt] w]
    puts $f $message
    close $f
}
set dsps [lsort [get_cells -hierarchical -quiet -filter {REF_NAME == DSP48E2}]]
set f [open [file join $out dsp_inventory.tsv] w]
puts $f "name\tref_name\tloc\tbel\torig_ref_name"
foreach cell $dsps {
    set fields [list [get_property NAME $cell]]
    foreach property {REF_NAME LOC BEL ORIG_REF_NAME} {
        set value ""
        catch {set value [get_property $property $cell]}
        lappend fields $value
    }
    puts $f [join $fields "\t"]
}
close $f
set recovery_cells [lsort -unique [concat \
    [get_cells -hierarchical -quiet -filter {REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}] \
    [get_cells -hierarchical -quiet -filter {ORIG_REF_NAME =~ *hap_a8w4_scalecode_recover2_lut*}]]]
set f [open [file join $out recovery_mapping.tsv] w]
puts $f "name\tref_name\torig_ref_name\tdsp_descendants"
set recovery_count 0
foreach cell $recovery_cells {
    set name [get_property NAME $cell]
    if {![string match {*u_recover*} $name]} {continue}
    set ref ""
    set orig ""
    catch {set ref [get_property REF_NAME $cell]}
    catch {set orig [get_property ORIG_REF_NAME $cell]}
    set child_dsp 0
    foreach dsp $dsps {
        if {[string first "$name/" [get_property NAME $dsp]] == 0} {incr child_dsp}
    }
    puts $f "$name\t$ref\t$orig\t$child_dsp"
    incr recovery_count
}
close $f
puts "RECOVERY_LEAF_QUERY_COUNT stage=place_qualified count=$recovery_count"
set bb [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}]
set f [open [file join $out blackboxes.txt] w]
foreach cell $bb {puts $f [get_property NAME $cell]}
close $f
set f [open [file join $out blackboxes_identity.tsv] w]
puts $f "name\tref_name\tis_primitive\tis_debug_core"
set debug_cores [get_debug_cores -quiet]
foreach cell $bb {
    set name [get_property NAME $cell]
    puts $f "$name\t[get_property REF_NAME $cell]\t[get_property IS_PRIMITIVE $cell]\t[expr {[lsearch -exact $debug_cores $name] >= 0}]"
}
close $f
if {[llength $bb]} {error "Unresolved blackboxes: [llength $bb]"}
close_design
puts {PLACE_DCP_REQUALIFIED_PASS blackboxes=0}
