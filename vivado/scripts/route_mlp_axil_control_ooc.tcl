set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set part xcvu9p-flga2104-2L-e
set top hap_mlp_axil_control_registered_ooc_harness
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32: $jobs"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "Invalid MLP AXI-Lite input manifest SHA256"
}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}
set_param general.maxThreads $jobs
file mkdir $report_dir

proc write_text {path text} {
    set fp [open $path w]
    puts -nonewline $fp $text
    close $fp
}

proc timing_check_count {text label} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $label]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "Missing check_timing category: $label"
    }
    return $count
}

proc route_status_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} \
                $line -> count]} {
            return $count
        }
    }
    if {$required} {
        error "Missing route-status row: $label"
    }
    return 0
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl integration hap_mlp_axil_control.sv]
read_verilog -sv [file join $root rtl integration \
    hap_mlp_axil_control_registered_ooc_harness.sv]
read_xdc [file join $root vivado constraints mlp_axil_control_ooc_150mhz.xdc]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none

set source_proxy [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink_proxy [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
if {[llength $source_proxy] != 2335 || [llength $sink_proxy] != 409} {
    error "MLP AXI-Lite proxy FF mismatch source=[llength $source_proxy] sink=[llength $sink_proxy]"
}
if {[llength [get_cells -quiet u_dut]] != 1 || \
    [llength [get_ports -quiet]] != 1} {
    error "MLP AXI-Lite registered OOC hierarchy/port identity mismatch"
}
opt_design
set dut_nonclock_nets {}
foreach net [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}] {
    if {[llength [get_clocks -quiet -of_objects $net]] == 0} {
        lappend dut_nonclock_nets $net
    }
}
if {[llength $dut_nonclock_nets] != 0} {
    set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
}
place_design
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
write_text [file join $report_dir timing_summary.rpt] $timing_text
report_utilization -hierarchical -hierarchical_depth 4 \
    -file [file join $report_dir utilization.rpt]
set route_text [report_route_status -return_string]
write_text [file join $report_dir route_status.rpt] $route_text
report_drc -file [file join $report_dir drc.rpt]

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "MLP AXI-Lite OOC timing paths are missing"
}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set no_clock [timing_check_count $timing_text no_clock]
set unconstrained [timing_check_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [timing_check_count $timing_text no_input_delay]
set no_output_delay [timing_check_count $timing_text no_output_delay]
set partial_input_delay [timing_check_count $timing_text partial_input_delay]
set partial_output_delay [timing_check_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 && \
    $no_input_delay == 0 && $no_output_delay == 0 && \
    $partial_input_delay == 0 && $partial_output_delay == 0}]

set route_errors [route_status_row $route_text \
    "# of nets with routing errors" 1]
set explicit_gaps [route_status_row $route_text \
    "# of nets with explicit gaps"]
set unrouted_rows [route_status_row $route_text "# of unrouted nets"]
set partial_rows [route_status_row $route_text \
    "# of nets with some unrouted pins"]
set resource_conflicts [route_status_row $route_text \
    "# of nets with resource conflicts"]
set antennas [route_status_row $route_text \
    "# of nets with antennas/islands"]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
    }
}
set route_clean [expr {$route_errors == 0 && $unrouted_rows == 0 && \
    $partial_rows == 0 && \
    $resource_conflicts == 0 && $antennas == 0 && $unrouted == 0}]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $timing_coverage_ok && \
    $route_clean && $drc == 0 && $dsp == 0 && $data_bufg == 0 ? \
    "PASS" : "FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
foreach {key value} [list \
        tool [version -short] part $part top $top \
        core_clock_mhz 150 jobs $jobs \
        input_manifest_sha256 $input_manifest_sha \
        source_proxy_ff [llength $source_proxy] \
        sink_proxy_ff [llength $sink_proxy] \
        dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff \
        wns_ns $wns whs_ns $whs \
        dsp48e2 $dsp data_bufg $data_bufg \
        no_clock $no_clock unconstrained_internal_endpoints $unconstrained \
        no_input_delay $no_input_delay no_output_delay $no_output_delay \
        partial_input_delay $partial_input_delay \
        partial_output_delay $partial_output_delay \
        timing_coverage_ok $timing_coverage_ok \
        route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
        route_status_unrouted_nets $unrouted_rows \
        route_status_partial_nets $partial_rows \
        route_status_resource_conflicts $resource_conflicts \
        route_status_antenna_island_nets $antennas \
        unrouted_nets $unrouted route_clean $route_clean \
        drc_errors $drc status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "PASS"} {
    error "MLP AXI-Lite control OOC physical gate failed"
}
write_checkpoint -force [file join $report_dir post_route.dcp]
