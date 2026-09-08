set out [file normalize $::env(HAP_REPORT_DIR)]
set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
file mkdir $out
if {![file exists $input_dcp]} {error "missing input DCP $input_dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set jobs 32
if {[info exists ::env(HAP_JOBS)]} {set jobs $::env(HAP_JOBS)}
set_param general.maxThreads $jobs
open_checkpoint $input_dcp

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc audit_weight_capture_class {label name_glob expected_nets expected_loads} {
    set nets [lsort -dictionary [get_nets -quiet -hierarchical -filter \
        "NAME =~ $name_glob"]]
    require_count ${label}_nets $nets $expected_nets
    set min_load 1000000000
    set max_load 0
    foreach net $nets {
        set driver_pins [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        require_count ${label}_driver_pin $driver_pins 1
        set driver [get_cells -quiet -of_objects $driver_pins]
        require_count ${label}_driver $driver 1
        if {[get_property REF_NAME $driver] ne "LUT2"} {
            error "$label capture driver is not a LUT2: $driver"
        }
        set loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN}]
        require_count ${label}_loads $loads $expected_loads
        set ce_loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN && REF_PIN_NAME == CE}]
        require_count ${label}_ce_loads $ce_loads $expected_loads
        set load_count [llength $loads]
        if {$load_count < $min_load} {set min_load $load_count}
        if {$load_count > $max_load} {set max_load $load_count}
    }
    return [list [llength $nets] $min_load $max_load]
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

set src_count [require_count source_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ src_r_reg* && REF_NAME =~ FD*}] 10600]
set sink_count [require_count sink_proxy_ff \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ sink_r_reg* && REF_NAME =~ FD*}] 3327]
require_count top_port_count [get_ports -quiet] 1
set lane_count [require_count attention_lane_instances \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && (REF_NAME == hap_a8w8_group32_lane_s42 || \
         ORIG_REF_NAME == hap_a8w8_group32_lane_s42)}] 128]
set dual_accumulator_count [require_count local_dual_accumulator_instances \
    [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/* && (REF_NAME == hap_linear_tile_accum_dual_s42 || \
         ORIG_REF_NAME == hap_linear_tile_accum_dual_s42)}] 6]
set accum_context_count [expr {$dual_accumulator_count * 2}]
if {$accum_context_count != 12} {
    error "local accumulator context mismatch: expected=12 actual=$accum_context_count"
}

set raw_weight_push [get_nets -quiet -hierarchical -filter \
    {NAME == u_dut/weight_push}]
require_count raw_weight_push_net $raw_weight_push 1
set raw_weight_push_loads [get_pins -quiet -leaf \
    -of_objects $raw_weight_push -filter {DIRECTION == IN}]
require_count raw_weight_push_loads $raw_weight_push_loads 37
set weight_data_capture [audit_weight_capture_class weight_data \
    {u_dut/weight_data_capture_enable*} 32 256]
set weight_meta_capture [audit_weight_capture_class weight_meta \
    {u_dut/weight_meta_capture_enable*} 2 256]
set weight_group_capture [audit_weight_capture_class weight_group \
    {u_dut/weight_group_capture_enable*} 2 7]

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
set tfp [open [file join $out timing_post_synth_audit.rpt] w]
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

report_utilization -file [file join $out utilization_post_synth_audit.rpt]
report_utilization -hierarchical -hierarchical_depth 20 -file \
    [file join $out utilization_hier_post_synth_audit.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage_post_synth_audit.rpt]
report_drc -file [file join $out drc_post_synth_audit.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set efp [open [file join $out exceptions_coverage_post_synth_audit.rpt] r]
set exception_text [read $efp]
close $efp
set no_timing_exceptions [expr {
    [string first "No timing exceptions found." $exception_text] >= 0}]
set wns [get_slack max]
set whs [get_slack min]
set structural_ok [expr {$lane_count == 128 && \
    $accum_context_count == 12 && $dut_dsp == 2240 && \
    $array_dsp == 2176 && $frontend_dsp == 64 && \
    [llength $raw_weight_push_loads] == 37 && \
    [lindex $weight_data_capture 0] == 32 && \
    [lindex $weight_meta_capture 0] == 2 && \
    [lindex $weight_group_capture 0] == 2}]
set status [expr {$structural_ok && $wns >= 0.0 && $data_bufg == 0 && \
    $no_timing_exceptions && $timing_coverage_ok && $drc_errors == 0 ? \
    "PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] \
    part xcvu9p-flga2104-2L-e \
    top hap_projection_core16x16_w8_reuse_registered_ooc_harness \
    stage INDEPENDENT_POST_SYNTH_DCP_AUDIT input_dcp $input_dcp jobs $jobs \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    attention_lane_instances $lane_count \
    local_dual_accumulator_instances $dual_accumulator_count \
    local_accumulator_contexts $accum_context_count \
    raw_weight_push_loads [llength $raw_weight_push_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_loads \
        [lindex $weight_data_capture 1]/[lindex $weight_data_capture 2] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_loads \
        [lindex $weight_meta_capture 1]/[lindex $weight_meta_capture 2] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_loads \
        [lindex $weight_group_capture 1]/[lindex $weight_group_capture 2] \
    dut_dsp48e2 $dut_dsp array_dsp48e2 $array_dsp \
    frontend_dsp48e2 $frontend_dsp dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_uram288 $dut_uram \
    wns_ns $wns whs_diagnostic_ns $whs setup_timing_ok [expr {$wns >= 0.0}] \
    clock_bufg $clock_bufg data_bufg $data_bufg drc_errors $drc_errors \
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
puts "PROJECTION_REUSE_DCP_AUDIT DSP=$dut_dsp ARRAY_DSP=$array_dsp FRONTEND_DSP=$frontend_dsp LANES=$lane_count ACCUM_CONTEXTS=$accum_context_count WNS=$wns DATA_BUFG=$data_bufg DRC_ERRORS=$drc_errors STATUS=$status"
if {$status ne "PASS"} {error "projection reuse post-synth audit failed"}
