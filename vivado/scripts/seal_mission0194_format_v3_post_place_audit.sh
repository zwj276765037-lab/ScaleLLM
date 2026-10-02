#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$ROOT/vivado/scripts/seal_mission0194_format_v3_post_place_audit.sh"
AUDIT_DIR="$ROOT/vivado/reports/production_v5_p16_noclip_post_place_audit_20260914_mission0194_v2r2_format3"
PLACE_DIR="$ROOT/vivado/reports/production_v5_p16_noclip_place_20260914_mission0194_v2r2_format3"
POST_OPT_DCP="$ROOT/vivado/reports/production_v5_synth_20260914_mission0194_v2_format3/post_opt.dcp"
POST_PLACE_DCP="$PLACE_DIR/post_place_diagnostic_only.dcp"
EXPECTED_POST_OPT_SHA=35438565f8577c1ab7f4d2d959bd1709b286ac9560e4f2b0a58680eb1bc778d1
EXPECTED_POST_PLACE_SHA=01f134c30570072c5fe650b2e0d03241d9e9b32699756f28dc005920d17d6de3
EXPECTED_AUDIT_INPUT_SHA=dacb6b7f62f6e4d329c5cb0cfe0f97662d8b8b538c56615744155f9bb1c999a0
EXPECTED_AUDIT_OUTPUT_SHA=685d8bf1a27375ea50c2c02de1e478adab20f801a14326523344f29890519ba5
EXPECTED_AUDIT_SUMMARY_SHA=5f6a44ee24bd73e19132bafaeac3523104c28a79676c6ce2a8be97a7f2d099fa

