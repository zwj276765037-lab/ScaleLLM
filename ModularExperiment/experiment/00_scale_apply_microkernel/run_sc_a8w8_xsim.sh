#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/00_scale_apply_microkernel"
RESULT="$ROOT/ModularExperiment/result/00_scale_apply_microkernel"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"

python3 "$MODULE/legacy_seed/generate_vectors.py"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/sc/xsim/${stamp}_a8w8_scalecode"
build="${TMPDIR:-/tmp}/scalellm_modular_scale_apply_xsim/${stamp}_sc"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT=sc HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"
sha256sum "$ROOT/rtl/attention/hap_a8w8_group32_lane_s42.sv" \
    "$MODULE/legacy_seed/tb/m3_lane_tb.sv" \
    "$MODULE/legacy_seed/generate_vectors.py" \
    "$MODULE/vivado/run_matched_xsim.tcl" > "$report/INPUT_SHA256SUMS"
set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_matched_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M3_LANE_METRIC_JSON:|PASS: M3|FAIL: M3|MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && grep -Fq 'PASS: M3 matched group32 lane' "$report/console.log"; then
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
