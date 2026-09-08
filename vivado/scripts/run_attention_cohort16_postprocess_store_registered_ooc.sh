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
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; postprocess route not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

export HAP_REPORT_DIR="$(readlink -m -- "${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_cohort16_postprocess_store_registered_ooc_$STAMP}")"
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'postprocess OOC report directory exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

RTL="$ROOT/rtl/attention/hap_attention_cohort16_local_stores.sv"
HARNESS="$ROOT/rtl/attention/hap_attention_cohort16_postprocess_store_registered_ooc_harness.sv"
XDC="$ROOT/vivado/constraints/attention_cohort16_postprocess_store_registered_ooc_150mhz.xdc"
TCL="$ROOT/vivado/scripts/route_attention_cohort16_postprocess_store_registered_ooc.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_cohort16_postprocess_store_registered_ooc.sh"
inputs=("$RTL" "$HARNESS" "$XDC" "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || { printf 'missing OOC input: %s\n' "$input" >&2; exit 2; }
done
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
export HAP_INPUT_MANIFEST_SHA256
HAP_INPUT_MANIFEST_SHA256="$(sha256sum "$HAP_REPORT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1

set +e
cd "$ROOT"
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

gate_rc=0
(( vivado_rc == 0 && input_rc == 0 )) || gate_rc=1
for required in summary.txt post_route.dcp timing_summary.rpt utilization.rpt \
        route_status.rpt drc.rpt congestion_post_place.rpt \
        congestion_post_route.rpt vivado.log vivado.jou \
        input_sha_precheck.txt input_sha_postcheck.txt INPUT_FILES \
        INPUT_SHA256SUMS; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || gate_rc=1
done
if (( gate_rc == 0 )); then
    for literal in 'status=PASS' 'source_proxy_ff=3151' 'sink_proxy_ff=3120' \
            'row_bank_instances=16' 'dut_ff_primitives=24580' \
            'dsp48e2=0' 'uram288=0' 'data_bufg=0' \
            'timing_coverage_ok=1' 'placer_level6_or_higher=0' \
            'router_level6_or_higher=0' 'route_clean=1' \
            'unrouted_nets=0' 'drc_errors=0' "jobs=$HAP_JOBS" \
            "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256"; do
        grep -Fqx "$literal" "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    done
fi
status=FAIL
(( gate_rc == 0 )) && status=PASS
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\ngate_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" "$gate_rc" \
    > "$HAP_REPORT_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
(( gate_rc == 0 )) || {
    printf 'postprocess registered OOC failed: %s\n' "$HAP_REPORT_DIR" >&2
    exit 1
}
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS")
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
