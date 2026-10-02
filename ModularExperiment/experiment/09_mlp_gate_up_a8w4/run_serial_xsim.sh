#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 2 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/09_mlp_gate_up_a8w4"
RESULT="$ROOT/ModularExperiment/result/09_mlp_gate_up_a8w4"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2

python3 "$MODULE/model/generate_vectors.py"
stamp="$(date +%Y%m%d_%H%M%S)"
mode=continuous
[[ "$backpressure" == 1 ]] && mode=periodic_backpressure
report="$RESULT/raw/$variant/xsim/${stamp}_gate_up_a8w4_serial_ooc_wrapper_${mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m09_serial_xsim/${stamp}_${variant}_${mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/fp_ooc.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc_ooc.sources"
sources=("$MODULE/model/generate_vectors.py"
    "$MODULE/tb/m09_gate_up_serial_ooc_wrapper_tb.sv"
    "$MODULE/vivado/run_serial_xsim.tcl" "$MODULE/data/manifest.json"
    "$list")
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$MODULE/data" -maxdepth 1 -type f -name '*.mem' -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_serial_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M09_SERIAL_METRIC_JSON:|PASS: M09|FAIL: M09' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M09 Gate/Up serial physical wrapper' \
        "$report/console.log" && ! grep -Fq 'FAIL: M09' "$report/console.log"; then
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
