#!/usr/bin/env python3

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
from run_s11_cross_model_quality_accuracy import (  # noqa: E402
    TASK_PATHS,
    WIKITEXT_PATH,
    append_jsonl,
    build_mcqa_samples,
    configure_reproducibility,
    dtype_from_name,
    evaluate_mcqa,
    evaluate_wikitext,
    read_jsonl,
    write_csv,
    write_json,
)


DEFAULT_OUT = ARCHIVE_ROOT / "results" / "_rerun" / "final_scalecode_quality_accuracy"


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
        description="Accuracy smoke for ScalaPath iah_scale_code with only MLP folded weights quantized to 4 bits."
    )
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--model_name", default="")
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUT)
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
    parser.add_argument("--hadamard_block", type=int, default=32)
    parser.add_argument("--group_size", type=int, default=32)
    parser.add_argument("--act_bits", type=int, default=8)
    parser.add_argument("--attention_weight_bits", type=int, default=8)
    parser.add_argument("--mlp_weight_bits", type=int, default=4)
    parser.add_argument("--scale_code_bits", type=int, default=8)
    parser.add_argument("--scale_format", choices=["scale_code", "fp16", "fp32"], default="scale_code")
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
    print(f"[MLP4-quality:{model_name}] attached {method_summary}", flush=True)

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
                    "status": metrics["status"],
                    "source_artifact": str(output_dir / "quality_smoke_by_model.csv"),
                    "num_tokens": metrics["num_tokens"],
                    "elapsed_sec": metrics["elapsed_sec"],
                    "seed": args.seed,
                    "deterministic": args.deterministic,
                    "allow_tf32": args.allow_tf32,
                    "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                    "method_summary_json": json.dumps(method_summary, ensure_ascii=False),
                }
            )
            print(f"[MLP4-quality:{model_name}] wikitext2 ppl={metrics['ppl']:.4f} token_acc={metrics['token_accuracy']:.4f}", flush=True)
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
        append_jsonl(records_path, [{"model": model_name, "case": case_name, **row} for row in records])
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
                "status": metrics["status"],
                "source_artifact": str(records_path),
                "num_tokens": "",
                "elapsed_sec": metrics["elapsed_sec"],
                "seed": args.seed,
                "deterministic": args.deterministic,
                "allow_tf32": args.allow_tf32,
                "reproducibility_json": json.dumps(reproducibility, ensure_ascii=False),
                "method_summary_json": json.dumps(method_summary, ensure_ascii=False),
            }
        )
        print(f"[MLP4-quality:{model_name}] {task} acc={metrics['mcqa_accuracy']:.4f}", flush=True)

    write_csv(output_dir / "quality_smoke_by_model.csv", summary_rows)
    write_csv(output_dir / "quality_smoke_invalid_rows.csv", invalid_rows)
    manifest = {
        "model": model_name,
        "model_path": str(args.model_path),
        "output_dir": str(output_dir),
        "case": case_name,
        "scale_format": args.scale_format,
        "tasks": tasks,
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
