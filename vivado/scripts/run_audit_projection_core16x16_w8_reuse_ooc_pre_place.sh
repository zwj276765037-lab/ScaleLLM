#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_JOBS="${HAP_JOBS:-32}"
if ! [[ "$HAP_JOBS" =~ ^[0-9]+$ ]] ||
        (( HAP_JOBS < 1 || HAP_JOBS > 32 )); then
    printf 'HAP_JOBS must be an integer in 1..32, got %q\n' \
        "$HAP_JOBS" >&2
    exit 2
fi
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}

require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; Attention pre-place not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}
require_free_batch_slot

: "${HAP_INPUT_DCP:?set HAP_INPUT_DCP to the fresh post-synth checkpoint}"
export HAP_INPUT_DCP="$(readlink -m -- "$HAP_INPUT_DCP")"
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_ooc_pre_place_audit_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested_report")"
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'Attention pre-place report directory exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

FLOORPLAN="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
TCL="$ROOT/vivado/scripts/audit_projection_core16x16_w8_reuse_ooc_pre_place.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_audit_projection_core16x16_w8_reuse_ooc_pre_place.sh"
inputs=("$HAP_INPUT_DCP" "$FLOORPLAN" "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty Attention pre-place input: %s\n' "$input" >&2
        exit 2
    }
done
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_INPUT_DCP" | awk '{print $1}')"
export HAP_INPUT_MANIFEST_SHA256
HAP_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1
printf '%s\n' \
    "launcher_pid=$$" \
    "start_epoch=$(date +%s)" \
    "jobs=$HAP_JOBS" \
    "input_dcp=$HAP_INPUT_DCP" \
    "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
    > "$HAP_REPORT_DIR/run_metadata.txt"

status=1
vivado_rc=125
input_postcheck_rc=125
manifest_post_match=0
gate_rc=125
archive() {
    set +e
    printf 'end_epoch=%s\n' "$(date +%s)" >> \
        "$HAP_REPORT_DIR/run_metadata.txt"
    printf '%s\n' \
        "status=$([[ "$status" -eq 0 ]] && printf PASS || printf FAIL)" \
        "vivado_exit_code=$vivado_rc" \
        "input_postcheck_exit_code=$input_postcheck_rc" \
        "input_manifest_post_match=$manifest_post_match" \
        "gate_exit_code=$gate_rc" \
        > "$HAP_REPORT_DIR/launcher_status.txt"
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}
trap archive EXIT

# Close the check-to-launch window after all evidence inputs are frozen.
require_free_batch_slot
cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_projection_core16x16_w8_reuse_ooc_pre_place.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_postcheck_rc=$?
actual_manifest_sha="$(sha256sum -- \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_INPUT_MANIFEST_SHA256" ]]; then
    manifest_post_match=1
fi

gate_rc=0
if [[ "$vivado_rc" -ne 0 || "$input_postcheck_rc" -ne 0 || \
      "$manifest_post_match" -ne 1 ]]; then
    gate_rc=1
fi
summary="$HAP_REPORT_DIR/pre_place_summary.txt"
for required in "$summary" "$HAP_REPORT_DIR/vivado.log" \
        "$HAP_REPORT_DIR/vivado.jou"; do
    [[ -s "$required" ]] || gate_rc=1
done
if [[ "$gate_rc" -eq 0 ]]; then
    for literal in \
        'status=PASS' \
        'stage=REGISTERED_OOC_PRE_PLACE_AUDIT' \
        "input_dcp=$HAP_INPUT_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
        'weight_fifo_ff_pre_opt=8718' \
        'weight_fifo_ram_pre_opt=0' \
        'weight_fifo_ff_post_opt=8718' \
        'weight_fifo_ram_post_opt=0' \
        'pblock_count=10' \
        'floorplan_center_region1_cols4_5_lane_roots=16' \
        'floorplan_center_region1_cols6_7_lane_roots=16' \
        'floorplan_center_region1_bisect_exact_cover=1' \
        'floorplan_center_region1_cols4_5_dsp_primitives=272' \
        'floorplan_center_region1_cols6_7_dsp_primitives=272' \
        'floorplan_center_region1_logic_residual_dsp48e2=0' \
        'floorplan_center_region1_dsp_stripe_exact_cover=1' \
        'floorplan_owner_region2_weight_ff_primitives=1024' \
        'floorplan_owner_region2_weight_lut_primitives=1024' \
        'floorplan_owner_region2_weight_primitives=2048' \
        'floorplan_owner_region2_weight_exact_cover=1' \
        'floorplan_region0_input_activation_primitives=2048' \
        'floorplan_region0_input_zero_point_primitives=64' \
        'floorplan_region0_input_weight_ff_primitives=512' \
        'floorplan_region0_input_weight_lut_primitives=512' \
        'floorplan_region0_input_weight_primitives=1024' \
        'floorplan_region0_input_primitives=3136' \
        'floorplan_region0_input_fdre=2624' \
        'floorplan_region0_input_lut3=512' \
        'floorplan_region0_input_dsp48e2=0' \
        'floorplan_owner_region0_input_exact_cover=1' \
        'floorplan_region0_input_localization_ok=1' \
        'floorplan_region3_input_activation_primitives=2048' \
        'floorplan_region3_input_zero_point_primitives=64' \
        'floorplan_region3_input_weight_ff_primitives=0' \
        'floorplan_region3_input_weight_lut_primitives=0' \
        'floorplan_region3_owner_weight_ff_primitives=512' \
        'floorplan_region3_owner_weight_lut_primitives=512' \
        'floorplan_region3_input_primitives=2112' \
        'floorplan_region3_input_fdre=2112' \
        'floorplan_region3_input_lut3=0' \
        'floorplan_region3_input_dsp48e2=0' \
        'floorplan_owner_region3_input_exact_cover=1' \
        'floorplan_region3_weight_owner_residency_ok=1' \
        'floorplan_region3_input_localization_ok=1' \
        'floorplan_owner_region2_weight_anchor_ok=1' \
        'drc_errors=0'; do
        grep -Fqx -- "$literal" "$summary" || gate_rc=1
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
        gate_rc=1
    fi
fi
if [[ "$gate_rc" -ne 0 ]]; then
    printf 'Attention pre-place audit failed; evidence retained in %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 1
fi
status=0
cat "$summary"
printf '%s\n' "$HAP_REPORT_DIR"
