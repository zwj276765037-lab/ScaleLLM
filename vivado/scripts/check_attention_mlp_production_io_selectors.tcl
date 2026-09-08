# Ordinary Tcl fail-closed audit for the pure-XDC port selectors. The design
# must already be open. Vivado expands vector ports to individual port bits, so
# the exact contract below is deliberately bit-level (1,894 total bits), not
# the 74 signal declarations visible in the SystemVerilog module header. This
# script intentionally contains control flow that is not legal inside an XDC.
proc hap_list_subtract {left right} {
    set result {}
    foreach item $left {
        if {[lsearch -exact $right $item] < 0} {lappend result $item}
    }
    return [lsort -dictionary -unique $result]
}
set hap_excluded_names [lsort -dictionary {
    core_clk core_rst_n ddr0_clk ddr0_rst_n ddr1_clk ddr1_rst_n
}]
set hap_core_names [lsort -dictionary [get_property NAME [get_ports -quiet {
    core_clear ctrl_* data_axi_* attention_irq mlp_irq integration_error
}]]]
set hap_ddr0_names [lsort -dictionary \
    [get_property NAME [get_ports -quiet {ddr0_axi_*}]]]
set hap_ddr1_names [lsort -dictionary \
    [get_property NAME [get_ports -quiet {ddr1_axi_*}]]]
set hap_all_names [lsort -dictionary [get_property NAME [get_ports -quiet *]]]
set hap_functional_names [hap_list_subtract $hap_all_names $hap_excluded_names]
set hap_budgeted_names [lsort -dictionary -unique \
    [concat $hap_core_names $hap_ddr0_names $hap_ddr1_names]]
set hap_missing_names [hap_list_subtract $hap_functional_names $hap_budgeted_names]
set hap_unexpected_names [hap_list_subtract $hap_budgeted_names $hap_functional_names]
set hap_selected_sum [expr {[llength $hap_core_names] +
    [llength $hap_ddr0_names] + [llength $hap_ddr1_names]}]
if {[llength $hap_all_names] != 1894 ||
    [llength $hap_excluded_names] != 6 ||
    [llength $hap_core_names] != 760 ||
    [llength $hap_ddr0_names] != 564 ||
    [llength $hap_ddr1_names] != 564 ||
    [llength $hap_missing_names] != 0 ||
    [llength $hap_unexpected_names] != 0 ||
    $hap_selected_sum != [llength $hap_budgeted_names]} {
    error "Production I/O selector audit failed: all=[llength $hap_all_names] core=[llength $hap_core_names] ddr0=[llength $hap_ddr0_names] ddr1=[llength $hap_ddr1_names] missing=$hap_missing_names unexpected=$hap_unexpected_names"
}
