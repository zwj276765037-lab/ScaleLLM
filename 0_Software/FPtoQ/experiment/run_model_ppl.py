#!/usr/bin/env python3
"""Model-level WikiText2 comparison for the activation frontend only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


THIS_DIR = Path(__file__).resolve().parent
ARCHIVE_ROOT = THIS_DIR.parents[1]
ARCHIVE_SCRIPTS = ARCHIVE_ROOT / "experiment" / "scripts"
SCALE_CODE_DIR = ARCHIVE_SCRIPTS / "scale_code_linear"
MLP4_DIR = ARCHIVE_SCRIPTS / "accuracy_MLP_4bit"
for path in (SCALE_CODE_DIR, MLP4_DIR, THIS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mlp4_method_inference import attach_scalepath_iah_scale_code_mlp_w4  # noqa: E402
from run_s11_cross_model_quality_accuracy import (  # noqa: E402
    configure_reproducibility,
    evaluate_wikitext,
)
from torch_frontend import attach_frontend_case, collect_rtl_audit  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["software", "pre_q_only", "rtl_exact"],
                        required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--wikitext", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"],
                        default="bfloat16")
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--stride", type=int, default=512)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260911)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    reproducibility = configure_reproducibility(
        seed=args.seed, deterministic=True, allow_tf32=False)
    device = torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.set_device(device)
    dtype = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[args.dtype]

    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=True,
        torch_dtype=dtype,
        attn_implementation="eager",
    ).to(device)
    model.eval()

    if args.case == "software":
        attached = attach_scalepath_iah_scale_code_mlp_w4(
            model,
            hadamard_block=32,
            group_size=32,
            act_bits=8,
            attention_weight_bits=8,
            mlp_weight_bits=4,
            scale_code_bits=8,
            compute_dtype=dtype,
        )
        method = {
            "case": "software",
            "module_count": attached.module_count,
            "per_op": attached.per_op,
            "activation_frontend": "archived software FP Hadamard32 + A8 ScaleCode",
            "weight_path": "archived folded ScaleCode W8 attention / W4 MLP",
        }
    else:
        method = attach_frontend_case(model, case=args.case, compute_dtype=dtype)
    model.eval()
    print(json.dumps(method, indent=2, ensure_ascii=False), flush=True)

    metrics = evaluate_wikitext(
        model=model,
        tokenizer=tokenizer,
        path=args.wikitext,
        device=device,
        block_size=args.block_size,
        stride=args.stride,
        max_tokens=args.max_tokens,
    )
    rtl_audit = collect_rtl_audit(model) if args.case == "rtl_exact" else None
    result = {
        "schema": "scalellm_fp_to_q_ppl_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "model": str(args.model.resolve()),
        "wikitext": str(args.wikitext.resolve()),
        "dtype": args.dtype,
        "device": str(device),
        "block_size": args.block_size,
        "stride": args.stride,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "method": method,
        "reproducibility": reproducibility,
        "metrics": metrics,
        "rtl_audit": rtl_audit,
        "elapsed_sec_total": time.time() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
