set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_tensor_dma_bridge_registered_ooc_harness
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required, got [version -short]"
}

proc actual_pin_loads {net} {
    return [llength [get_pins -quiet -leaf -of_objects $net \
        -filter {DIRECTION == IN}]]
}

proc nonclock_nets {nets} {
    set result {}
    foreach net $nets {
        if {[llength [get_clocks -quiet -of_objects $net]] == 0} {
            lappend result $net
        }
    }
    return $result
}

set xdc_path [file join $root vivado constraints \
    mlp_tensor_dma_bridge_registered_ooc_150mhz.xdc]
set script_path [file normalize [info script]]
set audit_text ""
foreach path [list $xdc_path $script_path] {
    set fp [open $path r]; append audit_text [read $fp]; close $fp
}
set forbidden_pattern [join [list "set_false" "_path|set_clock" \
    "_groups|set_max" "_delay|set_min" "_delay|-datapath" "_only"] ""]
set forbidden_count [regexp -all -nocase $forbidden_pattern $audit_text]
if {$forbidden_count != 0} {
    error "tensor DMA registered OOC contains forbidden timing exception"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl attention hap_axi256_dma.sv]
read_verilog -sv [file join $root rtl integration \
    hap_mlp_tensor_dma_bridge.sv]
read_verilog -sv [file join $root rtl integration \
    hap_mlp_tensor_dma_bridge_registered_ooc_harness.sv]
read_xdc $xdc_path
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
if {[llength $src] != 6489 || [llength $sink] != 12822} {
    error "registered proxy FF mismatch src=[llength $src] sink=[llength $sink]"
}
if {[llength [get_cells -quiet u_dut]] != 1} {
    error "tensor DMA DUT hierarchy missing"
}

set dut_cells [get_cells -quiet -hierarchical -filter {NAME =~ u_dut/*}]
set dut_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
set dut_nonclock_nets [nonclock_nets $dut_nets]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets

# Post-synth actual load accounting.  Derive the input controls from the CE
# pins of all 12,288 input-bank FFs and the output controls from the CE pins
# of all 6,144 output-bank FFs.  This proves the physical control topology
# without depending on one generated-register spelling.
set fanout_fp [open [file join $out fanout_post_synth.tsv] w]
puts $fanout_fp "class\tindex\tdriver\tnet\tflat_pin_loads"
set named_max 0
set named_rows 0
set input_bank_cells [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/*input_group_beat_r_reg* && REF_NAME =~ FD*}]
set output_bank_cells [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/*output_tile_beat_r_reg* && REF_NAME =~ FD*}]
if {[llength $input_bank_cells] != 12288 || \
    [llength $output_bank_cells] != 6144} {
    error "bank FF count mismatch input=[llength $input_bank_cells] output=[llength $output_bank_cells]"
}
foreach {class cells expected_controls} [list input $input_bank_cells 48 \
        output $output_bank_cells 24] {
    set control_nets {}
    foreach cell $cells {
        set ce [get_pins -quiet -of_objects $cell \
            -filter {REF_PIN_NAME == CE}]
        if {[llength $ce] != 1} {
            error "$class bank FF has no unique CE: $cell"
        }
        set net [get_nets -quiet -of_objects $ce]
        if {[llength $net] != 1} {
            error "$class bank FF CE has no unique net: $cell"
        }
        lappend control_nets [lindex $net 0]
    }
    set control_nets [lsort -unique $control_nets]
    if {[llength $control_nets] != $expected_controls} {
        error "$class local control count mismatch expected=$expected_controls actual=[llength $control_nets]"
    }
    set index 0
    foreach net $control_nets {
        set driver_pin [get_pins -quiet -leaf -of_objects $net \
            -filter {DIRECTION == OUT}]
        set loads [actual_pin_loads $net]
        if {$loads > $named_max} {set named_max $loads}
        incr named_rows
        puts $fanout_fp "$class\t$index\t$driver_pin\t$net\t$loads"
        incr index
    }
}

set all_max 0
set all_max_net ""
foreach net $dut_nonclock_nets {
    set loads [actual_pin_loads $net]
    if {$loads > $all_max} {set all_max $loads; set all_max_net $net}
}
puts $fanout_fp "all_dut_nonclock\tmax\t-\t$all_max_net\t$all_max"
close $fanout_fp

opt_design -directive Explore
set dut_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
set dut_nonclock_nets [nonclock_nets $dut_nets]
set_property CLOCK_BUFFER_TYPE NONE $dut_nonclock_nets
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation \
    -file [file join $out timing_summary.rpt]
report_utilization -hierarchical -hierarchical_depth 8 \
    -file [file join $out utilization_hierarchical.rpt]
report_utilization -file [file join $out utilization.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_clock_utilization -file [file join $out clock_utilization.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_paths] != 1 || [llength $hold_paths] != 1} {
    error "registered OOC timing paths missing"
}
set wns [get_property SLACK [lindex $setup_paths 0]]
set whs [get_property SLACK [lindex $hold_paths 0]]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_bram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ RAMB*}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set data_bufg 0
set clock_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set output [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $output]] > 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}
set exceptions_fp [open [file join $out exceptions_coverage.rpt] r]
set exceptions_text [read $exceptions_fp]; close $exceptions_fp
set exception_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+(Max Delay|Min Delay|False Path)[[:space:]]} \
    $exceptions_text]
set route_gap_count 0
set log_path [file join $out vivado.log]
if {[file exists $log_path]} {
    set log_fp [open $log_path r]; set log_text [read $log_fp]; close $log_fp
    set route_gap_count [regexp -all {Route 35-198} $log_text]
}

set status [expr {$wns >= 0.0 && $whs >= 0.0 && $unrouted == 0 &&
    $conflicts == 0 && $drc_errors == 0 && $data_bufg == 0 &&
    $dut_dsp == 0 && $dut_bram == 0 && $dut_uram == 0 &&
    $forbidden_count == 0 && $exception_rows == 0 &&
    $route_gap_count == 0 && $named_rows == 72 && $named_max <= 256 ?
    "REGISTERED_EXCEPTION_FREE_OOC_PASS" : "FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    clock_mhz 150.015 source_proxy_ff [llength $src] \
    sink_proxy_ff [llength $sink] dut_lut_primitives $dut_lut \
    dut_ff_primitives $dut_ff dut_dsp48e2 $dut_dsp \
    dut_bram_primitives $dut_bram dut_uram288 $dut_uram \
    named_fanout_rows $named_rows named_max_fanout $named_max \
    all_dut_nonclock_max_fanout $all_max \
    all_dut_nonclock_max_fanout_net $all_max_net \
    wns_ns $wns whs_ns $whs clock_bufg $clock_bufg data_bufg $data_bufg \
    unrouted_nets $unrouted conflict_nets $conflicts drc_errors $drc_errors \
    route_gap_count $route_gap_count forbidden_timing_exception_count \
    $forbidden_count exception_rows $exception_rows status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "REGISTERED_EXCEPTION_FREE_OOC_PASS"} {
    error "tensor DMA registered OOC gate failed"
}
close_project
