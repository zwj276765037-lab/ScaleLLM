set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_projection_core16x16_w8_reuse_registered_ooc_harness
set manifest [file join $root vivado manifests \
    attention_projection_core16x16_w8_reuse_sources.list]
set constraint [file join $root vivado constraints \
    projection_core16x16_w8_reuse_registered_ooc_150mhz.xdc]
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

set xfp [open $constraint r]
set xdc_text [read $xfp]
close $xfp
set forbidden_exceptions [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only|set_multicycle_path} \
    $xdc_text]
if {$forbidden_exceptions != 0} {
    error "projection reuse OOC XDC contains a forbidden exception"
}

create_project projection_reuse_ooc $build -part $part -force
set_property target_language Verilog [current_project]
set mfp [open $manifest r]
foreach raw [split [read $mfp] "\n"] {
    set line [string trim $raw]
    if {$line eq "" || [string index $line 0] eq "#"} {continue}
    set path [file normalize [file join $root $line]]
    if {![file exists $path]} {error "missing source $path"}
    add_files -fileset sources_1 $path
    set_property file_type SystemVerilog [get_files $path]
}
close $mfp
set harness [file join $root rtl attention \
    hap_projection_core16x16_w8_reuse_registered_ooc_harness.sv]
add_files -fileset sources_1 $harness
set_property file_type SystemVerilog [get_files $harness]
add_files -fileset constrs_1 -norecurse $constraint
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set src_count [require_count source_proxy_ff $src 10600]
set sink_count [require_count sink_proxy_ff $sink 3327]
require_count dut_instance [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1

set lanes [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && (REF_NAME == hap_a8w8_group32_lane_s42 || \
     ORIG_REF_NAME == hap_a8w8_group32_lane_s42)}]
set dual_accumulators [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && (REF_NAME == hap_linear_tile_accum_dual_s42 || \
     ORIG_REF_NAME == hap_linear_tile_accum_dual_s42)}]
set lane_count [require_count attention_lane_instances $lanes 128]
set dual_accumulator_count [require_count local_dual_accumulator_instances \
    $dual_accumulators 6]
set accum_context_count [expr {$dual_accumulator_count * 2}]
if {$accum_context_count != 12} {
    error "local accumulator context mismatch: expected=12 actual=$accum_context_count"
}

set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set array_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_array/* && REF_NAME == DSP48E2}]]
set frontend_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_frontend/* && REF_NAME == DSP48E2}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set tfp [open [file join $out timing_post_synth.rpt] w]
puts $tfp $timing_text
close $tfp
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

report_utilization -file [file join $out utilization_post_synth.rpt]
report_utilization -hierarchical -hierarchical_depth 20 -file \
    [file join $out utilization_hier_post_synth.rpt]
report_high_fanout_nets -max_nets 300 -timing -file \
    [file join $out high_fanout_post_synth.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_synth.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage_post_synth.rpt]
report_drc -file [file join $out drc_post_synth.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set efp [open [file join $out exceptions_coverage_post_synth.rpt] r]
set exception_text [read $efp]
close $efp
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exception_text] >= 0}]
set wns [get_slack max]
set whs [get_slack min]
set structural_ok [expr {$lane_count == 128 && \
    $accum_context_count == 12 && $dut_dsp == 2240 && \
    $array_dsp == 2176 && $frontend_dsp == 64}]
set setup_ok [expr {$wns >= 0.0}]
set status [expr {$structural_ok && $setup_ok && $data_bufg == 0 && \
    $forbidden_exceptions == 0 && $no_timing_exceptions && \
    $timing_coverage_ok ? "PASS" : "FAIL"}]

set sfp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    stage REGISTERED_OOC_POST_SYNTH clock_mhz 150 jobs $jobs \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    attention_lane_instances $lane_count local_dual_accumulator_instances \
    $dual_accumulator_count local_accumulator_contexts \
    $accum_context_count dut_dsp48e2 $dut_dsp array_dsp48e2 $array_dsp \
    frontend_dsp48e2 $frontend_dsp dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_uram288 $dut_uram \
    wns_ns $wns whs_diagnostic_ns $whs setup_timing_ok $setup_ok \
    clock_bufg $clock_bufg data_bufg $data_bufg \
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
    puts $sfp "$key=$value"
}
close $sfp
puts "PROJECTION_REUSE_OOC WNS=$wns WHS_DIAGNOSTIC=$whs DSP=$dut_dsp ARRAY_DSP=$array_dsp FRONTEND_DSP=$frontend_dsp LANES=$lane_count ACCUM_CONTEXTS=$accum_context_count RAMB36=$dut_ramb36 RAMB18=$dut_ramb18 DATA_BUFG=$data_bufg STATUS=$status"
if {$status ne "PASS"} {
    error "cohort16 projection reuse registered OOC synth gate failed"
}
