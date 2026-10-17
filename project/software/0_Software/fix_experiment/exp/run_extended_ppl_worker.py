#!/usr/bin/env python3
"""Evaluate the five ScaleLLM configurations on additional local PPL corpora.

This worker deliberately keeps the already-frozen ScaleLLM model/QDQ loader,
but extends the WikiText-2 non-overlapping 2048-token PPL protocol to the
other pinned local corpora.  Each completed corpus is checkpointed separately
so a long run can resume without discarding earlier GPU work.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback
from typing import Any

import torch
import torch.nn.functional as F

from run_eval_worker import (
    atomic_json,
    configure_reproducibility,
    load_model,
    load_model_identity,
    package_versions,
)
from six_model_matrix import (
    FIVE_CONFIG_CASES,
    QUANTIZED_CASE_SPECS,
    get_model_spec,
    validate_quantized_summary,
)
from protocol import DATA_ROOT, MODEL_ROOT


THIS_DIR = Path(__file__).resolve().parent
DATA_MANIFEST = DATA_ROOT / "bape_eval" / "manifest.json"
DEFAULT_MODEL = MODEL_ROOT / "Llama-3.1-8B-Instruct"

TASK_SPECS = {
    "ptb_ppl": {
        "asset_id": "ptb_test",
        "separator": "none",
        "description": "Penn Treebank legacy text-only test",
    },
    "c4_fixed_ppl": {
        "asset_id": "c4_official_validation_first10000",
        "separator": "none",
        "description": "C4-en validation shard-0 fixed rows [0,10000)",
    },
    "lambada_full_ppl": {
        "asset_id": "lambada_test",
        "separator": "none",
        "description": "LAMBADA OpenAI full-text token PPL",
    },
    "imdb_ppl": {
        "asset_id": "imdb_test",
        "separator": "none",
        "description": "IMDB test full-text domain-stress PPL",
    },
    "ag_news_ppl": {
        "asset_id": "ag_news_test",
        "separator": "none",
        "description": "AG News test full-text domain-stress PPL",
    },
}
TASK_ORDER = tuple(TASK_SPECS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=FIVE_CONFIG_CASES, required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--model-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", default=",".join(TASK_ORDER))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--block-size", type=int, default=2048)
    parser.add_argument("--ppl-batch-size", type=int, default=1)
    parser.add_argument(
        "--limit-blocks",
        type=int,
        default=0,
        help="Positive value is a smoke limit per corpus; zero means all complete blocks.",
    )
    parser.add_argument("--seed", type=int, default=20260913)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_registered_assets() -> dict[str, dict[str, Any]]:
    manifest = json.loads(DATA_MANIFEST.read_text(encoding="utf-8"))
    assets = {str(asset["id"]): asset for asset in manifest["assets"]}
    for spec in TASK_SPECS.values():
        asset_id = str(spec["asset_id"])
        if asset_id not in assets:
            raise KeyError(f"asset {asset_id!r} absent from {DATA_MANIFEST}")
    return assets


def validate_asset(asset: dict[str, Any]) -> Path:
    path = DATA_ROOT / Path(asset["path"]).relative_to("data")
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    expected = str(asset["sha256"])
    if observed != expected:
        raise ValueError(f"dataset SHA-256 mismatch for {asset['id']}: {observed} != {expected}")
    return path


def read_texts(path: Path, asset: dict[str, Any]) -> list[str]:
    if path.suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        if asset["id"] == "c4_official_validation_first10000":
            rows.sort(key=lambda row: int(row["source_index"]))
        texts = [str(row["text"]) for row in rows]
    elif path.suffix == ".txt":
        texts = path.read_text(encoding="utf-8").splitlines()
    elif path.suffix == ".parquet":
        import pyarrow.parquet as pq

        texts = [str(value) for value in pq.read_table(path, columns=["text"])["text"].to_pylist()]
    else:
        raise ValueError(f"unsupported PPL data file: {path}")
    expected_rows = int(asset["rows"])
    if len(texts) != expected_rows:
        raise ValueError(f"row count mismatch for {asset['id']}: {len(texts)} != {expected_rows}")
    if not texts:
        raise ValueError(f"empty PPL corpus: {asset['id']}")
    return texts


def join_texts(texts: list[str], separator: str) -> str:
    joiner = {"none": "", "newline": "\n", "double_newline": "\n\n"}[separator]
    return joiner.join(texts)


def result_is_valid(
    path: Path,
    *,
    task: str,
    case: str,
    fingerprint: str,
    full_split: bool,
) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return (
            value.get("status") == "complete"
            and value.get("task") == task
            and value.get("case") == case
            and value.get("model_fingerprint_sha256") == fingerprint
            and bool(value.get("full_split")) == full_split
            and int(value.get("scoring_tokens", 0)) > 0
            and math.isfinite(float(value.get("value")))
        )
    except Exception:
        return False


@torch.no_grad()
def evaluate_nonoverlap_ppl(
    *,
    model: Any,
    tokenizer: Any,
    device: torch.device,
    text: str,
    task: str,
    block_size: int,
    batch_size: int,
    limit_blocks: int | None,
) -> dict[str, Any]:
    started = time.time()
    token_ids = tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    raw_tokens = int(token_ids.numel())
    available_blocks = raw_tokens // block_size
    block_count = available_blocks if limit_blocks is None else min(limit_blocks, available_blocks)
    if block_count <= 0:
        raise ValueError(f"{task} has no complete {block_size}-token block")
    used = token_ids[: block_count * block_size].reshape(block_count, block_size)
    total_nll = 0.0
    scoring_tokens = 0
    batch_size = max(1, batch_size)
    report_every = max(1, min(100, block_count // 20 or 1))
    for start in range(0, block_count, batch_size):
        batch = used[start : start + batch_size].to(device)
        logits = model(input_ids=batch, use_cache=False, return_dict=True).logits
        shifted = logits[:, :-1, :].to(torch.float32)
        labels = batch[:, 1:]
        loss = F.cross_entropy(
            shifted.reshape(-1, shifted.shape[-1]),
            labels.reshape(-1),
            reduction="sum",
        )
        if not torch.isfinite(loss):
            raise FloatingPointError(f"non-finite NLL in {task}")
        total_nll += float(loss.detach().cpu())
        scoring_tokens += int(labels.numel())
        completed = min(start + batch_size, block_count)
        if completed == block_count or completed % report_every == 0:
            print(
                json.dumps(
                    {
                        "task": task,
                        "blocks": completed,
                        "total_blocks": block_count,
                        "ppl_so_far": math.exp(total_nll / scoring_tokens),
                    }
                ),
                flush=True,
            )
        del batch, logits, shifted, labels, loss
    avg_nll = total_nll / scoring_tokens
    return {
        "task": task,
        "kind": "ppl",
        "primary_metric": "token_perplexity",
        "value": math.exp(avg_nll),
        "avg_nll": avg_nll,
        "total_nll": total_nll,
        "raw_token_count": raw_tokens,
        "block_size": block_size,
        "available_complete_blocks": available_blocks,
        "evaluated_blocks": block_count,
        "tokens_in_evaluated_blocks": block_count * block_size,
        "scoring_tokens": scoring_tokens,
        "discarded_tail_tokens": raw_tokens - available_blocks * block_size,
        "unscored_block_initial_tokens": block_count,
        "elapsed_sec": time.time() - started,
        "full_split": limit_blocks is None,
        "non_overlapping": True,
        "tail_policy": "drop_incomplete_block",
        "add_special_tokens": False,
    }


def main() -> None:
    args = parse_args()
    args.model = args.model.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.block_size != 2048:
        raise ValueError("extended literature protocol is frozen to block_size=2048")
    tasks = [part.strip() for part in args.tasks.split(",") if part.strip()]
    invalid = set(tasks) - set(TASK_ORDER)
    if invalid or len(tasks) != len(set(tasks)):
        raise ValueError(f"invalid/duplicate extended PPL tasks: {sorted(invalid)}")
    limit_blocks = None if args.limit_blocks <= 0 else args.limit_blocks
    full_split = limit_blocks is None
    configure_reproducibility(args.seed)
    spec = get_model_spec(args.model)
    identity = load_model_identity(args.model_identity, args.model)
    if identity is None:
        raise ValueError("model identity is required")
    fingerprint = str(identity["fingerprint_sha256"])
    assets = load_registered_assets()
    sources: dict[str, dict[str, Any]] = {}
    texts: dict[str, list[str]] = {}
    for task in tasks:
        task_spec = TASK_SPECS[task]
        asset = assets[str(task_spec["asset_id"])]
        path = validate_asset(asset)
        task_texts = read_texts(path, asset)
        texts[task] = task_texts
        sources[task] = {
            "asset_id": asset["id"],
            "path": str(path.resolve()),
            "sha256": asset["sha256"],
            "rows": len(task_texts),
            "split": asset["split"],
            "separator": task_spec["separator"],
            "description": task_spec["description"],
        }
    result_paths = {task: args.output / f"{task}.json" for task in tasks}
    pending = [
        task for task in tasks
        if not result_is_valid(
            result_paths[task],
            task=task,
            case=args.case,
            fingerprint=fingerprint,
            full_split=full_split,
        )
    ]
    state_base = {
        "schema": "scalellm_extended_ppl_worker_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "device": args.device,
        "model": str(args.model),
        "model_spec": spec.to_dict(),
        "model_identity": identity,
        "case": args.case,
        "tasks": tasks,
        "pending_tasks": pending,
        "block_size": args.block_size,
        "ppl_batch_size": args.ppl_batch_size,
        "limit_blocks": limit_blocks,
        "full_split": full_split,
        "seed": args.seed,
        "data_manifest": str(DATA_MANIFEST.resolve()),
        "data_manifest_sha256": sha256_file(DATA_MANIFEST),
        "sources": sources,
    }
    if not pending:
        atomic_json(args.output / "run_state.json", {**state_base, "status": "complete_cached"})
        return
    atomic_json(args.output / "run_state.json", {**state_base, "status": "loading_model"})
    started = time.time()
    try:
        model, tokenizer, method, audit = load_model(args)
        if args.case in QUANTIZED_CASE_SPECS:
            validate_quantized_summary(method, spec, args.case)
        completed: list[str] = [task for task in tasks if task not in pending]
        for task in pending:
            atomic_json(
                args.output / "run_state.json",
                {**state_base, "status": "evaluating", "active_task": task, "completed_tasks": completed},
            )
            metric = evaluate_nonoverlap_ppl(
                model=model,
                tokenizer=tokenizer,
                device=torch.device(args.device),
                text=join_texts(texts[task], str(TASK_SPECS[task]["separator"])),
                task=task,
                block_size=args.block_size,
                batch_size=args.ppl_batch_size,
                limit_blocks=limit_blocks,
            )
            result = {
                "schema": "scalellm_extended_ppl_result_v1",
                "status": "complete",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model": spec.name,
                "model_fingerprint_sha256": fingerprint,
                "case": args.case,
                "full_split": full_split,
                "source": sources[task],
                "method": method,
                **metric,
            }
            atomic_json(result_paths[task], result)
            completed.append(task)
        results = [json.loads(result_paths[task].read_text(encoding="utf-8")) for task in tasks]
        manifest = {
            **state_base,
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_sec": time.time() - started,
            "method": method,
            "hardware_audit": audit.collect() if audit is not None else None,
            "versions": package_versions(),
            "results": results,
        }
        atomic_json(args.output / "manifest.json", manifest)
        atomic_json(args.output / "run_state.json", {**state_base, "status": "complete", "completed_tasks": tasks})
    except Exception as exc:
        failure = {
            **state_base,
            "status": "failed",
            "elapsed_sec": time.time() - started,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        atomic_json(args.output / "run_state.json", failure)
        atomic_json(args.output / "failure.json", failure)
        raise
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
