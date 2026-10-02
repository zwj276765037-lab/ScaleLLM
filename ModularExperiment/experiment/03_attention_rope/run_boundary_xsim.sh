#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 && ( "$1" == sc || "$1" == fp16 || "$1" == fp32 ) ]] || {
    printf 'usage: %s sc|fp16|fp32 [0|1|2 backpressure] [synthetic|trace]\n' "$0" >&2
    exit 2
}
ROOT=/home/user/EDA-202/zhuowenjun/ScaleLLM
MODULE="$ROOT/ModularExperiment/experiment/03_attention_rope"
RESULT="$ROOT/ModularExperiment/result/03_attention_rope"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
variant="$1"
backpressure="${2:-1}"
dataset="${3:-synthetic}"
[[ "$backpressure" == 0 || "$backpressure" == 1 || "$backpressure" == 2 ]] || exit 2
[[ "$dataset" == synthetic || "$dataset" == trace ]] || {
    printf 'dataset must be synthetic or trace\n' >&2
    exit 2
}

if [[ "$dataset" == trace ]]; then
    data_dir="$MODULE/data_trace"
    python3 "$MODULE/model/verify_trace_vectors.py" --integrity-only
else
    data_dir="$MODULE/data_boundary"
    python3 "$MODULE/model/generate_boundary_vectors.py"
    python3 "$MODULE/model/verify_boundary_vectors.py"
fi
stamp="$(date +%Y%m%d_%H%M%S)"
report="$RESULT/raw/$variant/xsim/${stamp}_projection_tail_rope_boundary_${dataset}_bp${backpressure}"
build="${TMPDIR:-/tmp}/scalellm_modular_m03_boundary/${stamp}_${variant}_${dataset}_bp${backpressure}"
mkdir -p "$report" "$build"
export HAP_SCALE_VARIANT="$variant" HAP_BACKPRESSURE="$backpressure"
export HAP_REPORT_DIR="$report" HAP_BUILD_DIR="$build" HAP_DATA_DIR="$data_dir"
printf 'RUNNING\n' > "$report/STATUS"

list="$MODULE/vivado/boundary_fp.sources"
[[ "$variant" == sc ]] && list="$MODULE/vivado/boundary_sc.sources"
sources=("$MODULE/README.md"
    "$MODULE/tb/m03_projection_rope_boundary_tb.sv"
    "$MODULE/vivado/run_boundary_xsim.tcl" "$list")
if [[ "$dataset" == trace ]]; then
    trace_run="$ROOT/ModularExperiment/result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
    capture_dir="$MODULE/data_trace_projection_input"
    model_dir="$ROOT/../fpga_llm_project/configs/models/Llama-3.1-8B-Instruct"
    sources+=("$MODULE/model/generate_trace_vectors.py"
        "$MODULE/model/verify_trace_vectors.py"
        "$MODULE/model/capture_trace_projection_inputs.py"
        "$MODULE/model/verify_trace_projection_inputs.py"
        "$MODULE/model/generate_boundary_vectors.py"
        "$ROOT/model/export_scalellm_llama31_artifacts.py"
        "$ROOT/model/fixbit_v2.py"
        "$data_dir/manifest.json"
        "$capture_dir/manifest.json" "$capture_dir/MANIFEST_SHA256"
        "$trace_run/STATUS" "$trace_run/exit_status.txt"
        "$trace_run/trace/manifest.json" "$trace_run/trace/MANIFEST_SHA256"
        "$model_dir/config.json" "$model_dir/model.safetensors.index.json"
        "$model_dir/model-00001-of-00004.safetensors"
        "$model_dir/model-00002-of-00004.safetensors"
        "$model_dir/model-00003-of-00004.safetensors")
    while IFS= read -r -d '' capture_file; do
        sources+=("$capture_file")
    done < <(find "$capture_dir" -maxdepth 1 -type f -name '*.npy' -print0 | sort -z)
else
    sources+=("$MODULE/model/generate_boundary_vectors.py"
        "$MODULE/model/verify_boundary_vectors.py"
        "$data_dir/manifest.json")
fi
while IFS= read -r source; do
    [[ -n "$source" && "$source" != \#* ]] && sources+=("$source")
done < "$list"
[[ "$variant" == sc ]] || sources+=("$MODULE/vivado/create_boundary_fp_ip.tcl")
while IFS= read -r -d '' data_file; do
    sources+=("$data_file")
done < <(find "$data_dir" -maxdepth 1 -type f ! -name manifest.json -print0 | sort -z)
sha256sum "${sources[@]}" > "$report/INPUT_SHA256SUMS"

set +e
"$VIVADO" -mode batch -notrace -source "$MODULE/vivado/run_boundary_xsim.tcl" \
    -journal "$report/vivado.jou" -log "$report/vivado.log" \
    > "$report/console.log" 2>&1
rc=$?
set -e
grep -E 'M03_BOUNDARY_METRIC_JSON:|PASS: M03|FAIL: M03|M03_BOUNDARY_MISMATCH' \
    "$report/console.log" > "$report/summary.txt" || true
if [[ "$rc" -eq 0 ]] && \
        grep -Fq 'PASS: M03 projection-tail RoPE boundary' "$report/console.log" && \
        ! grep -Fq 'FAIL: M03' "$report/console.log"; then
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
