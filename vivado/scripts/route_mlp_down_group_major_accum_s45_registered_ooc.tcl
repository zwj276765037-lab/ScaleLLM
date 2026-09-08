set root [file normalize [file join [file dirname [info script]] ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_down_group_major_accum_s45_registered_ooc_harness
file mkdir $report_dir

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set_param general.maxThreads 8

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

proc first_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} {
        error "No $delay_type timing path found"
    }
    return [get_property SLACK [lindex $paths 0]]
}

proc protected_capture_audit {out stage label driver_pattern \
        expected_domains expected_loads expected_ff} {
    # Start from the protected leaves instead of synthesized packed-register
    # names, which Vivado may legally reshape between optimization stages.
    set driver_cells [get_cells -quiet -hierarchical -filter \
        "NAME =~ $driver_pattern && REF_NAME == LUT1"]
    require_count ${stage}_${label}_capture_driver_cell $driver_cells \
        $expected_domains

    set fp [open [file join $out ${label}_capture_${stage}.tsv] w]
    puts $fp "index\tdriver_cell\tdriver_ref\tnet\tce_loads\tall_pin_loads\tdata_bufg_driver"
    set min_ce 1000000000
    set max_ce 0
    set max_all 0
    set lut1_drivers 0
    set bufg_drivers 0
    set all_ce_pins {}
    set ce_nets {}
    set index 0
    foreach driver_cell [lsort -dictionary $driver_cells] {
        set driver_pins [get_pins -quiet -of_objects $driver_cell -filter \
            {DIRECTION == OUT}]
        require_count ${stage}_${label}_capture_driver_pin_$index \
            $driver_pins 1
        set net [get_nets -quiet -of_objects $driver_pins]
        require_count ${stage}_${label}_capture_net_$index $net 1
        lappend ce_nets $net
        set capture_ce [get_pins -quiet -leaf -of_objects $net -filter \
            {REF_PIN_NAME == CE}]
        set all_ce_pins [concat $all_ce_pins $capture_ce]
        set ce_loads [llength $capture_ce]
        set all_loads [actual_pin_loads $net]
        set driver_ref [get_property REF_NAME $driver_cell]
        if {$driver_ref eq "LUT1"} {incr lut1_drivers}
        set is_bufg [expr {[string match "BUFG*" $driver_ref] ? 1 : 0}]
        incr bufg_drivers $is_bufg
        if {$ce_loads < $min_ce} {set min_ce $ce_loads}
        if {$ce_loads > $max_ce} {set max_ce $ce_loads}
        if {$all_loads > $max_all} {set max_all $all_loads}
        puts $fp "$index\t$driver_cell\t$driver_ref\t$net\t$ce_loads\t$all_loads\t$is_bufg"
        incr index
    }
    set all_ce_pins [lsort -dictionary -unique $all_ce_pins]
    require_count ${stage}_${label}_capture_ce_pin $all_ce_pins $expected_ff
    set capture_ff [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $all_ce_pins]]
    require_count ${stage}_${label}_capture_ff $capture_ff $expected_ff
    close $fp

    set ok [expr {$min_ce == $expected_loads && \
        $max_ce == $expected_loads && $max_all == $expected_loads && \
        $lut1_drivers == $expected_domains && $bufg_drivers == 0}]
    return [list $ok [llength $capture_ff] [llength $ce_nets] \
        $lut1_drivers $min_ce $max_ce $max_all $bufg_drivers]
}

proc classify_bufg {out stage} {
    set fp [open [file join $out bufg_${stage}.tsv] w]
    puts $fp "cell\tref\tnets\tclock_count\tloads\tguard_ce_hits"
    set clock_count 0
    set data_count 0
    set guard_data_count 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        set nets [get_nets -quiet -of_objects $outputs]
        set clocks [get_clocks -quiet -of_objects $outputs]
        set loads 0
        set guard_hits 0
        foreach net $nets {
            incr loads [actual_pin_loads $net]
            incr guard_hits [llength [get_pins -quiet -leaf \
                -of_objects $net -filter \
                {NAME =~ u_accum/pipe_guard_r_reg*/CE}]]
        }
        if {[llength $clocks] != 0} {
            incr clock_count
        } else {
            incr data_count
            if {$guard_hits != 0} {incr guard_data_count}
        }
        puts $fp "$cell\t[get_property REF_NAME $cell]\t$nets\t[llength $clocks]\t$loads\t$guard_hits"
    }
    close $fp
    return [list $clock_count $data_count $guard_data_count]
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_down_group_major_accum_s45.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_down_group_major_accum_s45_ooc_wrapper.sv]
set xdc_path [file join $root vivado constraints \
    mlp_down_group_major_accum_s45_registered_ooc_150mhz.xdc]
set xdc_fp [open $xdc_path r]
set xdc_text [read $xdc_fp]
close $xdc_fp
set forbidden_constraint_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only} \
    $xdc_text]
