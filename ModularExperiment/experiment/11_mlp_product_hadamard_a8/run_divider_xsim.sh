#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/11_mlp_product_hadamard_a8"
RESULT="$ROOT/ModularExperiment/result/11_mlp_product_hadamard_a8"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/fp_common/xsim/${stamp}_u44_div_u36_radix16_directed_random"
build="${TMPDIR:-/tmp}/scalellm_modular_m11_divider_xsim/$stamp"
mkdir -p "$report" "$build"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

sources=(
    "$MODULE/rtl/m11_u44_div_u36_radix16.sv"
    "$MODULE/tb/m11_div_tb.sv"
    "$MODULE/vivado/run_divider_xsim.tcl"
)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_divider_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'PASS: M11 radix16 divider|FAIL: M11|M11_DIV_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M11 radix16 divider cases=265 mismatches=0' \
        "$report/console.log" && ! grep -Fq 'FAIL: M11' "$report/console.log"; then
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
