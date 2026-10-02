#!/usr/bin/env python3
"""Generate a common M3 pre-centered MAC/scale workload."""

from __future__ import annotations

import json
import random
import struct
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
COUNT = 256
SEED = 0x4D_33_5343_414C45


def pack(values: list[int], width: int) -> int:
    word = 0
    mask = (1 << width) - 1
    for lane, value in enumerate(values):
        word |= (value & mask) << (lane * width)
    return word


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def fp16_bits(value: float | np.floating) -> int:
    return int(np.float16(value).view(np.uint16))


def trunc_fixed(value: float | np.floating, fraction: int = 24) -> int:
    scaled = float(value) * float(1 << fraction)
    result = int(np.trunc(scaled))
    if not -(1 << 41) <= result < (1 << 41):
        raise OverflowError(result)
    return result


def round_fixed(value: float | np.floating, fraction: int = 24) -> int:
    """AMD Floating-Point float-to-fixed uses round-to-nearest-even."""
    scaled = float(value) * float(1 << fraction)
    result = int(np.rint(scaled))
    if not -(1 << 41) <= result < (1 << 41):
        raise OverflowError(result)
    return result


def fp16_ftz(value: float | np.floating) -> np.float16:
    """Xilinx FP operator half semantics: flush denormal results to zero."""
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        return np.float16(-0.0 if bits & 0x8000 else 0.0)
    return rounded


def fp16_mul_ftz(a: np.float16, b: np.float16) -> np.float16:
    # Denormal operands are treated as signed zero by the generated core.
    return fp16_ftz(np.float32(fp16_ftz(a)) * np.float32(fp16_ftz(b)))


def main() -> None:
    rng = random.Random(SEED)
    vectors = []
    while len(vectors) < COUNT:
        index = len(vectors)
        if index == 0:
            acts, weights, zp = [0] * 32, [0] * 32, 0
        elif index == 1:
            acts, weights, zp = [255] * 32, [1] * 32, 128
        elif index == 2:
            acts, weights, zp = [0] * 32, [1] * 32, 255
        else:
            # Keep the common dot product inside FP16's finite range while
            # retaining signed pre-centering and signed W8 behavior. Wide
            # random full-range vectors overwhelmingly overflow FP16 before
            # scale is applied and are therefore not a matched finite-output
            # workload.
            zp = rng.randrange(96, 160)
            acts = [max(0, min(255, zp + rng.randrange(-16, 17)))
                    for _ in range(32)]
            weights = [rng.randrange(-16, 17) for _ in range(32)]
        act_code = rng.randrange(1, 256)
        weight_code = rng.randrange(1, 256)
        total_shift = rng.randrange(30, 48)
        act_shift = rng.randrange(max(0, total_shift - 32), min(32, total_shift) + 1)
        weight_shift = total_shift - act_shift
        corr = sum((a - zp) * w for a, w in zip(acts, weights))
        if not -(1 << 20) <= corr < (1 << 20):
            continue
        act_scale = act_code / float(1 << act_shift)
        weight_scale = weight_code / float(1 << weight_shift)

        sc_guard = (corr * act_code * weight_code) >> (total_shift - 24)
        corr32 = np.float32(corr)
        a32 = np.float32(act_scale)
        w32 = np.float32(weight_scale)
        scale32 = np.float32(a32 * w32)
        out32 = np.float32(corr32 * scale32)
        fp32_guard = round_fixed(out32)

        corr16 = fp16_ftz(corr32)
        a16 = np.float16(act_scale)
        w16 = np.float16(weight_scale)
        with np.errstate(over="ignore", invalid="ignore"):
            scale16 = np.float16(a16 * w16)
            out16 = np.float16(corr16 * scale16)
            ip_stage1 = fp16_mul_ftz(corr16, a16)
            ip_out16 = fp16_mul_ftz(ip_stage1, w16)
        if not np.isfinite(out16):
            # The matched FP16 arithmetic cannot represent this case. Keep the
            # common vector set finite for a strict S42 mismatch gate.
            continue
        fp16_guard = trunc_fixed(np.float32(out16))
        fp16_ip_guard = trunc_fixed(np.float32(ip_out16))
        vectors.append((acts, weights, zp, act_code, act_shift, weight_code,
                        weight_shift, act_scale, weight_scale, corr, sc_guard,
                        fp16_guard, fp16_ip_guard, fp32_guard))

    OUT.mkdir(parents=True, exist_ok=True)
    names = [
        "act_u8.mem", "weight_s8.mem", "meta_scalecode.mem",
        "scale_fp16.mem", "scale_fp32.mem", "expected_corr_s21.mem",
        "expected_scalecode_s42.mem", "expected_fp16_s42.mem",
        "expected_fp16_ip_s42.mem",
        "expected_fp32_s42.mem",
    ]
    files = [(OUT / name).open("w", encoding="ascii") for name in names]
    try:
        for (acts, weights, zp, ac, ash, wc, wsh, ascale, wscale,
             corr, sc, f16, f16_ip, f32) in vectors:
            meta = (wsh << 34) | (wc << 26) | (ash << 20) | (ac << 12) | zp
            float16_record = (fp16_bits(wscale) << 16) | fp16_bits(ascale)
            float32_record = (fp32_bits(wscale) << 32) | fp32_bits(ascale)
            records = [
                f"{pack(acts, 8):064x}",
                f"{pack(weights, 8):064x}",
                f"{meta:010x}",
                f"{float16_record:08x}",
                f"{float32_record:016x}",
                f"{corr & ((1 << 42)-1):011x}",
                f"{sc & ((1 << 42)-1):011x}",
                f"{f16 & ((1 << 42)-1):011x}",
                f"{f16_ip & ((1 << 42)-1):011x}",
                f"{f32 & ((1 << 42)-1):011x}",
            ]
            for handle, record in zip(files, records):
                handle.write(record + "\n")
    finally:
        for handle in files:
            handle.close()

    manifest = {
        "schema": "hap_m3_matched_group32_vectors_v1",
        "seed": SEED,
        "vector_count": len(vectors),
        "centering": "pre-MAC a-zp",
        "common_scaled_output": "signed S42 Q18.24",
        "scale_truth": "ScaleCode decoded value code*2^-shift",
        "fp_fixed_conversion": "AMD FP IP round-to-nearest-even",
        "fp16_ip_semantics": "corr*act_scale*weight_scale; denormals flushed to zero",
        "fp16_ip_zero_outputs": sum(1 for item in vectors if item[-2] == 0),
        "fp16_ieee_vs_ip_mismatches": sum(
            1 for item in vectors if item[-3] != item[-2]),
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("M3_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
