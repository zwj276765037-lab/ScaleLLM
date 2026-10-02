#!/usr/bin/env python3
"""Generate the frozen 128-group projection-tail -> RoPE pair workload."""

from __future__ import annotations

import hashlib
import json
import math
import random
import struct
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data_boundary"
GROUPS = 128
SEEDS = tuple(range(0x30301, 0x3030D))
PAIRS = len(SEEDS)
MASK21 = (1 << 21) - 1
MASK24 = (1 << 24) - 1


def fp32(value: float | np.floating) -> np.float32:
    return np.float32(value)


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(fp32(value))))[0]


def fp16_ftz(value: float | np.floating) -> np.float16:
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        return np.float16(-0.0 if bits & 0x8000 else 0.0)
    return rounded


def fp16_bits(value: float | np.floating) -> int:
    return int(fp16_ftz(value).view(np.uint16))


def fp16_mul(a: np.float16, b: np.float16) -> np.float16:
    return fp16_ftz(fp32(fp16_ftz(a)) * fp32(fp16_ftz(b)))


def fp16_add(a: np.float16, b: np.float16) -> np.float16:
    return fp16_ftz(fp32(fp16_ftz(a)) + fp32(fp16_ftz(b)))


def fp16_sub(a: np.float16, b: np.float16) -> np.float16:
    return fp16_ftz(fp32(fp16_ftz(a)) - fp32(fp16_ftz(b)))


def sat24(value: int) -> int:
    return min((1 << 23) - 1, max(-(1 << 23), value))


def round_s42_q24_to_s24_q16(value: int) -> int:
    if value < 0:
        magnitude = -value
        rounded = -((magnitude + 128) >> 8)
    else:
        rounded = (value + 128) >> 8
    return sat24(rounded)


def round_s41_q32_to_s25_q16(value: int) -> int:
    return (value + (32767 if value < 0 else 32768)) >> 16


def sc_rope(x0_s24: int, x1_s24: int, cos_s18: int,
            sin_s18: int) -> tuple[int, int]:
    x0_cos = round_s41_q32_to_s25_q16(x0_s24 * cos_s18)
    x1_sin = round_s41_q32_to_s25_q16(x1_s24 * sin_s18)
    x0_sin = round_s41_q32_to_s25_q16(x0_s24 * sin_s18)
    x1_cos = round_s41_q32_to_s25_q16(x1_s24 * cos_s18)
    return sat24(x0_cos - x1_sin), sat24(x0_sin + x1_cos)


def fp_to_s24(value: np.float32) -> int:
    if not np.isfinite(value):
        return (1 << 23) - 1 if not np.signbit(value) else -(1 << 23)
    return sat24(int(np.rint(float(value) * float(1 << 16))))


def fp32_add(a: np.float32, b: np.float32) -> np.float32:
    return fp32(fp32(a) + fp32(b))


def reduce_six(values: list[np.float32]) -> np.float32:
    """Frozen balanced reduction used by the six-bank matched-II baseline."""
    s01 = fp32_add(values[0], values[1])
    s23 = fp32_add(values[2], values[3])
    s45 = fp32_add(values[4], values[5])
    s0123 = fp32_add(s01, s23)
    return fp32_add(s0123, s45)


def fp32_rope(x0: np.float32, x1: np.float32, cos_s18: int,
              sin_s18: int) -> tuple[int, int]:
    cos_value = fp32(cos_s18 / float(1 << 16))
    sin_value = fp32(sin_s18 / float(1 << 16))
    p0 = fp32(x0 * cos_value)
    p1 = fp32(x1 * sin_value)
    p2 = fp32(x0 * sin_value)
    p3 = fp32(x1 * cos_value)
    return fp_to_s24(fp32(p0 - p1)), fp_to_s24(fp32(p2 + p3))


