#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_weight_meta_resident_ab_ooc_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/mlp_weight_meta_resident_ab_ooc}"
export HAP_JOBS="${HAP_JOBS:-32}"
TCL="$ROOT/vivado/scripts/synth_mlp_weight_meta_resident_ab_ooc.tcl"
XDC="$ROOT/vivado/constraints/mlp_weight_meta_resident_ab_ooc_150mhz.xdc"
LAUNCHER="$ROOT/vivado/scripts/run_mlp_weight_meta_resident_ab_ooc.sh"
RTL="$ROOT/rtl/mlp/hap_mlp_weight_meta_resident_ab.sv"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; metadata OOC not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

inputs=("$RTL" "$XDC" "$TCL" "$LAUNCHER")
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

cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source "$TCL" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
grep -qx 'status=METADATA_SHAPE_PASS' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'uram288=672' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'dsp48e2=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'metadata_leaf_instances=4' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_wr_en_ff=4' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_wr_addr_ff=70' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_wr_data_ff=896' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'protected_local_write_ff=970' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'local_write_boundary_ok=1' "$HAP_REPORT_DIR/summary.txt"
status=0
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
