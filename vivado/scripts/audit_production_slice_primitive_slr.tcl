set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_AUDIT_FILE)]
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
open_checkpoint $dcp
set roots [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]]
if {[llength $roots] != 2} {error "Expected two slice roots"}
set f [open $out w]
puts $f "dcp=$dcp"
foreach root $roots target {0 2} {
    set cells [get_cells -quiet -hierarchical -filter \
        "IS_PRIMITIVE && NAME =~ $root/*"]
    set counts {0 0 0}
    set bad 0
    foreach cell $cells {
        set slr [get_property SLR_INDEX $cell]
        if {$slr eq ""} {continue}
        lset counts $slr [expr {[lindex $counts $slr] + 1}]
        if {$slr != $target} {
            incr bad
            puts $f "wrong_cell=$cell ref=[get_property REF_NAME $cell] slr=$slr"
        }
    }
    puts $f "slice=$root target_slr=$target total=[llength $cells] slr0=[lindex $counts 0] slr1=[lindex $counts 1] slr2=[lindex $counts 2] wrong=$bad"
}
close $f
close_design
