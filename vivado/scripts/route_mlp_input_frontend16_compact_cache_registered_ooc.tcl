set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_input_frontend16_compact_cache_registered_ooc_harness
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "compact-input registered OOC requires HAP_JOBS=32"
}
set_param general.maxThreads $jobs

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch: expected=$expected actual=$actual"
    }
    return $actual
}

proc actual_pin_loads {net} {
    return [llength [get_pins -quiet -leaf -of_objects $net \
        -filter {DIRECTION == IN}]]
}

proc first_slack {delay from_set to_set label} {
    set args [list -quiet -delay_type $delay -max_paths 1]
    if {[llength $from_set] != 0} {lappend args -from $from_set}
    if {[llength $to_set] != 0} {lappend args -to $to_set}
    set paths [get_timing_paths {*}$args]
    if {[llength $paths] == 0} {error "$label returned no timing path"}
    return [get_property SLACK [lindex $paths 0]]
}

proc capture_audit {out stage} {
    set row_ff [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/input_buffer_row_r_reg* && REF_NAME =~ FD*}]
    require_count ${stage}_input_buffer_ff $row_ff 12288

    set ce_pins [get_pins -quiet -of_objects $row_ff -filter \
        {REF_PIN_NAME == CE}]
    require_count ${stage}_input_buffer_ce_pin $ce_pins 12288
    set ce_nets [lsort -unique [get_nets -quiet -of_objects $ce_pins]]
    require_count ${stage}_capture_control_net $ce_nets 48

    set fp [open [file join $out capture_fanout_${stage}.tsv] w]
    puts $fp "index\tdriver_cell\tdriver_ref\tnet\tce_loads\tall_pin_loads\tdata_bufg_driver"
    set min_ce 1000000000
    set max_ce 0
    set max_all 0
    set bufg_driven 0
    set local_logic_driven 0
    set parent_nets {}
    set index 0
    foreach net $ce_nets {
        set ce [get_pins -quiet -leaf -of_objects $net -filter \
            {REF_PIN_NAME == CE && NAME =~ u_dut/input_buffer_row_r_reg*}]
        set ce_loads [llength $ce]
        set all_loads [actual_pin_loads $net]
        set drivers [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        require_count ${stage}_capture_net_driver_$index $drivers 1
        set driver_cell [get_cells -quiet -of_objects $drivers]
        require_count ${stage}_capture_driver_cell_$index $driver_cell 1
        set driver_ref [get_property REF_NAME $driver_cell]
        set is_bufg [expr {[string match "BUFG*" $driver_ref] ? 1 : 0}]
        incr bufg_driven $is_bufg
        if {[string match "LUT*" $driver_ref]} {incr local_logic_driven}
        set driver_inputs [get_pins -quiet -of_objects $driver_cell \
            -filter {REF_PIN_NAME == I0}]
        if {[llength $driver_inputs] == 1} {
            lappend parent_nets [get_nets -quiet -of_objects $driver_inputs]
        }
        if {$ce_loads < $min_ce} {set min_ce $ce_loads}
        if {$ce_loads > $max_ce} {set max_ce $ce_loads}
        if {$all_loads > $max_all} {set max_all $all_loads}
        puts $fp "$index\t$driver_cell\t$driver_ref\t$net\t$ce_loads\t$all_loads\t$is_bufg"
        incr index
    }

    set parent_nets [lsort -unique $parent_nets]
    set parent_max 0
    set parent_bufg_driven 0
    foreach net $parent_nets {
        set loads [actual_pin_loads $net]
        if {$loads > $parent_max} {set parent_max $loads}
        foreach pin [get_pins -quiet -leaf -of_objects $net -filter \
                {DIRECTION == OUT}] {
            set cell [get_cells -quiet -of_objects $pin]
            if {[string match "BUFG*" [get_property REF_NAME $cell]]} {
                incr parent_bufg_driven
            }
        }
    }
    puts $fp "parent\t-\t-\t$parent_nets\t-\t$parent_max\t$parent_bufg_driven"
    close $fp

    set ok [expr {$min_ce == 256 && $max_ce == 256 && \
        $max_all == 256 && $bufg_driven == 0 && \
        $local_logic_driven == 48 && \
        $parent_bufg_driven == 0}]
    return [list $ok [llength $row_ff] [llength $ce_nets] \
        $local_logic_driven $min_ce $max_ce $max_all $bufg_driven \
        [llength $parent_nets] $parent_max $parent_bufg_driven]
}

