#!/usr/bin/env python3
"""Generate 12-seed boundary-inclusive ScaleCode/FP16/FP32 QK vectors."""
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
SHAPES = (128, 112, 64, 32, 16, 1)
SEEDS = tuple(range(2026090801, 2026090813))
GROUPS = 4
LANES = 32
HEAD_SCALE_Q16 = 5793
SCALE_CHOICES = ((0, 0), (1, 8), (255, 16), (73, 20),
                 (201, 22), (127, 18), (255, 32), (17, 14))

sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import (  # noqa: E402
    q24k12_group_dot_s40,
    score_finalize_s20,
    score_group_q14_s35,
)


def pack_lanes(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (lane * width)
               for lane, value in enumerate(values))


def fp16_bits(value: float | np.float16) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.float32) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def bits_fp16(value: int) -> np.float16:
    return np.asarray([value], dtype=np.uint16).view(np.float16)[0]


def bits_fp32(value: int) -> np.float32:
    return np.asarray([value], dtype=np.uint32).view(np.float32)[0]


def ftz16(value: float | np.float16) -> np.float16:
    rounded = np.float16(value)
    bits = fp16_bits(rounded)
    if (bits & 0x7C00) == 0:
        return bits_fp16(bits & 0x8000)
    return rounded


def mul16(a: np.float16, b: np.float16) -> np.float16:
    """Xilinx Floating-Point v7.1 half multiply with denormal flush."""
    with np.errstate(over="ignore", invalid="ignore"):
        product = np.float32(ftz16(a)) * np.float32(ftz16(b))
        normal_round_midpoint = 2.0**-14 * (1.0 - 2.0**-12)
        if product != 0 and abs(float(product)) < normal_round_midpoint:
            return bits_fp16(0x8000 if product < 0 else 0x0000)
        return ftz16(product)


def balanced_sum_f32(values: list[np.float32]) -> np.float32:
    work = [np.float32(value) for value in values]
    if not work or (len(work) & (len(work) - 1)):
        raise ValueError("balanced tree requires a nonzero power-of-two length")
    while len(work) > 1:
        work = [np.float32(work[index] + work[index + 1])
                for index in range(0, len(work), 2)]
    return work[0]


def clip_score(value: int) -> tuple[int, bool]:
    clipped = max(-(16 << 14), min(16 << 14, int(value)))
    return clipped, clipped != value


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (4 * digits)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def error_metrics(values: list[int], golden: list[float]) -> dict[str, float]:
    measured = np.asarray(values, dtype=np.float64) / float(1 << 14)
    reference = np.asarray(golden, dtype=np.float64)
    delta = measured - reference
    denom = np.linalg.norm(measured) * np.linalg.norm(reference)
    cosine = float(np.dot(measured, reference) / denom) if denom else 1.0
    return {
        "max_abs_error": float(np.max(np.abs(delta))),
        "mean_abs_error": float(np.mean(np.abs(delta))),
        "rmse": float(math.sqrt(float(np.mean(delta * delta)))),
        "cosine_similarity": cosine,
    }


