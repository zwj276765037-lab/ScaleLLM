#!/usr/bin/env bash
set -euo pipefail
MLP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$MLP_ROOT/../.." && pwd)"
PYTHON="${PYTHON:-/home/user/anaconda3/envs/zhouwenjun/bin/python}"
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" "$PYTHON" \
    "$MLP_ROOT/model/audit_mlp_activation_scalecode.py" \
    --model_path "$PROJECT_ROOT/configs/models/Llama-3.1-8B-Instruct" \
    --weight_audit_csv "$PROJECT_ROOT/results/All_results/accuracy_MLP_4bit/scala_code_accuracy/summary/mlp4_scale_format_audit_by_layer.csv" \
    --text_jsonl "$PROJECT_ROOT/data/wikitext-2-raw-v1/test-00000-of-00001.jsonl" \
    --output_dir "$MLP_ROOT/data/mlp_activation_scalecode_audit_20260810" \
    --max_samples "${MAX_SAMPLES:-8}" \
    --max_length "${MAX_LENGTH:-128}"
