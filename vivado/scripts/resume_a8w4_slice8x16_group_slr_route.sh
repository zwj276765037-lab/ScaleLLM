#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
BASE="${HAP_BASE_REPORT_DIR:-$ROOT/vivado/reports/a8w4_slice8x16_group_slr0_v3_20260810}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PLACE_DCP="${HAP_PLACE_DCP:-$BASE/post_place.dcp}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/a8w4_slice8x16_group_slr0_v3_route_resume_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/resume_a8w4_slice8x16_group_slr_route.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
printf '%s\n' "$HAP_REPORT_DIR"