def main() -> None:
    query_s24_records: list[int] = []
    query_cache16_records: list[int] = []
    query_cache32_records: list[int] = []
    key_s12_records: list[int] = []
    key_meta_records: list[int] = []
    key_scale16_records: list[int] = []
    key_scale32_records: list[int] = []
    key_cache16_records: list[int] = []
    key_cache32_records: list[int] = []
    row_key_counts: list[int] = []
    masks: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    golden64: list[float] = []
    clip_counts = {"sc": 0, "fp16": 0, "fp32": 0}
    fp16_scale_subnormal_records = 0
    fp16_zero_key_lanes_from_nonzero_inputs = 0

    # Shapes are outermost so every row transition is non-increasing.  This
    # respects the current production row terminal-index update protocol.
    for shape_index, key_count in enumerate(SHAPES):
        for seed_index, seed in enumerate(SEEDS):
            rng = np.random.default_rng(seed ^ (shape_index << 24))
            row_key_counts.append(key_count)
            query_groups: list[list[int]] = []
            query16_groups: list[list[np.float16]] = []
            query32_groups: list[list[np.float32]] = []

            for group in range(GROUPS):
                query_real = np.clip(rng.normal(0.0, 0.70, LANES), -3.5, 3.5)
                fixed = np.clip(np.rint(query_real * (1 << 16)),
                                -(1 << 23), (1 << 23) - 1).astype(np.int64)
                if shape_index == 0 and seed_index == 0 and group == 0:
                    directed = (0, 1 << 16, -(1 << 16), 3 << 15,
                                -(3 << 15), 7 << 16, -(7 << 16), 127 << 16)
                    fixed[:len(directed)] = directed
                fixed_lanes = [int(value) for value in fixed]
                lanes32 = [np.float32(value / float(1 << 16))
                           for value in fixed_lanes]
                lanes16 = [ftz16(np.float16(value)) for value in lanes32]
                if not all(np.isfinite(value) for value in lanes16 + lanes32):
                    raise AssertionError("nonfinite query cache input")
                query_groups.append(fixed_lanes)
                query16_groups.append(lanes16)
                query32_groups.append(lanes32)
                query_s24_records.append(pack_lanes(fixed_lanes, 24))
                query_cache16_records.append(pack_lanes(
                    [fp16_bits(value) for value in lanes16], 16))
                query_cache32_records.append(pack_lanes(
                    [fp32_bits(value) for value in lanes32], 32))

            q16_flat = [value for values in query16_groups for value in values]
            q32_flat = [value for values in query32_groups for value in values]
            q64_flat = [value / float(1 << 16)
                        for values in query_groups for value in values]
            q16_scaled = [mul16(value, bits_fp16(0x2DA8))
                          for value in q16_flat]

            for key in range(key_count):
                sc_groups: list[int] = []
                k16_flat: list[np.float16] = []
                k32_flat: list[np.float32] = []
                k64_flat: list[float] = []
                for group in range(GROUPS):
                    if shape_index == 0 and seed_index == 0 and key < 2:
                        code, shift = 255, 16
                        polarity = 1 if key == 0 else -1
                        fixed_lanes = [
                            polarity * (2047 if value >= 0 else -2047)
                            for value in query_groups[group]
                        ]
                    else:
                        code, shift = SCALE_CHOICES[
                            (seed_index * 5 + shape_index * 3 + key + group) %
                            len(SCALE_CHOICES)]
                        if code == 0:
                            fixed_lanes = [0] * LANES
                        else:
                            sigma = 96.0 if shift <= 14 else 320.0
                            raw = np.clip(np.rint(rng.normal(0.0, sigma, LANES)),
                                          -2047, 2047).astype(np.int64)
                            fixed_lanes = [int(value) for value in raw]

                    scale = 0.0 if code == 0 else code / float(1 << shift)
                    meta = code | (shift << 8)
                    scale16 = np.float16(scale)
                    scale32 = np.float32(scale)
                    scale16_bits = fp16_bits(scale16)
                    if code and (scale16_bits & 0x7C00) == 0:
                        fp16_scale_subnormal_records += 1
                    lanes16 = [mul16(np.float16(value), scale16)
                               for value in fixed_lanes]
                    lanes32 = [np.float32(np.float32(value) * scale32)
                               for value in fixed_lanes]
                    fp16_zero_key_lanes_from_nonzero_inputs += sum(
                        int(value != 0 and fp16_bits(dequant) in (0, 0x8000))
                        for value, dequant in zip(fixed_lanes, lanes16, strict=True))
                    if not all(np.isfinite(value) for value in lanes16 + lanes32):
                        raise AssertionError("nonfinite key cache input")

                    key_s12_records.append(pack_lanes(fixed_lanes, 12))
                    key_meta_records.append(meta)
                    key_scale16_records.append(scale16_bits)
                    key_scale32_records.append(fp32_bits(scale32))
                    key_cache16_records.append(pack_lanes(
                        [fp16_bits(value) for value in lanes16], 16))
                    key_cache32_records.append(pack_lanes(
                        [fp32_bits(value) for value in lanes32], 32))
                    k16_flat.extend(lanes16)
                    k32_flat.extend(lanes32)
                    k64_flat.extend(value * scale for value in fixed_lanes)
                    if code == 0:
                        sc_groups.append(0)
                    else:
                        dot = q24k12_group_dot_s40(
                            query_groups[group], fixed_lanes)
                        sc_groups.append(score_group_q14_s35(dot, code, shift))

                sc_score, sc_clip = score_finalize_s20(sc_groups)
                products16 = [np.float32(mul16(qvalue, kvalue))
                              for qvalue, kvalue in zip(
                                  q16_scaled, k16_flat, strict=True)]
                sum16 = balanced_sum_f32(products16)
                score16, clip16 = clip_score(
                    int(np.rint(float(sum16) * (1 << 14))))
                products32 = [np.float32(qvalue * kvalue)
                              for qvalue, kvalue in zip(
                                  q32_flat, k32_flat, strict=True)]
                sum32 = balanced_sum_f32(products32)
                scaled32 = np.float32(sum32 * bits_fp32(0x3DB50800))
                score32, clip32 = clip_score(
                    int(np.rint(float(scaled32) * (1 << 14))))
                reference = float(np.dot(
                    np.asarray(q64_flat, dtype=np.float64),
                    np.asarray(k64_flat, dtype=np.float64)) *
                    (HEAD_SCALE_Q16 / float(1 << 16)))
                if not (np.isfinite(sum16) and np.isfinite(scaled32) and
                        math.isfinite(reference)):
                    raise AssertionError("nonfinite boundary QK result")

                expected_sc.append(sc_score)
                expected16.append(score16)
                expected32.append(score32)
                golden64.append(max(-16.0, min(16.0, reference)))
                clip_counts["sc"] += int(sc_clip)
                clip_counts["fp16"] += int(clip16)
                clip_counts["fp32"] += int(clip32)
                masks.append(int(key != 0 and
                                 (key + 3 * shape_index + seed_index) % 17 == 0))

    rows = len(SHAPES) * len(SEEDS)
    scores = sum(SHAPES) * len(SEEDS)
    key_groups = scores * GROUPS
    if not (len(row_key_counts) == rows and
            len(query_s24_records) == rows * GROUPS and
            len(key_s12_records) == key_groups and
            len(expected_sc) == scores and len(masks) == scores):
        raise AssertionError("boundary record count mismatch")

    OUT.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "query_group_s24.mem": (query_s24_records, 192),
        "query_cache_fp16.mem": (query_cache16_records, 128),
        "query_cache_fp32.mem": (query_cache32_records, 256),
        "key_group_s12.mem": (key_s12_records, 96),
        "key_meta_sc_u16.mem": (key_meta_records, 4),
        "key_scale_fp16.mem": (key_scale16_records, 4),
        "key_scale_fp32.mem": (key_scale32_records, 8),
        "key_cache_fp16.mem": (key_cache16_records, 128),
        "key_cache_fp32.mem": (key_cache32_records, 256),
        "mask.mem": (masks, 1),
        "expected_sc.mem": (expected_sc, 5),
        "expected_fp16.mem": (expected16, 5),
        "expected_fp32.mem": (expected32, 5),
        "clip_count_sc.mem": ([clip_counts["sc"]], 8),
        "clip_count_fp16.mem": ([clip_counts["fp16"]], 8),
        "clip_count_fp32.mem": ([clip_counts["fp32"]], 8),
    }
    file_schema: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)
        file_schema[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(OUT / filename),
        }

    manifest = {
        "schema": "scalellm_modular_qk_boundary_inclusive_v1",
        "seeds": list(SEEDS),
        "shapes": list(SHAPES),
        "row_schedule": "shape descending outer, seed inner",
        "rows": rows,
        "scores": scores,
        "key_groups": key_groups,
        "groups_per_score": GROUPS,
        "lanes_per_group": LANES,
        "common_input": "Q S24 Q8.16 and K S12 plus native scale metadata",
        "common_output": "signed S20 Q6.14 with explicit +/-16 clip",
        "input_cadence_target": "one group32 every two cycles",
        "output_cadence_target": "one score every eight cycles",
        "numeric_models": {
            "sc": "production fixed dot, ScaleCode group shift, accum4, clip",
            "fp16": "S24/S12 to FP32 to FP16; explicit FP16 K scale multiply with FTZ; existing balanced QK",
            "fp32": "S24/S12 to FP32; explicit FP32 K scale multiply; existing balanced QK",
            "reference": "FP64 dequantized QK dot times 5793/65536",
        },
        "coverage": {
            "fp16_scale_subnormal_records": fp16_scale_subnormal_records,
            "fp16_zero_key_lanes_from_nonzero_inputs":
                fp16_zero_key_lanes_from_nonzero_inputs,
        },
        "clip_counts": clip_counts,
        "accuracy_vs_clipped_fp64": {
            "sc": error_metrics(expected_sc, golden64),
            "fp16": error_metrics(expected16, golden64),
            "fp32": error_metrics(expected32, golden64),
        },
        "files": file_schema,
        "production_model": str(ROOT / "model" / "fixbit_v2.py"),
        "production_model_sha256": sha256_file(ROOT / "model" / "fixbit_v2.py"),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M05_BOUNDARY_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M05 12-seed boundary-inclusive QK vectors generated")


if __name__ == "__main__":
    main()
