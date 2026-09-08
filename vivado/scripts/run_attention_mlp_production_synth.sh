#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/production_core_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/production_synth}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR";cd "$ROOT"
"$VIVADO" -mode batch -notrace -source vivado/scripts/synth_attention_mlp_production_core.tcl \
 -log "$HAP_REPORT_DIR/vivado.log" -journal "$HAP_REPORT_DIR/vivado.jou"
grep -Fq 'status=PRODUCTION_RESOURCE_PASS' "$HAP_REPORT_DIR/summary.txt"
sha256sum "$HAP_REPORT_DIR/post_synth.dcp" "$HAP_REPORT_DIR/post_opt.dcp" > "$HAP_REPORT_DIR/SHA256SUMS"
printf '%s\n' "$HAP_REPORT_DIR"
