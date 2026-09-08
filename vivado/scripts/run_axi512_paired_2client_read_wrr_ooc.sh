#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/axi512_paired_wrr_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR";cd "$ROOT"
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/route_axi512_paired_2client_read_wrr_ooc.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" -journal "$HAP_REPORT_DIR/vivado.jou"
sha256sum "$HAP_REPORT_DIR/post_route.dcp" \
  rtl/integration/hap_axi512_paired_2client_read_wrr.sv \
  vivado/constraints/axi512_paired_2client_read_wrr_ooc_150_300_300.xdc \
  vivado/scripts/route_axi512_paired_2client_read_wrr_ooc.tcl \
  > "$HAP_REPORT_DIR/SHA256SUMS"
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
