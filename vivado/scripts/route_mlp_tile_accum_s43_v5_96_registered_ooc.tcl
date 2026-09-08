set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_tile_accum_s43_v5_96_registered_ooc_harness
file mkdir $out

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
    if {[llength $paths] == 0} {error "No $delay_type timing path found"}
    return [get_property SLACK [lindex $paths 0]]
}

proc control_audit {out stage} {
    set write_leaves [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/*u_accum_write_enable && REF_NAME == LUT1}]
    require_count ${stage}_write_control_leaf $write_leaves 8
    set write_min 1000000000
    set write_max 0
    set write_bufg 0
    set fp [open [file join $out write_control_${stage}.tsv] w]
    puts $fp "index\tcell\tnet\tloads\tbufg_driver"
    set index 0
    foreach cell [lsort -dictionary $write_leaves] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        require_count ${stage}_write_control_output_$index $outputs 1
        set net [get_nets -quiet -of_objects $outputs]
        require_count ${stage}_write_control_net_$index $net 1
        set loads [actual_pin_loads $net]
        if {$loads < $write_min} {set write_min $loads}
        if {$loads > $write_max} {set write_max $loads}
        set ref [get_property REF_NAME $cell]
        set is_bufg [expr {[string match "BUFG*" $ref] ? 1 : 0}]
        incr write_bufg $is_bufg
        puts $fp "$index\t$cell\t$net\t$loads\t$is_bufg"
        incr index
    }
    close $fp

    set finalize_ff [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/finalize_pending_bank_r_reg* && REF_NAME =~ FD*}]
    require_count ${stage}_finalize_owner_ff $finalize_ff 8
    set finalize_nets {}
    set finalize_min 1000000000
    set finalize_max 0
    set ffp [open [file join $out finalize_control_${stage}.tsv] w]
    puts $ffp "index\tcell\tnet\tloads"
    set index 0
    foreach cell [lsort -dictionary $finalize_ff] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {REF_PIN_NAME == Q}]
        require_count ${stage}_finalize_owner_output_$index $outputs 1
        set net [get_nets -quiet -of_objects $outputs]
        require_count ${stage}_finalize_owner_net_$index $net 1
        lappend finalize_nets $net
        set loads [actual_pin_loads $net]
        if {$loads < $finalize_min} {set finalize_min $loads}
        if {$loads > $finalize_max} {set finalize_max $loads}
        puts $ffp "$index\t$cell\t$net\t$loads"
        incr index
    }
    close $ffp
    set finalize_nets [lsort -dictionary -unique $finalize_nets]
    require_count ${stage}_finalize_owner_unique_net $finalize_nets 8

    set ok [expr {$write_min > 0 && $write_max <= 600 && \
        $write_bufg == 0 && $finalize_min > 0 && $finalize_max <= 400}]
    return [list $ok [llength $write_leaves] $write_min $write_max \
        [llength $finalize_ff] $finalize_min $finalize_max]
}

proc classify_bufg {out stage} {
    set fp [open [file join $out bufg_${stage}.tsv] w]
    puts $fp "cell\tref\tnets\tclock_count\tloads"
    set clock_count 0
    set data_count 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        set nets [get_nets -quiet -of_objects $outputs]
        set clocks [get_clocks -quiet -of_objects $outputs]
        set loads 0
        foreach net $nets {incr loads [actual_pin_loads $net]}
        if {[llength $clocks] != 0} {
            incr clock_count
        } else {
            incr data_count
        }
        puts $fp "$cell\t[get_property REF_NAME $cell]\t$nets\t[llength $clocks]\t$loads"
    }
    close $fp
    return [list $clock_count $data_count]
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl mlp hap_mlp_tile_accum_s36.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_tile_accum_s43_v5_96_registered_ooc_harness.sv]
set xdc [file join $root vivado constraints \
    mlp_tile_accum_s43_v5_96_registered_ooc_150mhz.xdc]
set handle [open $xdc r]
set xdc_text [read $handle]
close $handle
set forbidden_constraint_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only} \
    $xdc_text]
if {$forbidden_constraint_count != 0} {
    error "V5 gate accumulator registered XDC contains a timing exception"
}
read_xdc $xdc

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
require_count source_proxy_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}] 3462
require_count sink_proxy_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}] 2403
require_count accumulator_dut [get_cells -quiet u_dut] 1
lassign [control_audit $out post_synth] control_synth_ok \
    write_leaf_synth write_min_synth write_max_synth finalize_ff_synth \
    finalize_min_synth finalize_max_synth
lassign [classify_bufg $out post_synth] clock_bufg_synth data_bufg_synth
write_checkpoint -force [file join $out post_synth.dcp]

opt_design -directive Explore
lassign [control_audit $out post_opt] control_opt_ok \
    write_leaf_opt write_min_opt write_max_opt finalize_ff_opt \
    finalize_min_opt finalize_max_opt
lassign [classify_bufg $out post_opt] clock_bufg_opt data_bufg_opt
write_checkpoint -force [file join $out post_opt.dcp]

place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
lassign [control_audit $out post_phys_opt] control_phys_ok \
    write_leaf_phys write_min_phys write_max_phys finalize_ff_phys \
    finalize_min_phys finalize_max_phys
lassign [classify_bufg $out post_phys_opt] clock_bufg_phys data_bufg_phys
write_checkpoint -force [file join $out post_phys_opt.dcp]

route_design -directive AggressiveExplore
lassign [control_audit $out post_route] control_route_ok \
    write_leaf_route write_min_route write_max_route finalize_ff_route \
    finalize_min_route finalize_max_route
lassign [classify_bufg $out post_route] clock_bufg_route data_bufg_route

report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -file \
    [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 5 -file \
    [file join $out utilization_hierarchical.rpt]
report_route_status -file [file join $out route_status.rpt]
report_drc -file [file join $out drc.rpt]
report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
write_checkpoint -force [file join $out post_route.dcp]

set wns [first_slack max]
set whs [first_slack min]
set unrouted [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set conflicts [llength [get_nets -quiet -hierarchical -filter \
    {ROUTE_STATUS == CONFLICTS}]]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]
set dsp [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set bram36 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB36E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set structural_ok [expr {$control_synth_ok && $control_opt_ok && \
    $control_phys_ok && $control_route_ok}]
set natural_bufg_ok [expr {$data_bufg_synth == 0 && $data_bufg_opt == 0 && \
    $data_bufg_phys == 0 && $data_bufg_route == 0}]
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set resource_ok [expr {$dsp == 0 && $bram36 == 0 && $uram == 0}]
set status [expr {$structural_ok && $natural_bufg_ok && $timing_ok && \
    $resource_ok && $unrouted == 0 && $conflicts == 0 && $drc_errors == 0 && \
    $forbidden_constraint_count == 0 ? \
    "REGISTERED_GATE_WRITE8_OOC_PASS" : \
    "REGISTERED_GATE_WRITE8_OOC_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    evidence_class REGISTERED_EXCEPTION_FREE_NATURAL_PHYSICAL_OOC \
    clock_mhz 150 lanes 96 groups 128 accumulator_width 43 \
    write_control_contract 8 finalize_owner_contract 8 \
    post_synth_write_leaves $write_leaf_synth \
    post_synth_write_loads "$write_min_synth/$write_max_synth" \
    post_synth_finalize_ff $finalize_ff_synth \
    post_synth_finalize_loads "$finalize_min_synth/$finalize_max_synth" \
    post_opt_write_leaves $write_leaf_opt \
    post_opt_write_loads "$write_min_opt/$write_max_opt" \
    post_opt_finalize_ff $finalize_ff_opt \
    post_opt_finalize_loads "$finalize_min_opt/$finalize_max_opt" \
    post_phys_opt_write_leaves $write_leaf_phys \
    post_phys_opt_write_loads "$write_min_phys/$write_max_phys" \
    post_phys_opt_finalize_ff $finalize_ff_phys \
    post_phys_opt_finalize_loads "$finalize_min_phys/$finalize_max_phys" \
    post_route_write_leaves $write_leaf_route \
    post_route_write_loads "$write_min_route/$write_max_route" \
    post_route_finalize_ff $finalize_ff_route \
    post_route_finalize_loads "$finalize_min_route/$finalize_max_route" \
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
    dsp48e2 $dsp ramb36e2 $bram36 uram288 $uram \
    dut_lut_primitives $lut dut_ff_primitives $ff resource_ok $resource_ok \
    forbidden_timing_exception_count $forbidden_constraint_count \
    clock_buffer_type_override_count 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "GATE96_WRITE8_REGISTERED_OOC WRITE=$write_leaf_route:$write_min_route/$write_max_route FINALIZE=$finalize_ff_route:$finalize_min_route/$finalize_max_route DATA_BUFG=$data_bufg_route WNS=$wns WHS=$whs UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "REGISTERED_GATE_WRITE8_OOC_PASS"} {
    error "V5 gate accumulator protected control OOC gate failed"
}
close_project
