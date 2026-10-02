#!/usr/bin/env python3
"""Generate matched four-row S24 to KV12/direct-FP cache-boundary vectors."""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE.parent / "data"
BATCHES = 16
ROWS_PER_BATCH = 4
LANES = 32
SEED = 20260908

sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import kv12_quantize_s24  # noqa: E402


def pack_lanes(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (lane * width)
               for lane, value in enumerate(values))


def bits_fp16(bits: int) -> np.float16:
    return np.asarray([bits], dtype=np.uint16).view(np.float16)[0]


def ftz16(value: float) -> np.float16:
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        return bits_fp16(bits & 0x8000)
    return rounded


def fp16_bits(value: float) -> int:
    return int(ftz16(value).view(np.uint16))


def fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (4 * digits)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(measured: list[float], reference: list[float]) -> dict[str, float]:
    a = np.asarray(measured, dtype=np.float64)
    b = np.asarray(reference, dtype=np.float64)
    d = a - b
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return {
        "max_abs_error": float(np.max(np.abs(d))),
        "mean_abs_error": float(np.mean(np.abs(d))),
        "rmse": float(math.sqrt(float(np.mean(d*d)))),
        "cosine_similarity": float(np.dot(a, b) / denom) if denom else 1.0,
    }


def make_record(rng: np.random.Generator, record_index: int) -> list[int]:
    if record_index == 0:
        return [0] * LANES
    if record_index == 1:
        directed = [-(1 << 23), (1 << 23) - 1, 0, 1, -1, 2, -2, 3,
                    -3, 4, -4, 5, -5, 1 << 16, -(1 << 16), 1 << 15,
                    -(1 << 15), 2047, -2047, 65535, -65535]
        return directed + [((lane * 65537) & 0x7FFFFF) - 0x400000
                           for lane in range(LANES-len(directed))]
    if record_index == 2:
        return [((1 << 22) if lane & 1 else -(1 << 22))
                for lane in range(LANES)]
    if record_index == 3:
        return [record_index * 4096 - 32768] * LANES
    if record_index % 7 == 0:
        raw = rng.standard_t(df=3, size=LANES) * (1 << 18)
    else:
        raw = rng.normal(0.0, 1 << (12 + record_index % 10), LANES)
    clipped = np.clip(np.rint(raw), -(1 << 23), (1 << 23) - 1)
    return [int(value) for value in clipped]


def main() -> None:
    rng = np.random.default_rng(SEED)
    input_batches: list[int] = []
    expected_s12: list[int] = []
    expected_meta: list[int] = []
    expected_fp16: list[int] = []
    expected_fp32: list[int] = []
    reference: list[float] = []
    reconstructed_sc: list[float] = []
    reconstructed_fp16: list[float] = []
    reconstructed_fp32: list[float] = []
    sc_clip_count = 0
    reserved_code_count = 0

    for batch in range(BATCHES):
        batch_values: list[int] = []
        for row in range(ROWS_PER_BATCH):
            record_index = batch * ROWS_PER_BATCH + row
            values = make_record(rng, record_index)
            result = kv12_quantize_s24(values)
            if any(value == -2048 for value in result.values):
                reserved_code_count += 1
            expected_s12.append(pack_lanes(list(result.values), 12))
            expected_meta.append(result.metadata)
            sc_clip_count += result.clip_count

            fp16_values = [ftz16(value / float(1 << 16)) for value in values]
            fp32_values = [np.float32(value / float(1 << 16))
                           for value in values]
            expected_fp16.append(pack_lanes(
                [int(value.view(np.uint16)) for value in fp16_values], 16))
            expected_fp32.append(pack_lanes(
                [fp32_bits(float(value)) for value in fp32_values], 32))
            batch_values.extend(values)

            for value, qvalue, f16value, f32value in zip(
                    values, result.values, fp16_values, fp32_values):
                source_real = value / float(1 << 16)
                reference.append(source_real)
                reconstructed_sc.append(
                    qvalue * result.scale_code / float(1 << result.scale_shift)
                    if result.scale_code else 0.0)
                reconstructed_fp16.append(float(f16value))
                reconstructed_fp32.append(float(f32value))
        input_batches.append(pack_lanes(batch_values, 24))

    if reserved_code_count != 0:
        raise AssertionError("KV12 generated reserved -2048")
    if len(input_batches) != BATCHES or len(expected_s12) != BATCHES*4:
        raise AssertionError("record count mismatch")

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "input_s24.mem": (input_batches, 768),
        "expected_s12.mem": (expected_s12, 96),
        "expected_meta.mem": (expected_meta, 4),
        "expected_fp16.mem": (expected_fp16, 128),
        "expected_fp32.mem": (expected_fp32, 256),
    }
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)

    manifest = {
        "schema": "scalellm_modular_kv_boundary_v1",
        "seed": SEED,
        "batches": BATCHES,
        "rows_per_batch": ROWS_PER_BATCH,
        "lanes_per_record": LANES,
        "input": "signed S24 Q8.16",
        "formats": {
            "sc": "32xS12 plus ScaleCode meta16",
            "fp16": "32 fully dequantized IEEE FP16 lanes; subnormals FTZ",
            "fp32": "32 fully dequantized IEEE FP32 lanes",
        },
        "record_bits": {"sc": 400, "fp16": 512, "fp32": 1024},
        "sc_clip_count": sc_clip_count,
        "sc_reserved_minus_2048_count": reserved_code_count,
        "accuracy_vs_s24_real": {
            "sc": metrics(reconstructed_sc, reference),
            "fp16": metrics(reconstructed_fp16, reference),
            "fp32": metrics(reconstructed_fp32, reference),
        },
        "sha256": {filename: sha256_file(OUT / filename)
                   for filename in outputs},
        "production_model": str(ROOT / "model" / "fixbit_v2.py"),
        "production_model_sha256": sha256_file(ROOT / "model" / "fixbit_v2.py"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M4_KV_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M4 KV boundary vectors generated")


if __name__ == "__main__":
    main()
