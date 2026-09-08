#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
[[ $# -eq 1 ]] || {
    printf 'usage: %s OWNER_CAPTURE_SYNTH_REPORT_DIR\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}

export HAP_JOBS="${HAP_JOBS:-32}"
if ! [[ "$HAP_JOBS" =~ ^[0-9]+$ ]] ||
        (( HAP_JOBS < 1 || HAP_JOBS > 32 )); then
    printf 'HAP_JOBS must be an integer in 1..32, got %q\n' \
        "$HAP_JOBS" >&2
    exit 2
fi
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-AltSpreadLogic_high}"
export HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE="${HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_ROUTE_DIRECTIVE="${HAP_ROUTE_DIRECTIVE:-AggressiveExplore}"
export HAP_POST_ROUTE_PHYSOPT_DIRECTIVE="${HAP_POST_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_MAX_POST_PLACE_LEVEL5_WINDOWS="${HAP_MAX_POST_PLACE_LEVEL5_WINDOWS:-1}"
if ! [[ "$HAP_MAX_POST_PLACE_LEVEL5_WINDOWS" =~ ^[0-9]+$ ]] ||
        (( HAP_MAX_POST_PLACE_LEVEL5_WINDOWS > 100 )); then
    printf 'HAP_MAX_POST_PLACE_LEVEL5_WINDOWS must be in 0..100, got %q\n' \
        "$HAP_MAX_POST_PLACE_LEVEL5_WINDOWS" >&2
    exit 2
fi
for directive in "$HAP_PLACE_DIRECTIVE" \
        "$HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE" "$HAP_ROUTE_DIRECTIVE" \
        "$HAP_POST_ROUTE_PHYSOPT_DIRECTIVE"; do
    [[ "$directive" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
        printf 'invalid MLP OOC implementation directive: %q\n' \
            "$directive" >&2
        exit 2
    }
done

require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; MLP OOC route not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}

SOURCE_DIR="$(readlink -e -- "$1")"
[[ -d "$SOURCE_DIR" ]] || {
    printf 'MLP synth report directory is missing: %s\n' "$1" >&2
    exit 2
}
export HAP_INPUT_DCP="$SOURCE_DIR/post_synth.dcp"
SOURCE_SUMMARY="$SOURCE_DIR/summary.txt"
SOURCE_STATUS="$SOURCE_DIR/launcher_status.txt"
SOURCE_OUTPUT_SHA="$SOURCE_DIR/OUTPUT_SHA256SUMS"
for input in "$HAP_INPUT_DCP" "$SOURCE_SUMMARY" "$SOURCE_STATUS" \
        "$SOURCE_OUTPUT_SHA"; do
    [[ -s "$input" ]] || {
        printf 'missing MLP synth evidence: %s\n' "$input" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$SOURCE_OUTPUT_SHA") >/dev/null
grep -qx 'launcher_exit_status=0' "$SOURCE_STATUS"
for literal in status=PASS stage=OWNER_CAPTURE_REGISTERED_OOC_POST_SYNTH \
        clock_mhz=100 timing_coverage_ok=1 no_timing_exceptions=1 \
        dut_dsp48e2=1536 mlp_pack2_lane_instances=48 \
        ingress_capture_leaf_instances=816 ingress_capture_leaf_lut1=816 \
        ingress_capture_leaf_load_ok=1; do
    grep -qx "$literal" "$SOURCE_SUMMARY"
done
require_free_batch_slot

STAMP="$(date +%Y%m%d_%H%M%S)"
requested_report="${HAP_REPORT_DIR:-$ROOT/vivado/reports/a8w4_slice8x12_owner_capture_registered_ooc_route_$STAMP}"
export HAP_REPORT_DIR="$(readlink -m -- "$requested_report")"
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'MLP OOC route report directory exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

TCL="$ROOT/vivado/scripts/route_a8w4_slice8x12_owner_capture_registered_ooc.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_a8w4_slice8x12_owner_capture_registered_ooc_route.sh"
FLOORPLAN="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
RUN_CONTRACT="$HAP_REPORT_DIR/RUN_CONTRACT"
printf '%s\n' \
    "jobs=$HAP_JOBS" \
    "source_dir=$SOURCE_DIR" \
    "place_directive=$HAP_PLACE_DIRECTIVE" \
    "pre_route_physopt_directive=$HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE" \
    "route_directive=$HAP_ROUTE_DIRECTIVE" \
    "post_route_physopt_directive=$HAP_POST_ROUTE_PHYSOPT_DIRECTIVE" \
    "max_post_place_level5_windows=$HAP_MAX_POST_PLACE_LEVEL5_WINDOWS" \
    > "$RUN_CONTRACT"
inputs=("$HAP_INPUT_DCP" "$SOURCE_SUMMARY" "$SOURCE_STATUS" \
    "$SOURCE_OUTPUT_SHA" "$TCL" "$LAUNCHER" "$FLOORPLAN" "$RUN_CONTRACT")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty MLP OOC route input: %s\n' "$input" >&2
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

require_free_batch_slot
cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
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
summary="$HAP_REPORT_DIR/summary.txt"
for required in "$summary" "$HAP_REPORT_DIR/post_place_fast_gate.txt" \
        "$HAP_REPORT_DIR/post_place_diagnostic_only.dcp" \
        "$HAP_REPORT_DIR/post_place.dcp" \
        "$HAP_REPORT_DIR/post_route_before_physopt.dcp" \
        "$HAP_REPORT_DIR/post_route.dcp" \
        "$HAP_REPORT_DIR/vivado.log" "$HAP_REPORT_DIR/vivado.jou"; do
    [[ -s "$required" ]] || gate_rc=1
done
if [[ "$gate_rc" -eq 0 ]]; then
    for literal in \
        status=PASS \
        stage=OWNER_CAPTURE_REGISTERED_OOC_POST_ROUTE \
        clock_mhz=100 \
        "input_dcp=$HAP_INPUT_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
        jobs="$HAP_JOBS" \
        "place_directive=$HAP_PLACE_DIRECTIVE" \
        "pre_route_physopt_directive=$HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE" \
        "route_directive=$HAP_ROUTE_DIRECTIVE" \
        "post_route_physopt_directive=$HAP_POST_ROUTE_PHYSOPT_DIRECTIVE" \
        source_proxy_ff=4136 sink_proxy_ff=3523 \
        mlp_pack2_lane_instances=48 ingress_capture_leaf_instances=816 \
        ingress_capture_leaf_lut1=816 dut_dsp48e2=1536 fast_gate_ok=1 \
        unaccepted_explicit_route_gaps=0 route_clean=1 drc_errors=0 data_bufg=0 \
        final_level6_or_higher_windows=0 final_unplaced_primitives=0 \
        final_wrong_slr_primitives=0 final_dsp_slr0=1536 \
        final_dsp_other_slr=0 no_timing_exceptions=1 \
        timing_coverage_ok=1 route_started=1; do
        grep -Fqx -- "$literal" "$summary" || gate_rc=1
    done
    for literal in drc_errors=0 level6_or_higher_windows=0 \
            fast_gate_ok=1; do
        grep -Fqx -- "$literal" \
            "$HAP_REPORT_DIR/post_place_fast_gate.txt" || gate_rc=1
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_REPORT_DIR/vivado.log"; then
        gate_rc=1
    fi
fi
if [[ "$gate_rc" -ne 0 ]]; then
    printf 'MLP OOC route failed; evidence retained in %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 1
fi
status=0
cat "$summary"
printf '%s\n' "$HAP_REPORT_DIR"
