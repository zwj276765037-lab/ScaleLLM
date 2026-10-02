#!/usr/bin/env python3
"""Generate the formal 12-seed, shape-swept M06 Softmax workload."""
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
SEEDS = tuple(range(2026091001, 2026091013))
SCORE_SCALE = 1 << 14

sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import softmax_row_u16  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp16_bits(value: float | np.float16) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.float32) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (4 * digits)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def fp_softmax_u16(scores: list[int], masks: list[bool], width: int) -> list[int]:
    """Reference the explicit native-FP operation order used by M06 RTL."""
    if width == 16:
        values = [np.float16(score / SCORE_SCALE) for score in scores]
        visible = [value for value, mask in zip(values, masks, strict=True)
                   if not mask]
        maximum = max(visible)
        exponents: list[np.float16] = []
        for value, mask in zip(values, masks, strict=True):
            if mask:
                exponents.append(np.float16(0.0))
            else:
                delta = np.float16(value - maximum)
                exponents.append(np.float16(np.exp(delta)))
        row_sum = np.float16(0.0)
        for value in exponents:
            row_sum = np.float16(row_sum + value)
        probabilities = [np.float16(value / row_sum) for value in exponents]
    elif width == 32:
        values = [np.float32(score / SCORE_SCALE) for score in scores]
        visible = [value for value, mask in zip(values, masks, strict=True)
                   if not mask]
        maximum = max(visible)
        exponents32: list[np.float32] = []
        for value, mask in zip(values, masks, strict=True):
            if mask:
                exponents32.append(np.float32(0.0))
            else:
                delta = np.float32(value - maximum)
                exponents32.append(np.float32(np.exp(delta)))
        row_sum32 = np.float32(0.0)
        for value in exponents32:
            row_sum32 = np.float32(row_sum32 + value)
        probabilities = [np.float32(value / row_sum32)
                         for value in exponents32]
    else:
        raise ValueError("FP Softmax width must be 16 or 32")
    return [min(65535, max(0, int(np.rint(float(value) * 65536.0))))
            for value in probabilities]


def ideal_softmax(scores: list[int], masks: list[bool]) -> list[float]:
    values = [score / SCORE_SCALE for score in scores]
    maximum = max(value for value, mask in zip(values, masks, strict=True)
                  if not mask)
    exponents = [0.0 if mask else math.exp(value - maximum)
                 for value, mask in zip(values, masks, strict=True)]
    total = sum(exponents)
    return [value / total for value in exponents]


def build_row(shape_index: int, seed_index: int,
              seed: int, key_count: int) -> tuple[list[int], list[bool]]:
    rng = np.random.default_rng(seed ^ (shape_index << 24))
    if seed_index == 0:
        scores = [int(value) for value in rng.integers(
            -(16 << 14), (16 << 14) + 1, size=key_count)]
        visible = (shape_index * 7) % key_count
        masks = [index != visible for index in range(key_count)]
    elif seed_index == 1:
        scores = [0] * key_count
        masks = [False] * key_count
    elif seed_index == 2:
        scores = [-(16 << 14) if index % 2 == 0 else (16 << 14)
                  for index in range(key_count)]
        masks = [False] * key_count
    elif seed_index == 3:
        scores = [int(value) for value in rng.integers(
            -(8 << 14), (8 << 14) + 1, size=key_count)]
        scores[0] = 12 << 14
        scores[-1] = 12 << 14
        masks = [index % 7 == 5 for index in range(key_count)]
        masks[0] = False
        masks[-1] = False
    else:
        scores = [int(value) for value in rng.integers(
            -(16 << 14), (16 << 14) + 1, size=key_count)]
        masks = [bool(value) for value in (rng.random(key_count) < 0.2)]
        masks[(seed_index * 11 + shape_index * 3) % key_count] = False
    if all(masks):
        raise AssertionError("valid M06 row may not be fully masked")
    return scores, masks


def accuracy_metrics(rows: list[dict[str, object]], version: str) -> dict[str, object]:
    absolute_errors: list[float] = []
    sum_errors: list[int] = []
    divergences: list[float] = []
    top1_matches = 0
    epsilon = 1.0e-12
    for row in rows:
        measured_u16 = row[version]
        reference = row["ideal"]
        masks = row["masks"]
        assert isinstance(measured_u16, list)
        assert isinstance(reference, list)
        assert isinstance(masks, list)
        measured = [int(value) / 65536.0 for value in measured_u16]
        absolute_errors.extend(abs(value - golden)
                               for value, golden in zip(
                                   measured, reference, strict=True))
        sum_errors.append(abs(sum(int(value) for value in measured_u16) - 65536))
        measured_sum = sum(measured)
        normalized = [value / measured_sum for value in measured]
        divergences.append(sum(
            golden * math.log(golden / max(value, epsilon))
            for golden, value, mask in zip(
                reference, normalized, masks, strict=True)
            if not mask and golden > 0.0))
        best_value = max(reference)
        acceptable = {index for index, value in enumerate(reference)
                      if value == best_value}
        measured_top = max(range(len(measured_u16)),
                           key=lambda index: int(measured_u16[index]))
        top1_matches += int(measured_top in acceptable)
    squared = [value * value for value in absolute_errors]
    return {
        "max_abs_probability_error": max(absolute_errors),
        "mean_abs_probability_error": sum(absolute_errors) / len(absolute_errors),
        "rmse_probability": math.sqrt(sum(squared) / len(squared)),
        "probability_sum_abs_error_u16_mean": sum(sum_errors) / len(sum_errors),
        "probability_sum_abs_error_u16_max": max(sum_errors),
        "kl_divergence_mean": sum(divergences) / len(divergences),
        "kl_divergence_max": max(divergences),
        "kl_epsilon": epsilon,
        "top1_matches": top1_matches,
        "top1_rows": len(rows),
    }


