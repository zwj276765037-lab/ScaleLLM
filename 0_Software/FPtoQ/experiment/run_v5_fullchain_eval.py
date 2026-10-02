#!/usr/bin/env python3
"""Run matched BF16/V5-production ACC and WikiText2 PPL evaluations."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


THIS_DIR = Path(__file__).resolve().parent
SOFTWARE_ROOT = THIS_DIR.parents[1]
SCRIPT_ROOT = SOFTWARE_ROOT / "experiment" / "scripts"
SCALE_CODE_DIR = SCRIPT_ROOT / "scale_code_linear"
GYROT_DIR = (
    SCRIPT_ROOT
    / "accuracy_MLP_4bit"
    / "scala_code_accuracy"
)
for path in (THIS_DIR, SCALE_CODE_DIR, GYROT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_s11_cross_model_quality_accuracy import (  # noqa: E402
    append_jsonl,
    configure_reproducibility,
    evaluate_mcqa,
    evaluate_wikitext,
    read_wikitext,
    score_completion_batch,
    write_csv,
    write_json,
)
from run_gyrot_aligned_quality_accuracy import (  # noqa: E402
    PRIMARY_METRIC,
    TASK_LABELS,
    TASK_PATHS,
    build_gyrot_samples,
    load_task_rows,
)
from v5_fullchain import attach_v5_fullchain  # noqa: E402


DEFAULT_PROJECT = THIS_DIR.parents[3] / "fpga_llm_project"
DEFAULT_MODEL = DEFAULT_PROJECT / "configs/models/Llama-3.1-8B-Instruct"
DEFAULT_WIKITEXT = (
    DEFAULT_PROJECT / "data/wikitext-2-raw-v1/test-00000-of-00001.jsonl"
)
DEFAULT_OUTPUT = SOFTWARE_ROOT / "results/v5_fullchain/Llama-3.1-8B-Instruct"
MCQA_TASKS = ("piqa", "arc_challenge", "openbookqa", "hellaswag", "winogrande")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("bf16", "v5"), required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--wikitext", type=Path, default=DEFAULT_WIKITEXT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--tasks",
        default="wikitext2," + ",".join(MCQA_TASKS),
        help="Comma-separated wikitext2/piqa/arc_challenge/openbookqa/hellaswag/winogrande",
    )
    parser.add_argument("--max-mcqa-samples", type=int, default=0)
    parser.add_argument("--mcqa-batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--wikitext-max-tokens", type=int, default=65536)
    parser.add_argument("--wikitext-block-size", type=int, default=128)
    parser.add_argument("--wikitext-stride", type=int, default=127)
    parser.add_argument("--wikitext-batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument(
        "--allow-format-errors",
        action="store_true",
        help="Continue with RTL zero-guard semantics while retaining a failing audit.",
    )
    return parser.parse_args()


def _atomic_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_csv(temporary, rows)
    temporary.replace(path)


@torch.no_grad()
def evaluate_mcqa_flat_batched(
    *,
    model: Any,
    tokenizer: Any,
    task: str,
    samples: list[dict[str, Any]],
    device: torch.device,
    batch_size: int,
    rank_metric: str,
    max_length: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Batch choices across samples while preserving the archived scoring rule."""
    started = time.time()
    flat: list[tuple[int, int, str, str]] = []
    for sample_index, sample in enumerate(samples):
        for choice_index, (prefix, suffix) in enumerate(
            zip(sample["prefixes"], sample["suffixes"], strict=True)
        ):
            flat.append((sample_index, choice_index, prefix, suffix))
    scores: list[list[dict[str, Any] | None]] = [
        [None] * len(sample["suffixes"]) for sample in samples
    ]
    for start in range(0, len(flat), max(1, batch_size)):
        chunk = flat[start : start + max(1, batch_size)]
        results = score_completion_batch(
            model,
            tokenizer,
            [row[2] for row in chunk],
            [row[3] for row in chunk],
            device,
            max_length,
        )
        for (sample_index, choice_index, _prefix, _suffix), result in zip(
            chunk, results, strict=True
        ):
            scores[sample_index][choice_index] = result
        if start and start % (50 * max(1, batch_size)) == 0:
            print(
                f"[V5:{task}] scored {start}/{len(flat)} choices",
                flush=True,
            )

    correct = {name: 0 for name in ("score_sum", "score_mean", "score_char_norm")}
    records: list[dict[str, Any]] = []
    finite = True
    for sample_index, (sample, optional_scores) in enumerate(zip(samples, scores)):
        choice_scores = [value for value in optional_scores if value is not None]
        if len(choice_scores) != len(optional_scores):
            raise AssertionError("missing flattened MCQA choice score")
        predictions = {
            metric: max(
                range(len(choice_scores)),
                key=lambda index: float(choice_scores[index][metric]),
            )
            for metric in correct
        }
        gold = int(sample["gold_index"])
        for metric, prediction in predictions.items():
            correct[metric] += int(prediction == gold)
        finite = finite and all(
            math.isfinite(float(score[rank_metric])) for score in choice_scores
        )
        records.append(
            {
                "task": task,
                "sample_id": sample.get("row_id", sample_index),
                "sample_index": sample_index,
                "gold_index": gold,
                "pred_score_sum": predictions["score_sum"],
                "pred_score_mean": predictions["score_mean"],
                "pred_score_char_norm": predictions["score_char_norm"],
                "active_pred": predictions[rank_metric],
                "active_correct": int(predictions[rank_metric] == gold),
                "choice_scores_json": json.dumps(choice_scores, ensure_ascii=False),
            }
        )
    count = len(samples)
    denominator = max(1, count)
    return (
        {
            "task": task,
            "samples": count,
            "records_complete": count > 0 and len(records) == count,
            "mcqa_accuracy": correct[rank_metric] / denominator,
            "accuracy_score_sum": correct["score_sum"] / denominator,
            "accuracy_score_mean": correct["score_mean"] / denominator,
            "accuracy_score_char_norm": correct["score_char_norm"] / denominator,
            "rank_metric": rank_metric,
            "finite": finite,
            "elapsed_sec": time.time() - started,
            "status": "pass" if finite and count > 0 else "inspect",
        },
        records,
    )


