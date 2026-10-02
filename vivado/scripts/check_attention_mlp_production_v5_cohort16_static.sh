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
MLP_QUANTIZER="$ROOT/rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv"
COL_SHARD="$ROOT/rtl/attention/hap_a8w8_col_shard_s42.sv"
CENTER_SHARD="$ROOT/rtl/attention/hap_a8w8_col_shard_center12_s42.sv"
DUAL_ACCUM="$ROOT/rtl/attention/hap_linear_tile_accum_dual_s42.sv"
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
    "    localparam [32:0] SCALE_EXACT_LIMIT_Q16 = 33'd4261478400;"
require_once "$QUANTIZER" \
    "                    low_now = \$signed({raw_min_r[26], raw_min_r});"
require_once "$QUANTIZER" \
    "                    high_now = \$signed({raw_max_r[26], raw_max_r});"
require_once "$QUANTIZER" \
    "                        affine_numerator = (sample_wide <<< 8) -"
require_once "$QUANTIZER" "module hap_u36_div_u28_rne_seq ("
require_once "$QUANTIZER" \
    '    (* DONT_TOUCH = "yes", KEEP = "yes" *) reg [35:0] zero_point_term_r;'
require_once "$QUANTIZER" \
    '    reg [1:0] zero_point_mul_step_r;'
require_once "$QUANTIZER" \
    '                            state_r <= ST_ZP_TERM;'
require_once "$MLP_QUANTIZER" \
    '    (* DONT_TOUCH = "yes", KEEP = "yes" *) reg [43:0] zero_point_term_r;'
require_once "$MLP_QUANTIZER" \
    '    reg [1:0] zero_point_mul_step_r;'
require_once "$MLP_QUANTIZER" \
    '                            state_r <= ST_ZP_TERM;'
require_once "$MLP_QUANTIZER" \
    '    localparam integer DIV_LANES = 2;'
require_once "$MLP_QUANTIZER" \
    '    reg [DIV_LANES-1:0] div_active_r;'
require_once "$MLP_QUANTIZER" \
    '    reg [DIV_LANES*44-1:0] div_numerator_r;'
require_once "$MLP_QUANTIZER" \
    '        for (div_lane = 0; div_lane < DIV_LANES;'
require_once "$MLP_QUANTIZER" \
    '                            if (quant_base_r == 30)'
require_once "$MLP_QUANTIZER" \
    "                                quant_base_r <= quant_base_r + 6'd2;"
for quantizer in "$QUANTIZER" "$MLP_QUANTIZER"; do
    reject_text "$quantizer" '(* use_dsp = "no" *) wire'
    reject_text "$quantizer" "ABS_Q9999"
    reject_text "$quantizer" "CLIP_Q001"
    reject_text "$quantizer" "CLIP_Q999"
    reject_text "$quantizer" "clipped_mem"
    reject_text "$quantizer" "abs_threshold"
done
for legacy_s35 in 'reg [7:0] div_active_r;' \
        'reg [8*44-1:0] div_numerator_r;' 'div_lane < 8' \
        'if (quant_base_r == 24)' "quant_base_r + 6'd8" \
        'localparam integer DIV_LANES = 4;' 'if (quant_base_r == 28)' \
        "quant_base_r + 6'd4" 'localparam integer DIV_LANES = 1;' \
        'if (quant_base_r == 31)' "quant_base_r + 6'd1"; do
    reject_text "$MLP_QUANTIZER" "$legacy_s35"
done
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
require_once "$CENTER_SHARD" \
    '        .SPLIT_DUAL_ACCUMULATOR(DUAL_CONTEXT != 0),'
require_once "$CENTER_SHARD" \
    '        .BUFFER_DUAL_ACCUMULATOR(DUAL_CONTEXT != 0)'
require_once "$CENTER_SHARD" '    reg owner_out_pending_r;'
require_once "$CENTER_SHARD" \
    '    wire subshard_out_ready = owner_out_fire;'
require_once "$CENTER_SHARD" '    assign out_valid = owner_out_pending_r;'
require_once "$CENTER_SHARD" \
    '        .out_valid(region2_out_valid), .out_ready(subshard_out_ready),'
require_once "$COL_SHARD" \
    '                .INPUT_BUFFER(BUFFER_DUAL_ACCUMULATOR)'
