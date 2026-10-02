#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/11_mlp_product_hadamard_a8"
RESULT="$ROOT/ModularExperiment/result/11_mlp_product_hadamard_a8"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-0}"
dataset="${3:-synthetic}"
[[ "$backpressure" == 0 || "$backpressure" == 1 ]] || exit 2
[[ "$dataset" == synthetic || "$dataset" == trace ]] || {
    printf 'dataset must be synthetic or trace\n' >&2
    exit 2
}

if [[ "$dataset" == trace ]]; then
    data_dir="$MODULE/data_trace"
    python3 "$MODULE/model/verify_trace_vectors.py"
else
    data_dir="$MODULE/data"
    python3 "$MODULE/model/generate_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
mode=continuous
[[ "$backpressure" == 1 ]] && mode=periodic_backpressure
report="$RESULT/raw/$variant/xsim/${stamp}_mlp_product_frontend_native_scale_${dataset}_${mode}"
build="${TMPDIR:-/tmp}/scalellm_modular_m11_xsim/${stamp}_${variant}_${dataset}_${mode}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
export HAP_DATA_DIR="$data_dir"
printf 'RUNNING\n' > "$report/STATUS"

sources=("$MODULE/tb/m11_mlp_product_frontend_tb.sv"
    "$MODULE/vivado/run_matched_xsim.tcl")
if [[ "$dataset" == trace ]]; then
    sources+=("$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/generate_vectors.py"
        "$ROOT/model/mlp_fixed.py"
        "$data_dir/manifest.json"
        "$ROOT/ModularExperiment/result/trace/raw/20260909_221332_llama31_8b_replayable_trace/trace/manifest.json")
else
    sources+=("$MODULE/model/generate_vectors.py" "$data_dir/manifest.json")
fi
list="$MODULE/vivado/fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/sc.sources"
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$data_dir" -maxdepth 1 -type f -name '*.mem' -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_matched_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M11_METRIC_JSON:|PASS: M11|FAIL: M11|M11_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M11 MLP product frontend native-scale boundary' \
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
