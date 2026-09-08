# Strict 100 MHz P12 production placement.  The P9 floorplan is retained and
# only the Attention region1 non-DSP logic pblock gains X5Y5 as a legal relief
# region.  DSP stripes, quantizer3, RTL, clocks, and dataflow are unchanged.

set place_script [file normalize [info script]]
set in_dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PLACE_DIR)]
set input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PLACE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_PLACE_GEOMETRY_LIB)]
set p5_lib [file normalize $::env(HAP_PLACE_P5_LIB)]
set post_lib [file normalize $::env(HAP_PLACE_P9_POST_LIB)]
set quantizer3_lib [file normalize $::env(HAP_PLACE_P9_QUANTIZER3_LIB)]
set relief_lib [file normalize $::env(HAP_PLACE_P12_RELIEF_LIB)]
set boundary_lib [file normalize $::env(HAP_PLACE_BOUNDARY_LIB)]
set p10_proc_lib [file normalize $::env(HAP_PLACE_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_PLACE_LAUNCHER)]
set io_audit [file normalize $::env(HAP_PLACE_IO_AUDIT)]
set clock_xdc [file normalize $::env(HAP_PLACE_CLOCK_XDC)]
set preplace_output_sha [file normalize $::env(HAP_P12_PREPLACE_OUTPUT_SHA)]
set expected_preplace_sha $::env(HAP_P12_PREPLACE_OUTPUT_SHA256)
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "AltSpreadLogic_high"}]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set max_level5 [expr {
    [info exists ::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)] ?
    $::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS) : 100}]
set contract_variant P2_COHORT16_COL2_12_2
set p5_contract P5_INPUT_HALF_LOCAL_8_8
set post_contract P9_POSTPROCESS_SPLIT_6_4_6
set quantizer3_contract P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
set relief_contract P12_ATTN_REGION1_LOGIC_PLUS_X5Y5
set geometry_prefix p3_
file mkdir $out

set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p12_require_kv {values key expected label} {
    if {![dict exists $values $key] || [dict get $values $key] ne $expected} {
        set actual [expr {[dict exists $values $key] ?
            [dict get $values $key] : "<missing>"}]
        error "$label mismatch: $key expected=$expected actual=$actual"
    }
}

if {![string match "2025.2*" [version -short]]} {
    error "P12 placement requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P12 placement requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P12 production placement requires HAP_JOBS=32"
}
if {![string is integer -strict $max_level5] || $max_level5 < 0 ||
    $max_level5 > 100} {
    error "P12 max Level-5 window count must be in 0..100"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha \
        $expected_preplace_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P12 received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 14 $expected_manifest_sha]
foreach required [list $in_dcp $selector_lib $geometry_lib $p5_lib $post_lib \
        $quantizer3_lib $relief_lib $boundary_lib $p10_proc_lib \
        $place_script $expected_launcher \
        $clock_xdc $io_audit $preplace_output_sha] {
    if {![dict exists $frozen $required]} {
        error "P12 required input absent from manifest: $required"
    }
}
set actual_dcp_sha [hap_p10_sha256 $in_dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P12 DCP identity mismatch"
}

set preplace_outputs [hap_p10_verify_manifest $preplace_output_sha -1 \
    $expected_preplace_sha]
set preplace_dir [file dirname $preplace_output_sha]
set preplace_summary_path [file join $preplace_dir summary.txt]
set preplace_launcher_path [file join $preplace_dir launcher_status.txt]
set preplace_inputs_path [file join $preplace_dir INPUT_SHA256SUMS]
foreach required [list $preplace_summary_path $preplace_launcher_path \
        $preplace_inputs_path] {
    if {![dict exists $preplace_outputs [file normalize $required]]} {
        error "P12 pre-place output manifest is incomplete: $required"
    }
}
set preplace [hap_p10_parse_kv $preplace_summary_path "P12 pre-place summary"]
foreach {key expected} {
    status V5_P10_P12_PRE_PLACE_PASS
    stage V5_P10_P12_PRE_PLACE
    evidence_class READ_ONLY_PRE_PLACE
    input_manifest_entries 14
    provenance_verified 1
    contract_variant P2_COHORT16_COL2_12_2
    p5_contract P5_INPUT_HALF_LOCAL_8_8
    p12_decision_manifest_sha256 1f379a9469cd0d37a81309fcaf303b94a3a43a58de3a32b63ad37cee0cda8c47
    p12_decision_verified 1
    p9_postprocess_contract P9_POSTPROCESS_SPLIT_6_4_6
    p9_quantizer3_contract P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6
    p12_region1_relief_contract P12_ATTN_REGION1_LOGIC_PLUS_X5Y5
    jobs 32
    core_clock_mhz 100
    ddr0_clock_mhz 300
    ddr1_clock_mhz 300
    dsp48e2 5453
    uram288 752
    mlp_kernel_dsp48e2 3072
    projected_slr_dsp48e2 {1862 1781 1810}
    projected_slr_uram288 {224 224 304}
    canonical_pblock_count 11
    geometry_pblock_count 10
    p5_added_pblock_count 2
    p9_postprocess_added_pblock_count 2
    p9_quantizer3_added_pblock_count 1
    p12_region1_relief_added_pblock_count 0
    total_pblock_count 26
    completed_u8_ff 4096
    completed_meta_ff 352
    input_capture_ff 12288
    input_capture_controls 48
    p9_slr0_row_primitives 16044
    p9_center_row_primitives 10696
    p9_slr2_row_primitives 16044
    p9_quantizer3_primitives 11178
    p9_quantizer3_grid_range CLOCKREGION_X2Y5:CLOCKREGION_X3Y6
    p12_region1_relief_primitives 68257
    p12_region1_relief_base_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9
    p12_region1_relief_range CLOCKREGION_X5Y5:CLOCKREGION_X5Y5
    parent_head_ff 6560
    parent_tail_ff 6560
    parent_count_ff 2
    parent_count_physical_ff 2
    parent_count_replica_ff 0
    parent_count_replica_equivalence_ok 1
    parent_pointer_ff 0
    local_clear_shared_upstream_ready_paths 0
    branch_credit_shared_upstream_ready_paths 0
    local_clear_gate_compute_ready_paths 0
    branch_credit_gate_compute_ready_paths 0
    local_clear_down_compute_ready_paths 0
    branch_credit_down_compute_ready_paths 0
    local_clear_input_cache_ready_paths 0
    branch_credit_input_cache_ready_paths 0
    pre_place_drc_errors 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
} {
    hap_p12_require_kv $preplace $key $expected "P12 pre-place summary"
}
hap_p12_require_kv $preplace input_dcp $in_dcp "P12 pre-place summary"
hap_p12_require_kv $preplace input_dcp_sha256 $actual_dcp_sha \
    "P12 pre-place summary"
