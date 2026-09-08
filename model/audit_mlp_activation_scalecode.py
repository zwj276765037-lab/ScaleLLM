#!/usr/bin/env python3
"""Trace Llama MLP activation ScaleCode ranges on a real checkpoint.

This is a read-only model audit.  It hooks gate/up/down projection inputs and
uses the same local Hadamard32, include-zero asymmetric A8 and code8/shift
encoding as the MLP-W4 ScaleCode reference.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MLP_OPS = {"gate_proj", "up_proj", "down_proj"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=Path, required=True)
    parser.add_argument("--weight_audit_csv", type=Path, required=True)
    parser.add_argument("--text_jsonl", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max_samples", type=int, default=8)
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--model_name", default="Llama-3.1-8B-Instruct")
    return parser.parse_args()


def fwht32_last(x: torch.Tensor) -> torch.Tensor:
    if x.shape[-1] % 32:
        raise ValueError("MLP projection input must be divisible by 32")
    original_shape = x.shape
    y = x.to(torch.float32).reshape(-1, 32)
    step = 1
    while step < 32:
        y = y.reshape(-1, 2, step)
        lhs = y[:, 0, :]
        rhs = y[:, 1, :]
        y = torch.cat((lhs + rhs, lhs - rhs), dim=1)
        step *= 2
    return (y * (1.0 / math.sqrt(32.0))).reshape(*original_shape)


def encode_scale(scale: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    safe = scale.detach().to(torch.float32).clamp_min(1e-30)
    shift = torch.floor(torch.log2(255.0 / safe)).clamp(0, 255).to(torch.int64)
    code = torch.round(torch.ldexp(safe, shift)).clamp(0, 255).to(torch.int64)
    return code, shift


def load_samples(path: Path, count: int) -> list[str]:
    samples: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = str(json.loads(line).get("text", "")).strip()
            if len(text) < 64:
                continue
            samples.append(text)
            if len(samples) == count:
                break
    if not samples:
        raise RuntimeError(f"no non-empty samples in {path}")
    return samples


def weight_shift_rows(path: Path, model_name: str) -> dict[tuple[int, str], dict[str, int]]:
    selected: dict[tuple[int, str], dict[str, int]] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["model"] != model_name or int(row["weight_bits"]) != 4:
                continue
            op = row["op"]
            if op in MLP_OPS:
                selected[(int(row["layer"]), op)] = {
                    "weight_shift_min": int(row["shift_min"]),
                    "weight_shift_max": int(row["shift_max"]),
                }
    if len(selected) != 96:
        raise RuntimeError(f"expected 96 Llama W4 rows, found {len(selected)}")
    return selected


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        dtype=torch.bfloat16,
        local_files_only=True,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval()

    stats: dict[tuple[int, str], dict[str, Any]] = {}
    hooks = []

    def make_hook(layer: int, op: str):
        def hook(_module: torch.nn.Module, inputs: tuple[torch.Tensor, ...]) -> None:
            source = inputs[0].detach()
            transformed = fwht32_last(source)
            groups = transformed.reshape(-1, 32)
            zero = torch.zeros((), device=groups.device)
            xmin = torch.minimum(groups.amin(dim=-1), zero)
            xmax = torch.maximum(groups.amax(dim=-1), zero)
            scale = ((xmax - xmin) / 255.0).clamp_min(1e-30)
            code, shift = encode_scale(scale)
            key = (layer, op)
            item = stats.setdefault(key, {
                "layer": layer,
                "op": op,
                "calls": 0,
                "tokens": 0,
                "groups": 0,
                "activation_shift_min": 255,
                "activation_shift_max": 0,
                "activation_code_min": 255,
                "activation_code_max": 0,
                "zero_code_count": 0,
                "hadamard_abs_max": 0.0,
                "shift_hist": Counter(),
            })
            item["calls"] += 1
            item["tokens"] += int(source.numel() // source.shape[-1])
            item["groups"] += int(groups.shape[0])
            item["activation_shift_min"] = min(
                item["activation_shift_min"], int(shift.min().item()))
            item["activation_shift_max"] = max(
                item["activation_shift_max"], int(shift.max().item()))
            item["activation_code_min"] = min(
                item["activation_code_min"], int(code.min().item()))
            item["activation_code_max"] = max(
                item["activation_code_max"], int(code.max().item()))
            item["zero_code_count"] += int((code == 0).sum().item())
            item["hadamard_abs_max"] = max(
                item["hadamard_abs_max"], float(transformed.abs().max().item()))
            values, counts = torch.unique(shift, return_counts=True)
            item["shift_hist"].update({
                int(value): int(count)
                for value, count in zip(values.cpu().tolist(), counts.cpu().tolist())
            })
        return hook

    for name, module in model.named_modules():
        op = name.rsplit(".", 1)[-1]
        if op not in MLP_OPS or not isinstance(module, torch.nn.Linear):
            continue
        parts = name.split(".")
        try:
            layer = int(parts[parts.index("layers") + 1])
        except (ValueError, IndexError):
            continue
        hooks.append(module.register_forward_pre_hook(make_hook(layer, op)))
    if len(hooks) != 96:
        raise RuntimeError(f"expected 96 MLP hooks, installed {len(hooks)}")

    samples = load_samples(args.text_jsonl, args.max_samples)
    with torch.inference_mode():
        for index, text in enumerate(samples):
            encoded = tokenizer(
                text, return_tensors="pt", truncation=True,
                max_length=args.max_length).to(device)
            model(**encoded, use_cache=False, return_dict=True)
            print(
                f"sample={index + 1}/{len(samples)} tokens={encoded['input_ids'].shape[-1]}",
                flush=True)

    for handle in hooks:
        handle.remove()
    weights = weight_shift_rows(args.weight_audit_csv, args.model_name)
    rows: list[dict[str, Any]] = []
    for key in sorted(stats):
        item = stats[key]
        weight = weights[key]
        rows.append({
            "layer": item["layer"],
            "op": item["op"],
            "calls": item["calls"],
            "tokens": item["tokens"],
            "activation_groups": item["groups"],
            "activation_shift_min": item["activation_shift_min"],
            "activation_shift_max": item["activation_shift_max"],
            "activation_code_min": item["activation_code_min"],
            "activation_code_max": item["activation_code_max"],
            "zero_code_count": item["zero_code_count"],
            "hadamard_abs_max": item["hadamard_abs_max"],
            **weight,
            "conservative_total_shift_min": (
                item["activation_shift_min"] + weight["weight_shift_min"]),
            "conservative_total_shift_max": (
                item["activation_shift_max"] + weight["weight_shift_max"]),
            "activation_shift_hist_json": json.dumps(
                dict(sorted(item["shift_hist"].items())), separators=(",", ":")),
        })
    if len(rows) != 96:
        raise RuntimeError(f"expected 96 result rows, found {len(rows)}")
    write_csv(args.output_dir / "mlp_activation_scalecode_by_layer.csv", rows)

    summary: dict[str, Any] = {
        "model": args.model_name,
        "checkpoint": str(args.model_path),
        "samples": len(samples),
        "max_length": args.max_length,
        "trace_contract": (
            "BF16 checkpoint projection inputs; Hadamard32 normalized; "
            "include-zero asymmetric A8; ScaleCode code8/shift"
        ),
        "per_op": {},
    }
    for op in sorted(MLP_OPS):
        op_rows = [row for row in rows if row["op"] == op]
        summary["per_op"][op] = {
            "layers": len(op_rows),
            "tokens": sum(int(row["tokens"]) for row in op_rows),
            "activation_groups": sum(int(row["activation_groups"]) for row in op_rows),
            "activation_shift_min": min(int(row["activation_shift_min"]) for row in op_rows),
            "activation_shift_max": max(int(row["activation_shift_max"]) for row in op_rows),
            "weight_shift_min": min(int(row["weight_shift_min"]) for row in op_rows),
            "weight_shift_max": max(int(row["weight_shift_max"]) for row in op_rows),
            "conservative_total_shift_min": min(
                int(row["conservative_total_shift_min"]) for row in op_rows),
            "conservative_total_shift_max": max(
                int(row["conservative_total_shift_max"]) for row in op_rows),
            "hadamard_abs_max": max(float(row["hadamard_abs_max"]) for row in op_rows),
            "zero_code_count": sum(int(row["zero_code_count"]) for row in op_rows),
        }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
