#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
export HAP_JOBS="${HAP_JOBS:-32}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:?HAP_REPORT_DIR is required}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:?HAP_BUILD_DIR is required}"
TCL="$ROOT/vivado/scripts/synth_a8w4_slice8x12_owner_capture_registered_ooc.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_a8w4_slice8x12_owner_capture_registered_ooc_synth.sh"
XDC="$ROOT/vivado/constraints/a8w4_slice8x12_group_registered_ooc_100mhz.xdc"
inputs=(
    "$ROOT/rtl/mlp/hap_a8w4_pack2_dsp.sv"
    "$ROOT/rtl/mlp/hap_a8w4_group32_pack2_s17.sv"
    "$ROOT/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv"
    "$ROOT/rtl/mlp/hap_a8w4_group32_lane2_s36.sv"
    "$ROOT/rtl/mlp/hap_a8w4_slice8x12_group_s36.sv"
    "$ROOT/rtl/mlp/hap_a8w4_slice8x12_group_registered_ooc_harness.sv"
    "$XDC" "$TCL" "$LAUNCHER"
)
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; MLP owner-capture OOC not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
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
grep -qx 'status=PASS' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'mlp_pack2_lane_instances=48' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_instances=816' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_lut1=816' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_min_ce_load=32' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_max_ce_load=42' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_total_ce_loads=28128' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_load32_count=384' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_load36_count=384' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_load42_count=48' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_non_ce_endpoints=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'ingress_capture_leaf_load_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'dut_dsp48e2=1536' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'forbidden_timing_exception_count=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'timing_coverage_ok=1' "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    printf 'Vivado log contains ERROR/FATAL after nominal return\n' >&2
    exit 1
fi
status=0
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
