#!/usr/bin/env python3
"""Generate 12-seed, shape-swept boundary-inclusive M07 PV vectors."""
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
SEEDS = tuple(range(2026091101, 2026091113))
LANES = 16
SCALE_CHOICES = ((0, 0), (1, 8), (255, 16), (73, 20),
                 (201, 22), (127, 18), (255, 32), (17, 14))

sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import pv_row_tile16_s24, softmax_row_u16  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp16_bits(value: float | np.float16) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.float32) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def bits_fp16(value: int) -> np.float16:
    return np.asarray([value], dtype=np.uint16).view(np.float16)[0]


def ftz16(value: float | np.float16) -> np.float16:
    rounded = np.float16(value)
    bits = fp16_bits(rounded)
    if (bits & 0x7C00) == 0:
        return bits_fp16(bits & 0x8000)
    return rounded


def mul16(a: np.float16, b: np.float16) -> np.float16:
    with np.errstate(over="ignore", invalid="ignore"):
        product = np.float32(ftz16(a)) * np.float32(ftz16(b))
        normal_round_midpoint = 2.0**-14 * (1.0 - 2.0**-12)
        if product != 0 and abs(float(product)) < normal_round_midpoint:
            return bits_fp16(0x8000 if product < 0 else 0x0000)
        return ftz16(product)


def add16(a: np.float16, b: np.float16) -> np.float16:
    with np.errstate(over="ignore", invalid="ignore"):
        return ftz16(np.float32(ftz16(a)) + np.float32(ftz16(b)))


def pack_lanes(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (lane * width)
               for lane, value in enumerate(values))


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (digits * 4)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def s24_from_float(value: float) -> tuple[int, bool]:
    if not math.isfinite(value):
        quantized = (1 << 23) - 1 if value > 0 else -(1 << 23)
        return quantized, True
    raw = int(np.rint(value * 65536.0))
    clipped = min((1 << 23) - 1, max(-(1 << 23), raw))
    return clipped, clipped != raw


def probability_row(shape_index: int, seed_index: int,
                    seed: int, key_count: int) -> list[int]:
    rng = np.random.default_rng(seed ^ (shape_index << 23))
    if seed_index == 0:
        scores = [int(value) for value in rng.integers(
            -(16 << 14), (16 << 14) + 1, size=key_count)]
        masks = [True] * key_count
        masks[0] = False
    elif seed_index == 1:
        scores = [0] * key_count
        masks = [False] * key_count
    elif seed_index == 2:
        scores = [-(16 << 14) if index % 2 == 0 else (16 << 14)
                  for index in range(key_count)]
        masks = [False] * key_count
    else:
        scores = [int(value) for value in rng.integers(
            -(16 << 14), (16 << 14) + 1, size=key_count)]
        masks = [bool(value) for value in (rng.random(key_count) < 0.2)]
        masks[(seed_index * 7 + shape_index) % key_count] = False
    padded_scores = scores + [0] * (128 - key_count)
    padded_masks = masks + [True] * (128 - key_count)
    return list(softmax_row_u16(padded_scores, padded_masks)[0][:key_count])