set preplace_launcher [hap_p10_parse_kv $preplace_launcher_path \
    "P12 pre-place launcher"]
foreach {key expected} {
    status PASS
    vivado_exit_code 0
    input_sha_recheck_exit_code 0
    implementation_commands_run 0
    checkpoint_written 0
    route_eligible 0
    bitstream_generated 0
} {
    hap_p12_require_kv $preplace_launcher $key $expected \
        "P12 pre-place launcher"
}

set preplace_input_entries [hap_p10_verify_manifest $preplace_inputs_path 14 \
    [dict get $preplace_outputs [file normalize $preplace_inputs_path]]]
foreach required [list $in_dcp $selector_lib $geometry_lib $p5_lib $post_lib \
        $quantizer3_lib $relief_lib $boundary_lib $p10_proc_lib $clock_xdc \
        $io_audit] {
    if {![dict exists $preplace_input_entries $required]} {
        error "P12 pre-place lineage is missing: $required"
    }
}

set xdc_text [hap_p10_read_nonempty $clock_xdc "P12 clock XDC"]
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
if {[regexp -nocase -- [format {%s|%s} $forbidden_false_path \
        $forbidden_datapath] $xdc_code]} {
    error "P12 XDC contains a forbidden timing waiver"
}
if {[llength [regexp -all -inline {create_clock[[:space:]]} $xdc_code]] != 3 ||
    [llength [regexp -all -inline {set_input_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_output_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_clock_groups[[:space:]]+-asynchronous} \
        $xdc_code]] != 1} {
    error "P12 XDC command cardinality mismatch"
}

source $selector_lib
source $geometry_lib
source $p5_lib
source $post_lib
source $quantizer3_lib
source $relief_lib
source $boundary_lib
open_checkpoint $in_dcp
read_xdc $clock_xdc
source $io_audit
set pre_boundary [hap_mlp_p8_parent_boundary::audit]
hap_mlp_p8_parent_boundary::write_audit $pre_boundary \
    [file join $out p8_parent_ingress_boundary_pre_place.txt] \
    V5_P10_P12_PARENT_INGRESS_BOUNDARY_PRE_PLACE_PASS
foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P12 clock contract mismatch: $name"
    }
}

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {error "P12 compute-net selector is empty"}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "P12 pre-place compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
}

