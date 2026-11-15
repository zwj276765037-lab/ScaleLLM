# SPDX-License-Identifier: Apache-2.0
# The production hook saves the exact post-opt checkpoint before this gate.
source [file join $::env(HAP_HW_ROOT) vivado scripts release_save_opt_design.tcl]
set out [file join $::env(HAP_REPORT_DIR) blackboxes_post_opt.tsv]
set f [open $out w]
puts $f "name\tref_name"
set blackboxes [get_cells -hierarchical -quiet -filter {IS_BLACKBOX == 1}]
foreach cell $blackboxes {
    puts $f "[get_property NAME $cell]\t[get_property REF_NAME $cell]"
}
close $f
if {[llength $blackboxes] != 0} {
    error "Post-opt blackboxes remain: [llength $blackboxes]"
}
puts {POST_OPT_BLACKBOX_PASS count=0}
