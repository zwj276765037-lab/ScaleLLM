#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_serial_ddr_command16_v5_reduced_xsim_$STAMP}"
SIM=hap_mlp_serial_ddr_command16_v5_s45_reduced_sim
WORK="$ROOT/xsim_work/$SIM"
mkdir -p "$OUT" "$WORK"
cd "$ROOT"

"$PYTHON" model/generate_mlp_silu_artifacts.py >"$OUT/silu_generation.log"
"$PYTHON" model/generate_mlp_serial_ddr_command16_v5_reduced_vectors.py \
  2>&1 | tee "$OUT/vector_generation.log"

RTL=(
  rtl/mlp/hap_a8w4_pack2_dsp.sv
  rtl/mlp/hap_a8w4_group32_pack2_s17.sv
  rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv
  rtl/mlp/hap_a8w4_group32_lane2_s36.sv
  rtl/mlp/hap_a8w4_slice8x12_group_s36.sv
  rtl/mlp/hap_mlp_tile_accum_s36.sv
  rtl/mlp/hap_mlp_down_group_major_accum_s45.sv
  rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv
  rtl/mlp/hap_mlp_gate_up_gather_pingpong12.sv
  rtl/mlp/hap_mlp_w4_repack48_to12.sv
  rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv
  rtl/mlp/hap_mlp_silu_mul.sv
  rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv
  rtl/attention/hap_u16_div_u8_seq.sv
  rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv
  rtl/mlp/hap_mlp_product_frontend16_q4.sv
  rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv
  rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv
  rtl/mlp/hap_mlp_down_activation_cache16.sv
  rtl/mlp/hap_mlp_down_v5_scheduler16_s45.sv
  rtl/mlp/hap_axi512_w4_weight_reader.sv
  rtl/mlp/hap_ddr512_w4_halfgroup_async.sv
  rtl/mlp/hap_mlp_w4_dual_channel_join.sv
  rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv
  rtl/mlp/hap_mlp_serial_ddr_command16_v5_s45.sv
)

"$BIN/xvlog" -sv "${RTL[@]}" \
  tb/hap_mlp_serial_ddr_command16_v5_s45_reduced_tb.sv \
  2>&1 | tee "$OUT/xvlog.log"
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
"$BIN/xvlog" "$GLBL_V" 2>&1 | tee -a "$OUT/xvlog.log"
"$BIN/xelab" -L xpm -L unisims_ver \
  hap_mlp_serial_ddr_command16_v5_s45_reduced_tb glbl -s "$SIM" \
  2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"

# A PASS marker is necessary but never sufficient.  Any compiler, elaborator,
# simulator or TB failure marker rejects the run, including Vivado's plain
# "Error:"/"Fatal:" capitalization and a stale PASS printed after $fatal.
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$OUT/vector_generation.log" "$OUT/xvlog.log" "$OUT/xelab.log" \
    "$OUT/xsim.log"; then
  echo "launcher rejected FAIL/Error/Fatal marker in V5 serial logs" >&2
  exit 1
fi
if [[ "$(grep -c '^PASS: V5 serial reduced end-to-end bit-exact .*mismatches=0$' \
    "$OUT/xsim.log")" -ne 1 ]]; then
  echo "launcher requires exactly one trusted V5 serial PASS marker" >&2
  exit 1
fi

printf '%s\n' "$OUT"
