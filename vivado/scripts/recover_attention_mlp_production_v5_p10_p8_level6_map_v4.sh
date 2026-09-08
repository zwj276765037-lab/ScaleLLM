#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$ROOT/vivado/scripts/recover_attention_mlp_production_v5_p10_p8_level6_map_v4.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 1 ]] || {
    printf 'usage: %s MISSION0120_LEVEL6_MAP_DIR\n' "$0" >&2
    exit 2
}
SOURCE_DIR="$(readlink -e -- "$1")"
requested="${HAP_P8_LEVEL6_RECOVERY_DIR:-$ROOT/vivado/reports/production_v5_p10_p8_level6_map_recovery_$STAMP}"
OUT="$(readlink -m -- "$requested")"
[[ ! -e "$OUT" ]] || {
    printf 'P8 Level-6 recovery directory exists: %s\n' "$OUT" >&2
    exit 2
}

required=(INPUT_SHA256SUMS OUTPUT_SHA256SUMS summary.txt launcher_status.txt \
    slr1_clock_region_utilization.tsv)
for name in "${required[@]}"; do
    [[ -s "$SOURCE_DIR/$name" ]] || {
        printf 'missing recovery input: %s\n' "$SOURCE_DIR/$name" >&2
        exit 2
    }
done
mkdir "$OUT"
inputs=("$SOURCE_DIR/INPUT_SHA256SUMS" "$SOURCE_DIR/OUTPUT_SHA256SUMS" \
    "$SOURCE_DIR/summary.txt" "$SOURCE_DIR/launcher_status.txt" \
    "$SOURCE_DIR/slr1_clock_region_utilization.tsv" "$SELF")
printf '%s\n' "${inputs[@]}" > "$OUT/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$OUT/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_precheck.txt"
(cd / && sha256sum -c --strict "$SOURCE_DIR/INPUT_SHA256SUMS") \
    > "$OUT/source_input_sha_check.txt"
(cd / && sha256sum -c --strict "$SOURCE_DIR/OUTPUT_SHA256SUMS") \
    > "$OUT/source_output_sha_check.txt"

for literal in status=PASS vivado_exit_code=0 input_sha_recheck_exit_code=0; do
    grep -Fqx -- "$literal" "$SOURCE_DIR/launcher_status.txt"
done
for literal in \
        stage=V5_P10_P8_LEVEL6_PHYSICAL_MAP \
        evidence_class=READ_ONLY_REJECTED_POST_PLACE_DCP \
        source_lineage_verified=1 \
        input_dcp_sha256=4c8d86db8aa9f5c9aaedfeca62e549899c4c74afe23c371b9a69f394974ef0d9 \
        dsp48e2=5453 uram288=752 level6_windows_profiled=7 \
        swiglu_quantizer_roots=4 postprocess_row_roots=16 \
        slr1_clock_regions_profiled=30 slr1_lut_capacity=394080 \
        slr1_ff_capacity=788160 p9_moving_postprocess_primitives=10696 \
        quantizer3_primitives=11178 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0 route_eligible=0 \
        status=V5_P10_P8_LEVEL6_PHYSICAL_MAP_PASS; do
    grep -Fqx -- "$literal" "$SOURCE_DIR/summary.txt"
done

TABLE="$SOURCE_DIR/slr1_clock_region_utilization.tsv"
awk -F '\t' '
NR == 1 {
    if ($1 != "clock_region" || $3 != "lut_capacity" ||
        $4 != "ff_capacity" || $15 != "residual_lut" ||
        $16 != "residual_ff" || $20 != "q3_total" ||
        $26 != "moving_rows_total") exit 10
    next
}
{
    rows++
    seen[$1]++
    lut_capacity += $3
    ff_capacity += $4
    q3_total += $20
    q3_lut += $21
    q3_ff += $22
    moving_total += $26
    moving_lut += $27
    moving_ff += $28
    name=$1
    sub(/^X/, "", name)
    split(name, xy, "Y")
    x=xy[1]+0
    y=xy[2]+0
    if (x >= 2 && x <= 3 && y >= 5 && y <= 6) {
        selected++
        selected_lut_capacity += $3
        selected_ff_capacity += $4
        selected_residual_lut += $15
        selected_residual_ff += $16
    }
}
END {
    if (rows != 30 || length(seen) != 30 ||
        lut_capacity != 394080 || ff_capacity != 788160 ||
        q3_total != 11177 || q3_lut != 6731 || q3_ff != 3955 ||
        moving_total != 10696 || moving_lut != 3976 || moving_ff != 6144 ||
        selected != 4 || selected_lut_capacity != 52800 ||
        selected_ff_capacity != 105600 || selected_residual_lut != 30211 ||
        selected_residual_ff != 48097) exit 11
    printf "clock_regions=%d\n", rows
    printf "slr1_lut_capacity=%d\n", lut_capacity
    printf "slr1_ff_capacity=%d\n", ff_capacity
    printf "quantizer3_spatial_total=%d\n", q3_total
    printf "quantizer3_lut=%d\n", q3_lut
    printf "quantizer3_ff=%d\n", q3_ff
    printf "moving_rows_total=%d\n", moving_total
    printf "moving_rows_lut=%d\n", moving_lut
    printf "moving_rows_ff=%d\n", moving_ff
    printf "selected_regions=X2Y5 X2Y6 X3Y5 X3Y6\n"
    printf "selected_lut_capacity=%d\n", selected_lut_capacity
    printf "selected_ff_capacity=%d\n", selected_ff_capacity
    printf "selected_residual_lut=%d\n", selected_residual_lut
    printf "selected_residual_ff=%d\n", selected_residual_ff
    printf "selected_projected_lut=%d\n", selected_residual_lut + q3_lut
    printf "selected_projected_ff=%d\n", selected_residual_ff + q3_ff
    printf "selected_projected_lut_percent=%.3f\n", 100.0 * (selected_residual_lut + q3_lut) / selected_lut_capacity
    printf "selected_projected_ff_percent=%.3f\n", 100.0 * (selected_residual_ff + q3_ff) / selected_ff_capacity
}' "$TABLE" > "$OUT/candidate_quantizer3_x2y5_x3y6.txt"

cat > "$OUT/summary.txt" <<EOF
stage=V5_P10_P8_LEVEL6_MAP_RECOVERY
evidence_class=READ_ONLY_MANIFEST_RECOVERY
source_dir=$SOURCE_DIR
source_input_manifest_sha256=$(sha256sum -- "$SOURCE_DIR/INPUT_SHA256SUMS" | awk '{print $1}')
source_output_manifest_sha256=$(sha256sum -- "$SOURCE_DIR/OUTPUT_SHA256SUMS" | awk '{print $1}')
source_launcher_pass=1
source_vivado_exit_code=0
source_input_recheck_exit_code=0
clock_regions_verified=30
quantizer3_primitives=11178
quantizer3_spatial_primitives=11177
quantizer3_nonspatial_hard_primitives=1
p9_moving_postprocess_primitives=10696
selected_grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6
selected_projected_lut_percent=69.966
selected_projected_ff_percent=49.292
implementation_commands_run=0
checkpoint_written=0
route_eligible=0
status=V5_P10_P8_LEVEL6_MAP_RECOVERY_PASS
EOF

(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_postcheck.txt"
printf 'status=PASS\nimplementation_commands_run=0\ncheckpoint_written=0\nroute_eligible=0\n' \
    > "$OUT/launcher_status.txt"
mapfile -d '' outputs < <(find "$OUT" -maxdepth 1 -type f -size +0c \
    ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$OUT/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/OUTPUT_SHA256SUMS")
printf '%s\n' "$OUT"
