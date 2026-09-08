#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/weight_meta_ready_boundary_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"

sha256sum rtl/attention/hap_weight_meta_resident.sv \
    vivado/constraints/weight_meta_resident_ooc_150mhz.xdc \
    vivado/scripts/synth_weight_meta_resident_ready_boundary_ooc.tcl \
    > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/synth_weight_meta_resident_ready_boundary_ooc.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
grep -Fqx 'status=PASS' "$HAP_REPORT_DIR/summary.txt"
sha256sum "$HAP_REPORT_DIR/post_opt.dcp" \
    "$HAP_REPORT_DIR/summary.txt" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
