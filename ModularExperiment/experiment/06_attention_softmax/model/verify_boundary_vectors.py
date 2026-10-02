#!/usr/bin/env python3
"""Independently verify M06 boundary vector structure, hashes and SC golden."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DATA = HERE.parent / "data_boundary"
sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import softmax_row_u16  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def fp16_bits(value: float) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def read_mem(filename: str) -> list[int]:
    return [int(line, 16) for line in
            (DATA / filename).read_text(encoding="ascii").splitlines()]


def main() -> None:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "scalellm_modular_softmax_boundary_inclusive_v1":
        raise AssertionError("unexpected M06 boundary schema")
    if len(manifest["seeds"]) < 10:
        raise AssertionError("M06 boundary workload requires at least 10 seeds")
    if manifest["rows"] != len(manifest["seeds"]) * len(manifest["shapes"]):
        raise AssertionError("M06 boundary row count mismatch")
    if manifest["scores"] != sum(manifest["shapes"]) * len(manifest["seeds"]):
        raise AssertionError("M06 boundary score count mismatch")
    generator = HERE / "generate_boundary_vectors.py"
    if sha256_file(generator) != manifest["generator_sha256"]:
        raise AssertionError("M06 boundary generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M06 production model hash changed")

    for filename, spec in manifest["files"].items():
        path = DATA / filename
        lines = path.read_text(encoding="ascii").splitlines()
        if len(lines) != spec["records"]:
            raise AssertionError(f"{filename}: record count changed")
        if any(len(line) != spec["hex_digits"] for line in lines):
            raise AssertionError(f"{filename}: hex width changed")
        if any(not line or any(char not in "0123456789abcdef" for char in line)
               for line in lines):
            raise AssertionError(f"{filename}: non-lowercase-hex data")
        if sha256_file(path) != spec["sha256"]:
            raise AssertionError(f"{filename}: sha256 changed")

    row_counts = read_mem("row_key_count_u8.mem")
    expected_schedule = [shape for shape in manifest["shapes"]
                         for _ in manifest["seeds"]]
    if row_counts != expected_schedule:
        raise AssertionError("M06 boundary row schedule changed")
    scores = [signed(value, 20) for value in read_mem("score_s20.mem")]
    masks = [bool(value) for value in read_mem("mask.mem")]
    score16 = read_mem("score_fp16.mem")
    score32 = read_mem("score_fp32.mem")
    golden_sc = read_mem("expected_sc_u16.mem")
    if any(not -(16 << 14) <= score <= (16 << 14) for score in scores):
        raise AssertionError("M06 score outside clipped Q6.14 contract")

    offset = 0
    rebuilt_sc: list[int] = []
    for key_count in row_counts:
        row_scores = scores[offset:offset + key_count]
        row_masks = masks[offset:offset + key_count]
        if all(row_masks):
            raise AssertionError("M06 valid row is fully masked")
        padded_scores = row_scores + [0] * (128 - key_count)
        padded_masks = row_masks + [True] * (128 - key_count)
        rebuilt_sc.extend(softmax_row_u16(padded_scores, padded_masks)[0][
            :key_count])
        offset += key_count
    if offset != manifest["scores"] or rebuilt_sc != golden_sc:
        raise AssertionError("M06 SC golden does not match production model")
    rebuilt16 = [fp16_bits(score / float(1 << 14)) for score in scores]
    rebuilt32 = [fp32_bits(score / float(1 << 14)) for score in scores]
    if rebuilt16 != score16 or rebuilt32 != score32:
        raise AssertionError("M06 native FP boundary conversion cache changed")
    coverage = manifest["coverage"]
    for key in ("single_visible_rows", "tied_maximum_rows", "masked_scores",
                "minimum_score_records", "maximum_score_records"):
        if coverage[key] <= 0:
            raise AssertionError(f"M06 boundary misses coverage: {key}")
    print("M06_BOUNDARY_VECTOR_VERIFY_PASS "
          f"files={len(manifest['files'])} rows={manifest['rows']} "
          f"scores={manifest['scores']}")


if __name__ == "__main__":
    main()
