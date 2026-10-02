#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

from scalepath4_method_inference import attach_scalepath_iah_scale_code


ARCHIVE_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PROJECT_ROOT = Path(__file__).resolve().parents[5] / "fpga_llm_project"
PROJECT_ROOT = Path(os.environ.get("FPGA_LLM_PROJECT_ROOT", _FALLBACK_PROJECT_ROOT)).expanduser().resolve()
DEFAULT_ROOT = (
    ARCHIVE_ROOT
    / "results"
    / "_rerun"
    / "scalecode_a8w8_quality_accuracy"
)

TASK_PATHS = {
    "arc_challenge": PROJECT_ROOT / "data" / "arc_challenge" / "validation_first300.jsonl",
    "piqa": PROJECT_ROOT / "data" / "piqa" / "validation_first300.jsonl",
    "openbookqa": PROJECT_ROOT / "data" / "openbookqa" / "validation_first300.jsonl",
    "hellaswag": PROJECT_ROOT / "data" / "hellaswag" / "hellaswag_val.jsonl",
    "winogrande": PROJECT_ROOT / "data" / "winogrande" / "winogrande_1.1" / "winogrande_1.1" / "dev.jsonl",
}
WIKITEXT_PATH = PROJECT_ROOT / "data" / "wikitext-2-raw-v1" / "test-00000-of-00001.jsonl"


