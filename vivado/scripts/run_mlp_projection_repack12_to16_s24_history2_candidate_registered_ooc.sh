#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"

"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/route_mlp_projection_repack12_to16_s24_history2_candidate_registered_ooc.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"

test -s "$HAP_REPORT_DIR/summary.txt"
grep -qx 'status=REGISTERED_OOC_DIAGNOSTIC_PASS_NO_SHELL_BUDGET' \
    "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    echo "Vivado log contains an ERROR/FATAL after a nominal return" >&2
    exit 1
fi
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
