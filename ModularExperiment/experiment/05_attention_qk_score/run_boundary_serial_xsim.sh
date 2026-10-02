#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 2 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/05_attention_qk_score"
RESULT="$ROOT/ModularExperiment/result/05_attention_qk_score"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2

stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_qk_boundary_serial_physical_bp${backpressure}"
build="${TMPDIR:-/tmp}/scalellm_modular_m05_boundary_serial/${stamp}_${variant}_bp${backpressure}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/boundary_fp_ooc.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/boundary_sc_ooc.sources"
sources=("$MODULE/tb/m05_qk_boundary_serial_ooc_wrapper_tb.sv"
    "$MODULE/vivado/run_boundary_serial_xsim.tcl" "$list")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
if [[ "$variant" != sc ]]; then
    sources+=("$MODULE/vivado/create_fp_ip.tcl"
        "$MODULE/vivado/create_boundary_fp_ip.tcl"
        "$MODULE/vivado/create_boundary_all_fp_ip.tcl")
fi
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_boundary_serial_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M05_BOUNDARY_SERIAL_METRIC_JSON:|PASS: M05|FAIL: M05' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M05 QK boundary serial physical wrapper' \
            "$report/console.log" && \
        ! grep -Fq 'FAIL: M05' "$report/console.log"; then
    printf 'PASS\n' > "$report/STATUS"
else
    printf 'FAIL\n' > "$report/STATUS"
    rc=1
fi
find "$build" -type f -name '*.xci' -print0 | sort -z | xargs -0 -r sha256sum \
    > "$report/FP_XCI_SHA256SUMS"
printf '%s\n' "$rc" > "$report/exit_status.txt"
find "$report" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum > "$report/SHA256SUMS"
printf '%s\n' "$report"
exit "$rc"
