#!/usr/bin/env python3
"""Generate deterministic 96-lane recovery-only vectors and bit goldens."""

from __future__ import annotations

import hashlib
import json
import math
import random
import struct
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data"
LANES = 96
VECTORS = 4096
SEED = 0x13A8F016


def pack(values: list[int], width: int) -> int:
    result = 0
    mask = (1 << width) - 1
    for index, value in enumerate(values):
        result |= (int(value) & mask) << (index * width)
    return result


def fp16_bits(value: float | np.floating) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def fp16_ftz(value: float | np.floating) -> np.float16:
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if bits & 0x7C00 == 0:
        return np.float16(-0.0 if bits & 0x8000 else 0.0)
    return rounded


def fp16_mul_ip(lhs: np.float16, rhs: np.float16) -> np.float16:
    """AMD half multiply: normal inputs/results, RNE, subnormal flush-to-zero."""
    product = np.float32(fp16_ftz(lhs)) * np.float32(fp16_ftz(rhs))
    tiny = float(np.finfo(np.float16).tiny)
    threshold = tiny - float(np.finfo(np.float16).smallest_subnormal) / 4.0
    if 0.0 < abs(float(product)) < threshold:
        return np.float16(-0.0 if np.signbit(product) else 0.0)
    return fp16_ftz(product)


def round_fixed_q24(value: float | np.floating) -> int:
    """AMD float-to-fixed default is round-to-nearest, ties-to-even."""
    if not math.isfinite(float(value)):
        raise ValueError(f"non-finite contribution {value}")
    rounded = int(np.rint(float(value) * (1 << 24)))
    if not -(1 << 35) <= rounded < (1 << 35):
        raise ValueError(f"S36 Q12.24 overflow: {value} -> {rounded}")
    return rounded


def write_word(handle, value: int, bits: int) -> None:
    handle.write(f"{value & ((1 << bits) - 1):0{(bits + 3) // 4}x}\n")


def make_dot(rng: random.Random, cycle: int, lane: int, stream: int) -> int:
    if cycle == 0:
        return 0
    if cycle == 1:
        return (-1 if (lane + stream) & 1 else 1)
    if cycle == 2:
        return (-60000 if (lane + stream) & 1 else 60000)
    if cycle == 3:
        return [-32768, -255, -1, 0, 1, 255, 32767, 60000][
            (lane + 3 * stream) & 7]
    if cycle % 257 == 0:
        return [0, 1, -1, 32767, -32768, 60000, -60000][
            (lane + stream) % 7]
    return rng.randrange(-60000, 60001)


