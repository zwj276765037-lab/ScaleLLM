#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$ROOT/vivado/scripts/derive_attention_mlp_production_v5_p10_candidate.sh"
STAMP="$(date +%Y%m%d_%H%M%S)"

[[ $# -eq 2 ]] || {
    printf 'usage: %s P9_PLACE_DIR P8_LEVEL6_RECOVERY_DIR\n' "$0" >&2
    exit 2
}
P9_DIR="$(readlink -e -- "$1")"
RECOVERY_DIR="$(readlink -e -- "$2")"
requested="${HAP_P10_DECISION_DIR:-$ROOT/vivado/reports/production_v5_p10_candidate_$STAMP}"
OUT="$(readlink -m -- "$requested")"
[[ ! -e "$OUT" ]] || {
    printf 'P10 decision directory exists: %s\n' "$OUT" >&2
    exit 2
}

P9_OUTPUT="$P9_DIR/OUTPUT_SHA256SUMS"
P9_SUMMARY="$P9_DIR/summary.txt"
P9_LAUNCHER="$P9_DIR/launcher_status.txt"
P9_CONGESTION="$P9_DIR/congestion_post_place.rpt"
RECOVERY_OUTPUT="$RECOVERY_DIR/OUTPUT_SHA256SUMS"
RECOVERY_INPUT="$RECOVERY_DIR/INPUT_SHA256SUMS"
RECOVERY_SUMMARY="$RECOVERY_DIR/summary.txt"
for path in "$P9_OUTPUT" "$P9_SUMMARY" "$P9_LAUNCHER" "$P9_CONGESTION" \
        "$RECOVERY_OUTPUT" "$RECOVERY_INPUT" "$RECOVERY_SUMMARY" "$SELF"; do
    [[ -s "$path" ]] || { printf 'missing P10 decision input: %s\n' "$path" >&2; exit 2; }
done

SOURCE_DIR="$(awk -F= '$1=="source_dir" {print substr($0,index($0,"=")+1)}' "$RECOVERY_SUMMARY")"
TABLE="$SOURCE_DIR/slr1_clock_region_utilization.tsv"
[[ -s "$TABLE" ]] || { printf 'missing authenticated clock-region table: %s\n' "$TABLE" >&2; exit 2; }

mkdir "$OUT"
inputs=("$P9_OUTPUT" "$P9_SUMMARY" "$P9_LAUNCHER" "$P9_CONGESTION" \
    "$RECOVERY_OUTPUT" "$RECOVERY_INPUT" "$RECOVERY_SUMMARY" "$TABLE" "$SELF")
printf '%s\n' "${inputs[@]}" > "$OUT/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$OUT/INPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$OUT/INPUT_SHA256SUMS") \
    > "$OUT/input_sha_precheck.txt"
(cd / && sha256sum -c --strict "$P9_OUTPUT") \
    > "$OUT/p9_output_sha_check.txt"
(cd / && sha256sum -c --strict "$RECOVERY_OUTPUT") \
    > "$OUT/recovery_output_sha_check.txt"
(cd / && sha256sum -c --strict "$RECOVERY_INPUT") \
    > "$OUT/recovery_input_sha_check.txt"

for literal in \
        stage=V5_P10_P9_POST_PLACE_FAST_GATE \
        failure_stage=post_place_fast_gate acceptance_evidence=0 \
        route_eligible=0 checkpoint_written=0 diagnostic_checkpoint_written=1 \
        input_dcp_sha256=734fe5c776f7735deb4dade2c888f1af90439a3e99d22004d330a4f814dfa731 \
        input_manifest_entries=13 provenance_verified=1 pre_place_verified=1 \
        p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6 \
        p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
        dsp48e2=5453 uram288=752 unplaced_primitives=0 \
        wrong_slr_primitives=0 p9_quantizer3_wrong_region=0 \
        p9_quantizer3_unplaced=0 pre_place_drc_errors=0 \
        post_place_drc_errors=0 congestion_level5_or_higher_windows=16 \
        congestion_level6_or_higher_windows=5 resource_ok=1 structure_ok=1 \
        placement_ok=1 optimizer_extras_ok=1 fast_gate_ok=0 status=FAIL; do
    grep -Fqx -- "$literal" "$P9_SUMMARY"
