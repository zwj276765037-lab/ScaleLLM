# Read-only P7 pre-place qualification.  This recreates the P3 base and
# Attention geometry with the P7 region2 row split, layers the P5 input and P6
# 4/8/4 postprocess partitions, runs DRC, and exits without implementation.

set audit_script [file normalize [info script]]
set dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PREPLACE_DIR)]
set input_sha [file normalize $::env(HAP_PREPLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PREPLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PREPLACE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_PREPLACE_GEOMETRY_LIB)]
set p5_lib [file normalize $::env(HAP_PREPLACE_P5_LIB)]
set p6_lib [file normalize $::env(HAP_PREPLACE_P6_LIB)]
set p10_proc_lib [file normalize $::env(HAP_PREPLACE_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_PREPLACE_LAUNCHER)]
set clock_xdc [file normalize $::env(HAP_PREPLACE_CLOCK_XDC)]
set io_audit [file normalize $::env(HAP_PREPLACE_IO_AUDIT)]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set contract_variant P2_COHORT16_COL2_12_2
set geometry_prefix p3_
set region2_variant rowsplit_y5_y6_y6_y8
set p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

if {![string match "2025.2*" [version -short]]} {
    error "P7 pre-place requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P7 pre-place requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P7 pre-place requires HAP_JOBS=32"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P7 pre-place received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 10 $expected_manifest_sha]
foreach required [list $dcp $selector_lib $geometry_lib $p5_lib $p6_lib \
        $p10_proc_lib $audit_script $expected_launcher $clock_xdc $io_audit] {
    if {![dict exists $frozen $required]} {
        error "P7 pre-place required input absent from manifest: $required"
    }
}
set actual_dcp_sha [hap_p10_sha256 $dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P7 pre-place DCP identity mismatch"
}

set xdc_text [hap_p10_read_nonempty $clock_xdc "P7 clock XDC"]
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
if {[regexp -nocase -- [format {%s|%s} $forbidden_false_path \
        $forbidden_datapath] $xdc_code]} {
    error "P7 XDC contains a forbidden timing waiver"
}
if {[llength [regexp -all -inline {create_clock[[:space:]]} $xdc_code]] != 3 ||
    [llength [regexp -all -inline {set_input_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_output_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_clock_groups[[:space:]]+-asynchronous} \
        $xdc_code]] != 1} {
    error "P7 XDC command cardinality mismatch"
}

source $selector_lib
source $geometry_lib
source $p5_lib
source $p6_lib
open_checkpoint $dcp
read_xdc $clock_xdc
source $io_audit
foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P7 clock contract mismatch: $name"
    }
}

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {
    error "P7 pre-place compute-net selector is empty"
}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "P7 pre-place compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
}

set base_plan [hap_v5_floorplan::discover $contract_variant]
set projection_root [file dirname \
    [get_property NAME [dict get $base_plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set p5_plan [hap_v5_p5_input_partition::discover $base_plan]
set p6_plan [hap_v5_p6_postprocess_partition::discover $base_plan $p5_plan]

foreach spec [hap_v5_floorplan::pblock_specs $base_plan $contract_variant] {
    hap_p10_create_hard_slr_pblock [dict get $spec name] \
        [dict get $spec target] [dict get $base_plan [dict get $spec key]]
}
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0 \
    $region2_variant
hap_v5_p5_input_partition::apply $p5_plan
hap_v5_p6_postprocess_partition::apply $p6_plan

set geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1 $region2_variant]
set base_audit [hap_v5_floorplan::audit_pblock_contract \
    $base_plan 0 $contract_variant \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix \
        $region2_variant]]
set p5_audit [hap_v5_p5_input_partition::audit $p5_plan 0]
set p6_audit [hap_v5_p6_postprocess_partition::audit $p6_plan 0]
set pblock_count [llength [get_pblocks -quiet]]

hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors.txt] V5_P10_P7_BASE_SELECTORS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry.txt] V5_P10_P7_GEOMETRY_PASS
hap_v5_floorplan::write_pblock_audit $base_audit \
    [file join $out base_pblocks.txt] V5_P10_P7_BASE_PBLOCK_PASS
hap_v5_p5_input_partition::write_plan $p5_plan \
    [file join $out p5_input_plan.txt] V5_P10_P5_INPUT_PLAN_PASS
hap_v5_p5_input_partition::write_audit $p5_audit \
    [file join $out p5_input_pblocks.txt] V5_P10_P5_INPUT_PBLOCK_PASS
hap_v5_p6_postprocess_partition::write_plan $p6_plan \
    [file join $out p6_postprocess_plan.txt] \
    V5_P10_P6_POSTPROCESS_PLAN_PASS
hap_v5_p6_postprocess_partition::write_audit $p6_audit \
    [file join $out p6_postprocess_pblocks.txt] \
    V5_P10_P6_POSTPROCESS_PBLOCK_PASS
report_drc -file [file join $out drc_pre_place.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]

set expected_base_extras [expr {
    [llength [dict get $p5_plan center_base_extras]] +
    [llength [dict get $p6_plan center_rows]]}]
