#!/usr/bin/env python3
"""GyRot-aligned full-split zero-shot MCQA evaluation.

This runner is intentionally separate from the older smoke-test runners. It
uses the benchmark set and reporting style used by the GyRot paper:

  PIQA, ARC-Easy, ARC-Challenge, BoolQ, HellaSwag, WinoGrande

The runner records all three local scoring variants, but the primary metric is
task-specific: acc_norm-like score_char_norm for PIQA/ARC/HellaSwag and raw
score_sum for BoolQ/WinoGrande.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


ARCHIVE_ROOT = Path(__file__).resolve().parents[4]
ARCHIVE_SCRIPTS_DIR = Path(__file__).resolve().parents[2]
_FALLBACK_PROJECT_ROOT = Path(__file__).resolve().parents[6] / "fpga_llm_project"
PROJECT_ROOT = Path(os.environ.get("FPGA_LLM_PROJECT_ROOT", _FALLBACK_PROJECT_ROOT)).expanduser().resolve()
SCRIPT_DIR = Path(__file__).resolve().parent
MLP4_DIR = ARCHIVE_SCRIPTS_DIR / "accuracy_MLP_4bit"
SCALE_CODE_DIR = ARCHIVE_SCRIPTS_DIR / "scale_code_linear"
for path in (SCRIPT_DIR, MLP4_DIR, SCALE_CODE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mlp4_method_inference import (  # noqa: E402
    attach_scalepath_iah_fp16_scale_mlp_w4,
    attach_scalepath_iah_fp32_scale_mlp_w4,
    attach_scalepath_iah_scale_code_mlp_w4,
)
from run_s11_cross_model_quality_accuracy import (  # noqa: E402
    WIKITEXT_PATH,
    append_jsonl,
    configure_reproducibility,
    dtype_from_name,
    evaluate_mcqa,
    evaluate_wikitext,
    letter_to_index,
    read_jsonl,
    write_csv,
    write_json,
)


DEFAULT_OUT = (
    ARCHIVE_ROOT
    / "results"
    / "_rerun"
    / "final_scalecode_gyrot_aligned_accuracy"
)

TASK_PATHS = {
    "arc_easy": PROJECT_ROOT / "data" / "arc_easy" / "validation_full.jsonl",
    "arc_challenge": PROJECT_ROOT / "data" / "arc_challenge" / "validation_full.jsonl",
    "openbookqa": PROJECT_ROOT / "data" / "openbookqa" / "validation_full.jsonl",
    "piqa": PROJECT_ROOT / "data" / "piqa" / "validation_full.jsonl",
    "boolq": PROJECT_ROOT / "data" / "boolq" / "validation_full.jsonl",
    "hellaswag": PROJECT_ROOT / "data" / "hellaswag" / "hellaswag_val.jsonl",
    "winogrande": PROJECT_ROOT
    / "data"
    / "winogrande"
    / "winogrande_1.1"
    / "winogrande_1.1"
    / "dev.jsonl",
}

TASK_LABELS = {
    "arc_easy": "ARC-e",
    "arc_challenge": "ARC-c",
    "openbookqa": "OpenBookQA",
    "piqa": "PIQA",
    "boolq": "BoolQ",
    "hellaswag": "HellaSwag",
    "winogrande": "WinoGrande",
}

PRIMARY_METRIC = {
    "arc_easy": "score_char_norm",
    "arc_challenge": "score_char_norm",
    "openbookqa": "score_char_norm",
    "piqa": "score_char_norm",
    "boolq": "score_sum",
    "hellaswag": "score_char_norm",
    "winogrande": "score_sum",
}

DATASET_LOADERS = {
    "arc_easy": ("allenai/ai2_arc", "ARC-Easy", "validation"),
    "arc_challenge": ("allenai/ai2_arc", "ARC-Challenge", "validation"),
    "openbookqa": ("allenai/openbookqa", "main", "validation"),
    "piqa": ("piqa", None, "validation"),
    "boolq": ("google/boolq", None, "validation"),
    "hellaswag": ("hellaswag", None, "validation"),
    "winogrande": ("winogrande", "winogrande_xl", "validation"),
}


def summary_to_dict(summary: Any) -> dict[str, Any]:
    return {
        "case": summary.case,
        "target_scope": summary.target_scope,
        "module_count": summary.module_count,
        "per_op": summary.per_op,
        "per_op_weight_bits": summary.per_op_weight_bits,
        "hadamard_block": summary.hadamard_block,
        "group_size": summary.group_size,
        "act_bits": summary.act_bits,
        "attention_weight_bits": summary.attention_weight_bits,
        "mlp_weight_bits": summary.mlp_weight_bits,
        "scale_code_bits": summary.scale_code_bits,
        "payload_format": summary.payload_format,
        "invariant": summary.invariant,
    }


def load_hf_dataset_rows(task: str) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "datasets is required to materialize missing GyRot-aligned data. "
            "Run with the zhouwenjun conda env or provide local JSONL paths."
        ) from exc

    name, config, split = DATASET_LOADERS[task]
    kwargs = {"split": split}
    ds = load_dataset(name, config, **kwargs) if config else load_dataset(name, **kwargs)
    return [dict(row) for row in ds]


def materialize_rows(task: str, path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for idx, row in enumerate(rows):
            if task == "winogrande" and "answer" not in row and "label" in row:
                row = dict(row)
                row["answer"] = str(int(row["label"]) + 1)
            row.setdefault("id", f"{task}_{idx}")
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_task_rows(
    *,
    task: str,
    path: Path,
    limit: int | None,
    allow_dataset_download: bool,
    materialize_missing_data: bool,
) -> tuple[list[dict[str, Any]], str]:
    if path.exists():
        return read_jsonl(path, limit), str(path)
    if not allow_dataset_download:
        raise FileNotFoundError(
            f"missing dataset for {task}: {path}. Re-run with --allow_dataset_download "
            "or pass the task path explicitly."
        )
    rows = load_hf_dataset_rows(task)
    if materialize_missing_data:
        materialize_rows(task, path, rows)
        source = f"{path} (materialized from HuggingFace:{DATASET_LOADERS[task]})"
    else:
        source = f"HuggingFace:{DATASET_LOADERS[task]}"
    if limit is not None:
        rows = rows[:limit]
    return rows, source


def boolq_answer_index(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"true", "yes", "1"} else 0
    return int(bool(value))


def build_gyrot_samples(task: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        try:
            if task in {"arc_easy", "arc_challenge"}:
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
                question = row["question"]
                raw_choices = question["choices"]
                if isinstance(raw_choices, list):
                    labels = [str(choice["label"]) for choice in raw_choices]
                    choices = [str(choice["text"]) for choice in raw_choices]
                else:
                    labels = [str(x) for x in raw_choices["label"]]
                    choices = [str(x) for x in raw_choices["text"]]
                samples.append(
                    {
                        "row_id": row.get("id", idx),
                        "prefixes": [f"Question: {question['stem']}\nAnswer:" for _ in choices],
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
            elif task == "boolq":
                question = str(row["question"]).strip()
                if question and not question.endswith("?"):
                    question += "?"
                passage = str(row["passage"]).strip()
                prefix = f"{passage}\nQuestion: {question}\nAnswer:"
                samples.append(
                    {
                        "row_id": row.get("id", idx),
                        "prefixes": [prefix, prefix],
                        "suffixes": [" no", " yes"],
                        "gold_index": boolq_answer_index(row["answer"]),
                    }
                )
            elif task == "hellaswag":
                endings = [str(x) for x in row["endings"]]
                ctx = str(row.get("ctx") or (str(row.get("ctx_a", "")) + " " + str(row.get("ctx_b", "")))).strip()
                samples.append(
                    {
                        "row_id": row.get("ind", row.get("id", idx)),
                        "prefixes": [ctx for _ in endings],
                        "suffixes": [" " + ending for ending in endings],
                        "gold_index": int(row["label"]),
                    }
                )
            elif task == "winogrande":
                sentence = str(row["sentence"])
                before, after = sentence.split("_", 1)
                choices = [str(row["option1"]), str(row["option2"])]
                answer = row.get("answer", row.get("label"))
                gold = int(answer) - 1 if str(answer) in {"1", "2"} else int(answer)
                samples.append(
                    {
                        "row_id": row.get("qID", row.get("id", idx)),
                        "prefixes": [before for _ in choices],
                        "suffixes": [choice + after for choice in choices],
                        "gold_index": gold,
                    }
                )
            else:
                raise ValueError(f"unsupported task: {task}")
        except Exception as exc:  # noqa: BLE001
            invalid.append({"task": task, "row_index": idx, "reason": repr(exc), "status": "invalid_input"})
    return samples, invalid


def default_case_name(args: argparse.Namespace) -> str:
    if args.method == "original":
        return f"original_{args.dtype.replace('bfloat16', 'bf16').replace('float16', 'fp16').replace('float32', 'fp32')}"
    payload = {"scale_code": "scalecode", "fp16": "fp16_scale", "fp32": "fp32_scale"}[args.scale_format]
    return f"mlp_w{args.mlp_weight_bits}_{payload}"


def default_method_label(args: argparse.Namespace, case_name: str) -> str:
    if args.method == "original":
        return {
            "bfloat16": "Full Precision BF16",
            "float16": "Full Precision FP16",
            "float32": "Full Precision FP32",
        }[args.dtype]
    return (
        f"ActivationW{args.act_bits}A{args.act_bits} "
        f"AttentionW{args.attention_weight_bits} MLPW{args.mlp_weight_bits} "
        f"{args.scale_format} payload"
    )


def attach_method(args: argparse.Namespace, model: Any, dtype: torch.dtype) -> dict[str, Any]:
    if args.method == "original":
        return {
            "case": default_case_name(args),
            "target_scope": "none",
            "module_count": 0,
            "invariant": "Original model; no quantized module wrapper attached.",
            "payload_format": "none",
        }
    common = dict(
        hadamard_block=args.hadamard_block,
        group_size=args.group_size,
        act_bits=args.act_bits,
        attention_weight_bits=args.attention_weight_bits,
        mlp_weight_bits=args.mlp_weight_bits,
        compute_dtype=dtype,
    )
    if args.scale_format == "fp16":
        return summary_to_dict(attach_scalepath_iah_fp16_scale_mlp_w4(model, **common))
    if args.scale_format == "fp32":
        return summary_to_dict(attach_scalepath_iah_fp32_scale_mlp_w4(model, **common))
    return summary_to_dict(
        attach_scalepath_iah_scale_code_mlp_w4(
            model,
            scale_code_bits=args.scale_code_bits,
            **common,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-split GyRot-aligned zero-shot MCQA.")
    parser.add_argument("--model_path", type=Path)
    parser.add_argument("--model_name", default="")
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--attn_implementation", choices=["eager", "sdpa"], default="eager")
    parser.add_argument("--local_files_only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trust_remote_code", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--tasks", default="piqa,arc_easy,arc_challenge,boolq,hellaswag,winogrande")
    parser.add_argument("--max_mcqa_samples", type=int, default=0, help="0 means full split.")
    parser.add_argument("--mcqa_batch_size", type=int, default=4)
    parser.add_argument("--rank_metric", choices=["auto", "score_sum", "score_mean", "score_char_norm"], default="auto")
    parser.add_argument("--max_length", type=int, default=1024)
    parser.add_argument("--arc_easy_path", type=Path, default=TASK_PATHS["arc_easy"])
    parser.add_argument("--arc_challenge_path", type=Path, default=TASK_PATHS["arc_challenge"])
    parser.add_argument("--openbookqa_path", type=Path, default=TASK_PATHS["openbookqa"])
    parser.add_argument("--piqa_path", type=Path, default=TASK_PATHS["piqa"])
    parser.add_argument("--boolq_path", type=Path, default=TASK_PATHS["boolq"])
    parser.add_argument("--hellaswag_path", type=Path, default=TASK_PATHS["hellaswag"])
    parser.add_argument("--winogrande_path", type=Path, default=TASK_PATHS["winogrande"])
    parser.add_argument("--allow_dataset_download", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--materialize_missing_data", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--prepare_data_only", action="store_true")
    parser.add_argument("--method", choices=["original", "mlp_quant"], default="original")
    parser.add_argument("--case_name", default="")
    parser.add_argument("--method_label", default="")
    parser.add_argument("--hadamard_block", type=int, default=32)
    parser.add_argument("--group_size", type=int, default=32)
    parser.add_argument("--act_bits", type=int, default=8)
    parser.add_argument("--attention_weight_bits", type=int, default=8)
    parser.add_argument("--mlp_weight_bits", type=int, default=4)
    parser.add_argument("--scale_code_bits", type=int, default=8)
    parser.add_argument("--scale_format", choices=["scale_code", "fp16", "fp32"], default="scale_code")
    parser.add_argument("--wikitext_path", type=Path, default=WIKITEXT_PATH)
    parser.add_argument("--include_wikitext", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--wikitext_block_size", type=int, default=1024)
    parser.add_argument("--wikitext_stride", type=int, default=1024)
    parser.add_argument("--wikitext_max_tokens", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--allow_tf32", action=argparse.BooleanOptionalAction, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    case_name = args.case_name or default_case_name(args)
    method_label = args.method_label or default_method_label(args, case_name)
    tasks = [part.strip() for part in args.tasks.split(",") if part.strip()]
    task_paths = {
        "arc_easy": args.arc_easy_path,
        "arc_challenge": args.arc_challenge_path,
        "openbookqa": args.openbookqa_path,
        "piqa": args.piqa_path,
        "boolq": args.boolq_path,
        "hellaswag": args.hellaswag_path,
        "winogrande": args.winogrande_path,
    }

    limit = None if args.max_mcqa_samples <= 0 else args.max_mcqa_samples
    data_manifest: list[dict[str, Any]] = []
    prepared_rows: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        if task not in TASK_PATHS:
            raise ValueError(f"unsupported GyRot-aligned task: {task}")
        rows, source = load_task_rows(
            task=task,
            path=task_paths[task],
            limit=limit,
            allow_dataset_download=args.allow_dataset_download,
            materialize_missing_data=args.materialize_missing_data,
        )
        prepared_rows[task] = rows
        data_manifest.append(
            {
                "task": task,
                "task_label": TASK_LABELS[task],
                "rows": len(rows),
                "source": source,
                "primary_metric": PRIMARY_METRIC[task],
            }
        )

    if args.prepare_data_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "gyrot_aligned_data_manifest.json", data_manifest)
        print(json.dumps({"prepared": data_manifest}, ensure_ascii=False, indent=2))
        return

    if args.model_path is None:
        raise ValueError("--model_path is required unless --prepare_data_only is set")

    reproducibility = configure_reproducibility(seed=args.seed, deterministic=args.deterministic, allow_tf32=args.allow_tf32)
    base_model_name = args.model_path.name
    model_name = args.model_name or f"{base_model_name}__{case_name}"
    output_dir = args.output_dir / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "gyrot_aligned_mcqa_records.jsonl"
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
    method_summary = attach_method(args, model, dtype)
    model.eval()

    summary_rows: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []
    for task in tasks:
        rows = prepared_rows[task]
        samples, invalid = build_gyrot_samples(task, rows)
        invalid_rows.extend({"model": model_name, "case": case_name, **row} for row in invalid)
        rank_metric = PRIMARY_METRIC[task] if args.rank_metric == "auto" else args.rank_metric
        metrics, records = evaluate_mcqa(
            model=model,
            tokenizer=tokenizer,
            task=task,
            samples=samples,
            device=device,
            batch_size=args.mcqa_batch_size,
            rank_metric=rank_metric,
            max_length=args.max_length,
        )
        append_jsonl(records_path, [{"model": model_name, "case": case_name, **row} for row in records])
        primary_accuracy = metrics[f"accuracy_{rank_metric}"]
        summary_rows.append(
            {
                "model": model_name,
                "base_model": base_model_name,
                "case": case_name,
                "method_label": method_label,
                "dataset": data_manifest[tasks.index(task)]["source"],
                "task": task,
                "task_label": TASK_LABELS[task],
                "samples": metrics["samples"],
                "records_complete": metrics["records_complete"],
                "primary_metric": rank_metric,
                "primary_accuracy": primary_accuracy,
                "mcqa_accuracy": metrics["mcqa_accuracy"],
                "accuracy_score_sum": metrics["accuracy_score_sum"],
                "accuracy_score_mean": metrics["accuracy_score_mean"],
                "accuracy_score_char_norm": metrics["accuracy_score_char_norm"],
                "finite": metrics["finite"],
                "status": metrics["status"],
                "source_artifact": str(output_dir / "gyrot_aligned_quality_by_model.csv"),
                "records_artifact": str(records_path),
                "elapsed_sec": metrics["elapsed_sec"],
                "seed": args.seed,
                "deterministic": args.deterministic,
                "allow_tf32": args.allow_tf32,
                "protocol": "gyrot_aligned_lm_eval_style_zero_shot_full_split",
                "prompt_style": "local_lm_eval_style_loglikelihood_mcqa",
                "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                "method_summary_json": json.dumps(method_summary, ensure_ascii=False),
            }
        )
        print(
            f"[GyRot-aligned:{model_name}] {task} {rank_metric}={primary_accuracy:.4f} "
            f"samples={metrics['samples']} status={metrics['status']}",
            flush=True,
        )

    if args.include_wikitext:
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
                "base_model": base_model_name,
                "case": case_name,
                "method_label": method_label,
                "dataset": str(args.wikitext_path),
                "task": "wikitext2",
                "task_label": "WikiText2",
                "samples": metrics["samples"],
                "records_complete": metrics["records_complete"],
                "ppl": metrics["ppl"],
                "avg_nll": metrics["avg_nll"],
                "token_accuracy": metrics["token_accuracy"],
                "finite": metrics["finite"],
                "status": metrics["status"],
                "source_artifact": str(output_dir / "gyrot_aligned_quality_by_model.csv"),
                "elapsed_sec": metrics["elapsed_sec"],
                "protocol": "wikitext2_optional_quality_guardrail",
                "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                "method_summary_json": json.dumps(method_summary, ensure_ascii=False),
            }
        )

    write_csv(output_dir / "gyrot_aligned_quality_by_model.csv", summary_rows)
    write_csv(output_dir / "gyrot_aligned_invalid_rows.csv", invalid_rows)
    write_json(
        output_dir / "gyrot_aligned_manifest.json",
        {
            "model_name": model_name,
            "base_model": base_model_name,
            "case": case_name,
            "method_label": method_label,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_sec": time.time() - started,
            "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
            "data_manifest": data_manifest,
            "method_summary": method_summary,
        },
    )


if __name__ == "__main__":
    main()