require_text "$DUAL_ACCUM" 'reg [1:0] buffer_count_r;'
require_text "$DUAL_ACCUM" \
    'assign in_ready = rst_n && !clear && (buffer_count_r != 2);'
require_text "$DUAL_ACCUM" \
    'assign lower_bank_guard_s42 = lower_head_guard_s42_r;'
require_text "$DUAL_ACCUM" \
    'assign upper_bank_guard_s42 = upper_head_guard_s42_r;'
reject_text "$DUAL_ACCUM" \
    'assign lower_bank_guard_s42 = buffer_drain ? in_guard_s42'

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
require_text "$SYNTH_TCL" '$attention_base_frontend_dsp == 64'
require_text "$SYNTH_TCL" '$attention_quantizer_dsp == 0'
require_text "$SYNTH_TCL" '$compact_input_frontend_dsp == 8'
require_text "$SYNTH_TCL" '$compact_input_base_frontend_dsp == 8'
require_text "$SYNTH_TCL" '$compact_input_quantizer_dsp == 0'
require_text "$SYNTH_TCL" '$swiglu_frontend_dsp == 72'
require_text "$SYNTH_TCL" '$swiglu_hadamard_dsp == 64'
require_text "$SYNTH_TCL" '$swiglu_quantizer_dsp == 0'
require_text "$SYNTH_TCL" '$swiglu_silu_dsp == 4'
require_text "$SYNTH_TCL" '$dsp == 5449 && $uram == 752'
require_text "$SYNTH_TCL" 'attention_projection_ok $attention_projection_ok'
require_text "$SYNTH_TCL" \
    'compact_input_frontend_ok $compact_input_frontend_ok'
require_text "$SYNTH_TCL" 'swiglu_frontend_ok $swiglu_frontend_ok'
require_text "$SYNTH_TCL" \
    'no_clip_quantizer_dsp_ok $no_clip_quantizer_dsp_ok'
reject_text "$SYNTH_TCL" '$attention_projection_dsp == 2248'
reject_text "$SYNTH_TCL" '$dsp == 5465'

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
    require_text "$audit" 'attention_base_frontend_dsp48e2'
    require_text "$audit" 'attention_quantizer_dsp48e2'
    require_text "$audit" 'compact_input_frontend_dsp48e2'
    require_text "$audit" 'compact_input_quantizer_dsp48e2'
    require_text "$audit" 'swiglu_frontend_dsp48e2'
    require_text "$audit" 'swiglu_quantizer_dsp48e2'
    require_text "$audit" 'no_clip_quantizer_dsp_ok'
done
require_text "$POST_OPT_TCL" '$swiglu_frontend_dsp == 72'
require_text "$POST_OPT_TCL" '$swiglu_silu_dsp == 4'
require_text "$POST_OPT_TCL" '$swiglu_other_dsp == 0'
require_text "$POST_OPT_TCL" '$total_dsp == 5449 && $total_uram == 752'
require_text "$POST_OPT_TCL" 'dsp_required 5449 dsp_limit 5500'
require_text "$POST_OPT_LAUNCHER" "'swiglu_frontend_dsp48e2=72'"
require_text "$POST_OPT_LAUNCHER" "'swiglu_silu_dsp48e2=4'"
require_text "$POST_OPT_LAUNCHER" "'swiglu_other_dsp48e2=0'"
require_text "$POST_OPT_LAUNCHER" "'dsp48e2=5449'"
require_text "$POST_OPT_LAUNCHER" "'dsp_required=5449'"
reject_text "$POST_OPT_TCL" '$total_dsp == 5445'
reject_text "$POST_OPT_LAUNCHER" 'dsp48e2=5445'

printf '%s\n' \
    V5_COHORT16_STATIC_CONTRACT_PASS \
    production_profile=cohort16 \
    production_attention_board=hap_attention_board_cohort16_core \
    attention_lanes=128 \
    local_dual_accumulators=6 \
    local_accumulator_contexts=12 \
    region2_input_buffer_slots=2 \
    projection_dsp48e2=2240 \
    production_dsp48e2=5449 \
    attention_weight_groups=81920 \
    tensor_axi256_beats=6144 \
    rope_axi256_beats=256
