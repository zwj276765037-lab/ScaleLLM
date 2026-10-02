#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MLP="$ROOT/rtl/mlp"
INTEGRATION="$ROOT/rtl/integration"
MANIFEST="$ROOT/vivado/manifests/attention_mlp_resource_top_v5_sources.list"
COHORT_MANIFEST="$ROOT/vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
LANE="$MLP/hap_a8w4_group32_lane2_s37.sv"
SLICE="$MLP/hap_a8w4_slice8x12_group_s37.sv"
ACCUM="$MLP/hap_mlp_tile_accum_s37.sv"
DOWN_ACCUM="$MLP/hap_mlp_down_group_major_accum_s46.sv"
SHARED="$MLP/hap_mlp_shared_dual_slice16x12_s44_s46.sv"
SERIAL="$MLP/hap_mlp_serial_ddr_command16_v5_s46.sv"
FULL="$MLP/hap_mlp_full_command16_v5_s46.sv"
PKG="$MLP/hap_mlp_pkg.sv"
CONTROL="$INTEGRATION/hap_mlp_axil_control.sv"
TOP="$INTEGRATION/hap_attention_mlp_resource_top.sv"
SHIFT20_TB="$ROOT/tb/hap_mlp_v5_shift20_recovery_tb.sv"
REDUCED_TB="$ROOT/tb/hap_mlp_serial_ddr_command16_v5_s46_reduced_tb.sv"
REDUCED_RUN="$ROOT/vivado/scripts/run_mlp_serial_ddr_command16_v5_reduced_xsim.sh"
SMOKE_RUN="$ROOT/vivado/scripts/run_v5_production_top_smoke_xsim.sh"
HOST="$ROOT/host/scalellm_hardware.py"
EXPORTER="$ROOT/model/export_scalellm_llama31_artifacts.py"
MODEL="$ROOT/model/mlp_fixed.py"
HOST_TEST="$ROOT/tests/test_scalellm_hardware.py"
ARTIFACT_TEST="$ROOT/tests/test_scalellm_artifacts.py"

fail() {
    printf 'MLP_V5_FORMAT_V3_STATIC_FAIL: %s\n' "$*" >&2
    exit 1
}

require_fixed() {
    local file="$1" text="$2"
    grep -Fq -- "$text" "$file" ||
        fail "missing contract in ${file#"$ROOT/"}: $text"
}

require_regex() {
    local file="$1" expression="$2"
    grep -Eq -- "$expression" "$file" ||
        fail "missing contract in ${file#"$ROOT/"}: $expression"
}

reject_fixed() {
    local file="$1" text="$2"
    ! grep -Fq -- "$text" "$file" ||
        fail "forbidden legacy contract in ${file#"$ROOT/"}: $text"
}

for file in "$LANE" "$SLICE" "$ACCUM" "$DOWN_ACCUM" "$SHARED" "$SERIAL" "$FULL" "$PKG" "$CONTROL" "$TOP" "$SHIFT20_TB" "$REDUCED_TB" "$REDUCED_RUN" "$SMOKE_RUN" "$HOST" "$EXPORTER" "$MODEL" "$HOST_TEST" "$ARTIFACT_TEST" "$MANIFEST" "$COHORT_MANIFEST"; do
    [[ -s "$file" ]] || fail "missing or empty input: ${file#"$ROOT/"}"
done

# Unchanged packed-dot and raw recovery widths.
require_fixed "$MLP/hap_a8w4_group32_pack2_s17.sv" '    output reg signed [16:0]            dot0_s17,'
require_fixed "$MLP/hap_a8w4_scalecode_recover2_lut.sv" '    output reg signed [32:0]    raw0_s33,'

