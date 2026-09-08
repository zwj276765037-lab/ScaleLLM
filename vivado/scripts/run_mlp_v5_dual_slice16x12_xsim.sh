#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_v5_dual_slice16x12_xsim_$STAMP}"
mkdir -p "$OUT"; cd "$ROOT"
python3 model/generate_mlp_v5_dual_slice16x12_vectors.py | tee "$OUT/generate.log"
"$BIN/xvlog" -sv rtl/mlp/hap_a8w4_pack2_dsp.sv rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
 rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
 rtl/mlp/hap_a8w4_slice8x12_group_s36.sv rtl/mlp/hap_mlp_tile_accum_s36.sv \
 rtl/mlp/hap_mlp_down_group_major_accum_s45.sv rtl/mlp/hap_mlp_shared_slice8x12_s43_s45.sv \
 rtl/mlp/hap_mlp_gate_up_dual_slice16x12_s43.sv rtl/mlp/hap_mlp_down_group_major_dual_slice16x12_s45.sv \
 tb/hap_mlp_v5_dual_slice16x12_tb.sv 2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" hap_mlp_v5_dual_slice16x12_tb -s hap_mlp_v5_dual_slice16x12_sim 2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" hap_mlp_v5_dual_slice16x12_sim -runall 2>&1 | tee "$OUT/xsim.log"
grep -q '^PASS: V5 dual 16x12 gate/down bit-exact' "$OUT/xsim.log"
printf '%s\n' "$OUT"
