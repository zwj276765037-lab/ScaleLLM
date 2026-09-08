#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_ROOT="$ROOT"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
export HAP_REPORT_DIR="$(readlink -m -- "${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_cohort16_context_store_ooc_$STAMP}")"
export HAP_BUILD_DIR="$(readlink -m -- "${HAP_BUILD_DIR:-$ROOT/vivado/build/attention_cohort16_context_store_ooc_$STAMP}")"
RTL="$ROOT/rtl/attention/hap_attention_cohort16_local_stores.sv"
WRAPPER="$ROOT/rtl/attention/hap_attention_cohort16_context_store_ooc_wrapper.sv"
TCL="$ROOT/vivado/scripts/synth_attention_cohort16_context_store_ooc.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_cohort16_context_store_ooc_synth.sh"

[[ -x "$VIVADO" ]] || { printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2; exit 2; }
[[ ! -e "$HAP_REPORT_DIR" ]] || { printf 'evidence directory exists: %s\n' "$HAP_REPORT_DIR" >&2; exit 2; }
[[ ! -e "$HAP_BUILD_DIR" ]] || { printf 'build directory exists: %s\n' "$HAP_BUILD_DIR" >&2; exit 2; }
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; context OOC not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

mkdir "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
inputs=("$RTL" "$WRAPPER" "$TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" | LC_ALL=C sort > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum "${inputs[@]}" | LC_ALL=C sort -k2 > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt"

set +e
cd "$ROOT"
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
set -e
set +e
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e
printf 'vivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$vivado_rc" "$input_rc" > "$HAP_REPORT_DIR/launcher_status.txt"

archive_outputs() {
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}

if (( vivado_rc != 0 || input_rc != 0 )); then
    archive_outputs
    printf 'context-store OOC synthesis failed: %s\n' "$HAP_REPORT_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit "$input_rc"
fi
for required in summary.txt post_synth.dcp post_opt.dcp \
        utilization_post_synth.rpt utilization_post_opt.rpt \
        context_store_post_opt_funcsim.v vivado.log vivado.jou \
        launcher_status.txt input_sha_postcheck.txt; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || {
        archive_outputs
        printf 'missing OOC output: %s\n' "$required" >&2
        exit 1
    }
done
grep -Fqx 'status=ATTENTION_COHORT16_CONTEXT_STORE_OOC_PASS' \
    "$HAP_REPORT_DIR/summary.txt"
for literal in 'context_store_instances=1' 'ramb36e2=44' 'ramb18e2=0' \
        'lutram_primitives=0' 'dsp48e2=0' 'uram288=0' "jobs=$HAP_JOBS"; do
    grep -Fqx "$literal" "$HAP_REPORT_DIR/summary.txt" || {
        archive_outputs
        printf 'OOC summary contract missing: %s\n' "$literal" >&2
        exit 1
    }
done
archive_outputs
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_REPORT_DIR"
