#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
MODEL_PATH=${MODEL_PATH:-/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct}
RESULT_ROOT=${RESULT_ROOT:-/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/s32_candidate_validation}
WORKER="$SCRIPT_DIR/run_eval_worker.py"
MERGER="$SCRIPT_DIR/merge_eval_shards.py"

run_worker() {
  local physical_gpu=$1
  local case_name=$2
  local tasks=$3
  local output=$4

  if [[ -f "$output/manifest.json" ]]; then
    printf 'skip completed gpu=%s case=%s tasks=%s output=%s\n' \
      "$physical_gpu" "$case_name" "$tasks" "$output"
    return 0
  fi
  mkdir -p "$output"
  rm -f "$output/failure.json"
  printf 'start gpu=%s case=%s tasks=%s output=%s\n' \
    "$physical_gpu" "$case_name" "$tasks" "$output"
  CUDA_VISIBLE_DEVICES="$physical_gpu" "$PYTHON_BIN" "$WORKER" \
    --case "$case_name" \
    --protocol hardware_128 \
    --model "$MODEL_PATH" \
    --device cuda:0 \
    --batch-size 32 \
    --ppl-batch-size 1 \
    --tasks "$tasks" \
    --output "$output" \
    > "$output/worker.log" 2>&1
  printf 'complete gpu=%s case=%s tasks=%s output=%s\n' \
    "$physical_gpu" "$case_name" "$tasks" "$output"
}

lane_gpu0() {
  run_worker 0 v5_mlp_down_s32_ablation wikitext2 \
    "$RESULT_ROOT/full_ppl/mlp_s32"
  run_worker 0 v5_mlp_down_s32_ablation hellaswag \
    "$RESULT_ROOT/full_acc/mlp_s32/shard_hellaswag"
  run_worker 0 v5_down_s32_ablation \
    piqa,arc_easy,arc_challenge,boolq,winogrande \
    "$RESULT_ROOT/full_acc/full_s32/shard_other"
}

lane_gpu1() {
  run_worker 1 v5_down_s32_ablation wikitext2 \
    "$RESULT_ROOT/full_ppl/full_s32"
  run_worker 1 v5_down_s32_ablation hellaswag \
    "$RESULT_ROOT/full_acc/full_s32/shard_hellaswag"
  run_worker 1 v5_mlp_down_s32_ablation \
    piqa,arc_easy,arc_challenge,boolq,winogrande \
    "$RESULT_ROOT/full_acc/mlp_s32/shard_other"
}

lane_gpu0 &
lane0_pid=$!
lane_gpu1 &
lane1_pid=$!
failed=0
wait "$lane0_pid" || failed=1
wait "$lane1_pid" || failed=1
if ((failed)); then
  printf 'S32 candidate worker failed; inspect logs under %s\n' "$RESULT_ROOT" >&2
  exit 1
fi

"$PYTHON_BIN" "$MERGER" \
  --source "$RESULT_ROOT/full_acc/mlp_s32/shard_hellaswag" \
  --source "$RESULT_ROOT/full_acc/mlp_s32/shard_other" \
  --source "$RESULT_ROOT/full_ppl/mlp_s32" \
  --output "$RESULT_ROOT/full_acc/mlp_s32/merged"

"$PYTHON_BIN" "$MERGER" \
  --source "$RESULT_ROOT/full_acc/full_s32/shard_hellaswag" \
  --source "$RESULT_ROOT/full_acc/full_s32/shard_other" \
  --source "$RESULT_ROOT/full_ppl/full_s32" \
  --output "$RESULT_ROOT/full_acc/full_s32/merged"

printf 'S32 candidate validation complete: %s\n' "$RESULT_ROOT"
