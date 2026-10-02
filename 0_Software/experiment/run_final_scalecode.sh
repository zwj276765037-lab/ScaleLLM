#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: bash experiment/run_final_scalecode.sh <acc|ppl|gsm8k> <model_path> [model_name] [prompt_style] [attn_implementation]" >&2
  exit 2
fi

MODE=$1
MODEL_PATH=$2
MODEL_NAME=${3:-$(basename "$MODEL_PATH")}
PROMPT_STYLE=${4:-fair}
ATTN_IMPLEMENTATION=${5:-eager}

EXPERIMENT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ARCHIVE_ROOT=$(cd "$EXPERIMENT_DIR/.." && pwd)
WORKSPACE_ROOT=$(cd "$ARCHIVE_ROOT/../.." && pwd)
export FPGA_LLM_PROJECT_ROOT=${FPGA_LLM_PROJECT_ROOT:-$WORKSPACE_ROOT/fpga_llm_project}

MLP4_DIR=$EXPERIMENT_DIR/scripts/accuracy_MLP_4bit
COMMON_ARGS=(
  --model_path "$MODEL_PATH"
  --device cuda:0
  --dtype bfloat16
  --attn_implementation "$ATTN_IMPLEMENTATION"
  --hadamard_block 32
  --group_size 32
  --act_bits 8
  --attention_weight_bits 8
  --mlp_weight_bits 4
  --scale_code_bits 8
  --scale_format scale_code
  --deterministic
  --no-allow_tf32
)

case "$MODE" in
  acc)
    python3 "$MLP4_DIR/scala_code_accuracy/run_gyrot_aligned_quality_accuracy.py" \
      "${COMMON_ARGS[@]}" \
      --model_name "${MODEL_NAME}__mlp_w4_scalecode" \
      --method mlp_quant \
      --case_name mlp_w4_scalecode \
      --method_label "A8W4 ScaleCode" \
      --tasks piqa,arc_challenge,openbookqa,hellaswag,winogrande \
      --max_mcqa_samples 0 \
      --rank_metric auto \
      --max_length 1024 \
      --seed 20260626 \
      --no-allow_dataset_download \
      --no-materialize_missing_data
    ;;
  ppl)
    python3 "$MLP4_DIR/run_mlp4_quality_accuracy.py" \
      "${COMMON_ARGS[@]}" \
      --model_name "${MODEL_NAME}__iah_scale_code_mlp_w4" \
      --tasks wikitext2 \
      --wikitext_block_size 1024 \
      --wikitext_stride 1024 \
      --wikitext_max_tokens 65536 \
      --seed 20260618
    ;;
  gsm8k)
    python3 "$MLP4_DIR/run_mlp4_gsm8k_accuracy.py" \
      "${COMMON_ARGS[@]}" \
      --model_name "${MODEL_NAME}__iah_scale_code_mlp_w4" \
      --max_samples 300 \
      --max_input_tokens 1536 \
      --max_new_tokens 512 \
      --generation_batch_size 1 \
      --temperature 0 \
      --prompt_style "$PROMPT_STYLE" \
      --seed 20260626
    ;;
  *)
    echo "Unknown mode: $MODE (expected acc, ppl, or gsm8k)" >&2
    exit 2
    ;;
esac
