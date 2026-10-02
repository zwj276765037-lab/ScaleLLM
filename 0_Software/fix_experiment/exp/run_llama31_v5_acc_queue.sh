#!/usr/bin/env bash

set -euo pipefail

if (($# != 2)); then
  printf 'usage: %s RESULT_ROOT ATTENTION_DRIVER_PID\n' "$0" >&2
  exit 2
fi

RESULT_ROOT=$1
ATTENTION_DRIVER_PID=$2
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
RUN_CASE="$SCRIPT_DIR/run_llama31_v5_real_inference.sh"
SUMMARIZE="$SCRIPT_DIR/summarize_fixedpoint_validation.py"
BASELINE_MANIFEST=/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/algorithm_precision_full/bf16_hardware_128/merged/manifest.json

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

ATTENTION_MERGED="$RESULT_ROOT/full_acc_rtl_zero_guard_v3/v5_attention/merged"
MLP_PPL="$RESULT_ROOT/full_ppl/v5_mlp_retry_gpu0"
FULL_PPL="$RESULT_ROOT/full_ppl/v5"

wait_for_manifest "$ATTENTION_MERGED" "$ATTENTION_DRIVER_PID"
wait_for_manifest "$MLP_PPL"
wait_for_manifest "$FULL_PPL"

"$RUN_CASE" \
  --case v5_mlp \
  --ppl-source "$MLP_PPL" \
  --output "$RESULT_ROOT/full_acc_rtl_zero_guard_v3/v5_mlp" \
  --batch-size 32 \
  --allow-format-errors

"$RUN_CASE" \
  --case v5 \
  --ppl-source "$FULL_PPL" \
  --output "$RESULT_ROOT/full_acc_rtl_zero_guard_v3/v5" \
  --batch-size 32 \
  --allow-format-errors

"$PYTHON_BIN" "$SUMMARIZE" \
  --root "$RESULT_ROOT" \
  --baseline-manifest "$BASELINE_MANIFEST"

printf 'V5 ACC queue complete: %s\n' "$RESULT_ROOT"
