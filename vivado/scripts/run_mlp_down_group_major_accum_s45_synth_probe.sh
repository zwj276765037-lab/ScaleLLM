#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_group_major_accum_s45_synth_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/mlp_down_group_major_accum_s45_synth}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_mlp_down_group_major_accum_s45_synth.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
printf '%s\n' "$HAP_REPORT_DIR"
