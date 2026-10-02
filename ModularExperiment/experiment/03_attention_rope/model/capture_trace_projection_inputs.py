#!/usr/bin/env python3
"""Capture the missing pre-projection activations for the formal M03 trace.

The frozen shared trace contains pre/post-RoPE Q/K but not the input to q_proj
and k_proj.  M03's fair boundary starts before scale application, so those Q/K
outputs cannot be inverted to invent correlation or scale metadata.  This
supplement replays the frozen input IDs through the exact checkpoint, captures
the common q_proj input, and proves provenance by comparing newly computed
pre-RoPE Q and K tensors with the frozen tensors.  Deep BF16 CUDA forwards are
not assumed bit-reproducible: bit differences are retained and a normalized
RMSE/cosine gate is applied instead of hiding them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

import numpy as np
import torch
import transformers
from transformers import AutoModelForCausalLM


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
)
DEFAULT_OUTPUT = MODULE / "data_trace_projection_input"
LAYERS = (0, 15, 31)
SAMPLES = (0, 1)
HEAD_DIM = 128
Q_HEADS = 32
KV_HEADS = 8
HIDDEN = 4096
MAX_NORMALIZED_RMSE = 0.02
MIN_COSINE = 0.9998


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda:1")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_hash(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def bf16_bits(tensor: torch.Tensor) -> np.ndarray:
    cpu = tensor.detach().to(torch.bfloat16).contiguous().cpu()
    return cpu.view(torch.uint16).numpy()


def bf16_bits_to_fp32(array: np.ndarray) -> np.ndarray:
    if array.dtype != np.uint16:
        raise AssertionError("expected raw BF16 uint16")
    return (np.asarray(array, dtype=np.uint32) << np.uint32(16)).view(
        np.float32)


def comparison_metrics(
        replayed_bits: np.ndarray, frozen_bits: np.ndarray,
) -> dict[str, float | int]:
    replayed = bf16_bits_to_fp32(replayed_bits).astype(np.float64).reshape(-1)
    frozen = bf16_bits_to_fp32(frozen_bits).astype(np.float64).reshape(-1)
    if (replayed.shape != frozen.shape or not np.all(np.isfinite(replayed)) or
            not np.all(np.isfinite(frozen))):
        raise AssertionError("invalid replay comparison arrays")
    error = replayed - frozen
    rmse = float(np.sqrt(np.mean(error * error)))
    reference_rms = float(np.sqrt(np.mean(frozen * frozen)))
    denominator = float(np.linalg.norm(replayed) * np.linalg.norm(frozen))
    return {
        "bit_mismatches": int(np.count_nonzero(
            replayed_bits != frozen_bits)),
        "max_abs": float(np.max(np.abs(error))),
        "mean_abs": float(np.mean(np.abs(error))),
        "rmse": rmse,
        "reference_rms": reference_rms,
        "normalized_rmse": rmse / reference_rms if reference_rms else rmse,
        "cosine": float(np.dot(replayed, frozen) / denominator)
        if denominator else 1.0,
    }


def save_array(path: Path, array: np.ndarray) -> dict[str, Any]:
    np.save(path, array, allow_pickle=False)
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "shape": list(array.shape),
        "storage_dtype": str(array.dtype),
        "payload_sha256": payload_hash(array),
        "file_sha256": sha256_file(path),
    }


def load_array(path: Path, record: dict[str, Any]) -> np.ndarray:
    if (path.stat().st_size != record["bytes"] or
            sha256_file(path) != record["file_sha256"]):
        raise AssertionError(f"source file mismatch: {path}")
    array = np.load(path, allow_pickle=False)
    if (list(array.shape) != record["shape"] or
            str(array.dtype) != record["storage_dtype"] or
            payload_hash(array) != record["payload_sha256"]):
        raise AssertionError(f"source payload mismatch: {path}")
    return array


def verify_trace(trace_run: Path) -> tuple[Path, dict[str, Any]]:
    trace_run = trace_run.resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("source trace STATUS is not PASS")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("source trace exit status is nonzero")
    trace_dir = trace_run / "trace"
    manifest_path = trace_dir / "manifest.json"
    expected = (trace_dir / "MANIFEST_SHA256").read_text(
        encoding="ascii").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("source trace manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "scalellm_modular_llama_trace_v1" or
            manifest.get("layers") != list(LAYERS) or
            [item["sample"] for item in manifest["samples"]] !=
            list(SAMPLES)):
        raise AssertionError("source trace contract mismatch")
    return trace_dir, manifest


def verify_checkpoint(
        model_dir: Path, trace_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    model_dir = model_dir.resolve(strict=True)
    config_path = model_dir / "config.json"
    index_path = model_dir / "model.safetensors.index.json"
    if sha256_file(config_path) != trace_manifest["config_sha256"]:
        raise AssertionError("checkpoint config hash mismatch")
    if sha256_file(index_path) != trace_manifest["checkpoint_index_sha256"]:
        raise AssertionError("checkpoint index hash mismatch")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    source_records = {
        record["name"]: record
        for record in trace_manifest["checkpoint_files"]
    }
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for layer in LAYERS:
        for operation in ("q_proj", "k_proj"):
            tensor = (
                f"model.layers.{layer}.self_attn.{operation}.weight")
            shard = index["weight_map"].get(tensor)
            if not isinstance(shard, str) or shard not in source_records:
                raise AssertionError(f"checkpoint mapping missing: {tensor}")
            if shard in seen:
                continue
            record = source_records[shard]
            path = model_dir / shard
            if (path.stat().st_size != record["bytes"] or
                    sha256_file(path) != record["sha256"]):
                raise AssertionError(f"checkpoint shard mismatch: {path}")
            selected.append({
                "name": shard,
                "bytes": int(record["bytes"]),
                "sha256": str(record["sha256"]),
            })
            seen.add(shard)
    return selected


def main() -> None:
    args = parse_args()
    trace_run = args.trace_run.resolve(strict=True)
    trace_dir, trace_manifest = verify_trace(trace_run)
    model_dir = Path(args.model_dir or trace_manifest["checkpoint"]).resolve(
        strict=True)
    checkpoint_shards = verify_checkpoint(model_dir, trace_manifest)
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(
        prefix=f".{output.name}.tmp.", dir=output.parent))

    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }
    sample_records = {
        record["sample"]: record for record in trace_manifest["samples"]
    }
    model = None
    handles = []
    try:
        device = torch.device(args.device)
        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            dtype=torch.bfloat16,
            local_files_only=True,
            attn_implementation="eager",
            low_cpu_mem_usage=True,
        ).to(device)
        model.eval()

        captured: dict[int, dict[str, torch.Tensor]] = {
            layer: {} for layer in LAYERS
        }

        def input_hook(layer: int):
            def hook(_module, hook_args):
                if "attention_input" in captured[layer]:
                    raise RuntimeError("q_proj input hook fired more than once")
                captured[layer]["attention_input"] = hook_args[0].detach()
            return hook

        def output_hook(layer: int, name: str):
            def hook(_module, _hook_args, result):
                if name in captured[layer]:
                    raise RuntimeError(f"{name} hook fired more than once")
                captured[layer][name] = result.detach()
            return hook

        for layer in LAYERS:
            attention = model.model.layers[layer].self_attn
            handles.extend([
                attention.q_proj.register_forward_pre_hook(input_hook(layer)),
                attention.q_proj.register_forward_hook(
                    output_hook(layer, "q_linear")),
                attention.k_proj.register_forward_hook(
                    output_hook(layer, "k_linear")),
            ])

        files: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []
        input_sources: list[dict[str, Any]] = []
        with torch.inference_mode():
            for sample in SAMPLES:
                for values in captured.values():
                    values.clear()
                source_sample = sample_records[sample]
                input_record = source_sample["input_ids"]
                input_path = trace_dir / input_record["file"]
                input_ids_np = load_array(input_path, input_record)
                if input_ids_np.shape != (128,) or input_ids_np.dtype != np.int64:
                    raise AssertionError("unexpected frozen input_ids shape")
                input_ids = torch.from_numpy(input_ids_np.copy())[None].to(device)
                model(
                    input_ids=input_ids,
                    attention_mask=torch.ones_like(input_ids),
                    use_cache=False,
                    return_dict=True,
                )
                input_sources.append({
                    "sample": sample,
                    "file": input_record["file"],
                    "file_sha256": input_record["file_sha256"],
                    "payload_sha256": input_record["payload_sha256"],
                })

                for layer in LAYERS:
                    item = captured[layer]
                    if set(item) != {"attention_input", "q_linear", "k_linear"}:
                        raise AssertionError(
                            f"incomplete layer capture: sample={sample} "
                            f"layer={layer} keys={sorted(item)}")
                    attention_input = bf16_bits(item["attention_input"][0])
                    if attention_input.shape != (128, HIDDEN):
                        raise AssertionError("unexpected projection input shape")
                    name = f"s{sample:02d}_l{layer:02d}_attention_input_bf16.npy"
                    record = save_array(temporary / name, attention_input)
                    record.update({"sample": sample, "layer": layer})
                    files.append(record)

                    for operation, heads in (
                            ("q", Q_HEADS), ("k", KV_HEADS)):
                        actual = bf16_bits(item[f"{operation}_linear"][0]).reshape(
                            128, heads, HEAD_DIM)
                        source_record = tensor_records[
                            (sample, layer, f"{operation}_pre_rope_bf16")]
                        expected = load_array(
                            trace_dir / source_record["file"], source_record)
                        metrics = comparison_metrics(actual, expected)
                        if (metrics["normalized_rmse"] > MAX_NORMALIZED_RMSE or
                                metrics["cosine"] < MIN_COSINE):
                            raise AssertionError(
                                f"frozen {operation.upper()} replay exceeds "
                                f"numeric provenance gate: sample={sample} "
                                f"layer={layer} metrics={metrics}")
                        print(
                            "M03_PROJECTION_OUTPUT_COMPARE "
                            f"sample={sample} layer={layer} op={operation} "
                            f"bit_mismatches={metrics['bit_mismatches']} "
                            f"nrmse={metrics['normalized_rmse']:.9e} "
                            f"cosine={metrics['cosine']:.12f}", flush=True)
                        checks.append({
                            "sample": sample,
                            "layer": layer,
                            "operation": operation,
                            "elements": int(actual.size),
                            **metrics,
                            "replayed_payload_sha256": payload_hash(actual),
                            "frozen_tensor": source_record["file"],
                            "frozen_file_sha256": source_record["file_sha256"],
                            "frozen_payload_sha256": source_record[
                                "payload_sha256"],
                        })
                print(
                    f"M03_PROJECTION_INPUT_SAMPLE_PASS sample={sample} "
                    f"layers={list(LAYERS)}", flush=True)

        for handle in handles:
            handle.remove()
        handles.clear()
        capture_script = Path(__file__).resolve()
        manifest = {
            "schema": "scalellm_modular_m03_projection_input_trace_v1",
            "samples": list(SAMPLES),
            "layers": list(LAYERS),
            "tokens": 128,
            "hidden": HIDDEN,
            "storage": "raw BF16 uint16 in NPY",
            "provenance_contract": (
                "q_proj input from exact frozen input_ids/checkpoint; newly "
                "computed pre-RoPE Q/K are compared to frozen trace with all "
                "BF16 bit mismatches retained and explicit numeric gates"),
            "projection_output_gate": {
                "max_normalized_rmse": MAX_NORMALIZED_RMSE,
                "min_cosine": MIN_COSINE,
            },
            "source_trace_run": str(trace_run),
            "source_trace_manifest_sha256": sha256_file(
                trace_dir / "manifest.json"),
            "checkpoint": str(model_dir),
            "checkpoint_index_sha256": trace_manifest[
                "checkpoint_index_sha256"],
            "checkpoint_shards": checkpoint_shards,
            "input_id_sources": input_sources,
            "projection_output_checks": checks,
            "files": sorted(files, key=lambda value: value["file"]),
            "capture_script": str(capture_script),
            "capture_script_sha256": sha256_file(capture_script),
            "environment": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "device": args.device,
            },
        }
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        manifest_hash = sha256_file(manifest_path)
        (temporary / "MANIFEST_SHA256").write_text(
            f"{manifest_hash}  manifest.json\n", encoding="ascii")
        temporary.replace(output)
        print(
            "M03_PROJECTION_INPUT_CAPTURE_PASS "
            f"files={len(files)} samples={len(SAMPLES)} layers={len(LAYERS)} "
            f"qk_checks={len(checks)} "
            f"bit_mismatches={sum(int(item['bit_mismatches']) for item in checks)} "
            f"manifest_sha256={manifest_hash}")
    except BaseException:
        for handle in handles:
            handle.remove()
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