done
for literal in status=FAIL acceptance_evidence=0 route_eligible=0 \
        final_exit_code=1 vivado_exit_code=1 input_sha_recheck_exit_code=0 \
        input_manifest_sha_match=1 checkpoint_written=0 bitstream_generated=0; do
    grep -Fqx -- "$literal" "$P9_LAUNCHER"
done
for literal in clock_regions_verified=30 quantizer3_primitives=11178 \
        p9_moving_postprocess_primitives=10696 \
        implementation_commands_run=0 checkpoint_written=0 route_eligible=0 \
        status=V5_P10_P8_LEVEL6_MAP_RECOVERY_PASS; do
    grep -Fqx -- "$literal" "$RECOVERY_SUMMARY"
done

awk -F '|' '
function trim(s) {gsub(/^[[:space:]]+|[[:space:]]+$/, "", s); return s}
/^\| (North|South|East|West)/ {
    level=trim($4)
    if (level == "6") {
        count++
        window=trim($5)
        if (window !~ /Y(40[2-9]|4[1-7][0-9]|480)/) outside++
        print "level6_window_" count "=" window
    }
}
END {
    if (count != 5 || outside != 0) exit 12
    print "level6_window_count=" count
    print "level6_all_y402_y480=1"
}' "$P9_CONGESTION" > "$OUT/p9_level6_windows.txt"

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
    if (x >= 0 && x <= 2 && y == 5) {
        selected++
        lut_capacity += $3
        ff_capacity += $4
        residual_lut += $15
        residual_ff += $16
        local_q3 += $20
        moving_total += $26
        moving_lut += $27
        moving_ff += $28
        local_q012 += $38
    }
}
END {
    if (selected != 3 || lut_capacity != 39360 || ff_capacity != 78720 ||
        residual_lut != 19174 || residual_ff != 29675 ||
        q3_total != 11177 || q3_lut != 6731 || q3_ff != 3955 ||
        local_q3 != 0 || moving_total != 2202 || moving_lut != 754 ||
        moving_ff != 1304 || local_q012 != 0) exit 13
    printf "selected_grid_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y5\n"
    printf "selected_regions=X0Y5 X1Y5 X2Y5\n"
    printf "selected_lut_capacity=%d\n", lut_capacity
    printf "selected_ff_capacity=%d\n", ff_capacity
    printf "selected_residual_lut=%d\n", residual_lut
    printf "selected_residual_ff=%d\n", residual_ff
    printf "selected_projected_lut=%d\n", residual_lut + q3_lut
    printf "selected_projected_ff=%d\n", residual_ff + q3_ff
    printf "selected_projected_lut_percent=%.3f\n", 100.0 * (residual_lut + q3_lut) / lut_capacity
    printf "selected_projected_ff_percent=%.3f\n", 100.0 * (residual_ff + q3_ff) / ff_capacity
    printf "selected_existing_quantizer3_primitives=%d\n", local_q3
    printf "selected_existing_quantizer012_primitives=%d\n", local_q012
    printf "selected_p9_moving_row_primitives=%d\n", moving_total
}' "$TABLE" > "$OUT/p10_quantizer3_candidate.txt"

cat > "$OUT/summary.txt" <<EOF
stage=V5_P10_P9_TO_P10_PHYSICAL_DECISION
evidence_class=READ_ONLY_MANIFESTED_DIAGNOSIS
p9_place_output_manifest=$P9_OUTPUT
p9_place_output_manifest_sha256=$(sha256sum -- "$P9_OUTPUT" | awk '{print $1}')
p8_level6_recovery_manifest=$RECOVERY_OUTPUT
p8_level6_recovery_manifest_sha256=$(sha256sum -- "$RECOVERY_OUTPUT" | awk '{print $1}')
p9_level5_or_higher_windows=16
p9_level6_or_higher_windows=5
p9_level6_all_y402_y480=1
p9_resource_ok=1
p9_structure_ok=1
p9_placement_ok=1
p9_pre_place_drc_errors=0
p9_post_place_drc_errors=0
selected_grid_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y5
selected_projected_lut_percent=65.816
selected_projected_ff_percent=42.721
selected_existing_quantizer3_primitives=0
selected_existing_quantizer012_primitives=0
implementation_commands_run=0
checkpoint_written=0
route_eligible=0
status=V5_P10_P9_TO_P10_PHYSICAL_DECISION_PASS
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