def dtype_from_name(name: str) -> torch.dtype:
    return {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[name]


def configure_reproducibility(
    *,
    seed: int | None,
    deterministic: bool,
    allow_tf32: bool | None,
) -> dict[str, Any]:
    if seed is not None:
        os.environ.setdefault("PYTHONHASHSEED", str(seed))
        random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    if allow_tf32 is not None and hasattr(torch.backends, "cuda"):
        torch.backends.cuda.matmul.allow_tf32 = bool(allow_tf32)
        torch.backends.cudnn.allow_tf32 = bool(allow_tf32)
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except TypeError:
            torch.use_deterministic_algorithms(True)
    return {
        "seed": seed,
        "deterministic": deterministic,
        "allow_tf32": allow_tf32,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", ""),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG", ""),
        "torch_initial_seed": int(torch.initial_seed()),
        "torch_deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if limit is not None and len(rows) >= limit:
                break
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def letter_to_index(label: str, labels: list[str]) -> int:
    if label in labels:
        return labels.index(label)
    return ord(label.upper()) - ord("A")


def build_mcqa_samples(task: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        try:
            if task == "arc_challenge":
                labels = [str(x) for x in row["choices"]["label"]]
                choices = [str(x) for x in row["choices"]["text"]]
                samples.append(
                    {
                        "row_id": row.get("id", idx),
                        "prefixes": [f"Question: {row['question']}\nAnswer:" for _ in choices],
                        "suffixes": [" " + choice for choice in choices],
                        "gold_index": letter_to_index(str(row["answerKey"]), labels),
                    }
                )
            elif task == "openbookqa":
                if isinstance(row.get("question"), dict):
                    question_obj = row["question"]
                    labels = [str(choice["label"]) for choice in question_obj["choices"]]
                    choices = [str(choice["text"]) for choice in question_obj["choices"]]
                    question = str(question_obj.get("stem", ""))
                else:
                    labels = [str(x) for x in row["choices"]["label"]]
                    choices = [str(x) for x in row["choices"]["text"]]
                    question = row.get("question_stem") or row.get("question") or ""
                samples.append(
                    {
                        "row_id": row.get("id", idx),
                        "prefixes": [f"Question: {question}\nAnswer:" for _ in choices],
                        "suffixes": [" " + choice for choice in choices],
                        "gold_index": letter_to_index(str(row["answerKey"]), labels),
                    }
                )
            elif task == "piqa":
                choices = [str(row["sol1"]), str(row["sol2"])]
                samples.append(
                    {
                        "row_id": row.get("id", idx),
                        "prefixes": [f"Goal: {row['goal']}\nSolution:" for _ in choices],
                        "suffixes": [" " + choice for choice in choices],
                        "gold_index": int(row["label"]),
                    }
                )
            elif task == "hellaswag":
                endings = [str(x) for x in row["endings"]]
                ctx = str(row.get("ctx") or (str(row.get("ctx_a", "")) + " " + str(row.get("ctx_b", "")))).strip()
                samples.append(
                    {
                        "row_id": row.get("ind", idx),
                        "prefixes": [ctx for _ in endings],
                        "suffixes": [" " + ending for ending in endings],
                        "gold_index": int(row["label"]),
                    }
                )
            elif task == "winogrande":
                sentence = str(row["sentence"])
                before, after = sentence.split("_", 1)
                choices = [str(row["option1"]), str(row["option2"])]
                samples.append(
                    {
                        "row_id": row.get("qID", idx),
                        "prefixes": [before for _ in choices],
                        "suffixes": [choice + after for choice in choices],
                        "gold_index": int(row["answer"]) - 1,
                    }
                )
            else:
                raise ValueError(f"unsupported task: {task}")
        except Exception as exc:  # noqa: BLE001
            invalid.append({"task": task, "row_index": idx, "reason": repr(exc), "status": "invalid_input"})
    return samples, invalid


def encode_context_continuation(tokenizer: Any, context: str, continuation: str) -> tuple[list[int], list[int]]:
    if not context:
        cont = tokenizer(continuation, add_special_tokens=False)["input_ids"]
        bos = tokenizer.bos_token_id if tokenizer.bos_token_id is not None else tokenizer.eos_token_id
        if bos is None:
            return cont[:1], cont[1:]
        if cont and bos == cont[0]:
            return cont[:1], cont[1:]
        return [bos], cont
    n_spaces = len(context) - len(context.rstrip())
    if n_spaces > 0:
        continuation = context[-n_spaces:] + continuation
        context = context[:-n_spaces]
    whole = tokenizer(context + continuation, add_special_tokens=False)["input_ids"]
    ctx = tokenizer(context, add_special_tokens=False)["input_ids"]
    cont = whole[len(ctx) :]
    if not cont:
        cont = tokenizer(continuation, add_special_tokens=False)["input_ids"]
    return ctx, cont


@torch.no_grad()
def score_completion_batch(
    model: Any,
    tokenizer: Any,
    prefixes: list[str],
    suffixes: list[str],
    device: torch.device,
    max_length: int,
) -> list[dict[str, Any]]:
    encoded = [encode_context_continuation(tokenizer, p, s) for p, s in zip(prefixes, suffixes)]
    full = [ctx + cont for ctx, cont in encoded]
    cont_lens = [len(cont) for _, cont in encoded]
    valid = [idx for idx, length in enumerate(cont_lens) if length > 0 and len(full[idx]) > 1]
    if not valid:
        return [
            {
                "score_sum": float("-inf"),
                "score_mean": float("-inf"),
                "score_char_norm": float("-inf"),
                "num_completion_tokens": 0,
            }
            for _ in suffixes
        ]

    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    if pad_id is None:
        pad_id = 0
    trimmed: list[list[int]] = []
    trimmed_cont_lens: list[int] = []
    for idx in valid:
        ids = full[idx][-max_length:]
        cont_len = min(cont_lens[idx], len(ids) - 1)
        trimmed.append(ids)
        trimmed_cont_lens.append(cont_len)
    max_len = max(len(ids) for ids in trimmed)
    input_rows = []
    mask_rows = []
    for ids in trimmed:
        inp = ids[:-1]
        pad = max_len - 1 - len(inp)
        input_rows.append(inp + [pad_id] * pad)
        mask_rows.append([1] * len(inp) + [0] * pad)

    input_ids = torch.tensor(input_rows, dtype=torch.long, device=device)
    attention_mask = torch.tensor(mask_rows, dtype=torch.long, device=device)
    out = model(input_ids=input_ids, attention_mask=attention_mask, use_cache=False, return_dict=True)
    log_probs = F.log_softmax(out.logits.to(torch.float32), dim=-1)

    by_index: dict[int, dict[str, Any]] = {}
    for batch_idx, original_idx in enumerate(valid):
        ids = trimmed[batch_idx]
        labels = torch.tensor(ids[1:], dtype=torch.long, device=device)
        seq_lp = log_probs[batch_idx, : labels.numel(), :].gather(-1, labels.unsqueeze(-1)).squeeze(-1)
        cont_len = trimmed_cont_lens[batch_idx]
        selected = seq_lp[-cont_len:]
        score_sum = float(selected.sum().detach().cpu())
        suffix_len = max(1, len(suffixes[original_idx]))
        by_index[original_idx] = {
            "score_sum": score_sum,
            "score_mean": float(selected.mean().detach().cpu()),
            "score_char_norm": score_sum / suffix_len,
            "num_completion_tokens": cont_len,
        }

    results: list[dict[str, Any]] = []
    for idx, suffix in enumerate(suffixes):
        results.append(
            by_index.get(
                idx,
                {
                    "score_sum": float("-inf"),
                    "score_mean": float("-inf"),
                    "score_char_norm": float("-inf"),
                    "num_completion_tokens": 0,
                },
            )
            | {"suffix": suffix}
        )
    return results


@torch.no_grad()
def evaluate_mcqa(
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
    started = time.time()
    correct_by_metric = {"score_sum": 0, "score_mean": 0, "score_char_norm": 0}
    active_correct = 0
    records: list[dict[str, Any]] = []
    finite = True
    for sample_idx, sample in enumerate(samples):
        scores: list[dict[str, Any]] = []
        for start in range(0, len(sample["suffixes"]), max(1, batch_size)):
            scores.extend(
                score_completion_batch(
                    model,
                    tokenizer,
                    sample["prefixes"][start : start + batch_size],
                    sample["suffixes"][start : start + batch_size],
                    device,
                    max_length,
                )
            )
        preds = {
            metric: max(range(len(scores)), key=lambda i: scores[i][metric])
            for metric in ("score_sum", "score_mean", "score_char_norm")
        }
        gold = int(sample["gold_index"])
        for metric, pred in preds.items():
            correct_by_metric[metric] += int(pred == gold)
        active_correct += int(preds[rank_metric] == gold)
        finite = finite and all(math.isfinite(float(score[rank_metric])) for score in scores)
        records.append(
            {
                "task": task,
                "sample_id": sample.get("row_id", sample_idx),
                "sample_index": sample_idx,
                "gold_index": gold,
                "pred_score_sum": preds["score_sum"],
                "pred_score_mean": preds["score_mean"],
                "pred_score_char_norm": preds["score_char_norm"],
                "active_pred": preds[rank_metric],
                "active_correct": int(preds[rank_metric] == gold),
                "choice_scores_json": json.dumps(scores, ensure_ascii=False),
            }
        )
        if (sample_idx + 1) % 50 == 0:
            acc = active_correct / (sample_idx + 1)
            print(f"[S11-E:{task}] {sample_idx + 1}/{len(samples)} acc={acc:.4f}", flush=True)
    sample_count = len(samples)
    denom = max(1, sample_count)
    records_complete = sample_count > 0 and len(records) == sample_count
    metrics = {
        "task": task,
        "samples": sample_count,
        "records_complete": records_complete,
        "mcqa_accuracy": active_correct / denom,
        "accuracy_score_sum": correct_by_metric["score_sum"] / denom,
        "accuracy_score_mean": correct_by_metric["score_mean"] / denom,
        "accuracy_score_char_norm": correct_by_metric["score_char_norm"] / denom,
        "rank_metric": rank_metric,
        "finite": finite,
        "elapsed_sec": time.time() - started,
        "status": "pass" if finite and records_complete else "inspect",
    }
    return metrics, records


def read_wikitext(path: Path, max_docs: int | None = None) -> str:
    texts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if max_docs is not None and len(texts) >= max_docs:
                break
            if not line.strip():
                continue
            row = json.loads(line)
            text = str(row.get("text", ""))
            if text.strip():
                texts.append(text)
    return "\n\n".join(texts)


@torch.no_grad()
def evaluate_wikitext(
    *,
    model: Any,
    tokenizer: Any,
    path: Path,
    device: torch.device,
    block_size: int,
    stride: int,
    max_tokens: int,
) -> dict[str, Any]:
    started = time.time()
    text = read_wikitext(path)
    ids = tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    if max_tokens > 0:
        ids = ids[:max_tokens]
    if ids.numel() < 4:
        raise ValueError(f"not enough WikiText tokens in {path}")
    total_nll = 0.0
    total_tokens = 0
    total_correct = 0
    windows = 0
    finite = True
    for start in range(0, max(1, ids.numel() - 1), stride):
        end = min(start + block_size, ids.numel())
        if end - start < 4:
            break
        input_ids = ids[start:end].unsqueeze(0).to(device)
        outputs = model(input_ids=input_ids[:, :-1], use_cache=False, return_dict=True)
        logits = outputs.logits.to(torch.float32)
        labels = input_ids[:, 1:]
        loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1), reduction="sum")
        if not torch.isfinite(loss):
            finite = False
            break
        preds = logits.argmax(dim=-1)
        total_correct += int((preds == labels).sum().detach().cpu())
        token_count = int(labels.numel())
        total_nll += float(loss.detach().cpu())
        total_tokens += token_count
        windows += 1
        if end >= ids.numel():
            break
    avg_nll = total_nll / max(1, total_tokens)
    ppl = math.exp(avg_nll) if math.isfinite(avg_nll) and avg_nll < 80 else float("inf")
    return {
        "task": "wikitext2",
        "samples": windows,
        "records_complete": total_tokens > 0,
        "num_tokens": total_tokens,
        "avg_nll": avg_nll,
        "ppl": ppl,
        "token_accuracy": total_correct / max(1, total_tokens),
        "finite": finite and math.isfinite(ppl),
        "elapsed_sec": time.time() - started,
        "status": "pass" if finite and math.isfinite(ppl) else "inspect",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="S11-E cross-model quality/accuracy smoke for all portability models.")
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--model_name", default="")
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--attn_implementation", choices=["eager", "sdpa"], default="eager")
    parser.add_argument("--local_files_only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trust_remote_code", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--tasks", default="wikitext2,arc_challenge,piqa,openbookqa,hellaswag,winogrande")
    parser.add_argument("--max_mcqa_samples", type=int, default=300)
    parser.add_argument("--mcqa_batch_size", type=int, default=4)
    parser.add_argument("--rank_metric", choices=["score_sum", "score_mean", "score_char_norm"], default="score_sum")
    parser.add_argument("--max_length", type=int, default=768)
    parser.add_argument("--wikitext_path", type=Path, default=WIKITEXT_PATH)
    parser.add_argument("--arc_challenge_path", type=Path, default=TASK_PATHS["arc_challenge"])
    parser.add_argument("--piqa_path", type=Path, default=TASK_PATHS["piqa"])
    parser.add_argument("--openbookqa_path", type=Path, default=TASK_PATHS["openbookqa"])
    parser.add_argument("--hellaswag_path", type=Path, default=TASK_PATHS["hellaswag"])
    parser.add_argument("--winogrande_path", type=Path, default=TASK_PATHS["winogrande"])
    parser.add_argument("--wikitext_block_size", type=int, default=1024)
    parser.add_argument("--wikitext_stride", type=int, default=1024)
    parser.add_argument("--wikitext_max_tokens", type=int, default=65536)
    parser.add_argument(
        "--inference_case",
        choices=["bf16_baseline", "fp16_baseline", "fp32_baseline", "iah_scale_code"],
        default="bf16_baseline",
    )
    parser.add_argument("--hadamard_block", type=int, default=32)
    parser.add_argument("--group_size", type=int, default=32)
    parser.add_argument("--act_bits", type=int, default=8)
    parser.add_argument("--weight_bits", type=int, default=8)
    parser.add_argument("--scale_code_bits", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--allow_tf32", action=argparse.BooleanOptionalAction, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    reproducibility = configure_reproducibility(
        seed=args.seed,
        deterministic=args.deterministic,
        allow_tf32=args.allow_tf32,
    )
    model_name = args.model_name or args.model_path.name
    output_dir = args.output_dir / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "quality_mcqa_records.jsonl"
    if records_path.exists():
        records_path.unlink()
    device = torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.set_device(device)
    dtype = dtype_from_name(args.dtype)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        torch_dtype=dtype,
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
        attn_implementation=args.attn_implementation,
    ).to(device)
    model.eval()
    method_summary: dict[str, Any] | None = None
    case_name = args.inference_case if args.inference_case != "iah_scale_code" else "iah_scale_code"
    if args.inference_case == "iah_scale_code":
        summary = attach_scalepath_iah_scale_code(
            model,
            hadamard_block=args.hadamard_block,
            group_size=args.group_size,
            act_bits=args.act_bits,
            weight_bits=args.weight_bits,
            scale_code_bits=args.scale_code_bits,
            compute_dtype=dtype,
        )
        method_summary = {
            "case": summary.case,
            "target_scope": summary.target_scope,
            "module_count": summary.module_count,
            "per_op": summary.per_op,
            "hadamard_block": summary.hadamard_block,
            "group_size": summary.group_size,
            "act_bits": summary.act_bits,
            "weight_bits": summary.weight_bits,
            "scale_code_bits": summary.scale_code_bits,
            "payload_format": summary.payload_format,
        }
        model.eval()
        print(f"[S11-method:{model_name}] attached {method_summary}", flush=True)

    summary_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    tasks = [part.strip() for part in args.tasks.split(",") if part.strip()]
    task_paths = {
        "arc_challenge": args.arc_challenge_path,
        "piqa": args.piqa_path,
        "openbookqa": args.openbookqa_path,
        "hellaswag": args.hellaswag_path,
        "winogrande": args.winogrande_path,
    }
    for task in tasks:
        if task == "wikitext2":
            metrics = evaluate_wikitext(
                model=model,
                tokenizer=tokenizer,
                path=args.wikitext_path,
                device=device,
                block_size=args.wikitext_block_size,
                stride=args.wikitext_stride,
                max_tokens=args.wikitext_max_tokens,
            )
            summary_rows.append(
                {
                    "model": model_name,
                    "case": case_name,
                    "dataset": str(args.wikitext_path),
                    "task": "wikitext2",
                    "samples": metrics["samples"],
                    "records_complete": metrics["records_complete"],
                    "ppl": metrics["ppl"],
                    "avg_nll": metrics["avg_nll"],
                    "token_accuracy": metrics["token_accuracy"],
                    "mcqa_accuracy": "",
                    "finite": metrics["finite"],
                    "delta_ppl_vs_raw_fp_scale": "",
                    "delta_nll_vs_raw_fp_scale": "",
                    "status": metrics["status"],
                    "source_artifact": str(output_dir / "quality_smoke_by_model.csv"),
                    "num_tokens": metrics["num_tokens"],
                    "elapsed_sec": metrics["elapsed_sec"],
                    "seed": args.seed,
                    "deterministic": args.deterministic,
                    "allow_tf32": args.allow_tf32,
                    "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                    "method_summary_json": json.dumps(method_summary, ensure_ascii=False) if method_summary else "",
                }
            )
            print(f"[S11-E:{model_name}] wikitext2 ppl={metrics['ppl']:.4f} token_acc={metrics['token_accuracy']:.4f}", flush=True)
            continue
        row_limit = None if args.max_mcqa_samples <= 0 else args.max_mcqa_samples
        rows = read_jsonl(task_paths[task], row_limit)
        samples, invalid = build_mcqa_samples(task, rows)
        invalid_rows.extend({"model": model_name, **row} for row in invalid)
        metrics, records = evaluate_mcqa(
            model=model,
            tokenizer=tokenizer,
            task=task,
            samples=samples,
            device=device,
            batch_size=args.mcqa_batch_size,
            rank_metric=args.rank_metric,
            max_length=args.max_length,
        )
        append_jsonl(records_path, [{"model": model_name, **row} for row in records])
        summary_rows.append(
            {
                "model": model_name,
                "case": case_name,
                "dataset": str(task_paths[task]),
                "task": task,
                "samples": metrics["samples"],
                "records_complete": metrics["records_complete"],
                "ppl": "",
                "avg_nll": "",
                "token_accuracy": "",
                "mcqa_accuracy": metrics["mcqa_accuracy"],
                "accuracy_score_sum": metrics["accuracy_score_sum"],
                "accuracy_score_mean": metrics["accuracy_score_mean"],
                "accuracy_score_char_norm": metrics["accuracy_score_char_norm"],
                "rank_metric": metrics["rank_metric"],
                "finite": metrics["finite"],
                "delta_ppl_vs_raw_fp_scale": "",
                "delta_nll_vs_raw_fp_scale": "",
                "status": metrics["status"],
                "source_artifact": str(records_path),
                "num_tokens": "",
                "elapsed_sec": metrics["elapsed_sec"],
                "seed": args.seed,
                "deterministic": args.deterministic,
                "allow_tf32": args.allow_tf32,
                "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                "method_summary_json": json.dumps(method_summary, ensure_ascii=False) if method_summary else "",
            }
        )
        print(f"[S11-E:{model_name}] {task} acc={metrics['mcqa_accuracy']:.4f}", flush=True)

    write_csv(output_dir / "quality_smoke_by_model.csv", summary_rows)
    write_csv(output_dir / "quality_smoke_invalid_rows.csv", invalid_rows)
    manifest = {
        "model": model_name,
        "model_path": str(args.model_path),
        "output_dir": str(output_dir),
        "tasks": tasks,
        "inference_case": args.inference_case,
        "method_summary": method_summary,
        "reproducibility": reproducibility,
        "rows": len(summary_rows),
        "invalid_rows": len(invalid_rows),
        "all_finite": all(str(row.get("finite")).lower() == "true" or row.get("finite") is True for row in summary_rows),
        "started_at": datetime.fromtimestamp(started).isoformat(),
        "finished_at": datetime.now().isoformat(),
        "elapsed_sec": time.time() - started,
        "status": "complete" if summary_rows else "no_rows",
    }
    write_json(output_dir / "quality_smoke_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
