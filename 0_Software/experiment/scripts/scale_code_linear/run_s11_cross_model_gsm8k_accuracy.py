#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import math
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from scalepath4_method_inference import attach_scalepath_iah_scale_code


ARCHIVE_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PROJECT_ROOT = Path(__file__).resolve().parents[5] / "fpga_llm_project"
PROJECT_ROOT = Path(os.environ.get("FPGA_LLM_PROJECT_ROOT", _FALLBACK_PROJECT_ROOT)).expanduser().resolve()
DEFAULT_DATASET = PROJECT_ROOT / "data" / "gsm8k_openai_main_raw" / "test_first300.jsonl"
DEFAULT_OUT = (
    ARCHIVE_ROOT
    / "results"
    / "_rerun"
    / "scalecode_a8w8_gsm8k_first300"
)


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


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if limit is not None and len(rows) >= limit:
                break
            if line.strip():
                rows.append(json.loads(line))
    return rows


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


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def completed_existing_run(
    *,
    manifest_path: Path,
    records_path: Path,
    sample_start: int,
    sample_end: int,
) -> bool:
    if not manifest_path.exists() or not records_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not bool(manifest.get("records_complete")):
        return False
    if int(manifest.get("sample_start", -1)) != sample_start:
        return False
    if int(manifest.get("sample_end", -1)) != sample_end:
        return False
    records = [
        record
        for record in read_csv(records_path)
        if sample_start <= int(record.get("sample_index", -1)) < sample_end
    ]
    if len(records) != sample_end - sample_start:
        return False
    observed = sorted(int(record.get("sample_index", -1)) for record in records)
    return observed == list(range(sample_start, sample_end))


