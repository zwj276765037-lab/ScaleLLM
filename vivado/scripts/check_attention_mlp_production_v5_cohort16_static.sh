#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOP="$ROOT/rtl/integration/hap_attention_mlp_resource_top.sv"
MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
BOARD_MANIFEST="$ROOT/vivado/manifests/attention_board_cohort16_sources.list"
BOARD="$ROOT/rtl/attention/hap_attention_board_cohort16_core.sv"
CONTROL="$ROOT/rtl/attention/hap_attention_cohort16_axil_control.sv"
COMPUTE="$ROOT/rtl/attention/hap_attention_compute_cohort16_top.sv"
LOCAL_STORES="$ROOT/rtl/attention/hap_attention_cohort16_local_stores.sv"
QUANTIZER="$ROOT/rtl/attention/hap_robust_a8_quantizer.sv"
ELAB_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_elaboration.sh"
SYNTH_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_synth.sh"
SMOKE_LAUNCHER="$ROOT/vivado/scripts/run_v5_production_top_smoke_xsim.sh"
ELAB_TCL="$ROOT/vivado/scripts/elaborate_attention_mlp_production_v5.tcl"
SYNTH_TCL="$ROOT/vivado/scripts/synth_attention_mlp_production_v5.tcl"
SELECTORS="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
POST_OPT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_post_opt_dcp.tcl"
POST_OPT_LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_post_opt_audit.sh"

fail() {
    printf 'V5_COHORT16_STATIC_CONTRACT_FAIL: %s\n' "$*" >&2
    exit 1
}

require_once() {
    local file="$1" text="$2"
    [[ "$(grep -Fxc -- "$text" "$file")" -eq 1 ]] ||
        fail "missing or duplicate contract in ${file#"$ROOT/"}: $text"
}

require_text() {
    local file="$1" text="$2"
    grep -Fq -- "$text" "$file" ||
        fail "missing contract in ${file#"$ROOT/"}: $text"
}

reject_text() {
    local file="$1" text="$2"
    ! grep -Fq -- "$text" "$file" ||
        fail "forbidden contract in ${file#"$ROOT/"}: $text"
}

require_once "$TOP" '`define HAP_ATTENTION_BOARD_MODULE hap_attention_board_core'
require_once "$TOP" '    `HAP_ATTENTION_BOARD_MODULE u_attention('
require_once "$MANIFEST" \
    'vivado/manifests/attention_mlp_production_v5_sources.list'
require_once "$MANIFEST" \
    'vivado/manifests/attention_board_cohort16_sources.list'
require_once "$BOARD_MANIFEST" \
    'rtl/attention/hap_attention_board_cohort16_core.sv'
require_once "$BOARD_MANIFEST" \
    'rtl/attention/hap_attention_compute_cohort16_top.sv'
require_once "$BOARD_MANIFEST" \
    'rtl/attention/hap_attention_cohort16_local_stores.sv'
require_once "$BOARD_MANIFEST" \
    'rtl/attention/hap_projection_core16x16_w8_reuse.sv'
require_once "$BOARD" "        state_r==ST_ROPE_CMD ? 32'd256 : 32'd6144;"
require_once "$BOARD" "        .group_count(17'd81920), .ddr0_clk(ddr0_clk),"
require_once "$BOARD" \
    '    parameter integer COMMAND_TIMEOUT_CYCLES = 10000000'
require_once "$CONTROL" "    localparam [31:0] ABI_VERSION = 32'h0002_0000;"
require_once "$QUANTIZER" \
    "            saturation_threshold = ({56'd0, code} << 24) -"
require_once "$QUANTIZER" "                ({56'd0, code} << 16);"
reject_text "$QUANTIZER" "{56'd0, code} * 64'd255"
for module in hap_attention_cohort16_query_store \
        hap_attention_cohort16_postprocess_store \
        hap_attention_cohort16_context_store; do
    require_once "$LOCAL_STORES" "module $module ("
