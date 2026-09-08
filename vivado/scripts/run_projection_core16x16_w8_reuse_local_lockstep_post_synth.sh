#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SOURCE_REPORT="${HAP_SOURCE_REPORT:?HAP_SOURCE_REPORT is required}"
export HAP_INPUT_DCP="${HAP_INPUT_DCP:-$SOURCE_REPORT/post_synth.dcp}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:?HAP_REPORT_DIR is required}"
export HAP_JOBS="${HAP_JOBS:-32}"
TCL="$ROOT/vivado/scripts/diagnose_projection_core16x16_w8_reuse_local_lockstep_post_synth.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_projection_core16x16_w8_reuse_local_lockstep_post_synth.sh"
SOURCE_MANIFEST="$SOURCE_REPORT/OUTPUT_SHA256SUMS"
mkdir -p "$HAP_REPORT_DIR"

test -s "$SOURCE_MANIFEST"
sha256sum -c "$SOURCE_MANIFEST" > "$HAP_REPORT_DIR/source_manifest_precheck.txt"
inputs=("$HAP_INPUT_DCP" "$SOURCE_MANIFEST" "$TCL" "$LAUNCHER")
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

"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
sha256sum -c "$SOURCE_MANIFEST" > "$HAP_REPORT_DIR/source_manifest_postcheck.txt"
grep -qx 'status=PASS' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'array_control_registers=1' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'center_wrapper_control_registers=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_shard_control_registers=6' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'remote_array_control_startpoints=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'retired_compare_nets=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'dut_dsp48e2=2240' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'implementation_commands=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'checkpoints_written=0' "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    printf 'Vivado log contains ERROR/FATAL after nominal return\n' >&2
    exit 1
fi
status=0
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
