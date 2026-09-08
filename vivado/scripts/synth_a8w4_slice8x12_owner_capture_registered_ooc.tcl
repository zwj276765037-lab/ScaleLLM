set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_a8w4_slice8x12_group_registered_ooc_harness
set constraint [file join $root vivado constraints \
    a8w4_slice8x12_group_registered_ooc_100mhz.xdc]
file mkdir $out
file mkdir $build
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set jobs 32
if {[info exists ::env(HAP_JOBS)]} {set jobs $::env(HAP_JOBS)}
set_param general.maxThreads $jobs

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc get_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} {return -999.0}
    return [get_property SLACK [lindex $paths 0]]
}

proc check_timing_count {text check_name} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $check_name]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "check_timing category '$check_name' is missing"
    }
    return $count
}

set fp [open $constraint r]
set xdc_text [read $fp]
close $fp
set forbidden_exceptions [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only|set_multicycle_path} \
    $xdc_text]
if {$forbidden_exceptions != 0} {
    error "MLP kernel OOC XDC contains a forbidden timing exception"
}

create_project mlp_owner_capture_ooc $build -part $part -force
set_property target_language Verilog [current_project]
foreach file {
    hap_a8w4_pack2_dsp.sv
    hap_a8w4_group32_pack2_s17.sv
    hap_a8w4_scalecode_recover2_lut.sv
    hap_a8w4_group32_lane2_s36.sv
    hap_a8w4_slice8x12_group_s36.sv
    hap_a8w4_slice8x12_group_registered_ooc_harness.sv
} {
    set path [file join $root rtl mlp $file]
    add_files -fileset sources_1 $path
    set_property file_type SystemVerilog [get_files $path]
}
add_files -fileset constrs_1 -norecurse $constraint
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized

set src_count [require_count source_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ src_r_reg* && REF_NAME =~ FD*}] 4136]
set sink_count [require_count sink_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ sink_r_reg* && REF_NAME =~ FD*}] 3523]
require_count dut_instance [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1
set lane_count [require_count mlp_pack2_lane_instances \
    [get_cells -quiet -hierarchical -filter {
        NAME =~ u_dut/* && (REF_NAME == hap_a8w4_group32_lane2_s36 ||
        ORIG_REF_NAME == hap_a8w4_group32_lane2_s36)}] 48]
set leaf_count [require_count ingress_capture_leaf_instances \
    [get_cells -quiet -hierarchical -filter {
        NAME =~ u_dut/* && (REF_NAME == hap_a8w4_ingress_capture_leaf ||
        ORIG_REF_NAME == hap_a8w4_ingress_capture_leaf)}] 816]
set leaf_lut [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/*/u_leaf && REF_NAME == LUT1}]
set leaf_lut_count [require_count ingress_capture_leaf_lut1 $leaf_lut 816]

set leaf_min_load 1000000000
set leaf_max_load 0
set leaf_total_load 0
set leaf_load32_count 0
set leaf_load36_count 0
set leaf_load42_count 0
set leaf_non_ce_endpoints 0
foreach cell $leaf_lut {
    set output_pin [get_pins -quiet -of_objects $cell -filter {
        DIRECTION == OUT}]
    require_count ingress_capture_leaf_output $output_pin 1
    # The LUT is inside a preserved leaf module, while its CE sinks are in the
    # parent lane.  Net segments stop at that hierarchy port; endpoint fanout
    # is the authoritative cross-hierarchy connectivity query.
    set endpoints [all_fanout -quiet -flat -endpoints_only -from $output_pin]
    set loads [filter $endpoints {IS_LEAF && REF_PIN_NAME == CE}]
    set load_count [llength $loads]
    incr leaf_total_load $load_count
    incr leaf_non_ce_endpoints [expr {[llength $endpoints] - $load_count}]
    if {$load_count == 32} {incr leaf_load32_count}
    if {$load_count == 36} {incr leaf_load36_count}
    if {$load_count == 42} {incr leaf_load42_count}
    if {$load_count < $leaf_min_load} {set leaf_min_load $load_count}
    if {$load_count > $leaf_max_load} {set leaf_max_load $load_count}
}
set leaf_load_ok [expr {$leaf_min_load == 32 && $leaf_max_load == 42 &&
    $leaf_total_load == 28128 && $leaf_load32_count == 384 &&
    $leaf_load36_count == 384 && $leaf_load42_count == 48 &&
    $leaf_non_ce_endpoints == 0}]

set dut_dsp [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {
        DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
    }
}

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set fp [open [file join $out timing_post_synth.rpt] w]
puts $fp $timing_text
close $fp
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_text no_input_delay]
set no_output_delay [check_timing_count $timing_text no_output_delay]
set partial_input_delay [check_timing_count $timing_text partial_input_delay]
set partial_output_delay [check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 && \
    $no_input_delay == 0 && $no_output_delay == 0 && \
    $partial_input_delay == 0 && $partial_output_delay == 0}]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_synth.rpt]
report_high_fanout_nets -timing -max_nets 300 -file \
    [file join $out high_fanout_post_synth.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage_post_synth.rpt]
report_drc -file [file join $out drc_post_synth.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set fp [open [file join $out exceptions_coverage_post_synth.rpt] r]
set exception_text [read $fp]
close $fp
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exception_text] >= 0}]
set wns [get_slack max]
set whs [get_slack min]
set structural_ok [expr {$lane_count == 48 && $leaf_count == 816 &&
    $leaf_lut_count == 816 && $leaf_load_ok && $dut_dsp == 1536}]
set status [expr {$structural_ok && $wns >= 0.0 && $data_bufg == 0 &&
    $forbidden_exceptions == 0 && $no_timing_exceptions &&
    $timing_coverage_ok ? "PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    stage OWNER_CAPTURE_REGISTERED_OOC_POST_SYNTH clock_mhz 100 jobs $jobs \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    mlp_pack2_lane_instances $lane_count \
    ingress_capture_leaf_instances $leaf_count \
    ingress_capture_leaf_lut1 $leaf_lut_count \
    ingress_capture_leaf_min_ce_load $leaf_min_load \
    ingress_capture_leaf_max_ce_load $leaf_max_load \
    ingress_capture_leaf_total_ce_loads $leaf_total_load \
    ingress_capture_leaf_load32_count $leaf_load32_count \
    ingress_capture_leaf_load36_count $leaf_load36_count \
    ingress_capture_leaf_load42_count $leaf_load42_count \
    ingress_capture_leaf_non_ce_endpoints $leaf_non_ce_endpoints \
    ingress_capture_leaf_load_ok $leaf_load_ok dut_dsp48e2 $dut_dsp \
    dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff wns_ns $wns \
    whs_diagnostic_ns $whs setup_timing_ok [expr {$wns >= 0.0}] \
    data_bufg $data_bufg \
    forbidden_timing_exception_count $forbidden_exceptions \
    no_timing_exceptions $no_timing_exceptions \
    no_clock_endpoints $no_clock \
    unconstrained_internal_endpoints $unconstrained \
    no_input_delay_endpoints $no_input_delay \
    no_output_delay_endpoints $no_output_delay \
    partial_input_delay_endpoints $partial_input_delay \
    partial_output_delay_endpoints $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok structural_ok $structural_ok \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "MLP_OWNER_CAPTURE_OOC WNS=$wns DSP=$dut_dsp LANES=$lane_count LEAVES=$leaf_count LOADS=$leaf_min_load/$leaf_max_load STATUS=$status"
if {$status ne "PASS"} {
    error "MLP owner/capture registered OOC synth gate failed"
}
