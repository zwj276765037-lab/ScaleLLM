#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SOURCE_REPORT="${HAP_SOURCE_REPORT:-$ROOT/vivado/reports/a8w4_slice8x16_group_slr0_v3_route_resume_20260810_184830}"
export HAP_CHECKPOINT="${HAP_CHECKPOINT:-$SOURCE_REPORT/post_route.dcp}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/a8w4_slice8x16_group_hold_repair_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/repair_a8w4_slice8x16_group_hold.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
printf '%s\n' "$HAP_REPORT_DIR"