def normalize_number(text: str) -> str:
    text = text.replace(",", "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def extract_answer(text: str) -> str:
    patterns = [
        r"####\s*([-+]?\d[\d,]*(?:\.\d+)?)",
        r"\\boxed\{\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*\}",
        r"<numeric_answer>\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*</numeric_answer>",
        r"final answer\s*[:=]\s*([-+]?\d[\d,]*(?:\.\d+)?)",
        r"final answer is\s*([-+]?\d[\d,]*(?:\.\d+)?)",
        r"answer\s*[:=]\s*([-+]?\d[\d,]*(?:\.\d+)?)",
        r"answer is\s*([-+]?\d[\d,]*(?:\.\d+)?)",
    ]
    for pattern in patterns:
        found = re.findall(pattern, text, flags=re.IGNORECASE)
        if found:
            return normalize_number(found[-1])
    nums = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    return normalize_number(nums[-1]) if nums else ""


def token_ids_to_list(token_ids: Any) -> list[int]:
    if isinstance(token_ids, torch.Tensor):
        return [int(item) for item in token_ids.detach().cpu().view(-1).tolist()]
    if hasattr(token_ids, "tolist"):
        return [int(item) for item in token_ids.tolist()]
    return [int(item) for item in token_ids]


def safe_decode_response(tokenizer: Any, token_ids: Any) -> tuple[str, str, int]:
    ids = token_ids_to_list(token_ids)
    try:
        return tokenizer.decode(ids, skip_special_tokens=True), "", 0
    except (OverflowError, ValueError) as exc:
        invalid: list[int] = []
        upper = (1 << 32) - 1
        for token_id in ids:
            if token_id < 0 or token_id > upper:
                invalid.append(token_id)
        preview = ",".join(str(item) for item in invalid[:8])
        error = f"{type(exc).__name__}: {exc}"
        if invalid:
            error = f"{error}; invalid_token_preview={preview}"
        return "[DECODE_ERROR]", error, len(invalid)


def gsm8k_fewshot_examples() -> list[tuple[str, str]]:
    return [
        (
            "There are 15 trees in the grove. Grove workers will plant trees in the grove today. "
            "After they are done, there will be 21 trees. How many trees did the grove workers plant today?",
            "There are 15 trees originally. After planting, there are 21 trees. "
            "So the workers planted 21 - 15 = 6 trees.\n#### 6",
        ),
        (
            "If there are 3 cars in the parking lot and 2 more cars arrive, how many cars are in the parking lot?",
            "There are 3 cars originally. 2 more cars arrive, so 3 + 2 = 5 cars.\n#### 5",
        ),
        (
            "Leah had 32 chocolates and her sister had 42. If they ate 35, how many pieces do they have left in total?",
            "Together they had 32 + 42 = 74 chocolates. After eating 35, they have 74 - 35 = 39 left.\n#### 39",
        ),
        (
            "Jason had 20 lollipops. He gave Denny some lollipops. Now Jason has 12 lollipops. "
            "How many lollipops did Jason give to Denny?",
            "Jason started with 20 and ended with 12. He gave away 20 - 12 = 8 lollipops.\n#### 8",
        ),
    ]


def build_fewshot_block() -> str:
    return "\n\n".join(f"Question:\n{q}\nAnswer:\n{a}" for q, a in gsm8k_fewshot_examples())


def build_prompt(
    tokenizer: Any,
    question: str,
    *,
    prompt_style: str,
    disable_thinking: bool,
    use_chat_template: bool,
) -> str:
    if prompt_style == "gsm8k_cot_standard":
        parts = [f"Q: {q}\nA: {a}" for q, a in gsm8k_fewshot_examples()]
        parts.append(f"Q: {question.strip()}\nA: Let's think step by step.")
        return "\n\n".join(parts)

    if prompt_style in {"chat_fewshot_cot", "mistral_fewshot_cot"}:
        system = (
            "You are a careful GSM8K math solver. Follow the examples, solve briefly, "
            "and end with exactly one final line: #### <numeric_answer>. "
            "Do not put any other number after that final line."
        )
        user = (
            "Use the same format as the examples.\n\n"
            f"{build_fewshot_block()}\n\n"
            f"Question:\n{question.strip()}\n"
            "Answer:"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if use_chat_template and hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            kwargs: dict[str, Any] = {}
            if disable_thinking:
                kwargs["enable_thinking"] = False
            try:
                return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)
            except TypeError:
                return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return f"{system}\n\n{user}"

    if prompt_style == "fair":
        system = (
            "You are a careful GSM8K math solver. Solve briefly. "
            "End with exactly one final line: #### <numeric_answer>. "
            "Do not put any other number after that final line."
        )
        user = f"{question}\n\nReturn the final answer on the last line as: #### <numeric_answer>"
    else:
        system = "You are a careful math solver. Give concise reasoning and end with exactly one line: #### <numeric_answer>"
        user = f"{question}\n\nEnd with exactly one final line as: #### <numeric_answer>"
    messages = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": user,
        },
    ]
    if use_chat_template and hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        kwargs: dict[str, Any] = {}
        if disable_thinking:
            kwargs["enable_thinking"] = False
        try:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return (
        f"{system}\n\n"
        f"Question: {question}\nAnswer:"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="S11-E GSM8K first300 generation accuracy for cross-model portability.")
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--model_name", default="")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--attn_implementation", choices=["eager", "sdpa"], default="eager")
    parser.add_argument("--local_files_only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trust_remote_code", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max_samples", type=int, default=300)
    parser.add_argument("--sample_start", type=int, default=0)
    parser.add_argument("--sample_end", type=int, default=None)
    parser.add_argument("--max_input_tokens", type=int, default=1536)
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--generation_batch_size", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--prompt_style",
        choices=["default", "fair", "gsm8k_cot_standard", "chat_fewshot_cot", "mistral_fewshot_cot"],
        default="default",
    )
    parser.add_argument("--disable_thinking", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--use_chat_template", action=argparse.BooleanOptionalAction, default=True)
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
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--save_interval", type=int, default=5)
    parser.add_argument("--output_prefix", default="gsm8k_first300")
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
    out_dir = args.output_dir / model_name
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_all = read_jsonl(args.dataset, args.max_samples)
    sample_start = max(0, args.sample_start)
    sample_end = len(rows_all) if args.sample_end is None else min(args.sample_end, len(rows_all))
    if sample_start >= sample_end:
        raise ValueError(f"empty sample range: start={sample_start}, end={sample_end}, total={len(rows_all)}")
    indexed_rows = list(enumerate(rows_all[sample_start:sample_end], start=sample_start))
    records_path = out_dir / f"{args.output_prefix}_records.csv"
    manifest_path = out_dir / f"{args.output_prefix}_manifest.json"
    lock_path = out_dir / f".{args.output_prefix}.lock"
    if args.resume and completed_existing_run(
        manifest_path=manifest_path,
        records_path=records_path,
        sample_start=sample_start,
        sample_end=sample_end,
    ):
        print(f"[S11-E:GSM8K:{model_name}] existing complete run; skip model load", flush=True)
        return
    lock_handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    if args.resume and completed_existing_run(
        manifest_path=manifest_path,
        records_path=records_path,
        sample_start=sample_start,
        sample_end=sample_end,
    ):
        print(f"[S11-E:GSM8K:{model_name}] existing complete run after lock; skip model load", flush=True)
        return
    device = torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.set_device(device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    if args.generation_batch_size > 1:
        tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        torch_dtype=dtype_from_name(args.dtype),
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
        attn_implementation=args.attn_implementation,
    ).to(device)
    model.eval()
    method_summary: dict[str, Any] | None = None
    if args.inference_case == "iah_scale_code":
        summary = attach_scalepath_iah_scale_code(
            model,
            hadamard_block=args.hadamard_block,
            group_size=args.group_size,
            act_bits=args.act_bits,
            weight_bits=args.weight_bits,
            scale_code_bits=args.scale_code_bits,
            compute_dtype=dtype_from_name(args.dtype),
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
        print(f"[S11-method:GSM8K:{model_name}] attached {method_summary}", flush=True)
    loaded_records: list[dict[str, Any]] = read_csv(records_path) if args.resume else []
    records = [
        record
        for expected, record in enumerate(
            sorted(
                (record for record in loaded_records if sample_start <= int(record.get("sample_index", -1)) < sample_end),
                key=lambda item: int(item.get("sample_index", -1)),
            ),
            start=sample_start,
        )
        if int(record.get("sample_index", -1)) == expected
    ]
    correct = sum(int(record.get("correct", 0)) for record in records)
    finite = all(bool(record.get("prediction") or record.get("response")) for record in records)
    if records:
        print(
            f"[S11-E:GSM8K:{model_name}] resume {len(records)}/{len(indexed_rows)} "
            f"range={sample_start}:{sample_end} acc={correct/max(1, len(records)):.4f}",
            flush=True,
        )
    pending_rows = indexed_rows[len(records) :]
    generation_batch_size = max(1, int(args.generation_batch_size))
    last_saved = len(records)
    for batch_start in range(0, len(pending_rows), generation_batch_size):
        batch_rows = pending_rows[batch_start : batch_start + generation_batch_size]
        questions = [
            str(row.get("instruction") or row.get("question") or row.get("input") or "")
            for _, row in batch_rows
        ]
        golds = [extract_answer(str(row.get("output") or row.get("answer") or "")) for _, row in batch_rows]
        prompts = [
            build_prompt(
                tokenizer,
                question,
                prompt_style=args.prompt_style,
                disable_thinking=args.disable_thinking,
                use_chat_template=args.use_chat_template,
            )
            for question in questions
        ]
        enc = tokenizer(
            prompts,
            return_tensors="pt",
            padding=len(prompts) > 1,
            truncation=True,
            max_length=args.max_input_tokens,
        ).to(device)
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": args.max_new_tokens,
            "do_sample": args.temperature > 0,
            "temperature": args.temperature if args.temperature > 0 else None,
            "pad_token_id": tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        gen_kwargs = {key: value for key, value in gen_kwargs.items() if value is not None}
        with torch.no_grad():
            output = model.generate(**enc, **gen_kwargs)
        prompt_width = enc["input_ids"].shape[1]
        for (idx, _row), question, gold, output_ids in zip(batch_rows, questions, golds, output):
            response_ids = output_ids[prompt_width:]
            response, decode_error, invalid_token_count = safe_decode_response(tokenizer, response_ids)
            pred = extract_answer(response)
            is_correct = pred != "" and pred == gold
            has_final_marker = "####" in response
            correct += int(is_correct)
            finite = finite and bool(decode_error or pred != "" or response.strip())
            records.append(
                {
                    "model": model_name,
                    "case": args.inference_case,
                    "prompt_style": args.prompt_style,
                    "disable_thinking": int(args.disable_thinking),
                    "use_chat_template": int(args.use_chat_template),
                    "sample_index": idx,
                    "question": question,
                    "gold": gold,
                    "prediction": pred,
                    "correct": int(is_correct),
                    "has_final_marker": int(has_final_marker),
                    "response_chars": len(response),
                    "decode_error": decode_error,
                    "decode_invalid_token_count": invalid_token_count,
                    "response": response,
                }
            )
            completed = len(records)
            if completed % 25 == 0 or (idx + 1) == sample_end:
                print(
                    f"[S11-E:GSM8K:{model_name}] {completed}/{len(indexed_rows)} "
                    f"range={sample_start}:{sample_end} acc={correct/max(1, completed):.4f}",
                    flush=True,
                )
        completed = len(records)
        should_save = completed == len(indexed_rows)
        if args.save_interval > 0 and completed - last_saved >= args.save_interval:
            should_save = True
        if should_save:
            write_csv(records_path, records)
            last_saved = completed
            partial_metrics = {
                "model": model_name,
                "case": args.inference_case,
                "dataset": str(args.dataset),
                "sample_start": sample_start,
                "sample_end": sample_end,
                "samples_done": len(records),
                "samples_target": len(indexed_rows),
                "gsm8k_accuracy_so_far": correct / max(1, len(records)),
                "prompt_style": args.prompt_style,
                "disable_thinking": args.disable_thinking,
                "use_chat_template": args.use_chat_template,
                "max_new_tokens": args.max_new_tokens,
                "generation_batch_size": generation_batch_size,
                "seed": args.seed,
                "deterministic": args.deterministic,
                "decode_error_count": sum(1 for record in records if record.get("decode_error")),
                "finite": finite,
                "status": "running" if len(records) < len(indexed_rows) else "complete",
                "updated_at": datetime.now().isoformat(),
            }
            write_json(out_dir / f"{args.output_prefix}_progress.json", partial_metrics)
    write_csv(records_path, records)
    metrics = {
        "model": model_name,
        "case": args.inference_case,
        "dataset": str(args.dataset),
        "sample_start": sample_start,
        "sample_end": sample_end,
        "samples": len(indexed_rows),
        "records_complete": len(records) == len(indexed_rows),
        "gsm8k_accuracy": correct / max(1, len(indexed_rows)),
        "prompt_style": args.prompt_style,
        "disable_thinking": args.disable_thinking,
        "use_chat_template": args.use_chat_template,
        "max_input_tokens": args.max_input_tokens,
        "max_new_tokens": args.max_new_tokens,
        "generation_batch_size": generation_batch_size,
        "seed": args.seed,
        "deterministic": args.deterministic,
        "allow_tf32": args.allow_tf32,
        "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
        "final_marker_rate": sum(int(record.get("has_final_marker", 0)) for record in records) / max(1, len(records)),
        "avg_response_chars": sum(int(record.get("response_chars", 0)) for record in records) / max(1, len(records)),
        "decode_error_count": sum(1 for record in records if record.get("decode_error")),
        "finite": finite,
        "status": "pass" if finite and len(records) == len(indexed_rows) else "inspect",
        "started_at": datetime.fromtimestamp(started).isoformat(),
        "finished_at": datetime.now().isoformat(),
        "elapsed_sec": time.time() - started,
        "method_summary_json": json.dumps(method_summary, ensure_ascii=False) if method_summary else "",
        "reproducibility": reproducibility,
    }
    write_json(manifest_path, metrics)
    write_csv(out_dir / f"{args.output_prefix}_summary.csv", [metrics])
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
