#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_gate_up_dual_local_accum16x12_s43_xsim_$STAMP}"
SIM=hap_mlp_gate_up_dual_local_accum16x12_s43_sim
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
    rtl/mlp/hap_mlp_gate_up_dual_slice16x12_s43.sv \
    rtl/mlp/hap_mlp_gate_up_dual_local_accum16x12_s43.sv \
    tb/hap_mlp_gate_up_dual_local_accum16x12_s43_tb.sv \
    2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" hap_mlp_gate_up_dual_local_accum16x12_s43_tb \
    -s "$SIM" 2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"
grep -q '^PASS: V5 gate dual-local S43 bit-exact' "$OUT/xsim.log"
printf '%s\n' "$OUT"
