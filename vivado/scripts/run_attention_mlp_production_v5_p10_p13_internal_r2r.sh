#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
DIAG="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p13_internal_r2r.tcl"
P10_PROC_LIB="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p13_internal_r2r.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 3 ]] || {
    printf 'usage: %s P13_DIAGNOSTIC_DCP MISSION0141_OUTPUT_SHA256SUMS MISSION0143_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || { printf 'P13 internal timing diagnosis requires HAP_JOBS=32\n' >&2; exit 2; }
export HAP_P13_R2R_DCP="$(readlink -e -- "$1")"
export HAP_P13_R2R_PLACE_OUTPUT_SHA="$(readlink -e -- "$2")"
export HAP_P13_R2R_TIMING_OUTPUT_SHA="$(readlink -e -- "$3")"
requested="${HAP_P13_R2R_DIR:-$ROOT/vivado/reports/production_v5_p10_p13_internal_r2r_${STAMP}}"
export HAP_P13_R2R_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P13_R2R_DIR" ]] || {
    printf 'P13 internal timing directory exists: %s\n' "$HAP_P13_R2R_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P13 internal timing not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

mkdir "$HAP_P13_R2R_DIR"
export HAP_P13_R2R_P10_PROC_LIB="$P10_PROC_LIB"
export HAP_P13_R2R_LAUNCHER="$LAUNCHER"
inputs=("$HAP_P13_R2R_DCP" "$HAP_P13_R2R_PLACE_OUTPUT_SHA" \
    "$HAP_P13_R2R_TIMING_OUTPUT_SHA" "$P10_PROC_LIB" "$DIAG" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_P13_R2R_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P13_R2R_DIR/INPUT_SHA256SUMS"
export HAP_P13_R2R_INPUT_SHA="$HAP_P13_R2R_DIR/INPUT_SHA256SUMS"
export HAP_P13_R2R_INPUT_MANIFEST_SHA256
HAP_P13_R2R_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_P13_R2R_INPUT_SHA" | awk '{print $1}')"
export HAP_P13_R2R_DCP_SHA256
HAP_P13_R2R_DCP_SHA256="$(sha256sum -- "$HAP_P13_R2R_DCP" | awk '{print $1}')"
export HAP_P13_R2R_PLACE_OUTPUT_SHA256
HAP_P13_R2R_PLACE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P13_R2R_PLACE_OUTPUT_SHA" | awk '{print $1}')"
export HAP_P13_R2R_TIMING_OUTPUT_SHA256
HAP_P13_R2R_TIMING_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P13_R2R_TIMING_OUTPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P13_R2R_INPUT_SHA") \
    > "$HAP_P13_R2R_DIR/input_sha_precheck.txt" 2>&1

set +e
"$VIVADO" -mode batch -notrace -source "$DIAG" \
    -log "$HAP_P13_R2R_DIR/vivado.log" \
    -journal "$HAP_P13_R2R_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P13_R2R_INPUT_SHA") \
    > "$HAP_P13_R2R_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

status=FAIL
if (( vivado_rc == 0 && input_rc == 0 )) && \
   [[ -s "$HAP_P13_R2R_DIR/summary.txt" ]] && \
   grep -Fqx 'status=V5_P10_P13_INTERNAL_R2R_TIMING_DIAGNOSIS_PASS' \
        "$HAP_P13_R2R_DIR/summary.txt"; then
    status=PASS
fi
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" \
    > "$HAP_P13_R2R_DIR/launcher_status.txt"
printf 'implementation_commands_run=0\ncheckpoint_written=0\nroute_eligible=0\n' \
    >> "$HAP_P13_R2R_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_P13_R2R_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P13_R2R_DIR/OUTPUT_SHA256SUMS"
if [[ "$status" != PASS ]]; then
    printf 'P13 internal timing diagnosis failed; evidence: %s\n' "$HAP_P13_R2R_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
fi
for literal in source_lineage_verified=1 top_level_port_paths_included=0 \
        floorplan_mutated=0 implementation_commands_run=0 \
        checkpoint_written=0 route_eligible=0; do
    grep -Fqx -- "$literal" "$HAP_P13_R2R_DIR/summary.txt"
done
(cd / && sha256sum -c --strict "$HAP_P13_R2R_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_P13_R2R_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_P13_R2R_DIR"
