#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_shared_dual_slice16x12_s43_s45_xsim_$STAMP}"
SIM=hap_mlp_shared_dual_slice16x12_s43_s45_sim
II_SIM=hap_mlp_shared_dual_slice16x12_s43_s45_ii_sim
mkdir -p "$OUT"
cd "$ROOT"
python3 model/generate_mlp_v5_dual_slice16x12_vectors.py \
    | tee "$OUT/generate.log"
"$BIN/xvlog" -sv \
    rtl/mlp/hap_a8w4_pack2_dsp.sv \
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv \
    rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
    rtl/mlp/hap_a8w4_slice8x12_group_s36.sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    rtl/mlp/hap_mlp_gate_up_dual_local_accum16x12_s43.sv \
    rtl/mlp/hap_mlp_down_group_major_dual_slice16x12_s45.sv \
    rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv \
    tb/hap_mlp_shared_dual_slice16x12_s43_s45_tb.sv \
    tb/hap_mlp_shared_dual_slice16x12_s43_s45_ii_tb.sv \
    2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" -L unisims_ver hap_mlp_shared_dual_slice16x12_s43_s45_tb \
    -s "$SIM" 2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"
grep -q '^PASS: V5 shared dual 16x12 gate/down bit-exact' \
    "$OUT/xsim.log"
"$BIN/xelab" -L unisims_ver hap_mlp_shared_dual_slice16x12_s43_s45_ii_tb \
    -s "$II_SIM" 2>&1 | tee "$OUT/ii_xelab.log"
"$BIN/xsim" "$II_SIM" -runall 2>&1 | tee "$OUT/ii_xsim.log"
grep -q '^PASS: V5 shared dual 16x12 no-stall II=1' \
    "$OUT/ii_xsim.log"
printf '%s\n' "$OUT"
