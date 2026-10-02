#!/usr/bin/env python3
"""Freeze replayable Llama-3.1 attention/MLP tensors for ModularExperiment.

The existing activation audit stores range statistics only.  This collector
stores the actual tensors needed to derive module workloads: pre/post-RoPE
Q/K, V, pre-softmax score, probability, Gate/Up, and the SwiGLU product that
is also the Down projection input.  BF16 payloads are written as raw uint16
bit patterns in NPY containers so no conversion silently changes their bits.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.models.llama.modeling_llama import (
    apply_rotary_pos_emb,
    repeat_kv,
)


SCHEMA = "scalellm_modular_llama_trace_v1"
TENSOR_AXES = {
    "q_pre_rope_bf16": ["token", "q_head", "head_dim"],
    "q_post_rope_bf16": ["token", "q_head", "head_dim"],
    "k_pre_rope_bf16": ["token", "kv_head", "head_dim"],
    "k_post_rope_bf16": ["token", "kv_head", "head_dim"],
    "v_bf16": ["token", "kv_head", "head_dim"],
    "score_raw_fp32": ["query_token", "q_head", "key_token"],
    "score_masked_fp32": ["query_token", "q_head", "key_token"],
    "probability_fp32": ["query_token", "q_head", "key_token"],
    "gate_bf16": ["token", "intermediate_channel"],
    "up_bf16": ["token", "intermediate_channel"],
    "swiglu_down_input_bf16": ["token", "intermediate_channel"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--text-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--layers", default="0,15,31")
    parser.add_argument("--max-samples", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--model-name", default="Llama-3.1-8B-Instruct")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_layers(raw: str, count: int) -> list[int]:
    values = sorted({int(value.strip()) for value in raw.split(",")})
    if not values or values[0] < 0 or values[-1] >= count:
        raise ValueError(f"layers must be within [0,{count - 1}]")
    return values


def load_samples(path: Path, count: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for source_line, line in enumerate(handle, start=1):
            record = json.loads(line)
            text = str(record.get("text", "")).strip()
            if len(text) < 64:
                continue
            samples.append({
                "source_line": source_line,
                "text": text,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
            })
            if len(samples) == count:
                break
    if len(samples) != count:
        raise RuntimeError(f"requested {count} samples but found {len(samples)}")
    return samples


def bf16_bits(tensor: torch.Tensor) -> np.ndarray:
    cpu = tensor.detach().to(torch.bfloat16).contiguous().cpu()
    return cpu.view(torch.uint16).numpy()


def fp32_values(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().to(torch.float32).contiguous().cpu().numpy()


def payload_hash(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes(order="C"))


def save_array(path: Path, array: np.ndarray) -> dict[str, Any]:
    np.save(path, array, allow_pickle=False)
    return {
        "file": path.name,
        "shape": list(array.shape),
        "storage_dtype": str(array.dtype),
        "payload_sha256": payload_hash(array),
        "file_sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def selected_tokens(length: int) -> list[int]:
    return sorted({0, length // 2, length - 1})


def append_slice_hashes(
    rows: list[dict[str, Any]], sample: int, layer: int, name: str,
    array: np.ndarray, token_ids: np.ndarray,
) -> None:
    tokens = selected_tokens(array.shape[0])
    if name.startswith(("q_", "k_", "v_")):
        for token in tokens:
            for head in range(array.shape[1]):
                rows.append({
                    "sample": sample, "layer": layer, "tensor": name,
                    "token": token, "token_id": int(token_ids[token]),
                    "head": head, "group": "",
                    "slice_payload_sha256": payload_hash(array[token, head]),
                })
    elif name.startswith(("score_", "probability_")):
        for token in tokens:
            for head in range(array.shape[1]):
                rows.append({
                    "sample": sample, "layer": layer, "tensor": name,
                    "token": token, "token_id": int(token_ids[token]),
                    "head": head, "group": "",
                    "slice_payload_sha256": payload_hash(array[token, head]),
                })
    elif name in {"gate_bf16", "up_bf16", "swiglu_down_input_bf16"}:
        if array.shape[1] % 32:
            raise AssertionError(f"{name} channel count is not group32 aligned")
        for token in tokens:
            for group in range(array.shape[1] // 32):
                rows.append({
                    "sample": sample, "layer": layer, "tensor": name,
                    "token": token, "token_id": int(token_ids[token]),
                    "head": "", "group": group,
                    "slice_payload_sha256": payload_hash(
                        array[token, group * 32:(group + 1) * 32]),
                })


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.max_samples < 1 or args.max_length < 1:
        raise ValueError("max-samples and max-length must be positive")
    model_path = args.model_path.resolve(strict=True)
    text_jsonl = args.text_jsonl.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(
        prefix=f".{output_dir.name}.tmp.", dir=output_dir.parent))

    try:
        config_path = model_path / "config.json"
        tokenizer_path = model_path / "tokenizer.json"
        index_path = model_path / "model.safetensors.index.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        layers = parse_layers(args.layers, int(config["num_hidden_layers"]))
        samples = load_samples(text_jsonl, args.max_samples)

        tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            local_files_only=True,
            attn_implementation="eager",
            low_cpu_mem_usage=True,
        ).to(torch.device(args.device))
        model.eval()

        current_sample = -1
        cache: dict[int, dict[str, Any]] = {layer: {} for layer in layers}
        handles = []

        def attention_pre_hook(layer: int):
            def hook(_module, hook_args, hook_kwargs):
                item = cache[layer]
                position_embeddings = hook_kwargs.get("position_embeddings")
                if position_embeddings is None:
                    raise RuntimeError("attention hook did not receive RoPE embeddings")
                item["cos"], item["sin"] = position_embeddings
                item["attention_mask"] = hook_kwargs.get("attention_mask")
            return hook

        def projection_hook(layer: int, name: str):
            def hook(_module, _hook_args, output):
                cache[layer][name] = output.detach()
            return hook

        def attention_post_hook(layer: int):
            def hook(module, _hook_args, _hook_kwargs, _output):
                item = cache[layer]
                q_linear = item.pop("q_linear")
                k_linear = item.pop("k_linear")
                v_linear = item.pop("v_linear")
                batch, length, _ = q_linear.shape
                if batch != 1:
                    raise RuntimeError("trace contract requires batch size one")
                q = q_linear.view(batch, length, -1, module.head_dim).transpose(1, 2)
                k = k_linear.view(batch, length, -1, module.head_dim).transpose(1, 2)
                v = v_linear.view(batch, length, -1, module.head_dim).transpose(1, 2)
                q_rope, k_rope = apply_rotary_pos_emb(
                    q, k, item.pop("cos"), item.pop("sin"))
                k_repeat = repeat_kv(k_rope, module.num_key_value_groups)
                score_raw = torch.matmul(
                    q_rope.to(torch.float32),
                    k_repeat.transpose(2, 3).to(torch.float32),
                ) * float(module.scaling)
                mask = item.pop("attention_mask")
                if mask is None:
                    causal = torch.full(
                        (length, length), float("-inf"),
                        dtype=torch.float32, device=score_raw.device)
                    mask = torch.triu(causal, diagonal=1)[None, None]
                else:
                    mask = mask[..., :length].to(torch.float32)
                score_masked = score_raw + mask
                probability = torch.softmax(score_masked, dim=-1)
                item.update({
                    "q_pre_rope_bf16": q[0].transpose(0, 1),
                    "q_post_rope_bf16": q_rope[0].transpose(0, 1),
                    "k_pre_rope_bf16": k[0].transpose(0, 1),
                    "k_post_rope_bf16": k_rope[0].transpose(0, 1),
                    "v_bf16": v[0].transpose(0, 1),
                    "score_raw_fp32": score_raw[0].permute(1, 0, 2),
                    "score_masked_fp32": score_masked[0].permute(1, 0, 2),
                    "probability_fp32": probability[0].permute(1, 0, 2),
                })
            return hook

        def down_input_hook(layer: int):
            def hook(_module, hook_args):
                cache[layer]["swiglu_down_input_bf16"] = hook_args[0].detach()[0]
            return hook

        for layer in layers:
            block = model.model.layers[layer]
            attention = block.self_attn
            handles.extend([
                attention.register_forward_pre_hook(
                    attention_pre_hook(layer), with_kwargs=True),
                attention.q_proj.register_forward_hook(
                    projection_hook(layer, "q_linear")),
                attention.k_proj.register_forward_hook(
                    projection_hook(layer, "k_linear")),
                attention.v_proj.register_forward_hook(
                    projection_hook(layer, "v_linear")),
                attention.register_forward_hook(
                    attention_post_hook(layer), with_kwargs=True),
                block.mlp.gate_proj.register_forward_hook(
                    projection_hook(layer, "gate_linear")),
                block.mlp.up_proj.register_forward_hook(
                    projection_hook(layer, "up_linear")),
                block.mlp.down_proj.register_forward_pre_hook(
                    down_input_hook(layer)),
            ])

        tensor_records: list[dict[str, Any]] = []
        slice_rows: list[dict[str, Any]] = []
        workload_records: list[dict[str, Any]] = []
        device = torch.device(args.device)
        with torch.inference_mode():
            for sample_index, sample in enumerate(samples):
                current_sample = sample_index
                for item in cache.values():
                    item.clear()
                encoded = tokenizer(
                    sample["text"], return_tensors="pt", truncation=True,
                    max_length=args.max_length)
                encoded = {name: value.to(device) for name, value in encoded.items()}
                model(**encoded, use_cache=False, return_dict=True)
                token_ids = encoded["input_ids"][0].detach().cpu().numpy()
                input_file = temporary / f"sample{sample_index:02d}_input_ids.npy"
                input_record = save_array(input_file, token_ids.astype(np.int64))
                workload_records.append({
                    "sample": sample_index,
                    "source_line": sample["source_line"],
                    "text_sha256": sample["text_sha256"],
                    "token_count": int(token_ids.size),
                    "input_ids": input_record,
                    "selected_token_coordinates": selected_tokens(int(token_ids.size)),
                })

                for layer in layers:
                    item = cache[layer]
                    item["gate_bf16"] = item.pop("gate_linear")[0]
                    item["up_bf16"] = item.pop("up_linear")[0]
                    expected = set(TENSOR_AXES)
                    if set(item) != expected:
                        raise RuntimeError(
                            f"layer {layer} trace mismatch: have={sorted(item)} "
                            f"expected={sorted(expected)}")
                    for name in sorted(item):
                        tensor = item[name]
                        logical_dtype = (
                            "bfloat16" if name.endswith("_bf16") else "float32")
                        array = (bf16_bits(tensor) if logical_dtype == "bfloat16"
                                 else fp32_values(tensor))
                        filename = f"s{sample_index:02d}_l{layer:02d}_{name}.npy"
                        record = save_array(temporary / filename, array)
                        record.update({
                            "sample": sample_index,
                            "layer": layer,
                            "name": name,
                            "logical_dtype": logical_dtype,
                            "axes": TENSOR_AXES[name],
                        })
                        tensor_records.append(record)
                        append_slice_hashes(
                            slice_rows, sample_index, layer, name, array, token_ids)
                    item.clear()
                print(
                    f"TRACE_SAMPLE_PASS sample={sample_index} "
                    f"tokens={token_ids.size} layers={layers}", flush=True)

        for handle in handles:
            handle.remove()

        slice_path = temporary / "coordinate_hashes.csv"
        with slice_path.open("w", newline="", encoding="utf-8") as handle:
            fields = ["sample", "layer", "tensor", "token", "token_id",
                      "head", "group", "slice_payload_sha256"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(slice_rows)

        shard_files = sorted(model_path.glob("model-*.safetensors"))
        manifest = {
            "schema": SCHEMA,
            "model": args.model_name,
            "checkpoint": str(model_path),
            "checkpoint_files": [
                {
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in shard_files
            ],
            "checkpoint_index_sha256": sha256_file(index_path),
            "config_sha256": sha256_file(config_path),
            "tokenizer_sha256": sha256_file(tokenizer_path),
            "workload_source": str(text_jsonl),
            "workload_source_sha256": sha256_file(text_jsonl),
            "layers": layers,
            "max_length": args.max_length,
            "samples": workload_records,
            "tensor_count": len(tensor_records),
            "tensors": tensor_records,
            "coordinate_hashes": {
                "file": slice_path.name,
                "rows": len(slice_rows),
                "sha256": sha256_file(slice_path),
                "contract": (
                    "all heads/groups at token coordinates 0,middle,last; "
                    "attention row hashes cover every key position"),
            },
            "trace_contract": {
                "checkpoint_compute_dtype": "bfloat16",
                "batch_size": 1,
                "attention_implementation": "eager",
                "score": "FP32(Q_rope @ K_rope^T) * module.scaling",
                "probability": "softmax(score + model causal attention mask)",
                "mlp": "gate, up, and actual down_proj pre-hook payload",
                "bf16_storage": "uint16 raw bfloat16 bit pattern",
                "group_size": 32,
            },
            "environment": {
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "numpy": np.__version__,
                "platform": platform.platform(),
                "device": args.device,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            },
        }
        write_json(temporary / "manifest.json", manifest)
        manifest_sha = sha256_file(temporary / "manifest.json")
        (temporary / "MANIFEST_SHA256").write_text(
            f"{manifest_sha}  manifest.json\n", encoding="utf-8")
        temporary.rename(output_dir)
        print(
            f"LLAMA_TRACE_CAPTURE_PASS samples={len(samples)} layers={len(layers)} "
            f"tensors={len(tensor_records)} slices={len(slice_rows)} "
            f"manifest_sha256={manifest_sha}", flush=True)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
