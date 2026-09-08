set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_axi512_paired_2client_read_wrr_ooc_harness
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected $expected, got $actual"
    }
    return $actual
}

proc first_slack {delay from_set to_set label} {
    set args [list -quiet -delay_type $delay -max_paths 1]
    if {[llength $from_set] != 0} {lappend args -from $from_set}
    if {[llength $to_set] != 0} {lappend args -to $to_set}
    set paths [get_timing_paths {*}$args]
    if {[llength $paths] == 0} {error "$label returned no timing path"}
    return [get_property SLACK [lindex $paths 0]]
}

proc report_pair {out stem from_set to_set} {
    set common [list -max_paths 100 -path_type full_clock_expanded]
    if {[llength $from_set] != 0} {lappend common -from $from_set}
    if {[llength $to_set] != 0} {lappend common -to $to_set}
    report_timing -delay_type max {*}$common -file \
        [file join $out ${stem}_setup_worst100.rpt]
    report_timing -delay_type min {*}$common -file \
        [file join $out ${stem}_hold_worst100.rpt]
}

proc route_row {text label} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    # Vivado omits zero-valued detail rows (for example explicit gaps) from a
    # clean report.  The aggregate routing-error row is always present and is
    # independently required to be zero below.
    return 0
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl integration \
    hap_axi512_paired_2client_read_wrr.sv]
read_verilog -sv [file join $root rtl integration \
    hap_axi512_paired_2client_read_wrr_ooc_harness.sv]
read_xdc [file join $root vivado constraints \
    axi512_paired_2client_read_wrr_registered_ooc_150_300_300.xdc]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized

# These exact counts make the harness auditable and prevent a future synthesis
# change from silently trimming a wide boundary.  The two committed mode
# enables now originate with the core boundary; 1,228 source + 2,391 sink =
# 3,619 registered timing anchors remains unchanged.
set core_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ core_src_r_reg* && REF_NAME =~ FD*}]
set ddr0_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr0_src_r_reg* && REF_NAME =~ FD*}]
set ddr1_src [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr1_src_r_reg* && REF_NAME =~ FD*}]
set core_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ core_sink_r_reg* && REF_NAME =~ FD*}]
set ddr0_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr0_sink_r_reg* && REF_NAME =~ FD*}]
set ddr1_sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ ddr1_sink_r_reg* && REF_NAME =~ FD*}]
set core_src_count [require_count core_source_boundary $core_src 6]
set ddr0_src_count [require_count ddr0_source_boundary $ddr0_src 611]
set ddr1_src_count [require_count ddr1_source_boundary $ddr1_src 611]
set core_sink_count [require_count core_sink_boundary $core_sink 101]
set ddr0_sink_count [require_count ddr0_sink_boundary $ddr0_sink 1145]
set ddr1_sink_count [require_count ddr1_sink_boundary $ddr1_sink 1145]
set boundary_ff_count [expr {$core_src_count + $ddr0_src_count +
    $ddr1_src_count + $core_sink_count + $ddr0_sink_count +
    $ddr1_sink_count}]
if {$boundary_ff_count != 3619} {error "total boundary FF count mismatch"}

