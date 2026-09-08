#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_hadamard_s32_ooc_$STAMP}"
cd "$ROOT"
"$VIVADO" -mode batch -source vivado/scripts/route_mlp_hadamard_s32_ooc.tcl
