#!/usr/bin/env bash

set -euo pipefail

if (($# != 2)); then
  printf 'usage: %s RESULT_ROOT BALANCED_QUEUE_PID\n' "$0" >&2
  exit 2
fi

RESULT_ROOT=$1
QUEUE_PID=$2
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-/home/user/anaconda3/envs/zhouwenjun/bin/python}
WORKBOOK_PYTHON_BIN=${WORKBOOK_PYTHON_BIN:-/home/user/anaconda3/bin/python}
VERIFY="$SCRIPT_DIR/verify_fixedpoint_validation.py"
BASELINE_MANIFEST=/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/algorithm_precision_full/bf16_hardware_128/merged/manifest.json
ACC_ROOT="$RESULT_ROOT/full_acc_rtl_zero_guard_v3"

for case_name in v5_attention v5_mlp v5; do
  target="$ACC_ROOT/$case_name/merged"
  while [[ ! -f "$target/manifest.json" ]]; do
    if [[ -f "$target/failure.json" ]]; then
      printf 'finalization stopped: %s/failure.json exists\n' "$target" >&2
      exit 1
    fi
    if ! kill -0 "$QUEUE_PID" 2>/dev/null; then
      printf 'finalization stopped: queue %s exited before %s/manifest.json\n' \
        "$QUEUE_PID" "$target" >&2
      exit 1
    fi
    sleep 30
  done
done

"$PYTHON_BIN" "$SCRIPT_DIR/run_fixedpoint_regressions.py" \
  --output-root "$RESULT_ROOT" \
  --include-gpu
"$PYTHON_BIN" "$SCRIPT_DIR/audit_format_v3_contract.py" \
  --output-root "$RESULT_ROOT"
"$PYTHON_BIN" "$SCRIPT_DIR/summarize_fixedpoint_validation.py" \
  --root "$RESULT_ROOT" \
  --baseline-manifest "$BASELINE_MANIFEST"
"$WORKBOOK_PYTHON_BIN" "$SCRIPT_DIR/build_fixedpoint_validation_workbook.py" \
  --root "$RESULT_ROOT"
"$WORKBOOK_PYTHON_BIN" "$VERIFY" \
  --root "$RESULT_ROOT" \
  --baseline-manifest "$BASELINE_MANIFEST" \
  --require-complete

printf 'fixed-point validation finalization complete: %s\n' "$RESULT_ROOT"
