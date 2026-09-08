set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_down_branch_elastic2_s24_ooc_harness
file mkdir $report_dir

proc hierarchy_util_row {path instance} {
    set fp [open $path r]
    set text [read $fp]
    close $fp
    foreach line [split $text "\n"] {
        set fields [split $line "|"]
        if {[llength $fields] < 12 ||
            [string trim [lindex $fields 1]] ne $instance} {
            continue
        }
        set result {}
        for {set index 3} {$index <= 11} {incr index} {
            set value [string trim [lindex $fields $index]]
            if {![string is integer -strict $value]} {
                error "non-integer utilization field for $instance: $value"
            }
            lappend result $value
        }
        return $result
    }
    error "utilization hierarchy row '$instance' is missing"
}

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set_param general.maxThreads 8
create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_shared_dual_slice16x12_s43_s45.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_down_branch_elastic2_s24_ooc_harness.sv]
set xdc_path [file join $root vivado constraints \
    mlp_down_branch_elastic2_s24_ooc_150mhz.xdc]
set fp [open $xdc_path r]
set xdc_text [read $fp]
close $fp
set forbidden_exception_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|-datapath_only|set_multicycle_path} \
    $xdc_text]
if {$forbidden_exception_count != 0} {
    error "down queue OOC XDC contains forbidden timing exception"
}
read_xdc $xdc_path

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive PerformanceOptimized
opt_design -directive Explore
place_design -directive ExtraNetDelay_high
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -file [file join $report_dir timing_summary.rpt]
set util_hier_path [file join $report_dir utilization_hierarchical.rpt]
report_utilization -hierarchical -hierarchical_depth 6 -file $util_hier_path
report_utilization -file [file join $report_dir utilization.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_high_fanout_nets -timing -load_types -max_nets 200 -file \
    [file join $report_dir high_fanout_nets.rpt]
report_design_analysis -congestion -file \
    [file join $report_dir congestion.rpt]
report_drc -file [file join $report_dir drc.rpt]
write_checkpoint -force [file join $report_dir post_route.dcp]

set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_paths] == 0 || [llength $hold_paths] == 0} {
    error "down queue OOC has no setup or hold timing path"
}
set wns [get_property SLACK [lindex $setup_paths 0]]
set whs [get_property SLACK [lindex $hold_paths 0]]
set queue_cells [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_queue/*}]
set lut_primitive_count [llength [filter $queue_cells {REF_NAME =~ LUT*}]]
set ff_count [llength [filter $queue_cells {REF_NAME =~ FD*}]]
set dsp_count [llength [filter $queue_cells {REF_NAME == DSP48E2}]]
set bram_count [llength [filter $queue_cells \
    {REF_NAME == RAMB18E2 || REF_NAME == RAMB36E2}]]
set uram_count [llength [filter $queue_cells {REF_NAME == URAM288}]]
set all_bufg [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}]
set data_bufg 0
foreach cell $all_bufg {
    set outputs [get_pins -quiet -of_objects $cell -filter \
        {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] == 0} {
        incr data_bufg
    }
}
set queue_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_queue/*}]
set max_fanout 0
set max_fanout_net NONE
foreach net $queue_nets {
    set net_name [get_property NAME $net]
    set net_clocks [get_clocks -quiet -of_objects [concat \
        [get_pins -quiet -of_objects $net] \
        [get_ports -quiet -of_objects $net]]]
    if {[llength $net_clocks] != 0 ||
        $net_name eq "u_queue/<const0>" ||
        $net_name eq "u_queue/<const1>"} {
        continue
    }
    set fanout [llength [get_pins -quiet -leaf -of_objects $net -filter \
        {DIRECTION == IN}]]
    if {$fanout > $max_fanout} {
        set max_fanout $fanout
        set max_fanout_net $net_name
    }
}
set out_ready_nets [get_nets -quiet -hierarchical -filter \
    {NAME =~ *out_ready*}]
set out_ready_max_fanout 0
foreach net $out_ready_nets {
    set fanout [llength [get_pins -quiet -leaf -of_objects $net -filter \
        {DIRECTION == IN}]]
    if {$fanout > $out_ready_max_fanout} {
        set out_ready_max_fanout $fanout
    }
}
set partial_all [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED ||
     ROUTE_STATUS == PARTIAL}]
set bad_partial {}
set accepted_clock_partial {}
foreach net $partial_all {
    set outputs [get_pins -quiet -of_objects $net -filter \
        {DIRECTION == OUT}]
    set inputs [get_pins -quiet -of_objects $net -filter \
        {DIRECTION == IN}]
    if {[llength [get_clocks -quiet -of_objects [concat $outputs $inputs]]] != 0} {
        lappend accepted_clock_partial $net
    } else {
        lappend bad_partial $net
    }
}
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
report_drc -file [file join $report_dir drc_final.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
lassign [hierarchy_util_row $util_hier_path u_queue] \
    queue_clb_lut queue_logic_lut queue_lutram queue_srl \
    queue_clb_register queue_ramb36 queue_ramb18 queue_uram queue_dsp
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $dsp_count == 0 &&
    $bram_count == 0 && $uram_count == 0 && $data_bufg == 0 &&
    [llength $bad_partial] == 0 && $conflicts == 0 && $drc_errors == 0 &&
    $queue_clb_lut == 1217 && $queue_clb_register == 4642 &&
    $max_fanout == 292 && $out_ready_max_fanout == 9 &&
    $forbidden_exception_count == 0 ?
    "DOWN_ELASTIC2_EXCEPTION_FREE_OOC_PASS" : "FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    clock_mhz 150 rows 8 cols 12 depth 2 payload_width 2304 \
    wns_ns $wns whs_ns $whs queue_clb_lut $queue_clb_lut \
    queue_logic_lut $queue_logic_lut queue_lutram $queue_lutram \
    queue_srl $queue_srl queue_lut_primitives $lut_primitive_count \
    queue_ff_primitives $ff_count dsp48e2 $dsp_count bram $bram_count \
    uram288 $uram_count data_bufg $data_bufg \
    maximum_nonclock_nonconstant_queue_net_fanout $max_fanout \
    maximum_nonclock_nonconstant_queue_net_name $max_fanout_net \
    maximum_out_ready_named_net_fanout $out_ready_max_fanout \
    partial_nets_total [llength $partial_all] \
    accepted_clock_partial_nets [llength $accepted_clock_partial] \
    bad_partial_nets [llength $bad_partial] conflict_nets $conflicts \
    drc_errors $drc_errors \
    forbidden_timing_exception_count $forbidden_exception_count \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "DOWN_ELASTIC2_OOC WNS=$wns WHS=$whs CLB_LUT=$queue_clb_lut FF=$ff_count MAX_FANOUT=$max_fanout OUT_READY_FANOUT=$out_ready_max_fanout DATA_BUFG=$data_bufg STATUS=$status"
if {$status ne "DOWN_ELASTIC2_EXCEPTION_FREE_OOC_PASS"} {
    error "down queue exception-free OOC gate failed"
}
close_project
