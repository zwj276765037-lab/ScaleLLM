#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VIVADO_ROOT="${VIVADO_ROOT:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado}"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
SIM=hap_mlp_swiglu_product_frontend16_q4_sim
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_swiglu_product_frontend16_q4_xsim_$STAMP}"
WORK="$ROOT/xsim_work/$SIM"
mkdir -p "$REPORT_DIR"

archive_outputs() {
    for f in xvlog.log xvlog.pb xelab.log xelab.pb; do
        [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$REPORT_DIR/$f"
    done
    [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$REPORT_DIR/xsim.log"
    [[ -f "$WORK/console.log" ]] && cp -p "$WORK/console.log" "$REPORT_DIR/console.log"
    local log="$REPORT_DIR/xsim.log"
    [[ -s "$log" ]] || log="$REPORT_DIR/console.log"
    grep -E '^(PASS:|ERROR:|FATAL:)|^Time:|^xsim: ' "$log" \
        > "$REPORT_DIR/summary.txt" || true
    (cd "$REPORT_DIR" && sha256sum ./* > SHA256SUMS)
}
trap archive_outputs EXIT

cd "$ROOT"
PYTHONPATH=model "$PYTHON" \
    model/generate_mlp_swiglu_product_frontend16_q4_vectors.py
sha256sum \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/mlp/hap_mlp_silu_mul.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    tb/hap_mlp_swiglu_product_frontend16_q4_tb.sv \
    model/generate_mlp_swiglu_product_frontend16_q4_vectors.py \
    > "$REPORT_DIR/INPUT_SHA256SUMS"
rm -rf "$WORK" "xsim.dir/$SIM"
mkdir -p "$WORK"
"$VIVADO_ROOT/bin/xvlog" -sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/mlp/hap_mlp_silu_mul.sv \
    rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv \
    rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv \
    rtl/mlp/hap_mlp_product_frontend16_q4.sv \
    rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv \
    tb/hap_mlp_swiglu_product_frontend16_q4_tb.sv
"$VIVADO_ROOT/bin/xelab" hap_mlp_swiglu_product_frontend16_q4_tb \
    -L unisims_ver -s "$SIM"
"$VIVADO_ROOT/bin/xsim" "$SIM" -runall --log "$WORK/xsim.log"
[[ -s "$WORK/xsim.log" ]] || {
    printf 'missing SwiGLU xsim log\n' >&2
    exit 1
}
if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$ROOT/xvlog.log" "$ROOT/xelab.log" "$WORK/xsim.log"; then
    printf 'SwiGLU regression rejected FAIL/Error/Fatal marker\n' >&2
    exit 1
fi
[[ "$(grep -c '^PASS: hap_mlp_swiglu_product_frontend16_q4 .*mismatches=0$' \
        "$WORK/xsim.log" || true)" -eq 1 ]] || {
    printf 'SwiGLU regression requires exactly one trusted PASS marker\n' >&2
    exit 1
}
printf '%s\n' "$REPORT_DIR"
