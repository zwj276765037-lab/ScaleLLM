set root [file normalize [file join [file dirname [file normalize [info script]]] ../..]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_XDC_AUDIT_DIR)]
set part xcvu9p-flga2104-2L-e
set clock_xdc [expr {[info exists ::env(HAP_CLOCK_XDC)] ?
    [file normalize $::env(HAP_CLOCK_XDC)] :
    [file join $root vivado constraints attention_mlp_production_ooc_clocks.xdc]}]
set expected_core_period [expr {[info exists ::env(HAP_CORE_PERIOD_NS)] ?
    double($::env(HAP_CORE_PERIOD_NS)) : 6.666}]
file mkdir $out
if {![string match "2025.2*" [version -short]]} {error "Vivado 2025.2 required"}
open_checkpoint $dcp
if {[get_property PART [current_design]] ne $part} {error "Unexpected part"}
read_xdc $clock_xdc
source [file join $root vivado scripts check_attention_mlp_production_io_selectors.tcl]

foreach {name period} [list core_clk $expected_core_period \
        ddr0_clk 3.333 ddr1_clk 3.333] {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1} {error "Clock $name selector failed"}
    set actual [get_property PERIOD $clocks]
    if {abs($actual - $period) > 0.001} {
        error "Clock $name period mismatch: $actual"
    }
}

set timing_text [report_timing_summary -delay_type min_max -max_paths 10 \
    -report_unconstrained -return_string]
set fh [open [file join $out timing_coverage.rpt] w]
puts -nonewline $fh $timing_text
close $fh
proc check_count {text category} {
    set pattern [format {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $category]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "Missing check_timing category $category"
    }
    return $count
}
set no_clock [check_count $timing_text no_clock]
set unconstrained [check_count $timing_text unconstrained_internal_endpoints]
set no_input [check_count $timing_text no_input_delay]
set no_output [check_count $timing_text no_output_delay]
set partial_input [check_count $timing_text partial_input_delay]
set partial_output [check_count $timing_text partial_output_delay]

set expected_resets {core_rst_n ddr0_rst_n ddr1_rst_n}
set status [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input == 3 && $no_output == 0 && $partial_input == 0 &&
    $partial_output == 0 && [llength $hap_missing_names] == 0 ?
    "XDC_AUDIT_PASS" : "XDC_AUDIT_FAIL"}]
set f [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part \
    core_period_ns [get_property PERIOD [get_clocks core_clk]] \
    ddr0_period_ns [get_property PERIOD [get_clocks ddr0_clk]] \
    ddr1_period_ns [get_property PERIOD [get_clocks ddr1_clk]] \
    core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
    no_clock $no_clock unconstrained_internal_endpoints $unconstrained \
    no_input_delay $no_input no_output_delay $no_output \
    partial_input_delay $partial_input partial_output_delay $partial_output \
    excluded_reset_names $expected_resets all_logical_ports [llength $hap_all_names] \
    core_functional_ports [llength $hap_core_names] \
    ddr0_functional_ports [llength $hap_ddr0_names] \
    ddr1_functional_ports [llength $hap_ddr1_names] status $status] {
    puts $f "$key=$value"
}
close $f
set core_clock_mhz [expr {1000.0 / $expected_core_period}]
puts [format "PRODUCTION_XDC_AUDIT CLOCKS=%.3f/300/300 IO=1.0/0.8 UNCONSTRAINED=%s STATUS=%s" \
    $core_clock_mhz $unconstrained $status]
if {$status ne "XDC_AUDIT_PASS"} {error "Production XDC audit failed"}
close_design