def fp16_rope(x0_fp32: np.float32, x1_fp32: np.float32, cos_s18: int,
              sin_s18: int) -> tuple[int, int]:
    x0 = fp16_ftz(x0_fp32)
    x1 = fp16_ftz(x1_fp32)
    cos_value = fp16_ftz(fp32(cos_s18 / float(1 << 16)))
    sin_value = fp16_ftz(fp32(sin_s18 / float(1 << 16)))
    p0 = fp16_mul(x0, cos_value)
    p1 = fp16_mul(x1, sin_value)
    p2 = fp16_mul(x0, sin_value)
    p3 = fp16_mul(x1, cos_value)
    y0 = fp16_sub(p0, p1)
    y1 = fp16_add(p2, p3)
    return fp_to_s24(fp32(y0)), fp_to_s24(fp32(y1))


def pack_pair(y0: int, y1: int) -> int:
    return ((y1 & MASK24) << 24) | (y0 & MASK24)


def metrics(actual: list[tuple[int, int]],
            reference: list[tuple[float, float]],
            indices: list[int] | None = None) -> dict[str, float]:
    if indices is not None:
        actual = [actual[index] for index in indices]
        reference = [reference[index] for index in indices]
    actual_array = np.asarray(actual, dtype=np.float64).reshape(-1) / (1 << 16)
    reference_array = np.asarray(reference, dtype=np.float64).reshape(-1)
    error = actual_array - reference_array
    denominator = (np.linalg.norm(actual_array) *
                   np.linalg.norm(reference_array))
    cosine = float(np.dot(actual_array, reference_array) / denominator)
    return {
        "max_abs_error": float(np.max(np.abs(error))),
        "mean_abs_error": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "cosine_similarity": cosine,
    }


