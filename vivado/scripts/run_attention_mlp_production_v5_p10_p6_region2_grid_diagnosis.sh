#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p6_region2_grid.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p6_region2_grid_diagnosis.sh"
FAILED_DIR="$ROOT/vivado/reports/production_v5_p10_p6_place_20260905_mission0088_lockstep_v1"
DCP="$FAILED_DIR/post_place_diagnostic_only.dcp"
FAILED_OUTPUT="$FAILED_DIR/OUTPUT_SHA256SUMS"
EXPECTED_DCP_SHA=1aa5b274ae73c668993cb4fc3ff410c80a40d55b51c69f9491c00b1a0c208ba3
EXPECTED_FAILED_OUTPUT_SHA=c416defdc53a979f75ce6d89355c3de8c98b9e9e4572a34a790b1c85d86267d8
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_P6_GRID_DIR="${HAP_P6_GRID_DIR:-$ROOT/vivado/reports/production_v5_p10_p6_region2_grid_$STAMP}"
export HAP_JOBS="${HAP_JOBS:-32}"

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ "$HAP_JOBS" == 32 ]] || { printf 'HAP_JOBS must equal 32\n' >&2; exit 2; }
for file in "$VIVADO" "$TCL" "$LAUNCHER" "$DCP" "$FAILED_OUTPUT"; do
    [[ -s "$file" ]] || { printf 'missing grid diagnostic input: %s\n' "$file" >&2; exit 2; }
done
[[ "$(sha256sum "$DCP" | awk '{print $1}')" == "$EXPECTED_DCP_SHA" ]]
[[ "$(sha256sum "$FAILED_OUTPUT" | awk '{print $1}')" == \
    "$EXPECTED_FAILED_OUTPUT_SHA" ]]
(cd / && sha256sum -c --strict "$FAILED_OUTPUT") >/dev/null

code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|create_pblock|resize_pblock)([^[:alnum:]_]|$)' \
        <<<"$code"; then
    printf 'region2 grid diagnosis contains a forbidden command\n' >&2
    exit 2
fi
mapfile -t active < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; grid diagnosis not started:\n' >&2
    printf '  %s\n' "${active[@]}" >&2
    exit 75
fi
[[ ! -e "$HAP_P6_GRID_DIR" ]] || {
    printf 'grid diagnostic directory exists: %s\n' "$HAP_P6_GRID_DIR" >&2
    exit 2
}
mkdir "$HAP_P6_GRID_DIR"
printf '%s\n' "$DCP" "$FAILED_OUTPUT" "$TCL" "$LAUNCHER" \
    > "$HAP_P6_GRID_DIR/INPUT_FILES"
sha256sum -- "$DCP" "$FAILED_OUTPUT" "$TCL" "$LAUNCHER" \
    > "$HAP_P6_GRID_DIR/INPUT_SHA256SUMS"
export HAP_P6_GRID_DCP="$DCP"
export HAP_P6_GRID_DCP_SHA256="$EXPECTED_DCP_SHA"
export HAP_P6_GRID_FAILED_OUTPUT_SHA="$FAILED_OUTPUT"
export HAP_P6_GRID_FAILED_OUTPUT_SHA256="$EXPECTED_FAILED_OUTPUT_SHA"
export HAP_P6_GRID_INPUT_SHA="$HAP_P6_GRID_DIR/INPUT_SHA256SUMS"
export HAP_P6_GRID_INPUT_SHA256
HAP_P6_GRID_INPUT_SHA256="$(sha256sum "$HAP_P6_GRID_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P6_GRID_INPUT_SHA") \
    > "$HAP_P6_GRID_DIR/input_sha_precheck.txt" 2>&1

final_rc=1
vivado_rc=255
input_rc=125
archive() {
    local trap_rc="$?"
    trap - EXIT
    [[ "$trap_rc" -eq 0 ]] || final_rc="$trap_rc"
    printf '%s\n' "status=$([[ "$final_rc" -eq 0 ]] && echo PASS || echo FAIL)" \
        "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
        "input_sha_recheck_exit_code=$input_rc" 'floorplan_mutated=0' \
        'implementation_commands_run=0' 'checkpoint_written=0' \
        'route_eligible=0' > "$HAP_P6_GRID_DIR/launcher_status.txt"
    find "$HAP_P6_GRID_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P6_GRID_DIR/OUTPUT_SHA256SUMS" || true
    exit "$final_rc"
}
trap archive EXIT

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P6_GRID_DIR/vivado.log" -journal "$HAP_P6_GRID_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P6_GRID_INPUT_SHA") \
    > "$HAP_P6_GRID_DIR/input_sha_postcheck.txt" 2>&1
input_rc=$?
set -e
if [[ "$vivado_rc" -eq 0 && "$input_rc" -eq 0 ]]; then
    final_rc=0
    for file in summary.txt clock_region_capacity.tsv \
            clock_region_resources.tsv vivado.log vivado.jou; do
        [[ -s "$HAP_P6_GRID_DIR/$file" ]] || final_rc=1
    done
    for literal in status=V5_P10_P6_REGION2_GRID_DIAGNOSIS_PASS \
            pblock_count=25 dsp48e2=5453 uram288=752 \
            region2_primitives=68799 region2_dsp48e2=544 \
            floorplan_mutated=0 implementation_commands_run=0 \
            checkpoint_written=0 route_eligible=0; do
        grep -Fqx "$literal" "$HAP_P6_GRID_DIR/summary.txt" || final_rc=1
    done
    grep -Eq '^(ERROR|FATAL):' "$HAP_P6_GRID_DIR/vivado.log" && final_rc=1
fi
[[ "$final_rc" -eq 0 ]] || exit 1
printf 'P6_REGION2_GRID_DIAGNOSIS_PASS\n%s\n' "$HAP_P6_GRID_DIR"
