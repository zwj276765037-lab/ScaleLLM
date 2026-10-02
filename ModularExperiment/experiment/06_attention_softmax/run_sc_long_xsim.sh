#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/06_attention_softmax"
RESULT="$ROOT/ModularExperiment/result/06_attention_softmax"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/sc/xsim/${stamp}_long_96_rows"
sim="modular_softmax_sc_long_${stamp}"
work="$ROOT/xsim_work/$sim"
mkdir -p "$report" "$work/work"
printf 'RUNNING\n' > "$report/STATUS"
sha256sum "$ROOT/rtl/attention/hap_fixbit_v2_pkg.sv" \
    "$ROOT/rtl/attention/hap_unsigned_div_seq.sv" \
    "$ROOT/rtl/attention/hap_softmax_exp_u17.sv" \
    "$ROOT/rtl/attention/hap_softmax_recip_u17.sv" \
    "$ROOT/rtl/attention/hap_softmax_prob_u16.sv" \
    "$ROOT/rtl/attention/hap_softmax_row_128.sv" \
    "$MODULE/tb/hap_softmax_row_128_long_tb.sv" \
    "$ROOT/data/softmax_row_128/input.mem" \
    "$ROOT/data/softmax_row_128/expected_prob.mem" \
    > "$report/INPUT_SHA256SUMS"
cd "$ROOT"
set +e
"$BIN/xvlog" -sv --work "work=$work/work" \
    "$ROOT/rtl/attention/hap_fixbit_v2_pkg.sv" \
    "$ROOT/rtl/attention/hap_unsigned_div_seq.sv" \
    "$ROOT/rtl/attention/hap_softmax_exp_u17.sv" \
    "$ROOT/rtl/attention/hap_softmax_recip_u17.sv" \
    "$ROOT/rtl/attention/hap_softmax_prob_u16.sv" \
    "$ROOT/rtl/attention/hap_softmax_row_128.sv" \
    "$MODULE/tb/hap_softmax_row_128_long_tb.sv" \
    > "$report/xvlog.log" 2>&1 && \
"$BIN/xelab" -L "work=$work/work" work.hap_softmax_row_128_long_tb \
    -generic_top "DATA_DIR=$ROOT/data/softmax_row_128" -s "$sim" \
    > "$report/xelab.log" 2>&1 && \
"$BIN/xsim" "$sim" -runall --log "$report/xsim.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'SOFTMAX_ROW_128_LONG_METRIC_JSON:|PASS: long Softmax|FAIL: long Softmax|MISMATCH' \
    "$report/xsim.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: long Softmax row128' "$report/xsim.log"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
