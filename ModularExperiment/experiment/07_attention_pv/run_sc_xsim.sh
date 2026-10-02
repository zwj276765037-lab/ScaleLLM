#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/07_attention_pv"
RESULT="$ROOT/ModularExperiment/result/07_attention_pv"
BIN="${VIVADO_BIN_DIR:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin}"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/sc/xsim/${stamp}_matched_workload"
sim=modular_pv_sc_sim
work="$ROOT/xsim_work/$sim"
mkdir -p "$report" "$work/work"
rm -rf "$ROOT/xsim.dir/$sim"
printf 'RUNNING\n' > "$report/STATUS"
sha256sum "$ROOT/rtl/attention/hap_pv_tile16_s43.sv" \
    "$MODULE/tb/hap_pv_tile16_s43_tb.sv" "$MODULE/data/SC_SOURCE_SHA256SUMS" \
    > "$report/INPUT_SHA256SUMS"
cd "$ROOT"
set +e
"$BIN/xvlog" -sv --work "work=$work/work" \
    "$ROOT/rtl/attention/hap_pv_tile16_s43.sv" \
    "$MODULE/tb/hap_pv_tile16_s43_tb.sv" > "$report/xvlog.log" 2>&1 && \
"$BIN/xelab" -L "work=$work/work" work.hap_pv_tile16_s43_tb \
    -generic_top "DATA_DIR=$MODULE/data/sc_source" -s "$sim" \
    > "$report/xelab.log" 2>&1 && \
"$BIN/xsim" "$sim" -runall --log "$report/xsim.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'PV_TILE16_METRIC_JSON:|PASS: PV|FAIL: PV' "$report/xsim.log" \
    > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: PV tile16 S43' "$report/xsim.log"; then
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
