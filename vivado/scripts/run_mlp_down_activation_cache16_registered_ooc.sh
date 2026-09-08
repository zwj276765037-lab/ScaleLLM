#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_down_activation_cache16_registered_ooc_$STAMP}"
mkdir -p "$HAP_REPORT_DIR"

inputs=(
    "$ROOT/rtl/mlp/hap_mlp_down_activation_cache16.sv"
    "$ROOT/rtl/mlp/hap_mlp_down_activation_cache16_registered_ooc_harness.sv"
    "$ROOT/vivado/constraints/mlp_down_activation_cache16_registered_ooc_150mhz.xdc"
    "$ROOT/vivado/scripts/route_mlp_down_activation_cache16_registered_ooc.tcl"
    "$ROOT/vivado/scripts/run_mlp_down_activation_cache16_registered_ooc.sh"
)
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE"

archive() {
    local incoming="$1" final="$1"
    set +e
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
trap 'archive "$?"' EXIT

cd "$ROOT"
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/route_mlp_down_activation_cache16_registered_ooc.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"

for required in summary.txt post_synth.dcp post_opt.dcp post_phys_opt.dcp \
        post_route.dcp timing_summary.rpt route_status.rpt drc.rpt; do
    test -s "$HAP_REPORT_DIR/$required"
done
grep -Fqx 'status=REGISTERED_DOWN_ACTIVATION16_OOC_PASS' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'capture_contract=16x280' "$HAP_REPORT_DIR/summary.txt"
for stage in post_synth post_opt post_phys_opt post_route; do
    grep -Fqx "${stage}_capture_owners=16" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "${stage}_capture_nets=16" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "${stage}_capture_payload_ff=4480" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "${stage}_capture_loads=280/280" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "${stage}_data_bufg=0" "$HAP_REPORT_DIR/summary.txt"
done
grep -Fqx 'clock_buffer_type_override_count=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'forbidden_timing_exception_count=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'unrouted_nets=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'conflict_nets=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'drc_errors=0' "$HAP_REPORT_DIR/summary.txt"
if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
    printf 'Vivado log contains ERROR/FATAL after nominal return\n' >&2
    exit 1
fi
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
cmp "$HAP_REPORT_DIR/INPUT_SHA256SUMS_PRE" \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS_POST"
printf 'input_sha_stable=1\n' > "$HAP_REPORT_DIR/input_sha_status.txt"
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