set core_regs [all_registers -clock [get_clocks core_clk]]
set ddr0_regs [all_registers -clock [get_clocks ddr0_clk]]
set ddr1_regs [all_registers -clock [get_clocks ddr1_clk]]
set core_dut_regs [filter $core_regs {NAME =~ u_dut/*}]
set ddr0_dut_regs [filter $ddr0_regs {NAME =~ u_dut/*}]
set ddr1_dut_regs [filter $ddr1_regs {NAME =~ u_dut/*}]
if {[llength $core_dut_regs] == 0 || [llength $ddr0_dut_regs] == 0 ||
    [llength $ddr1_dut_regs] == 0} {
    error "one or more DUT clock domains contain no sequential cell"
}

# Preserve the raw OOC I/O contract without top-level part pins.  A 1.000 ns
# core shell budget leaves 6.666-1.000=5.666 ns; a 0.800 ns DDR shell budget
# leaves 3.333-0.800=2.533 ns.  Source/sink harness registers use the same
# clock trees as the DUT, so min=0 audits real local hold instead of assuming a
# zero-insertion external launch clock.  No -datapath_only, false path or broad
# asynchronous clock grouping is used.
set core_capture [filter $core_regs {NAME !~ core_src_r_reg*}]
set ddr0_capture [filter $ddr0_regs {NAME !~ ddr0_src_r_reg*}]
set ddr1_capture [filter $ddr1_regs {NAME !~ ddr1_src_r_reg*}]
set core_launch [filter $core_regs {NAME !~ core_sink_r_reg*}]
set ddr0_launch [filter $ddr0_regs {NAME !~ ddr0_sink_r_reg*}]
set ddr1_launch [filter $ddr1_regs {NAME !~ ddr1_sink_r_reg*}]

set_max_delay 5.666 -from $core_src -to $core_capture
set_min_delay 0.000 -from $core_src -to $core_capture
set_max_delay 2.533 -from $ddr0_src -to $ddr0_capture
set_min_delay 0.000 -from $ddr0_src -to $ddr0_capture
set_max_delay 2.533 -from $ddr1_src -to $ddr1_capture
set_min_delay 0.000 -from $ddr1_src -to $ddr1_capture
set_max_delay 5.666 -from $core_launch -to $core_sink
set_min_delay 0.000 -from $core_launch -to $core_sink
set_max_delay 2.533 -from $ddr0_launch -to $ddr0_sink
set_min_delay 0.000 -from $ddr0_launch -to $ddr0_sink
set_max_delay 2.533 -from $ddr1_launch -to $ddr1_sink
set_min_delay 0.000 -from $ddr1_launch -to $ddr1_sink

# Fail at synthesis time if any intended internal/boundary category is empty.
foreach {label from_set to_set} [list \
        core_internal $core_dut_regs $core_dut_regs \
        ddr0_internal $ddr0_dut_regs $ddr0_dut_regs \
        ddr1_internal $ddr1_dut_regs $ddr1_dut_regs \
        core_boundary_in $core_src $core_capture \
        ddr0_boundary_in $ddr0_src $ddr0_capture \
        ddr1_boundary_in $ddr1_src $ddr1_capture \
        core_boundary_out $core_launch $core_sink \
        ddr0_boundary_out $ddr0_launch $ddr0_sink \
        ddr1_boundary_out $ddr1_launch $ddr1_sink] {
    first_slack max $from_set $to_set ${label}_setup_nonempty
    first_slack min $from_set $to_set ${label}_hold_nonempty
}

report_utilization -hierarchical -hierarchical_depth 7 -file \
    [file join $out utilization_post_synth.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set synth_only 0
if {[info exists ::env(HAP_SYNTH_ONLY)] && $::env(HAP_SYNTH_ONLY) ne "0"} {
    set synth_only 1
}
if {$synth_only} {
    set fp [open [file join $out summary.txt] w]
    foreach {key value} [list tool [version -short] part $part top $top \
        core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
        core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
        core_source_boundary_ff $core_src_count \
        ddr0_source_boundary_ff $ddr0_src_count \
        ddr1_source_boundary_ff $ddr1_src_count \
        core_sink_boundary_ff $core_sink_count \
        ddr0_sink_boundary_ff $ddr0_sink_count \
        ddr1_sink_boundary_ff $ddr1_sink_count \
        boundary_ff_total $boundary_ff_count \
        core_dut_sequential [llength $core_dut_regs] \
        ddr0_dut_sequential [llength $ddr0_dut_regs] \
        ddr1_dut_sequential [llength $ddr1_dut_regs] \
        status REGISTERED_OOC_SYNTH_PASS] {puts $fp "$key=$value"}
    close $fp
    puts "REGISTERED_PAIRED_WRR_OOC SYNTH_ONLY_PASS BOUNDARY_FF=$boundary_ff_count"
    exit 0
}

opt_design -directive Explore
place_design -directive ExtraTimingOpt
phys_opt_design -directive AggressiveExplore
# Explore produces one final routing solution.  Acceptance below is based only
# on reports from the final in-memory design, never on an intermediate router
# console line.
route_design -directive Explore

report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_summary.rpt]
report_pair $out core_internal $core_dut_regs $core_dut_regs
report_pair $out ddr0_internal $ddr0_dut_regs $ddr0_dut_regs
report_pair $out ddr1_internal $ddr1_dut_regs $ddr1_dut_regs
report_pair $out core_boundary_in $core_src $core_capture
report_pair $out ddr0_boundary_in $ddr0_src $ddr0_capture
report_pair $out ddr1_boundary_in $ddr1_src $ddr1_capture
report_pair $out core_boundary_out $core_launch $core_sink
report_pair $out ddr0_boundary_out $ddr0_launch $ddr0_sink
report_pair $out ddr1_boundary_out $ddr1_launch $ddr1_sink
report_utilization -hierarchical -hierarchical_depth 7 -file \
    [file join $out utilization_hier.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
set route_text [report_route_status -return_string]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -details -file [file join $out cdc.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction.rpt]
report_methodology -file [file join $out methodology.rpt]
report_design_analysis -congestion -file [file join $out congestion.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set wns [first_slack max {} {} global_setup]
set whs [first_slack min {} {} global_hold]
foreach {key delay from_set to_set} [list \
        core_internal_wns max $core_dut_regs $core_dut_regs \
        core_internal_whs min $core_dut_regs $core_dut_regs \
        ddr0_internal_wns max $ddr0_dut_regs $ddr0_dut_regs \
        ddr0_internal_whs min $ddr0_dut_regs $ddr0_dut_regs \
        ddr1_internal_wns max $ddr1_dut_regs $ddr1_dut_regs \
        ddr1_internal_whs min $ddr1_dut_regs $ddr1_dut_regs \
        core_boundary_in_wns max $core_src $core_capture \
        core_boundary_in_whs min $core_src $core_capture \
        ddr0_boundary_in_wns max $ddr0_src $ddr0_capture \
        ddr0_boundary_in_whs min $ddr0_src $ddr0_capture \
        ddr1_boundary_in_wns max $ddr1_src $ddr1_capture \
        ddr1_boundary_in_whs min $ddr1_src $ddr1_capture \
        core_boundary_out_wns max $core_launch $core_sink \
        core_boundary_out_whs min $core_launch $core_sink \
        ddr0_boundary_out_wns max $ddr0_launch $ddr0_sink \
        ddr0_boundary_out_whs min $ddr0_launch $ddr0_sink \
        ddr1_boundary_out_wns max $ddr1_launch $ddr1_sink \
        ddr1_boundary_out_whs min $ddr1_launch $ddr1_sink] {
    set $key [first_slack $delay $from_set $to_set $key]
}

# Route 35-16 means the Tcl command terminated, not that all nets are clean.
# Gate both the detailed report rows and the final ROUTE_STATUS enum histogram.
set route_errors [route_row $route_text "# of nets with routing errors"]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]
# Vivado 2025.2 exposes neither an EXPLICIT_GAP net enum nor a gap-to-net
# query.  Audit both OOC-only cases by their exact roots instead of treating
# every PARTIAL enum or every top-level gap as a failure/waiver.
set allowed_ooc_clocks [lsort {core_clk ddr0_clk ddr1_clk}]
set allowed_ooc_resets [lsort {core_rst_n ddr0_rst_n ddr1_rst_n}]
set partial_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == UNROUTED}]
set bad_partial {}
set partial_parents {}
foreach n $partial_all {
    set parent [get_property PARENT $n]
    set type [get_property TYPE $n]
    set ports [lsort -unique [get_property NAME \
        [get_ports -quiet -of_objects $n]]]
    if {$type eq "LOCAL_CLOCK" &&
        [lsearch -exact $allowed_ooc_clocks $parent] >= 0 &&
        [llength $ports] == 1 && [lindex $ports 0] eq $parent} {
        lappend partial_parents $parent
    } else {
        lappend bad_partial $n
    }
}
set partial_clock_roots [lsort -unique $partial_parents]
set clock_alias_audit_ok [expr {[llength $partial_all] > 0 &&
    $partial_clock_roots eq $allowed_ooc_clocks &&
    [llength $bad_partial] == 0}]

# HIERPORT aliases must reduce to exactly the three reset roots, all with
# zero route nodes.  Together with explicit_gaps==3 and zero route errors,
# this narrowly recognizes Route 35-198 from missing production partpin locs.
set hierport_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == HIERPORT}]
set bad_hierport {}
set hierport_roots {}
foreach n $hierport_all {
    set root [get_property PARENT $n]
    if {[lsearch -exact $allowed_ooc_resets $root] < 0 ||
        [llength [get_nodes -quiet -of_objects $n]] != 0} {
        lappend bad_hierport $n
    } else {
        lappend hierport_roots $root
    }
}
set reset_roots [lsort -unique $hierport_roots]
set reset_gap_audit_ok [expr {$explicit_gaps == 3 &&
    $reset_roots eq $allowed_ooc_resets &&
    [llength $bad_hierport] == 0}]
foreach r $allowed_ooc_resets {
    set n [get_nets -quiet $r]
    set p [get_ports -quiet $r]
    if {[llength $n] != 1 || [llength $p] != 1 ||
        [get_property ROUTE_STATUS $n] ne "HIERPORT" ||
        [llength [get_nodes -quiet -of_objects $n]] != 0} {
        set reset_gap_audit_ok 0
    }
}
set route35198_ok 0
set log_path [file join $out vivado.log]
if {[file exists $log_path]} {
    set log_fh [open $log_path r]
    set log_text [read $log_fh]
    close $log_fh
    set route35198_ports {}
    foreach line [split $log_text "\n"] {
        if {[regexp {WARNING: \[Route 35-198\] Port "([^"]+)" does not have an associated HD\.PARTPIN_LOCS} $line -> p]} {
            lappend route35198_ports $p
        }
    }
    set route35198_ok [expr {[lsort -unique $route35198_ports] eq
        $allowed_ooc_resets}]
}
set reset_gap_audit_ok [expr {$reset_gap_audit_ok && $route35198_ok}]
set partial_status [llength $partial_all]
set partial_nonclock [llength $bad_partial]
set conflict_status [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]

set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set cdc_fh [open [file join $out cdc.rpt] r]
set cdc_text [read $cdc_fh]
close $cdc_fh
set cdc_critical 0
foreach {whole count} [regexp -all -inline \
        {Critical[[:space:]]+([1-9][0-9]*)} $cdc_text] {
    incr cdc_critical $count
}
set unconstrained 0
foreach line [split [report_timing_summary -return_string] "\n"] {
    if {[regexp -nocase \
            {Unconstrained Paths[[:space:]]+([1-9][0-9]*)} \
            $line -> count]} {incr unconstrained $count}
}
set dsp [llength [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]

set all_timing_ok [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $core_internal_wns >= 0.0 && $core_internal_whs >= 0.0 &&
    $ddr0_internal_wns >= 0.0 && $ddr0_internal_whs >= 0.0 &&
    $ddr1_internal_wns >= 0.0 && $ddr1_internal_whs >= 0.0 &&
    $core_boundary_in_wns >= 0.0 && $core_boundary_in_whs >= 0.0 &&
    $ddr0_boundary_in_wns >= 0.0 && $ddr0_boundary_in_whs >= 0.0 &&
    $ddr1_boundary_in_wns >= 0.0 && $ddr1_boundary_in_whs >= 0.0 &&
    $core_boundary_out_wns >= 0.0 && $core_boundary_out_whs >= 0.0 &&
    $ddr0_boundary_out_wns >= 0.0 && $ddr0_boundary_out_whs >= 0.0 &&
    $ddr1_boundary_out_wns >= 0.0 && $ddr1_boundary_out_whs >= 0.0}]
set route_clean [expr {$route_errors == 0 &&
    $unrouted_rows == 0 && $unrouted_pins == 0 &&
    $resource_conflicts == 0 && $antennas == 0 &&
    $conflict_status == 0 && $clock_alias_audit_ok &&
    $reset_gap_audit_ok}]
set status [expr {$all_timing_ok && $route_clean && $drc_errors == 0 &&
    $cdc_critical == 0 && $unconstrained == 0 && $dsp == 0 && $uram == 0 ?
    "REGISTERED_OOC_PROXY_PASS_EXPECTED_RESET_PARTPIN_GAPS" :
    "REGISTERED_OOC_POST_ROUTE_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
    wns_ns $wns whs_ns $whs \
    core_internal_wns_ns $core_internal_wns core_internal_whs_ns $core_internal_whs \
    ddr0_internal_wns_ns $ddr0_internal_wns ddr0_internal_whs_ns $ddr0_internal_whs \
    ddr1_internal_wns_ns $ddr1_internal_wns ddr1_internal_whs_ns $ddr1_internal_whs \
    core_boundary_in_wns_ns $core_boundary_in_wns core_boundary_in_whs_ns $core_boundary_in_whs \
    ddr0_boundary_in_wns_ns $ddr0_boundary_in_wns ddr0_boundary_in_whs_ns $ddr0_boundary_in_whs \
    ddr1_boundary_in_wns_ns $ddr1_boundary_in_wns ddr1_boundary_in_whs_ns $ddr1_boundary_in_whs \
    core_boundary_out_wns_ns $core_boundary_out_wns core_boundary_out_whs_ns $core_boundary_out_whs \
    ddr0_boundary_out_wns_ns $ddr0_boundary_out_wns ddr0_boundary_out_whs_ns $ddr0_boundary_out_whs \
    ddr1_boundary_out_wns_ns $ddr1_boundary_out_wns ddr1_boundary_out_whs_ns $ddr1_boundary_out_whs \
    core_source_boundary_ff $core_src_count ddr0_source_boundary_ff $ddr0_src_count \
    ddr1_source_boundary_ff $ddr1_src_count core_sink_boundary_ff $core_sink_count \
    ddr0_sink_boundary_ff $ddr0_sink_count ddr1_sink_boundary_ff $ddr1_sink_count \
    boundary_ff_total $boundary_ff_count lut_primitives $lut ff_primitives $ff \
    ramb36e2 $ramb36 ramb18e2 $ramb18 dsp48e2 $dsp uram288 $uram \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts antenna_island_nets $antennas \
    route_status_partial $partial_status route_status_conflicts $conflict_status \
    partial_clock_aliases [llength $partial_all] \
    bad_partial_nets [llength $bad_partial] \
    partial_clock_roots [join $partial_clock_roots ,] \
    reset_hierport_aliases [llength $hierport_all] \
    bad_hierport_nets [llength $bad_hierport] \
    reset_gap_roots [join $reset_roots ,] \
    route35198_reset_port_audit $route35198_ok \
    ooc_reset_explicit_gaps_accepted [expr {$reset_gap_audit_ok ? 3 : 0}] \
    drc_errors $drc_errors cdc_critical $cdc_critical \
    unconstrained_paths $unconstrained status $status] {puts $fp "$key=$value"}
close $fp
puts "REGISTERED_PAIRED_WRR_OOC WNS=$wns WHS=$whs ROUTE_ERRORS=$route_errors PARTIAL=$partial_status CONFLICTS=$conflict_status CDC=$cdc_critical STATUS=$status"
if {$status ne "REGISTERED_OOC_PROXY_PASS_EXPECTED_RESET_PARTPIN_GAPS"} {
    error "Registered paired AXI512 arbiter OOC acceptance failed"
}
