#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SYNTH_DIR="$ROOT/vivado/reports/production_v5_synth_20260914_mission0194_v2_format3"
POST_OPT_DCP="$SYNTH_DIR/post_opt.dcp"
PLACE_DIR="$ROOT/vivado/reports/production_v5_p16_noclip_place_20260914_mission0194_v2r2_format3"
POST_PLACE_DCP="$PLACE_DIR/post_place_diagnostic_only.dcp"
PLACE_SUMMARY="$PLACE_DIR/summary.txt"
PLACE_STATUS="$PLACE_DIR/launcher_status.txt"
PLACE_LOG="$PLACE_DIR/vivado.log"
PLACE_INPUT_SHA="$PLACE_DIR/INPUT_SHA256SUMS"
PLACE_OUTPUT_SHA="$PLACE_DIR/OUTPUT_SHA256SUMS"
REGION2_DIR="$ROOT/vivado/reports/production_v5_p16_region2_post_opt_probe_20260914_mission0194_v2r1_format3"
REGION2_SUMMARY="$REGION2_DIR/summary.txt"
REGION2_OUTPUT_SHA="$REGION2_DIR/OUTPUT_SHA256SUMS"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p16_noclip_post_place_delta.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_mission0194_format_v3_post_place_audit.sh"

EXPECTED_POST_OPT_SHA=35438565f8577c1ab7f4d2d959bd1709b286ac9560e4f2b0a58680eb1bc778d1
EXPECTED_POST_PLACE_SHA=01f134c30570072c5fe650b2e0d03241d9e9b32699756f28dc005920d17d6de3
EXPECTED_PLACE_INPUT_SHA=36edbc4284032e90e7f6583ec36039db1921c77da72ccc2934433c6a1c0fb9be
EXPECTED_PLACE_OUTPUT_SHA=aa979aecfb7f8e9a83905ca6dfa49c60123a7f920e8a7e7e30451424b601f25b
EXPECTED_REGION2_SUMMARY_SHA=2567a8bf69268922f54adb6f582d9a36ad1bd0da70c7c4bde00f23fedec8cc3f
EXPECTED_REGION2_OUTPUT_SHA=cb1cf6cc0b6be623154753ed030485523c7f36efc529a00e0adc7ade10031ec1

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'Mission 0194 post-place audit requires HAP_JOBS=32\n' >&2
    exit 2
}

inputs=("$POST_OPT_DCP" "$POST_PLACE_DCP" "$PLACE_SUMMARY"
    "$PLACE_STATUS" "$PLACE_LOG" "$PLACE_INPUT_SHA" "$PLACE_OUTPUT_SHA"
    "$REGION2_SUMMARY" "$REGION2_OUTPUT_SHA" "$SELECTOR_LIB"
    "$BOUNDARY_LIB" "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || {
        printf 'missing Mission 0194 post-place audit input: %s\n' "$input" >&2
        exit 2
    }
done

require_sha() {
    local file="$1" expected="$2" actual
    actual="$(sha256sum -- "$file" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || {
        printf 'Mission 0194 SHA mismatch: %s\n' "$file" >&2
        exit 2
    }
}
require_sha "$POST_OPT_DCP" "$EXPECTED_POST_OPT_SHA"
require_sha "$POST_PLACE_DCP" "$EXPECTED_POST_PLACE_SHA"
require_sha "$PLACE_INPUT_SHA" "$EXPECTED_PLACE_INPUT_SHA"
require_sha "$PLACE_OUTPUT_SHA" "$EXPECTED_PLACE_OUTPUT_SHA"
require_sha "$REGION2_SUMMARY" "$EXPECTED_REGION2_SUMMARY_SHA"
require_sha "$REGION2_OUTPUT_SHA" "$EXPECTED_REGION2_OUTPUT_SHA"
(cd / && sha256sum -c --strict "$PLACE_INPUT_SHA" >/dev/null)
(cd / && sha256sum -c --strict "$PLACE_OUTPUT_SHA" >/dev/null)
(cd / && sha256sum -c --strict "$REGION2_OUTPUT_SHA" >/dev/null)
grep -Fqx 'status=FAIL' "$PLACE_STATUS"
grep -Fqx 'acceptance_evidence=0' "$PLACE_STATUS"
grep -Fqx 'route_eligible=0' "$PLACE_STATUS"
grep -Fqx 'checkpoint_written=0' "$PLACE_STATUS"
grep -Fqx 'status=FAIL' "$PLACE_SUMMARY"
grep -Fqx 'failure_stage=post_place_live_rediscovery' "$PLACE_SUMMARY"
[[ "$(grep -Fxc 'place_design completed successfully' "$PLACE_LOG")" -eq 1 ]]

