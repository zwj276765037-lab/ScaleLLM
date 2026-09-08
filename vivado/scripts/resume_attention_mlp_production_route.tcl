set root [file normalize [file join [file dirname [file normalize [info script]]] ../..]]
set in_dcp [file normalize $::env(HAP_POST_PLACE_DCP)]
set out [file normalize $::env(HAP_ROUTE_DIR)]
set physopt_directive [expr {[info exists ::env(HAP_PHYSOPT_DIRECTIVE)] ?
    $::env(HAP_PHYSOPT_DIRECTIVE) : "AggressiveExplore"}]
set route_directive [expr {[info exists ::env(HAP_ROUTE_DIRECTIVE)] ?
    $::env(HAP_ROUTE_DIRECTIVE) : "AggressiveExplore"}]
set expected_part xcvu9p-flga2104-2L-e
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
if {![file exists $in_dcp]} {
    error "Post-place checkpoint does not exist: $in_dcp"
}

open_checkpoint $in_dcp
set actual_part [get_property PART [current_design]]
if {$actual_part ne $expected_part} {
    error "Illegal route input part: expected $expected_part, got $actual_part"
}

proc route_row {text label {required 0}} {
    foreach line [split $text "\n"] {
        if {[string first $label $line] >= 0 &&
            [regexp {:[[:space:]]*([0-9]+)[[:space:]]*:} $line -> count]} {
            return $count
        }
    }
    if {$required} {
        error "Required route-status row '$label' is missing"
    }
    # Vivado omits zero-valued detail rows from a clean report.
    return 0
}

proc check_timing_count {text check_name} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $check_name]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "check_timing category '$check_name' is missing"
    }
    return $count
}

