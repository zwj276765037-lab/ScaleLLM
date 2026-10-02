#!/usr/bin/env bash

set -euo pipefail

MODE=${1:-fast}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FPTOQ_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
WORKSPACE_ROOT=$(cd "$FPTOQ_ROOT/../../.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
MODEL_PATH=${MODEL_PATH:-$WORKSPACE_ROOT/fpga_llm_project/configs/models/Qwen2.5-0.5B-Instruct}
MODEL_TAG=${MODEL_TAG:-qwen2.5-0.5b}
CALIBRATION_PATH=${CALIBRATION_PATH:-$WORKSPACE_ROOT/fpga_llm_project/data/calibration/first64.jsonl}
WIKITEXT_PATH=${WIKITEXT_PATH:-$WORKSPACE_ROOT/fpga_llm_project/data/wikitext-2-raw-v1/test-00000-of-00001.jsonl}
DEVICE=${DEVICE:-cuda:0}
PPL_BLOCK_SIZE=${PPL_BLOCK_SIZE:-1024}
PPL_STRIDE=${PPL_STRIDE:-1024}
PPL_MAX_TOKENS=${PPL_MAX_TOKENS:-65536}
RESULT_ROOT=$FPTOQ_ROOT/results
TRACE=$RESULT_ROOT/$MODEL_TAG/activation_groups.npz

run_fast() {
  PYTHONPATH=$SCRIPT_DIR "$PYTHON_BIN" "$SCRIPT_DIR/test_fptoq_core.py"
  "$PYTHON_BIN" "$SCRIPT_DIR/run_experiment.py" \
    --output-dir "$RESULT_ROOT/synthetic" \
    --count-per-case 4096 \
    --seed 20260911
}

run_capture() {
  "$PYTHON_BIN" "$SCRIPT_DIR/capture_model_activations.py" \
    --model "$MODEL_PATH" \
    --calibration-jsonl "$CALIBRATION_PATH" \
    --output "$TRACE" \
    --max-prompts 8 \
    --max-length 256 \
    --groups-per-call 128 \
    --max-groups-per-op 8192 \
    --device "$DEVICE" \
    --dtype bfloat16 \
    --seed 20260911
  "$PYTHON_BIN" "$SCRIPT_DIR/run_experiment.py" \
    --input "$TRACE" \
    --output-dir "$RESULT_ROOT/$MODEL_TAG/analysis" \
    --seed 20260911
}

run_ppl() {
  local case_name
  for case_name in software pre_q_only rtl_exact; do
    PYTHONPATH=$SCRIPT_DIR "$PYTHON_BIN" "$SCRIPT_DIR/run_model_ppl.py" \
      --case "$case_name" \
      --model "$MODEL_PATH" \
      --wikitext "$WIKITEXT_PATH" \
      --output "$RESULT_ROOT/$MODEL_TAG/ppl_full/$case_name.json" \
      --device "$DEVICE" \
      --dtype bfloat16 \
      --block-size "$PPL_BLOCK_SIZE" \
      --stride "$PPL_STRIDE" \
      --max-tokens "$PPL_MAX_TOKENS" \
      --seed 20260911
  done
  "$PYTHON_BIN" "$SCRIPT_DIR/summarize_ppl.py" \
    --input-dir "$RESULT_ROOT/$MODEL_TAG/ppl_full" \
    --output-dir "$RESULT_ROOT/$MODEL_TAG/ppl_full"
}

case "$MODE" in
  fast)
    run_fast
    ;;
  capture)
    run_capture
    ;;
  ppl)
    run_ppl
    ;;
  all)
    run_fast
    run_capture
    run_ppl
    ;;
  *)
    echo "usage: bash experiment/run_reproduction.sh <fast|capture|ppl|all>" >&2
    exit 2
    ;;
esac
