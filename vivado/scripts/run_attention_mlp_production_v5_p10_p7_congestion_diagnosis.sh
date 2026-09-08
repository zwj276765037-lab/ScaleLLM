#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p7_congestion.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p7_congestion_diagnosis.sh"
FAILED_DIR="$ROOT/vivado/reports/production_v5_p10_p7_place_20260905_mission0095_rowsplit_v1"
DCP="$FAILED_DIR/post_place_diagnostic_only.dcp"
FAILED_OUTPUT_SHA="$FAILED_DIR/OUTPUT_SHA256SUMS"
EXPECTED_DCP_SHA=f230de63e683afba7e87342ab2914b6f6f7252701fc0446cba3d8ec61a459c3b
EXPECTED_FAILED_OUTPUT_SHA=f941467ad68ac8f2734177e67f012e5d8d849001635b74f9fa92abdafb31e410
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_P7_DIAG_DIR="${HAP_P7_DIAG_DIR:-$ROOT/vivado/reports/production_v5_p10_p7_congestion_diagnosis_$STAMP}"
export HAP_P7_DIAG_DCP="$DCP"
export HAP_P7_DIAG_DCP_SHA256="$EXPECTED_DCP_SHA"
export HAP_P7_FAILED_OUTPUT_SHA="$FAILED_OUTPUT_SHA"
export HAP_P7_FAILED_OUTPUT_SHA256="$EXPECTED_FAILED_OUTPUT_SHA"
export HAP_P7_DIAG_LAUNCHER="$LAUNCHER"
export HAP_JOBS="${HAP_JOBS:-32}"

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P7 diagnosis requires HAP_JOBS=32\n' >&2
    exit 2
}
for path in "$VIVADO" "$TCL" "$LAUNCHER" "$DCP" "$FAILED_OUTPUT_SHA"; do
    [[ -s "$path" ]] || { printf 'missing P7 diagnosis input: %s\n' "$path" >&2; exit 2; }
done
[[ "$(sha256sum "$DCP" | awk '{print $1}')" == "$EXPECTED_DCP_SHA" ]] || {
    printf 'P7 diagnostic DCP SHA mismatch\n' >&2
    exit 2
}
[[ "$(sha256sum "$FAILED_OUTPUT_SHA" | awk '{print $1}')" == \
        "$EXPECTED_FAILED_OUTPUT_SHA" ]] || {
    printf 'P7 failed output manifest SHA mismatch\n' >&2
    exit 2
}
(cd / && sha256sum -c --strict "$FAILED_OUTPUT_SHA" >/dev/null)

code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eqi '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|write_bitstream|create_pblock|resize_pblock|add_cells_to_pblock|delete_pblocks)([^[:alnum:]_]|$)' \
        <<<"$code"; then
    printf 'P7 diagnosis contains a forbidden implementation command\n' >&2
    exit 2
fi
mapfile -t active < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; diagnosis not started:\n' >&2
    printf '  %s\n' "${active[@]}" >&2
    exit 75
fi

[[ ! -e "$HAP_P7_DIAG_DIR" ]] || {
    printf 'P7 diagnosis directory exists: %s\n' "$HAP_P7_DIAG_DIR" >&2
    exit 2
}
mkdir "$HAP_P7_DIAG_DIR"
inputs=("$DCP" "$FAILED_OUTPUT_SHA" "$TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_P7_DIAG_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P7_DIAG_DIR/INPUT_SHA256SUMS"
export HAP_P7_DIAG_INPUT_SHA="$HAP_P7_DIAG_DIR/INPUT_SHA256SUMS"
export HAP_P7_DIAG_INPUT_MANIFEST_SHA256
HAP_P7_DIAG_INPUT_MANIFEST_SHA256="$(sha256sum \
    "$HAP_P7_DIAG_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P7_DIAG_INPUT_SHA") \
    > "$HAP_P7_DIAG_DIR/input_sha_precheck.txt" 2>&1

final_rc=1
vivado_exit_code=255
input_sha_recheck_exit_code=125
write_status() {
    local status=FAIL
    [[ "$final_rc" -eq 0 ]] && status=PASS
    printf '%s\n' "status=$status" "final_exit_code=$final_rc" \
        "vivado_exit_code=$vivado_exit_code" \
        "input_sha_recheck_exit_code=$input_sha_recheck_exit_code" \
        'floorplan_mutated=0' 'implementation_commands_run=0' \
        'checkpoint_written=0' 'route_eligible=0' \
        > "$HAP_P7_DIAG_DIR/launcher_status.txt"
}
archive() {
    local trap_rc="$?"
    trap - EXIT
    [[ "$trap_rc" -eq 0 ]] || final_rc="$trap_rc"
    write_status || final_rc=96
    find "$HAP_P7_DIAG_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P7_DIAG_DIR/OUTPUT_SHA256SUMS" || final_rc=97
    write_status || true
    find "$HAP_P7_DIAG_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P7_DIAG_DIR/OUTPUT_SHA256SUMS" || true
    exit "$final_rc"
}
trap archive EXIT

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P7_DIAG_DIR/vivado.log" \
    -journal "$HAP_P7_DIAG_DIR/vivado.jou"
vivado_exit_code=$?
(cd / && sha256sum -c --strict "$HAP_P7_DIAG_INPUT_SHA") \
    > "$HAP_P7_DIAG_DIR/input_sha_postcheck.txt" 2>&1
input_sha_recheck_exit_code=$?
set -e

required=(summary.txt pblock_ranges.tsv hierarchy_geometry.tsv
    window_category_counts.tsv window_reference_counts.tsv
    utilization_slr_post_place.rpt utilization_hier_post_place.rpt
    timing_post_place.rpt timing_setup_paths.rpt timing_hold_paths.rpt
    vivado.log vivado.jou)
if [[ "$vivado_exit_code" -eq 0 && "$input_sha_recheck_exit_code" -eq 0 ]]; then
    final_rc=0
    for file in "${required[@]}"; do
        [[ -s "$HAP_P7_DIAG_DIR/$file" ]] || final_rc=1
    done
    expected=(
        'status=V5_P10_P7_CONGESTION_DIAGNOSIS_PASS'
        'evidence_class=READ_ONLY_REJECTED_P7_PLACEMENT'
        'failed_output_entries=29' 'pblock_count=27' 'dsp48e2=5453'
        'uram288=752' 'mlp_kernel_dsp48e2=3072'
        'slr_dsp48e2=1862 1781 1810' 'slr_uram288=224 224 304'
        'region2_rows0_3_primitives=26800'
        'region2_rows4_7_primitives=26800' 'level6_windows_profiled=8'
        'floorplan_mutated=0' 'implementation_commands_run=0'
        'checkpoint_written=0' 'route_eligible=0')
    for literal in "${expected[@]}"; do
        [[ "$(grep -Fxc -- "$literal" "$HAP_P7_DIAG_DIR/summary.txt" || true)" -eq 1 ]] || final_rc=1
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_P7_DIAG_DIR/vivado.log"; then
        final_rc=1
    fi
fi
[[ "$final_rc" -eq 0 ]] || exit 1
printf 'P7_CONGESTION_DIAGNOSIS_PASS\n%s\n' "$HAP_P7_DIAG_DIR"