done
require_text "$LOCAL_STORES" 'context_mem_region0 [0:4095]'
require_text "$LOCAL_STORES" 'context_mem_region3 [0:4095]'
require_text "$LOCAL_STORES" '(* ram_style = "block" *)'
require_once "$COMPUTE" "    localparam [4:0] ST_CONTEXT_DRAIN = 5'd24;"
require_once "$COMPUTE" \
    '    hap_attention_cohort16_query_store u_query_store ('
require_once "$COMPUTE" \
    '    hap_attention_cohort16_postprocess_store u_postprocess_store ('
require_once "$COMPUTE" \
    '    hap_attention_cohort16_context_store u_context_store ('

for launcher in "$ELAB_LAUNCHER" "$SYNTH_LAUNCHER"; do
    require_once "$launcher" 'export HAP_PRODUCTION_PROFILE=cohort16'
    require_once "$launcher" \
        'export HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core'
    require_once "$launcher" \
        'export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"'
    reject_text "$launcher" \
        'export HAP_PRODUCTION_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_sources.list"'
done

for driver in "$ELAB_TCL" "$SYNTH_TCL"; do
    require_text "$driver" 'attention_mlp_production_v5_cohort16_sources.list'
    require_text "$driver" \
        'HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core'
    require_text "$driver" 'Explicit cohort16 production profile required'
    require_text "$driver" 'hap_attention_board_cohort16_core'
    require_text "$driver" 'hap_attention_compute_cohort16_top'
    require_text "$driver" 'hap_projection_core16x16_w8_reuse'
    require_text "$driver" 'hap_linear_tile_accum_dual_s42'
    require_text "$driver" 'set_msg_config -id {Synth 8-324} -new_severity ERROR'
    require_text "$driver" '[llength $attention_lanes] == 128'
    require_text "$driver" '[llength $attention_dual_accumulators] == 6'
    require_text "$driver" '$attention_local_contexts == 12'
done

require_once "$SMOKE_LAUNCHER" \
    'MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"'
require_text "$SMOKE_LAUNCHER" \
    'HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core'
require_text "$SMOKE_LAUNCHER" 'recursive manifest count ${#manifests[@]} != 4'
require_text "$SMOKE_LAUNCHER" 'recursive leaf-source count ${#sources[@]} != 90'

require_text "$SYNTH_TCL" '$attention_projection_dsp == 2240'
require_text "$SYNTH_TCL" '$attention_array_dsp == 2176'
require_text "$SYNTH_TCL" '$attention_frontend_dsp == 64'
require_text "$SYNTH_TCL" 'attention_projection_ok $attention_projection_ok'

require_text "$SELECTORS" 'hap_attention_board_core'
require_text "$SELECTORS" 'hap_attention_board_cohort16_core'
require_text "$SELECTORS" 'attention_board_variant cohort16'
require_text "$SELECTORS" 'attention_board_variant $attention_board_variant'

for audit in "$POST_OPT_TCL" "$POST_OPT_LAUNCHER"; do
    require_text "$audit" 'attention_cohort16_board_instances'
    require_text "$audit" 'attention_legacy_board_instances'
    require_text "$audit" 'attention_projection16_instances'
    require_text "$audit" 'attention_projection8_instances'
    require_text "$audit" 'attention_lane_instances'
    require_text "$audit" 'attention_dual_accumulator_instances'
    require_text "$audit" 'attention_local_accumulator_contexts'
    require_text "$audit" 'attention_projection_dsp48e2'
    require_text "$audit" 'attention_array_dsp48e2'
    require_text "$audit" 'attention_frontend_dsp48e2'
done

printf '%s\n' \
    V5_COHORT16_STATIC_CONTRACT_PASS \
    production_profile=cohort16 \
    production_attention_board=hap_attention_board_cohort16_core \
    attention_lanes=128 \
    local_dual_accumulators=6 \
    local_accumulator_contexts=12 \
    projection_dsp48e2=2240 \
    attention_weight_groups=81920 \
    tensor_axi256_beats=6144 \
    rope_axi256_beats=256