@torch.no_grad()
def evaluate_wikitext_batched(
    *,
    model: Any,
    tokenizer: Any,
    path: Path,
    device: torch.device,
    block_size: int,
    stride: int,
    max_tokens: int,
    batch_size: int,
) -> dict[str, Any]:
    """Matched non-overlapping V5-context PPL with independent windows batched."""
    import torch.nn.functional as functional

    started = time.time()
    ids = tokenizer(
        read_wikitext(path), add_special_tokens=False, return_tensors="pt"
    )["input_ids"][0]
    if max_tokens > 0:
        ids = ids[:max_tokens]
    windows: list[torch.Tensor] = []
    for start in range(0, max(1, ids.numel() - 1), stride):
        end = min(start + block_size, ids.numel())
        if end - start < 4:
            break
        windows.append(ids[start:end])
        if end >= ids.numel():
            break
    total_nll = 0.0
    total_tokens = 0
    total_correct = 0
    finite = True
    for start in range(0, len(windows), max(1, batch_size)):
        chunk = windows[start : start + max(1, batch_size)]
        # With stride=block_size-1, only the final window can be shorter.
        # Evaluate it separately to avoid adding padding labels.
        by_length: dict[int, list[torch.Tensor]] = {}
        for window in chunk:
            by_length.setdefault(int(window.numel()), []).append(window)
        for same_length in by_length.values():
            token_batch = torch.stack(same_length).to(device)
            outputs = model(
                input_ids=token_batch[:, :-1], use_cache=False, return_dict=True
            )
            logits = outputs.logits.to(torch.float32)
            labels = token_batch[:, 1:]
            loss = functional.cross_entropy(
                logits.reshape(-1, logits.shape[-1]),
                labels.reshape(-1),
                reduction="sum",
            )
            if not torch.isfinite(loss):
                finite = False
                break
            total_nll += float(loss.detach().cpu())
            total_tokens += int(labels.numel())
            total_correct += int((logits.argmax(dim=-1) == labels).sum().cpu())
        if not finite:
            break
        print(
            f"[V5:wikitext2] windows {min(start + batch_size, len(windows))}/{len(windows)}",
            flush=True,
        )
    avg_nll = total_nll / max(1, total_tokens)
    perplexity = (
        math.exp(avg_nll)
        if finite and math.isfinite(avg_nll) and avg_nll < 80
        else float("inf")
    )
    return {
        "task": "wikitext2",
        "samples": len(windows),
        "records_complete": finite and total_tokens > 0,
        "num_tokens": total_tokens,
        "avg_nll": avg_nll,
        "ppl": perplexity,
        "token_accuracy": total_correct / max(1, total_tokens),
        "finite": finite and math.isfinite(perplexity),
        "elapsed_sec": time.time() - started,
        "status": "pass" if finite and math.isfinite(perplexity) else "inspect",
    }


