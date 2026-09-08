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

set array_control [get_cells -quiet -hierarchical -filter {
    NAME == u_dut/u_array/control_error_r_reg && REF_NAME =~ FD*}]
set array_control_count [require_count array_control_register \
    $array_control 1]
set center_wrapper_control [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/control_error_r_reg*}]
set center_wrapper_control_count [require_count \
    center_wrapper_control_register $center_wrapper_control 0]

set local_control [get_cells -quiet -hierarchical -filter {
    (NAME == u_dut/u_array/u_left2/u_shard/control_error_r_reg) ||
    (NAME == u_dut/u_array/u_center12/u_region0_cols2_3/control_error_r_reg) ||
    (NAME == u_dut/u_array/u_center12/u_region1_cols4_7/control_error_r_reg) ||
    (NAME == u_dut/u_array/u_center12/u_region2_cols8_11/control_error_r_reg) ||
    (NAME == u_dut/u_array/u_center12/u_region3_cols12_13/control_error_r_reg) ||
    (NAME == u_dut/u_array/u_right2/u_shard/control_error_r_reg)}]
set local_control_count [require_count local_shard_control_register \
    $local_control 6]
set local_control_copies [get_cells -quiet -hierarchical -filter {
    ((NAME =~ u_dut/u_array/u_left2/u_shard/control_error_r_reg*) ||
     (NAME =~ u_dut/u_array/u_center12/u_region0_cols2_3/control_error_r_reg*) ||
     (NAME =~ u_dut/u_array/u_center12/u_region1_cols4_7/control_error_r_reg*) ||
     (NAME =~ u_dut/u_array/u_center12/u_region2_cols8_11/control_error_r_reg*) ||
     (NAME =~ u_dut/u_array/u_center12/u_region3_cols12_13/control_error_r_reg*) ||
     (NAME =~ u_dut/u_array/u_right2/u_shard/control_error_r_reg*)) &&
    REF_NAME =~ FD*}]
set local_control_copy_count [llength $local_control_copies]
if {$local_control_copy_count < $local_control_count} {
    error "local shard control copy count is smaller than logical count"
}
set fp [open [file join $out local_control_cells.txt] w]
foreach cell [lsort -dictionary $local_control_copies] {
    puts $fp [join [list [get_property NAME $cell] \
        [get_property REF_NAME $cell] [get_property ORIG_REF_NAME $cell]] \t]
}
close $fp

set array_control_d [get_pins -quiet -of_objects $array_control -filter {
    REF_PIN_NAME == D}]
require_count array_control_d_pin $array_control_d 1
set control_start_pins [all_fanin -flat -startpoints_only -to $array_control_d]
set control_start_cells [get_cells -quiet -of_objects $control_start_pins]
set remote_control_start_cells [filter $control_start_cells {
    (NAME =~ u_dut/u_array/u_left2/*) ||
    (NAME =~ u_dut/u_array/u_right2/*) ||
    (NAME =~ u_dut/u_array/u_center12/u_region0_cols2_3/*) ||
    (NAME =~ u_dut/u_array/u_center12/u_region2_cols8_11/*) ||
    (NAME =~ u_dut/u_array/u_center12/u_region3_cols12_13/*)}]
set remote_control_start_count [require_count \
    remote_array_control_startpoint $remote_control_start_cells 0]

set retired_compare_nets [get_nets -quiet -hierarchical -filter {
    (NAME =~ u_dut/u_array/all_capture_ready*) ||
    (NAME =~ u_dut/u_array/all_launch_ready*) ||
    (NAME =~ u_dut/u_array/all_guard_valid*) ||
    (NAME =~ u_dut/u_array/all_accum_ready*) ||
    (NAME =~ u_dut/u_array/u_center12/all_*ready*) ||
    (NAME =~ u_dut/u_array/u_center12/all_*valid*)}]
set retired_compare_net_count [require_count retired_compare_net \
    $retired_compare_nets 0]

set lanes [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_a8w8_group32_lane_s42 ||
    ORIG_REF_NAME == hap_a8w8_group32_lane_s42)}]
set dual_accumulators [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && (REF_NAME == hap_linear_tile_accum_dual_s42 ||
    ORIG_REF_NAME == hap_linear_tile_accum_dual_s42)}]
set lane_count [require_count attention_lane_instances $lanes 128]
set dual_accumulator_count [require_count local_dual_accumulator_instances \
    $dual_accumulators 6]
set dut_dsp [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/* && REF_NAME == DSP48E2}]]
set array_dsp [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/* && REF_NAME == DSP48E2}]]
set frontend_dsp [llength [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_frontend/* && REF_NAME == DSP48E2}]]
if {$dut_dsp != 2240 || $array_dsp != 2176 || $frontend_dsp != 64} {
    error "projection DSP identity mismatch $dut_dsp/$array_dsp/$frontend_dsp"
}

report_timing -delay_type max -to $array_control_d -max_paths 100 \
    -file [file join $out array_control_setup_post_synth.rpt]
report_high_fanout_nets -timing -max_nets 300 -file \
    [file join $out high_fanout_post_synth.rpt]

set status [expr {$array_control_count == 1 &&
    $center_wrapper_control_count == 0 && $local_control_count == 6 &&
    $remote_control_start_count == 0 && $retired_compare_net_count == 0 &&
    $lane_count == 128 && $dual_accumulator_count == 6 &&
    $dut_dsp == 2240 && $array_dsp == 2176 && $frontend_dsp == 64 ?
    "PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] jobs $jobs \
    stage READ_ONLY_LOCAL_LOCKSTEP_POST_SYNTH_DIAGNOSIS \
    input_dcp $input_dcp array_control_registers $array_control_count \
    center_wrapper_control_registers $center_wrapper_control_count \
    local_shard_control_registers $local_control_count \
    local_shard_control_register_copies $local_control_copy_count \
    remote_array_control_startpoints $remote_control_start_count \
    retired_compare_nets $retired_compare_net_count \
    attention_lane_instances $lane_count \
    local_dual_accumulator_instances $dual_accumulator_count \
    dut_dsp48e2 $dut_dsp array_dsp48e2 $array_dsp \
    frontend_dsp48e2 $frontend_dsp implementation_commands 0 \
    checkpoints_written 0 status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "ATTENTION_LOCAL_LOCKSTEP_POST_SYNTH STATUS=$status LOCAL=$local_control_count REMOTE_FANIN=$remote_control_start_count DSP=$dut_dsp"
if {$status ne "PASS"} {
    error "Attention local lockstep post-synth diagnosis failed"
}
