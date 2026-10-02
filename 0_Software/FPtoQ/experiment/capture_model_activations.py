#!/usr/bin/env python3
"""Capture bounded Group32 samples from real transformer linear inputs."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np


TARGET_OPS = {
    # q/k/v and gate/up consume the same tensor. Capture one representative
    # instead of counting identical Group32 values two or three times.
    "q_proj", "o_proj", "gate_proj", "down_proj", "gate_up_proj",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--calibration-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-prompts", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--groups-per-call", type=int, default=128)
    parser.add_argument("--max-groups-per-op", type=int, default=8192)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"],
                        default="bfloat16")
    parser.add_argument("--seed", type=int, default=20260911)
    return parser.parse_args()


def read_prompts(path: Path, limit: int) -> list[str]:
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            text = row.get("text")
            if isinstance(text, str) and text.strip():
                prompts.append(text)
            if len(prompts) >= limit:
                break
    if not prompts:
        raise ValueError(f"no non-empty text records in {path}")
    return prompts


def main() -> None:
    args = parse_args()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "capture requires PyTorch and Transformers; use the project conda Python"
        ) from exc

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    dtype = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[args.dtype]
    if device.type == "cuda":
        torch.cuda.set_device(device)

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

    captured: dict[str, list[np.ndarray]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    calls: dict[str, int] = defaultdict(int)
    module_counts: dict[str, int] = defaultdict(int)
    hooks = []

    def make_hook(module_name: str, op: str):
        def hook(_module: Any, inputs: tuple[Any, ...]) -> None:
            calls[op] += 1
            if counts[op] >= args.max_groups_per_op or not inputs:
                return
            tensor = inputs[0]
            if not torch.is_tensor(tensor) or tensor.numel() == 0:
                return
            width = tensor.shape[-1]
            main = (width // 32) * 32
            if main == 0:
                return
            groups = tensor[..., :main].detach().to(torch.float32).reshape(-1, 32)
            remaining = args.max_groups_per_op - counts[op]
            take = min(args.groups_per_call, remaining, groups.shape[0])
            if take <= 0:
                return
            if take == groups.shape[0]:
                chosen = groups
            else:
                # The phase offset changes per call and remains deterministic.
                phase = (calls[op] * 104729) % groups.shape[0]
                index = (torch.linspace(0, groups.shape[0] - 1, take,
                                        device=groups.device).long() + phase) % groups.shape[0]
                chosen = groups.index_select(0, index)
            captured[op].append(chosen.cpu().numpy())
            counts[op] += int(chosen.shape[0])
            module_counts[module_name] += int(chosen.shape[0])
        return hook

    for name, module in model.named_modules():
        op = name.rsplit(".", 1)[-1]
        if op in TARGET_OPS and isinstance(module, torch.nn.Linear):
            hooks.append(module.register_forward_pre_hook(make_hook(name, op)))

    prompts = read_prompts(args.calibration_jsonl, args.max_prompts)
    with torch.inference_mode():
        for index, prompt in enumerate(prompts, start=1):
            encoded = tokenizer(
                prompt, return_tensors="pt", truncation=True,
                max_length=args.max_length)
            encoded = {key: value.to(device) for key, value in encoded.items()}
            model(**encoded, use_cache=False)
            print(f"captured prompt {index}/{len(prompts)}", flush=True)

    for hook in hooks:
        hook.remove()

    groups_parts = []
    labels_parts = []
    for op in sorted(captured):
        values = np.concatenate(captured[op], axis=0)
        groups_parts.append(values)
        labels_parts.append(np.full(values.shape[0], op, dtype="U16"))
    if not groups_parts:
        raise RuntimeError("no target linear activations were captured")
    groups = np.concatenate(groups_parts, axis=0)
    labels = np.concatenate(labels_parts, axis=0)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, groups=groups, labels=labels)
    manifest = {
        "schema": "scalellm_fp_to_q_activation_capture_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": str(args.model.resolve()),
        "calibration_jsonl": str(args.calibration_jsonl.resolve()),
        "prompts": len(prompts),
        "max_length": args.max_length,
        "dtype": args.dtype,
        "device": str(device),
        "seed": args.seed,
        "target_ops": sorted(TARGET_OPS),
        "groups_by_op": dict(sorted(counts.items())),
        "sampled_groups_by_module": dict(sorted(module_counts.items())),
        "total_groups": int(groups.shape[0]),
        "output": str(args.output.resolve()),
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
