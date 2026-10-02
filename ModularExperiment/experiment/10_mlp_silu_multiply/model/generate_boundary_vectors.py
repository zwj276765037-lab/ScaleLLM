#!/usr/bin/env python3
"""Generate the formal 12-seed M10 Gate/Up-to-SwiGLU boundary workload."""
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
OUT = HERE.parent / "data_boundary"
SEEDS = tuple(range(2026091201, 2026091213))
VECTORS_PER_SEED = 512
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1

sys.path.insert(0, str(ROOT / "model"))
from mlp_fixed import build_silu_lut, silu_real, swiglu_product_s32  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp16_bits(value: float | np.float16) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.float32) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (digits * 4)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def fixed_s32(value: float) -> tuple[int, bool]:
    if math.isnan(value):
        return 0, True
    if math.isinf(value):
        return ((1 << 31) - 1 if value > 0 else -(1 << 31)), True
    raw = int(np.rint(value * 65536.0))
    clipped = min((1 << 31) - 1, max(-(1 << 31), raw))
    return clipped, clipped != raw


def fp_swiglu(gate: int, up: int, width: int) -> tuple[int, bool]:
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if width == 16:
            gate_fp = np.float16(gate / 65536.0)
            up_fp = np.float16(up / 65536.0)
            exponential = np.exp(np.float16(-gate_fp), dtype=np.float16)
            denominator = np.float16(np.float16(1.0) + exponential)
            silu = np.float16(gate_fp / denominator)
            product = np.float16(silu * up_fp)
        elif width == 32:
            gate_fp = np.float32(gate / 65536.0)
            up_fp = np.float32(up / 65536.0)
            exponential = np.exp(np.float32(-gate_fp), dtype=np.float32)
            denominator = np.float32(np.float32(1.0) + exponential)
            silu = np.float32(gate_fp / denominator)
            product = np.float32(silu * up_fp)
        else:
            raise ValueError("M10 FP width must be 16 or 32")
    return fixed_s32(float(product))


def build_seed_vectors(seed_index: int, seed: int) -> tuple[list[int], list[int]]:
    rng = np.random.default_rng(seed)
    gate = np.clip(np.rint(rng.normal(0.0, 18.0, VECTORS_PER_SEED) * 65536.0),
                   S24_MIN, S24_MAX).astype(np.int64)
    up = np.clip(np.rint(rng.normal(0.0, 24.0, VECTORS_PER_SEED) * 65536.0),
                 S24_MIN, S24_MAX).astype(np.int64)
    if seed_index == 0:
        directed = (
            (0, 0), (1, 1), (-1, 1), (1 << 16, 1 << 16),
            (-(1 << 16), 1 << 16), (8 << 16, -(3 << 16)),
            (-(8 << 16), 3 << 16), (16 << 16, 16 << 16),
            (-(16 << 16), 16 << 16), (S24_MAX, S24_MAX),
            (S24_MIN, S24_MAX), (S24_MAX, S24_MIN),
            (S24_MIN, S24_MIN), ((16 << 16) - 1, -(16 << 16)),
            ((-16 << 16) + 1, 16 << 16), (127 << 16, -(127 << 16)),
        )
        for index, (gate_value, up_value) in enumerate(directed):
            gate[index] = gate_value
            up[index] = up_value
    return [int(value) for value in gate], [int(value) for value in up]


def error_metrics(values: list[int], golden: list[float]) -> dict[str, float]:
    measured = np.asarray(values, dtype=np.float64) / 65536.0
    reference = np.asarray(golden, dtype=np.float64)
    delta = measured - reference
    denominator = np.linalg.norm(measured) * np.linalg.norm(reference)
    cosine = float(np.dot(measured, reference) / denominator) \
        if denominator else 1.0
    return {
        "max_abs_error": float(np.max(np.abs(delta))),
        "mean_abs_error": float(np.mean(np.abs(delta))),
        "rmse": float(math.sqrt(float(np.mean(delta * delta)))),
        "cosine_similarity": cosine,
    }


def main() -> None:
    table = build_silu_lut()
    gate_records: list[int] = []
    up_records: list[int] = []
    gate16_records: list[int] = []
    up16_records: list[int] = []
    gate32_records: list[int] = []
    up32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    ideal64: list[float] = []
    saturation = {"fp16": 0, "fp32": 0}

    for seed_index, seed in enumerate(SEEDS):
        gates, ups = build_seed_vectors(seed_index, seed)
        for gate, up in zip(gates, ups, strict=True):
            gate_real = gate / 65536.0
            up_real = up / 65536.0
            value16, sat16 = fp_swiglu(gate, up, 16)
            value32, sat32 = fp_swiglu(gate, up, 32)
            gate_records.append(gate)
            up_records.append(up)
            gate16_records.append(fp16_bits(gate_real))
            up16_records.append(fp16_bits(up_real))
            gate32_records.append(fp32_bits(gate_real))
            up32_records.append(fp32_bits(up_real))
            expected_sc.append(swiglu_product_s32(gate, up, table))
            expected16.append(value16)
            expected32.append(value32)
            ideal64.append(silu_real(gate_real) * up_real)
            saturation["fp16"] += int(sat16)
            saturation["fp32"] += int(sat32)

    vectors = len(SEEDS) * VECTORS_PER_SEED
    if not (len(gate_records) == len(up_records) == len(expected_sc) == vectors):
        raise AssertionError("M10 boundary vector count mismatch")
    OUT.mkdir(parents=True, exist_ok=True)
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
        write_mem(OUT / filename, values, digits)
        files[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(OUT / filename),
        }
    production_model = ROOT / "model" / "mlp_fixed.py"
    manifest = {
        "schema": "scalellm_modular_silu_boundary_inclusive_v1",
        "seeds": list(SEEDS),
        "vectors_per_seed": VECTORS_PER_SEED,
        "vectors": vectors,
        "common_input": "Gate S24 Q8.16 and Up S24 Q8.16",
        "common_output": "signed S32 Q16.16 SwiGLU product",
        "input_cadence_target": "two independent lanes, one element per lane per cycle",
        "coverage": {
            "zero_gate_records": sum(value == 0 for value in gate_records),
            "positive_gate_records": sum(value > 0 for value in gate_records),
            "negative_gate_records": sum(value < 0 for value in gate_records),
            "gate_below_silu_lut": sum(value <= -(16 << 16)
                                       for value in gate_records),
            "gate_above_silu_lut": sum(value >= (16 << 16)
                                       for value in gate_records),
            "s24_endpoint_records": sum(
                value in (S24_MIN, S24_MAX)
                for value in gate_records + up_records),
        },
        "saturation_counts": saturation,
        "software_accuracy_vs_fp64": {
            "sc": error_metrics(expected_sc, ideal64),
            "fp16": error_metrics(expected16, ideal64),
            "fp32": error_metrics(expected32, ideal64),
        },
        "numeric_models": {
            "sc": "production 8192-entry SiLU LUT and round-away-zero product",
            "fp16": "fixed-to-FP16 then exp/add/div/multiply in native FP16",
            "fp32": "fixed-to-FP32 then exp/add/div/multiply in native FP32",
            "reference": "stable FP64 SiLU(gate)*up",
        },
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M10_BOUNDARY_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M10 12-seed Gate/Up boundary vectors generated")


if __name__ == "__main__":
    main()