def main() -> None:
    args = parse_args()
    if args.max_length > 128 or args.wikitext_block_size > 128:
        raise ValueError("V5 production comparison must not exceed 128 keys")
    tasks = [value.strip() for value in args.tasks.split(",") if value.strip()]
    invalid_tasks = set(tasks) - ({"wikitext2"} | set(MCQA_TASKS))
    if invalid_tasks:
        raise ValueError(f"unsupported tasks: {sorted(invalid_tasks)}")

    started = time.time()
    reproducibility = configure_reproducibility(
        seed=args.seed, deterministic=True, allow_tf32=False
    )
    device = torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.set_device(device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=True
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",
    ).to(device)
    model.eval()
    if args.case == "v5":
        method, audit = attach_v5_fullchain(
            model,
            checkpoint_dir=args.model,
            device=device,
            strict_total_shift=not args.allow_format_errors,
        )
    else:
        method = {
            "case": "bf16_matched_context128",
            "max_context": 128,
            "dtype": "bfloat16",
        }
        audit = None
    model.eval()

    case_dir = args.output / args.case
    case_dir.mkdir(parents=True, exist_ok=True)
    summary_path = case_dir / "quality_by_task.csv"
    records_path = case_dir / "mcqa_records.jsonl"
    if records_path.exists():
        records_path.unlink()
    summary_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []

    def save_progress() -> None:
        current_audit = audit.collect() if audit is not None else None
        hardware_status = (
            "invalid_format_error"
            if current_audit is not None
            and current_audit["linear_total_shift_format_error"] > 0
            else "valid_so_far"
        )
        if summary_rows:
            summary_rows[-1]["hardware_contract_status"] = hardware_status
        _atomic_rows(summary_path, summary_rows)
        _atomic_rows(case_dir / "invalid_rows.csv", invalid_rows)
        write_json(
            case_dir / "run_state.json",
            {
                "schema": "scalellm_v5_fullchain_quality_v1",
                "case": args.case,
                "status": "running",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_sec": time.time() - started,
                "completed_tasks": [row["task"] for row in summary_rows],
                "method": method,
                "audit": current_audit,
                "hardware_contract_status": hardware_status,
            },
        )

    for task in tasks:
        task_started = time.time()
        if task == "wikitext2":
            metrics = evaluate_wikitext_batched(
                model=model,
                tokenizer=tokenizer,
                path=args.wikitext,
                device=device,
                block_size=args.wikitext_block_size,
                stride=args.wikitext_stride,
                max_tokens=args.wikitext_max_tokens,
                batch_size=args.wikitext_batch_size,
            )
            summary_rows.append(
                {
                    "case": args.case,
                    "task": task,
                    "task_label": "WikiText2",
                    "samples": metrics["samples"],
                    "records_complete": metrics["records_complete"],
                    "ppl": metrics["ppl"],
                    "avg_nll": metrics["avg_nll"],
                    "token_accuracy": metrics["token_accuracy"],
                    "scoring_tokens": metrics["num_tokens"],
                    "status": metrics["status"],
                    "elapsed_sec": metrics["elapsed_sec"],
                    "context_length": args.wikitext_block_size,
                    "stride": args.wikitext_stride,
                }
            )
        else:
            limit = None if args.max_mcqa_samples <= 0 else args.max_mcqa_samples
            rows, source = load_task_rows(
                task=task,
                path=TASK_PATHS[task],
                limit=limit,
                allow_dataset_download=False,
                materialize_missing_data=False,
            )
            samples, invalid = build_gyrot_samples(task, rows)
            invalid_rows.extend({"case": args.case, **row} for row in invalid)
            metric_name = PRIMARY_METRIC[task]
            metrics, records = evaluate_mcqa_flat_batched(
                model=model,
                tokenizer=tokenizer,
                task=task,
                samples=samples,
                device=device,
                batch_size=args.mcqa_batch_size,
                rank_metric=metric_name,
                max_length=args.max_length,
            )
            append_jsonl(
                records_path,
                [{"case": args.case, **record} for record in records],
            )
            summary_rows.append(
                {
                    "case": args.case,
                    "task": task,
                    "task_label": TASK_LABELS[task],
                    "dataset": source,
                    "samples": metrics["samples"],
                    "records_complete": metrics["records_complete"],
                    "primary_metric": metric_name,
                    "primary_accuracy": metrics[f"accuracy_{metric_name}"],
                    "accuracy_score_sum": metrics["accuracy_score_sum"],
                    "accuracy_score_mean": metrics["accuracy_score_mean"],
                    "accuracy_score_char_norm": metrics[
                        "accuracy_score_char_norm"
                    ],
                    "status": metrics["status"],
                    "elapsed_sec": metrics["elapsed_sec"],
                    "max_length": args.max_length,
                }
            )
        save_progress()
        print(
            json.dumps(
                {
                    "completed": task,
                    "case": args.case,
                    "elapsed_sec": time.time() - task_started,
                    "row": summary_rows[-1],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

    final_audit = audit.collect() if audit is not None else None
    hardware_status = (
        "invalid_format_error"
        if final_audit is not None
        and final_audit["linear_total_shift_format_error"] > 0
        else "valid"
    )
    write_json(
        case_dir / "manifest.json",
        {
            "schema": "scalellm_v5_fullchain_quality_v1",
            "case": args.case,
            "status": (
                "complete_invalid_format_error"
                if hardware_status != "valid"
                else "complete"
            ),
            "hardware_contract_status": hardware_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_sec": time.time() - started,
            "model": str(args.model.resolve()),
            "args": {
                key: str(value) if isinstance(value, Path) else value
                for key, value in vars(args).items()
            },
            "reproducibility": reproducibility,
            "method": method,
            "audit": final_audit,
            "results": summary_rows,
        },
    )
    write_json(
        case_dir / "run_state.json",
        {
            "schema": "scalellm_v5_fullchain_quality_v1",
            "case": args.case,
            "status": (
                "complete_invalid_format_error"
                if hardware_status != "valid"
                else "complete"
            ),
            "hardware_contract_status": hardware_status,
            "elapsed_sec": time.time() - started,
            "completed_tasks": tasks,
            "audit": final_audit,
        },
    )
    print(json.dumps({
        "status": (
            "complete_invalid_format_error"
            if hardware_status != "valid"
            else "complete"
        ),
        "hardware_contract_status": hardware_status,
        "results": summary_rows,
        "audit": final_audit,
    }, indent=2))


if __name__ == "__main__":
    main()
