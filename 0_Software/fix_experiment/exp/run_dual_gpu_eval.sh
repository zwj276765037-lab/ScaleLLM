#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
MODEL_PATH=${MODEL_PATH:-$WORKSPACE_ROOT/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct}
MODEL_IDENTITY=${MODEL_IDENTITY:-}
OUTPUT_ROOT=${OUTPUT_ROOT:-$SCRIPT_DIR/../results}
PLAN=paper
LIMIT=0
BATCH_SIZE=8
PPL_BATCH_SIZE=1
ALLOW_FORMAT_ERRORS=0
OFFLINE_DATA=0
CHILD_PIDS=()

stop_children() {
  if ((${#CHILD_PIDS[@]})); then
    kill "${CHILD_PIDS[@]}" 2>/dev/null || true
  fi
}
trap stop_children INT TERM

usage() {
  printf '%s\n' \
    "usage: $0 [--plan paper|literature|hardware|fixedpoint|algorithm|algorithm-only|v5-algorithm|v5-algorithm-only] [--model PATH] [--model-identity PATH] [--output PATH]" \
    "          [--limit N] [--batch-size N] [--ppl-batch-size N]" \
    "          [--allow-format-errors] [--offline-data]"
}

while (($#)); do
  case "$1" in
    --plan) PLAN=$2; shift 2 ;;
    --model) MODEL_PATH=$2; shift 2 ;;
    --model-identity) MODEL_IDENTITY=$2; shift 2 ;;
    --output) OUTPUT_ROOT=$2; shift 2 ;;
    --limit) LIMIT=$2; shift 2 ;;
    --batch-size) BATCH_SIZE=$2; shift 2 ;;
    --ppl-batch-size) PPL_BATCH_SIZE=$2; shift 2 ;;
    --allow-format-errors) ALLOW_FORMAT_ERRORS=1; shift ;;
    --offline-data) OFFLINE_DATA=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$PLAN" != paper && "$PLAN" != literature && "$PLAN" != hardware && "$PLAN" != fixedpoint && "$PLAN" != algorithm && "$PLAN" != algorithm-only && "$PLAN" != v5-algorithm && "$PLAN" != v5-algorithm-only ]]; then
  printf 'invalid plan: %s\n' "$PLAN" >&2
  exit 2
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'python is not executable: %s\n' "$PYTHON_BIN" >&2
  exit 2
fi
if [[ ! -d "$MODEL_PATH" ]]; then
  printf 'model directory does not exist: %s\n' "$MODEL_PATH" >&2
  exit 2
fi
if [[ -n "$MODEL_IDENTITY" && ! -f "$MODEL_IDENTITY" ]]; then
  printf 'model identity does not exist: %s\n' "$MODEL_IDENTITY" >&2
  exit 2
fi
if [[ $(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l) -lt 2 ]]; then
  printf 'two CUDA GPUs are required\n' >&2
  exit 2
fi

mkdir -p "$OUTPUT_ROOT"
prepare_args=()
if ((OFFLINE_DATA)); then
  prepare_args+=(--offline)
fi
"$PYTHON_BIN" "$SCRIPT_DIR/prepare_standard_data.py" "${prepare_args[@]}" \
  > "$OUTPUT_ROOT/data_manifest.json"

run_phase() {
  local case_name=$1
  local protocol=$2
  local phase_dir=$OUTPUT_ROOT/${case_name}_${protocol}
  local common=(
    --case "$case_name"
    --protocol "$protocol"
    --model "$MODEL_PATH"
    --device cuda:0
    --batch-size "$BATCH_SIZE"
    --ppl-batch-size "$PPL_BATCH_SIZE"
    --limit "$LIMIT"
  )
  local format_args=()
  local identity_args=()
  if [[ -n "$MODEL_IDENTITY" ]]; then
    identity_args+=(--model-identity "$MODEL_IDENTITY")
  fi
  if ((ALLOW_FORMAT_ERRORS)) && [[ "$case_name" == v5 ]]; then
    format_args+=(--allow-format-errors)
  fi
  mkdir -p "$phase_dir/shard_gpu0" "$phase_dir/shard_gpu1"

  CUDA_VISIBLE_DEVICES=0 "$PYTHON_BIN" "$SCRIPT_DIR/run_eval_worker.py" \
    "${common[@]}" "${identity_args[@]}" "${format_args[@]}" \
    --tasks hellaswag \
    --output "$phase_dir/shard_gpu0" \
    > "$phase_dir/gpu0.log" 2>&1 &
  local pid0=$!
  CUDA_VISIBLE_DEVICES=1 "$PYTHON_BIN" "$SCRIPT_DIR/run_eval_worker.py" \
    "${common[@]}" "${identity_args[@]}" "${format_args[@]}" \
    --tasks wikitext2,piqa,arc_easy,arc_challenge,boolq,winogrande \
    --output "$phase_dir/shard_gpu1" \
    > "$phase_dir/gpu1.log" 2>&1 &
  local pid1=$!
  CHILD_PIDS=("$pid0" "$pid1")

  printf 'started %s/%s: GPU0 pid=%s, GPU1 pid=%s\n' \
    "$case_name" "$protocol" "$pid0" "$pid1"
  local failed=0
  wait "$pid0" || failed=1
  wait "$pid1" || failed=1
  CHILD_PIDS=()
  if ((failed)); then
    printf 'phase %s/%s failed; inspect %s/gpu*.log\n' \
      "$case_name" "$protocol" "$phase_dir" >&2
    return 1
  fi
  "$PYTHON_BIN" "$SCRIPT_DIR/merge_eval_shards.py" \
    --source "$phase_dir/shard_gpu0" \
    --source "$phase_dir/shard_gpu1" \
    --output "$phase_dir/merged"
}

summarize_completed_phases() {
  "$PYTHON_BIN" "$SCRIPT_DIR/summarize_plan.py" --root "$OUTPUT_ROOT"
}

if [[ "$PLAN" == paper || "$PLAN" == literature ]]; then
  if ! run_phase bf16 literature_2048; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == paper ]]; then
  if ! run_phase reference_qdq literature_2048; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == paper || "$PLAN" == hardware ]]; then
  if ! run_phase bf16 hardware_128; then
    summarize_completed_phases || true
    exit 1
  fi
  if ! run_phase v5 hardware_128; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == fixedpoint ]]; then
  for case_name in bf16 reference_qdq v5_attention v5_mlp v5; do
    if ! run_phase "$case_name" hardware_128; then
      summarize_completed_phases || true
      exit 1
    fi
  done
fi
if [[ "$PLAN" == algorithm ]]; then
  if ! run_phase bf16 literature_2048; then
    summarize_completed_phases || true
    exit 1
  fi
  if ! run_phase reference_qdq literature_2048; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == algorithm-only ]]; then
  if ! run_phase reference_qdq literature_2048; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == v5-algorithm ]]; then
  if ! run_phase bf16 hardware_128; then
    summarize_completed_phases || true
    exit 1
  fi
  if ! run_phase v5_algorithm hardware_128; then
    summarize_completed_phases || true
    exit 1
  fi
fi
if [[ "$PLAN" == v5-algorithm-only ]]; then
  if ! run_phase v5_algorithm hardware_128; then
    summarize_completed_phases || true
    exit 1
  fi
fi

summarize_completed_phases
