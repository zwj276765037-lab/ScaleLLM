#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/10_mlp_silu_multiply"
RESULT="$ROOT/ModularExperiment/result/10_mlp_silu_multiply"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
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
    data_dir="$MODULE/data_boundary"
    python3 "$MODULE/model/verify_boundary_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_gate_up_to_silu_boundary_x2_${dataset}_bp${backpressure}"
build="${TMPDIR:-/tmp}/scalellm_modular_m10_boundary/${stamp}_${variant}_${dataset}_bp${backpressure}"
mkdir -p "$report" "$build"
export HAP_FP_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build"
export HAP_DATA_DIR="$data_dir"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/boundary_fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/boundary_sc.sources"
sources=("$MODULE/tb/m10_silu_boundary_tb.sv"
    "$MODULE/vivado/run_boundary_xsim.tcl" "$list")
if [[ "$dataset" == trace ]]; then
    sources+=("$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/generate_boundary_vectors.py"
        "$ROOT/model/mlp_fixed.py"
        "$data_dir/manifest.json"
        "$ROOT/ModularExperiment/result/trace/raw/20260909_221332_llama31_8b_replayable_trace/trace/manifest.json")
else
    sources+=("$MODULE/model/generate_boundary_vectors.py"
        "$MODULE/model/verify_boundary_vectors.py"
        "$data_dir/manifest.json")
fi
while IFS= read -r source; do
    [[ -n "$source" ]] && sources+=("$source")
done < "$list"
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$data_dir" -maxdepth 1 -type f -name '*.mem' -print0 | sort -z)
if [[ "$variant" != sc ]]; then
    sources+=("$MODULE/vivado/create_fp_ip.tcl"
        "$MODULE/vivado/create_boundary_fp_ip.tcl"
        "$MODULE/vivado/create_boundary_all_fp_ip.tcl")
fi
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace \
    -source "$MODULE/vivado/run_boundary_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M10_BOUNDARY_METRIC_JSON:|PASS: M10|FAIL: M10|MISMATCH: M10' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M10 Gate/Up to SiLU boundary' "$report/console.log" && \
        ! grep -Fq 'FAIL: M10' "$report/console.log"; then
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
