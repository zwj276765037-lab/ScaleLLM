#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_branch_elastic2_s24_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"

INPUTS=(
  rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv
  rtl/mlp/hap_mlp_down_branch_elastic2_s24_ooc_harness.sv
  vivado/constraints/mlp_down_branch_elastic2_s24_ooc_150mhz.xdc
  vivado/scripts/route_mlp_down_branch_elastic2_s24_ooc.tcl
  vivado/scripts/run_mlp_down_branch_elastic2_s24_ooc.sh
)
sha256sum \
  "${INPUTS[@]}" \
  >"$HAP_REPORT_DIR/INPUT_SHA256SUMS"
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/route_mlp_down_branch_elastic2_s24_ooc.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" \
  -journal "$HAP_REPORT_DIR/vivado.jou"

sha256sum "${INPUTS[@]}" >"$HAP_REPORT_DIR/POST_INPUT_SHA256SUMS"
cmp -s "$HAP_REPORT_DIR/INPUT_SHA256SUMS" \
  "$HAP_REPORT_DIR/POST_INPUT_SHA256SUMS" || {
    echo "launcher rejected input mutation during down elastic2 OOC" >&2
    exit 1
  }
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
    "$HAP_REPORT_DIR/summary.txt"; then
  echo "launcher rejected FAIL/Error/Fatal marker in down elastic2 summary" >&2
  exit 1
fi
if grep -Eiq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
  echo "launcher rejected Vivado Error/Fatal marker in down elastic2 log" >&2
  exit 1
fi
if [[ "$(grep -c '^status=DOWN_ELASTIC2_EXCEPTION_FREE_OOC_PASS$' \
    "$HAP_REPORT_DIR/summary.txt")" -ne 1 ]]; then
  echo "launcher requires exactly one trusted down elastic2 OOC PASS" >&2
  exit 1
fi
OUTPUTS=(
  INPUT_SHA256SUMS
  POST_INPUT_SHA256SUMS
  summary.txt
  post_route.dcp
  timing_summary.rpt
  utilization.rpt
  utilization_hierarchical.rpt
  route_status.rpt
  high_fanout_nets.rpt
  congestion.rpt
  drc.rpt
  drc_final.rpt
  vivado.log
  vivado.jou
)
for output in "${OUTPUTS[@]}"; do
  [[ -s "$HAP_REPORT_DIR/$output" ]] || {
    echo "launcher rejected missing/empty output: $output" >&2
    exit 1
  }
done
(
  cd "$HAP_REPORT_DIR"
  sha256sum "${OUTPUTS[@]}" >OUTPUT_SHA256SUMS
)
printf '%s\n' "$HAP_REPORT_DIR"