if {$forbidden_constraint_count != 0} {
    error "registered OOC XDC contains forbidden timing exception"
}
read_xdc $xdc_path

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $report_dir post_synth.dcp]
set src [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}]
set sink [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
require_count source_proxy_ff $src 3471
require_count sink_proxy_ff $sink 2444
require_count accumulator_dut [get_cells -quiet u_accum] 1
require_count top_port_count [get_ports -quiet] 1
lassign [protected_capture_audit $report_dir post_synth guard \
    "u_accum/*u_guard_capture_enable" 8 432 3456] guard_synth_ok \
    guard_ff_synth guard_nets_synth guard_lut_synth guard_min_synth \
    guard_max_synth guard_all_synth guard_bufg_driver_synth
lassign [protected_capture_audit $report_dir post_synth output \
    "u_accum/*u_output_capture_enable" 8 288 2304] output_synth_ok \
    output_ff_synth output_nets_synth output_lut_synth output_min_synth \
    output_max_synth output_all_synth output_bufg_driver_synth
lassign [classify_bufg $report_dir post_synth] clock_bufg_synth \
    data_bufg_synth guard_data_bufg_synth

opt_design -directive Explore
lassign [protected_capture_audit $report_dir post_opt guard \
    "u_accum/*u_guard_capture_enable" 8 432 3456] guard_opt_ok \
    guard_ff_opt guard_nets_opt guard_lut_opt guard_min_opt guard_max_opt \
    guard_all_opt guard_bufg_driver_opt
lassign [protected_capture_audit $report_dir post_opt output \
    "u_accum/*u_output_capture_enable" 8 288 2304] output_opt_ok \
    output_ff_opt output_nets_opt output_lut_opt output_min_opt \
    output_max_opt output_all_opt output_bufg_driver_opt
lassign [classify_bufg $report_dir post_opt] clock_bufg_opt \
    data_bufg_opt guard_data_bufg_opt
write_checkpoint -force [file join $report_dir post_opt.dcp]

# Natural implementation must retain the protected local controls.  No
# CLOCK_BUFFER_TYPE property is applied to any DUT net.
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
lassign [protected_capture_audit $report_dir post_phys_opt guard \
    "u_accum/*u_guard_capture_enable" 8 432 3456] guard_phys_ok \
    guard_ff_phys guard_nets_phys guard_lut_phys guard_min_phys \
    guard_max_phys guard_all_phys guard_bufg_driver_phys
lassign [protected_capture_audit $report_dir post_phys_opt output \
    "u_accum/*u_output_capture_enable" 8 288 2304] output_phys_ok \
    output_ff_phys output_nets_phys output_lut_phys output_min_phys \
    output_max_phys output_all_phys output_bufg_driver_phys
lassign [classify_bufg $report_dir post_phys_opt] clock_bufg_phys \
    data_bufg_phys guard_data_bufg_phys
write_checkpoint -force [file join $report_dir post_phys_opt.dcp]

route_design -directive AggressiveExplore
lassign [protected_capture_audit $report_dir post_route guard \
    "u_accum/*u_guard_capture_enable" 8 432 3456] guard_route_ok \
    guard_ff_route guard_nets_route guard_lut_route guard_min_route \
    guard_max_route guard_all_route guard_bufg_driver_route
lassign [protected_capture_audit $report_dir post_route output \
    "u_accum/*u_output_capture_enable" 8 288 2304] output_route_ok \
    output_ff_route output_nets_route output_lut_route output_min_route \
    output_max_route output_all_route output_bufg_driver_route
lassign [classify_bufg $report_dir post_route] clock_bufg_route \
    data_bufg_route guard_data_bufg_route

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -file \
    [file join $report_dir timing_summary.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $report_dir utilization_hierarchical.rpt]
report_utilization -file [file join $report_dir utilization.rpt]
report_route_status -file [file join $report_dir route_status.rpt]
report_drc -file [file join $report_dir drc.rpt]
report_clock_utilization -file [file join $report_dir clock_utilization.rpt]
report_exceptions -coverage -file \
    [file join $report_dir exceptions_coverage.rpt]
write_checkpoint -force [file join $report_dir post_route.dcp]

set wns [first_slack max]
set whs [first_slack min]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_accum/* && REF_NAME == DSP48E2}]]
set lut_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_accum/* && REF_NAME =~ LUT*}]]
set ff_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_accum/* && REF_NAME =~ FD*}]]
set bram36_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_accum/* && REF_NAME == RAMB36E2}]]
set uram_count [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_accum/* && REF_NAME == URAM288}]]

set structural_ok [expr {$guard_synth_ok && $guard_opt_ok && \
    $guard_phys_ok && $guard_route_ok && $output_synth_ok && \
    $output_opt_ok && $output_phys_ok && $output_route_ok}]
set natural_bufg_ok [expr {$data_bufg_synth == 0 && $data_bufg_opt == 0 && \
    $data_bufg_phys == 0 && $data_bufg_route == 0 && \
    $guard_data_bufg_synth == 0 && $guard_data_bufg_opt == 0 && \
    $guard_data_bufg_phys == 0 && $guard_data_bufg_route == 0}]
set resource_ok [expr {$dsp_count == 0 && $bram36_count == 96 && \
    $uram_count == 0}]
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set status [expr {$structural_ok && $natural_bufg_ok && $resource_ok && \
    $timing_ok && $unrouted == 0 && $conflicts == 0 && $drc_errors == 0 && \
    $forbidden_constraint_count == 0 ? \
    "REGISTERED_GUARD8_OUTPUT8_OOC_PASS" : \
    "REGISTERED_GUARD8_OUTPUT8_OOC_FAIL"}]

set fp [open [file join $report_dir summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    evidence_class REGISTERED_EXCEPTION_FREE_NATURAL_PHYSICAL_OOC \
    clock_mhz 150 lanes 96 tiles 342 groups 448 \
    source_proxy_ff [llength $src] sink_proxy_ff [llength $sink] \
    guard_capture_contract "8x432" output_capture_contract "8x288" \
    post_synth_guard_ff $guard_ff_synth \
    post_synth_guard_control_nets $guard_nets_synth \
    post_synth_guard_lut1_drivers $guard_lut_synth \
    post_synth_guard_loads "$guard_min_synth/$guard_max_synth" \
    post_opt_guard_ff $guard_ff_opt \
    post_opt_guard_control_nets $guard_nets_opt \
    post_opt_guard_lut1_drivers $guard_lut_opt \
    post_opt_guard_loads "$guard_min_opt/$guard_max_opt" \
    post_phys_opt_guard_ff $guard_ff_phys \
    post_phys_opt_guard_control_nets $guard_nets_phys \
    post_phys_opt_guard_lut1_drivers $guard_lut_phys \
    post_phys_opt_guard_loads "$guard_min_phys/$guard_max_phys" \
    post_route_guard_ff $guard_ff_route \
    post_route_guard_control_nets $guard_nets_route \
    post_route_guard_lut1_drivers $guard_lut_route \
    post_route_guard_loads "$guard_min_route/$guard_max_route" \
    post_synth_output_ff $output_ff_synth \
    post_synth_output_control_nets $output_nets_synth \
    post_synth_output_lut1_drivers $output_lut_synth \
    post_synth_output_loads "$output_min_synth/$output_max_synth" \
    post_opt_output_ff $output_ff_opt \
    post_opt_output_control_nets $output_nets_opt \
    post_opt_output_lut1_drivers $output_lut_opt \
    post_opt_output_loads "$output_min_opt/$output_max_opt" \
    post_phys_opt_output_ff $output_ff_phys \
    post_phys_opt_output_control_nets $output_nets_phys \
    post_phys_opt_output_lut1_drivers $output_lut_phys \
    post_phys_opt_output_loads "$output_min_phys/$output_max_phys" \
    post_route_output_ff $output_ff_route \
    post_route_output_control_nets $output_nets_route \
    post_route_output_lut1_drivers $output_lut_route \
    post_route_output_loads "$output_min_route/$output_max_route" \
    post_synth_clock_bufg $clock_bufg_synth \
    post_synth_data_bufg $data_bufg_synth \
    post_opt_clock_bufg $clock_bufg_opt post_opt_data_bufg $data_bufg_opt \
    post_phys_opt_clock_bufg $clock_bufg_phys \
    post_phys_opt_data_bufg $data_bufg_phys \
    post_route_clock_bufg $clock_bufg_route \
    post_route_data_bufg $data_bufg_route \
    structural_ok $structural_ok natural_bufg_ok $natural_bufg_ok \
    wns_ns $wns whs_ns $whs timing_ok $timing_ok \
    unrouted_nets $unrouted conflict_nets $conflicts drc_errors $drc_errors \
    dsp48e2 $dsp_count dut_lut_primitives $lut_count \
    dut_ff_primitives $ff_count ramb36e2 $bram36_count uram288 $uram_count \
    resource_ok $resource_ok \
    forbidden_timing_exception_count $forbidden_constraint_count \
    clock_buffer_type_override_count 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "DOWN96_CAPTURE8_REGISTERED_OOC GUARD=$guard_nets_route:$guard_min_route/$guard_max_route OUTPUT=$output_nets_route:$output_min_route/$output_max_route DATA_BUFG=$data_bufg_route WNS=$wns WHS=$whs BRAM36=$bram36_count UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "REGISTERED_GUARD8_OUTPUT8_OOC_PASS"} {
    error "V5 down96 protected capture OOC gate failed"
}
close_project
