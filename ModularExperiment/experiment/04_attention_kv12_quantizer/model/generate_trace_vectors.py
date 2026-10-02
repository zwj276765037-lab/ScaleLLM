#!/usr/bin/env python3
"""Derive the M04 K/V producer+cache workload from frozen Llama tensors."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

import generate_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
)
LANES = 32
ROWS_PER_BATCH = 4
BATCHES = 16
S24_SCALE = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
COORDINATES = (
    (0, 0, 0, 0),
    (0, 0, 64, 4),
    (0, 15, 31, 1),
    (0, 31, 127, 7),
    (1, 0, 1, 2),
    (1, 15, 63, 5),
    (1, 31, 95, 3),
    (1, 31, 111, 6),
)

sys.path.insert(0, str(EXPERIMENT_ROOT.parent / "model"))
from fixbit_v2 import kv12_quantize_s24  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--output-dir", type=Path,
                        default=MODULE / "data_trace")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
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
    if manifest.get("schema") != "scalellm_modular_llama_trace_v1":
        raise AssertionError("source trace contract mismatch")
    return trace_dir, manifest


def load_source_tensor(
        trace_dir: Path, record: dict[str, object],
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


def quantize_s24(values: np.ndarray) -> tuple[list[int], int]:
    output: list[int] = []
    saturation_count = 0
    for raw in values:
        value = float(raw)
        if not math.isfinite(value):
            raise AssertionError("non-finite K/V trace value")
        rounded = int(np.rint(value * S24_SCALE))
        clipped = min(S24_MAX, max(S24_MIN, rounded))
        output.append(clipped)
        saturation_count += int(clipped != rounded)
    return output, saturation_count


def source_summary(record: dict[str, object]) -> dict[str, object]:
    return {
        "sample": record["sample"], "layer": record["layer"],
        "name": record["name"], "file": record["file"],
        "file_sha256": record["file_sha256"],
        "payload_sha256": record["payload_sha256"],
        "shape": record["shape"],
        "storage_dtype": record["storage_dtype"],
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
    arrays: dict[tuple[int, int, str], np.ndarray] = {}
    used_sources: dict[str, dict[str, object]] = {}
    for sample, layer, _token, _head in COORDINATES:
        for name in ("k_post_rope_bf16", "v_bf16"):
            key = (sample, layer, name)
            if key in arrays:
                continue
            record = tensor_records[key]
            arrays[key] = load_source_tensor(trace_dir, record)
            used_sources[str(record["file"])] = source_summary(record)

    input_batches: list[int] = []
    expected_s12: list[int] = []
    expected_meta: list[int] = []
    expected_fp16: list[int] = []
    expected_fp32: list[int] = []
    raw_reference: list[float] = []
    s24_reference: list[float] = []
    reconstructed_sc: list[float] = []
    reconstructed_fp16: list[float] = []
    reconstructed_fp32: list[float] = []
    provenance: list[dict[str, object]] = []
    s24_saturation_count = 0
    kv12_clip_count = 0
    reserved_minus_2048_count = 0
    zero_scale_records = 0

    for coordinate_index, (sample, layer, token, kv_head) in enumerate(
            COORDINATES):
        for is_v, tensor_name in (
                (0, "k_post_rope_bf16"), (1, "v_bf16")):
            batch = coordinate_index * 2 + is_v
            tensor = arrays[(sample, layer, tensor_name)]
            vector = tensor[token, kv_head]
            if vector.shape != (128,):
                raise AssertionError("unexpected K/V head shape")
            batch_values: list[int] = []
            for group in range(ROWS_PER_BATCH):
                source = vector[group*LANES:(group+1)*LANES]
                s24, saturation = quantize_s24(source)
                quantized = kv12_quantize_s24(s24)
                if any(value == -2048 for value in quantized.values):
                    reserved_minus_2048_count += 1
                scale = (quantized.scale_code /
                         float(1 << quantized.scale_shift)
                         if quantized.scale_code else 0.0)
                lanes16 = [base.ftz16(value / S24_SCALE) for value in s24]
                lanes32 = [np.float32(value / S24_SCALE) for value in s24]

                batch_values.extend(s24)
                expected_s12.append(base.pack_lanes(
                    list(quantized.values), 12))
                expected_meta.append(quantized.metadata)
                expected_fp16.append(base.pack_lanes(
                    [base.fp16_bits(value) for value in lanes16], 16))
                expected_fp32.append(base.pack_lanes(
                    [base.fp32_bits(value) for value in lanes32], 32))
                s24_saturation_count += saturation
                kv12_clip_count += quantized.clip_count
                zero_scale_records += int(quantized.scale_code == 0)
                for raw, fixed, qvalue, value16, value32 in zip(
                        source, s24, quantized.values, lanes16, lanes32,
                        strict=True):
                    raw_reference.append(float(raw))
                    s24_reference.append(fixed / S24_SCALE)
                    reconstructed_sc.append(qvalue * scale)
                    reconstructed_fp16.append(float(value16))
                    reconstructed_fp32.append(float(value32))
            input_batches.append(base.pack_lanes(batch_values, 24))
            provenance.append({
                "batch": batch,
                "kind": "V" if is_v else "K",
                "sample": sample,
                "layer": layer,
                "token": token,
                "kv_head": kv_head,
                "source_tensor": tensor_records[
                    (sample, layer, tensor_name)]["file"],
                "source_payload_sha256": tensor_records[
                    (sample, layer, tensor_name)]["payload_sha256"],
            })

    if (len(input_batches) != BATCHES or
            len(expected_s12) != BATCHES*ROWS_PER_BATCH or
            reserved_minus_2048_count != 0):
        raise AssertionError("M04 trace output contract mismatch")
    outputs = {
        "input_s24.mem": (input_batches, 768),
        "expected_s12.mem": (expected_s12, 96),
        "expected_meta.mem": (expected_meta, 4),
        "expected_fp16.mem": (expected_fp16, 128),
        "expected_fp32.mem": (expected_fp32, 256),
    }
    files: dict[str, dict[str, int | str]] = {}
    for name, (values, digits) in outputs.items():
        base.write_mem(output / name, values, digits)
        files[name] = {
            "records": len(values), "hex_digits": digits,
            "sha256": sha256_file(output / name),
        }
    provenance_path = output / "trace_batches.csv"
    with provenance_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "batch", "kind", "sample", "layer", "token", "kv_head",
            "source_tensor", "source_payload_sha256"))
        writer.writeheader()
        writer.writerows(provenance)
    files[provenance_path.name] = {
        "records": len(provenance), "hex_digits": 0,
        "sha256": sha256_file(provenance_path),
    }

    manifest = {
        "schema": "scalellm_modular_m04_kv_boundary_real_trace_v1",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(
            trace_dir / "manifest.json"),
        "coordinates": [
            {"sample": sample, "layer": layer,
             "token": token, "kv_head": head}
            for sample, layer, token, head in COORDINATES
        ],
        "batches": BATCHES,
        "rows_per_batch": ROWS_PER_BATCH,
        "lanes_per_record": LANES,
        "k_records": 32,
        "v_records": 32,
        "ordering": "alternating K,V batches; each batch contains four consecutive head-dim group32 records",
        "s24_saturation_count": s24_saturation_count,
        "kv12_clip_count": kv12_clip_count,
        "reserved_minus_2048_count": reserved_minus_2048_count,
        "zero_scale_records": zero_scale_records,
        "accuracy_vs_raw_bf16": {
            "s24_input": base.metrics(s24_reference, raw_reference),
            "sc_kv12": base.metrics(reconstructed_sc, raw_reference),
            "fp16": base.metrics(reconstructed_fp16, raw_reference),
            "fp32": base.metrics(reconstructed_fp32, raw_reference),
        },
        "accuracy_vs_common_s24": {
            "sc_kv12": base.metrics(reconstructed_sc, s24_reference),
            "fp16": base.metrics(reconstructed_fp16, s24_reference),
            "fp32": base.metrics(reconstructed_fp32, s24_reference),
        },
        "source_tensors": [
            used_sources[name] for name in sorted(used_sources)
        ],
        "files": files,
        "production_model": str(Path(sys.modules[
            kv12_quantize_s24.__module__].__file__).resolve()),
        "production_model_sha256": sha256_file(Path(sys.modules[
            kv12_quantize_s24.__module__].__file__).resolve()),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M04_TRACE_VECTOR_PASS "
        f"files={len(files)+1} batches={BATCHES} records=64 lanes=32 "
        f"source_tensors={len(used_sources)} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
