# Generic out-of-context synth/place/route driver for the modular experiment.
# Required environment variables:
#   HAP_OOC_NAME, HAP_OOC_TOP, HAP_OOC_SOURCES_FILE,
#   HAP_OOC_REPORT_DIR, HAP_OOC_BUILD_DIR
# Optional:
#   HAP_OOC_PART, HAP_OOC_CLOCK_PORT, HAP_OOC_CLOCK_PERIOD_NS,
#   HAP_OOC_SETUP_UNCERTAINTY_NS, HAP_OOC_HOLD_UNCERTAINTY_NS,
#   HAP_OOC_CLOCK_SOURCE_SITE, HAP_OOC_PRE_SYNTH_TCL

proc require_env {name} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "missing required environment variable $name"
    }
    return $::env($name)
}

set case_name [require_env HAP_OOC_NAME]
set top [require_env HAP_OOC_TOP]
set sources_file [file normalize [require_env HAP_OOC_SOURCES_FILE]]
set report_dir [file normalize [require_env HAP_OOC_REPORT_DIR]]
set build_dir [file normalize [require_env HAP_OOC_BUILD_DIR]]
set part [expr {[info exists ::env(HAP_OOC_PART)] ? $::env(HAP_OOC_PART) : "xcvu9p-flga2104-2L-e"}]
set clock_port [expr {[info exists ::env(HAP_OOC_CLOCK_PORT)] ? $::env(HAP_OOC_CLOCK_PORT) : "clk"}]
set period [expr {[info exists ::env(HAP_OOC_CLOCK_PERIOD_NS)] ? double($::env(HAP_OOC_CLOCK_PERIOD_NS)) : 10.0}]
set setup_uncertainty [expr {[info exists ::env(HAP_OOC_SETUP_UNCERTAINTY_NS)] ? double($::env(HAP_OOC_SETUP_UNCERTAINTY_NS)) : 0.150}]
set hold_uncertainty [expr {[info exists ::env(HAP_OOC_HOLD_UNCERTAINTY_NS)] ? double($::env(HAP_OOC_HOLD_UNCERTAINTY_NS)) : 0.000}]
set clock_source_site [expr {[info exists ::env(HAP_OOC_CLOCK_SOURCE_SITE)] ? $::env(HAP_OOC_CLOCK_SOURCE_SITE) : "BUFGCE_X0Y0"}]

file mkdir $report_dir
file mkdir [file dirname $build_dir]
create_project $case_name $build_dir -part $part -force
set_property target_language Verilog [current_project]

if {[info exists ::env(HAP_OOC_PRE_SYNTH_TCL)] && $::env(HAP_OOC_PRE_SYNTH_TCL) ne ""} {
    source [file normalize $::env(HAP_OOC_PRE_SYNTH_TCL)]
}

set source_fh [open $sources_file r]
set source_text [read $source_fh]
close $source_fh
set sources [list]
foreach line [split $source_text "\n"] {
    set source [string trim $line]
    if {$source eq "" || [string match "#*" $source]} { continue }
    set source [file normalize $source]
    if {![file exists $source]} { error "source does not exist: $source" }
    lappend sources $source
}
if {[llength $sources] == 0} { error "source list is empty: $sources_file" }
foreach source $sources {
    add_files -fileset sources_1 -norecurse $source
    if {[string equal -nocase [file extension $source] ".sv"]} {
        set_property file_type SystemVerilog [get_files $source]
    }
}
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

set start_seconds [clock seconds]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
set clock_pin [get_ports -quiet $clock_port]
if {[llength $clock_pin] != 1} { error "expected one clock port named $clock_port" }
create_clock -name core_clk -period $period $clock_pin
# OOC timing has no parent design from which to infer the source BUFG.  Freeze
# one legal site for every variant so clock insertion/skew is estimated rather
# than left pessimistic and implementation comparisons remain reproducible.
if {[llength [get_sites -quiet $clock_source_site]] != 1} {
    error "invalid OOC clock source site: $clock_source_site"
}
set_property HD.CLK_SRC $clock_source_site $clock_pin
set_clock_uncertainty -setup $setup_uncertainty [get_clocks core_clk]
set_clock_uncertainty -hold $hold_uncertainty [get_clocks core_clk]

write_checkpoint -force [file join $report_dir post_synth.dcp]
report_utilization -file [file join $report_dir utilization_post_synth.rpt]
report_timing_summary -delay_type min_max -max_paths 30 \
    -file [file join $report_dir timing_post_synth.rpt]

opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
# Vivado 2025.2 infers the post-route phase from the routed design.  The old
# -post_route option is not accepted, while -hold_fix remains a valid action.
set preliminary_hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$preliminary_hold_path ne "" &&
    [get_property SLACK $preliminary_hold_path] < 0.0} {
    puts "MODULAR_OOC_HOLD_FIX pre_whs=[get_property SLACK $preliminary_hold_path]"
    phys_opt_design -hold_fix
}

write_checkpoint -force [file join $report_dir post_route.dcp]
report_utilization -file [file join $report_dir utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 6 \
    -file [file join $report_dir utilization_hierarchical_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 50 \
    -file [file join $report_dir timing_post_route.rpt]
report_route_status -file [file join $report_dir route_status_post_route.rpt]
report_drc -ruledecks default -file [file join $report_dir drc_post_route.rpt]

set setup_path [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} { error "timing paths missing" }
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set bram36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set bram18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set elapsed [expr {[clock seconds] - $start_seconds}]
set clock_mhz [expr {1000.0 / $period}]
set critical_period [expr {$period - $wns}]
set fmax_mhz [expr {$critical_period > 0.0 ? 1000.0 / $critical_period : 0.0}]
set valid [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 && $drc_errors == 0}]

set kv [list \
    schema_version 1 tool [version -short] part $part case $case_name top $top \
    clock_mhz $clock_mhz clock_period_ns $period clock_source_site $clock_source_site \
    setup_uncertainty_ns $setup_uncertainty \
    hold_uncertainty_ns $hold_uncertainty wns_ns $wns whs_ns $whs fmax_mhz $fmax_mhz \
    lut_primitives $lut ff_primitives $ff dsp48e2 $dsp bram36e2 $bram36 \
    bram18e2 $bram18 uram288 $uram drc_errors $drc_errors unrouted_nets $unrouted \
    elapsed_seconds $elapsed valid $valid]
set summary [open [file join $report_dir summary.kv] w]
foreach {key value} $kv { puts $summary "$key=$value" }
close $summary

set json [open [file join $report_dir summary.json] w]
puts $json "{"
set count [expr {[llength $kv] / 2}]
set index 0
foreach {key value} $kv {
    incr index
    set comma [expr {$index < $count ? "," : ""}]
    if {[string is double -strict $value] || $value eq "true" || $value eq "false"} {
        puts $json "  \"$key\": $value$comma"
    } else {
        set escaped [string map [list "\\" "\\\\" "\"" "\\\""] $value]
        puts $json "  \"$key\": \"$escaped\"$comma"
    }
}
puts $json "}"
close $json

puts "MODULAR_OOC_RESULT case=$case_name top=$top valid=$valid WNS=$wns WHS=$whs LUT=$lut FF=$ff DSP=$dsp BRAM36=$bram36 BRAM18=$bram18 URAM=$uram DRC_ERRORS=$drc_errors UNROUTED=$unrouted"
if {!$valid} { error "post-route validity gate failed" }
close_project
