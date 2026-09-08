set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
file mkdir $out
cd $root

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc property_true {object property_name} {
    set value [string tolower [get_property $property_name $object]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

proc first_slack {delay from_set to_set label} {
    set paths [get_timing_paths -quiet -delay_type $delay -max_paths 1 \
        -from $from_set -to $to_set]
    if {[llength $paths] != 1} {error "$label path set is empty"}
    return [get_property SLACK [lindex $paths 0]]
}

proc audit_local_clear {} {
    set root [get_cells -quiet u_dut]
    require_count swiglu_dut $root 1
    set control [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/control_clear_local_r_reg* && REF_NAME =~ FD*}]
    set hadamard [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/hadamard_clear_local_r_reg* && REF_NAME =~ FD*}]
    set quantizer [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/quantizer_clear_local_r_reg* && REF_NAME =~ FD*}]
    set row_leaves [get_cells -quiet -hierarchical -filter {
        NAME =~ u_dut/* && (REF_NAME == hap_mlp_swiglu_row_stream8_q4 ||
        ORIG_REF_NAME == hap_mlp_swiglu_row_stream8_q4)}]
    require_count swiglu_row_clear_roots $row_leaves 2
    set row_candidates [get_cells -quiet -hierarchical -filter {
        NAME =~ */clear_local_r_reg* && REF_NAME =~ FD*}]
    set row_clear {}
    foreach leaf [lsort -dictionary $row_leaves] {
        set prefix "[get_property NAME $leaf]/"
        set local {}
        foreach cell $row_candidates {
            if {[string first $prefix [get_property NAME $cell]] == 0} {
                lappend local $cell
            }
        }
        require_count swiglu_row_clear_ff_per_leaf $local 1
        set row_clear [concat $row_clear $local]
    }
    set row_clear [lsort -dictionary -unique $row_clear]
    require_count swiglu_control_clear_ff $control 1
    require_count swiglu_hadamard_clear_ff $hadamard 1
    require_count swiglu_quantizer_clear_ff $quantizer 4
    require_count swiglu_row_clear_ff $row_clear 2
    set all_clear [lsort -dictionary -unique \
        [concat $control $hadamard $quantizer $row_clear]]
    require_count swiglu_local_clear_ff $all_clear 8
    set protected 0
    foreach cell $all_clear {
        if {![property_true $cell DONT_TOUCH]} {
            error "SwiGLU local-clear FF lost DONT_TOUCH: $cell"
        }
        incr protected
    }
    set d_pins [get_pins -quiet -of_objects $all_clear -filter \
        {REF_PIN_NAME == D}]
    require_count swiglu_local_clear_d_pins $d_pins 8
    set clear_nets [lsort -dictionary -unique \
        [get_nets -quiet -of_objects $d_pins]]
    set direct_cells [lsort -dictionary -unique [get_cells -quiet \
        -of_objects [get_pins -quiet -leaf -of_objects $clear_nets \
            -filter {DIRECTION == IN}]]]
    set bypass {}
    foreach cell $direct_cells {
        if {[string match {u_dut/*} [get_property NAME $cell]] &&
            [lsearch -exact $all_clear $cell] < 0} {
            lappend bypass $cell
        }
    }
    set bypass [lsort -dictionary -unique $bypass]
    require_count swiglu_direct_clear_bypass_state $bypass 0
    return [dict create total 8 protected $protected control 1 hadamard 1 \
        quantizer 4 row 2 input_nets [llength $clear_nets] bypass 0]
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
if {[llength [get_designs -quiet]] != 0} {
    error "SwiGLU registered OOC requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "SwiGLU registered OOC requires HAP_JOBS=32"
}
set_param general.maxThreads $jobs

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl attention hap_u16_div_u8_seq.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_silu_mul.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_hadamard32_s32_norm_stream.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_robust_a8_quantizer_s35.sv]
read_verilog -sv [file join $root rtl mlp hap_mlp_swiglu_product_frontend16_q4.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness.sv]
read_xdc [file join $root vivado constraints \
    mlp_swiglu_product_frontend16_q4_registered_ooc_100mhz.xdc]
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
require_count source_proxy_ff $src 6150
require_count sink_proxy_ff $sink 4611
set pre_clear [audit_local_clear]

opt_design -directive Explore
set dut_nonclock_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore

set dut_regs [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]
if {[llength $dut_regs] == 0} {error "SwiGLU DUT register set is empty"}
set post_clear [audit_local_clear]

set wns [get_property SLACK [lindex \
    [get_timing_paths -delay_type max -max_paths 1] 0]]
set whs [get_property SLACK [lindex \
    [get_timing_paths -delay_type min -max_paths 1] 0]]
set source_to_dut_wns [first_slack max $src $dut_regs source_to_dut_setup]
set source_to_dut_whs [first_slack min $src $dut_regs source_to_dut_hold]
set dut_internal_wns [first_slack max $dut_regs $dut_regs dut_internal_setup]
set dut_internal_whs [first_slack min $dut_regs $dut_regs dut_internal_hold]
set dut_to_sink_wns [first_slack max $dut_regs $sink dut_to_sink_setup]
set dut_to_sink_whs [first_slack min $dut_regs $sink dut_to_sink_hold]

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation \
    -file [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -from $src -to $dut_regs \
    -file [file join $out source_to_dut_setup_worst100.rpt]
report_timing -delay_type min -max_paths 100 -from $src -to $dut_regs \
    -file [file join $out source_to_dut_hold_worst100.rpt]
report_timing -delay_type max -max_paths 100 -from $dut_regs -to $dut_regs \
    -file [file join $out dut_internal_setup_worst100.rpt]
report_timing -delay_type min -max_paths 100 -from $dut_regs -to $dut_regs \
    -file [file join $out dut_internal_hold_worst100.rpt]
report_timing -delay_type max -max_paths 100 -from $dut_regs -to $sink \
    -file [file join $out dut_to_sink_setup_worst100.rpt]
report_timing -delay_type min -max_paths 100 -from $dut_regs -to $sink \
    -file [file join $out dut_to_sink_hold_worst100.rpt]
report_utilization -hierarchical -hierarchical_depth 8 \
    -file [file join $out utilization.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]

set route_errors [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength $dut_regs]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set hadamard_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_hadamard/* && REF_NAME == DSP48E2}]]
set silu_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/g_row_branch*.u_branch_leaf/u_silu/* &&
     REF_NAME == DSP48E2}]]
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
require_count swiglu_hadamard_instances [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_mlp_hadamard32_s32_norm_stream ||
    ORIG_REF_NAME == hap_mlp_hadamard32_s32_norm_stream)}] 1
require_count swiglu_quantizer_instances [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_mlp_robust_a8_quantizer_s35 ||
    ORIG_REF_NAME == hap_mlp_robust_a8_quantizer_s35)}] 4
require_count swiglu_row_instances [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_mlp_swiglu_row_stream8_q4 ||
    ORIG_REF_NAME == hap_mlp_swiglu_row_stream8_q4)}] 2

set all_bufg [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}]
set clock_bufg 0
set data_bufg 0
foreach cell $all_bufg {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] > 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}
set top_ports [get_ports -quiet]
set nonclock_top_ports [get_ports -quiet -filter {NAME != clk}]
set exceptions_fh [open [file join $out exceptions_coverage.rpt] r]
set exceptions_text [read $exceptions_fh]
close $exceptions_fh
set max_delay_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+Max Delay[[:space:]]} $exceptions_text]
set min_delay_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+Min Delay[[:space:]]} $exceptions_text]
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} $exceptions_text]

set status [expr {$wns >= 0.0 && $whs >= 0.0 &&
    $source_to_dut_wns >= 0.0 && $source_to_dut_whs >= 0.0 &&
    $dut_internal_wns >= 0.0 && $dut_internal_whs >= 0.0 &&
    $dut_to_sink_wns >= 0.0 && $dut_to_sink_whs >= 0.0 &&
    $route_errors == 0 && $conflicts == 0 && $drc_errors == 0 &&
    $dut_dsp == 68 && $hadamard_dsp == 64 && $silu_dsp == 4 &&
    $dut_ramb36 == 12 && $dut_ramb18 == 0 &&
    $dut_uram == 0 && $data_bufg == 0 && [llength $top_ports] == 1 &&
    [llength $nonclock_top_ports] == 0 &&
    $max_delay_rows == 0 && $min_delay_rows == 0 &&
    $false_path_rows == 0 && [dict get $pre_clear total] == 8 &&
    [dict get $post_clear total] == 8 &&
    [dict get $post_clear protected] == 8 &&
    [dict get $post_clear bypass] == 0 ?
    "REGISTERED_OOC_ROUTE_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top jobs $jobs \
    clock_mhz 100 clock_period_ns 10.000 source_proxy_ff [llength $src] \
    sink_proxy_ff [llength $sink] dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_dsp48e2 $dut_dsp dut_uram288 $dut_uram \
    swiglu_hadamard_dsp48e2 $hadamard_dsp \
    swiglu_silu_dsp48e2 $silu_dsp \
    swiglu_local_clear_ff [dict get $post_clear total] \
    swiglu_local_clear_protected_ff [dict get $post_clear protected] \
    swiglu_control_clear_ff [dict get $post_clear control] \
    swiglu_hadamard_clear_ff [dict get $post_clear hadamard] \
    swiglu_quantizer_clear_ff [dict get $post_clear quantizer] \
    swiglu_row_clear_ff [dict get $post_clear row] \
    swiglu_clear_input_nets [dict get $post_clear input_nets] \
    swiglu_direct_clear_bypass_state [dict get $post_clear bypass] \
    wns_ns $wns whs_ns $whs source_to_dut_wns_ns $source_to_dut_wns \
    source_to_dut_whs_ns $source_to_dut_whs \
    dut_internal_wns_ns $dut_internal_wns \
    dut_internal_whs_ns $dut_internal_whs \
    dut_to_sink_wns_ns $dut_to_sink_wns \
    dut_to_sink_whs_ns $dut_to_sink_whs top_port_count [llength $top_ports] \
    nonclock_top_port_count [llength $nonclock_top_ports] \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    max_delay_exception_rows $max_delay_rows \
    min_delay_exception_rows $min_delay_rows \
    false_path_exception_rows $false_path_rows \
    unrouted_or_partial_nets $route_errors conflict_nets $conflicts \
    drc_errors $drc_errors status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "REGISTERED_OOC_ROUTE_PASS"} {
    error "SwiGLU registered OOC route gate failed"
}
write_checkpoint -force [file join $out post_route.dcp]
close_project