# Reject a partial or illegal placement before spending hours in physical
# optimization and routing.
set pre_unplaced [llength [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && !IS_PLACED
}]]
set pre_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2
}]]
set pre_uram [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == URAM288
}]]
set pre_kernel_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2 &&
    NAME =~ u_compute/u_mlp/u_serial_command/u_shared_compute/*
}]]
if {$pre_unplaced != 0 || $pre_dsp != 6492 || $pre_uram != 752 ||
    $pre_kernel_dsp != 4096} {
    error "Illegal route input: unplaced=$pre_unplaced DSP=$pre_dsp URAM=$pre_uram kernel_DSP=$pre_kernel_dsp"
}

phys_opt_design -directive $physopt_directive
write_checkpoint -force [file join $out post_phys_opt.dcp]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_post_phys_opt.rpt]

route_design -directive $route_directive
write_checkpoint -force [file join $out post_route.dcp]

report_utilization -file [file join $out utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 9 -file \
    [file join $out utilization_hier_post_route.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_route.rpt]
set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set timing_fh [open [file join $out timing_post_route.rpt] w]
puts -nonewline $timing_fh $timing_text
close $timing_fh
report_timing -delay_type max -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_setup_worst100_post_route.rpt]
report_timing -delay_type min -max_paths 100 -path_type full_clock_expanded \
    -file [file join $out timing_hold_worst100_post_route.rpt]
set route_text [report_route_status -return_string]
set route_fh [open [file join $out route_status_post_route.rpt] w]
puts -nonewline $route_fh $route_text
close $route_fh
report_drc -file [file join $out drc_post_route.rpt]
report_cdc -details -file [file join $out cdc_post_route.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_route.rpt]
report_design_analysis -congestion -file \
    [file join $out congestion_post_route.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_route.rpt]

set setup_path [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set hold_path [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
if {$setup_path eq "" || $hold_path eq ""} {
    error "No setup or hold timing path was returned"
}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set setup_start [get_property STARTPOINT_PIN $setup_path]
set setup_end [get_property ENDPOINT_PIN $setup_path]
set hold_start [get_property STARTPOINT_PIN $hold_path]
set hold_end [get_property ENDPOINT_PIN $hold_path]

# A successful route_design command is not proof that routing is complete.
# Gate the detailed report rows and the final ROUTE_STATUS histogram.  Unlike
# the small registered harness, this production run accepts no OOC reset
# PARTPIN gap: explicit gaps, partial nets and conflicts must all be zero.
set route_errors [route_row $route_text "# of nets with routing errors" 1]
set explicit_gaps [route_row $route_text "# of nets with explicit gaps"]
set unrouted_rows [route_row $route_text "# of unrouted nets"]
set unrouted_pins [route_row $route_text "# of nets with some unrouted pins"]
set resource_conflicts [route_row $route_text "# of nets with resource conflicts"]
set antennas [route_row $route_text "# of nets with antennas/islands"]
set partial_nets [llength [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == PARTIAL || ROUTE_STATUS == PARTIALLY_ROUTED ||
    ROUTE_STATUS == UNROUTED || ROUTE_STATUS == HIERPORT
}]]
set conflict_nets [llength [get_nets -quiet -hierarchical -filter {
    ROUTE_STATUS == CONFLICTS
}]]
set route_clean [expr {$route_errors == 0 && $explicit_gaps == 0 &&
    $unrouted_rows == 0 && $unrouted_pins == 0 &&
    $resource_conflicts == 0 && $antennas == 0 &&
    $partial_nets == 0 && $conflict_nets == 0}]

# report_timing_summary embeds the canonical check_timing categories.  Require
# no unclocked sequential cells, no unconstrained internal endpoints and no
# missing functional I/O delays.  Clock ports are omitted by this Vivado
# check; the only intentionally delay-free data inputs are the three reset
# assertions.
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [check_timing_count $timing_text no_input_delay]
set no_output_delay [check_timing_count $timing_text no_output_delay]
set partial_input_delay [check_timing_count $timing_text partial_input_delay]
set partial_output_delay [check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]
set drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error
}]]
set cdc_report [file join $out cdc_post_route.rpt]
set cdc_fh [open $cdc_report r]
set cdc_text [read $cdc_fh]
close $cdc_fh
set cdc_critical 0
foreach {whole count} [regexp -all -inline \
        {Critical[[:space:]]+([1-9][0-9]*)} $cdc_text] {
    incr cdc_critical $count
}
set post_unplaced [llength [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && !IS_PLACED
}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2
}]]
set uram [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == URAM288
}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == RAMB36E2
}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == RAMB18E2
}]]
set lut [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ LUT*
}]]
set ff [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ FD*
}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2 &&
    NAME =~ u_compute/u_mlp/u_serial_command/u_shared_compute/*
}]]

# Re-audit the physical contract after phys_opt, since replication or
# optimization must not move either 2,048-DSP MLP slice outside its SLR.
set slice_roots [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]]
set slice_root_count [llength $slice_roots]
set slice0_primitive_wrong -1
set slice1_primitive_wrong -1
if {$slice_root_count == 2} {
    set slice0_primitive_wrong 0
    foreach cell [get_cells -quiet -hierarchical -filter \
        "IS_PRIMITIVE && NAME =~ [lindex $slice_roots 0]/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 0} {incr slice0_primitive_wrong}
    }
    set slice1_primitive_wrong 0
    foreach cell [get_cells -quiet -hierarchical -filter \
        "IS_PRIMITIVE && NAME =~ [lindex $slice_roots 1]/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 2} {incr slice1_primitive_wrong}
    }
}

set gate_bank0 [get_cells -quiet u_meta_bank/u_gate_bank0]
set gate_bank1 [get_cells -quiet u_meta_bank/u_gate_bank1]
set down_bank0 [get_cells -quiet u_meta_bank/u_down_bank0]
set down_bank1 [get_cells -quiet u_meta_bank/u_down_bank1]
set metadata_uram_wrong -1
set metadata_bank_counts {-1 -1 -1 -1}
if {[llength $gate_bank0] == 1 && [llength $gate_bank1] == 1 &&
    [llength $down_bank0] == 1 && [llength $down_bank1] == 1} {
    set gate0_uram [get_cells -quiet -hierarchical -filter \
        "REF_NAME == URAM288 && NAME =~ $gate_bank0/*"]
    set gate1_uram [get_cells -quiet -hierarchical -filter \
        "REF_NAME == URAM288 && NAME =~ $gate_bank1/*"]
    set down0_uram [get_cells -quiet -hierarchical -filter \
        "REF_NAME == URAM288 && NAME =~ $down_bank0/*"]
    set down1_uram [get_cells -quiet -hierarchical -filter \
        "REF_NAME == URAM288 && NAME =~ $down_bank1/*"]
    set metadata_bank_counts [list [llength $gate0_uram] \
        [llength $gate1_uram] [llength $down0_uram] [llength $down1_uram]]
    set metadata_uram_wrong 0
    foreach cell $gate0_uram {
        if {[get_property SLR_INDEX $cell] != 0} {incr metadata_uram_wrong}
    }
    foreach cell $gate1_uram {
        if {[get_property SLR_INDEX $cell] != 2} {incr metadata_uram_wrong}
    }
    foreach cell [concat $down0_uram $down1_uram] {
        if {[get_property SLR_INDEX $cell] != 1} {incr metadata_uram_wrong}
    }
}

# The eleven projection lanes relieve the center SLR's nearly saturated DSP
# and CLB columns. Re-audit every descendant primitive after phys_opt/route;
# checking only the DSP total would miss replicated or migrated local control
# logic, while checking only wrong==0 would let an empty selector pass.
set projection_array u_compute/u_attention/u_compute/u_projection/u_array
set projection_lane_slr0 [get_cells -quiet [list \
    ${projection_array}/g_row\[0\].g_col\[0\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[1\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[2\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[3\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[4\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[5\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[6\].u_lane \
    ${projection_array}/g_row\[0\].g_col\[7\].u_lane]]
set projection_lane_slr2 [get_cells -quiet [list \
    ${projection_array}/g_row\[7\].g_col\[13\].u_lane \
    ${projection_array}/g_row\[7\].g_col\[14\].u_lane \
    ${projection_array}/g_row\[7\].g_col\[15\].u_lane]]
set projection_slr0_dsp {}
set projection_slr2_dsp {}
set projection_slr0_primitive_wrong 0
set projection_slr2_primitive_wrong 0
foreach lane $projection_lane_slr0 {
    set projection_slr0_dsp [concat $projection_slr0_dsp \
        [get_cells -quiet -hierarchical -filter \
            "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $lane/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 0} {incr projection_slr0_primitive_wrong}
    }
}
foreach lane $projection_lane_slr2 {
    set projection_slr2_dsp [concat $projection_slr2_dsp \
        [get_cells -quiet -hierarchical -filter \
            "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
    foreach cell [get_cells -quiet -hierarchical -filter \
            "IS_PRIMITIVE && NAME =~ $lane/*"] {
        set index [get_property SLR_INDEX $cell]
        if {$index ne "" && $index != 2} {incr projection_slr2_primitive_wrong}
    }
}
set projection_slr0_dsp_wrong 0
foreach cell $projection_slr0_dsp {
    if {[get_property SLR_INDEX $cell] != 0} {incr projection_slr0_dsp_wrong}
}
set projection_slr2_dsp_wrong 0
foreach cell $projection_slr2_dsp {
    if {[get_property SLR_INDEX $cell] != 2} {incr projection_slr2_dsp_wrong}
}
set projection_ok [expr {[llength $projection_lane_slr0] == 8 &&
    [llength $projection_lane_slr2] == 3 &&
    [llength $projection_slr0_dsp] == 136 &&
    [llength $projection_slr2_dsp] == 51 &&
    $projection_slr0_dsp_wrong == 0 && $projection_slr2_dsp_wrong == 0 &&
    $projection_slr0_primitive_wrong == 0 &&
    $projection_slr2_primitive_wrong == 0}]

set slr_dsp {0 0 0}
set slr_uram {0 0 0}
set slr_ramb36 {0 0 0}
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}] {
    set index [get_property SLR_INDEX $cell]
    lset slr_dsp $index [expr {[lindex $slr_dsp $index] + 1}]
}
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}] {
    set index [get_property SLR_INDEX $cell]
    lset slr_uram $index [expr {[lindex $slr_uram $index] + 1}]
}
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}] {
    set index [get_property SLR_INDEX $cell]
    lset slr_ramb36 $index [expr {[lindex $slr_ramb36 $index] + 1}]
}

set resource_exact [expr {$dsp == 6492 && $uram == 752 &&
    $kernel_dsp == 4096}]
set physical_ok [expr {$post_unplaced == 0 && $slice_root_count == 2 &&
    $slice0_primitive_wrong == 0 && $slice1_primitive_wrong == 0 &&
    $metadata_bank_counts eq {224 224 112 112} &&
    $metadata_uram_wrong == 0 &&
    $projection_ok &&
    [lindex $slr_dsp 0] <= 2200 && [lindex $slr_dsp 1] <= 2200 &&
    [lindex $slr_dsp 2] <= 2200 && $dsp <= 6498 && $resource_exact}]
set status [expr {$wns >= 0.0 && $whs >= 0.0 && $route_clean &&
    $timing_coverage_ok && $drc_errors == 0 && $cdc_critical == 0 &&
    $physical_ok ? "OOC_POST_ROUTE_PASS" :
    "OOC_POST_ROUTE_FAIL"}]

set summary [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $actual_part input_dcp $in_dcp \
    core_clock_mhz 150 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    core_io_budget_ns 1.000 ddr_io_budget_ns 0.800 \
    physopt_directive $physopt_directive route_directive $route_directive \
    pre_unplaced_primitives $pre_unplaced pre_dsp48e2 $pre_dsp \
    pre_uram288 $pre_uram pre_mlp_kernel_dsp48e2 $pre_kernel_dsp \
    post_unplaced_primitives $post_unplaced \
    post_route_wns_ns $wns post_route_whs_ns $whs \
    worst_setup_start $setup_start worst_setup_end $setup_end \
    worst_hold_start $hold_start worst_hold_end $hold_end \
    route_error_nets $route_errors explicit_gap_nets $explicit_gaps \
    unrouted_nets $unrouted_rows some_unrouted_pin_nets $unrouted_pins \
    resource_conflict_nets $resource_conflicts \
    antenna_island_nets $antennas route_status_partial $partial_nets \
    route_status_conflicts $conflict_nets route_clean $route_clean \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    no_input_delay_ports $no_input_delay no_output_delay_ports $no_output_delay \
    partial_input_delay_ports $partial_input_delay \
    partial_output_delay_ports $partial_output_delay \
    timing_coverage_ok $timing_coverage_ok drc_errors $drc_errors \
    cdc_critical $cdc_critical \
    lut_primitives $lut ff_primitives $ff dsp48e2 $dsp \
    mlp_kernel_dsp48e2 $kernel_dsp \
    ramb36e2 $ramb36 ramb18e2 $ramb18 uram288 $uram \
    slice_root_count $slice_root_count \
    slice0_primitive_wrong_slr $slice0_primitive_wrong \
    slice1_primitive_wrong_slr $slice1_primitive_wrong \
    metadata_bank_uram_counts $metadata_bank_counts \
    metadata_uram_wrong_slr $metadata_uram_wrong \
    projection_slr0_root_count [llength $projection_lane_slr0] \
    projection_slr2_root_count [llength $projection_lane_slr2] \
    projection_slr0_dsp [llength $projection_slr0_dsp] \
    projection_slr2_dsp [llength $projection_slr2_dsp] \
    projection_slr0_dsp_wrong $projection_slr0_dsp_wrong \
    projection_slr2_dsp_wrong $projection_slr2_dsp_wrong \
    projection_slr0_primitive_wrong $projection_slr0_primitive_wrong \
    projection_slr2_primitive_wrong $projection_slr2_primitive_wrong \
    projection_contract_ok $projection_ok \
    slr0_dsp [lindex $slr_dsp 0] slr1_dsp [lindex $slr_dsp 1] \
    slr2_dsp [lindex $slr_dsp 2] \
    slr0_uram [lindex $slr_uram 0] slr1_uram [lindex $slr_uram 1] \
    slr2_uram [lindex $slr_uram 2] \
    slr0_ramb36 [lindex $slr_ramb36 0] \
    slr1_ramb36 [lindex $slr_ramb36 1] \
    slr2_ramb36 [lindex $slr_ramb36 2] \
    exact_resource_contract_ok $resource_exact \
    physical_contract_ok $physical_ok status $status] {
    puts $summary "$key=$value"
}
close $summary

puts "PRODUCTION_OOC_ROUTE WNS=$wns WHS=$whs ROUTE_CLEAN=$route_clean EXPLICIT_GAPS=$explicit_gaps UNCONSTRAINED=$unconstrained IODELAY_MISSING=$no_input_delay/$no_output_delay DRC=$drc_errors CDC_CRITICAL=$cdc_critical DSP=$dsp URAM=$uram PHYSICAL=$physical_ok STATUS=$status"
if {$status ne "OOC_POST_ROUTE_PASS"} {
    error "Production OOC post-route acceptance failed"
}
close_design
