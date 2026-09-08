set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_mlp_down_activation_cache16_registered_ooc_harness
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

proc capture_audit {out stage} {
    set owners [get_cells -quiet -hierarchical -filter \
        {NAME =~ u_dut/output_capture_pending_bank_r_reg* && REF_NAME =~ FD*}]
    require_count ${stage}_capture_owner_ff $owners 16
    set nets {}
    set all_payload_pins {}
    set min_load 1000000000
    set max_load 0
    set fp [open [file join $out capture_owner_${stage}.tsv] w]
    puts $fp "index\towner\towner_net\tlocal_driver\tlocal_net\tpayload_loads"
    set index 0
    foreach owner [lsort -dictionary $owners] {
        set q [get_pins -quiet -of_objects $owner -filter {REF_PIN_NAME == Q}]
        require_count ${stage}_capture_owner_q_$index $q 1
        set net [get_nets -quiet -of_objects $q]
        require_count ${stage}_capture_owner_net_$index $net 1
        lappend nets $net
        set owner_loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN}]
        require_count ${stage}_capture_owner_load_$index $owner_loads 1
        set local_driver [get_cells -quiet -of_objects $owner_loads]
        require_count ${stage}_capture_local_driver_$index $local_driver 1
        set local_ref [get_property REF_NAME $local_driver]
        if {![string match "LUT*" $local_ref]} {
            error "${stage} capture local driver is not a LUT: $local_driver $local_ref"
        }
        set local_q [get_pins -quiet -of_objects $local_driver -filter \
            {DIRECTION == OUT}]
        require_count ${stage}_capture_local_output_$index $local_q 1
        set local_net [get_nets -quiet -of_objects $local_q]
        require_count ${stage}_capture_local_net_$index $local_net 1
        set payload_pins [get_pins -quiet -leaf -of_objects $local_net \
            -filter {DIRECTION == IN}]
        set all_payload_pins [concat $all_payload_pins $payload_pins]
        set payload_loads [llength $payload_pins]
        if {$payload_loads < $min_load} {set min_load $payload_loads}
        if {$payload_loads > $max_load} {set max_load $payload_loads}
        puts $fp "$index\t$owner\t$net\t$local_driver\t$local_net\t$payload_loads"
        incr index
    }
    close $fp
    set nets [lsort -dictionary -unique $nets]
    set all_payload_pins [lsort -dictionary -unique $all_payload_pins]
    require_count ${stage}_capture_owner_unique_net $nets 16
    require_count ${stage}_capture_payload_pin $all_payload_pins 4480
    set payload_ff [lsort -dictionary -unique \
        [get_cells -quiet -of_objects $all_payload_pins]]
    require_count ${stage}_capture_payload_ff $payload_ff 4480
    set ok [expr {$min_load == 280 && $max_load == 280}]
    return [list $ok [llength $owners] [llength $nets] \
        [llength $payload_ff] $min_load $max_load]
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
read_verilog -sv [file join $root rtl mlp hap_mlp_down_activation_cache16.sv]
read_verilog -sv [file join $root rtl mlp \
    hap_mlp_down_activation_cache16_registered_ooc_harness.sv]
set xdc [file join $root vivado constraints \
    mlp_down_activation_cache16_registered_ooc_150mhz.xdc]
set handle [open $xdc r]
set xdc_text [read $handle]
close $handle
set forbidden_constraint_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only} \
    $xdc_text]
if {$forbidden_constraint_count != 0} {
    error "down activation registered XDC contains a timing exception"
}
read_xdc $xdc

synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $out post_synth.dcp]
require_count source_proxy_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ src_r_reg* && REF_NAME =~ FD*}] 4485
require_count sink_proxy_ff [get_cells -quiet -hierarchical -filter \
    {NAME =~ sink_r_reg* && REF_NAME =~ FD*}] 4548
require_count cache_dut [get_cells -quiet u_dut] 1
lassign [capture_audit $out post_synth] capture_synth_ok \
    owners_synth nets_synth payload_synth min_synth max_synth
lassign [classify_bufg $out post_synth] clock_bufg_synth data_bufg_synth

opt_design -directive Explore
lassign [capture_audit $out post_opt] capture_opt_ok \
    owners_opt nets_opt payload_opt min_opt max_opt
lassign [classify_bufg $out post_opt] clock_bufg_opt data_bufg_opt
write_checkpoint -force [file join $out post_opt.dcp]

place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
lassign [capture_audit $out post_phys_opt] capture_phys_ok \
    owners_phys nets_phys payload_phys min_phys max_phys
lassign [classify_bufg $out post_phys_opt] clock_bufg_phys data_bufg_phys
write_checkpoint -force [file join $out post_phys_opt.dcp]

route_design -directive AggressiveExplore
lassign [capture_audit $out post_route] capture_route_ok \
    owners_route nets_route payload_route min_route max_route
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
set bram18 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == RAMB18E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME == URAM288}]]
set lut [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/* && REF_NAME =~ FD*}]]
set structural_ok [expr {$capture_synth_ok && $capture_opt_ok && \
    $capture_phys_ok && $capture_route_ok}]
set natural_bufg_ok [expr {$data_bufg_synth == 0 && $data_bufg_opt == 0 && \
    $data_bufg_phys == 0 && $data_bufg_route == 0}]
set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
set resource_ok [expr {$dsp == 0 && $bram36 == 64 && $bram18 == 0 && \
    $uram == 0}]
set status [expr {$structural_ok && $natural_bufg_ok && $timing_ok && \
    $resource_ok && $unrouted == 0 && $conflicts == 0 && $drc_errors == 0 && \
    $forbidden_constraint_count == 0 ? \
    "REGISTERED_DOWN_ACTIVATION16_OOC_PASS" : \
    "REGISTERED_DOWN_ACTIVATION16_OOC_FAIL"}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part top $top \
    evidence_class REGISTERED_EXCEPTION_FREE_NATURAL_PHYSICAL_OOC \
    clock_mhz 150 groups 448 capture_contract "16x280" \
    post_synth_capture_owners $owners_synth \
    post_synth_capture_nets $nets_synth \
    post_synth_capture_payload_ff $payload_synth \
    post_synth_capture_loads "$min_synth/$max_synth" \
    post_opt_capture_owners $owners_opt post_opt_capture_nets $nets_opt \
    post_opt_capture_payload_ff $payload_opt \
    post_opt_capture_loads "$min_opt/$max_opt" \
    post_phys_opt_capture_owners $owners_phys \
    post_phys_opt_capture_nets $nets_phys \
    post_phys_opt_capture_payload_ff $payload_phys \
    post_phys_opt_capture_loads "$min_phys/$max_phys" \
    post_route_capture_owners $owners_route \
    post_route_capture_nets $nets_route \
    post_route_capture_payload_ff $payload_route \
    post_route_capture_loads "$min_route/$max_route" \
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
    dsp48e2 $dsp ramb36e2 $bram36 ramb18e2 $bram18 uram288 $uram \
    dut_lut_primitives $lut dut_ff_primitives $ff resource_ok $resource_ok \
    forbidden_timing_exception_count $forbidden_constraint_count \
    clock_buffer_type_override_count 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "DOWN_ACTIVATION16_REGISTERED_OOC CAPTURE=$owners_route:$min_route/$max_route DATA_BUFG=$data_bufg_route WNS=$wns WHS=$whs BRAM36=$bram36 UNROUTED=$unrouted DRC=$drc_errors STATUS=$status"
if {$status ne "REGISTERED_DOWN_ACTIVATION16_OOC_PASS"} {
    error "down activation 16-row registered OOC gate failed"
}
close_project
