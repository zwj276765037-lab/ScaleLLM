#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$ROOT/vivado/scripts/derive_attention_mlp_production_v5_p11_candidate.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 1 ]] || {
    printf 'usage: %s P9_LEVEL6_MAP_DIR\n' "$0" >&2
    exit 2
}
MAP_DIR="$(readlink -e -- "$1")"
requested="${HAP_P11_DECISION_DIR:-$ROOT/vivado/reports/production_v5_p11_candidate_$STAMP}"
OUT="$(readlink -m -- "$requested")"
[[ ! -e "$OUT" ]] || {
    printf 'P11 decision directory exists: %s\n' "$OUT" >&2
    exit 2
}

MAP_OUTPUT="$MAP_DIR/OUTPUT_SHA256SUMS"
MAP_INPUT="$MAP_DIR/INPUT_SHA256SUMS"
MAP_SUMMARY="$MAP_DIR/summary.txt"
MAP_LAUNCHER="$MAP_DIR/launcher_status.txt"
TABLE="$MAP_DIR/slr1_clock_region_utilization.tsv"
CATEGORIES="$MAP_DIR/window_category_counts.tsv"
PBLOCKS="$MAP_DIR/window_pblock_counts.tsv"
for path in "$MAP_OUTPUT" "$MAP_INPUT" "$MAP_SUMMARY" "$MAP_LAUNCHER" \
        "$TABLE" "$CATEGORIES" "$PBLOCKS" "$SELF"; do
    [[ -s "$path" ]] || {
        printf 'missing P11 decision input: %s\n' "$path" >&2
        exit 2
    }
done

mkdir "$OUT"
inputs=("$MAP_OUTPUT" "$MAP_INPUT" "$MAP_SUMMARY" "$MAP_LAUNCHER" \
    "$TABLE" "$CATEGORIES" "$PBLOCKS" "$SELF")
printf '%s\n' "${inputs[@]}" > "$OUT/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$OUT/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_precheck.txt"
(cd / && sha256sum -c --strict "$MAP_OUTPUT") \
    > "$OUT/p9_map_output_sha_check.txt"
(cd / && sha256sum -c --strict "$MAP_INPUT") \
    > "$OUT/p9_map_input_sha_check.txt"

[[ "$(sha256sum -- "$MAP_OUTPUT" | awk '{print $1}')" == \
    14ab4b13cea008553df4a0be595b2505b00faace83423d63772839e2b8c8d66f ]]
for literal in \
        stage=V5_P10_P9_LEVEL6_PHYSICAL_MAP \
        evidence_class=READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified=1 \
        input_dcp_sha256=f1d8673e27769319af436d22a7461bc148669386596def9c9820ba8ebc716794 \
        pblock_count=26 dsp48e2=5453 uram288=752 \
        level6_windows_profiled=5 swiglu_quantizer_roots=4 \
        postprocess_row_roots=16 slr1_clock_regions_profiled=30 \
        p9_moving_postprocess_primitives=10696 quantizer3_primitives=11178 \
        floorplan_mutated=0 implementation_commands_run=0 \
        checkpoint_written=0 route_eligible=0 \
        status=V5_P10_P9_LEVEL6_PHYSICAL_MAP_PASS; do
    grep -Fqx -- "$literal" "$MAP_SUMMARY"
done
for literal in status=PASS vivado_exit_code=0 input_sha_recheck_exit_code=0; do
    grep -Fqx -- "$literal" "$MAP_LAUNCHER"
done

awk -F '\t' '
NR == 1 {next}
{
    name=$1
    sub(/^X/, "", name)
    split(name, xy, "Y")
    x=xy[1]+0
    y=xy[2]+0
    q3_total += $20
    q3_lut += $21
    q3_ff += $22
    if (x >= 0 && x <= 3 && (y == 5 || y == 6)) {
        selected++
        regions = regions (regions == "" ? "" : " ") $1
        lut_capacity += $3
        ff_capacity += $4
        dsp_capacity += $5
        uram_capacity += $6
        residual_lut += $15
        residual_ff += $16
        local_q3 += $20
        local_q012 += $38
        local_q012_lut += $39
        local_q012_ff += $40
    }
}
END {
    if (selected != 8 || lut_capacity != 103680 || ff_capacity != 207360 ||
        dsp_capacity != 672 || uram_capacity != 96 ||
        residual_lut != 63852 || residual_ff != 78330 ||
        q3_total != 11177 || q3_lut != 6731 || q3_ff != 3955 ||
        local_q3 != 11177 || local_q012 != 5804 ||
        local_q012_lut != 3695 || local_q012_ff != 1938) exit 13
    printf "selected_grid_range=CLOCKREGION_X0Y5:CLOCKREGION_X3Y6\n"
    printf "selected_regions=%s\n", regions
    printf "selected_lut_capacity=%d\n", lut_capacity
    printf "selected_ff_capacity=%d\n", ff_capacity
    printf "selected_dsp_capacity=%d\n", dsp_capacity
    printf "selected_uram_capacity=%d\n", uram_capacity
    printf "selected_residual_lut=%d\n", residual_lut
    printf "selected_residual_ff=%d\n", residual_ff
    printf "selected_projected_lut=%d\n", residual_lut + q3_lut
    printf "selected_projected_ff=%d\n", residual_ff + q3_ff
    printf "selected_projected_lut_percent=%.3f\n", \
        100.0 * (residual_lut + q3_lut) / lut_capacity
    printf "selected_projected_ff_percent=%.3f\n", \
        100.0 * (residual_ff + q3_ff) / ff_capacity
    printf "selected_existing_quantizer3_primitives=%d\n", local_q3
    printf "selected_existing_quantizer012_primitives=%d\n", local_q012
}' "$TABLE" > "$OUT/p11_quantizer3_candidate.txt"

{
    printf '%s\n' \
        'stage=V5_P10_P9_TO_P11_PHYSICAL_DECISION' \
        'evidence_class=READ_ONLY_MANIFESTED_DIAGNOSIS' \
        "p9_map_output_manifest=$MAP_OUTPUT" \
        "p9_map_output_manifest_sha256=$(sha256sum -- "$MAP_OUTPUT" | awk '{print $1}')" \
        'p9_source_dcp_sha256=f1d8673e27769319af436d22a7461bc148669386596def9c9820ba8ebc716794' \
        'p9_level5_or_higher_windows=16' \
        'p9_level6_or_higher_windows=5' \
        'p10_level6_or_higher_windows=8' \
        'p9_resource_ok=1' 'p9_structure_ok=1' 'p9_placement_ok=1' \
        'p9_pre_place_drc_errors=0' 'p9_post_place_drc_errors=0' \
        'selected_grid_range=CLOCKREGION_X0Y5:CLOCKREGION_X3Y6' \
        'selected_projected_lut_percent=68.078' \
        'selected_projected_ff_percent=39.682' \
        'selected_existing_quantizer3_primitives=11177' \
        'selected_existing_quantizer012_primitives=5804' \
        'attention_ooc_geometry_retained=1' \
        'implementation_commands_run=0' 'checkpoint_written=0' \
        'route_eligible=0' \
        'status=V5_P10_P9_TO_P11_PHYSICAL_DECISION_PASS'
} > "$OUT/summary.txt"
(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_postcheck.txt"
printf 'status=PASS\nimplementation_commands_run=0\ncheckpoint_written=0\nroute_eligible=0\n' \
    > "$OUT/launcher_status.txt"
mapfile -d '' outputs < <(find "$OUT" -maxdepth 1 -type f -size +0c \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$OUT/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/OUTPUT_SHA256SUMS")
printf '%s\n' "$OUT"
