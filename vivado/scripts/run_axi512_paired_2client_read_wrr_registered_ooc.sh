#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/axi512_paired_wrr_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"

INPUTS=(
  rtl/integration/hap_axi512_paired_2client_read_wrr.sv
  rtl/integration/hap_axi512_paired_2client_read_wrr_ooc_harness.sv
  vivado/constraints/axi512_paired_2client_read_wrr_registered_ooc_150_300_300.xdc
  vivado/scripts/route_axi512_paired_2client_read_wrr_registered_ooc.tcl
  vivado/scripts/run_axi512_paired_2client_read_wrr_registered_ooc.sh
)

cd "$ROOT" || exit 2
# Capture immutable inputs before Vivado starts.  This exists even if synthesis,
# route, acceptance, a timeout or the shell itself returns nonzero.
sha256sum "${INPUTS[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"

"$VIVADO" -mode batch -notrace \
  -source vivado/scripts/route_axi512_paired_2client_read_wrr_registered_ooc.tcl \
  -log "$HAP_REPORT_DIR/vivado.log" -journal "$HAP_REPORT_DIR/vivado.jou"
rc=$?

# Do not let a failing Vivado status suppress provenance.  Hash every artifact
# that actually exists and preserve Vivado's original return code.
find "$HAP_REPORT_DIR" -maxdepth 1 -type f ! -name ARTIFACT_SHA256SUMS \
  -print0 | sort -z | xargs -0 -r sha256sum > "$HAP_REPORT_DIR/ARTIFACT_SHA256SUMS"
if [[ -f "$HAP_REPORT_DIR/summary.txt" ]]; then
  cat "$HAP_REPORT_DIR/summary.txt"
fi
printf '%s\n' "$HAP_REPORT_DIR"
exit "$rc"
