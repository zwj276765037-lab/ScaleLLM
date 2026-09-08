#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_tile_accum_clear_xsim_$STAMP}"
mkdir -p "$OUT"
cd "$ROOT"

"$BIN/xvlog" -sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    tb/hap_mlp_tile_accum_clear_tb.sv \
    2>&1 | tee "$OUT/xvlog.log"

for WIDTH in 43 45; do
    TOP="hap_mlp_tile_accum_s${WIDTH}_clear_tb"
    SIM="hap_mlp_tile_accum_s${WIDTH}_clear_${STAMP}_sim"
    "$BIN/xelab" -L unisims_ver "$TOP" -s "$SIM" \
        2>&1 | tee "$OUT/s${WIDTH}_xelab.log"
    "$BIN/xsim" "$SIM" -runall \
        2>&1 | tee "$OUT/s${WIDTH}_xsim.log"
    grep -q "^PASS: hap_mlp_tile_accum clear/stall/overflow contract ACC_W=${WIDTH}" \
        "$OUT/s${WIDTH}_xsim.log"
done

printf '%s\n' "$OUT"
