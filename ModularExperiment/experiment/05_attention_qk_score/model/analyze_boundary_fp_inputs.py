#!/usr/bin/env python3
"""Audit whether operator-only cached FP keys match explicit HW dequantization."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


DATA = Path(__file__).resolve().parent.parent / "data"


def bits_to_fp16(bits: int) -> np.float16:
    return np.asarray([bits], dtype=np.uint16).view(np.float16)[0]


def fp16_to_bits(value: float | np.float16) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_to_bits(value: float | np.float32) -> int:
    return int(np.float32(value).view(np.uint32))


def ftz16(value: float | np.float16) -> np.float16:
    rounded = np.float16(value)
    bits = fp16_to_bits(rounded)
    if (bits & 0x7C00) == 0:
        return bits_to_fp16(bits & 0x8000)
    return rounded


def mul16(a: np.float16, b: np.float16) -> np.float16:
    """Xilinx Floating-Point v7.1 half multiply with denormal flush."""
    with np.errstate(over="ignore", invalid="ignore"):
        product = np.float32(ftz16(a)) * np.float32(ftz16(b))
        normal_round_midpoint = 2.0**-14 * (1.0 - 2.0**-12)
        if product != 0 and abs(float(product)) < normal_round_midpoint:
            return bits_to_fp16(0x8000 if product < 0 else 0x0000)
        return ftz16(product)


def sign_extend(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def read_hex(name: str) -> list[int]:
    return [int(line, 16) for line in (DATA / name).read_text().split()]


def main() -> None:
    fixed_records = read_hex("key_group_fixed.mem")
    meta_records = read_hex("key_meta_fixed.mem")
    cached_fp16_records = read_hex("key_group_fp16.mem")
    cached_fp32_records = read_hex("key_group_fp32.mem")
    lengths = {
        len(fixed_records), len(meta_records), len(cached_fp16_records),
        len(cached_fp32_records),
    }
    if len(lengths) != 1:
        raise AssertionError("M05 key input files have different record counts")

    fp16_scale_subnormal_records = 0
    fp16_cached_bit_differences = 0
    fp16_qk_semantic_differences = 0
    fp32_bit_differences = 0

    for fixed, meta, cached16, cached32 in zip(
            fixed_records, meta_records, cached_fp16_records,
            cached_fp32_records, strict=True):
        code = meta & 0xFF
        shift = (meta >> 8) & 0x3F
        scale = 0.0 if code == 0 else code / float(1 << shift)
        scale16_bits = fp16_to_bits(scale)
        scale16 = bits_to_fp16(scale16_bits)
        if code != 0 and (scale16_bits & 0x7C00) == 0:
            fp16_scale_subnormal_records += 1

        for lane in range(32):
            key = sign_extend((fixed >> (12 * lane)) & 0xFFF, 12)
            explicit16 = fp16_to_bits(mul16(np.float16(key), scale16))
            old16 = (cached16 >> (16 * lane)) & 0xFFFF
            if explicit16 != old16:
                fp16_cached_bit_differences += 1
                old_qk_semantic = fp16_to_bits(ftz16(bits_to_fp16(old16)))
                if explicit16 != old_qk_semantic:
                    fp16_qk_semantic_differences += 1

            explicit32 = fp32_to_bits(
                np.float32(np.float32(key) * np.float32(scale)))
            old32 = (cached32 >> (32 * lane)) & 0xFFFFFFFF
            fp32_bit_differences += int(explicit32 != old32)

    metrics = {
        "records": len(fixed_records),
        "lanes": len(fixed_records) * 32,
        "fp16_scale_subnormal_records": fp16_scale_subnormal_records,
        "fp16_cached_bit_differences": fp16_cached_bit_differences,
        "fp16_qk_semantic_differences": fp16_qk_semantic_differences,
        "fp32_bit_differences": fp32_bit_differences,
    }
    print("M05_BOUNDARY_INPUT_AUDIT_JSON:", json.dumps(metrics, sort_keys=True))
    if fp16_qk_semantic_differences == 0:
        raise AssertionError("expected explicit FP16 boundary to differ from old input")
    if fp32_bit_differences != 0:
        raise AssertionError("FP32 explicit dequantization changed unexpectedly")
    print("PASS: M05 boundary input reuse audit")


if __name__ == "__main__":
    main()