audit_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
        '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$audit_code"; then
    printf 'Mission 0194 audit Tcl contains a state-changing command\n' >&2
    exit 2
fi
mapfile -t blockers < <(pgrep -u "$(id -u)" -af \
    '([u]nwrapped/lnx64.o/vivado .*[-]mode batch|[r]un_module_power[.]sh)' || true)
if [[ "${#blockers[@]}" -ne 0 ]]; then
    printf 'another current-user Vivado flow is active; audit not started:\n' >&2
    printf '  %s\n' "${blockers[@]}" >&2
    exit 75
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_M0194_POST_PLACE_AUDIT_DIR:-$ROOT/vivado/reports/production_v5_p16_noclip_post_place_audit_${STAMP}_mission0194_v2r2_format3}"
export HAP_P16_DELTA_OUT="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P16_DELTA_OUT" ]] || {
    printf 'Mission 0194 audit output exists: %s\n' "$HAP_P16_DELTA_OUT" >&2
    exit 2
}
mkdir "$HAP_P16_DELTA_OUT"
printf '%s\n' "${inputs[@]}" > "$HAP_P16_DELTA_OUT/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P16_DELTA_OUT/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_P16_DELTA_OUT/INPUT_SHA256SUMS") \
    > "$HAP_P16_DELTA_OUT/input_sha_precheck.txt"

export HAP_P16_DELTA_POST_OPT_DCP="$POST_OPT_DCP"
export HAP_P16_DELTA_POST_PLACE_DCP="$POST_PLACE_DCP"
export HAP_P16_DELTA_EXPECTED_POST_OPT_SHA256="$EXPECTED_POST_OPT_SHA"
export HAP_P16_DELTA_EXPECTED_POST_PLACE_SHA256="$EXPECTED_POST_PLACE_SHA"
export HAP_P16_DELTA_INPUT_SHA="$HAP_P16_DELTA_OUT/INPUT_SHA256SUMS"
export HAP_P16_DELTA_INPUT_COUNT="${#inputs[@]}"
export HAP_P16_DELTA_EXPECTED_REMOVED_LUT=2
export HAP_P16_DELTA_EXPECTED_RAMB36=829
export HAP_P16_DELTA_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_P16_DELTA_BOUNDARY_LIB="$BOUNDARY_LIB"
export HAP_P16_DELTA_EVIDENCE_CLASS=READ_ONLY_AUTHENTICATED_DCP_COMPARISON
export HAP_P16_DELTA_PASS_STATUS=V5_M0194_FORMAT3_POST_PLACE_AUDIT_PASS

vivado_rc=255
input_rc=125
status=FAIL
archive() {
    set +e
    printf '%s\n' "status=$status" "vivado_exit_code=$vivado_rc" \
        "input_sha_recheck_exit_code=$input_rc" \
        'implementation_commands_run=0' 'checkpoint_written=0' \
        'route_eligible=0' > "$HAP_P16_DELTA_OUT/launcher_status.txt"
    mapfile -d '' outputs < <(find "$HAP_P16_DELTA_OUT" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -eq 0 ]] || \
        sha256sum -- "${outputs[@]}" > "$HAP_P16_DELTA_OUT/OUTPUT_SHA256SUMS"
}
trap archive EXIT

set +e
"$VIVADO" -mode batch -notrace -source "$TCL" \
    -log "$HAP_P16_DELTA_OUT/vivado.log" \
    -journal "$HAP_P16_DELTA_OUT/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P16_DELTA_OUT/INPUT_SHA256SUMS") \
    > "$HAP_P16_DELTA_OUT/input_sha_postcheck.txt"
input_rc=$?
set -e

