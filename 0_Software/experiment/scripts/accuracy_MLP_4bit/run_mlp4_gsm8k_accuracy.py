#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


ARCHIVE_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
_FALLBACK_PROJECT_ROOT = Path(__file__).resolve().parents[5] / "fpga_llm_project"
PROJECT_ROOT = Path(os.environ.get("FPGA_LLM_PROJECT_ROOT", _FALLBACK_PROJECT_ROOT)).expanduser().resolve()
SCALE_CODE_DIR = ARCHIVE_SCRIPTS_DIR / "scale_code_linear"
if str(SCALE_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(SCALE_CODE_DIR))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from mlp4_method_inference import (  # noqa: E402
    attach_scalepath_iah_fp16_scale_mlp_w4,
    attach_scalepath_iah_fp32_scale_mlp_w4,
    attach_scalepath_iah_scale_code_mlp_w4,
)
from run_s11_cross_model_gsm8k_accuracy import (  # noqa: E402
    DEFAULT_DATASET,
    build_prompt,
    completed_existing_run,
    configure_reproducibility,
    dtype_from_name,
    extract_answer,
    read_csv,
    read_jsonl,
    safe_decode_response,
    write_csv,
    write_json,
)


DEFAULT_OUT = ARCHIVE_ROOT / "results" / "_rerun" / "final_scalecode_gsm8k_first300"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GSM8K accuracy for ScalaPath iah_scale_code with only MLP folded weights quantized to 4 bits."
    )
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
    parser.add_argument("--max_new_tokens", type=int, default=512)
    parser.add_argument("--generation_batch_size", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--prompt_style",
        choices=["default", "fair", "gsm8k_cot_standard", "chat_fewshot_cot", "mistral_fewshot_cot"],
        default="fair",
    )
    parser.add_argument("--disable_thinking", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--use_chat_template", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--hadamard_block", type=int, default=32)
    parser.add_argument("--group_size", type=int, default=32)
    parser.add_argument("--act_bits", type=int, default=8)
    parser.add_argument("--attention_weight_bits", type=int, default=8)
    parser.add_argument("--mlp_weight_bits", type=int, default=4)
    parser.add_argument("--scale_code_bits", type=int, default=8)
    parser.add_argument("--scale_format", choices=["scale_code", "fp16", "fp32"], default="scale_code")
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
    mlp_suffix = f"mlp_w{int(args.mlp_weight_bits)}"
    scale_cases = {
        "scale_code": f"iah_scale_code_{mlp_suffix}",
        "fp16": f"iah_fp16_scale_{mlp_suffix}",
        "fp32": f"iah_fp32_scale_{mlp_suffix}",
    }
    case_name = scale_cases[args.scale_format]
    model_suffix = scale_cases[args.scale_format]
    model_name = args.model_name or f"{args.model_path.name}__{model_suffix}"
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
        print(f"[MLP4-GSM8K:{model_name}] existing complete run; skip model load", flush=True)
        return
    lock_handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    if args.resume and completed_existing_run(
        manifest_path=manifest_path,
        records_path=records_path,
        sample_start=sample_start,
        sample_end=sample_end,
    ):
        print(f"[MLP4-GSM8K:{model_name}] existing complete run after lock; skip model load", flush=True)
        return

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
    if args.generation_batch_size > 1:
        tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        torch_dtype=dtype,
        local_files_only=args.local_files_only,
        trust_remote_code=args.trust_remote_code,
        attn_implementation=args.attn_implementation,
    ).to(device)
    model.eval()
    if args.scale_format == "fp16":
        method_summary = summary_to_dict(
            attach_scalepath_iah_fp16_scale_mlp_w4(
                model,
                hadamard_block=args.hadamard_block,
                group_size=args.group_size,
                act_bits=args.act_bits,
                attention_weight_bits=args.attention_weight_bits,
                mlp_weight_bits=args.mlp_weight_bits,
                compute_dtype=dtype,
            )
        )
    elif args.scale_format == "fp32":
        method_summary = summary_to_dict(
            attach_scalepath_iah_fp32_scale_mlp_w4(
                model,
                hadamard_block=args.hadamard_block,
                group_size=args.group_size,
                act_bits=args.act_bits,
                attention_weight_bits=args.attention_weight_bits,
                mlp_weight_bits=args.mlp_weight_bits,
                compute_dtype=dtype,
            )
        )
    else:
        method_summary = summary_to_dict(
            attach_scalepath_iah_scale_code_mlp_w4(
                model,
                hadamard_block=args.hadamard_block,
                group_size=args.group_size,
                act_bits=args.act_bits,
                attention_weight_bits=args.attention_weight_bits,
                mlp_weight_bits=args.mlp_weight_bits,
                scale_code_bits=args.scale_code_bits,
                compute_dtype=dtype,
            )
        )
    model.eval()
    print(f"[MLP4-GSM8K:{model_name}] attached {method_summary}", flush=True)

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
            f"[MLP4-GSM8K:{model_name}] resume {len(records)}/{len(indexed_rows)} "
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
                    "case": case_name,
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
                    f"[MLP4-GSM8K:{model_name}] {completed}/{len(indexed_rows)} "
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
            write_json(
                out_dir / f"{args.output_prefix}_progress.json",
                {
                    "model": model_name,
                    "case": case_name,
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
                },
            )

    write_csv(records_path, records)
    metrics = {
        "model": model_name,
        "case": case_name,
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
        "scale_format": args.scale_format,
        "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
        "final_marker_rate": sum(int(record.get("has_final_marker", 0)) for record in records) / max(1, len(records)),
        "avg_response_chars": sum(int(record.get("response_chars", 0)) for record in records) / max(1, len(records)),
        "decode_error_count": sum(1 for record in records if record.get("decode_error")),
        "finite": finite,
        "status": "pass" if finite and len(records) == len(indexed_rows) else "inspect",
        "started_at": datetime.fromtimestamp(started).isoformat(),
        "finished_at": datetime.now().isoformat(),
        "elapsed_sec": time.time() - started,
        "method_summary_json": json.dumps(method_summary, ensure_ascii=False),
        "method_summary": method_summary,
        "reproducibility": reproducibility,
    }
    write_json(manifest_path, metrics)
    write_csv(out_dir / f"{args.output_prefix}_summary.csv", [metrics])
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
