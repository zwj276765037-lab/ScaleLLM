#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
MAP="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p8_level6_map_v3.tcl"
P10_PROC_LIB="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p8_level6_map_v3.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 2 ]] || {
    printf 'usage: %s P8_DIAGNOSTIC_DCP MISSION0114_OUTPUT_SHA256SUMS\n' \
        "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_P8_LEVEL6_DCP="$(readlink -e -- "$1")"
export HAP_P8_LEVEL6_DIAG_OUTPUT_SHA="$(readlink -e -- "$2")"
requested="${HAP_P8_LEVEL6_DIR:-$ROOT/vivado/reports/production_v5_p10_p8_level6_map_$STAMP}"
export HAP_P8_LEVEL6_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P8_LEVEL6_DIR" ]] || {
    printf 'P8 Level-6 map directory exists: %s\n' "$HAP_P8_LEVEL6_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P8 Level-6 map not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

mkdir "$HAP_P8_LEVEL6_DIR"
export HAP_P8_LEVEL6_P10_PROC_LIB="$P10_PROC_LIB"
export HAP_P8_LEVEL6_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_P8_LEVEL6_LAUNCHER="$LAUNCHER"
inputs=("$HAP_P8_LEVEL6_DCP" "$HAP_P8_LEVEL6_DIAG_OUTPUT_SHA" \
    "$P10_PROC_LIB" "$SELECTOR_LIB" "$MAP" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_P8_LEVEL6_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P8_LEVEL6_DIR/INPUT_SHA256SUMS"
export HAP_P8_LEVEL6_INPUT_SHA="$HAP_P8_LEVEL6_DIR/INPUT_SHA256SUMS"
export HAP_P8_LEVEL6_INPUT_MANIFEST_SHA256
HAP_P8_LEVEL6_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_P8_LEVEL6_INPUT_SHA" | awk '{print $1}')"
export HAP_P8_LEVEL6_DCP_SHA256
HAP_P8_LEVEL6_DCP_SHA256="$(sha256sum -- "$HAP_P8_LEVEL6_DCP" | awk '{print $1}')"
export HAP_P8_LEVEL6_DIAG_OUTPUT_SHA256
HAP_P8_LEVEL6_DIAG_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P8_LEVEL6_DIAG_OUTPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P8_LEVEL6_INPUT_SHA") \
    > "$HAP_P8_LEVEL6_DIR/input_sha_precheck.txt" 2>&1

set +e
env HAP_JOBS=32 "$VIVADO" -mode batch -notrace -source "$MAP" \
    -log "$HAP_P8_LEVEL6_DIR/vivado.log" \
    -journal "$HAP_P8_LEVEL6_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P8_LEVEL6_INPUT_SHA") \
    > "$HAP_P8_LEVEL6_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e

status=FAIL
if (( vivado_rc == 0 && input_rc == 0 )) && \
   [[ -s "$HAP_P8_LEVEL6_DIR/summary.txt" ]] && \
   grep -Fqx 'status=V5_P10_P8_LEVEL6_PHYSICAL_MAP_PASS' \
        "$HAP_P8_LEVEL6_DIR/summary.txt"; then
    status=PASS
fi
printf 'status=%s\nvivado_exit_code=%d\ninput_sha_recheck_exit_code=%d\n' \
    "$status" "$vivado_rc" "$input_rc" \
    > "$HAP_P8_LEVEL6_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_P8_LEVEL6_DIR" -maxdepth 1 -type f \
    -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P8_LEVEL6_DIR/OUTPUT_SHA256SUMS"
if [[ "$status" != PASS ]]; then
    printf 'P8 Level-6 map failed; evidence: %s\n' "$HAP_P8_LEVEL6_DIR" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
fi
for literal in source_lineage_verified=1 level6_windows_profiled=7 \
        swiglu_quantizer_roots=4 postprocess_row_roots=16 \
        slr1_clock_regions_profiled=30 \
        p9_moving_postprocess_primitives=10696 \
        quantizer3_primitives=11186 \
        floorplan_mutated=0 implementation_commands_run=0 \
        checkpoint_written=0 route_eligible=0; do
    grep -Fqx -- "$literal" "$HAP_P8_LEVEL6_DIR/summary.txt"
done
(cd / && sha256sum -c --strict "$HAP_P8_LEVEL6_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict "$HAP_P8_LEVEL6_DIR/OUTPUT_SHA256SUMS")
printf '%s\n' "$HAP_P8_LEVEL6_DIR"

exit 0
