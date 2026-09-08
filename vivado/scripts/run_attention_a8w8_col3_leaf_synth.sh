#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_a8w8_col3_leaf_synth_$STAMP}"
export HAP_BUILD_DIR="${HAP_BUILD_DIR:-$ROOT/vivado/build/attention_a8w8_col3_leaf_synth_$STAMP}"
mkdir -p "$HAP_REPORT_DIR" "$HAP_BUILD_DIR"
cd "$ROOT"

inputs=(
    vivado/manifests/attention_a8w8_col3_leaf_sources.list
    vivado/constraints/attention_a8w8_col3_leaf_ooc_150mhz.xdc
    vivado/scripts/probe_attention_a8w8_col3_leaf_synth.tcl
    vivado/scripts/run_attention_a8w8_col3_leaf_synth.sh
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
)
sha256sum "${inputs[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"

status=1
archive() {
    set +e
    printf 'exit_status=%s\n' "$status" > "$HAP_REPORT_DIR/run_status.txt"
    (cd "$HAP_REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/probe_attention_a8w8_col3_leaf_synth.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
status=0
printf '%s\n' "$HAP_REPORT_DIR"
