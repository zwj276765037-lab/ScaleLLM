#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_projection_core16x16_w8_reuse_congestion_window.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_projection_core16x16_w8_reuse_congestion_window_diagnosis.sh"

if [[ $# -ne 3 ]]; then
    printf 'usage: %s ROUTE_ARTIFACT_DIR LOWER_TILE UPPER_TILE\n' "$0" >&2
    exit 2
fi
ROUTE_DIR="$(readlink -f -- "$1")"
export HAP_WINDOW_LOWER_TILE="$2"
export HAP_WINDOW_UPPER_TILE="$3"
[[ "$HAP_WINDOW_LOWER_TILE" =~ ^[A-Z0-9_]+_X[0-9]+Y[0-9]+$ &&
   "$HAP_WINDOW_UPPER_TILE" =~ ^[A-Z0-9_]+_X[0-9]+Y[0-9]+$ ]] || {
    printf 'window bounds must be exact Vivado tile names\n' >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2; exit 2; }

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; diagnosis not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

export HAP_INPUT_DCP="$ROUTE_DIR/post_route.dcp"
ROUTE_SUMMARY="$ROUTE_DIR/summary.txt"
ROUTE_CONGESTION="$ROUTE_DIR/congestion_post_route.rpt"
ROUTE_LAUNCHER_STATUS="$ROUTE_DIR/launcher_status.txt"
ROUTE_OUTPUT_SHA="$ROUTE_DIR/OUTPUT_SHA256SUMS"
for input in "$HAP_INPUT_DCP" "$ROUTE_SUMMARY" "$ROUTE_CONGESTION" \
        "$ROUTE_LAUNCHER_STATUS" "$ROUTE_OUTPUT_SHA" "$TCL" "$LAUNCHER"; do
    [[ -s "$input" ]] || { printf 'missing diagnosis input: %s\n' "$input" >&2; exit 2; }
done
grep -Fqx 'status=FAIL' "$ROUTE_SUMMARY"
route_level6_count="$(sed -n 's/^level6_or_higher_congestion_windows=//p' "$ROUTE_SUMMARY")"
[[ "$route_level6_count" =~ ^[1-9][0-9]*$ ]] || {
    printf 'route input must contain at least one Level-6 congestion window\n' >&2
    exit 2
}
grep -Fqx 'status=FAIL' "$ROUTE_LAUNCHER_STATUS"
(cd / && sha256sum -c --strict "$ROUTE_OUTPUT_SHA") >/dev/null

diagnostic_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|place_design|phys_opt_design|route_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$diagnostic_code"; then
    printf 'congestion diagnosis contains a forbidden implementation command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_congestion_window_diagnosis_${STAMP}}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_REPORT_DIR" ]] || { printf 'diagnosis output exists: %s\n' "$HAP_REPORT_DIR" >&2; exit 2; }
mkdir "$HAP_REPORT_DIR"

inputs=("$HAP_INPUT_DCP" "$ROUTE_SUMMARY" "$ROUTE_CONGESTION"
    "$ROUTE_LAUNCHER_STATUS" "$ROUTE_OUTPUT_SHA" "$TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_INPUT_DCP" | awk '{print $1}')"
export HAP_INPUT_MANIFEST_SHA256
HAP_INPUT_MANIFEST_SHA256="$(sha256sum -- "$HAP_REPORT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1
printf '%s\n' \
    "launcher_pid=$$" \
    "start_epoch=$(date +%s)" \
    "route_dir=$ROUTE_DIR" \
    "input_dcp=$HAP_INPUT_DCP" \
    "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
    "route_level6_or_higher_congestion_windows=$route_level6_count" \
    "lower_tile=$HAP_WINDOW_LOWER_TILE" \
    "upper_tile=$HAP_WINDOW_UPPER_TILE" \
    > "$HAP_REPORT_DIR/run_metadata.txt"

status=1
vivado_rc=125
input_postcheck_rc=125
manifest_post_match=0
gate_rc=125
archive() {
    set +e
    printf 'end_epoch=%s\n' "$(date +%s)" >> "$HAP_REPORT_DIR/run_metadata.txt"
    printf '%s\n' \
        "status=$([[ "$status" -eq 0 ]] && printf PASS || printf FAIL)" \
        "vivado_exit_code=$vivado_rc" \
        "input_postcheck_exit_code=$input_postcheck_rc" \
        "input_manifest_post_match=$manifest_post_match" \
        "gate_exit_code=$gate_rc" \
        'implementation_commands_run=0' \
        'checkpoint_written=0' \
        > "$HAP_REPORT_DIR/launcher_status.txt"
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 -type f \
        -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}
trap archive EXIT

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
[[ "${#active_batch[@]}" -eq 0 ]] || { printf 'batch Vivado appeared before diagnosis launch\n' >&2; exit 75; }

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/diagnose_projection_core16x16_w8_reuse_congestion_window.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_postcheck_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_REPORT_DIR/INPUT_SHA256SUMS" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
if [[ "$manifest_rc" -eq 0 && "$actual_manifest_sha" == "$HAP_INPUT_MANIFEST_SHA256" ]]; then
    manifest_post_match=1
fi

gate_rc=0
required_outputs=(summary.txt window_cells.tsv window_category_counts.tsv
    window_reference_counts.tsv window_pblock_counts.tsv crossing_nets.tsv
    crossing_net_details.tsv stage_cell_locations.tsv source_group_counts.tsv
    vivado.log vivado.jou)
for required in "${required_outputs[@]}"; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || gate_rc=1
done
if [[ "$vivado_rc" -ne 0 || "$input_postcheck_rc" -ne 0 ||
      "$manifest_post_match" -ne 1 ]]; then
    gate_rc=1
fi
if [[ "$gate_rc" -eq 0 ]]; then
    for literal in \
        'status=PASS' \
        'stage=PROJECTION_REUSE_OOC_ROUTED_CONGESTION_WINDOW_DIAGNOSIS' \
        'evidence_class=READ_ONLY_ROUTED_DCP_DIAGNOSIS' \
        "input_dcp=$HAP_INPUT_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
        "lower_tile=$HAP_WINDOW_LOWER_TILE" \
        "upper_tile=$HAP_WINDOW_UPPER_TILE" \
        'pblock_count=10' \
        'region0_primitives=36644' \
        'region1_primitives=70469' \
        'region2_primitives=70457' \
        'region3_primitives=36649' \
        'activation_source_universe=8192' \
        'zero_point_source_universe=256' \
        'weight_source_universe=8192' \
        'implementation_commands_run=0' \
        'checkpoint_written=0'; do
        grep -Fqx -- "$literal" "$HAP_REPORT_DIR/summary.txt" || gate_rc=1
    done
fi
if [[ "$gate_rc" -ne 0 ]]; then
    printf 'congestion-window diagnosis failed; evidence: %s\n' "$HAP_REPORT_DIR" >&2
    exit 1
fi
status=0
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
