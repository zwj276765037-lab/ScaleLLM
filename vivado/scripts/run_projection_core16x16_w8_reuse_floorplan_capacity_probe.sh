#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
PROBE_TCL="$ROOT/vivado/scripts/probe_projection_core16x16_w8_reuse_floorplan_capacity.tcl"
FLOORPLAN_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_projection_core16x16_w8_reuse_floorplan_capacity_probe.sh"

[[ $# -eq 1 ]] || { printf 'usage: %s POST_SYNTH_DCP\n' "$0" >&2; exit 2; }
export HAP_INPUT_DCP="$(readlink -f -- "$1")"
[[ -s "$HAP_INPUT_DCP" ]] || {
    printf 'missing or empty projection post-synth DCP: %s\n' \
        "$HAP_INPUT_DCP" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}

export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
HAP_WAIT_FOR_SLOT="${HAP_WAIT_FOR_SLOT:-0}"
[[ "$HAP_WAIT_FOR_SLOT" == 0 || "$HAP_WAIT_FOR_SLOT" == 1 ]] || {
    printf 'HAP_WAIT_FOR_SLOT must be 0 or 1: %q\n' "$HAP_WAIT_FOR_SLOT" >&2
    exit 2
}
HAP_POLL_SECONDS="${HAP_POLL_SECONDS:-3600}"
[[ "$HAP_POLL_SECONDS" =~ ^[0-9]+$ ]] &&
    (( HAP_POLL_SECONDS >= 1800 && HAP_POLL_SECONDS <= 3600 )) || {
    printf 'HAP_POLL_SECONDS must be in 1800..3600: %q\n' \
        "$HAP_POLL_SECONDS" >&2
    exit 2
}

for input in "$PROBE_TCL" "$FLOORPLAN_LIB" "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing projection capacity input: %s\n' "$input" >&2
        exit 2
    }
done
probe_code="$(sed -E '/^[[:space:]]*#/d' "$PROBE_TCL")"
if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|place_design|phys_opt_design|route_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$probe_code"; then
    printf 'capacity probe contains a forbidden implementation command\n' >&2
    exit 2
fi
if grep -Fq 'hap_projection_ooc_floorplan::apply' <<<"$probe_code"; then
    printf 'capacity probe must not apply or mutate the canonical floorplan\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core16x16_w8_reuse_floorplan_capacity_probe_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'projection capacity evidence directory exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

inputs=("$HAP_INPUT_DCP" "$FLOORPLAN_LIB" "$PROBE_TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_INPUT_DCP" | awk '{print $1}')"
export HAP_CAPACITY_INPUT_MANIFEST_SHA256
HAP_CAPACITY_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
printf '%s\n' \
    "launcher_pid=$$" \
    "queue_epoch=$(date +%s)" \
    "wait_for_slot=$HAP_WAIT_FOR_SLOT" \
    "poll_seconds=$HAP_POLL_SECONDS" \
    "jobs=$HAP_JOBS" \
    "input_dcp=$HAP_INPUT_DCP" \
    "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
    "input_manifest_sha256=$HAP_CAPACITY_INPUT_MANIFEST_SHA256" \
    > "$HAP_REPORT_DIR/run_metadata.txt"

status=1
vivado_rc=125
gate_rc=125
input_precheck_rc=125
input_postcheck_rc=125
manifest_post_match=0
slot_waits=0
archive() {
    set +e
    printf 'end_epoch=%s\nslot_waits=%s\n' "$(date +%s)" "$slot_waits" \
        >> "$HAP_REPORT_DIR/run_metadata.txt"
    printf '%s\n' \
        "status=$([[ "$status" -eq 0 ]] && printf PASS || printf FAIL)" \
        "final_exit_code=$status" \
        "vivado_exit_code=$vivado_rc" \
        "capacity_gate_exit_code=$gate_rc" \
        "input_precheck_exit_code=$input_precheck_rc" \
        "input_postcheck_exit_code=$input_postcheck_rc" \
        "input_manifest_post_match=$manifest_post_match" \
        "slot_waits=$slot_waits" \
        'implementation_commands_run=0' \
        'checkpoint_written=0' \
        > "$HAP_REPORT_DIR/launcher_status.txt"
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    if [[ "${#outputs[@]}" -ne 0 ]]; then
        sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    fi
}
trap archive EXIT

while true; do
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -eq 0 ]]; then
        break
    fi
    if [[ "$HAP_WAIT_FOR_SLOT" -ne 1 ]]; then
        printf 'another batch Vivado is active; capacity probe not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        status=75
        exit "$status"
    fi
    ((slot_waits += 1))
    printf 'slot_wait_epoch=%s active_batch_count=%s\n' \
        "$(date +%s)" "${#active_batch[@]}" >> "$HAP_REPORT_DIR/run_metadata.txt"
    sleep "$HAP_POLL_SECONDS"
