#!/usr/bin/env python3
"""Generate deterministic matched ScaleCode/FP16/FP32 QK score vectors."""
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
# Production has no row_key_count port: in_last_key updates the terminal index
# only when the final input group arrives.  Descending N guarantees that update
# precedes the corresponding terminal output without an inter-row clear.
SHAPES = (128, 112, 64, 32, 16, 1)
GROUPS = 4
LANES = 32
HEAD_SCALE_Q16 = 5793
SEED = 20260908

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
    bits = int(rounded.view(np.uint16))
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
    rng = np.random.default_rng(SEED)
    query_fixed_records: list[int] = []
    query16_records: list[int] = []
    query32_records: list[int] = []
    key_fixed_records: list[int] = []
    key_meta_records: list[int] = []
    key16_records: list[int] = []
    key32_records: list[int] = []
    masks: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    golden64: list[float] = []
    clip_counts = {"sc": 0, "fp16": 0, "fp32": 0}
    scale_choices = ((0, 0), (1, 8), (255, 16), (73, 20),
                     (201, 22), (127, 18), (255, 32), (17, 14))

    for shape_index, key_count in enumerate(SHAPES):
        query_groups: list[list[int]] = []
        query16_groups: list[list[np.float16]] = []
        query32_groups: list[list[np.float32]] = []
        for group in range(GROUPS):
            query_real = rng.normal(0.0, 0.70, LANES)
            query_real = np.clip(query_real, -3.5, 3.5)
            fixed = np.rint(query_real * (1 << 16)).astype(np.int64)
            fixed = np.clip(fixed, -(1 << 23), (1 << 23) - 1)
            if shape_index == 0 and group == 0:
                # Exact directed cases remain finite after FP16 prescaling.
                directed = (0, 1 << 16, -(1 << 16), (3 << 15),
                            -(3 << 15), (7 << 16), -(7 << 16), 127 << 16)
                fixed[:len(directed)] = directed
            fixed_lanes = [int(value) for value in fixed]
            lanes16 = [np.float16(value / float(1 << 16))
                       for value in fixed_lanes]
            lanes32 = [np.float32(value / float(1 << 16))
                       for value in fixed_lanes]
            if not all(np.isfinite(value) for value in lanes16 + lanes32):
                raise AssertionError("nonfinite query input")
            query_groups.append(fixed_lanes)
            query16_groups.append(lanes16)
            query32_groups.append(lanes32)
            query_fixed_records.append(pack_lanes(fixed_lanes, 24))
            query16_records.append(pack_lanes(
                [fp16_bits(value) for value in lanes16], 16))
            query32_records.append(pack_lanes(
                [fp32_bits(value) for value in lanes32], 32))

        q16_flat = [value for group in query16_groups for value in group]
        q32_flat = [value for group in query32_groups for value in group]
        q64_flat = [value / float(1 << 16)
                    for group in query_groups for value in group]
        q16_scaled = [mul16(value, bits_fp16(0x2DA8))
                      for value in q16_flat]

        for key in range(key_count):
            sc_groups: list[int] = []
            k16_flat: list[np.float16] = []
            k32_flat: list[np.float32] = []
            k64_flat: list[float] = []
            for group in range(GROUPS):
                if shape_index == 0 and key < 2:
                    # Two explicit positive/negative saturation vectors.
                    code, shift = 255, 16
                    polarity = 1 if key == 0 else -1
                    fixed_lanes = [polarity * (2047 if value >= 0 else -2047)
                                   for value in query_groups[group]]
                    scale = code / float(1 << shift)
                else:
                    code, shift = scale_choices[
                        (shape_index * 3 + key + group) % len(scale_choices)]
                if code == 0:
                    fixed_lanes = [0] * LANES
                    scale = 0.0
                elif not (shape_index == 0 and key < 2):
                    sigma = 96.0 if shift <= 14 else 320.0
                    raw = np.rint(rng.normal(0.0, sigma, LANES)).astype(np.int64)
                    raw = np.clip(raw, -2047, 2047)
                    fixed_lanes = [int(value) for value in raw]
                    scale = code / float(1 << shift)
                meta = code | (shift << 8)
                lanes16 = [np.float16(value * scale) for value in fixed_lanes]
                lanes32 = [np.float32(value * scale) for value in fixed_lanes]
                if not all(np.isfinite(value) for value in lanes16 + lanes32):
                    raise AssertionError("nonfinite key input")
                key_fixed_records.append(pack_lanes(fixed_lanes, 12))
                key_meta_records.append(meta)
                key16_records.append(pack_lanes(
                    [fp16_bits(value) for value in lanes16], 16))
                key32_records.append(pack_lanes(
                    [fp32_bits(value) for value in lanes32], 32))
                k16_flat.extend(lanes16)
                k32_flat.extend(lanes32)
                k64_flat.extend(value * scale for value in fixed_lanes)
                if code == 0:
                    sc_groups.append(0)
                else:
                    dot = q24k12_group_dot_s40(query_groups[group], fixed_lanes)
                    sc_groups.append(score_group_q14_s35(dot, code, shift))

            sc_score, sc_clip = score_finalize_s20(sc_groups)
            products16 = [np.float32(mul16(qvalue, kvalue))
                          for qvalue, kvalue in zip(q16_scaled, k16_flat)]
            sum16 = balanced_sum_f32(products16)
            raw16 = int(np.rint(float(sum16) * (1 << 14)))
            score16, clip16 = clip_score(raw16)
            products32 = [np.float32(qvalue * kvalue)
                          for qvalue, kvalue in zip(q32_flat, k32_flat)]
            sum32 = balanced_sum_f32(products32)
            scaled32 = np.float32(sum32 * bits_fp32(0x3DB50800))
            raw32 = int(np.rint(float(scaled32) * (1 << 14)))
            score32, clip32 = clip_score(raw32)
            reference = float(np.dot(np.asarray(q64_flat, dtype=np.float64),
                                     np.asarray(k64_flat, dtype=np.float64)) *
                              (HEAD_SCALE_Q16 / float(1 << 16)))
            if not (np.isfinite(sum16) and np.isfinite(scaled32) and
                    math.isfinite(reference)):
                raise AssertionError("nonfinite QK result")
            expected_sc.append(sc_score)
            expected16.append(score16)
            expected32.append(score32)
            golden64.append(max(-16.0, min(16.0, reference)))
            clip_counts["sc"] += int(sc_clip)
            clip_counts["fp16"] += int(clip16)
            clip_counts["fp32"] += int(clip32)
            masks.append(int(key != 0 and (key + 3 * shape_index) % 17 == 0))

    total_scores = sum(SHAPES)
    total_groups = GROUPS * total_scores
    lengths = {
        "query_records": len(query_fixed_records),
        "key_groups": len(key_fixed_records),
        "scores": len(expected_sc),
    }
    if lengths != {"query_records": len(SHAPES) * GROUPS,
                   "key_groups": total_groups,
                   "scores": total_scores}:
        raise AssertionError(f"record count mismatch: {lengths}")

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "query_group_fixed.mem": (query_fixed_records, 192),
        "query_group_fp16.mem": (query16_records, 128),
        "query_group_fp32.mem": (query32_records, 256),
        "key_group_fixed.mem": (key_fixed_records, 96),
        "key_meta_fixed.mem": (key_meta_records, 4),
        "key_group_fp16.mem": (key16_records, 128),
        "key_group_fp32.mem": (key32_records, 256),
        "mask.mem": (masks, 1),
        "expected_sc.mem": (expected_sc, 5),
        "expected_fp16.mem": (expected16, 5),
        "expected_fp32.mem": (expected32, 5),
        "clip_count_sc.mem": ([clip_counts["sc"]], 8),
        "clip_count_fp16.mem": ([clip_counts["fp16"]], 8),
        "clip_count_fp32.mem": ([clip_counts["fp32"]], 8),
    }
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)

    manifest = {
        "schema": "scalellm_modular_qk_matched_v1",
        "seed": SEED,
        "shapes": list(SHAPES),
        "head_dim": GROUPS * LANES,
        "groups_per_score": GROUPS,
        "scores": total_scores,
        "key_groups": total_groups,
        "input_cadence_target": "one group32 every two cycles",
        "output_cadence_target": "one score every eight cycles",
        "common_output": "signed S20 Q6.14 with explicit +/-16 clip",
        "numeric_models": {
            "sc": "current fixbit_v2 exact dot/group-scale/truncate/accumulate/clip",
            "fp16": "FP16 query prescale and product with FTZ; balanced FP32 tree",
            "fp32": "FP32 products; balanced FP32 tree and head scale",
            "reference": "FP64 dequantized QK dot times current 5793/65536 head scale",
        },
        "clip_counts": clip_counts,
        "accuracy_vs_clipped_fp64": {
            "sc": error_metrics(expected_sc, golden64),
            "fp16": error_metrics(expected16, golden64),
            "fp32": error_metrics(expected32, golden64),
        },
        "record_counts": lengths,
        "sha256": {filename: sha256_file(OUT / filename)
                   for filename in outputs},
        "production_model": str(ROOT / "model" / "fixbit_v2.py"),
        "production_model_sha256": sha256_file(ROOT / "model" / "fixbit_v2.py"),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M5_QK_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M5 matched QK vectors generated")


if __name__ == "__main__":
    main()
