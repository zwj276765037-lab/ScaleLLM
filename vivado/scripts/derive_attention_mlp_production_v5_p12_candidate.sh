#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$ROOT/vivado/scripts/derive_attention_mlp_production_v5_p12_candidate.sh"
EXPECTED_MAP_MANIFEST_SHA256=a2ac09468dae44042ad3ae3a0e80e58904c8e5393f395996c31f4291683b92bf

[[ $# -eq 1 ]] || {
    printf 'usage: %s MISSION0134_V3_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
map_manifest="$(readlink -e -- "$1")"
actual_map_sha="$(sha256sum -- "$map_manifest" | awk '{print $1}')"
[[ "$actual_map_sha" == "$EXPECTED_MAP_MANIFEST_SHA256" ]] || {
    printf 'P12 source map identity mismatch: expected=%s actual=%s\n' \
        "$EXPECTED_MAP_MANIFEST_SHA256" "$actual_map_sha" >&2
    exit 2
}
(cd / && sha256sum -c --strict "$map_manifest" >/dev/null)

map_dir="$(dirname "$map_manifest")"
map_summary="$map_dir/summary.txt"
clock_regions="$map_dir/clock_region_groups.tsv"
for literal in \
        'status=V5_P12_HADAMARD_CAPACITY_MAP_PASS' \
        'evidence_class=READ_ONLY_REJECTED_P9_POST_PLACE_DCP' \
        'source_lineage_verified=1' \
        'input_dcp_sha256=f1d8673e27769319af436d22a7461bc148669386596def9c9820ba8ebc716794' \
        'pblock_count=26' 'dsp48e2=5453' 'uram288=752' \
        'source_level5_or_higher_windows=16' \
        'source_level6_or_higher_windows=5' \
        'slr1_clock_regions_profiled=30' \
        'floorplan_mutated=0' 'implementation_commands_run=0' \
        'checkpoint_written=0' 'route_eligible=0'; do
    [[ "$(grep -Fxc -- "$literal" "$map_summary" || true)" -eq 1 ]] || {
        printf 'P12 source map summary mismatch: %s\n' "$literal" >&2
        exit 2
    }
done

x5y5_row="$(awk -F '\t' '$1 == "X5Y5" {print; count++} END {if (count != 1) exit 1}' \
    "$clock_regions")"
IFS=$'\t' read -r -a fields <<< "$x5y5_row"
[[ "${#fields[@]}" -eq 61 ]] || {
    printf 'P12 X5Y5 row cardinality mismatch: %d\n' "${#fields[@]}" >&2
    exit 2
}
expected=(X5Y5 1500 12000 24000 48 0 24 16710 4101 11695 35 0 2)
for index in "${!expected[@]}"; do
    [[ "${fields[$index]}" == "${expected[$index]}" ]] || {
        printf 'P12 X5Y5 field mismatch: index=%d expected=%s actual=%s\n' \
            "$index" "${expected[$index]}" "${fields[$index]}" >&2
        exit 2
    }
done
for index in $(seq 13 60); do
    [[ "${fields[$index]}" == 0 ]] || {
        printf 'P12 X5Y5 target-group occupancy is nonzero: index=%d value=%s\n' \
            "$index" "${fields[$index]}" >&2
        exit 2
    }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_P12_CANDIDATE_DIR:-$ROOT/vivado/reports/production_v5_p12_candidate_$STAMP}"
out="$(readlink -m -- "$requested")"
[[ ! -e "$out" ]] || {
    printf 'P12 candidate directory exists: %s\n' "$out" >&2
    exit 2
}
mkdir "$out"
inputs=("$map_manifest" "$SELF")
printf '%s\n' "${inputs[@]}" > "$out/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$out/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$out/INPUT_SHA256SUMS" >/dev/null)

cat > "$out/p12_region1_relief_candidate.txt" <<EOF
contract=P12_ATTN_REGION1_LOGIC_PLUS_X5Y5
pblock_name=p3_pb_projection_center_region1_logic_residual_cr_x2y5_x4y9
base_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9
relief_range=CLOCKREGION_X5Y5:CLOCKREGION_X5Y5
region1_logic_primitives=68257
region1_logic_lut=33885
region1_logic_ff=32032
region1_logic_dsp=0
relief_lut_capacity=12000
relief_ff_capacity=24000
relief_dsp_capacity=48
relief_occupied_lut=4101
relief_occupied_ff=11695
relief_occupied_dsp=35
relief_free_lut=7899
relief_free_ff=12305
relief_lut_percent=34.175
relief_ff_percent=48.729
relief_hadamard_lut=0
relief_gather_lut=0
relief_quantizer012_lut=0
relief_quantizer3_lut=0
relief_attention_region1_lut=0
relief_attention_region2_lut=0
status=V5_P12_REGION1_RELIEF_CANDIDATE_PASS
EOF

cat > "$out/summary.txt" <<EOF
stage=V5_P10_P9_TO_P12_REGION1_RELIEF_DECISION
evidence_class=READ_ONLY_MANIFESTED_DIAGNOSIS
map_output_manifest=$map_manifest
map_output_manifest_sha256=$actual_map_sha
p9_source_dcp_sha256=f1d8673e27769319af436d22a7461bc148669386596def9c9820ba8ebc716794
p9_level5_or_higher_windows=16
p9_level6_or_higher_windows=5
selected_contract=P12_ATTN_REGION1_LOGIC_PLUS_X5Y5
selected_pblock=p3_pb_projection_center_region1_logic_residual_cr_x2y5_x4y9
selected_base_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9
selected_relief_range=CLOCKREGION_X5Y5:CLOCKREGION_X5Y5
selected_relief_free_lut=7899
selected_relief_free_ff=12305
attention_dsp_geometry_retained=1
p9_quantizer3_retained=1
rtl_changed=0
external_ddr_format_changed=0
implementation_commands_run=0
checkpoint_written=0
route_eligible=0
status=V5_P10_P9_TO_P12_REGION1_RELIEF_DECISION_PASS
EOF
printf '%s\n' 'status=PASS' 'implementation_commands_run=0' \
    'checkpoint_written=0' 'route_eligible=0' > "$out/launcher_status.txt"

mapfile -d '' outputs < <(find "$out" -maxdepth 1 -type f -size +0c \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$out/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$out/OUTPUT_SHA256SUMS" >/dev/null)
printf '%s\n' "$out"