set base_plan [hap_v5_floorplan::discover $contract_variant]
set projection_root [file dirname \
    [get_property NAME [dict get $base_plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set p5_plan [hap_v5_p5_input_partition::discover $base_plan]
set post_plan [hap_v5_p9_postprocess_partition::discover $base_plan $p5_plan]
set quantizer3_plan [hap_v5_p9_quantizer3_locality::discover \
    $base_plan $p5_plan $post_plan]
set relief_plan [hap_v5_p12_region1_relief::discover $geometry_plan]
foreach spec [hap_v5_floorplan::pblock_specs $base_plan $contract_variant] {
    hap_p10_create_hard_slr_pblock [dict get $spec name] \
        [dict get $spec target] [dict get $base_plan [dict get $spec key]]
}
hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0
hap_v5_p5_input_partition::apply $p5_plan
hap_v5_p9_postprocess_partition::apply $post_plan
hap_v5_p9_quantizer3_locality::apply $quantizer3_plan
hap_v5_p12_region1_relief::apply $relief_plan
set pre_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
    $geometry_plan 1 $geometry_prefix 1 shared \
    [hap_v5_p12_region1_relief::range_overrides $relief_plan]]
set pre_base_delegate_specs [concat \
    [hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix] \
    [list [dict create name [dict get $quantizer3_plan pblock_name] \
        target 1]]]
set pre_base_audit [hap_v5_floorplan::audit_pblock_contract \
    $base_plan 0 $contract_variant $pre_base_delegate_specs]
set pre_p5_audit [hap_v5_p5_input_partition::audit $p5_plan 0]
set pre_post_audit [hap_v5_p9_postprocess_partition::audit $post_plan 0]
set pre_quantizer3_audit [hap_v5_p9_quantizer3_locality::audit \
    $quantizer3_plan 0]
set pre_relief_audit [hap_v5_p12_region1_relief::audit $relief_plan 0]
set pre_pblock_count [llength [get_pblocks -quiet]]
set expected_center_extras [expr {
    [llength [dict get $p5_plan center_base_extras]] +
    [llength [dict get $post_plan center_rows]]}]
report_drc -file [file join $out drc_pre_place.rpt]
set pre_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
set pre_ok [expr {
    [dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    [dict get $base_plan history2_count] == 2 &&
    [dict get $base_plan generic_repack_count] == 0 &&
    [dict get $base_plan projection_weight_capture_ok] == 1 &&
    [dict get $pre_base_audit ok] &&
    [dict get $pre_base_audit pblock_count] == 11 &&
    [dict get $pre_base_audit dsp_coverage] == 5453 &&
    [dict get $pre_base_audit uram_coverage] == 752 &&
    [dict get $pre_base_audit optimizer_extra_count] == $expected_center_extras &&
    [dict get $pre_geometry_audit pblock_count] == 10 &&
    [dict get $pre_p5_audit ok] &&
    [dict get $pre_p5_audit outer_extras] == 0 &&
    [dict get $pre_post_audit ok] &&
    [dict get $pre_post_audit outer_extras] == 0 &&
    [dict get $pre_quantizer3_audit ok] &&
    [dict get $pre_quantizer3_audit missing] == 0 &&
    [dict get $pre_quantizer3_audit extras] == 0 &&
    [dict get $pre_relief_audit ok] &&
    [dict get $pre_relief_audit missing] == 0 &&
    [dict get $pre_boundary ok] &&
    [dict get $pre_boundary parent_count_ff] == 2 &&
    [dict get $pre_boundary parent_count_physical_ff] == 2 &&
    [dict get $pre_boundary parent_count_replica_ff] == 0 &&
    [dict get $pre_boundary parent_count_replica_equivalence_ok] == 1 &&
    $pre_pblock_count == 26 && $pre_drc_errors == 0}]
hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors_pre_place.txt] V5_P10_P12_BASE_SELECTORS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry_pre_place.txt] \
    V5_P10_P12_GEOMETRY_PRE_PLACE_PASS
hap_v5_floorplan::write_pblock_audit $pre_base_audit \
    [file join $out base_pblocks_pre_place.txt] \
    V5_P10_P12_BASE_PBLOCK_PRE_PLACE_PASS
hap_v5_p5_input_partition::write_plan $p5_plan \
    [file join $out p5_input_plan_pre_place.txt] V5_P10_P5_INPUT_PLAN_PASS
hap_v5_p5_input_partition::write_audit $pre_p5_audit \
    [file join $out p5_input_pblocks_pre_place.txt] \
    V5_P10_P5_INPUT_PBLOCK_PRE_PLACE_PASS
hap_v5_p9_postprocess_partition::write_plan $post_plan \
    [file join $out p9_postprocess_plan_pre_place.txt] \
    V5_P10_P9_POSTPROCESS_PLAN_PRE_PLACE_PASS
hap_v5_p9_postprocess_partition::write_audit $pre_post_audit \
    [file join $out p9_postprocess_pblocks_pre_place.txt] \
    V5_P10_P9_POSTPROCESS_PBLOCK_PRE_PLACE_PASS
hap_v5_p9_quantizer3_locality::write_plan $quantizer3_plan \
    [file join $out p9_quantizer3_plan_pre_place.txt] \
    V5_P10_P9_QUANTIZER3_PLAN_PRE_PLACE_PASS
hap_v5_p9_quantizer3_locality::write_audit $pre_quantizer3_audit \
    [file join $out p9_quantizer3_pblock_pre_place.txt] \
    V5_P10_P9_QUANTIZER3_PBLOCK_PRE_PLACE_PASS
hap_v5_p12_region1_relief::write_plan $relief_plan \
    [file join $out p12_region1_relief_plan_pre_place.txt] \
    V5_P10_P12_REGION1_RELIEF_PLAN_PRE_PLACE_PASS
hap_v5_p12_region1_relief::write_audit $pre_relief_audit \
    [file join $out p12_region1_relief_pblock_pre_place.txt] \
    V5_P10_P12_REGION1_RELIEF_PBLOCK_PRE_PLACE_PASS
hap_p10_write_summary $out [list status \
    [expr {$pre_ok ? "V5_P10_P12_PRE_PLACE_IN_PROCESS_PASS" : "FAIL"}] \
    input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
    pre_place_lineage_verified 1 pblock_count $pre_pblock_count \
    base_pblock_count [dict get $pre_base_audit pblock_count] \
    geometry_pblock_count [dict get $pre_geometry_audit pblock_count] \
    p5_pblock_count [dict get $pre_p5_audit pblock_count] \
    p9_postprocess_pblock_count [dict get $pre_post_audit pblock_count] \
    p9_quantizer3_pblock_count 1 \
    p12_region1_relief_added_pblock_count 0 \
    base_pblock_optimizer_extras \
        [dict get $pre_base_audit optimizer_extra_count] \
    expected_center_base_extras $expected_center_extras \
    p5_outer_extras [dict get $pre_p5_audit outer_extras] \
    p9_postprocess_outer_extras [dict get $pre_post_audit outer_extras] \
    p9_quantizer3_missing [dict get $pre_quantizer3_audit missing] \
    p9_quantizer3_extras [dict get $pre_quantizer3_audit extras] \
    p12_region1_relief_missing [dict get $pre_relief_audit missing] \
    p12_region1_relief_range [dict get $relief_plan relief_range] \
    parent_head_ff [dict get $pre_boundary parent_head_ff] \
    parent_tail_ff [dict get $pre_boundary parent_tail_ff] \
    parent_count_ff [dict get $pre_boundary parent_count_ff] \
    parent_count_physical_ff [dict get $pre_boundary parent_count_physical_ff] \
    parent_count_replica_ff [dict get $pre_boundary parent_count_replica_ff] \
    parent_count_replica_equivalence_ok \
        [dict get $pre_boundary parent_count_replica_equivalence_ok] \
    local_clear_shared_upstream_ready_paths \
        [dict get $pre_boundary local_clear_shared_upstream_ready_paths] \
    branch_credit_shared_upstream_ready_paths \
        [dict get $pre_boundary branch_credit_shared_upstream_ready_paths] \
    local_clear_gate_compute_ready_paths \
        [dict get $pre_boundary local_clear_gate_compute_ready_paths] \
    branch_credit_gate_compute_ready_paths \
        [dict get $pre_boundary branch_credit_gate_compute_ready_paths] \
    local_clear_down_compute_ready_paths \
        [dict get $pre_boundary local_clear_down_compute_ready_paths] \
    branch_credit_down_compute_ready_paths \
        [dict get $pre_boundary branch_credit_down_compute_ready_paths] \
    local_clear_input_cache_ready_paths \
        [dict get $pre_boundary local_clear_input_cache_ready_paths] \
    branch_credit_input_cache_ready_paths \
        [dict get $pre_boundary branch_credit_input_cache_ready_paths] \
    pre_place_drc_errors $pre_drc_errors implementation_commands_run 0 \
    checkpoint_written 0 route_eligible 0]
file rename -force [file join $out summary.txt] \
    [file join $out pre_place_gate.txt]
if {!$pre_ok} {error "P12 strict in-process pre-place gate failed"}

place_design -directive $place_directive

set post_compute_nets [get_nets -quiet -hierarchical -filter {
    NAME =~ u_compute/*}]
if {[llength $post_compute_nets] == 0} {
    error "P12 post-place compute-net selector is empty"
}
set compute_none_missing_before 0
foreach net $post_compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        incr compute_none_missing_before
    }
}
set_property CLOCK_BUFFER_TYPE NONE $post_compute_nets
set compute_none_missing_after 0
foreach net $post_compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        incr compute_none_missing_after
    }
}
if {$compute_none_missing_after != 0} {
    error "P12 post-place CLOCK_BUFFER_TYPE NONE reapply failed"
}

set rediscovery_rc [catch {
    set post_base_plan [hap_v5_floorplan::discover $contract_variant]
    set post_projection_root [file dirname \
        [get_property NAME [dict get $post_base_plan projection_array]]]
    set post_geometry_plan [hap_projection_ooc_floorplan::discover \
        $post_projection_root 1]
    set post_p5_plan [hap_v5_p5_input_partition::discover $post_base_plan]
    set placed_post_plan [hap_v5_p9_postprocess_partition::discover \
        $post_base_plan $post_p5_plan]
    set post_quantizer3_plan [hap_v5_p9_quantizer3_locality::discover \
        $post_base_plan $post_p5_plan $placed_post_plan]
    set post_relief_plan [hap_v5_p12_region1_relief::discover \
        $post_geometry_plan]
    set post_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \
        $post_geometry_plan 0 $geometry_prefix 1 shared \
        [hap_v5_p12_region1_relief::range_overrides $post_relief_plan]]
    set post_base_delegate_specs [concat \
        [hap_projection_ooc_floorplan::specs \
            $post_geometry_plan $geometry_prefix] \
        [list [dict create name \
            [dict get $post_quantizer3_plan pblock_name] target 1]]]
    set post_base_audit [hap_v5_floorplan::audit_pblock_contract \
        $post_base_plan 1 $contract_variant $post_base_delegate_specs]
    set post_p5_audit [hap_v5_p5_input_partition::audit $post_p5_plan 1]
    set placed_post_audit [hap_v5_p9_postprocess_partition::audit $placed_post_plan 1]
    set post_quantizer3_audit [hap_v5_p9_quantizer3_locality::audit \
        $post_quantizer3_plan 1]
    set post_relief_audit [hap_v5_p12_region1_relief::audit \
        $post_relief_plan 1]
    set post_geometry_placement \
        [hap_projection_ooc_floorplan::audit_placement $post_geometry_plan]
    set physical [hap_v5_floorplan::physical_metrics \
        $post_base_plan $post_base_audit]
    set post_pblock_count [llength [get_pblocks -quiet]]
    set post_clear [hap_p10_mlp_local_clear_audit 1]
    set post_metadata [hap_p10_metadata_local_write_audit 1]
    set post_capture [hap_p10_mlp_capture_leaf_audit \
        [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s43_s45] 1]
    set post_boundary [hap_mlp_p8_parent_boundary::audit]
    hap_mlp_p8_parent_boundary::write_audit $post_boundary \
        [file join $out p8_parent_ingress_boundary_post_place.txt] \
        V5_P10_P12_PARENT_INGRESS_BOUNDARY_POST_PLACE_PASS
    hap_v5_floorplan::write_discovery $post_base_plan \
        [file join $out selectors_post_place.txt] \
        V5_P10_P12_BASE_SELECTORS_POST_PLACE_PASS
    hap_projection_ooc_floorplan::write_plan $post_geometry_plan \
        [file join $out attention_geometry_post_place.txt] \
        V5_P10_P12_GEOMETRY_POST_PLACE_PASS
    hap_projection_ooc_floorplan::write_placement $post_geometry_placement \
        [file join $out attention_geometry_placement.txt] \
        V5_P10_P12_GEOMETRY_PLACEMENT_PASS
    hap_v5_floorplan::write_pblock_audit $post_base_audit \
        [file join $out base_pblocks_post_place.txt] \
        V5_P10_P12_BASE_PBLOCK_POST_PLACE_PASS
    hap_v5_p5_input_partition::write_plan $post_p5_plan \
        [file join $out p5_input_plan_post_place.txt] \
        V5_P10_P5_INPUT_PLAN_POST_PLACE_PASS
    hap_v5_p5_input_partition::write_audit $post_p5_audit \
        [file join $out p5_input_pblocks_post_place.txt] \
        V5_P10_P5_INPUT_PBLOCK_POST_PLACE_PASS
    hap_v5_p9_postprocess_partition::write_plan $placed_post_plan \
        [file join $out p9_postprocess_plan_post_place.txt] \
        V5_P10_P9_POSTPROCESS_PLAN_POST_PLACE_PASS
    hap_v5_p9_postprocess_partition::write_audit $placed_post_audit \
        [file join $out p9_postprocess_pblocks_post_place.txt] \
        V5_P10_P9_POSTPROCESS_PBLOCK_POST_PLACE_PASS
    hap_v5_p9_quantizer3_locality::write_plan $post_quantizer3_plan \
        [file join $out p9_quantizer3_plan_post_place.txt] \
        V5_P10_P9_QUANTIZER3_PLAN_POST_PLACE_PASS
    hap_v5_p9_quantizer3_locality::write_audit $post_quantizer3_audit \
        [file join $out p9_quantizer3_pblock_post_place.txt] \
        V5_P10_P9_QUANTIZER3_PBLOCK_POST_PLACE_PASS
    hap_v5_p12_region1_relief::write_plan $post_relief_plan \
        [file join $out p12_region1_relief_plan_post_place.txt] \
        V5_P10_P12_REGION1_RELIEF_PLAN_POST_PLACE_PASS
    hap_v5_p12_region1_relief::write_audit $post_relief_audit \
        [file join $out p12_region1_relief_pblock_post_place.txt] \
        V5_P10_P12_REGION1_RELIEF_PBLOCK_POST_PLACE_PASS
} rediscovery_error]
if {$rediscovery_rc != 0} {
    set diagnostic_written [expr {![catch {write_checkpoint -force \
        [file join $out post_place_diagnostic_only.dcp]}]}]
    set clean_error [string map [list "\r" " " "\n" " "] $rediscovery_error]
    hap_p10_write_summary $out [list tool [version -short] \
        stage V5_P10_P12_POST_PLACE_REDISCOVERY flow_mode accept \
        failure_stage post_place_live_rediscovery acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        pre_place_verified 1 post_rediscovery_error $clean_error status FAIL]
    close_design
    error "P12 post-place rediscovery failed: $rediscovery_error"
}

set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_p10_congestion_counts \
    [hap_p10_read_nonempty $congestion_path "P12 congestion report"]]
set level5 [dict get $congestion level5]
set level6 [dict get $congestion level6]
report_drc -file [file join $out drc_post_place.rpt]
set post_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}

set slr_dsp [dict get $physical slr_dsp]
set slr_uram [dict get $physical slr_uram]
set slr_ramb36 [dict get $physical slr_ramb36]
set post_expected_center_extras [expr {
    [llength [dict get $post_p5_plan center_base_extras]] +
    [llength [dict get $placed_post_plan center_rows]]}]
set base_extra_delta [expr {
    [dict get $post_base_audit optimizer_extra_count] -
    $post_expected_center_extras}]
set resource_ok [expr {
    [dict get $post_base_plan total_dsp] == 5453 &&
    [dict get $post_base_plan total_uram] == 752 &&
    [dict get $post_base_plan kernel_dsp] == 3072 &&
    [dict get $post_base_plan history2_count] == 2 &&
    [dict get $post_base_plan generic_repack_count] == 0 &&
    [dict get $post_base_plan projection_weight_capture_ok] == 1}]
set structure_ok [expr {
    [dict get $post_p5_plan contract] eq $p5_contract &&
    [dict get $post_p5_plan completed_u8_ff] >= 4096 &&
    [dict get $post_p5_plan completed_meta_ff] >= 352 &&
    [dict get $post_p5_plan input_capture_ff] >= 12288 &&
    [dict get $post_p5_plan capture_leaf_count] >= 48 &&
    [dict get $post_clear total] == 2 &&
    [dict get $post_clear protected] == 2 &&
    [dict get $post_clear branch0_slr] eq {1 0 0} &&
    [dict get $post_clear branch1_slr] eq {0 0 1} &&
    [dict get $post_clear wrong] == 0 &&
    [dict get $post_metadata protected] == 970 &&
    [dict get $post_metadata leaf_slr_counts] eq \
        {{243 0 0} {0 0 243} {0 242 0} {0 242 0}} &&
    [dict get $post_metadata wrong] == 0 &&
    [dict get $post_capture instances] == 1632 &&
    [dict get $post_capture lut1] == 1632 &&
    [dict get $post_capture branch_slr_counts] eq \
        {{816 0 0} {0 0 816}} &&
    [dict get $post_capture wrong] == 0 &&
    [dict get $post_boundary ok] &&
    [dict get $post_boundary parent_count_ff] == 2 &&
    [dict get $post_boundary parent_count_physical_ff] >= 2 &&
    [dict get $post_boundary parent_count_replica_ff] ==
        [expr {[dict get $post_boundary parent_count_physical_ff] - 2}] &&
    [dict get $post_boundary parent_count_replica_equivalence_ok] == 1 &&
    [dict get $post_boundary local_clear_shared_upstream_ready_paths] == 0 &&
    [dict get $post_boundary branch_credit_shared_upstream_ready_paths] == 0 &&
    [dict get $post_boundary local_clear_gate_compute_ready_paths] == 0 &&
    [dict get $post_boundary branch_credit_gate_compute_ready_paths] == 0 &&
    [dict get $post_boundary local_clear_down_compute_ready_paths] == 0 &&
    [dict get $post_boundary branch_credit_down_compute_ready_paths] == 0 &&
    [dict get $post_boundary local_clear_input_cache_ready_paths] == 0 &&
    [dict get $post_boundary branch_credit_input_cache_ready_paths] == 0 &&
    $compute_none_missing_after == 0}]
set placement_ok [expr {
    [hap_v5_floorplan::physical_ok $post_base_plan $physical] &&
    [dict get $post_base_audit ok] &&
    [dict get $post_base_audit pblock_count] == 11 &&
    [dict get $post_geometry_audit pblock_count] == 10 &&
    [dict get $post_geometry_placement ok] &&
    [dict get $post_p5_audit ok] &&
    [dict get $post_p5_audit center_wrong] == 0 &&
    [dict get $post_p5_audit outer_wrong] == 0 &&
    [dict get $placed_post_audit ok] &&
    [dict get $placed_post_audit center_wrong] == 0 &&
    [dict get $placed_post_audit outer_wrong] == 0 &&
    [dict get $post_quantizer3_audit ok] &&
    [dict get $post_quantizer3_audit wrong] == 0 &&
    [dict get $post_quantizer3_audit unplaced] == 0 &&
    [dict get $post_relief_audit ok] &&
    [dict get $post_relief_audit missing] == 0 &&
    [dict get $post_relief_audit wrong] == 0 &&
    [dict get $post_relief_audit unplaced] == 0 &&
    $post_pblock_count == 26 &&
    [dict get $physical wrong_total] == 0 &&
    [dict get $physical unplaced] == 0 &&
    $slr_dsp eq {1862 1781 1810} &&
    $slr_uram eq {224 224 304}}]
set optimizer_extras_ok [expr {$base_extra_delta >= 0 &&
    $base_extra_delta <= 4096 &&
    [dict get $post_p5_audit outer_extras] >= 0 &&
    [dict get $post_p5_audit outer_extras] <= 4096 &&
    [dict get $placed_post_audit outer_extras] >= 0 &&
    [dict get $placed_post_audit outer_extras] <= 4096}]
set fast_gate_ok [expr {$resource_ok && $structure_ok && $placement_ok &&
    $optimizer_extras_ok && $pre_drc_errors == 0 && $post_drc_errors == 0 &&
    $data_bufg == 0 && $level6 == 0 && $level5 <= $max_level5}]
set fp [open [file join $out post_place_fast_gate.txt] w]
foreach {key value} [list resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
    pre_place_drc_errors $pre_drc_errors \
    post_place_drc_errors $post_drc_errors data_bufg $data_bufg \
    level5_or_higher_windows $level5 level6_or_higher_windows $level6 \
    max_level5_windows $max_level5 fast_gate_ok $fast_gate_ok] {
    puts $fp "$key=$value"
}
close $fp
if {!$fast_gate_ok} {
    set diagnostic_written [expr {![catch {write_checkpoint -force \
        [file join $out post_place_diagnostic_only.dcp]}]}]
    hap_p10_write_summary $out [list tool [version -short] \
        stage V5_P10_P12_POST_PLACE_FAST_GATE flow_mode accept \
        failure_stage post_place_fast_gate acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 14 provenance_verified 1 \
        pre_place_verified 1 p5_contract $p5_contract \
        p9_postprocess_contract $post_contract \
        p9_quantizer3_contract $quantizer3_contract \
        p12_region1_relief_contract $relief_contract \
        place_directive $place_directive jobs $jobs core_clock_mhz 100 \
        ddr0_clock_mhz 300 ddr1_clock_mhz 300 dsp48e2 5453 uram288 752 \
        slr_dsp48e2 $slr_dsp slr_uram288 $slr_uram \
        unplaced_primitives [dict get $physical unplaced] \
        wrong_slr_primitives [dict get $physical wrong_total] \
        p5_center_wrong_slr [dict get $post_p5_audit center_wrong] \
        p5_outer_wrong_slr [dict get $post_p5_audit outer_wrong] \
        p9_postprocess_center_wrong_slr \
            [dict get $placed_post_audit center_wrong] \
        p9_postprocess_outer_wrong_slr \
            [dict get $placed_post_audit outer_wrong] \
        p9_quantizer3_wrong_region [dict get $post_quantizer3_audit wrong] \
        p9_quantizer3_unplaced [dict get $post_quantizer3_audit unplaced] \
        p12_region1_relief_placed [dict get $post_relief_audit relief_placed] \
        p12_region1_relief_wrong [dict get $post_relief_audit wrong] \
        p12_region1_relief_unplaced [dict get $post_relief_audit unplaced] \
        pre_place_drc_errors $pre_drc_errors \
        post_place_drc_errors $post_drc_errors data_bufg $data_bufg \
        congestion_level5_or_higher_windows $level5 \
        congestion_level6_or_higher_windows $level6 \
        resource_ok $resource_ok structure_ok $structure_ok \
        placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
        fast_gate_ok 0 status FAIL]
    close_design
    error "P12 placement rejected by post-place fast gate"
}

report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set fp [open [file join $out timing_post_place.rpt] w]
puts $fp $timing_text
close $fp
report_cdc -details -file [file join $out cdc_post_place.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_place.rpt]
set exceptions_path [file join $out exceptions_coverage_post_place.rpt]
report_exceptions -coverage -file $exceptions_path

set no_clock [hap_p10_check_timing_count $timing_text no_clock]
set unconstrained [hap_p10_check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [hap_p10_check_timing_count $timing_text no_input_delay]
set no_output_delay [hap_p10_check_timing_count $timing_text no_output_delay]
set partial_input_delay [hap_p10_check_timing_count $timing_text \
    partial_input_delay]
set partial_output_delay [hap_p10_check_timing_count $timing_text \
    partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]
set cdc_text [hap_p10_read_nonempty [file join $out cdc_post_place.rpt] \
    "P12 CDC report"]
if {![regexp -line \
        {^[[:space:]]*ID[[:space:]]+Severity[[:space:]]+Count[[:space:]]+Description[[:space:]]*$} \
        $cdc_text]} {
    error "P12 CDC report summary header is missing"
}
set cdc_critical 0
foreach {whole count} [regexp -all -inline -line -nocase \
        {^[^\n]*[[:space:]]Critical[[:space:]]+([1-9][0-9]*)[[:space:]]+[^\n]*$} \
        $cdc_text] {
    incr cdc_critical $count
}
set exception_text [hap_p10_read_nonempty $exceptions_path \
    "P12 exception report"]
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} $exception_text]
set datapath_only_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} $exception_text]
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "P12 timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]
set policy_ok [expr {$post_drc_errors == 0 && $false_path_rows == 0 &&
    $datapath_only_rows == 0 && $data_bufg == 0 && $timing_coverage_ok &&
    $cdc_critical == 0}]
set status [expr {$fast_gate_ok && $policy_ok ?
    "V5_P10_P12_PRODUCTION_PLACE_PASS" : "FAIL"}]
set route_eligible [expr {$status eq "V5_P10_P12_PRODUCTION_PLACE_PASS"}]
if {$route_eligible} {
    write_checkpoint -force [file join $out post_place.dcp]
}

hap_p10_write_summary $out [list tool [version -short] \
    part [dict get $post_base_plan part] top [dict get $post_base_plan top] \
    stage V5_P10_P12_POST_PLACE_ACCEPT flow_mode accept \
    acceptance_evidence $route_eligible route_eligible $route_eligible \
    checkpoint_written $route_eligible input_dcp $in_dcp \
    input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_p10_sha256 $input_sha] \
    input_manifest_entries 14 provenance_verified 1 \
    pre_place_manifest $preplace_output_sha \
    pre_place_manifest_sha256 $expected_preplace_sha \
    pre_place_verified 1 contract_variant $contract_variant \
    p5_contract $p5_contract p9_postprocess_contract $post_contract \
    p9_quantizer3_contract $quantizer3_contract \
    p12_region1_relief_contract $relief_contract \
    place_directive $place_directive jobs $jobs \
    core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    dsp48e2 [dict get $post_base_plan total_dsp] \
    uram288 [dict get $post_base_plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $post_base_plan kernel_dsp] \
    history2_repack_instances [dict get $post_base_plan history2_count] \
    generic_repack_instances [dict get $post_base_plan generic_repack_count] \
    projection_weight_capture_ok \
        [dict get $post_base_plan projection_weight_capture_ok] \
    canonical_pblock_count [dict get $post_base_audit pblock_count] \
    geometry_pblock_count [dict get $post_geometry_audit pblock_count] \
    p5_added_pblock_count [dict get $post_p5_audit pblock_count] \
    p9_postprocess_added_pblock_count \
        [dict get $placed_post_audit pblock_count] \
    p9_quantizer3_added_pblock_count 1 \
    p12_region1_relief_added_pblock_count 0 \
    total_pblock_count $post_pblock_count \
    slr0_dsp48e2 [lindex $slr_dsp 0] \
    slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] \
    slr0_uram288 [lindex $slr_uram 0] \
    slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    slr0_ramb36e2 [lindex $slr_ramb36 0] \
    slr1_ramb36e2 [lindex $slr_ramb36 1] \
    slr2_ramb36e2 [lindex $slr_ramb36 2] \
    unplaced_primitives [dict get $physical unplaced] \
    wrong_slr_primitives [dict get $physical wrong_total] \
    p5_center_wrong_slr [dict get $post_p5_audit center_wrong] \
    p5_outer_wrong_slr [dict get $post_p5_audit outer_wrong] \
    p5_outer_optimizer_extras [dict get $post_p5_audit outer_extras] \
    p9_postprocess_center_wrong_slr \
        [dict get $placed_post_audit center_wrong] \
    p9_postprocess_outer_wrong_slr \
        [dict get $placed_post_audit outer_wrong] \
    p9_postprocess_outer_optimizer_extras \
        [dict get $placed_post_audit outer_extras] \
    p9_slr0_row_primitives \
        [llength [dict get $placed_post_plan slr0_rows]] \
    p9_center_row_primitives \
        [llength [dict get $placed_post_plan center_rows]] \
    p9_slr2_row_primitives \
        [llength [dict get $placed_post_plan slr2_rows]] \
    p9_quantizer3_primitives \
        [dict get $post_quantizer3_plan primitive_count] \
    p9_quantizer3_grid_range [dict get $post_quantizer3_plan grid_range] \
    p9_quantizer3_wrong_region [dict get $post_quantizer3_audit wrong] \
    p9_quantizer3_unplaced [dict get $post_quantizer3_audit unplaced] \
    p12_region1_relief_primitives \
        [dict get $post_relief_plan primitive_count] \
    p12_region1_relief_base_range [dict get $post_relief_plan base_range] \
    p12_region1_relief_range [dict get $post_relief_plan relief_range] \
    p12_region1_relief_placed [dict get $post_relief_audit relief_placed] \
    p12_region1_relief_wrong [dict get $post_relief_audit wrong] \
    p12_region1_relief_unplaced [dict get $post_relief_audit unplaced] \
    base_optimizer_extra_delta $base_extra_delta \
    completed_u8_ff [dict get $post_p5_plan completed_u8_ff] \
    completed_meta_ff [dict get $post_p5_plan completed_meta_ff] \
    input_capture_ff [dict get $post_p5_plan input_capture_ff] \
    input_capture_controls [dict get $post_p5_plan capture_leaf_count] \
    parent_head_ff [dict get $post_boundary parent_head_ff] \
    parent_tail_ff [dict get $post_boundary parent_tail_ff] \
    parent_count_ff [dict get $post_boundary parent_count_ff] \
    parent_count_physical_ff \
        [dict get $post_boundary parent_count_physical_ff] \
    parent_count_replica_ff [dict get $post_boundary parent_count_replica_ff] \
    parent_count_replica_equivalence_ok \
        [dict get $post_boundary parent_count_replica_equivalence_ok] \
    parent_pointer_ff [dict get $post_boundary parent_pointer_ff] \
    local_clear_shared_upstream_ready_paths \
        [dict get $post_boundary local_clear_shared_upstream_ready_paths] \
    branch_credit_shared_upstream_ready_paths \
        [dict get $post_boundary branch_credit_shared_upstream_ready_paths] \
    local_clear_gate_compute_ready_paths \
        [dict get $post_boundary local_clear_gate_compute_ready_paths] \
    branch_credit_gate_compute_ready_paths \
        [dict get $post_boundary branch_credit_gate_compute_ready_paths] \
    local_clear_down_compute_ready_paths \
        [dict get $post_boundary local_clear_down_compute_ready_paths] \
    branch_credit_down_compute_ready_paths \
        [dict get $post_boundary branch_credit_down_compute_ready_paths] \
    local_clear_input_cache_ready_paths \
        [dict get $post_boundary local_clear_input_cache_ready_paths] \
    branch_credit_input_cache_ready_paths \
        [dict get $post_boundary branch_credit_input_cache_ready_paths] \
    compute_clock_buffer_none_missing_before_reapply \
        $compute_none_missing_before \
    compute_clock_buffer_none_missing_after_reapply \
        $compute_none_missing_after \
    pre_place_drc_errors $pre_drc_errors \
    post_place_drc_errors $post_drc_errors \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    congestion_level5_or_higher_windows $level5 \
    congestion_level6_or_higher_windows $level6 \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
    fast_gate_ok $fast_gate_ok policy_ok $policy_ok \
    level5_screen_ok [expr {$level5 <= $max_level5}] \
    level6_congestion_ok [expr {$level6 == 0}] status $status]
close_design
if {!$route_eligible} {error "P12 production post-place policy gate failed"}