# Format-v3 recovery: local metadata widths stay code8/shift6 while only the
# guard and accumulators widen.
require_fixed "$LANE" 'module hap_a8w4_group32_lane2_s37 #('
require_fixed "$LANE" '    input  wire [7:0]                 activation_code_u8,'
require_fixed "$LANE" '    input  wire [5:0]                 activation_shift_u6,'
require_fixed "$LANE" '    reg signed [36:0] guard0_mem [0:GUARD_DEPTH-1];'
require_fixed "$LANE" '            extended_s37 = {{4{raw_s33[32]}}, raw_s33};'
require_fixed "$LANE" '            shifted_s38 = {{5{raw_s33[32]}}, raw_s33};'
require_fixed "$LANE" "            else if (total_shift_u7 < 7'd20 ||"
require_fixed "$LANE" "                     total_shift_u7 > 7'd44)"
require_fixed "$LANE" '    output reg                        guard_overflow,'
require_fixed "$SLICE" '    output reg signed [8*12*37-1:0]     guard_s37x8x12,'
require_fixed "$SLICE" '    output wire                         guard_overflow,'

# Gate/up uses S44 and down uses S46. Every addition has a one-bit-wider
# overflow check and the sticky status reaches the command error path.
require_fixed "$ACCUM" '    parameter integer ACC_W = 44,'
require_fixed "$ACCUM" '    input  wire signed [LANES*37-1:0]   in_guard_s37,'
require_fixed "$ACCUM" '                            lane_sum_ext[ACC_W] != lane_sum_ext[ACC_W-1];'
require_fixed "$DOWN_ACCUM" 'module hap_mlp_down_group_major_s46_bank #('
require_fixed "$DOWN_ACCUM" '    (* ram_style = "block" *) reg signed [45:0] memory [0:TILES-1];'
require_fixed "$DOWN_ACCUM" '    input  wire signed [LANES*37-1:0]   in_guard_s37,'
require_fixed "$DOWN_ACCUM" '                        lane_sum_ext[46] != lane_sum_ext[45];'
require_fixed "$SHARED" 'module hap_mlp_shared_dual_slice16x12_s44_s46 #('
require_fixed "$SHARED" 'module hap_mlp_shared_local_slice8x12_s44_s46 #('
require_fixed "$SHARED" '        .LANES(LANES), .ACC_W(44), .GROUPS(128),'
require_fixed "$SHARED" '    wire signed [LANES*37-1:0] guard_s37;'
require_fixed "$SHARED" 'module hap_mlp_down_branch_elastic2_s24_v6 #('
require_fixed "$SERIAL" 'module hap_mlp_serial_ddr_command16_v5_s46 #('
require_fixed "$SERIAL" '                down_error || shared_error || shared_guard_overflow ||'
require_fixed "$FULL" 'module `HAP_MLP_FULL_COMMAND_V5_MODULE #('
require_fixed "$TOP" '    hap_mlp_full_command16_s46 u_mlp('

require_fixed "$PKG" "    localparam logic [31:0] HAP_MLP_FIXBIT_V3_FORMAT_ID = 32'h4838_4d03;"
require_fixed "$PKG" "    localparam logic [31:0] HAP_FULL_FIXBIT_V3_FORMAT_ID = 32'h4838_4603;"
require_fixed "$PKG" '    localparam int MLP_GROUP_GUARD_W = 37;'
require_fixed "$PKG" '    localparam int MLP_GATE_UP_ACCUM_W = 44;'
require_fixed "$PKG" '    localparam int MLP_DOWN_ACCUM_W = 46;'

# Host-visible format ID is a hard compatibility boundary.
require_fixed "$CONTROL" "    localparam [31:0] FULL_FORMAT_ID = 32'h4838_4603;"
require_fixed "$HOST" 'MLP_FORMAT_ID = 0x4838_4603'
require_fixed "$EXPORTER" 'MLP_FORMAT_ID = 0x4838_4603'
require_fixed "$MODEL" 'FULL_FORMAT_ID = 0x4838_4603'
require_fixed "$HOST_TEST" 'old_width_bitstream.registers[0x100] = 0x4838_4602'
require_fixed "$ARTIFACT_TEST" 'raw["mlp_format_id"] = 0x4838_4602'
for active in "$CONTROL" "$HOST" "$EXPORTER" "$MODEL"; do
    reject_fixed "$active" '0x4838_4602'
    reject_fixed "$active" "32'h4838_4602"
