#!/usr/bin/env python3
"""Freeze GSM8K local inputs and audit all formal prompts on CPU only."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

from gsm8k_protocol import (
    DEFAULT_PLAN, STAGES, atomic_json, canonical_hash, load_verified_inputs,
    prepare_requests, resolve_input_path, sha256_file,
)


DEFAULT_MODEL_ROOT = Path("/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models")


def write_jsonl(path, rows):
    # Exclusive creation preserves every prior preparation attempt.
    with Path(path).open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def tokenizer_audit(plan, requests, model_root, output_dir):
    from transformers import AutoTokenizer
    from lm_eval.models.huggingface import HFLM

    model_names = list(dict.fromkeys(row["model"] for row in plan["matrix"]))
    if len(model_names) != 6:
        raise ValueError("tokenizer audit requires the exact six-model matrix")
    budget = int(plan["protocol"]["max_prompt_tokens"])
    model_audits = []
    for name in model_names:
        path = (model_root / name).resolve()
        tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
        # HFLM.tok_encode needs these three attributes and no model instance.
        # This calls the installed method without loading weights or allocating
        # CUDA tensors. None preserves checkpoint-native special-token policy.
        oracle = SimpleNamespace(
            tokenizer=tokenizer, add_bos_token=None,
            prefix_token_id=tokenizer.bos_token_id if tokenizer.bos_token_id is not None else tokenizer.eos_token_id,
        )
        rows = []
        mismatches = []
        oversize = []
        for request in requests:
            ids = tokenizer.encode(request["prompt"], truncation=False)
            expected = HFLM.tok_encode(oracle, request["prompt"])
            if ids != expected:
                mismatches.append(request["sample_id"])
            if len(ids) > budget:
                oversize.append({"sample_id": request["sample_id"], "input_tokens": len(ids)})
            rows.append({
                "sample_id": request["sample_id"], "prompt_sha256": request["prompt_sha256"],
                "input_tokens": len(ids), "input_token_ids_sha256": canonical_hash(ids),
            })
        token_path = output_dir / f"{name}.tokenization.jsonl"
        write_jsonl(token_path, rows)
        files = {}
        for filename in (
            "config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
            "special_tokens_map.json", "added_tokens.json", "tokenizer.model", "vocab.json", "merges.txt",
        ):
            candidate = path / filename
            if candidate.is_file():
                files[filename] = {"bytes": candidate.stat().st_size, "sha256": sha256_file(candidate)}
        lengths = sorted(row["input_tokens"] for row in rows)
        record = {
            "model": name, "model_path": str(path), "tokenizer_class": type(tokenizer).__name__,
            "requests": len(rows), "max_prompt_tokens": budget,
            "min_input_tokens": lengths[0], "max_input_tokens": lengths[-1],
            "mean_input_tokens": sum(lengths) / len(lengths),
            "p95_input_tokens": lengths[min(len(lengths) - 1, int(0.95 * len(lengths)))],
            "over_budget": oversize,
            "harness_tok_encode_mismatches": mismatches,
            "input_truncation": False, "chat_template_applied": False,
            "add_special_tokens": "checkpoint native tokenizer.encode default; harness add_bos_token=None",
            "bos_token_id": tokenizer.bos_token_id, "eos_token_id": tokenizer.eos_token_id,
            "pad_token_id": tokenizer.pad_token_id,
            "tokenizer_model_max_length": tokenizer.model_max_length,
            "tokenizer_add_bos_token": getattr(tokenizer, "add_bos_token", None),
            "tokenizer_files": files,
            "tokenization_file": str(token_path), "tokenization_sha256": sha256_file(token_path),
            "passed": not oversize and not mismatches,
        }
        model_audits.append(record)
        print(json.dumps({key: record[key] for key in ("model", "requests", "max_input_tokens", "passed")}), flush=True)
    return {
        "schema": "scalellm_gsm8k_tokenizer_context_audit_v1",
        "passed": all(row["passed"] for row in model_audits),
        "models": model_audits,
        "transformers_version": importlib.metadata.version("transformers"),
        "lm_eval_version": importlib.metadata.version("lm_eval"),
        "reference": "installed HFLM.tok_encode, no weights loaded, every formal prompt",
    }


def prepare(args):
    plan_path = args.plan.resolve()
    source_plan_sha256 = sha256_file(plan_path)
    plan, _, _ = load_verified_inputs(plan_path)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"preparation output is not empty; use a new attempt directory: {output_dir}")
    snapshot_dir = output_dir / "frozen_inputs"
    data_dir = snapshot_dir / "data"
    data_dir.mkdir(parents=True)
    shutil.copyfile(plan_path, snapshot_dir / "source_plan.json")
    schedule_path = resolve_input_path(plan_path, plan["protocol"]["fewshot_schedule_file"])
    shutil.copyfile(schedule_path, snapshot_dir / "fewshot_indices.json")
    data_root = resolve_input_path(plan_path, plan["data"]["root"])
    for split in ("train", "test"):
        shutil.copyfile(data_root / f"{split}.jsonl", data_dir / f"{split}.jsonl")
    frozen_plan = deepcopy(plan)
    frozen_plan["data"]["root"] = "data"
    frozen_plan["protocol"]["fewshot_schedule_file"] = "fewshot_indices.json"
    # Protocol parameters are preserved; only source locations become portable.
    frozen_plan_path = snapshot_dir / "plan.json"
    atomic_json(frozen_plan_path, frozen_plan)
    request_audits = {}
    formal = None
    for stage in STAGES:
        rows = prepare_requests(frozen_plan_path, stage)
        source_rows = prepare_requests(plan_path, stage)
        if rows != source_rows:
            raise ValueError(f"{stage} snapshot requests differ from original inputs")
        path = snapshot_dir / f"{stage}_requests.jsonl"
        write_jsonl(path, rows)
        request_audits[stage] = {
            "requests": len(rows), "path": str(path), "sha256": sha256_file(path),
            "canonical_requests_sha256": canonical_hash(rows),
            "sample_ids": [row["sample_id"] for row in rows],
        }
        if stage == "formal":
            formal = rows
    if sha256_file(plan_path) != source_plan_sha256:
        raise ValueError("source plan changed during preparation")
    manifest = {
        "schema": "scalellm_gsm8k_input_snapshot_v1",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_plan": str(plan_path), "source_plan_sha256": source_plan_sha256,
        "frozen_plan": str(frozen_plan_path), "frozen_plan_sha256": sha256_file(frozen_plan_path),
        "protocol_id": plan["protocol_id"], "protocol_sha256": canonical_hash(plan["protocol"]),
        "dataset_hashes": plan["data"]["dataset_hashes"],
        "fewshot_schedule_sha256": plan["protocol"]["fewshot_schedule_sha256"],
        "requests": request_audits,
        "snapshot_reconstruction_exact": True,
        "preparation_script_sha256": sha256_file(Path(__file__)),
        "protocol_module_sha256": sha256_file(Path(__file__).with_name("gsm8k_protocol.py")),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    atomic_json(output_dir / "input_manifest.json", manifest)
    if args.tokenizer_audit:
        tokenizer_dir = output_dir / "tokenizers"
        tokenizer_dir.mkdir()
        audit = tokenizer_audit(plan, formal, args.model_root, tokenizer_dir)
        audit["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(output_dir / "tokenizer_audit.json", audit)
        if not audit["passed"]:
            raise ValueError("tokenizer audit failed; inspect per-model budget/parity evidence")
    print(json.dumps({"input_manifest": str(output_dir / "input_manifest.json"), "snapshot_reconstruction_exact": True}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tokenizer-audit", action="store_true")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    args = parser.parse_args()
    # This CLI is intentionally CPU-only, including when started without the
    # shell environment recommended in the execution contract.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
    os.sched_setaffinity(0, {8, 9})
    try:
        prepare(args)
    except Exception as exc:
        print(f"preparation failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
