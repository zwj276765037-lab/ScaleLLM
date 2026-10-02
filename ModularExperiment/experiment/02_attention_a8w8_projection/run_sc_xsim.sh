#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
SIM=modular_a8w8_array_16x16_s42_col3_sim
WORK="$ROOT/xsim_work/$SIM"
REPORT_DIR="${HAP_REPORT_DIR:?HAP_REPORT_DIR must name the isolated result directory}"

sources=(
    "$ROOT/rtl/attention/hap_a8w8_group32_lane_s42.sv"
    "$ROOT/rtl/attention/hap_linear_tile_accum_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_array_16x16_s42.sv"
    "$ROOT/rtl/attention/hap_linear_tile_accum_shard_s42.sv"
    "$ROOT/rtl/attention/hap_linear_tile_accum_dual_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_col_shard_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_col_shard_left2_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_col_shard_center12_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_col_shard_right2_s42.sv"
    "$ROOT/rtl/attention/hap_a8w8_array_16x16_s42_col3.sv"
    "$ROOT/ModularExperiment/experiment/02_attention_a8w8_projection/tb/hap_a8w8_array_16x16_s42_col3_tb.sv"
)

rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work" "$REPORT_DIR"
sha256sum "${sources[@]}" "$0" > "$REPORT_DIR/INPUT_SHA256SUMS"
cd "$ROOT"
"$BIN/xvlog" -sv --work "work=$WORK/work" "${sources[@]}" \
    2>&1 | tee "$REPORT_DIR/xvlog.log"
"$BIN/xelab" -L "work=$WORK/work" -L unisims_ver \
    work.hap_a8w8_array_16x16_s42_col3_tb -s "$SIM" \
    2>&1 | tee "$REPORT_DIR/xelab.log"
"$BIN/xsim" "$SIM" -runall --log "$REPORT_DIR/xsim.log" \
    2>&1 | tee "$REPORT_DIR/console.log"
! grep -Eq '^FAIL:|(^|[^[:alnum:]_])(ERROR|FATAL)(:|\[|[[:space:]])' \
    "$REPORT_DIR/xvlog.log" "$REPORT_DIR/xelab.log" "$REPORT_DIR/xsim.log"
grep -Fq 'PASS: col3 array matched monolithic golden for two tiles' \
    "$REPORT_DIR/xsim.log"
