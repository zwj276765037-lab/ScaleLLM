#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.."&&pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/axi512_paired_wrr_place_probe_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"
cd "$ROOT"
sha256sum rtl/integration/hap_axi512_paired_2client_read_wrr.sv \
  vivado/constraints/axi512_paired_2client_read_wrr_ooc_150_300_300.xdc \
  vivado/scripts/probe_axi512_paired_2client_read_wrr_place.tcl \
  vivado/scripts/run_axi512_paired_2client_read_wrr_place_probe.sh \
  > "$HAP_REPORT_DIR/input_SHA256SUMS"
set +e
"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/probe_axi512_paired_2client_read_wrr_place.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" -journal "$HAP_REPORT_DIR/vivado.jou"
rc=$?
set -e
find "$HAP_REPORT_DIR" -maxdepth 1 -type f -print0 | sort -z | \
  xargs -0 -r sha256sum > "$HAP_REPORT_DIR/artifact_SHA256SUMS.tmp"
mv "$HAP_REPORT_DIR/artifact_SHA256SUMS.tmp" "$HAP_REPORT_DIR/artifact_SHA256SUMS"
[[ -f "$HAP_REPORT_DIR/summary.txt" ]] && cat "$HAP_REPORT_DIR/summary.txt"
printf 'exit_status=%s\n%s\n' "$rc" "$HAP_REPORT_DIR"
exit "$rc"
