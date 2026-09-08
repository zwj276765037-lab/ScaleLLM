#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-python3}"
SIM=hap_projection_core8x16_capture_fanout_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/projection_core8x16_capture_fanout_xsim_$STAMP}"
VECTOR_DIR="$ROOT/data/projection_core8x16"

rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work" "$REPORT_DIR"
cd "$ROOT"
status=1

archive() {
    set +e
    for f in xvlog.log xvlog.pb xelab.log xelab.pb xsim.jou; do
        [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
    done
    [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
    [[ -f "$WORK/console.log" ]] && cp -p "$WORK/console.log" "$REPORT_DIR/console.log"
    printf 'exit_status=%s\ntool=%s\ntop=%s\n' "$status" \
        "$("$BIN/xsim" -version 2>/dev/null | head -1)" \
        hap_projection_core8x16_capture_fanout_tb > "$REPORT_DIR/summary.txt"
    (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive EXIT

"$PYTHON" model/generate_projection_core8x16_vectors.py
for f in input_s24.mem weight_s8.mem weight_meta16.mem expected_s24.mem; do
    [[ -f "$VECTOR_DIR/$f" ]] || {
        printf 'missing golden vector: %s\n' "$VECTOR_DIR/$f" >&2
        exit 1
    }
done

sources=(
    rtl/attention/hap_fixbit_v2_pkg.sv
    rtl/attention/hap_hadamard32_norm_stream.sv
    rtl/attention/hap_u16_div_u8_seq.sv
    rtl/attention/hap_robust_a8_quantizer.sv
    rtl/attention/hap_activation_cache_8row.sv
    rtl/attention/hap_attention_frontend_8row.sv
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
    rtl/attention/hap_projection_core8x16.sv
    tb/hap_projection_core8x16_capture_fanout_tb.sv
)

sha256sum "${sources[@]}" "$VECTOR_DIR"/*.mem \
    vivado/scripts/run_projection_core8x16_capture_fanout_xsim.sh \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
"$BIN/xvlog" -sv --work "work=$WORK/work" "${sources[@]}"
"$BIN/xelab" -L "work=$WORK/work" -L unisims_ver \
    work.hap_projection_core8x16_capture_fanout_tb -s "$SIM"
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log" \
    2>&1 | tee "$WORK/console.log"
! grep -q '^FAIL:' "$WORK/console.log"
grep -Fq 'PASS: projection capture fanout kept 128-group A8W8 bit exact' \
    "$WORK/console.log"
status=0
printf '%s\n' "$REPORT_DIR"
