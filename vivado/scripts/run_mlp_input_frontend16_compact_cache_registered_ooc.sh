#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_input_frontend16_compact_cache_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR/work"

[[ "$HAP_JOBS" == 32 ]] || {
    printf 'compact-input registered OOC requires HAP_JOBS=32\n' >&2
    exit 2
}
mapfile -t active_vivado < <(pgrep -u "$(id -u)" -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_vivado[@]}" -ne 0 ]]; then
    printf 'another project-user batch Vivado is active:\n' >&2
    printf '  %s\n' "${active_vivado[@]}" >&2
    exit 75
fi

inputs=(
    "$ROOT/rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv"
    "$ROOT/rtl/attention/hap_u16_div_u8_seq.sv"
    "$ROOT/rtl/attention/hap_robust_a8_quantizer.sv"
    "$ROOT/rtl/attention/hap_activation_cache_8row.sv"
    "$ROOT/rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv"
    "$ROOT/rtl/mlp/hap_mlp_input_frontend16_compact_cache_registered_ooc_harness.sv"
    "$ROOT/vivado/constraints/mlp_input_frontend16_compact_cache_registered_ooc_150mhz.xdc"
    "$ROOT/vivado/scripts/route_mlp_input_frontend16_compact_cache_registered_ooc.tcl"
    "$ROOT/vivado/scripts/run_mlp_input_frontend16_compact_cache_registered_ooc.sh"
)
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE"

archive() {
    local incoming="$?" final="$?"
    set +e
    final="$incoming"
    sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
    if cmp -s "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE" \
            "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"; then
        printf 'input_sha_stable=1\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
    else
        printf 'input_sha_stable=0\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
        final=1
    fi
    printf 'launcher_exit_status=%s\n' "$final" > \
        "$HAP_REPORT_DIR/launcher_status.txt"
    find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    trap - EXIT
    exit "$final"
}
trap archive EXIT

cd "$HAP_REPORT_DIR/work"
"$VIVADO" -mode batch -notrace \
    -source "$ROOT/vivado/scripts/route_mlp_input_frontend16_compact_cache_registered_ooc.tcl" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"

test -s "$HAP_REPORT_DIR/summary.txt"
grep -qx 'status=REGISTERED_OOC_CAPTURE48_PASS' \
    "$HAP_REPORT_DIR/summary.txt"
grep -qx 'capture_contract_shape=48x256' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'capture_control_nets=48' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'capture_ce_min_loads=256' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'capture_ce_max_loads=256' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'capture_data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
grep -qx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    echo "Vivado log contains ERROR/FATAL after nominal return" >&2
    exit 1
fi
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
cmp "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE" \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
printf 'input_sha_stable=1\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
