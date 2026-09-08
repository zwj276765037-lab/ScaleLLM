#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_full_command16_s45_sim
WORK="$ROOT/xsim_work/$SIM"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_full_command16_s45_xsim_$STAMP}"
mkdir -p "$REPORT_DIR"

archive_outputs() {
    for f in xvlog.log xvlog.pb xelab.log xelab.pb; do
        [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
    done
    [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
    grep -E '^(PASS:|ERROR:|FATAL:)|^Time:|^xsim: ' \
        "$REPORT_DIR/xsim.log" > "$REPORT_DIR/summary.txt" || true
    (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive_outputs EXIT

cd "$ROOT"
"$PYTHON" model/generate_mlp_silu_artifacts.py >/dev/null
"$PYTHON" model/generate_mlp_full_command16_s45_vectors.py
sha256sum \
    rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_down_activation_cache16.sv \
    rtl/mlp/hap_mlp_full_command16_s45.sv \
    tb/hap_mlp_full_command16_s45_tb.sv \
    model/generate_mlp_full_command16_s45_vectors.py \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
rm -rf "$WORK" "$ROOT/xsim.dir/$SIM"
mkdir -p "$WORK/work"
"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/attention/hap_fixbit_v2_pkg.sv \
    rtl/attention/hap_hadamard32_norm_stream.sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/attention/hap_robust_a8_quantizer.sv \
    rtl/attention/hap_activation_cache_8row.sv \
    rtl/attention/hap_attention_frontend_8row.sv \
    rtl/mlp/hap_mlp_input_frontend16_cache.sv \
    rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv \
    rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv \
    rtl/mlp/hap_a8w4_pack2_dsp.sv \
    rtl/mlp/hap_a8w4_group32_pack2_s17.sv \
    rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv \
    rtl/mlp/hap_a8w4_group32_lane2_s36.sv \
    rtl/mlp/hap_a8w4_slice8x16_group_s36.sv \
    rtl/mlp/hap_mlp_tile_accum_s36.sv \
    rtl/mlp/hap_mlp_silu_mul.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_gate_up_external_scheduler16_q4.sv \
    rtl/mlp/hap_mlp_down_activation_cache16.sv \
    rtl/mlp/hap_mlp_down_group_major_accum_s45.sv \
    rtl/mlp/hap_mlp_down_activation_replay16.sv \
    rtl/mlp/hap_mlp_shared_slice8x16_s43_s45.sv \
    rtl/mlp/hap_mlp_shared_dual_slice16x16_s43_s45.sv \
    rtl/mlp/hap_axi512_w4_weight_reader.sv \
    rtl/mlp/hap_ddr512_w4_halfgroup_async.sv \
    rtl/mlp/hap_mlp_w4_dual_channel_join.sv \
    rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv \
    rtl/mlp/hap_mlp_serial_ddr_command16_s45.sv \
    rtl/mlp/hap_mlp_full_command16_s45.sv \
    tb/hap_mlp_full_command16_s45_tb.sv
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
"$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V"
"$BIN/xelab" -L "work=$WORK/work" -L xpm -L unisims_ver \
    work.hap_mlp_full_command16_s45_tb work.glbl \
    -s "$SIM" --debug typical
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$ROOT/xvlog.log" "$ROOT/xelab.log" "$WORK/xsim.log"; then
    printf 'full-command regression rejected FAIL/Error/Fatal marker\n' >&2
    exit 1
fi
[[ "$(grep -c '^PASS: hap_mlp_full_command16_s45 .*mismatches=0$' \
        "$WORK/xsim.log" || true)" -eq 1 ]] || {
    printf 'full-command regression requires exactly one trusted PASS marker\n' >&2
    exit 1
}
echo 'PASS: full S24-input gate/up+down MLP command xsim gate completed.'
printf '%s\n' "$REPORT_DIR"
