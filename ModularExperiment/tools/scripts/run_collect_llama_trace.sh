#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment"
MODEL="/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct"
TEXT_JSONL="/home/user/EDA-202/zhuowenjun/fpga_llm_project/data/wikitext-2-raw-v1/test-00000-of-00001.jsonl"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
DEVICE="${TRACE_DEVICE:-cuda:1}"
LAYERS="${TRACE_LAYERS:-0,15,31}"
MAX_SAMPLES="${TRACE_MAX_SAMPLES:-2}"
MAX_LENGTH="${TRACE_MAX_LENGTH:-128}"

cd "$ROOT"
stamp="$(date +%Y%m%d_%H%M%S)"
run_dir="$ROOT/result/trace/raw/${stamp}_llama31_8b_replayable_trace"
trace_dir="$run_dir/trace"
mkdir -p "$run_dir"
printf 'RUNNING\n' > "$run_dir/STATUS"

sha256sum \
    "$ROOT/tools/scripts/collect_llama_trace.py" \
    "$ROOT/tools/scripts/verify_llama_trace.py" \
    "$MODEL/config.json" \
    "$MODEL/model.safetensors.index.json" \
    "$MODEL/tokenizer.json" \
    "$TEXT_JSONL" > "$run_dir/INPUT_SHA256SUMS"

{
    printf 'root=%s\n' "$ROOT"
    printf 'model=%s\n' "$MODEL"
    printf 'text_jsonl=%s\n' "$TEXT_JSONL"
    printf 'python=%s\n' "$PYTHON"
    printf 'device=%s\n' "$DEVICE"
    printf 'layers=%s\n' "$LAYERS"
    printf 'max_samples=%s\n' "$MAX_SAMPLES"
    printf 'max_length=%s\n' "$MAX_LENGTH"
} > "$run_dir/config.txt"

set +e
"$PYTHON" "$ROOT/tools/scripts/collect_llama_trace.py" \
    --model-path "$MODEL" \
    --text-jsonl "$TEXT_JSONL" \
    --output-dir "$trace_dir" \
    --device "$DEVICE" \
    --layers "$LAYERS" \
    --max-samples "$MAX_SAMPLES" \
    --max-length "$MAX_LENGTH" \
    > "$run_dir/console.log" 2>&1
rc=$?
if [[ $rc -eq 0 ]]; then
    "$PYTHON" "$ROOT/tools/scripts/verify_llama_trace.py" "$trace_dir" \
        >> "$run_dir/console.log" 2>&1
    rc=$?
fi
set -e

printf '%d\n' "$rc" > "$run_dir/exit_status.txt"
if [[ $rc -eq 0 ]]; then
    printf 'PASS\n' > "$run_dir/STATUS"
else
    printf 'FAIL\n' > "$run_dir/STATUS"
fi

(
    cd "$run_dir"
    find . -type f ! -name SHA256SUMS -print0 | sort -z |
        xargs -0 sha256sum > SHA256SUMS
)

printf 'TRACE_RUN_DIR=%s\n' "$run_dir"
printf 'TRACE_STATUS=%s\n' "$(cat "$run_dir/STATUS")"
exit "$rc"