summary="$HAP_P16_DELTA_OUT/summary.txt"
required=(summary.txt post_place_region2_residual.tsv
    post_opt_region2_residual.tsv post_place_region2_lanes.tsv
    post_opt_region2_lanes.tsv residual_removed_names.txt
    residual_removed_post_opt_details.tsv timing_post_place.rpt
    timing_setup_paths_post_place.rpt timing_hold_paths_post_place.rpt
    drc_post_place.rpt congestion_post_place.rpt utilization_post_place.rpt
    utilization_slr_post_place.rpt utilization_pblocks_post_place.rpt
    data_bufg_post_place.txt p8_parent_ingress_boundary_post_place.txt
    vivado.log vivado.jou input_sha_precheck.txt input_sha_postcheck.txt)
if (( vivado_rc == 0 && input_rc == 0 )); then
    for file in "${required[@]}"; do
        [[ -s "$HAP_P16_DELTA_OUT/$file" ]] || {
            printf 'missing Mission 0194 audit output: %s\n' "$file" >&2
            exit 1
        }
    done
    for literal in \
        'status=V5_M0194_FORMAT3_POST_PLACE_AUDIT_PASS' \
        'evidence_class=READ_ONLY_AUTHENTICATED_DCP_COMPARISON' \
        "input_post_opt_dcp_sha256=$EXPECTED_POST_OPT_SHA" \
        "input_post_place_dcp_sha256=$EXPECTED_POST_PLACE_SHA" \
        'implementation_commands_run=0' 'checkpoint_written=0' \
        'route_eligible=0' 'post_opt_region2_primitives=72896' \
        'post_opt_region2_lut=35269' 'post_opt_region2_ff=34743' \
        'post_opt_region2_dsp48e2=544' \
        'post_place_region2_primitives=72894' \
        'post_place_region2_lut=35267' 'post_place_region2_ff=34743' \
        'post_place_region2_dsp48e2=544' \
        'expected_residual_removed_lut=2' 'residual_removed_count=2' \
        'residual_removed_lut=2' 'residual_removed_non_lut=0' \
        'residual_added_count=0' 'lane_identity_ok=1' \
        'region2_partition_exact_cover=1' 'region2_wrong_slr=0' \
        'region2_unplaced=0' 'post_place_dsp48e2=5449' \
        'post_place_uram288=752' 'post_place_ramb36e2=829' \
        'post_place_ramb18e2=22' 'slr_dsp48e2=1862 1777 1810' \
        'slr_uram288=224 224 304' 'global_unplaced_primitives=0' \
        'post_place_pblock_count=26' 'post_place_data_bufg=0' \
        'post_place_drc_errors=0' 'post_opt_signature_ok=1' \
        'post_place_delta_ok=1'; do
        grep -Fqx -- "$literal" "$summary" || {
            printf 'Mission 0194 audit summary gate failed: %s\n' "$literal" >&2
            exit 1
        }
    done
    grep -Fqx 'V5_M0194_PARENT_INGRESS_BOUNDARY_POST_PLACE_PASS' \
        "$HAP_P16_DELTA_OUT/p8_parent_ingress_boundary_post_place.txt"
    for literal in parent_head_ff=6560 parent_tail_ff=6560 \
            parent_count_ff=2 parent_count_replica_equivalence_ok=1 \
            parent_pointer_ff=0 \
            local_clear_shared_upstream_ready_paths=0 \
            branch_credit_shared_upstream_ready_paths=0 \
            local_clear_gate_compute_ready_paths=0 \
            branch_credit_gate_compute_ready_paths=0 \
            local_clear_down_compute_ready_paths=0 \
            branch_credit_down_compute_ready_paths=0 \
            local_clear_input_cache_ready_paths=0 \
            branch_credit_input_cache_ready_paths=0; do
        grep -Fqx -- "$literal" \
            "$HAP_P16_DELTA_OUT/p8_parent_ingress_boundary_post_place.txt"
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_P16_DELTA_OUT/vivado.log"; then
        printf 'Mission 0194 audit Vivado log contains Error/Fatal\n' >&2
        exit 1
    fi
    status=PASS
fi
[[ "$status" == PASS ]] || {
    printf 'Mission 0194 post-place audit failed: %s\n' \
        "$HAP_P16_DELTA_OUT" >&2
    (( vivado_rc != 0 )) && exit "$vivado_rc"
    exit 1
}
archive
(cd / && sha256sum -c --strict \
    "$HAP_P16_DELTA_OUT/OUTPUT_SHA256SUMS" >/dev/null)
trap - EXIT
cat "$summary"
printf '%s\n' "$HAP_P16_DELTA_OUT"
