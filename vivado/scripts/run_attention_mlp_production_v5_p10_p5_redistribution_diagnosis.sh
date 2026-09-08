#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p5_redistribution.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p5_redistribution_diagnosis.sh"
FAILED_DIR="$ROOT/vivado/reports/production_v5_p10_p5_place_20260905_mission0079_v2_r3"
DCP="$FAILED_DIR/post_place_diagnostic_only.dcp"
FAILED_OUTPUT_SHA="$FAILED_DIR/OUTPUT_SHA256SUMS"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P6_LIB="$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
EXPECTED_DCP_SHA=935742240d346a9c3bdbd4ad5d8b22a04c50ecb17256caad1ee76f47f8ceb830
EXPECTED_FAILED_OUTPUT_SHA=8c74a40be7cb60a548fa6e8a64c4fcdef95d39e4900cfa6bca2c3659f842dacb
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_P5_DIAG_DIR="${HAP_P5_DIAG_DIR:-$ROOT/vivado/reports/production_v5_p10_p5_redistribution_diagnosis_$STAMP}"
export HAP_P5_DIAG_DCP="$DCP"
export HAP_P5_DIAG_DCP_SHA256="$EXPECTED_DCP_SHA"
export HAP_P5_FAILED_OUTPUT_SHA="$FAILED_OUTPUT_SHA"
export HAP_P5_FAILED_OUTPUT_SHA256="$EXPECTED_FAILED_OUTPUT_SHA"
export HAP_P5_DIAG_LAUNCHER="$LAUNCHER"
export HAP_P5_DIAG_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_P5_DIAG_P5_LIB="$P5_LIB"
export HAP_P5_DIAG_P6_LIB="$P6_LIB"
export HAP_JOBS="${HAP_JOBS:-32}"

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P5 diagnosis requires HAP_JOBS=32\n' >&2
    exit 2
}
for path in "$VIVADO" "$TCL" "$LAUNCHER" "$DCP" "$FAILED_OUTPUT_SHA" \
        "$SELECTOR_LIB" "$P5_LIB" "$P6_LIB"; do
    [[ -s "$path" ]] || { printf 'missing P5 diagnosis input: %s\n' "$path" >&2; exit 2; }
done
[[ "$(sha256sum "$DCP" | awk '{print $1}')" == "$EXPECTED_DCP_SHA" ]] || {
    printf 'P5 diagnostic DCP SHA mismatch\n' >&2
    exit 2
}
[[ "$(sha256sum "$FAILED_OUTPUT_SHA" | awk '{print $1}')" == \
        "$EXPECTED_FAILED_OUTPUT_SHA" ]] || {
    printf 'P5 failed output manifest SHA mismatch\n' >&2
    exit 2
}
(cd / && sha256sum -c --strict "$FAILED_OUTPUT_SHA" >/dev/null)

code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$code"; then
    printf 'P5 diagnosis contains a forbidden implementation command\n' >&2
    exit 2
fi
mapfile -t active < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; diagnosis not started:\n' >&2
    printf '  %s\n' "${active[@]}" >&2
    exit 75
fi

[[ ! -e "$HAP_P5_DIAG_DIR" ]] || {
    printf 'P5 diagnosis directory exists: %s\n' "$HAP_P5_DIAG_DIR" >&2
    exit 2
}
mkdir "$HAP_P5_DIAG_DIR"
inputs=("$DCP" "$FAILED_OUTPUT_SHA" "$TCL" "$LAUNCHER" \
    "$SELECTOR_LIB" "$P5_LIB" "$P6_LIB")
printf '%s\n' "${inputs[@]}" > "$HAP_P5_DIAG_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P5_DIAG_DIR/INPUT_SHA256SUMS"
export HAP_P5_DIAG_INPUT_SHA="$HAP_P5_DIAG_DIR/INPUT_SHA256SUMS"
export HAP_P5_DIAG_INPUT_MANIFEST_SHA256
HAP_P5_DIAG_INPUT_MANIFEST_SHA256="$(sha256sum \
    "$HAP_P5_DIAG_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P5_DIAG_INPUT_SHA") \
    > "$HAP_P5_DIAG_DIR/input_sha_precheck.txt" 2>&1

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
        > "$HAP_P5_DIAG_DIR/launcher_status.txt"
}
archive() {
    local trap_rc="$?"
    trap - EXIT
    [[ "$trap_rc" -eq 0 ]] || final_rc="$trap_rc"
    write_status || final_rc=96
    find "$HAP_P5_DIAG_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P5_DIAG_DIR/OUTPUT_SHA256SUMS" || final_rc=97
    write_status || true
    find "$HAP_P5_DIAG_DIR" -maxdepth 1 -type f -size +0c \
        ! -name OUTPUT_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum \
        > "$HAP_P5_DIAG_DIR/OUTPUT_SHA256SUMS" || true
    exit "$final_rc"
}
trap archive EXIT

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P5_DIAG_DIR/vivado.log" \
    -journal "$HAP_P5_DIAG_DIR/vivado.jou"
vivado_exit_code=$?
(cd / && sha256sum -c --strict "$HAP_P5_DIAG_INPUT_SHA") \
    > "$HAP_P5_DIAG_DIR/input_sha_postcheck.txt" 2>&1
input_sha_recheck_exit_code=$?
set -e

required=(summary.txt pblock_ranges.tsv hierarchy_resources.tsv
    postprocess_bank_resources.tsv window_category_counts.tsv
    window_reference_counts.tsv redistribution_boundary_cost.tsv
    p6_postprocess_plan.txt
    timing_post_place.rpt timing_setup_paths.rpt timing_hold_paths.rpt
    vivado.log vivado.jou)
if [[ "$vivado_exit_code" -eq 0 && "$input_sha_recheck_exit_code" -eq 0 ]]; then
    final_rc=0
    for file in "${required[@]}"; do
        [[ -s "$HAP_P5_DIAG_DIR/$file" ]] || final_rc=1
    done
    expected=(
        'status=V5_P10_P5_REDISTRIBUTION_DIAGNOSIS_PASS'
        'evidence_class=READ_ONLY_REJECTED_P5_PLACEMENT'
        'failed_output_entries=25' 'pblock_count=23' 'dsp48e2=5453'
        'input_manifest_entries=7'
        'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
        'p6_slr0_row_primitives=10696'
        'p6_center_row_primitives=21392'
        'p6_slr2_row_primitives=10696'
        'uram288=752' 'slr_dsp48e2=1862 1781 1810'
        'slr_uram288=224 224 304' 'level6_windows_profiled=8'
        'floorplan_mutated=0' 'implementation_commands_run=0'
        'checkpoint_written=0' 'route_eligible=0')
    for literal in "${expected[@]}"; do
        [[ "$(grep -Fxc -- "$literal" "$HAP_P5_DIAG_DIR/summary.txt" || true)" -eq 1 ]] || final_rc=1
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_P5_DIAG_DIR/vivado.log"; then
        final_rc=1
    fi
fi
[[ "$final_rc" -eq 0 ]] || exit 1
printf 'P5_REDISTRIBUTION_DIAGNOSIS_PASS\n%s\n' "$HAP_P5_DIAG_DIR"
