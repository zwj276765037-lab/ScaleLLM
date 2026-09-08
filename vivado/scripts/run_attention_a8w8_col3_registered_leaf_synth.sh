#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_a8w8_col3_registered_leaf_synth_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/attention_a8w8_col3_registered_leaf_synth_$STAMP}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
cd "$ROOT"
inputs=(
    vivado/manifests/attention_a8w8_col3_leaf_sources.list
    vivado/constraints/attention_a8w8_col3_registered_leaf_ooc_150mhz.xdc
    vivado/scripts/probe_attention_a8w8_col3_registered_leaf_synth.tcl
    vivado/scripts/run_attention_a8w8_col3_registered_leaf_synth.sh
    rtl/attention/hap_a8w8_group32_lane_s42.sv
    rtl/attention/hap_linear_tile_accum_s42.sv
    rtl/attention/hap_a8w8_array_16x16_s42.sv
    rtl/attention/hap_linear_tile_accum_shard_s42.sv
    rtl/attention/hap_linear_tile_accum_dual_s42.sv
    rtl/attention/hap_a8w8_col_shard_s42.sv
    rtl/attention/hap_a8w8_col_shard_left2_s42.sv
    rtl/attention/hap_a8w8_col_shard_center12_s42.sv
    rtl/attention/hap_a8w8_col_shard_right2_s42.sv
    rtl/attention/hap_a8w8_array_16x16_s42_col3.sv
    rtl/attention/hap_a8w8_array_16x16_s42_registered_ooc_harness.sv
)
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
status=1
archive() {
    set +e
    printf 'exit_status=%s\n' "$status" > "$HAP_REPORT_DIR/run_status.txt"
    (cd "$HAP_REPORT_DIR" &&
        find . -type f ! -name SHA256SUMS ! -name SHA256SUMS.tmp -print0 |
        sort -z | xargs -0 sha256sum > SHA256SUMS.tmp &&
        mv SHA256SUMS.tmp SHA256SUMS)
}
trap archive EXIT
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_attention_a8w8_col3_registered_leaf_synth.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
summary="$HAP_REPORT_DIR/summary.txt"
[[ -s "$summary" ]]
required=(
    summary.txt
    reference/summary.txt
    reference/post_synth.dcp
    reference/utilization_post_synth.rpt
    reference/utilization_hier_post_synth.rpt
    reference/timing_post_synth.rpt
    reference/clock_utilization_post_synth.rpt
    reference/exceptions_coverage_post_synth.rpt
    col3/summary.txt
    col3/post_synth.dcp
    col3/utilization_post_synth.rpt
    col3/utilization_hier_post_synth.rpt
    col3/timing_post_synth.rpt
    col3/clock_utilization_post_synth.rpt
    col3/exceptions_coverage_post_synth.rpt
)
for file in "${required[@]}"; do
    [[ -s "$HAP_REPORT_DIR/$file" ]]
done
grep -Fqx 'status=PASS' "$summary"
[[ "$(grep -Fxc 'status=PASS' "$summary")" -eq 1 ]]
[[ "$(grep -Fxc 'status=PASS' "$HAP_REPORT_DIR/reference/summary.txt")" -eq 1 ]]
[[ "$(grep -Fxc 'status=PASS' "$HAP_REPORT_DIR/col3/summary.txt")" -eq 1 ]]
grep -Fqx 'timing_gate_scope=setup_only_unplaced' "$summary"
grep -Fqx 'hold_diagnostic_only=1' "$summary"
grep -Fqx 'reference_setup_timing_ok=1' "$summary"
grep -Fqx 'col3_setup_timing_ok=1' "$summary"
for variant in reference col3; do
    grep -Fqx 'timing_gate_scope=setup_only_unplaced' \
        "$HAP_REPORT_DIR/$variant/summary.txt"
    grep -Fqx 'hold_diagnostic_only=1' \
        "$HAP_REPORT_DIR/$variant/summary.txt"
    grep -Fqx 'setup_timing_ok=1' \
        "$HAP_REPORT_DIR/$variant/summary.txt"
done
grep -Fqx 'forbidden_timing_exception_count=0' "$summary"
grep -Fqx 'reference_data_bufg=0' "$summary"
grep -Fqx 'col3_data_bufg=0' "$summary"
grep -Fqx 'reference_dsp48e2=2176' "$summary"
grep -Fqx 'col3_dsp48e2=2176' "$summary"
grep -Fqx 'col3_lane_split=16/96/16' "$summary"
grep -Fqx 'col3_dsp_split=272/1632/272' "$summary"
grep -Fqx 'activation_stage_ff_delta=4096' "$summary"
while IFS= read -r line; do
    sha="${line%% *}"
    file="${line#*  }"
    [[ "$(sha256sum "$file" | awk '{print $1}')" == "$sha" ]]
done < "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
{
    for file in "${required[@]}" INPUT_SHA256SUMS vivado.log vivado.jou; do
        sha256sum "$HAP_REPORT_DIR/$file"
    done
} > "$HAP_REPORT_DIR/OUTPUT_MANIFEST"
expected_output_rows=$((${#required[@]} + 3))
[[ "$(wc -l < "$HAP_REPORT_DIR/OUTPUT_MANIFEST")" -eq "$expected_output_rows" ]]
while IFS= read -r line; do
    sha="${line%% *}"
    file="${line#*  }"
    [[ -s "$file" ]]
    [[ "$(sha256sum "$file" | awk '{print $1}')" == "$sha" ]]
done < "$HAP_REPORT_DIR/OUTPUT_MANIFEST"
status=0
printf '%s\n' "$HAP_REPORT_DIR"
