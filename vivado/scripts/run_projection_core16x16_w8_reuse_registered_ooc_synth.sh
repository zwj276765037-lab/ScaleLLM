#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_registered_ooc_synth_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/projection_core16x16_w8_reuse_registered_ooc_synth_$STAMP}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"

mapfile -t manifest_sources < <(grep -vE '^[[:space:]]*(#|$)' \
    "$ROOT/vivado/manifests/attention_projection_core16x16_w8_reuse_sources.list")
inputs=(
    "$ROOT/vivado/manifests/attention_projection_core16x16_w8_reuse_sources.list"
    "$ROOT/rtl/attention/hap_projection_core16x16_w8_reuse_registered_ooc_harness.sv"
    "$ROOT/vivado/constraints/projection_core16x16_w8_reuse_registered_ooc_150mhz.xdc"
    "$ROOT/vivado/scripts/synth_projection_core16x16_w8_reuse_registered_ooc.tcl"
    "$ROOT/vivado/scripts/run_projection_core16x16_w8_reuse_registered_ooc_synth.sh"
)
for file in "${manifest_sources[@]}"; do
    inputs+=("$ROOT/$file")
done
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE"
status=1
archive() {
    set +e
    sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
    if cmp -s "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE" \
            "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"; then
        printf 'input_sha_stable=1\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
    else
        printf 'input_sha_stable=0\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
        status=1
    fi
    printf 'launcher_exit_status=%s\n' "$status" > \
        "$HAP_REPORT_DIR/launcher_status.txt"
    find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
}
trap archive EXIT

"$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/synth_projection_core16x16_w8_reuse_registered_ooc.tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"

test -s "$HAP_REPORT_DIR/summary.txt"
grep -qx 'status=PASS' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'attention_lane_instances=128' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_accumulator_contexts=12' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'dut_dsp48e2=2240' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'array_dsp48e2=2176' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'frontend_dsp48e2=64' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'forbidden_timing_exception_count=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'timing_coverage_ok=1' "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    echo "Vivado log contains ERROR/FATAL after nominal return" >&2
    exit 1
fi
status=0
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
