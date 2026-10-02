#!/usr/bin/env bash

set -euo pipefail

if (($# != 4)); then
  printf 'usage: %s RESULT_ROOT ATTENTION_DRIVER_PID ATTENTION_GPU0_PID ATTENTION_GPU1_PID\n' "$0" >&2
  exit 2
fi

RESULT_ROOT=$1
ATTENTION_DRIVER_PID=$2
ATTENTION_GPU0_PID=$3
ATTENTION_GPU1_PID=$4
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
WORKBOOK_PYTHON_BIN=${WORKBOOK_PYTHON_BIN:-/home/user/anaconda3/bin/python}
MODEL_PATH=${MODEL_PATH:-/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct}
WORKER="$SCRIPT_DIR/run_eval_worker.py"
MERGER="$SCRIPT_DIR/merge_eval_shards.py"
SUMMARIZE="$SCRIPT_DIR/summarize_fixedpoint_validation.py"
AUDIT_CONTRACT="$SCRIPT_DIR/audit_format_v3_contract.py"
BUILD_WORKBOOK="$SCRIPT_DIR/build_fixedpoint_validation_workbook.py"
BASELINE_MANIFEST=/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/algorithm_precision_full/bf16_hardware_128/merged/manifest.json
ACC_ROOT="$RESULT_ROOT/full_acc_rtl_zero_guard_v3"
ATTENTION_ROOT="$ACC_ROOT/v5_attention"
MLP_ROOT="$ACC_ROOT/v5_mlp"
FULL_ROOT="$ACC_ROOT/v5"

mkdir -p "$MLP_ROOT" "$FULL_ROOT"

wait_for_manifest() {
  local directory=$1
  local watched_pid=${2:-}
  while [[ ! -f "$directory/manifest.json" ]]; do
    if [[ -f "$directory/failure.json" ]]; then
      printf 'failed result detected: %s/failure.json\n' "$directory" >&2
      return 1
    fi
    if [[ -n "$watched_pid" ]] && ! kill -0 "$watched_pid" 2>/dev/null; then
      printf 'process %s exited before creating %s/manifest.json\n' \
        "$watched_pid" "$directory" >&2
      return 1
    fi
    sleep 30
  done
}

run_worker() {
  local physical_gpu=$1
  local case_name=$2
  local tasks=$3
  local output=$4
  local allow_format_errors=$5
  local -a args=(
    --case "$case_name"
    --protocol hardware_128
    --model "$MODEL_PATH"
    --device cuda:0
    --batch-size 32
    --ppl-batch-size 1
    --tasks "$tasks"
    --output "$output"
  )
  if ((allow_format_errors)); then
    args+=(--allow-format-errors)
  fi
  mkdir -p "$output"
  printf 'start gpu=%s case=%s tasks=%s output=%s\n' \
    "$physical_gpu" "$case_name" "$tasks" "$output"
  CUDA_VISIBLE_DEVICES="$physical_gpu" "$PYTHON_BIN" "$WORKER" \
    "${args[@]}" > "$output/worker.log" 2>&1
  printf 'complete gpu=%s case=%s tasks=%s output=%s\n' \
    "$physical_gpu" "$case_name" "$tasks" "$output"
}

# The currently running Attention driver owns both GPUs until each existing
# worker exits.  Once a physical GPU is free, schedule the largest remaining
# independent shard on it.  This keeps one 8B model per GPU and avoids the
# deterministic-state corruption observed with two models on one device.
lane_gpu0() {
  wait_for_manifest "$ATTENTION_ROOT/shard_gpu0" "$ATTENTION_GPU0_PID"
  wait_for_manifest "$ATTENTION_ROOT/merged" "$ATTENTION_DRIVER_PID"
  run_worker 0 v5_mlp hellaswag "$MLP_ROOT/shard_hellaswag_gpu0" 0
  run_worker 0 v5 \
    piqa,arc_easy,arc_challenge,boolq,winogrande \
    "$FULL_ROOT/shard_other_gpu0" 1
}

lane_gpu1() {
  wait_for_manifest "$ATTENTION_ROOT/shard_gpu1" "$ATTENTION_GPU1_PID"
  run_worker 1 v5 hellaswag "$FULL_ROOT/shard_hellaswag_gpu1" 1
  run_worker 1 v5_mlp \
    piqa,arc_easy,arc_challenge,boolq,winogrande \
    "$MLP_ROOT/shard_other_gpu1" 0
}

lane_gpu0 &
lane0_pid=$!
lane_gpu1 &
lane1_pid=$!
failed=0
wait "$lane0_pid" || failed=1
wait "$lane1_pid" || failed=1
if ((failed)); then
  printf 'balanced V5 ACC lane failed; inspect worker logs under %s\n' "$ACC_ROOT" >&2
  exit 1
fi

"$PYTHON_BIN" "$MERGER" \
  --source "$MLP_ROOT/shard_hellaswag_gpu0" \
  --source "$MLP_ROOT/shard_other_gpu1" \
  --source "$RESULT_ROOT/full_ppl/v5_mlp_retry_gpu0" \
  --output "$MLP_ROOT/merged"

"$PYTHON_BIN" "$MERGER" \
  --source "$FULL_ROOT/shard_hellaswag_gpu1" \
  --source "$FULL_ROOT/shard_other_gpu0" \
  --source "$RESULT_ROOT/full_ppl/v5" \
  --allow-compatible-v5-format-policy \
  --output "$FULL_ROOT/merged"

"$PYTHON_BIN" "$SUMMARIZE" \
  --root "$RESULT_ROOT" \
  --baseline-manifest "$BASELINE_MANIFEST"

"$PYTHON_BIN" "$AUDIT_CONTRACT" --output-root "$RESULT_ROOT"

"$WORKBOOK_PYTHON_BIN" "$BUILD_WORKBOOK" --root "$RESULT_ROOT"

printf 'balanced V5 ACC queue complete: %s\n' "$RESULT_ROOT"
