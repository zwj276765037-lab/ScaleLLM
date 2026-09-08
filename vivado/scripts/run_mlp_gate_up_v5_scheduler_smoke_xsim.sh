#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_gate_up_v5_scheduler_smoke_xsim_$STAMP}"
SIM=hap_mlp_gate_up_v5_scheduler16_q4_smoke_sim
mkdir -p "$OUT"
cd "$ROOT"
"$BIN/xvlog" -sv \
  rtl/mlp/hap_mlp_gate_up_gather_pingpong12.sv \
  rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv \
  rtl/mlp/hap_mlp_silu_mul.sv \
  rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
  rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
  rtl/mlp/hap_mlp_product_frontend16_q4.sv \
  rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
  rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv \
  tb/hap_mlp_gate_up_v5_scheduler16_q4_smoke_tb.sv \
  2>&1 | tee "$OUT/xvlog.log"
"$BIN/xelab" -L unisims_ver \
  hap_mlp_gate_up_v5_scheduler16_q4_smoke_tb -s "$SIM" \
  2>&1 | tee "$OUT/xelab.log"
"$BIN/xsim" "$SIM" -runall 2>&1 | tee "$OUT/xsim.log"
if grep -Eq '(^|[^A-Za-z])(FAIL:|ERROR:|Error:|FATAL:|Fatal:)' \
    "$OUT/xvlog.log" "$OUT/xelab.log" "$OUT/xsim.log"; then
  printf 'V5 gate scheduler smoke rejected error/failure marker in logs\n' >&2
  exit 1
fi
PASS_COUNT="$(grep -c \
  '^PASS: gate V5 scheduler bit-exact conservation .*mismatches=0$' \
  "$OUT/xsim.log" || true)"
if [[ "$PASS_COUNT" -ne 1 ]]; then
  printf 'V5 gate scheduler smoke expected exactly one strict PASS, got %s\n' \
    "$PASS_COUNT" >&2
  exit 1
fi
printf '%s\n' "$OUT"
