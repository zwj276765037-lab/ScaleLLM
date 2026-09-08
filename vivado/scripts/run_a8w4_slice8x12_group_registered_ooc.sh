#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/a8w4_slice8x12_group_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/route_a8w4_slice8x12_group_registered_ooc.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" \
  -journal "$HAP_REPORT_DIR/vivado.jou"
printf '%s\n' "$HAP_REPORT_DIR"

