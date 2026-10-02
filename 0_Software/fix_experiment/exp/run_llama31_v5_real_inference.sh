#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
MODEL_PATH=${MODEL_PATH:-$WORKSPACE_ROOT/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct}
CASE_NAME=
PPL_SOURCE=
OUTPUT_ROOT=
BATCH_SIZE=8
ALLOW_FORMAT_ERRORS=0

usage() {
  printf '%s\n' \
    "usage: $0 --case v5_attention|v5_mlp|v5 --ppl-source DIR --output DIR [--batch-size N] [--allow-format-errors]"
}

while (($#)); do
  case "$1" in
    --case) CASE_NAME=$2; shift 2 ;;
    --ppl-source) PPL_SOURCE=$2; shift 2 ;;
    --output) OUTPUT_ROOT=$2; shift 2 ;;
    --batch-size) BATCH_SIZE=$2; shift 2 ;;
    --allow-format-errors) ALLOW_FORMAT_ERRORS=1; shift ;;
    --model) MODEL_PATH=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$CASE_NAME" != v5_attention && "$CASE_NAME" != v5_mlp && "$CASE_NAME" != v5 ]]; then
  printf 'invalid or missing --case\n' >&2
  exit 2
fi
if [[ -z "$PPL_SOURCE" || ! -f "$PPL_SOURCE/manifest.json" ]]; then
  printf 'completed --ppl-source manifest is required: %s\n' "$PPL_SOURCE" >&2
  exit 2
fi
if [[ -z "$OUTPUT_ROOT" ]]; then
  printf -- '--output is required\n' >&2
  exit 2
fi

mkdir -p "$OUTPUT_ROOT/shard_gpu0" "$OUTPUT_ROOT/shard_gpu1"
common=(
  --case "$CASE_NAME"
  --protocol hardware_128
  --model "$MODEL_PATH"
  --device cuda:0
  --batch-size "$BATCH_SIZE"
  --ppl-batch-size 1
)
if ((ALLOW_FORMAT_ERRORS)); then
  common+=(--allow-format-errors)
fi

CUDA_VISIBLE_DEVICES=0 "$PYTHON_BIN" "$SCRIPT_DIR/run_eval_worker.py" \
  "${common[@]}" --tasks hellaswag --output "$OUTPUT_ROOT/shard_gpu0" \
  > "$OUTPUT_ROOT/gpu0.log" 2>&1 &
pid0=$!
CUDA_VISIBLE_DEVICES=1 "$PYTHON_BIN" "$SCRIPT_DIR/run_eval_worker.py" \
  "${common[@]}" --tasks piqa,arc_easy,arc_challenge,boolq,winogrande \
  --output "$OUTPUT_ROOT/shard_gpu1" \
  > "$OUTPUT_ROOT/gpu1.log" 2>&1 &
pid1=$!
printf 'started %s ACC: GPU0=%s GPU1=%s\n' "$CASE_NAME" "$pid0" "$pid1"

failed=0
wait "$pid0" || failed=1
wait "$pid1" || failed=1
if ((failed)); then
  printf '%s ACC failed; inspect %s/gpu*.log\n' "$CASE_NAME" "$OUTPUT_ROOT" >&2
  exit 1
fi

merge_args=()
if ((ALLOW_FORMAT_ERRORS)); then
  merge_args+=(--allow-compatible-v5-format-policy)
fi
"$PYTHON_BIN" "$SCRIPT_DIR/merge_eval_shards.py" \
  --source "$OUTPUT_ROOT/shard_gpu0" \
  --source "$OUTPUT_ROOT/shard_gpu1" \
  --source "$PPL_SOURCE" \
  "${merge_args[@]}" \
  --output "$OUTPUT_ROOT/merged"