def main() -> None:
    row_key_counts: list[int] = []
    score_records: list[int] = []
    mask_records: list[int] = []
    score16_records: list[int] = []
    score32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    metric_rows: list[dict[str, object]] = []
    single_visible_rows = 0
    tied_maximum_rows = 0

    for shape_index, key_count in enumerate(SHAPES):
        for seed_index, seed in enumerate(SEEDS):
            scores, masks = build_row(shape_index, seed_index, seed, key_count)
            padded_scores = scores + [0] * (128 - key_count)
            padded_masks = masks + [True] * (128 - key_count)
            sc_row = list(softmax_row_u16(padded_scores, padded_masks)[0])[
                :key_count]
            fp16_row = fp_softmax_u16(scores, masks, 16)
            fp32_row = fp_softmax_u16(scores, masks, 32)
            ideal_row = ideal_softmax(scores, masks)

            row_key_counts.append(key_count)
            score_records.extend(scores)
            mask_records.extend(int(mask) for mask in masks)
            score16_records.extend(fp16_bits(score / SCORE_SCALE)
                                   for score in scores)
            score32_records.extend(fp32_bits(score / SCORE_SCALE)
                                   for score in scores)
            expected_sc.extend(sc_row)
            expected16.extend(fp16_row)
            expected32.extend(fp32_row)
            metric_rows.append({
                "sc": sc_row,
                "fp16": fp16_row,
                "fp32": fp32_row,
                "ideal": ideal_row,
                "masks": masks,
            })
            single_visible_rows += int(sum(not mask for mask in masks) == 1)
            visible_scores = [score for score, mask in zip(scores, masks, strict=True)
                              if not mask]
            tied_maximum_rows += int(visible_scores.count(max(visible_scores)) > 1)

    rows = len(SHAPES) * len(SEEDS)
    scores = sum(SHAPES) * len(SEEDS)
    if not (len(row_key_counts) == rows and len(score_records) == scores and
            len(mask_records) == scores and len(expected_sc) == scores):
        raise AssertionError("M06 boundary record count mismatch")

    OUT.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "score_s20.mem": (score_records, 5),
        "mask.mem": (mask_records, 1),
        "score_fp16.mem": (score16_records, 4),
        "score_fp32.mem": (score32_records, 8),
        "expected_sc_u16.mem": (expected_sc, 4),
        "expected_fp16_u16.mem": (expected16, 4),
        "expected_fp32_u16.mem": (expected32, 4),
    }
    files: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)
        files[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(OUT / filename),
        }

    production_model = ROOT / "model" / "fixbit_v2.py"
    manifest = {
        "schema": "scalellm_modular_softmax_boundary_inclusive_v1",
        "seeds": list(SEEDS),
        "shapes": list(SHAPES),
        "row_schedule": "shape descending outer, seed inner",
        "rows": rows,
        "scores": scores,
        "common_input": "signed S20 Q6.14 score plus mask/first/last",
        "common_output": "U16 Q0.16 probability",
        "input_cadence_target": "one score per cycle",
        "coverage": {
            "single_visible_rows": single_visible_rows,
            "tied_maximum_rows": tied_maximum_rows,
            "masked_scores": sum(mask_records),
            "minimum_score_records": sum(score == -(16 << 14)
                                         for score in score_records),
            "maximum_score_records": sum(score == (16 << 14)
                                         for score in score_records),
        },
        "software_accuracy_vs_fp64": {
            "sc": accuracy_metrics(metric_rows, "sc"),
            "fp16": accuracy_metrics(metric_rows, "fp16"),
            "fp32": accuracy_metrics(metric_rows, "fp32"),
        },
        "numeric_models": {
            "sc": "production fixbit_v2 Softmax exp LUT, reciprocal and U16 probability",
            "fp16": "native FP16 max/sub/exp/sequential-add/divide then U16 rounding",
            "fp32": "native FP32 max/sub/exp/sequential-add/divide then U16 rounding",
            "reference": "stable FP64 Softmax over visible keys",
        },
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M06_BOUNDARY_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M06 12-seed shape-swept boundary vectors generated")


if __name__ == "__main__":
    main()