proc classify_bufg {out stage} {
    set fp [open [file join $out bufg_${stage}.tsv] w]
    puts $fp "cell\tref\tnet\tclock_count\tflat_pin_loads\tcapture_leaf_i0_hits\tcapture_ff_ce_hits"
    set clock_count 0
    set data_count 0
    set capture_data_count 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        set nets [get_nets -quiet -of_objects $outputs]
        set clocks [get_clocks -quiet -of_objects $outputs]
        set loads 0
        set leaf_hits 0
        set ce_hits 0
        foreach net $nets {
            incr loads [actual_pin_loads $net]
            incr leaf_hits [llength [get_pins -quiet -leaf -of_objects $net \
                -filter {NAME =~ u_dut/g_input_capture*/u_input_capture_enable/I0}]]
            incr ce_hits [llength [get_pins -quiet -leaf -of_objects $net \
                -filter {NAME =~ u_dut/input_buffer_row_r_reg*/CE}]]
        }
        if {[llength $clocks] != 0} {
            incr clock_count
        } else {
            incr data_count
            if {$leaf_hits != 0 || $ce_hits != 0} {
                incr capture_data_count
            }
        }
        puts $fp "$cell\t[get_property REF_NAME $cell]\t$nets\t[llength $clocks]\t$loads\t$leaf_hits\t$ce_hits"
    }
    close $fp
    return [list $clock_count $data_count $capture_data_count]
}

create_project -in_memory -part $part
foreach path [list \
        [file join $root rtl mlp hap_mlp_hadamard32_s24_fold4.sv] \
        [file join $root rtl attention hap_u16_div_u8_seq.sv] \
        [file join $root rtl attention hap_robust_a8_quantizer.sv] \
        [file join $root rtl attention hap_activation_cache_8row.sv] \
        [file join $root rtl mlp hap_mlp_input_frontend16_compact_cache.sv] \
        [file join $root rtl mlp \
            hap_mlp_input_frontend16_compact_cache_registered_ooc_harness.sv]] {
    read_verilog -sv $path
}
read_xdc [file join $root vivado constraints \
    mlp_input_frontend16_compact_cache_registered_ooc_150mhz.xdc]

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high

set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
set src_count [require_count source_proxy_ff $src 12311]
set sink_count [require_count sink_proxy_ff $sink 4623]
require_count compact_input_dut [get_cells -quiet u_dut] 1
require_count top_port_count [get_ports -quiet] 1

