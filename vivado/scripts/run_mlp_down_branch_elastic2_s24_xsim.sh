#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_branch_elastic2_s24_xsim_$STAMP}"
SIM=hap_mlp_down_branch_elastic2_s24_sim
mkdir -p "$OUT"
cd "$ROOT"

"$BIN/xvlog" -sv \
  rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv \
  tb/hap_mlp_down_branch_elastic2_s24_tb.sv \
  2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" hap_mlp_down_branch_elastic2_s24_tb -s "$SIM" \
  2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"

if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$OUT/xvlog.log" "$OUT/xelab.log" "$OUT/xsim.log"; then
  echo "launcher rejected FAIL/Error/Fatal marker in down elastic2 logs" >&2
  exit 1
fi
if [[ "$(grep -c '^PASS: V5 branch-local down elastic2 .*clear-mid-stall discarded stale entries$' \
    "$OUT/xsim.log")" -ne 1 ]]; then
  echo "launcher requires exactly one trusted down elastic2 PASS marker" >&2
  exit 1
fi

sha256sum \
  rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv \
  tb/hap_mlp_down_branch_elastic2_s24_tb.sv \
  vivado/scripts/run_mlp_down_branch_elastic2_s24_xsim.sh \
  >"$OUT/INPUT_SHA256SUMS"
printf '%s\n' "$OUT"
