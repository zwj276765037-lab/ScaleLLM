#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_v5_scheduler_smoke_xsim_$STAMP}"
SIM=hap_mlp_down_v5_scheduler16_s45_smoke_sim
mkdir -p "$OUT"
cd "$ROOT"

"$BIN/xvlog" -sv \
  rtl/mlp/hap_mlp_w4_repack48_to12.sv \
  rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv \
  rtl/mlp/hap_mlp_down_v5_scheduler16_s45.sv \
  tb/hap_mlp_down_v5_scheduler16_s45_smoke_tb.sv \
  2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" -L unisims_ver \
  hap_mlp_down_v5_scheduler16_s45_smoke_tb -s "$SIM" \
  2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"

# A PASS marker is necessary but never sufficient.  Reject simulator or TB
# failure markers explicitly so a later accidental PASS print cannot mask a
# prior failure/fatal message.
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|[[:space:]])' \
    "$OUT/xvlog.log" "$OUT/xelab.log" "$OUT/xsim.log"; then
  echo "launcher rejected FAIL/Error/Fatal marker in simulation logs" >&2
  exit 1
fi
if [[ "$(grep -c '^PASS: down V5 scheduler bit-exact conservation .*source=12 compute=18 projection=6 output=4 .*modes=6/6/6 .*cycles=54$' \
    "$OUT/xsim.log")" -ne 1 ]]; then
  echo "launcher requires exactly one trusted down-scheduler PASS marker" >&2
  exit 1
fi

printf '%s\n' "$OUT"
