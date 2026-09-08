#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SIM="hap_mlp_input_frontend16_compact_cache_sim_${STAMP}"
WORK="$ROOT/xsim_work/$SIM"
OUT="${HAP_REPORT_DIR:-$ROOT/vivado/reports/mlp_input_frontend16_compact_cache_xsim_$STAMP}"
mkdir -p "$WORK/work" "$OUT"

archive() {
    for f in xvlog.log xvlog.pb xelab.log xelab.pb; do
        [[ -f "$ROOT/$f" ]] && cp -p "$ROOT/$f" "$OUT/$f"
    done
    [[ -f "$WORK/xsim.log" ]] && cp -p "$WORK/xsim.log" "$OUT/xsim.log"
    (cd "$OUT" && sha256sum -- * > SHA256SUMS.tmp &&
        mv SHA256SUMS.tmp SHA256SUMS) || true
}
trap archive EXIT

cd "$ROOT"
sha256sum \
    rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv \
    rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv \
    rtl/attention/hap_robust_a8_quantizer.sv \
    rtl/attention/hap_activation_cache_8row.sv \
    tb/hap_mlp_input_frontend16_compact_cache_tb.sv \
    > "$OUT/INPUT_SHA256SUMS"

"$BIN/xvlog" -sv --work "work=$WORK/work" \
    rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv \
    rtl/attention/hap_u16_div_u8_seq.sv \
    rtl/attention/hap_robust_a8_quantizer.sv \
    rtl/attention/hap_activation_cache_8row.sv \
    rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv \
    tb/hap_mlp_input_frontend16_compact_cache_tb.sv
GLBL_V="${GLBL_V:-$BIN/../ids_lite/ISE/verilog/src/glbl.v}"
"$BIN/xvlog" --work "work=$WORK/work" "$GLBL_V"
"$BIN/xelab" -L "work=$WORK/work" -L xpm -L unisims_ver \
    work.hap_mlp_input_frontend16_compact_cache_tb work.glbl \
    -s "$SIM" --debug typical
"$BIN/xsim" "$SIM" -runall --log "$WORK/xsim.log"

if grep -Eiq '(^|[^[:alnum:]_])(FAIL|ERROR|FATAL)(:|\[|[[:space:]])' \
        "$ROOT/xvlog.log" "$ROOT/xelab.log" "$WORK/xsim.log"; then
    echo "compact input-cache regression rejected failure marker" >&2
    exit 1
fi
[[ "$(grep -c '^PASS: compact MLP input cache bit-exact .*mismatches=0 saturation=.*$' \
        "$WORK/xsim.log" || true)" -eq 1 ]] || {
    echo "compact input-cache regression requires one trusted PASS" >&2
    exit 1
}
printf '%s\n' "$OUT"
