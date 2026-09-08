set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_AUDIT_FILE)]
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
open_checkpoint $dcp

set lanes [get_cells -quiet -hierarchical -filter {
    (ORIG_REF_NAME =~ hap_a8w8_group32_lane_s42* ||
     REF_NAME =~ hap_a8w8_group32_lane_s42*) &&
    NAME =~ u_compute/u_attention/u_compute/u_projection/u_array/*
}]
set lanes [lsort -dictionary $lanes]
if {[llength $lanes] != 128} {
    error "Expected 128 Attention projection lanes, got [llength $lanes]"
}

set f [open $out w]
puts $f "dcp=$dcp"
puts $f "projection_lanes=[llength $lanes]"
puts $f "lane,dsp_slr0,dsp_slr1,dsp_slr2"
foreach lane $lanes {
    set lane_dsp [get_cells -quiet -hierarchical -filter \
        "REF_NAME == DSP48E2 && NAME =~ $lane/*"]
    set counts {0 0 0}
    foreach dsp $lane_dsp {
        set slr [get_property SLR_INDEX $dsp]
        lset counts $slr [expr {[lindex $counts $slr] + 1}]
    }
    puts $f "$lane,[lindex $counts 0],[lindex $counts 1],[lindex $counts 2]"
}
close $f
puts "ATTENTION_PROJECTION_SLR_AUDIT lanes=[llength $lanes] out=$out"
close_design
