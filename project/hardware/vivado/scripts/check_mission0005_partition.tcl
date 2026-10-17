set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set checkpoint [file normalize $::env(HAP_DIAG_DCP)]
if {![string match [file join $root vivado reports *] $out] || [file exists $out]} {
    error "New Hardware-local diagnostic report required"
}
file mkdir $out
set before [lindex [exec sha256sum -- $checkpoint] 0]
set_param general.maxThreads 32
source [file join $script_dir mission0004_metadata_physical.tcl]
source [file join $script_dir mission0005_coordinated_physical.tcl]
open_checkpoint $checkpoint
if {[llength [get_pblocks -quiet mission0004_metadata_slr0]] == 0} {
    read_xdc [file join $root vivado constraints mission0004_metadata_width_local.xdc]
}
read_xdc [file join $root vivado constraints mission0005_coordinated_partition.xdc]
mission0005_require_partition 0 $out
mission0005_report_capacity $out
report_drc -file [file join $out partition_drc.rpt]
close_design
if {[lindex [exec sha256sum -- $checkpoint] 0] ne $before} {error "Diagnostic changed retained DCP"}
puts "MISSION0005_PARTITION_API_PASS read_only_no_place_or_signoff"
exit 0
