#!/usr/bin/env python3
"""Derive a 6,144-vector M10 workload from the frozen real Llama trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

import generate_boundary_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace")
SAMPLES = (0, 1)
LAYERS = (0, 15, 31)
TOKENS = (0, 1, 15, 31, 63, 95, 111, 127)
INTERMEDIATE = 14336
CHANNEL_STRIDE = 112
CHANNELS = tuple(range(0, INTERMEDIATE, CHANNEL_STRIDE))
VECTOR_COUNT = 6144
S24_SCALE = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1

sys.path.insert(0, str(base.ROOT / "model"))
from mlp_fixed import build_silu_lut, silu_real, swiglu_product_s32  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--output-dir", type=Path,
                        default=MODULE / "data_trace")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_hash(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def bf16_bits_to_fp32(array: np.ndarray) -> np.ndarray:
    if array.dtype != np.uint16:
        raise AssertionError(f"expected uint16 BF16 storage, got {array.dtype}")
    return (np.asarray(array, dtype=np.uint32) << np.uint32(16)).view(
        np.float32)


def quantize_s24(value: float) -> tuple[int, bool]:
    if not math.isfinite(value):
        raise AssertionError("non-finite Gate/Up value in source trace")
    rounded = int(np.rint(float(value) * S24_SCALE))
    clipped = min(S24_MAX, max(S24_MIN, rounded))
    return clipped, clipped != rounded


def verify_source_trace(trace_run: Path) -> tuple[Path, dict[str, object]]:
    trace_run = trace_run.resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("source trace STATUS is not PASS")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("source trace exit status is nonzero")
    trace_dir = trace_run / "trace"
    manifest_path = trace_dir / "manifest.json"
    expected = (trace_dir / "MANIFEST_SHA256").read_text(
        encoding="utf-8").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("source trace manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "scalellm_modular_llama_trace_v1" or
            manifest.get("layers") != list(LAYERS)):
        raise AssertionError("source trace contract mismatch")
    if [sample["sample"] for sample in manifest["samples"]] != list(SAMPLES):
        raise AssertionError("source trace sample contract mismatch")
    return trace_dir, manifest


def load_source_tensor(
        trace_dir: Path,
        record: dict[str, object],
) -> np.ndarray:
    path = trace_dir / str(record["file"])
    if sha256_file(path) != record["file_sha256"]:
        raise AssertionError(f"source tensor file hash mismatch: {path}")
    array = np.load(path, allow_pickle=False)
    if (list(array.shape) != record["shape"] or
            str(array.dtype) != record["storage_dtype"] or
            payload_hash(array) != record["payload_sha256"]):
        raise AssertionError(f"source tensor payload mismatch: {path}")
    return bf16_bits_to_fp32(array)


def source_record_summary(record: dict[str, object]) -> dict[str, object]:
    return {
        "sample": record["sample"],
        "layer": record["layer"],
        "name": record["name"],
        "file_sha256": record["file_sha256"],
        "payload_sha256": record["payload_sha256"],
        "shape": record["shape"],
        "storage_dtype": record["storage_dtype"],
    }


def input_error_metrics(errors: list[float], saturations: int) -> dict[str, float | int]:
    squares = [value * value for value in errors]
    return {
        "max_abs": max(errors),
        "mean_abs": sum(errors) / len(errors),
        "rmse": math.sqrt(sum(squares) / len(squares)),
        "saturation_count": saturations,
    }


def main() -> None:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace_dir, trace_manifest = verify_source_trace(args.trace_run)
    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }
    if len(CHANNELS) != 128 or CHANNELS[-1] != 14224:
        raise AssertionError("M10 channel schedule no longer has 128 coordinates")

    gate_records: list[int] = []
    up_records: list[int] = []
    gate16_records: list[int] = []
    up16_records: list[int] = []
    gate32_records: list[int] = []
    up32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    ideal_trace: list[float] = []
    ideal_common: list[float] = []
    gate_input_errors: list[float] = []
    up_input_errors: list[float] = []
    gate_saturations = 0
    up_saturations = 0
    output_saturations = {"fp16": 0, "fp32": 0}
    provenance_rows: list[dict[str, object]] = []
    source_records_used: dict[str, dict[str, object]] = {}
    table = build_silu_lut()

    vector_index = 0
    for sample in SAMPLES:
        for layer in LAYERS:
            gate_record = tensor_records[(sample, layer, "gate_bf16")]
            up_record = tensor_records[(sample, layer, "up_bf16")]
            gate_array = load_source_tensor(trace_dir, gate_record)
            up_array = load_source_tensor(trace_dir, up_record)
            source_records_used[str(gate_record["file"])] = \
                source_record_summary(gate_record)
            source_records_used[str(up_record["file"])] = \
                source_record_summary(up_record)
            for token in TOKENS:
                for channel in CHANNELS:
                    gate_trace = float(gate_array[token, channel])
                    up_trace = float(up_array[token, channel])
                    gate, gate_saturated = quantize_s24(gate_trace)
                    up, up_saturated = quantize_s24(up_trace)
                    gate_saturations += int(gate_saturated)
                    up_saturations += int(up_saturated)
                    gate_common = gate / S24_SCALE
                    up_common = up / S24_SCALE
                    gate_input_errors.append(abs(gate_trace - gate_common))
                    up_input_errors.append(abs(up_trace - up_common))

                    value16, sat16 = base.fp_swiglu(gate, up, 16)
                    value32, sat32 = base.fp_swiglu(gate, up, 32)
                    gate_records.append(gate)
                    up_records.append(up)
                    gate16_records.append(base.fp16_bits(gate_common))
                    up16_records.append(base.fp16_bits(up_common))
                    gate32_records.append(base.fp32_bits(gate_common))
                    up32_records.append(base.fp32_bits(up_common))
                    expected_sc.append(
                        swiglu_product_s32(gate, up, table))
                    expected16.append(value16)
                    expected32.append(value32)
                    ideal_trace.append(silu_real(gate_trace) * up_trace)
                    ideal_common.append(silu_real(gate_common) * up_common)
                    output_saturations["fp16"] += int(sat16)
                    output_saturations["fp32"] += int(sat32)
                    provenance_rows.append({
                        "vector": vector_index,
                        "sample": sample,
                        "layer": layer,
                        "token": token,
                        "intermediate_channel": channel,
                        "gate_source_tensor": gate_record["file"],
                        "gate_source_payload_sha256":
                            gate_record["payload_sha256"],
                        "up_source_tensor": up_record["file"],
                        "up_source_payload_sha256":
                            up_record["payload_sha256"],
                    })
                    vector_index += 1

    if not (vector_index == VECTOR_COUNT ==
            len(gate_records) == len(up_records) == len(expected_sc)):
        raise AssertionError("M10 trace-derived vector count mismatch")

    outputs: dict[str, tuple[list[int], int]] = {
        "gate_s24.mem": (gate_records, 6),
        "up_s24.mem": (up_records, 6),
        "gate_fp16.mem": (gate16_records, 4),
        "up_fp16.mem": (up16_records, 4),
        "gate_fp32.mem": (gate32_records, 8),
        "up_fp32.mem": (up32_records, 8),
        "expected_sc_s32.mem": (expected_sc, 8),
        "expected_fp16_s32.mem": (expected16, 8),
        "expected_fp32_s32.mem": (expected32, 8),
    }
    files: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        base.write_mem(output / filename, values, digits)
        files[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(output / filename),
        }

    provenance_path = output / "trace_vectors.csv"
    with provenance_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(provenance_rows[0]))
        writer.writeheader()
        writer.writerows(provenance_rows)
    files[provenance_path.name] = {
        "records": len(provenance_rows),
        "hex_digits": 0,
        "sha256": sha256_file(provenance_path),
    }

    trace_manifest_path = trace_dir / "manifest.json"
    production_model = base.ROOT / "model" / "mlp_fixed.py"
    manifest = {
        "schema": "scalellm_modular_m10_silu_real_trace_v1",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(trace_manifest_path),
        "samples": list(SAMPLES),
        "layers": list(LAYERS),
        "tokens": list(TOKENS),
        "intermediate_channels": list(CHANNELS),
        "channel_selection": (
            "128 channels spanning [0,14336) at exact stride 112"),
        "vector_schedule": "sample, layer, token, intermediate_channel",
        "vectors": VECTOR_COUNT,
        "common_input": (
            "captured BF16 Gate/Up rounded nearest-even to signed S24 Q8.16"),
        "common_output": "signed S32 Q16.16 SwiGLU product",
        "input_quantization_vs_trace": {
            "gate_bf16_to_s24": input_error_metrics(
                gate_input_errors, gate_saturations),
            "up_bf16_to_s24": input_error_metrics(
                up_input_errors, up_saturations),
        },
        "coverage": {
            "zero_gate_records": sum(value == 0 for value in gate_records),
            "positive_gate_records": sum(value > 0 for value in gate_records),
            "negative_gate_records": sum(value < 0 for value in gate_records),
            "gate_below_silu_lut": sum(
                value <= -(16 << 16) for value in gate_records),
            "gate_above_silu_lut": sum(
                value >= (16 << 16) for value in gate_records),
        },
        "saturation_counts": {
            "sc": 0,
            "fp16": output_saturations["fp16"],
            "fp32": output_saturations["fp32"],
        },
        "accuracy_vs_raw_trace_swiglu": {
            "sc": base.error_metrics(expected_sc, ideal_trace),
            "fp16": base.error_metrics(expected16, ideal_trace),
            "fp32": base.error_metrics(expected32, ideal_trace),
        },
        "accuracy_vs_common_s24_fp64_swiglu": {
            "sc": base.error_metrics(expected_sc, ideal_common),
            "fp16": base.error_metrics(expected16, ideal_common),
            "fp32": base.error_metrics(expected32, ideal_common),
        },
        "numeric_models": {
            "sc": "production 8192-entry SiLU LUT and round-away-zero product",
            "fp16": "fixed-to-FP16 then exp/add/div/multiply in native FP16",
            "fp32": "fixed-to-FP32 then exp/add/div/multiply in native FP32",
            "trace_reference": "stable FP64 SiLU over captured BF16 Gate/Up",
            "common_reference": "stable FP64 SiLU over common S24 Gate/Up",
        },
        "source_tensors": [
            source_records_used[name] | {"file": name}
            for name in sorted(source_records_used)
        ],
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M10_TRACE_VECTOR_PASS "
        f"vectors={VECTOR_COUNT} source_tensors={len(source_records_used)} "
        f"manifest_sha256={sha256_file(output / 'manifest.json')}")


if __name__ == "__main__":
    main()