def accuracy_metrics(values: list[int], golden: list[float]) -> dict[str, float]:
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
    row_key_counts: list[int] = []
    probability_records: list[int] = []
    value_records: list[int] = []
    meta_records: list[int] = []
    probability16_records: list[int] = []
    probability32_records: list[int] = []
    scale16_records: list[int] = []
    scale32_records: list[int] = []
    value16_records: list[int] = []
    value32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    ideal64: list[float] = []
    saturation = {"sc": 0, "fp16": 0, "fp32": 0}
    fp16_scale_subnormal_records = 0
    fp16_probability_ftz_records = 0
    fp16_zero_v_lanes_from_nonzero_inputs = 0

    for shape_index, key_count in enumerate(SHAPES):
        for seed_index, seed in enumerate(SEEDS):
            rng = np.random.default_rng(seed ^ (shape_index << 24))
            probabilities = probability_row(
                shape_index, seed_index, seed, key_count)
            row_values: list[list[int]] = []
            row_codes: list[int] = []
            row_shifts: list[int] = []
            row_v16: list[list[np.float16]] = []
            row_v32: list[list[np.float32]] = []
            row_v64: list[list[float]] = []
            row_p16: list[np.float16] = []
            row_p32: list[np.float32] = []

            for key, probability in enumerate(probabilities):
                if shape_index == 0 and seed_index == 0 and key == 0:
                    code, shift = 255, 8
                    values = [2047 if lane % 2 == 0 else -2047
                              for lane in range(LANES)]
                else:
                    code, shift = SCALE_CHOICES[
                        (seed_index * 5 + shape_index * 3 + key) %
                        len(SCALE_CHOICES)]
                    if code == 0:
                        values = [0] * LANES
                    else:
                        values = [int(value) for value in rng.integers(
                            -2047, 2048, size=LANES)]
                scale = 0.0 if code == 0 else code / float(1 << shift)
                scale16 = np.float16(scale)
                scale32 = np.float32(scale)
                if code and (fp16_bits(scale16) & 0x7C00) == 0:
                    fp16_scale_subnormal_records += 1
                values16 = [mul16(np.float16(value), scale16)
                            for value in values]
                values32 = [np.float32(np.float32(value) * scale32)
                            for value in values]
                values64 = [value * scale for value in values]
                probability16_raw = np.float16(probability / 65536.0)
                probability16 = ftz16(probability16_raw)
                probability32 = np.float32(probability / 65536.0)
                fp16_probability_ftz_records += int(
                    probability != 0 and fp16_bits(probability16) in (0, 0x8000))
                fp16_zero_v_lanes_from_nonzero_inputs += sum(
                    int(value != 0 and fp16_bits(converted) in (0, 0x8000))
                    for value, converted in zip(values, values16, strict=True))

                probability_records.append(probability)
                value_records.append(pack_lanes(values, 12))
                meta_records.append(code | (shift << 8))
                probability16_records.append(fp16_bits(probability16))
                probability32_records.append(fp32_bits(probability32))
                scale16_records.append(fp16_bits(scale16))
                scale32_records.append(fp32_bits(scale32))
                value16_records.append(pack_lanes(
                    [fp16_bits(value) for value in values16], 16))
                value32_records.append(pack_lanes(
                    [fp32_bits(value) for value in values32], 32))
                row_values.append(values)
                row_codes.append(code)
                row_shifts.append(shift)
                row_v16.append(values16)
                row_v32.append(values32)
                row_v64.append(values64)
                row_p16.append(probability16)
                row_p32.append(probability32)

            padded_probabilities = probabilities + [0] * (128 - key_count)
            padded_values = row_values + [[0] * LANES for _ in range(128-key_count)]
            padded_codes = row_codes + [0] * (128 - key_count)
            padded_shifts = row_shifts + [0] * (128 - key_count)
            sc_row, sc_saturation = pv_row_tile16_s24(
                padded_probabilities, padded_values, padded_codes, padded_shifts)
            accum16 = [np.float16(0.0)] * LANES
            accum32 = [np.float32(0.0)] * LANES
            accum64 = [0.0] * LANES
            for key in range(key_count):
                for lane in range(LANES):
                    accum16[lane] = add16(
                        accum16[lane], mul16(row_p16[key], row_v16[key][lane]))
                    accum32[lane] = np.float32(
                        accum32[lane] + np.float32(
                            row_p32[key] * row_v32[key][lane]))
                    accum64[lane] += (probabilities[key] / 65536.0) * \
                        row_v64[key][lane]
            fp16_row: list[int] = []
            fp32_row: list[int] = []
            for lane in range(LANES):
                value16, sat16 = s24_from_float(float(accum16[lane]))
                value32, sat32 = s24_from_float(float(accum32[lane]))
                fp16_row.append(value16)
                fp32_row.append(value32)
                saturation["fp16"] += int(sat16)
                saturation["fp32"] += int(sat32)
            saturation["sc"] += sc_saturation
            expected_sc.append(pack_lanes(list(sc_row), 24))
            expected16.append(pack_lanes(fp16_row, 24))
            expected32.append(pack_lanes(fp32_row, 24))
            ideal64.extend(
                min(((1 << 23) - 1) / 65536.0, max(-128.0, value))
                for value in accum64)
            row_key_counts.append(key_count)

    rows = len(SHAPES) * len(SEEDS)
    keys = sum(SHAPES) * len(SEEDS)
    if not (len(row_key_counts) == rows and len(probability_records) == keys and
            len(value_records) == keys and len(expected_sc) == rows):
        raise AssertionError("M07 boundary record count mismatch")

    OUT.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "probability_u16.mem": (probability_records, 4),
        "value_s12x16.mem": (value_records, 48),
        "value_meta_sc_u16.mem": (meta_records, 4),
        "probability_fp16.mem": (probability16_records, 4),
        "probability_fp32.mem": (probability32_records, 8),
        "value_scale_fp16.mem": (scale16_records, 4),
        "value_scale_fp32.mem": (scale32_records, 8),
        "value_cache_fp16x16.mem": (value16_records, 64),
        "value_cache_fp32x16.mem": (value32_records, 128),
        "expected_sc_s24x16.mem": (expected_sc, 96),
        "expected_fp16_s24x16.mem": (expected16, 96),
        "expected_fp32_s24x16.mem": (expected32, 96),
    }
    files: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)
        files[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(OUT / filename),
        }

    def unpack_expected(records: list[int]) -> list[int]:
        result: list[int] = []
        for record in records:
            for lane in range(LANES):
                value = (record >> (lane * 24)) & 0xFFFFFF
                result.append(value - (1 << 24) if value & (1 << 23) else value)
        return result

    production_model = ROOT / "model" / "fixbit_v2.py"
    manifest = {
        "schema": "scalellm_modular_pv_boundary_inclusive_v1",
        "seeds": list(SEEDS),
        "shapes": list(SHAPES),
        "row_schedule": "shape descending outer, seed inner",
        "rows": rows,
        "keys": keys,
        "lanes": LANES,
        "common_input": "U16 probability plus V S12x16 and native scale metadata",
        "common_output": "signed S24 Q8.16 context16",
        "input_cadence_target": "one key transaction per cycle at the cache boundary",
        "coverage": {
            "zero_probabilities": sum(value == 0 for value in probability_records),
            "fp16_scale_subnormal_records": fp16_scale_subnormal_records,
            "fp16_probability_ftz_records": fp16_probability_ftz_records,
            "fp16_zero_v_lanes_from_nonzero_inputs":
                fp16_zero_v_lanes_from_nonzero_inputs,
        },
        "saturation_counts": saturation,
        "software_accuracy_vs_clipped_fp64": {
            "sc": accuracy_metrics(unpack_expected(expected_sc), ideal64),
            "fp16": accuracy_metrics(unpack_expected(expected16), ideal64),
            "fp32": accuracy_metrics(unpack_expected(expected32), ideal64),
        },
        "numeric_models": {
            "sc": "production pv_row_tile16_s24 ScaleCode shift/accumulate/finalize",
            "fp16": "U16/V to FP16 with FTZ, native scale multiply, sequential FP16 MAC",
            "fp32": "U16/V to FP32, native scale multiply, sequential FP32 MAC",
            "reference": "FP64 over common quantized U16 probabilities and exact native scales, clipped once at the common S24 observation point",
        },
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M07_BOUNDARY_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M07 12-seed shape-swept boundary vectors generated")


if __name__ == "__main__":
    main()
