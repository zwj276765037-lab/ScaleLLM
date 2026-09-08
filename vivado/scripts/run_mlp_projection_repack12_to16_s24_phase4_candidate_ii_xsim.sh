#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_projection_repack12_to16_s24_phase4_candidate_ii_xsim_$STAMP}"
mkdir -p "$OUT"
cd "$ROOT"
"$VIVADO_BIN/xvlog" -sv \
    rtl/mlp/hap_mlp_projection_repack12_to16_s24_phase4_candidate.sv \
    tb/hap_mlp_projection_repack12_to16_s24_phase4_candidate_ii_tb.sv \
    2>&1 | tee "$OUT/xvlog.log"
"$VIVADO_BIN/xelab" \
    hap_mlp_projection_repack12_to16_s24_phase4_candidate_ii_tb \
    -s hap_mlp_projection_repack12_to16_s24_phase4_candidate_ii_sim \
    2>&1 | tee "$OUT/xelab.log"
"$VIVADO_BIN/xsim" \
    hap_mlp_projection_repack12_to16_s24_phase4_candidate_ii_sim \
    -runall 2>&1 | tee "$OUT/xsim.log"
grep -q '^PASS: phase4 candidate .* II=1' "$OUT/xsim.log"
printf '%s\n' "$OUT"