done

set +e
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_precheck.txt" 2>&1
input_precheck_rc=$?
actual_manifest_sha="$(sha256sum -- \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
if [[ "$input_precheck_rc" -ne 0 || "$manifest_rc" -ne 0 || \
      "$actual_manifest_sha" != "$HAP_CAPACITY_INPUT_MANIFEST_SHA256" ]]; then
    printf 'queued projection capacity inputs drifted; launch aborted\n' >&2
    exit 1
fi

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'batch Vivado appeared during capacity precheck; launch aborted\n' >&2
    status=75
    exit "$status"
fi
printf 'launch_epoch=%s\n' "$(date +%s)" >> "$HAP_REPORT_DIR/run_metadata.txt"

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_projection_core16x16_w8_reuse_floorplan_capacity.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS") \
    > "$HAP_REPORT_DIR/input_sha_postcheck.txt" 2>&1
input_postcheck_rc=$?
actual_manifest_sha="$(sha256sum -- \
    "$HAP_REPORT_DIR/INPUT_SHA256SUMS" 2>/dev/null | awk '{print $1}')"
manifest_post_rc=$?
set -e
if [[ "$manifest_post_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_CAPACITY_INPUT_MANIFEST_SHA256" ]]; then
    manifest_post_match=1
fi

summary="$HAP_REPORT_DIR/summary.txt"
capacity="$HAP_REPORT_DIR/candidate_capacity.txt"
if [[ "$vivado_rc" -eq 0 && "$input_postcheck_rc" -eq 0 && \
      "$manifest_post_match" -eq 1 && \
      -s "$summary" && -s "$capacity" ]]; then
    set +e
    gate_rc=0
    for literal in \
        'status=PASS' \
        'stage=PROJECTION_REUSE_OOC_FLOORPLAN_CAPACITY_PROBE' \
        'evidence_class=READ_ONLY_POST_SYNTH_CAPACITY_PROBE' \
        "input_dcp=$HAP_INPUT_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_CAPACITY_INPUT_MANIFEST_SHA256" \
        'candidate_count=10' 'target_candidate_count=10' \
        'candidate_region2_label=active_region2_shared_x0_x1' \
        'candidate_region2_raw_capacity_ok=1' \
        'candidate_region3_label=active_region3_shared_x0_x1' \
        'candidate_region3_raw_capacity_ok=1' \
        'candidate_region23_label=active_region23_shared_x0_x1' \
        'candidate_region23_primitive_count=109526' \
        'candidate_region23_lut_demand=53703' \
        'candidate_region23_lut_capacity=128160' \
        'candidate_region23_lut_util_pct=41.903' \
        'candidate_region23_ff_demand=51489' \
        'candidate_region23_ff_capacity=256320' \
        'candidate_region23_ff_util_pct=20.088' \
        'candidate_region23_dsp_demand=816' \
        'candidate_region23_dsp_capacity=960' \
        'candidate_region23_dsp_util_pct=85.000' \
        'candidate_region23_raw_capacity_ok=1' \
        'candidate_region1_owner_label=active_region1_owner_x2_x4' \
        'candidate_region1_owner_raw_capacity_ok=1' \
        'candidate_region0_frontend_label=active_region0_frontend_x4_x5' \
        'candidate_region0_frontend_raw_capacity_ok=1' \
        'candidate_center_total_label=active_center_total_x2_x5' \
        'candidate_center_total_raw_capacity_ok=1' \
        'candidate_region1_cols4_5_dsp_label=active_region1_cols4_5_dsp_x3_x4' \
        'candidate_region1_cols4_5_dsp_demand=272' \
        'candidate_region1_cols4_5_dsp_raw_capacity_ok=1' \
        'candidate_region1_cols6_7_dsp_label=active_region1_cols6_7_dsp_x2_x3' \
        'candidate_region1_cols6_7_dsp_demand=272' \
        'candidate_region1_cols6_7_dsp_raw_capacity_ok=1' \
        'candidate_region1_logic_residual_label=active_region1_logic_residual_x2_x4' \
        'candidate_region1_logic_residual_dsp_demand=0' \
        'candidate_region1_logic_residual_raw_capacity_ok=1' \
        'candidate_owner_region2_weight_label=active_owner_region2_weight_x2_x4_y5_y6' \
        'candidate_owner_region2_weight_primitive_count=2048' \
        'candidate_owner_region2_weight_lut_demand=1024' \
        'candidate_owner_region2_weight_ff_demand=1024' \
        'candidate_owner_region2_weight_dsp_demand=0' \
        'candidate_owner_region2_weight_raw_capacity_ok=1' \
        'center_region1_lane_roots=32' \
        'center_region1_cols4_5_lane_roots=16' \
        'center_region1_cols6_7_lane_roots=16' \
        'center_region1_bisect_exact_cover=1' \
        'center_region1_dsp_stripe_exact_cover=1' \
        'owner_region2_weight_ff_primitives=1024' \
        'owner_region2_weight_lut_primitives=1024' \
        'owner_region2_weight_primitives=2048' \
        'owner_region2_weight_exact_cover=1' \
        'region0_input_activation_primitives=2048' \
        'region0_input_zero_point_primitives=64' \
        'region0_input_weight_ff_primitives=512' \
        'region0_input_weight_lut_primitives=512' \
        'region0_input_weight_primitives=1024' \
        'region0_input_primitives=3136' \
        'region0_input_fdre=2624' \
        'region0_input_lut3=512' \
        'region0_input_dsp48e2=0' \
        'owner_region0_input_exact_cover=1' \
        'region0_input_localization_ok=1' \
        'region3_input_activation_primitives=2048' \
        'region3_input_zero_point_primitives=64' \
        'region3_input_weight_ff_primitives=0' \
        'region3_input_weight_lut_primitives=0' \
        'region3_owner_weight_ff_primitives=512' \
        'region3_owner_weight_lut_primitives=512' \
        'region3_input_primitives=2112' \
        'region3_input_fdre=2112' \
        'region3_input_lut3=0' \
        'region3_input_dsp48e2=0' \
        'owner_region3_input_exact_cover=1' \
        'region3_weight_owner_residency_ok=1' \
        'region3_input_localization_ok=1' \
        'owner_region2_weight_anchor_ok=1' \
        'active_floorplan_raw_capacity_ok=1' \
        'canonical_pblock_count=0' 'canonical_floorplan_mutated=0' \
        'implementation_commands_run=0' 'checkpoint_written=0'; do
        [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -eq 1 ]] || {
            printf 'capacity summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        }
    done
    [[ "$(grep -c '^candidate=' "$capacity")" -eq 10 ]] || gate_rc=1
    set -e
fi

if [[ "$vivado_rc" -eq 0 && "$input_postcheck_rc" -eq 0 && \
      "$manifest_post_match" -eq 1 && \
      "$gate_rc" -eq 0 ]]; then
    status=0
fi
if [[ "$status" -ne 0 ]]; then
    printf 'projection capacity probe failed; evidence: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 1
fi
cat "$summary"
printf '%s\n' "$HAP_REPORT_DIR"
