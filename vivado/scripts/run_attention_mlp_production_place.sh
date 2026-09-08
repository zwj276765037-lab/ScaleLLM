#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_DCP="${HAP_DCP:-$ROOT/vivado/reports/production_core_20260811_231932/post_opt.dcp}"
export HAP_PLACE_DIR="${HAP_PLACE_DIR:-$ROOT/vivado/reports/production_place_$STAMP}"
mkdir -p "$HAP_PLACE_DIR";cd "$ROOT"
"$VIVADO" -mode batch -notrace -source vivado/scripts/place_attention_mlp_production_feasibility.tcl \
 -log "$HAP_PLACE_DIR/vivado.log" -journal "$HAP_PLACE_DIR/vivado.jou"
grep -Fq 'status=PLACEMENT_FEASIBILITY_PASS' "$HAP_PLACE_DIR/summary.txt"
sha256sum "$HAP_PLACE_DIR/post_place.dcp" > "$HAP_PLACE_DIR/SHA256SUMS"
printf '%s\n' "$HAP_PLACE_DIR"
