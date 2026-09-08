#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT/vivado/manifests/attention_mlp_board_core_v5_sources.list"
WRAPPER="$ROOT/vivado/scripts/create_attention_mlp_vcu118_dual_ddr_v5_bd.tcl"
CONSTRUCTOR="$ROOT/vivado/scripts/create_attention_mlp_vcu118_dual_ddr_bd.tcl"
BD_LAUNCHER="$ROOT/vivado/scripts/run_create_attention_mlp_vcu118_dual_ddr_v5_bd.sh"

declare -A SEEN_MANIFESTS=()
declare -A SEEN_SOURCES=()
declare -a SOURCES=()

fail() {
    printf 'V5_BOARD_STATIC_CONTRACT_FAIL: %s\n' "$*" >&2
    exit 1
}

trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

expand_manifest() {
    local manifest="$1" raw line path rel
    manifest="$(readlink -f "$manifest")"
    [[ "$manifest" == "$ROOT"/* ]] || fail "manifest escapes project root: $manifest"
    [[ -s "$manifest" ]] || fail "missing or empty manifest: $manifest"
    [[ -z "${SEEN_MANIFESTS[$manifest]:-}" ]] || return 0
    SEEN_MANIFESTS[$manifest]=1

    while IFS= read -r raw || [[ -n "$raw" ]]; do
        line="${raw%%#*}"
        line="$(trim "$line")"
        [[ -n "$line" ]] || continue
        [[ "$line" != /* ]] || fail "absolute manifest entry rejected: $line"
        path="$(readlink -m "$ROOT/$line")"
        [[ "$path" == "$ROOT"/* ]] || fail "source escapes project root: $line"
        [[ -s "$path" ]] || fail "missing or empty source: $line"
        if [[ "$line" == *.list ]]; then
            expand_manifest "$path"
            continue
        fi
        rel="${path#"$ROOT/"}"
        [[ -z "${SEEN_SOURCES[$rel]:-}" ]] || fail "duplicate source in V5 closure: $rel"
        SEEN_SOURCES[$rel]=1
        SOURCES+=("$rel")
    done < "$manifest"
}

require_source() {
    [[ -n "${SEEN_SOURCES[$1]:-}" ]] || fail "required V5 source absent: $1"
}

reject_source() {
    [[ -z "${SEEN_SOURCES[$1]:-}" ]] || fail "forbidden V4 source present: $1"
}

require_text() {
    local file="$1" literal="$2"
    grep -Fq -- "$literal" "$file" || fail "missing static contract in ${file#"$ROOT/"}: $literal"
}

reject_text() {
    local file="$1" literal="$2"
    ! grep -Fq -- "$literal" "$file" || \
        fail "forbidden static contract in ${file#"$ROOT/"}: $literal"
}

expand_manifest "$MANIFEST"

for required in \
    rtl/mlp/hap_a8w4_slice8x12_group_s36.sv \
    rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv \
    rtl/mlp/hap_mlp_serial_ddr_command16_v5_s45.sv \
    rtl/mlp/hap_mlp_full_command16_v5_s45.sv \
    rtl/integration/hap_attention_mlp_resource_top.sv \
    rtl/integration/hap_attention_mlp_production_core.sv \
    rtl/integration/hap_attention_mlp_board_core.sv \
    rtl/attention/vcu118_pcie_refclk_ibuf.v \
    rtl/board/hap_v5_reset_gate_xpm.sv \
    rtl/board/hap_v5_dual_async_ready_gate_xpm.sv; do
    require_source "$required"
done

for forbidden in \
    rtl/mlp/hap_a8w4_slice8x16_group_s36.sv \
    rtl/mlp/hap_mlp_shared_dual_slice16x16_s43_s45.sv \
    rtl/mlp/hap_mlp_gate_up_external_scheduler16_q4.sv \
    rtl/mlp/hap_mlp_down_activation_replay16.sv \
    rtl/mlp/hap_mlp_serial_ddr_command16_s45.sv \
    rtl/mlp/hap_mlp_full_command16_s45.sv; do
    reject_source "$forbidden"
done

require_text "$ROOT/rtl/mlp/hap_mlp_full_command16_v5_s45.sv" \
    '`define HAP_MLP_FULL_COMMAND_V5_MODULE hap_mlp_full_command16_v5_s45'
require_text "$ROOT/rtl/mlp/hap_mlp_full_command16_v5_s45.sv" \
    'module `HAP_MLP_FULL_COMMAND_V5_MODULE #('
require_text "$ROOT/rtl/integration/hap_attention_mlp_resource_top.sv" \
    'hap_mlp_full_command16_s45 u_mlp('

require_text "$WRAPPER" 'set ::env(HAP_BOARD_PROFILE) V5_FULL_BOARD'
require_text "$WRAPPER" 'set_param general.maxThreads $jobs'
require_text "$WRAPPER" 'V5 board project creation requires HAP_JOBS=32'
require_text "$WRAPPER" 'attention_mlp_board_core_v5_sources.list'
require_text "$WRAPPER" 'HAP_BOARD_BUILD'
require_text "$WRAPPER" 'HAP_BOARD_V5'
require_text "$WRAPPER" \
    'HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s45'
require_text "$WRAPPER" 'set ::env(HAP_BOARD_CORE_CLK_MHZ) 100.0'
require_text "$WRAPPER" 'set ::env(HAP_BOARD_DDR_UI_CLK_HZ) 300000000'
require_text "$BD_LAUNCHER" 'export HAP_JOBS="${HAP_JOBS:-32}"'
require_text "$BD_LAUNCHER" '"$HAP_JOBS" == 32'
require_text "$BD_LAUNCHER" \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'"
require_text "$BD_LAUNCHER" \
    'another batch Vivado is active; V5 board project not created:'
require_text "$BD_LAUNCHER" '[[ ! -e "$PROJECT_DIR" ]]'
require_text "$ROOT/rtl/integration/hap_attention_mlp_board_core.sv" \
    'FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA'
require_text "$ROOT/rtl/attention/hap_attention_board_cohort16_core.sv" \
    'FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA'

require_text "$CONSTRUCTOR" 'set strict_v5 [expr {$board_profile eq "V5_FULL_BOARD"}]'
require_text "$CONSTRUCTOR" 'setcfg rst_core C_EXT_RESET_HIGH 0'
require_text "$CONSTRUCTOR" 'setcfg rst_ddr0 C_EXT_RESET_HIGH 0'
require_text "$CONSTRUCTOR" 'setcfg rst_ddr1 C_EXT_RESET_HIGH 0'
require_text "$CONSTRUCTOR" 'pl_link_cap_max_link_speed 8.0_GT/s'
require_text "$CONSTRUCTOR" 'axi_data_width 256_bit'
require_text "$CONSTRUCTOR" 'V5 construction refuses the preserved V4 project directory'
require_text "$CONSTRUCTOR" 'V5 reset gate module substitution rejected'
require_text "$CONSTRUCTOR" 'set d0ready [create_mig_ready ddr0 $d0cal $d0ui_sync_rst]'
require_text "$CONSTRUCTOR" 'set d1ready [create_mig_ready ddr1 $d1cal $d1ui_sync_rst]'
require_text "$CONSTRUCTOR" 'V5 core clock must be exactly 100.0 MHz'
require_text "$CONSTRUCTOR" 'V5 DDR UI clocks must be exactly 300000000 Hz'
require_text "$CONSTRUCTOR" 'proc assign_v5_address_map {}'
require_text "$CONSTRUCTOR" \
    'assign_bd_address -offset 0x80000000 -range 0x80000000'
require_text "$CONSTRUCTOR" \
    'require_bd_address_mapping "V5 XDMA DDR1" $host_data ddr4_1'
require_text "$CONSTRUCTOR" \
    'require_bd_address_mapping "V5 core weight DDR1" $core_weight1 ddr4_1'
require_text "$CONSTRUCTOR" \
    'assign_bd_address -offset 0x00000000 -range 0x00001000'
[[ "$(grep -Fc -- 'C0.DDR4_InputClockPeriod 4000' "$CONSTRUCTOR")" -eq 3 ]] ||
    fail 'V5 constructor must set both 250 MHz MIG references and verify 4000 ps'
reject_text "$CONSTRUCTOR" 'C0.DDR4_InputClockPeriod 3332'
[[ "$(grep -Fc -- 'C0.DDR4_TimePeriod 833' "$CONSTRUCTOR")" -eq 3 ]] ||
    fail 'V5 constructor must set both DDR rates and verify an 833 ps period'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'set expected_project attention_mlp_vcu118_v5_dual_ddr'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'error "Wrong V5 board top: [get_property TOP [current_fileset]]"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'V4 source leaked into V5 full-board project'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'V5 DDR0 downstream reset'
[[ "$(grep -Fc -- \
    'require_v5_bd_cfg_number $mig C0.DDR4_InputClockPeriod 4000' \
    "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl")" -eq 1 ]] ||
    fail 'V5 bitstream gate must verify the 4000 ps external MIG reference'
reject_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'C0.DDR4_InputClockPeriod 3332'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_bd_cfg_number $mig C0.DDR4_TimePeriod 833'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'error "V5 board core clock contract is not 100/300/300 MHz"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_same_bd_net "V5 DDR0 300 MHz UI clock"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_same_bd_net "V5 DDR1 300 MHz UI clock"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'proc require_v5_bd_address_mapping {label intf_pin target_token'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_bd_address_mapping "V5 XDMA DDR0"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_bd_address_mapping "V5 XDMA DDR1"'
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'require_v5_bd_address_mapping "V5 core tensor DDR0"'

BOARD_GATE="$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
BITSTREAM_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_bitstream.sh"
BUILD_TCL="$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
AUDIT_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_post_route_audit.sh"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
APPLY="$ROOT/vivado/scripts/apply_attention_mlp_vcu118_v5_floorplan.tcl"
PROVENANCE_LIB="$ROOT/vivado/scripts/v5_board_build_provenance.sh"
PROVENANCE_TEST="$ROOT/vivado/scripts/test_v5_board_build_provenance.sh"
BITSTREAM_PROVENANCE_TEST="$ROOT/vivado/scripts/test_attention_mlp_vcu118_v5_bitstream_provenance.sh"
AUDIT_PROVENANCE_TEST="$ROOT/vivado/scripts/test_attention_mlp_vcu118_v5_post_route_audit_provenance.sh"
BUFG_TOPOLOGY_TEST=\
"$ROOT/vivado/scripts/test_attention_mlp_vcu118_v5_bufg_topology_static.tcl"
for required_file in "$BOARD_GATE" "$BITSTREAM_LAUNCHER" \
        "$AUDIT_TCL" "$AUDIT_LAUNCHER" "$SELECTOR_LIB" "$APPLY" \
        "$PROVENANCE_LIB" "$PROVENANCE_TEST" \
        "$BITSTREAM_PROVENANCE_TEST" "$AUDIT_PROVENANCE_TEST" \
        "$BUFG_TOPOLOGY_TEST"; do
    [[ -s "$required_file" ]] || fail "missing board gate source: $required_file"
done
BUFG_TEST_OUTPUT="$(tclsh "$BUFG_TOPOLOGY_TEST")" || \
    fail 'BUFG/BUFG_GT_SYNC Tcl-only topology regression failed'
[[ "$(grep -Fxc 'V5_BOARD_BUFG_TOPOLOGY_STATIC_TEST_PASS' \
    <<< "$BUFG_TEST_OUTPUT")" -eq 1 ]] || \
    fail 'BUFG/BUFG_GT_SYNC Tcl-only topology PASS marker is not unique'
[[ "$(grep -Fxc 'negative_cases=8' <<< "$BUFG_TEST_OUTPUT")" -eq 1 ]] || \
    fail 'BUFG/BUFG_GT_SYNC negative-case count drifted'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected bufg_gt_without_o_clock bufg_gt_data'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected cesync_to_wrong_leaf bufg_gt_sync_bad_connections'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected clrsync_without_leaf bufg_gt_sync_bad_connections'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected gt_sync_clk_without_clock bufg_gt_sync_clk_without_clock'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected production_core_gt_sync production_core_bufg_gt_sync'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected gt_sync_unknown_pin bufg_gt_sync_bad_connections'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_rejected similar_name_is_not_excluded real_bufg_bad_connections'
require_text "$BUFG_TOPOLOGY_TEST" \
    'require_field $missing_sync bufg_gt_sync_total 0 missing_gt_sync'
require_text "$BOARD_GATE" 'v5_production_floorplan_selectors.tcl'
require_text "$BOARD_GATE" 'set clear_endpoints {}'
require_text "$BOARD_GATE" 'lsearch -exact $endpoint_cells $cell'
require_text "$BOARD_GATE" 'set central_nets [lsort -dictionary -unique '
require_text "$BOARD_GATE" 'get_pins -quiet -leaf -of_objects $central_nets'
require_text "$BOARD_GATE" 'set direct_branch_state {}'
require_text "$BOARD_GATE" \
    'central_branch_endpoints [llength $clear_endpoints]'
require_text "$BOARD_GATE" \
    'central_direct_branch_state [llength $direct_branch_state]'
reject_text "$BOARD_GATE" 'central_branch_endpoints 2 \'
reject_text "$BOARD_GATE" 'central_direct_branch_state 0]'
require_text "$BOARD_GATE" 'proc hap_v5_board_gate::cdc_critical {path}'
require_text "$BOARD_GATE" 'proc hap_v5_board_gate::timing_count {text category}'
require_text "$BOARD_GATE" '$timing_text unconstrained_internal_endpoints'
require_text "$BOARD_GATE" '$wns >= 0.0 && $whs >= 0.0 && $timing_coverage_ok &&'
require_text "$BOARD_GATE" 'timing_coverage_ok $timing_coverage_ok'
require_text "$BOARD_GATE" 'proc hap_v5_board_gate::bufg_topology {production_core}'
require_text "$BOARD_GATE" 'proc hap_v5_board_gate::clocks_through_pin {pin}'
require_text "$BOARD_GATE" 'if {$ref eq "BUFG_GT_SYNC"}'
require_text "$BOARD_GATE" 'set primitive_pins [lsort -dictionary -unique '
require_text "$BOARD_GATE" 'REF_PIN_NAME == $ref_pin && DIRECTION == $direction'
require_text "$BOARD_GATE" 'get_nets -quiet -segments -of_objects [list $output_pin]'
require_text "$BOARD_GATE" 'get_pins -quiet -leaf '
require_text "$BOARD_GATE" '$load_ref ne "BUFG_GT" ||'
require_text "$BOARD_GATE" '$load_ref_pin ne $expected_load_pin'
require_text "$BOARD_GATE" 'set bufg_gt_sync_topology_ok [expr {'
require_text "$BOARD_GATE" '$production_core_bufg_gt_sync == 0}'
require_text "$BOARD_GATE" '$bufg_gt_clock == $bufg_gt_total && $bufg_gt_data == 0 &&'
require_text "$BOARD_GATE" '$drc_errors == 0 && $level6 == 0 && $bufg_topology_ok &&'
require_text "$BOARD_GATE" 'bufg_topology_post_route.txt'
require_text "$BOARD_GATE" 'CDC report summary header is missing'
require_text "$BOARD_GATE" 'Congestion report is missing its placer section'
require_text "$BOARD_GATE" 'Malformed Global/Long congestion row:'
require_text "$BOARD_GATE" \
    'Congestion report has neither Global/Long rows nor a clean marker'
require_text "$BOARD_GATE" \
    'set floorplan_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]'
require_text "$BOARD_GATE" 'projection_core16x16_w8_reuse_ooc_floorplan.tcl'
require_text "$BOARD_GATE" 'v5_production_p5_input_partition_floorplan.tcl'
require_text "$BOARD_GATE" \
    'v5_production_p6_postprocess_partition_floorplan.tcl'
require_text "$BOARD_GATE" \
    '[hap_projection_ooc_floorplan::discover $projection_root 1]'
require_text "$BOARD_GATE" \
    'set p5_plan [hap_v5_p5_input_partition::discover $floorplan_plan]'
require_text "$BOARD_GATE" \
    'set p5_pblock_audit [hap_v5_p5_input_partition::audit $p5_plan 1]'
require_text "$BOARD_GATE" \
    'set p6_plan [hap_v5_p6_postprocess_partition::discover \'
require_text "$BOARD_GATE" \
    '[hap_v5_p6_postprocess_partition::audit $p6_plan 1]'
require_text "$BOARD_GATE" \
    '[hap_v5_floorplan::physical_ok $floorplan_plan $floorplan_metrics]'
require_text "$BOARD_GATE" 'selectors_post_route.txt'
require_text "$BOARD_GATE" 'attention_geometry_post_route.txt'
require_text "$BOARD_GATE" 'attention_geometry_placement_post_route.txt'
require_text "$BOARD_GATE" 'base_pblocks_post_route.txt'
require_text "$BOARD_GATE" 'p5_input_plan_post_route.txt'
require_text "$BOARD_GATE" 'p5_input_pblocks_post_route.txt'
require_text "$BOARD_GATE" 'p6_postprocess_plan_post_route.txt'
require_text "$BOARD_GATE" 'p6_postprocess_pblocks_post_route.txt'
require_text "$BOARD_GATE" '$cdc_critical == 0 && $floorplan_contract_ok &&'
require_text "$BOARD_GATE" \
    '$projection_weight_capture_ok && $architecture_boundary_ok &&'
require_text "$BOARD_GATE" '$exception_policy_ok ?'
require_text "$BOARD_GATE" \
    'projection_weight_capture_ok $projection_weight_capture_ok'
require_text "$BOARD_GATE" 'weight_data_capture_contract 32x256'
require_text "$BOARD_GATE" 'weight_meta_capture_contract 2x256'
require_text "$BOARD_GATE" 'weight_group_capture_contract 2x7'
require_text "$BOARD_GATE" 'cdc_critical $cdc_critical'
require_text "$BOARD_GATE" 'live_post_route_rediscovery_ok 1'
require_text "$BOARD_GATE" 'pblock_count [llength [get_pblocks -quiet]]'
require_text "$BOARD_GATE" 'canonical_pblock_count [dict get $base_pblock_audit pblock_count]'
require_text "$BOARD_GATE" 'geometry_pblock_count [dict get $geometry_audit pblock_count]'
require_text "$BOARD_GATE" 'p5_added_pblock_count [dict get $p5_pblock_audit pblock_count]'
require_text "$BOARD_GATE" 'p6_added_pblock_count [dict get $p6_pblock_audit pblock_count]'
require_text "$BOARD_GATE" 'pblock_dsp_coverage [dict get $base_pblock_audit dsp_coverage]'
require_text "$BOARD_GATE" 'pblock_uram_coverage [dict get $base_pblock_audit uram_coverage]'
require_text "$BOARD_GATE" \
    'physical_ok $physical_ok floorplan_contract_ok $floorplan_contract_ok'
require_text "$BOARD_GATE" \
    'pblock_optimizer_extra_count '
require_text "$BOARD_GATE" 'outer0_dsp48e2 [dict get $floorplan_plan outer0_dsp]'
require_text "$BOARD_GATE" \
    'p5_contract [dict get $p5_plan contract]'
require_text "$BOARD_GATE" \
    'p6_contract [dict get $p6_plan contract]'
require_text "$BOARD_GATE" \
    'projected_slr_dsp48e2 {1862 1781 1810}'
for literal in \
    'v5_production_p6_postprocess_partition_floorplan.tcl' \
    'set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4' \
    'set p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8' \
    'set region2_variant rowsplit_y5_y6_y6_y8' \
    'set p6_plan [hap_v5_p6_postprocess_partition::discover $plan $p5_plan]' \
    'hap_v5_p6_postprocess_partition::apply $p6_plan' \
    'set p6_audit [hap_v5_p6_postprocess_partition::audit $p6_plan 0]' \
    '[llength [get_pblocks -quiet]] != 27' \
    'v5_board_p6_postprocess_plan_pre_place.txt' \
    'V5_BOARD_P6_POSTPROCESS_PLAN_PRE_PLACE_PASS' \
    'v5_board_p6_postprocess_pblocks_pre_place.txt' \
    'V5_BOARD_P6_POSTPROCESS_PBLOCK_PRE_PLACE_PASS'; do
    require_text "$APPLY" "$literal"
done
for literal in \
    'proc hap_v5_board_gate::mlp_local_clear_audit {}' \
    'proc hap_v5_board_gate::swiglu_local_clear_audit {}' \
    'proc hap_v5_board_gate::metadata_local_write_audit {}' \
    'proc hap_v5_board_gate::mlp_capture_leaf_audit {}' \
    'proc hap_v5_board_gate::require_architecture_boundaries {clear swiglu metadata capture}' \
    'architecture_boundaries_post_route.txt' \
    'swiglu_local_clear_protected_ff' \
    'swiglu_direct_clear_bypass_state' \
    'metadata_local_write_protected_ff' \
    'mlp_capture_leaf_instances' \
    'mlp_capture_leaf_branch_slr_counts' \
    'architecture_boundary_ok $architecture_boundary_ok'; do
    require_text "$BOARD_GATE" "$literal"
done
require_text "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl" \
    'puts $fp "post_route_gate_status=$value"'
require_text "$BITSTREAM_LAUNCHER" \
    'for exact in no_clock_endpoints=0 unconstrained_paths=0 \'
require_text "$AUDIT_LAUNCHER" \
    'for exact in no_clock_endpoints=0 unconstrained_paths=0 \'
for literal in \
    'set ooc_route_artifact [file normalize $::env(HAP_OOC_ROUTE_DIR)]' \
    'HAP_BOARD_INPUT_COUNT 123' \
    'HAP_BOARD_IMMUTABLE_INPUT_COUNT 122' \
    'HAP_BOARD_SOURCE_MANIFEST_COUNT 3' \
    'HAP_BOARD_RTL_SOURCE_COUNT 87' \
    'HAP_BOARD_SOURCE_CLOSURE_COUNT 90' \
    'sha256sum --status -c --strict $path' \
    'ooc_route_input_sha' \
    'ooc_route_output_sha' \
    'status=V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS' \
    'status=V5_P7_ROUTE_FINAL_SELECTORS_PASS' \
    'status=V5_P7_ROUTE_FINAL_GEOMETRY_PASS' \
    'status=V5_P7_ROUTE_FINAL_GEOMETRY_PLACEMENT_PASS' \
    'status=V5_P7_ROUTE_FINAL_BASE_PBLOCKS_PASS' \
    'status=V5_P7_ROUTE_FINAL_INPUT_PLAN_PASS' \
    'status=V5_P7_ROUTE_FINAL_INPUT_PBLOCKS_PASS' \
    'status=V5_P7_ROUTE_FINAL_POSTPROCESS_PLAN_PASS' \
    'status=V5_P7_ROUTE_FINAL_POSTPROCESS_PBLOCKS_PASS' \
    'p5_contract=P5_INPUT_HALF_LOCAL_8_8' \
    'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4' \
    'p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8' \
    'region2_variant=rowsplit_y5_y6_y6_y8' \
    'slr0_dsp48e2=1862' \
    'slr1_dsp48e2=1781' \
    'slr2_dsp48e2=1810' \
    'route_input_manifest_entries=25' \
    'swiglu_local_clear_ff=8' \
    'swiglu_local_clear_protected_ff=8' \
    'swiglu_direct_clear_bypass_state=0' \
    'foreach literal {status=PASS final_exit_code=0 vivado_exit_code=0 \' \
    'puts $fp "ooc_route_authorization_verified=1"' \
    'puts $fp "complete_input_count=123"' \
    'puts $fp "immutable_input_count=122"' \
    'puts $fp "recursive_source_manifest_count=3"' \
    'puts $fp "recursive_rtl_source_count=87"' \
    'puts $fp "recursive_source_closure_count=90"'; do
    require_text "$BUILD_TCL" "$literal"
done
for literal in \
    'set exact_inputs [list $dcp $bitstream $xdc_inventory $audit_tcl' \
    'set frozen_inputs [hap_audit_verify_inputs $input_sha' \
    'expected_input_manifest_sha' \
    'audit_input_manifest_entries=[dict size $frozen_inputs]' \
    'audit_input_manifests_verified=1'; do
    require_text "$AUDIT_TCL" "$literal"
done
for literal in \
    'V5_BOARD_BITSTREAM_PROVENANCE_TEST_PASS' \
    'manifest_self_synchronized_mutation_negative=PASS' \
    'p7_route_to_open_project_positive=PASS' \
    'immutable_post_tool_mutation_negative=PASS' \
    'failure_dynamic_archive=PASS'; do
    require_text "$BITSTREAM_PROVENANCE_TEST" "$literal"
done
for literal in \
    'V5_BOARD_AUDIT_PROVENANCE_TEST_PASS' \
    'launcher_failure_dynamic_archive=PASS' \
    'tcl_mutated_input_negative=PASS' \
    'tcl_exact_path_negative=PASS'; do
    require_text "$AUDIT_PROVENANCE_TEST" "$literal"
done
require_text "$AUDIT_TCL" 'puts $fp "post_route_gate_status=$value"'
for literal in \
    'set complete_inputs [hap_board_verify_sha_manifest' \
    'set immutable_inputs [hap_board_verify_sha_manifest' \
    'expected_input_manifest_sha' \
    'expected_immutable_input_manifest_sha' \
    'complete-minus-project immutable input' \
    'source [file join $script_dir attention_mlp_vcu118_v5_post_route_gate.tcl]' \
    'open_project $project_file'; do
    require_text "$BUILD_TCL" "$literal"
done
for literal in \
    'HAP_INPUT_MANIFEST_SHA256' \
    'HAP_IMMUTABLE_INPUT_MANIFEST_SHA256' \
    'IMMUTABLE_INPUT_SHA256SUMS' \
    'immutable_input_postcheck=1' \
    'project_file_postcheck_exempt=1' \
    'archive_board_outputs'; do
    require_text "$BITSTREAM_LAUNCHER" "$literal"
done
for launcher in "$BITSTREAM_LAUNCHER" "$AUDIT_LAUNCHER"; do
    require_text "$launcher" 'attention_geometry_post_route.txt'
    require_text "$launcher" 'attention_geometry_placement_post_route.txt'
    require_text "$launcher" 'base_pblocks_post_route.txt'
    require_text "$launcher" 'p5_input_plan_post_route.txt'
    require_text "$launcher" 'p5_input_pblocks_post_route.txt'
    require_text "$launcher" 'p6_postprocess_plan_post_route.txt'
    require_text "$launcher" 'p6_postprocess_pblocks_post_route.txt'
    require_text "$launcher" 'architecture_boundaries_post_route.txt'
    require_text "$launcher" 'mlp_local_clear_protected_ff=2'
    require_text "$launcher" 'swiglu_local_clear_ff=8'
    require_text "$launcher" 'swiglu_local_clear_protected_ff=8'
    require_text "$launcher" 'swiglu_direct_clear_bypass_state=0'
    require_text "$launcher" 'metadata_local_write_protected_ff=970'
    require_text "$launcher" 'mlp_capture_leaf_instances=1632'
    require_text "$launcher" \
        "'mlp_capture_leaf_branch_slr_counts={816 0 0} {0 0 816}'"
    require_text "$launcher" 'architecture_boundary_ok=1'
    require_text "$launcher" \
        'status=V5_BOARD_ARCHITECTURE_BOUNDARIES_PASS'
    require_text "$launcher" "grep -Fqx 'cdc_critical=0'"
    require_text "$launcher" \
        "grep -Fqx 'base_contract_variant=P2_COHORT16_COL2_12_2'"
    require_text "$launcher" \
        "grep -Fqx 'pblock_contract_variant=P2_COHORT16_COL2_12_2'"
    require_text "$launcher" "grep -Fqx 'p5_contract=P5_INPUT_HALF_LOCAL_8_8'"
    require_text "$launcher" \
        "grep -Fqx 'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'"
    require_text "$launcher" \
        "grep -Fqx 'p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8'"
    require_text "$launcher" \
        "grep -Fqx 'region2_variant=rowsplit_y5_y6_y6_y8'"
    require_text "$launcher" "grep -Fqx 'pblock_count=27'"
    require_text "$launcher" "grep -Fqx 'total_pblock_count=27'"
    require_text "$launcher" "grep -Fqx 'physical_placement_ok=1'"
    require_text "$launcher" "grep -Fqx 'pblock_dsp_coverage=5453'"
    require_text "$launcher" "grep -Fqx 'pblock_uram_coverage=752'"
    require_text "$launcher" "grep -c '^status='"
    require_text "$launcher" 'status=V5_BOARD_POST_ROUTE_SELECTORS_PASS'
    require_text "$launcher" 'status=V5_BOARD_POST_ROUTE_GEOMETRY_PASS'
    require_text "$launcher" \
        'status=V5_BOARD_POST_ROUTE_GEOMETRY_PLACEMENT_PASS'
    require_text "$launcher" 'status=V5_BOARD_POST_ROUTE_BASE_PBLOCKS_PASS'
    require_text "$launcher" 'status=V5_BOARD_POST_ROUTE_P5_INPUT_PLAN_PASS'
    require_text "$launcher" \
        'status=V5_BOARD_POST_ROUTE_P5_INPUT_PBLOCKS_PASS'
    require_text "$launcher" \
        'status=V5_BOARD_POST_ROUTE_P6_POSTPROCESS_PLAN_PASS'
    require_text "$launcher" \
        'status=V5_BOARD_POST_ROUTE_P6_POSTPROCESS_PBLOCKS_PASS'
    require_text "$launcher" 'slr1_dsp48e2=1781'
    require_text "$launcher" 'bufg_topology_post_route.txt'
    require_text "$launcher" "grep -Fqx 'real_bufg_bad_connections=0'"
    require_text "$launcher" "grep -Fqx 'bufg_gt_data=0'"
    require_text "$launcher" \
        "grep -Fqx 'bufg_gt_sync_clk_without_clock=0'"
    require_text "$launcher" \
        "grep -Fqx 'bufg_gt_sync_bad_connections=0'"
    require_text "$launcher" \
        "grep -Fqx 'production_core_bufg_gt_sync=0'"
    require_text "$launcher" "grep -Fqx 'bufg_partition_ok=1'"
    require_text "$launcher" \
        "grep -Fqx 'bufg_gt_sync_topology_ok=1'"
    require_text "$launcher" "grep -Fqx 'bufg_topology_ok=1'"
    require_text "$launcher" 'check_bufg_summary_schema() {'
    require_text "$launcher" \
        'value["bufg_family_total"] !='
    require_text "$launcher" \
        'value["real_bufg_total"] + value["bufg_gt_sync_total"]'
    require_text "$launcher" \
        'value["bufg_gt_sync_cesync_leaf_loads"] <'
    require_text "$launcher" \
        'value["bufg_gt_sync_clrsync_leaf_loads"] <'
    require_text "$launcher" 'check_bufg_summary_schema "$HAP_'
done
require_text "$AUDIT_LAUNCHER" 'v5_production_floorplan_selectors.tcl'
for literal in \
    'usage: %s V5_PRODUCTION_OOC_ROUTE_PASS_ARTIFACT_DIR' \
    'hap_v5_verify_ooc_route_artifact "$HAP_OOC_ROUTE_DIR"' \
    'hap_v5_expand_source_manifest "$ROOT" "$BOARD_SOURCE_MANIFEST"' \
    '"${#SOURCE_MANIFESTS[@]}" -eq 3' \
    '"${#RTL_SOURCES[@]}" -eq 87' \
    '"${#SOURCE_CLOSURE[@]}" -eq 90' \
    '"${#INPUTS[@]}" -eq 123' \
    '"$HAP_BOARD_IMMUTABLE_INPUT_COUNT" -eq 122' \
    'RECURSIVE_SOURCE_SHA256SUMS' \
    'OOC_ROUTE_AUTHORIZATION_SHA256SUMS' \
    'sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS"' \
    'vivado_rc=90' 'vivado_rc=91' 'vivado_rc=92' \
    'immutable_input_postcheck=' \
    'immutable_input_manifest_sha_match=' \
    'recursive_source_post_build_sha_verified=' \
    'ooc_route_authorization_post_build_verified=' \
    "grep -Fqx 'ooc_route_authorization_verified=1'" \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'another batch Vivado is active; V5 board bitstream not started:' \
    'exit 75' \
    '[[ ! -e "$HAP_REPORT_DIR" ]]'; do
    require_text "$BITSTREAM_LAUNCHER" "$literal"
done
BITSTREAM_FRONT_ORDER="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$BITSTREAM_LAUNCHER")"
case "$BITSTREAM_FRONT_ORDER" in
    *'[[ ! -e "$HAP_REPORT_DIR" ]]'*\
"'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'"*\
'hap_v5_verify_ooc_route_artifact "$HAP_OOC_ROUTE_DIR"'*) ;;
    *) fail 'bitstream freshness/batch guards are not ahead of route verification' ;;
esac
for literal in \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'another batch Vivado is active; independent V5 audit not started:' \
    'exit 75' \
    '[[ ! -e "$HAP_AUDIT_DIR" ]]'; do
    require_text "$AUDIT_LAUNCHER" "$literal"
done
for literal in \
    'sha256sum -c --strict \' \
    'input_sha_postcheck=1' \
    'vivado_rc=90' \
    "grep -Fqx 'final_exit_code=0'" \
    "grep -Fqx 'input_sha_postcheck=1'" \
    '"$HAP_AUDIT_DIR/launcher_status.txt"' \
    '"$HAP_AUDIT_DIR/INPUT_SHA256SUMS"' \
    'archive_audit_outputs'; do
    require_text "$AUDIT_LAUNCHER" "$literal"
done
AUDIT_FRONT_ORDER="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$AUDIT_LAUNCHER")"
case "$AUDIT_FRONT_ORDER" in
    *'[[ ! -e "$HAP_AUDIT_DIR" ]]'*\
"'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'"*\
'export HAP_DCP='*) ;;
    *) fail 'independent audit freshness/batch guards are not first' ;;
esac
for literal in \
    'hap_v5_read_sha_manifest_paths_dynamic "$output_sha"' \
    'hap_v5_read_path_list "$input_files" 25' \
    'hap_v5_read_sha_manifest_paths "$input_sha" 25' \
    'complete OOC route output manifest' \
    'hap_v5_read_sha_manifest_paths "$place_dir/INPUT_SHA256SUMS" 11' \
    'hap_v5_read_sha_manifest_paths_dynamic \' \
    '"$place_dir/OUTPUT_SHA256SUMS" place_output_paths' \
    'place_output_manifest_entries="${#place_output_paths[@]}"' \
    'summary_place_output_manifest_entries' \
    'place_output_manifest_sha256' \
    'summary_place_output_manifest_sha' \
    'OOC route/place OUTPUT_SHA256SUMS self-SHA mismatch:' \
    'place_input_manifest_sha256' \
    'summary_place_input_manifest_sha' \
    'OOC route/place INPUT_SHA256SUMS self-SHA mismatch:' \
    'route_input_manifest_sha256' \
    'summary_route_input_manifest_sha' \
    'OOC route INPUT_SHA256SUMS self-SHA mismatch:' \
    '! -name OUTPUT_SHA256SUMS' \
    'hap_v5_require_same_path_set expected_place_output_paths \' \
    'place_output_paths "complete place output SHA manifest"' \
    'hap_v5_require_same_path_set expected_inputs route_input_paths' \
    'hap_v5_require_path_member place_output_paths "$input_dcp"' \
    'status=V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS' \
    'status=V5_P7_ROUTE_FINAL_SELECTORS_PASS' \
    'status=V5_P7_ROUTE_FINAL_GEOMETRY_PASS' \
    'status=V5_P7_ROUTE_FINAL_GEOMETRY_PLACEMENT_PASS' \
    'status=V5_P7_ROUTE_FINAL_BASE_PBLOCKS_PASS' \
    'status=V5_P7_ROUTE_FINAL_INPUT_PLAN_PASS' \
    'status=V5_P7_ROUTE_FINAL_INPUT_PBLOCKS_PASS' \
    'status=V5_P7_ROUTE_FINAL_POSTPROCESS_PLAN_PASS' \
    'status=V5_P7_ROUTE_FINAL_POSTPROCESS_PBLOCKS_PASS' \
    'architecture_boundaries_input.txt' \
    'architecture_boundaries_post_route.txt' \
    'V5_P7_ROUTE_INPUT_BOUNDARIES_PASS' \
    'V5_P7_ROUTE_FINAL_BOUNDARIES_PASS' \
    'place_input_manifest_entries=11' \
    'architecture_boundary_ok=1' \
    'bitstream_generated=0' \
    'find "$route_dir" -maxdepth 1 -type f -name '\''*.bit'\'''; do
    require_text "$PROVENANCE_LIB" "$literal"
done
for literal in \
    'V5_BOARD_BUILD_PROVENANCE_TEST_PASS' \
    'assert_rejected summary_only' \
    'assert_rejected bad_status' \
    'assert_rejected negative_wns' \
    'assert_rejected mutated_output' \
    'assert_rejected bad_architecture_boundaries' \
    'assert_rejected bitstream_in_ooc_route' \
    'assert_rejected untracked_route_output' \
    'assert_rejected untracked_place_output' \
    'assert_rejected missing_place_manifest_member' \
    'assert_rejected bad_place_manifest_self_sha' \
    'assert_rejected bad_place_input_manifest_self_sha' \
    'assert_rejected bad_route_input_manifest_self_sha'; do
    require_text "$PROVENANCE_TEST" "$literal"
done
reject_text "$BOARD_GATE" 'legacy10'
reject_text "$BOARD_GATE" '$floorplan_plan 0 P2_COHORT16_COL2_12_2'
reject_text "$PROVENANCE_LIB" 'place_output_manifest_entries=16'
reject_text "$PROVENANCE_LIB" \
    'hap_v5_read_sha_manifest_paths "$place_dir/OUTPUT_SHA256SUMS" 16'
reject_text "$BOARD_GATE" \
    'get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}'
reject_text "$BOARD_GATE" 'if {$ref ne "BUFG_GT_SYNC"}'
for file in "$BOARD_GATE" "$BUILD_TCL" "$BITSTREAM_LAUNCHER" \
        "$AUDIT_TCL" "$AUDIT_LAUNCHER" "$APPLY" "$PROVENANCE_LIB"; do
    for old in \
        'P0_11' 'move0=12' 'center_lanes=101' 'move2=15' \
        'moved_lanes_slr0=12' 'center_lanes_slr1=101' \
        'moved_lanes_slr2=15' 'planned_slr0_dsp=1794' \
        'planned_slr1_dsp=1878' 'planned_slr0_dsp48e2=1794' \
        'planned_slr1_dsp48e2=1878'; do
        reject_text "$file" "$old"
    done
done

BUILD_ORDER="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' "$BUILD_TCL")"
case "$BUILD_ORDER" in
    *'set complete_inputs [hap_board_verify_sha_manifest'*\
'source [file join $script_dir attention_mlp_vcu118_v5_post_route_gate.tcl]'*\
'open_project $project_file'*) ;;
    *) fail 'full-board input SHA/source/open_project order is invalid' ;;
esac
case "$BUILD_ORDER" in
    *'set initial [hap_v5_board_gate::audit $out $xdc_inventory]'*\
'write_bitstream -force $delivered_bit'*) ;;
    *) fail 'bitstream write is not ordered after the first full board gate' ;;
esac
AUDIT_ORDER="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' "$AUDIT_TCL")"
case "$AUDIT_ORDER" in
    *'set frozen_inputs [hap_audit_verify_inputs $input_sha'*\
'open_checkpoint $dcp'*\
'set result [hap_v5_board_gate::audit $out $xdc_inventory $bitstream]'*) ;;
    *) fail 'independent input SHA gate/checkpoint/full-board order is invalid' ;;
esac

printf 'V5_BOARD_STATIC_CONTRACT_PASS\n'
printf 'manifest=%s\n' "${MANIFEST#"$ROOT/"}"
printf 'manifest_count=%d\n' "${#SEEN_MANIFESTS[@]}"
printf 'source_count=%d\n' "${#SOURCES[@]}"
printf '%s\n' "${SOURCES[@]}" | LC_ALL=C sort | sha256sum | \
    awk '{print "flattened_source_names_sha256=" $1}'
sha256sum "${SOURCES[@]/#/$ROOT/}" | sha256sum | \
    awk '{print "source_content_set_sha256=" $1}'