done

# Production binding contains only v3 MLP width modules. Legacy files may
# remain for historical regressions but cannot enter the V5 source closure.
for required in rtl/mlp/hap_a8w4_group32_lane2_s37.sv rtl/mlp/hap_a8w4_slice8x12_group_s37.sv rtl/mlp/hap_mlp_tile_accum_s37.sv rtl/mlp/hap_mlp_down_group_major_accum_s46.sv rtl/mlp/hap_mlp_down_v5_scheduler16_s46.sv rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s46.sv rtl/mlp/hap_mlp_serial_ddr_command16_v5_s46.sv rtl/mlp/hap_mlp_full_command16_v5_s46.sv; do
    require_fixed "$MANIFEST" "$required"
done
for forbidden in hap_a8w4_group32_lane2_s36.sv hap_a8w4_slice8x12_group_s36.sv hap_mlp_tile_accum_s36.sv hap_mlp_down_group_major_accum_s45.sv hap_mlp_down_v5_scheduler16_s45.sv hap_mlp_shared_dual_slice16x12_s43_s45.sv hap_mlp_serial_ddr_command16_v5_s45.sv hap_mlp_full_command16_v5_s45.sv; do
    reject_fixed "$MANIFEST" "$forbidden"
done
require_fixed "$COHORT_MANIFEST" 'vivado/manifests/attention_mlp_production_v5_sources.list'
require_fixed "$SMOKE_RUN" 'HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s46'
require_fixed "$REDUCED_RUN" 'tb/hap_mlp_serial_ddr_command16_v5_s46_reduced_tb.sv'
require_fixed "$REDUCED_TB" '    hap_mlp_serial_ddr_command16_v5_s46 #('

# Mandatory layer31.down_proj shift-20 recovery vector.
require_fixed "$SHIFT20_TB" "    localparam signed [36:0] EXPECTED_GUARD = 37'sd7219200;"
require_fixed "$SHIFT20_TB" "    localparam signed [23:0] EXPECTED_S24 = 24'sd56400;"
require_fixed "$SHIFT20_TB" "            activation_code_u8x8[lane*8 +: 8] = 8'd100;"
require_fixed "$SHIFT20_TB" "            activation_shift_u6x8[lane*6 +: 6] = 6'd6;"
require_fixed "$SHIFT20_TB" "            weight_code_u8x12[lane*8 +: 8] = 8'd141;"
require_fixed "$SHIFT20_TB" "            weight_shift_u6x12[lane*6 +: 6] = 6'd14;"
require_fixed "$SHIFT20_TB" 'guard_overflow=0 accumulator_overflow=0");'

# Explicitly preserve boundaries outside this repair.
require_fixed "$ROOT/rtl/attention/hap_a8w8_array_16x16_s42.sv" 'module hap_a8w8_array_16x16_s42 #('
require_fixed "$SHARED" '    output wire signed [16*12*24-1:0]    gate_s24x16x12,'
require_fixed "$ROOT/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv" '    wire signed [31:0] branch_product_s32_stream [0:1];'
require_fixed "$MANIFEST" 'rtl/mlp/hap_mlp_w4_repack48_to12.sv'
require_fixed "$MANIFEST" 'rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv'

printf '%s\n' MLP_V5_FORMAT_V3_STATIC_PASS full_format_id=0x48384603 legal_total_shift=20..44 guard=S37_Q13.24 gate_up_accumulator=S44_Q20.24 down_accumulator=S46_Q22.24 external_ddr_abi=unchanged_dense16
