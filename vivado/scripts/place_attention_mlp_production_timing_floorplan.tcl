set root [file normalize [file join [file dirname [file normalize [info script]]] ../..]]
set in_dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PLACE_DIR)]
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "SSI_SpreadLogic_high"}]
set expected_part xcvu9p-flga2104-2L-e
file mkdir $out
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}
open_checkpoint $in_dcp
set actual_part [get_property PART [current_design]]
if {$actual_part ne $expected_part} {
    error "Illegal placement input part: expected $expected_part, got $actual_part"
}
read_xdc [file join $root vivado constraints attention_mlp_production_ooc_clocks.xdc]
source [file join $root vivado scripts check_attention_mlp_production_io_selectors.tcl]

# Fail before the expensive placement if the explicitly supplied checkpoint is
# not the resource-audited V4 production shape.  An older resource-only DCP can
# otherwise satisfy most hierarchy selectors and waste hours before detection.
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
if {$pre_dsp != 6492 || $pre_uram != 752 || $pre_kernel_dsp != 4096} {
    error "Illegal placement input resources: DSP=$pre_dsp URAM=$pre_uram kernel_DSP=$pre_kernel_dsp"
}

# Keep the two independently routable MLP slices on opposite outer SLRs.
set slice_roots [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45* ||
    REF_NAME =~ hap_mlp_shared_slice8x16_s43_s45*
}]
set slice_roots [lsort -dictionary $slice_roots]
if {[llength $slice_roots] != 2} {
    error "Expected two MLP slice roots, got [llength $slice_roots]"
}
set slice0_root [lindex $slice_roots 0]
set slice1_root [lindex $slice_roots 1]
create_pblock pb_mlp_slice0_slr0
add_cells_to_pblock [get_pblocks pb_mlp_slice0_slr0] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $slice0_root/*"]
resize_pblock [get_pblocks pb_mlp_slice0_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_mlp_slice0_slr0]
create_pblock pb_mlp_slice1_slr2
add_cells_to_pblock [get_pblocks pb_mlp_slice1_slr2] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $slice1_root/*"]
resize_pblock [get_pblocks pb_mlp_slice1_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_mlp_slice1_slr2]

# Keep every cascaded metadata URAM bank inside one SLR.  The previous free
# placement let individual cascade chains span SLRs and made the URAM enable
# path part of the global ready critical path.  224/224/112+112 exactly fills
# 224 metadata URAM per SLR before the unrelated 80 Attention URAMs are placed.
set gate_bank0 [get_cells -quiet u_meta_bank/u_gate_bank0]
set gate_bank1 [get_cells -quiet u_meta_bank/u_gate_bank1]
set down_bank0 [get_cells -quiet u_meta_bank/u_down_bank0]
set down_bank1 [get_cells -quiet u_meta_bank/u_down_bank1]
if {[llength $gate_bank0] != 1 || [llength $gate_bank1] != 1 ||
    [llength $down_bank0] != 1 || [llength $down_bank1] != 1} {
    error "Metadata bank hierarchy selectors did not resolve 1/1/1/1 roots"
}
create_pblock pb_meta_gate_bank0_slr0
add_cells_to_pblock [get_pblocks pb_meta_gate_bank0_slr0] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $gate_bank0/*"]
resize_pblock [get_pblocks pb_meta_gate_bank0_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_meta_gate_bank0_slr0]
create_pblock pb_meta_gate_bank1_slr2
add_cells_to_pblock [get_pblocks pb_meta_gate_bank1_slr2] \
    [get_cells -quiet -hierarchical -filter "NAME =~ $gate_bank1/*"]
resize_pblock [get_pblocks pb_meta_gate_bank1_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_meta_gate_bank1_slr2]
create_pblock pb_meta_down_banks_slr1
add_cells_to_pblock [get_pblocks pb_meta_down_banks_slr1] \
    [concat [get_cells -quiet -hierarchical -filter "NAME =~ $down_bank0/*"] \
        [get_cells -quiet -hierarchical -filter "NAME =~ $down_bank1/*"]]
resize_pblock [get_pblocks pb_meta_down_banks_slr1] -add {SLR1}
set_property IS_SOFT false [get_pblocks pb_meta_down_banks_slr1]

# Run 0050 still left 2,264 DSP and 99.63% CLB occupancy in SLR1. Move eleven
# complete 17-DSP lane modules, including their local LUT/FF pipelines. Eight
# lanes go to SLR0 and three to SLR2, targeting DSP ~=2184/2145/2163 while
# also relieving the center-SLR Attention projection congestion.
set projection_array \
    u_compute/u_attention/u_compute/u_projection/u_array
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
if {[llength $projection_lane_slr0] != 8 ||
    [llength $projection_lane_slr2] != 3} {
    error "Attention projection lane selectors did not resolve 8/3 roots"
}
create_pblock pb_attention_projection_lane_slr0
set projection_lane_slr0_cells {}
foreach lane $projection_lane_slr0 {
    set projection_lane_slr0_cells [concat $projection_lane_slr0_cells \
        [get_cells -quiet -hierarchical -filter "NAME =~ $lane/*"]]
}
add_cells_to_pblock [get_pblocks pb_attention_projection_lane_slr0] \
    $projection_lane_slr0_cells
resize_pblock [get_pblocks pb_attention_projection_lane_slr0] -add {SLR0}
set_property IS_SOFT false [get_pblocks pb_attention_projection_lane_slr0]
create_pblock pb_attention_projection_lanes_slr2
set projection_lane_slr2_cells {}
foreach lane $projection_lane_slr2 {
    set projection_lane_slr2_cells [concat $projection_lane_slr2_cells \
        [get_cells -quiet -hierarchical -filter "NAME =~ $lane/*"]]
}
add_cells_to_pblock [get_pblocks pb_attention_projection_lanes_slr2] \
    $projection_lane_slr2_cells
resize_pblock [get_pblocks pb_attention_projection_lanes_slr2] -add {SLR2}
set_property IS_SOFT false [get_pblocks pb_attention_projection_lanes_slr2]

report_drc -file [file join $out drc_pre_place.rpt]
set pre_drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
if {$pre_drc_errors != 0} {
    error "Pre-place DRC has $pre_drc_errors errors"
}

place_design -directive $place_directive
write_checkpoint -force [file join $out post_place.dcp]
report_utilization -file [file join $out utilization.rpt]
report_utilization -hierarchical -hierarchical_depth 9 -file \
    [file join $out utilization_hier.rpt]
report_utilization -slr -file [file join $out utilization_slr.rpt]
report_timing_summary -delay_type min_max -max_paths 100 -file \
    [file join $out timing_post_place.rpt]
report_design_analysis -congestion -file \
    [file join $out congestion_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization.rpt]

set unplaced [llength [get_cells -quiet -hierarchical -filter {
    IS_PRIMITIVE && !IS_PLACED
}]]
set dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2
}]]
set uram [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == URAM288
}]]
set kernel_dsp [llength [get_cells -quiet -hierarchical -filter {
    REF_NAME == DSP48E2 &&
    NAME =~ u_compute/u_mlp/u_serial_command/u_shared_compute/*
}]]
set slice0_dsp [get_cells -quiet -hierarchical -filter \
    "REF_NAME == DSP48E2 && NAME =~ $slice0_root/*"]
set slice1_dsp [get_cells -quiet -hierarchical -filter \
    "REF_NAME == DSP48E2 && NAME =~ $slice1_root/*"]
set slice0_bad 0
foreach cell $slice0_dsp {
    if {[get_property SLR_INDEX $cell] != 0} {incr slice0_bad}
}
set slice1_bad 0
foreach cell $slice1_dsp {
    if {[get_property SLR_INDEX $cell] != 2} {incr slice1_bad}
}
set slice0_primitive_bad 0
foreach cell [get_cells -quiet -hierarchical -filter \
    "IS_PRIMITIVE && NAME =~ $slice0_root/*"] {
    set index [get_property SLR_INDEX $cell]
    if {$index ne "" && $index != 0} {incr slice0_primitive_bad}
}
set slice1_primitive_bad 0
foreach cell [get_cells -quiet -hierarchical -filter \
    "IS_PRIMITIVE && NAME =~ $slice1_root/*"] {
    set index [get_property SLR_INDEX $cell]
    if {$index ne "" && $index != 2} {incr slice1_primitive_bad}
}

set gate0_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $gate_bank0/*"]
set gate1_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $gate_bank1/*"]
set down0_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $down_bank0/*"]
set down1_uram [get_cells -quiet -hierarchical -filter \
    "REF_NAME == URAM288 && NAME =~ $down_bank1/*"]
set metadata_uram_bad 0
foreach cell $gate0_uram {
    if {[get_property SLR_INDEX $cell] != 0} {incr metadata_uram_bad}
}
foreach cell $gate1_uram {
    if {[get_property SLR_INDEX $cell] != 2} {incr metadata_uram_bad}
}
foreach cell [concat $down0_uram $down1_uram] {
    if {[get_property SLR_INDEX $cell] != 1} {incr metadata_uram_bad}
}

set moved0_dsp {}
foreach lane $projection_lane_slr0 {
    set moved0_dsp [concat $moved0_dsp [get_cells -quiet -hierarchical \
        -filter "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
}
set moved2_dsp {}
foreach lane $projection_lane_slr2 {
    set moved2_dsp [concat $moved2_dsp [get_cells -quiet -hierarchical \
        -filter "REF_NAME == DSP48E2 && NAME =~ $lane/*"]]
}
set moved0_bad 0
foreach cell $moved0_dsp {
    if {[get_property SLR_INDEX $cell] != 0} {incr moved0_bad}
}
set moved2_bad 0
foreach cell $moved2_dsp {
    if {[get_property SLR_INDEX $cell] != 2} {incr moved2_bad}
}

set slr_dsp {0 0 0}
set slr_uram {0 0 0}
set slr_bram36 {0 0 0}
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
    lset slr_bram36 $index [expr {[lindex $slr_bram36 $index] + 1}]
}

set worst_setup [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set worst_hold [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $worst_setup]
set whs [get_property SLACK $worst_hold]
set setup_start [get_property STARTPOINT_PIN $worst_setup]
set setup_end [get_property ENDPOINT_PIN $worst_setup]
set hold_start [get_property STARTPOINT_PIN $worst_hold]
set hold_end [get_property ENDPOINT_PIN $worst_hold]
set status [expr {$unplaced == 0 && $slice0_bad == 0 && $slice1_bad == 0 &&
    $slice0_primitive_bad == 0 && $slice1_primitive_bad == 0 &&
    [llength $moved0_dsp] == 136 && [llength $moved2_dsp] == 51 &&
    $moved0_bad == 0 && $moved2_bad == 0 &&
    [llength $gate0_uram] == 224 && [llength $gate1_uram] == 224 &&
    [llength $down0_uram] == 112 && [llength $down1_uram] == 112 &&
    $metadata_uram_bad == 0 &&
    $dsp == 6492 && $uram == 752 && $kernel_dsp == 4096 &&
    [lindex $slr_dsp 0] <= 2200 && [lindex $slr_dsp 1] <= 2200 &&
    [lindex $slr_dsp 2] <= 2200 ? "TIMING_PLACE_COMPLETE" : "FAIL"}]
set f [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $actual_part input_dcp $in_dcp \
    directive $place_directive \
    pre_dsp48e2 $pre_dsp pre_uram288 $pre_uram \
    pre_mlp_kernel_dsp48e2 $pre_kernel_dsp \
    pre_place_drc_errors $pre_drc_errors unplaced_primitives $unplaced \
    dsp48e2 $dsp uram288 $uram mlp_kernel_dsp48e2 $kernel_dsp \
    exact_resource_contract_ok [expr {$dsp == 6492 && $uram == 752 &&
        $kernel_dsp == 4096}] \
    slice0_dsp [llength $slice0_dsp] slice0_wrong_slr $slice0_bad \
    slice0_primitive_wrong_slr $slice0_primitive_bad \
    slice1_dsp [llength $slice1_dsp] slice1_wrong_slr $slice1_bad \
    slice1_primitive_wrong_slr $slice1_primitive_bad \
    moved_projection_slr0_dsp [llength $moved0_dsp] \
    moved_projection_slr0_wrong $moved0_bad \
    moved_projection_slr2_dsp [llength $moved2_dsp] \
    moved_projection_slr2_wrong $moved2_bad \
    metadata_gate0_uram [llength $gate0_uram] \
    metadata_gate1_uram [llength $gate1_uram] \
    metadata_down0_uram [llength $down0_uram] \
    metadata_down1_uram [llength $down1_uram] \
    metadata_uram_wrong_slr $metadata_uram_bad \
    slr0_dsp [lindex $slr_dsp 0] slr1_dsp [lindex $slr_dsp 1] \
    slr2_dsp [lindex $slr_dsp 2] \
    slr0_uram [lindex $slr_uram 0] slr1_uram [lindex $slr_uram 1] \
    slr2_uram [lindex $slr_uram 2] \
    slr0_ramb36 [lindex $slr_bram36 0] \
    slr1_ramb36 [lindex $slr_bram36 1] \
    slr2_ramb36 [lindex $slr_bram36 2] \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    worst_setup_start $setup_start worst_setup_end $setup_end \
    worst_hold_start $hold_start worst_hold_end $hold_end \
    status $status] {
    puts $f "$key=$value"
}
close $f
puts "PRODUCTION_TIMING_PLACE UNPLACED=$unplaced DSP=$slr_dsp WNS=$wns WHS=$whs STATUS=$status"
if {$status ne "TIMING_PLACE_COMPLETE"} {
    error "production timing-driven placement audit failed"
}
close_design
