#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; MLP AXI-Lite OOC not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}
require_free_batch_slot

requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_axil_control_ooc_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested_report")"
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'MLP AXI-Lite OOC report directory exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

RTL="$ROOT/rtl/integration/hap_mlp_axil_control.sv"
HARNESS="$ROOT/rtl/integration/hap_mlp_axil_control_registered_ooc_harness.sv"
XDC="$ROOT/vivado/constraints/mlp_axil_control_ooc_150mhz.xdc"
TCL="$ROOT/vivado/scripts/route_mlp_axil_control_ooc.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_mlp_axil_control_ooc.sh"
for input in "$RTL" "$HARNESS" "$XDC" "$TCL" "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty MLP AXI-Lite OOC input: %s\n' "$input" >&2
        exit 2
    }
done
export HAP_INPUT_SHA="$HAP_REPORT_DIR/INPUT_SHA256SUMS"
printf '%s\n' "$RTL" "$HARNESS" "$XDC" "$TCL" "$LAUNCHER" \
    > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "$RTL" "$HARNESS" "$XDC" "$TCL" "$LAUNCHER" \
    > "$HAP_INPUT_SHA"
export HAP_INPUT_MANIFEST_SHA256
HAP_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_INPUT_SHA") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1
printf '%s\n' \
    "launcher_pid=$$" \
    "start_epoch=$(date +%s)" \
    "jobs=$HAP_JOBS" \
    "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
    > "$HAP_REPORT_DIR/run_metadata.txt"

require_free_batch_slot
cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/route_mlp_axil_control_ooc.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_INPUT_SHA") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi

gate_rc=0
(( vivado_rc == 0 && input_rc == 0 && manifest_match == 1 )) || gate_rc=1
for required in summary.txt post_route.dcp timing_summary.rpt \
        utilization.rpt route_status.rpt drc.rpt vivado.log vivado.jou \
        input_sha_precheck.txt input_sha_postcheck.txt run_metadata.txt \
        INPUT_FILES INPUT_SHA256SUMS; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || {
        printf 'missing or empty MLP AXI-Lite OOC output: %s\n' "$required" >&2
        gate_rc=1
    }
done
if (( gate_rc == 0 )); then
    grep -Fqx 'status=PASS' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx "jobs=$HAP_JOBS" "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
        "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'top=hap_mlp_axil_control_registered_ooc_harness' \
        "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'source_proxy_ff=2335' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'sink_proxy_ff=409' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'dsp48e2=0' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'timing_coverage_ok=1' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'route_clean=1' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'unrouted_nets=0' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    grep -Fqx 'drc_errors=0' "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
fi
launcher_status=FAIL
(( gate_rc == 0 )) && launcher_status=PASS
printf '%s\n' \
    "status=$launcher_status" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$input_rc" \
    "input_manifest_post_match=$manifest_match" \
    "gate_exit_code=$gate_rc" \
    > "$HAP_REPORT_DIR/launcher_status.txt"
printf 'end_epoch=%s\n' "$(date +%s)" >> "$HAP_REPORT_DIR/run_metadata.txt"
mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
if (( gate_rc != 0 )); then
    printf 'MLP AXI-Lite OOC failed; evidence retained in %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 1
fi
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