def make_meta(rng: random.Random, cycle: int, lane: int) -> tuple[int, ...]:
    if cycle == 0:
        return 1, 10, 1, 11, 1, 11
    if cycle == 1:
        return 1 + lane % 255, 10, 255 - lane % 255, 11, 1, 22
    if cycle == 2:
        return 255, 10, 255, 11, 254, 11
    if cycle == 3:
        return 1 + (17 * lane) % 255, 22, 1 + (29 * lane) % 255, 22, 255, 22

    activation_shift = rng.randrange(10, 23)
    legal_weights = [shift for shift in range(10, 23)
                     if 21 <= activation_shift + shift <= 44]
    weight0_shift = rng.choice(legal_weights)
    weight1_shift = rng.choice(legal_weights)
    return (rng.randrange(1, 256), activation_shift,
            rng.randrange(1, 256), weight0_shift,
            rng.randrange(1, 256), weight1_shift)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = [
        "dot0_s17x96.mem", "dot1_s17x96.mem",
        "activation_meta_sc_u1344.mem", "weight0_meta_sc_u1344.mem",
        "weight1_meta_sc_u1344.mem",
        "activation_scale_fp16x96.mem", "weight0_scale_fp16x96.mem",
        "weight1_scale_fp16x96.mem",
        "activation_scale_fp32x96.mem", "weight0_scale_fp32x96.mem",
        "weight1_scale_fp32x96.mem",
        "expected_sc0_s36x96.mem", "expected_sc1_s36x96.mem",
        "expected_fp16_0_s36x96.mem", "expected_fp16_1_s36x96.mem",
        "expected_fp32_0_s36x96.mem", "expected_fp32_1_s36x96.mem",
    ]
    handles = {name: (OUT / name).open("w", encoding="ascii") for name in names}
    rng = random.Random(SEED)
    total_shift_min = 127
    total_shift_max = 0
    fp16_zero = 0
    exact_sc_zero = 0

    try:
        for cycle in range(VECTORS):
            dots0: list[int] = []
            dots1: list[int] = []
            activation_codes: list[int] = []
            activation_shifts: list[int] = []
            weight0_codes: list[int] = []
            weight0_shifts: list[int] = []
            weight1_codes: list[int] = []
            weight1_shifts: list[int] = []
            activation_fp16: list[int] = []
            weight0_fp16: list[int] = []
            weight1_fp16: list[int] = []
            activation_fp32: list[int] = []
            weight0_fp32: list[int] = []
            weight1_fp32: list[int] = []
            expected_sc0: list[int] = []
            expected_sc1: list[int] = []
            expected_fp16_0: list[int] = []
            expected_fp16_1: list[int] = []
            expected_fp32_0: list[int] = []
            expected_fp32_1: list[int] = []

            for lane in range(LANES):
                dot0 = make_dot(rng, cycle, lane, 0)
                dot1 = make_dot(rng, cycle, lane, 1)
                acode, ashift, w0code, w0shift, w1code, w1shift = \
                    make_meta(rng, cycle, lane)
                total0 = ashift + w0shift
                total1 = ashift + w1shift
                assert 21 <= total0 <= 44 and 21 <= total1 <= 44
                total_shift_min = min(total_shift_min, total0, total1)
                total_shift_max = max(total_shift_max, total0, total1)

                ascale = acode / float(1 << ashift)
                w0scale = w0code / float(1 << w0shift)
                w1scale = w1code / float(1 << w1shift)
                a16 = fp16_ftz(ascale)
                w016 = fp16_ftz(w0scale)
                w116 = fp16_ftz(w1scale)
                a32 = np.float32(ascale)
                w032 = np.float32(w0scale)
                w132 = np.float32(w1scale)

                raw0 = dot0 * acode * w0code
                raw1 = dot1 * acode * w1code
                sc0 = (raw0 << (24-total0) if total0 < 24
                       else raw0 >> (total0-24))
                sc1 = (raw1 << (24-total1) if total1 < 24
                       else raw1 >> (total1-24))
                assert -(1 << 35) <= sc0 < (1 << 35)
                assert -(1 << 35) <= sc1 < (1 << 35)
                exact_sc_zero += int(sc0 == 0) + int(sc1 == 0)

                dot016 = fp16_ftz(np.float32(dot0))
                dot116 = fp16_ftz(np.float32(dot1))
                term016 = fp16_mul_ip(fp16_mul_ip(dot016, a16), w016)
                term116 = fp16_mul_ip(fp16_mul_ip(dot116, a16), w116)
                fp16_zero += int((int(term016.view(np.uint16)) & 0x7FFF) == 0)
                fp16_zero += int((int(term116.view(np.uint16)) & 0x7FFF) == 0)

                term032 = np.float32(np.float32(np.float32(dot0) * a32) * w032)
                term132 = np.float32(np.float32(np.float32(dot1) * a32) * w132)

                dots0.append(dot0)
                dots1.append(dot1)
                activation_codes.append(acode)
                activation_shifts.append(ashift)
                weight0_codes.append(w0code)
                weight0_shifts.append(w0shift)
                weight1_codes.append(w1code)
                weight1_shifts.append(w1shift)
                activation_fp16.append(fp16_bits(a16))
                weight0_fp16.append(fp16_bits(w016))
                weight1_fp16.append(fp16_bits(w116))
                activation_fp32.append(fp32_bits(a32))
                weight0_fp32.append(fp32_bits(w032))
                weight1_fp32.append(fp32_bits(w132))
                expected_sc0.append(sc0)
                expected_sc1.append(sc1)
                expected_fp16_0.append(round_fixed_q24(term016))
                expected_fp16_1.append(round_fixed_q24(term116))
                expected_fp32_0.append(round_fixed_q24(term032))
                expected_fp32_1.append(round_fixed_q24(term132))

            write_word(handles["dot0_s17x96.mem"], pack(dots0, 17), LANES*17)
            write_word(handles["dot1_s17x96.mem"], pack(dots1, 17), LANES*17)
            write_word(handles["activation_meta_sc_u1344.mem"],
                       pack(activation_codes, 8) |
                       (pack(activation_shifts, 6) << (LANES*8)), LANES*14)
            write_word(handles["weight0_meta_sc_u1344.mem"],
                       pack(weight0_codes, 8) |
                       (pack(weight0_shifts, 6) << (LANES*8)), LANES*14)
            write_word(handles["weight1_meta_sc_u1344.mem"],
                       pack(weight1_codes, 8) |
                       (pack(weight1_shifts, 6) << (LANES*8)), LANES*14)
            for stem, values16, values32 in [
                ("activation_scale", activation_fp16, activation_fp32),
                ("weight0_scale", weight0_fp16, weight0_fp32),
                ("weight1_scale", weight1_fp16, weight1_fp32),
            ]:
                write_word(handles[f"{stem}_fp16x96.mem"],
                           pack(values16, 16), LANES*16)
                write_word(handles[f"{stem}_fp32x96.mem"],
                           pack(values32, 32), LANES*32)
            for name, values in [
                ("expected_sc0_s36x96.mem", expected_sc0),
                ("expected_sc1_s36x96.mem", expected_sc1),
                ("expected_fp16_0_s36x96.mem", expected_fp16_0),
                ("expected_fp16_1_s36x96.mem", expected_fp16_1),
                ("expected_fp32_0_s36x96.mem", expected_fp32_0),
                ("expected_fp32_1_s36x96.mem", expected_fp32_1),
            ]:
                write_word(handles[name], pack(values, 36), LANES*36)
    finally:
        for handle in handles.values():
            handle.close()

    hashes = {
        name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        for name in names
    }
    manifest = {
        "schema_version": 1,
        "seed": SEED,
        "lanes": LANES,
        "outputs_per_lane": 2,
        "vectors": VECTORS,
        "accepted_contributions": VECTORS * LANES * 2,
        "common_output": "signed S36 Q12.24",
        "total_shift_range": [total_shift_min, total_shift_max],
        "dot_range": [-60000, 60000],
        "fp16_zero_contributions": fp16_zero,
        "sc_zero_contributions": exact_sc_zero,
        "fp16_semantics": "AMD RNE with subnormal input/result FTZ",
        "fp_fixed_conversion": "AMD round-to-nearest-even",
        "sha256": hashes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M13_VECTOR_GENERATION_PASS "
          f"vectors={VECTORS} lanes={LANES} contributions={VECTORS*LANES*2} "
          f"shift=[{total_shift_min},{total_shift_max}] fp16_zero={fp16_zero}")


if __name__ == "__main__":
    main()