[[ $# -eq 0 ]] || { printf 'usage: %s\n' "$0" >&2; exit 2; }
requested="${HAP_M0194_AUDIT_SEAL_DIR:-$ROOT/vivado/reports/production_v5_p16_noclip_post_place_audit_recovery_20260914_mission0194_v2r2_format3}"
OUT="$(readlink -m -- "$requested")"
[[ ! -e "$OUT" ]] || {
    printf 'Mission 0194 audit seal output exists: %s\n' "$OUT" >&2
    exit 2
}

inputs=(
    "$SELF"
    "$POST_OPT_DCP"
    "$POST_PLACE_DCP"
    "$PLACE_DIR/INPUT_SHA256SUMS"
    "$PLACE_DIR/OUTPUT_SHA256SUMS"
    "$AUDIT_DIR/INPUT_SHA256SUMS"
    "$AUDIT_DIR/OUTPUT_SHA256SUMS"
    "$AUDIT_DIR/summary.txt"
    "$AUDIT_DIR/launcher_status.txt"
    "$AUDIT_DIR/vivado.log"
    "$AUDIT_DIR/timing_post_place.rpt"
    "$AUDIT_DIR/drc_post_place.rpt"
    "$AUDIT_DIR/congestion_post_place.rpt"
    "$AUDIT_DIR/post_opt_region2_lanes.tsv"
    "$AUDIT_DIR/post_place_region2_lanes.tsv"
    "$AUDIT_DIR/residual_removed_names.txt"
    "$AUDIT_DIR/residual_removed_post_opt_details.tsv"
    "$AUDIT_DIR/p8_parent_ingress_boundary_post_place.txt"
    "$AUDIT_DIR/data_bufg_post_place.txt"
)
for input in "${inputs[@]}"; do
    [[ -e "$input" ]] || {
        printf 'missing Mission 0194 audit seal input: %s\n' "$input" >&2
        exit 2
    }
done
for input in "${inputs[@]:0:18}"; do
    [[ -s "$input" ]] || {
        printf 'empty Mission 0194 audit seal input: %s\n' "$input" >&2
        exit 2
    }
done
[[ ! -s "$AUDIT_DIR/data_bufg_post_place.txt" ]] || {
    printf 'zero-data-BUFG inventory is unexpectedly nonempty\n' >&2
    exit 2
}

require_sha() {
    local file="$1" expected="$2"
    [[ "$(sha256sum -- "$file" | awk '{print $1}')" == "$expected" ]] || {
        printf 'Mission 0194 audit seal SHA mismatch: %s\n' "$file" >&2
        exit 2
    }
}
require_sha "$POST_OPT_DCP" "$EXPECTED_POST_OPT_SHA"
require_sha "$POST_PLACE_DCP" "$EXPECTED_POST_PLACE_SHA"
require_sha "$AUDIT_DIR/INPUT_SHA256SUMS" "$EXPECTED_AUDIT_INPUT_SHA"
require_sha "$AUDIT_DIR/OUTPUT_SHA256SUMS" "$EXPECTED_AUDIT_OUTPUT_SHA"
require_sha "$AUDIT_DIR/summary.txt" "$EXPECTED_AUDIT_SUMMARY_SHA"
(cd / && sha256sum -c --strict "$PLACE_DIR/INPUT_SHA256SUMS" >/dev/null)
(cd / && sha256sum -c --strict "$PLACE_DIR/OUTPUT_SHA256SUMS" >/dev/null)
(cd / && sha256sum -c --strict "$AUDIT_DIR/INPUT_SHA256SUMS" >/dev/null)
(cd / && sha256sum -c --strict "$AUDIT_DIR/OUTPUT_SHA256SUMS" >/dev/null)

for literal in status=FAIL vivado_exit_code=0 input_sha_recheck_exit_code=0 \
        implementation_commands_run=0 checkpoint_written=0 route_eligible=0; do
    grep -Fqx -- "$literal" "$AUDIT_DIR/launcher_status.txt"
done
summary="$AUDIT_DIR/summary.txt"
for literal in \
        'status=V5_M0194_FORMAT3_POST_PLACE_AUDIT_PASS' \
        'evidence_class=READ_ONLY_AUTHENTICATED_DCP_COMPARISON' \
        "input_post_opt_dcp_sha256=$EXPECTED_POST_OPT_SHA" \
        "input_post_place_dcp_sha256=$EXPECTED_POST_PLACE_SHA" \
        'implementation_commands_run=0' 'checkpoint_written=0' \
        'route_eligible=0' 'post_opt_region2_primitives=72896' \
        'post_place_region2_primitives=72894' \
        'expected_residual_removed_lut=2' 'residual_removed_count=2' \
        'residual_removed_lut=2' 'residual_removed_non_lut=0' \
        'residual_added_count=0' 'lane_identity_ok=1' \
        'region2_partition_exact_cover=1' 'region2_wrong_slr=0' \
        'region2_unplaced=0' 'post_place_dsp48e2=5449' \
        'post_place_uram288=752' 'post_place_ramb36e2=829' \
        'post_place_ramb18e2=22' 'slr_dsp48e2=1862 1777 1810' \
        'slr_uram288=224 224 304' 'global_unplaced_primitives=0' \
        'post_place_pblock_count=26' 'post_place_data_bufg=0' \
        'post_place_drc_errors=0' \
        'congestion_level5_or_higher_windows=18' \
        'congestion_level6_or_higher_windows=6' \
        'post_place_wns_ns=-1.222' 'post_place_tns_ns=-149.439' \
        'post_place_whs_ns=-4.187' 'post_place_ths_ns=-119228.070' \
        'post_opt_signature_ok=1' 'post_place_delta_ok=1'; do
    grep -Fqx -- "$literal" "$summary"
done
cmp -s <(cut -f1-6 "$AUDIT_DIR/post_opt_region2_lanes.tsv") \
    <(cut -f1-6 "$AUDIT_DIR/post_place_region2_lanes.tsv")
[[ "$(wc -l < "$AUDIT_DIR/post_place_region2_lanes.tsv")" -eq 33 ]]
[[ "$(wc -l < "$AUDIT_DIR/residual_removed_names.txt")" -eq 2 ]]
[[ "$(awk -F '\t' '$2 == "REF_NAME" && $3 == "LUT5" {n++} END {print n+0}' \
    "$AUDIT_DIR/residual_removed_post_opt_details.tsv")" -eq 2 ]]
[[ "$(awk -F '\t' '$2 == "INIT" && $3 == "32\x27h00A20000" {n++} END {print n+0}' \
    "$AUDIT_DIR/residual_removed_post_opt_details.tsv")" -eq 2 ]]
grep -Fqx 'V5_M0194_PARENT_INGRESS_BOUNDARY_POST_PLACE_PASS' \
    "$AUDIT_DIR/p8_parent_ingress_boundary_post_place.txt"
if grep -Eq '^(ERROR|FATAL):' "$AUDIT_DIR/vivado.log"; then
    printf 'Mission 0194 authenticated audit log contains Error/Fatal\n' >&2
    exit 2
fi

mkdir "$OUT"
printf '%s\n' "${inputs[@]}" > "$OUT/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$OUT/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_latest.txt"
printf '%s\n' \
    'status=V5_M0194_FORMAT3_POST_PLACE_AUDIT_RECOVERY_PASS' \
    'evidence_class=READ_ONLY_CONTENT_ADDRESSED_RECOVERY' \
    "post_opt_dcp_sha256=$EXPECTED_POST_OPT_SHA" \
    "post_place_diagnostic_dcp_sha256=$EXPECTED_POST_PLACE_SHA" \
    "upstream_audit_input_manifest_sha256=$EXPECTED_AUDIT_INPUT_SHA" \
    "upstream_audit_output_manifest_sha256=$EXPECTED_AUDIT_OUTPUT_SHA" \
    "upstream_audit_summary_sha256=$EXPECTED_AUDIT_SUMMARY_SHA" \
    'upstream_launcher_status=FAIL' \
    'upstream_launcher_failure_reason=empty_zero_data_bufg_inventory_required_nonempty' \
    'upstream_vivado_exit_code=0' \
    'region2_removed_lut=2' \
    'region2_removed_non_lut=0' \
    'region2_added_count=0' \
    'region2_lane_identity_ok=1' \
    'region2_partition_exact_cover=1' \
    'resource_slr_membership_ok=1' \
    'p8_format3_boundary_ok=1' \
    'post_place_drc_errors=0' \
    'congestion_level5_or_higher_windows=18' \
    'congestion_level6_or_higher_windows=6' \
    'placement_recovery_eligible=0' \
    'route_eligible=0' \
    'implementation_commands_run=0' \
    'checkpoint_written=0' \
    > "$OUT/audit_acceptance.txt"
printf '%s\n' 'status=PASS' 'stage=complete' \
    'implementation_commands_run=0' 'checkpoint_written=0' \
    'route_eligible=0' > "$OUT/queue_status.txt"
sha256sum -- "$OUT/INPUT_FILES" "$OUT/INPUT_SHA256SUMS" \
    "$OUT/input_sha_latest.txt" "$OUT/audit_acceptance.txt" \
    "$OUT/queue_status.txt" > "$OUT/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/OUTPUT_SHA256SUMS" >/dev/null)
printf 'M0194_FORMAT3_POST_PLACE_AUDIT_RECOVERY_PASS\n%s\n' "$OUT"