set status_ok [expr {
    [dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    [dict get $base_plan history2_count] == 2 &&
    [dict get $base_plan generic_repack_count] == 0 &&
    [dict get $base_plan projection_weight_capture_ok] == 1 &&
    [dict get $base_plan planned_slr0_dsp] == 1862 &&
    [dict get $base_plan planned_slr1_dsp] == 1781 &&
    [dict get $base_plan planned_slr2_dsp] == 1810 &&
    [dict get $base_audit ok] &&
    [dict get $base_audit pblock_count] == 11 &&
    [dict get $base_audit dsp_coverage] == 5453 &&
    [dict get $base_audit uram_coverage] == 752 &&
    [dict get $base_audit optimizer_extra_count] == $expected_base_extras &&
    [dict get $geometry_audit pblock_count] == 12 &&
    [dict get $geometry_plan center_region2_row_exact_cover] == 1 &&
    [llength [dict get $geometry_plan \
        center_region2_rows0_3_primitives]] == 26800 &&
    [llength [dict get $geometry_plan \
        center_region2_rows4_7_primitives]] == 26800 &&
    [llength [dict get $geometry_plan \
        center_region2_residual_primitives]] == 15199 &&
    [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_rows0_3_primitives] \
        DSP48E2] == 272 &&
    [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_rows4_7_primitives] \
        DSP48E2] == 272 &&
    [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_residual_primitives] \
        DSP48E2] == 0 &&
    [dict get $p5_audit ok] &&
    [dict get $p5_audit pblock_count] == 2 &&
    [dict get $p5_audit outer_extras] == 0 &&
    [dict get $p6_audit ok] &&
    [dict get $p6_audit pblock_count] == 2 &&
    [dict get $p6_audit outer_extras] == 0 &&
    [dict get $p5_plan completed_u8_ff] == 4096 &&
    [dict get $p5_plan completed_meta_ff] == 352 &&
    [dict get $p5_plan input_capture_ff] == 12288 &&
    [dict get $p5_plan capture_leaf_count] == 48 &&
    $pblock_count == 27 && $drc_errors == 0}]
set status [expr {$status_ok ? "V5_P10_P7_PRE_PLACE_PASS" : "FAIL"}]
hap_p10_write_summary $out [list tool [version -short] \
    stage V5_P10_P7_PRE_PLACE evidence_class READ_ONLY_PRE_PLACE \
    input_dcp $dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_p10_sha256 $input_sha] \
    input_manifest_entries 10 provenance_verified 1 \
    contract_variant $contract_variant p5_contract [dict get $p5_plan contract] \
    p6_contract [dict get $p6_plan contract] \
    p7_contract $p7_contract region2_variant $region2_variant \
    jobs $jobs core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    dsp48e2 [dict get $base_plan total_dsp] \
    uram288 [dict get $base_plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $base_plan kernel_dsp] \
    projected_slr_dsp48e2 [list \
        [dict get $base_plan planned_slr0_dsp] \
        [dict get $base_plan planned_slr1_dsp] \
        [dict get $base_plan planned_slr2_dsp]] \
    projected_slr_uram288 {224 224 304} \
    canonical_pblock_count [dict get $base_audit pblock_count] \
    geometry_pblock_count [dict get $geometry_audit pblock_count] \
    p5_added_pblock_count [dict get $p5_audit pblock_count] \
    p6_added_pblock_count [dict get $p6_audit pblock_count] \
    total_pblock_count $pblock_count \
    base_pblock_optimizer_extras [dict get $base_audit optimizer_extra_count] \
    expected_center_base_extras $expected_base_extras \
    input_root_primitives [llength [dict get $p5_plan root_primitives]] \
    input_half0_primitives [llength [dict get $p5_plan half0_primitives]] \
    input_half1_primitives [llength [dict get $p5_plan half1_primitives]] \
    input_center_primitives [llength [dict get $p5_plan center_primitives]] \
    completed_u8_ff [dict get $p5_plan completed_u8_ff] \
    completed_meta_ff [dict get $p5_plan completed_meta_ff] \
    input_capture_ff [dict get $p5_plan input_capture_ff] \
    input_capture_controls [dict get $p5_plan capture_leaf_count] \
    p6_slr0_row_primitives [llength [dict get $p6_plan slr0_rows]] \
    p6_center_row_primitives [llength [dict get $p6_plan center_rows]] \
    p6_slr2_row_primitives [llength [dict get $p6_plan slr2_rows]] \
    p7_region2_rows0_3_primitives [llength [dict get $geometry_plan \
        center_region2_rows0_3_primitives]] \
    p7_region2_rows4_7_primitives [llength [dict get $geometry_plan \
        center_region2_rows4_7_primitives]] \
    p7_region2_residual_primitives [llength [dict get $geometry_plan \
        center_region2_residual_primitives]] \
    p7_region2_rows0_3_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_rows0_3_primitives] DSP48E2] \
    p7_region2_rows4_7_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_rows4_7_primitives] DSP48E2] \
    p7_region2_residual_dsp48e2 [hap_projection_ooc_floorplan::count_ref \
        [dict get $geometry_plan center_region2_residual_primitives] DSP48E2] \
    pre_place_drc_errors $drc_errors implementation_commands_run 0 \
    checkpoint_written 0 route_eligible 0 status $status]
close_design
if {!$status_ok} {error "P7 strict pre-place gate failed"}