def main() -> None:
    group_records: list[dict[str, int | float | np.float16 | np.float32]] = []
    coefficients: list[tuple[int, int]] = []
    expected_sc: list[tuple[int, int]] = []
    expected_fp16: list[tuple[int, int]] = []
    expected_fp32: list[tuple[int, int]] = []
    reference: list[tuple[float, float]] = []
    saturation_pairs = 0
    fp16_zero_contributions = 0
    total_shifts: list[int] = []

    for pair_index, seed in enumerate(SEEDS):
        rng = random.Random(seed)
        if pair_index == 0:
            cos_s18, sin_s18 = 65536, 0
        elif pair_index == 1:
            cos_s18, sin_s18 = 46341, 46341
        else:
            angle = rng.uniform(-math.pi, math.pi)
            cos_s18 = max(-65536, min(65536,
                int(round(math.cos(angle) * (1 << 16)))))
            sin_s18 = max(-65536, min(65536,
                int(round(math.sin(angle) * (1 << 16)))))
        coefficients.append((cos_s18, sin_s18))

        sc_accum = [0, 0]
        fp16_banks = [[fp32(0.0) for _ in range(6)] for _ in range(2)]
        fp32_banks = [[fp32(0.0) for _ in range(6)] for _ in range(2)]
        exact_accum = [0.0, 0.0]

        for group in range(GROUPS):
            if pair_index == 0:
                corr0 = corr1 = 0
                act_code = weight0_code = weight1_code = 1
                act_shift = weight0_shift = weight1_shift = 15
            elif pair_index == 1:
                corr0, corr1 = 50000, -45000
                act_code = weight0_code = weight1_code = 255
                act_shift = weight0_shift = weight1_shift = 15
            elif pair_index == 2 and group == 0:
                # Exercise the minimum legal production total shift.
                corr0, corr1 = 1, -1
                act_code, weight0_code, weight1_code = 1, 1, 1
                act_shift, weight0_shift, weight1_shift = 13, 13, 13
            elif pair_index == 2 and group == 1:
                # Exercise the maximum legal production total shift and an
                # FP16 scale underflow without perturbing the batch range.
                corr0, corr1 = 30000, -30000
                act_code, weight0_code, weight1_code = 1, 1, 1
                act_shift, weight0_shift, weight1_shift = 20, 27, 27
            else:
                corr0 = rng.randrange(-30000, 30001)
                corr1 = rng.randrange(-30000, 30001)
                act_code = rng.randrange(32, 256)
                weight0_code = rng.randrange(32, 256)
                weight1_code = rng.randrange(32, 256)
                total_shift0 = rng.randrange(30, 37)
                total_shift1 = rng.randrange(30, 37)
                low = max(13, total_shift0 - 20, total_shift1 - 20)
                high = min(20, total_shift0 - 13, total_shift1 - 13)
                act_shift = rng.randrange(low, high + 1)
                weight0_shift = total_shift0 - act_shift
                weight1_shift = total_shift1 - act_shift

            act_scale = act_code / float(1 << act_shift)
            weight0_scale = weight0_code / float(1 << weight0_shift)
            weight1_scale = weight1_code / float(1 << weight1_shift)
            correlation = (corr0, corr1)
            weight_code = (weight0_code, weight1_code)
            weight_shift = (weight0_shift, weight1_shift)
            weight_scale = (weight0_scale, weight1_scale)
            bank = group % 6
            total_shifts.extend((act_shift + weight0_shift,
                                 act_shift + weight1_shift))

            for lane in range(2):
                raw = correlation[lane] * act_code * weight_code[lane]
                total_shift = act_shift + weight_shift[lane]
                sc_accum[lane] += raw >> (total_shift - 24)
                exact_accum[lane] += (correlation[lane] * act_scale *
                                      weight_scale[lane])

                corr16 = fp16_ftz(fp32(correlation[lane]))
                act16 = fp16_ftz(fp32(act_scale))
                weight16 = fp16_ftz(fp32(weight_scale[lane]))
                contribution16 = fp16_mul(fp16_mul(corr16, act16), weight16)
                if (fp16_bits(contribution16) & 0x7FFF) == 0:
                    fp16_zero_contributions += 1
                fp16_banks[lane][bank] = fp32_add(
                    fp16_banks[lane][bank], fp32(contribution16))

                contribution32 = fp32(
                    fp32(fp32(correlation[lane]) * fp32(act_scale)) *
                    fp32(weight_scale[lane]))
                fp32_banks[lane][bank] = fp32_add(
                    fp32_banks[lane][bank], contribution32)

            group_records.append({
                "corr0": corr0,
                "corr1": corr1,
                "act_code": act_code,
                "act_shift": act_shift,
                "weight0_code": weight0_code,
                "weight0_shift": weight0_shift,
                "weight1_code": weight1_code,
                "weight1_shift": weight1_shift,
                "act_scale": act_scale,
                "weight0_scale": weight0_scale,
                "weight1_scale": weight1_scale,
            })

        projection_sc = [round_s42_q24_to_s24_q16(value)
                         for value in sc_accum]
        sc_result = sc_rope(projection_sc[0], projection_sc[1],
                            cos_s18, sin_s18)
        fp16_projection = [reduce_six(banks) for banks in fp16_banks]
        fp32_projection = [reduce_six(banks) for banks in fp32_banks]
        fp16_result = fp16_rope(fp16_projection[0], fp16_projection[1],
                                cos_s18, sin_s18)
        fp32_result = fp32_rope(fp32_projection[0], fp32_projection[1],
                                cos_s18, sin_s18)
        exact_result = (
            exact_accum[0] * (cos_s18 / (1 << 16)) -
            exact_accum[1] * (sin_s18 / (1 << 16)),
            exact_accum[0] * (sin_s18 / (1 << 16)) +
            exact_accum[1] * (cos_s18 / (1 << 16)),
        )

        expected_sc.append(sc_result)
        expected_fp16.append(fp16_result)
        expected_fp32.append(fp32_result)
        reference.append(exact_result)
        if any(value in (-(1 << 23), (1 << 23) - 1)
               for value in sc_result):
            saturation_pairs += 1

    OUT.mkdir(parents=True, exist_ok=True)
    output_specs = {
        "correlation_s21_pair.mem": 11,
        "scale_meta_sc_u42.mem": 11,
        "scale_fp16x3.mem": 12,
        "scale_fp32x3.mem": 24,
        "coeff_s18_pair.mem": 9,
        "expected_sc_s24_pair.mem": 12,
        "expected_fp16_s24_pair.mem": 12,
        "expected_fp32_s24_pair.mem": 12,
    }
    handles = {name: (OUT / name).open("w", encoding="ascii")
               for name in output_specs}
    try:
        for record in group_records:
            corr_word = ((int(record["corr1"]) & MASK21) << 21) | \
                (int(record["corr0"]) & MASK21)
            sc_word = (
                int(record["act_code"]) |
                (int(record["act_shift"]) << 8) |
                (int(record["weight0_code"]) << 14) |
                (int(record["weight0_shift"]) << 22) |
                (int(record["weight1_code"]) << 28) |
                (int(record["weight1_shift"]) << 36)
            )
            fp16_word = (
                fp16_bits(float(record["act_scale"])) |
                (fp16_bits(float(record["weight0_scale"])) << 16) |
                (fp16_bits(float(record["weight1_scale"])) << 32)
            )
            fp32_word = (
                fp32_bits(float(record["act_scale"])) |
                (fp32_bits(float(record["weight0_scale"])) << 32) |
                (fp32_bits(float(record["weight1_scale"])) << 64)
            )
            handles["correlation_s21_pair.mem"].write(f"{corr_word:011x}\n")
            handles["scale_meta_sc_u42.mem"].write(f"{sc_word:011x}\n")
            handles["scale_fp16x3.mem"].write(f"{fp16_word:012x}\n")
            handles["scale_fp32x3.mem"].write(f"{fp32_word:024x}\n")

        for cos_s18, sin_s18 in coefficients:
            coeff_word = ((sin_s18 & ((1 << 18) - 1)) << 18) | \
                (cos_s18 & ((1 << 18) - 1))
            handles["coeff_s18_pair.mem"].write(f"{coeff_word:09x}\n")
        for name, values in (
            ("expected_sc_s24_pair.mem", expected_sc),
            ("expected_fp16_s24_pair.mem", expected_fp16),
            ("expected_fp32_s24_pair.mem", expected_fp32),
        ):
            for y0, y1 in values:
                handles[name].write(f"{pack_pair(y0, y1):012x}\n")
    finally:
        for handle in handles.values():
            handle.close()

    hashes = {}
    for name in sorted(output_specs):
        hashes[name] = hashlib.sha256((OUT / name).read_bytes()).hexdigest()
    normal_indices = [
        index for index, values in enumerate(reference)
        if all(-128.0 <= value <= ((1 << 23) - 1) / float(1 << 16)
               for value in values)
    ]
    manifest = {
        "schema": "m03_projection_tail_rope_boundary_v1",
        "seeds": list(SEEDS),
        "pairs": PAIRS,
        "groups_per_pair": GROUPS,
        "transactions": PAIRS * GROUPS,
        "common_input": "two signed S21 correlations plus native scale metadata and S18 Q2.16 sin/cos",
        "sc_path": "ScaleCode S42 Q18.24 group accumulation -> S24 Q8.16 -> production integer RoPE",
        "fp16_path": "S21->FP32->FP16, two FP16 multiplies, FP16->FP32, six-bank FP32 accumulation, FP16 RoPE, one final FP32->S24",
        "fp32_path": "S21->FP32, two FP32 multiplies, six-bank FP32 accumulation, FP32 RoPE, one final FP32->S24",
        "fp_accumulator_reduction": "((bank0+bank1)+(bank2+bank3))+(bank4+bank5), every add rounded to FP32",
        "target_input_ii": 2,
        "fp_accumulator_banks": 6,
        "fp32_add_latency": 11,
        "fp_bank_revisit_cycles": 12,
        "total_shift_min": min(total_shifts),
        "total_shift_max": max(total_shifts),
        "fp16_zero_group_contributions": fp16_zero_contributions,
        "saturation_pairs_sc": saturation_pairs,
        "non_saturation_pair_indices": normal_indices,
        "software_metrics_all_pairs": {
            "sc": metrics(expected_sc, reference),
            "fp16": metrics(expected_fp16, reference),
            "fp32": metrics(expected_fp32, reference),
        },
        "software_metrics_non_saturation_pairs": {
            "sc": metrics(expected_sc, reference, normal_indices),
            "fp16": metrics(expected_fp16, reference, normal_indices),
            "fp32": metrics(expected_fp32, reference, normal_indices),
        },
        "sha256": hashes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("M03_BOUNDARY_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
