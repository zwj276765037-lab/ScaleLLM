#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SOURCE_REPORT="${HAP_SOURCE_REPORT:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_registered_ooc_synth_20260824_195853}"
export HAP_INPUT_DCP="${HAP_INPUT_DCP:-$SOURCE_REPORT/post_synth.dcp}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_registered_ooc_audit_$STAMP}"
export HAP_JOBS="${HAP_JOBS:-32}"
mkdir -p "$HAP_REPORT_DIR"

inputs=(
    "$HAP_INPUT_DCP"
    "$ROOT/vivado/scripts/audit_projection_core16x16_w8_reuse_registered_ooc_synth.tcl"
    "$ROOT/vivado/scripts/run_audit_projection_core16x16_w8_reuse_registered_ooc_synth.sh"
)
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
"$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/audit_projection_core16x16_w8_reuse_registered_ooc_synth.tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"

grep -qx 'status=PASS' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'dut_dsp48e2=2240' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'array_dsp48e2=2176' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'frontend_dsp48e2=64' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'attention_lane_instances=128' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_accumulator_contexts=12' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'drc_errors=0' "$HAP_REPORT_DIR/summary.txt"
sha256sum "$HAP_INPUT_DCP" > "$HAP_REPORT_DIR/INPUT_DCP_SHA256"
find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
    > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