set dut_dsp_synth [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_ramb36_synth [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18_synth [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram_synth [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
lassign [capture_audit $out post_synth] capture_synth_ok \
    capture_ff_synth capture_controls_synth capture_leaves_synth \
    capture_min_synth capture_max_synth capture_all_max_synth \
    capture_bufg_driver_synth capture_parent_nets_synth \
    capture_parent_max_synth capture_parent_bufg_driver_synth
lassign [classify_bufg $out post_synth] clock_bufg_synth \
    data_bufg_synth capture_data_bufg_synth
set resource_synth_ok [expr {$dut_dsp_synth == 8 && \
    $dut_ramb36_synth == 62 && $dut_ramb18_synth == 8 && \
    $dut_uram_synth == 0}]

report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $out utilization_post_synth_hierarchical.rpt]
report_utilization -file [file join $out utilization_post_synth.rpt]
report_high_fanout_nets -max_nets 200 -timing -file \
    [file join $out high_fanout_post_synth.rpt]
write_checkpoint -force [file join $out post_synth.dcp]

set sfp [open [file join $out synth_summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    corrected_resource_contract "DSP8_RAMB36_62_RAMB18_8_URAM0" \
    dut_dsp48e2 $dut_dsp_synth dut_ramb36e2 $dut_ramb36_synth \
    dut_ramb18e2 $dut_ramb18_synth dut_uram288 $dut_uram_synth \
    resource_contract_ok $resource_synth_ok \
    capture_input_buffer_ff $capture_ff_synth \
    capture_control_nets $capture_controls_synth \
    capture_local_logic_drivers $capture_leaves_synth \
    capture_ce_min_loads $capture_min_synth \
    capture_ce_max_loads $capture_max_synth \
    capture_all_pin_max_loads $capture_all_max_synth \
    capture_bufg_driver_count $capture_bufg_driver_synth \
    capture_parent_net_count $capture_parent_nets_synth \
    capture_parent_max_loads $capture_parent_max_synth \
    capture_parent_bufg_driver_count $capture_parent_bufg_driver_synth \
    clock_bufg $clock_bufg_synth data_bufg $data_bufg_synth \
    capture_data_bufg $capture_data_bufg_synth \
    capture_contract_ok $capture_synth_ok] {
    puts $sfp "$key=$value"
}
close $sfp

if {!$resource_synth_ok || !$capture_synth_ok || \
    $capture_data_bufg_synth != 0} {
    error "compact-input post-synth resource/capture contract failed"
}

# Do not force CLOCK_BUFFER_TYPE on DUT nets.  Natural implementation must
# demonstrate that the row-local capture controls avoid non-clock BUFGs.
opt_design -directive Explore
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore

set dut_seq [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && (REF_NAME =~ FD* || REF_NAME =~ RAMB* || \
     REF_NAME == DSP48E2)}]
if {[llength $dut_seq] == 0} {error "compact-input DUT sequential set empty"}
set wns [first_slack max {} {} global_setup]
set whs [first_slack min {} {} global_hold]
set source_to_dut_wns [first_slack max $src $dut_seq source_to_dut_setup]
set source_to_dut_whs [first_slack min $src $dut_seq source_to_dut_hold]
set dut_internal_wns [first_slack max $dut_seq $dut_seq dut_internal_setup]
set dut_internal_whs [first_slack min $dut_seq $dut_seq dut_internal_hold]
set dut_to_sink_wns [first_slack max $dut_seq $sink dut_to_sink_setup]
set dut_to_sink_whs [first_slack min $dut_seq $sink dut_to_sink_hold]

set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set dut_ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set dut_ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set dut_uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set dut_lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set dut_ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
lassign [capture_audit $out post_route] capture_route_ok \
    capture_ff_route capture_controls_route capture_leaves_route \
    capture_min_route capture_max_route capture_all_max_route \
    capture_bufg_driver_route capture_parent_nets_route \
    capture_parent_max_route capture_parent_bufg_driver_route
lassign [classify_bufg $out post_route] clock_bufg data_bufg \
    capture_data_bufg

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -file \
    [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 100 -from $src -to $dut_seq \
    -file [file join $out source_to_dut_setup_worst100.rpt]
report_timing -delay_type max -max_paths 100 -from $dut_seq -to $dut_seq \
    -file [file join $out dut_internal_setup_worst100.rpt]
report_timing -delay_type max -max_paths 100 -from $dut_seq -to $sink \
    -file [file join $out dut_to_sink_setup_worst100.rpt]
report_utilization -hierarchical -hierarchical_depth 8 -file \
    [file join $out utilization_hierarchical.rpt]
report_utilization -file [file join $out utilization.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
report_high_fanout_nets -max_nets 200 -timing -file \
    [file join $out high_fanout_post_route.rpt]
set route_text [report_route_status -return_string]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_clock_utilization -file [file join $out clock_utilization.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
report_design_analysis -congestion -file [file join $out congestion.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set resource_ok [expr {$dut_dsp == 8 && $dut_ramb36 == 62 && \
    $dut_ramb18 == 8 && $dut_uram == 0}]
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0 && \
    $source_to_dut_wns >= 0.0 && $source_to_dut_whs >= 0.0 && \
    $dut_internal_wns >= 0.0 && $dut_internal_whs >= 0.0 && \
    $dut_to_sink_wns >= 0.0 && $dut_to_sink_whs >= 0.0}]
set strict_ok [expr {$resource_ok && $capture_route_ok && \
    $capture_data_bufg == 0 && $data_bufg == 0 && $timing_ok && \
    $unrouted == 0 && $conflicts == 0 && $drc_errors == 0}]
set status [expr {$strict_ok ? \
    "REGISTERED_OOC_CAPTURE48_PASS" : \
    "REGISTERED_OOC_CAPTURE48_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    evidence_class REGISTERED_OOC_PHYSICAL_DIAGNOSTIC_ONLY jobs $jobs \
    clock_period_ns 6.667 clock_mhz 150 clock_uncertainty_ns 0.150 \
    boundary_shell_budget_ns 0.000 boundary_shell_budget_complete 0 \
    corrected_resource_contract "DSP8_RAMB36_62_RAMB18_8_URAM0" \
    source_proxy_ff $src_count sink_proxy_ff $sink_count \
    dut_lut_primitives $dut_lut dut_ff_primitives $dut_ff \
    dut_dsp48e2 $dut_dsp dut_ramb36e2 $dut_ramb36 \
    dut_ramb18e2 $dut_ramb18 dut_uram288 $dut_uram \
    resource_contract_ok $resource_ok \
    capture_contract_shape "48x256" \
    capture_input_buffer_ff $capture_ff_route \
    capture_control_nets $capture_controls_route \
    capture_local_logic_drivers $capture_leaves_route \
    capture_ce_min_loads $capture_min_route \
    capture_ce_max_loads $capture_max_route \
    capture_all_pin_max_loads $capture_all_max_route \
    capture_bufg_driver_count $capture_bufg_driver_route \
    capture_parent_net_count $capture_parent_nets_route \
    capture_parent_max_loads $capture_parent_max_route \
    capture_parent_bufg_driver_count $capture_parent_bufg_driver_route \
    capture_contract_ok $capture_route_ok \
    capture_data_bufg $capture_data_bufg \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    wns_ns $wns whs_ns $whs \
    source_to_dut_wns_ns $source_to_dut_wns \
    source_to_dut_whs_ns $source_to_dut_whs \
    dut_internal_wns_ns $dut_internal_wns \
    dut_internal_whs_ns $dut_internal_whs \
    dut_to_sink_wns_ns $dut_to_sink_wns \
    dut_to_sink_whs_ns $dut_to_sink_whs \
    timing_ok $timing_ok unrouted_nets $unrouted \
    conflict_nets $conflicts drc_errors $drc_errors status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "COMPACT_INPUT_CAPTURE48_OOC DSP=$dut_dsp RAMB36=$dut_ramb36 RAMB18=$dut_ramb18 URAM=$dut_uram CAPTURE_CONTROLS=$capture_controls_route CAPTURE_FANOUT=$capture_min_route/$capture_max_route CAPTURE_DATA_BUFG=$capture_data_bufg DATA_BUFG=$data_bufg WNS=$wns WHS=$whs STATUS=$status"
if {$status ne "REGISTERED_OOC_CAPTURE48_PASS"} {
    error "compact-input 48-domain registered OOC gate failed"
}
close_project
