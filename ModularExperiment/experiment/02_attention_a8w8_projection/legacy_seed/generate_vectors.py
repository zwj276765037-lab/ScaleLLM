#!/usr/bin/env python3
"""Generate one common 8x16x128 projection tile workload."""

from __future__ import annotations

import json
import random
import struct
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
ROWS, COLS, GROUPS, K = 8, 16, 128, 32
SEED = 0x4D_34_5449_4C45


def pack(values: list[int], width: int) -> int:
    word = 0
    mask = (1 << width) - 1
    for index, value in enumerate(values):
        word |= (value & mask) << (index * width)
    return word


def fp16_bits(value: float | np.floating) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def fp16_ftz(value: float | np.floating) -> np.float16:
    rounded = np.float16(value)
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        return np.float16(-0.0 if bits & 0x8000 else 0.0)
    return rounded


def fp16_mul_ip(a: np.float16, b: np.float16) -> np.float16:
    """Approximate AMD half multiply, including its normal-boundary tie.

    The core flushes denormal results.  At the lower normal boundary its
    underflow decision is made before the IEEE rounding promotion; empirical
    generated-IP vectors place the transition midway between the two adjacent
    exact products that bracket 0x0400.
    """
    product = np.float32(fp16_ftz(a)) * np.float32(fp16_ftz(b))
    tiny = float(np.finfo(np.float16).tiny)
    threshold = tiny - float(np.finfo(np.float16).smallest_subnormal) / 4.0
    if 0.0 < abs(float(product)) < threshold:
        return np.float16(-0.0 if np.signbit(product) else 0.0)
    return fp16_ftz(product)


def fp16_to_fp32_ip(value: np.float16) -> np.float32:
    """AMD half-to-single conversion treats half denormal inputs as zero."""
    return np.float32(fp16_ftz(value))


def round_even_s42(value: np.float32) -> int:
    result = int(np.rint(float(value) * (1 << 24)))
    if not -(1 << 41) <= result < (1 << 41):
        raise OverflowError(result)
    return result


def sat_s24(value_s42: int) -> int:
    magnitude = abs(value_s42)
    rounded = (magnitude + 128) >> 8
    rounded = -rounded if value_s42 < 0 else rounded
    return min((1 << 23) - 1, max(-(1 << 23), rounded))


def main() -> None:
    rng = random.Random(SEED)
    acts: list[list[list[int]]] = []
    weights: list[list[list[int]]] = []
    zps: list[list[int]] = []
    acodes: list[list[int]] = []
    ashifts: list[list[int]] = []
    wcodes: list[list[int]] = []
    wshifts: list[list[int]] = []
    for group in range(GROUPS):
        group_acts, group_zp, group_acode, group_ashift = [], [], [], []
        for row in range(ROWS):
            zp = rng.randrange(112, 145)
            group_acts.append([
                max(0, min(255, zp + rng.randrange(-8, 9))) for _ in range(K)
            ])
            group_zp.append(zp)
            group_acode.append(rng.randrange(64, 256))
            group_ashift.append(rng.randrange(16, 21))
        group_wgt, group_wcode, group_wshift = [], [], []
        for col in range(COLS):
            group_wgt.append([rng.randrange(-8, 9) for _ in range(K)])
            group_wcode.append(rng.randrange(64, 256))
            group_wshift.append(rng.randrange(16, 21))
        acts.append(group_acts)
        weights.append(group_wgt)
        zps.append(group_zp)
        acodes.append(group_acode)
        ashifts.append(group_ashift)
        wcodes.append(group_wcode)
        wshifts.append(group_wshift)

    mac_acc = [[0] * COLS for _ in range(ROWS)]
    sc_acc = [[0] * COLS for _ in range(ROWS)]
    f16_acc = [[0] * COLS for _ in range(ROWS)]
    f32_acc = [[0] * COLS for _ in range(ROWS)]
    fp16_group_zeros = 0
    for group in range(GROUPS):
        for row in range(ROWS):
            for col in range(COLS):
                corr = sum(
                    (a - zps[group][row]) * w
                    for a, w in zip(acts[group][row], weights[group][col])
                )
                scale_shift = ashifts[group][row] + wshifts[group][col]
                sc = (corr * acodes[group][row] * wcodes[group][col]) >> (
                    scale_shift - 24
                )
                a_scale = acodes[group][row] / float(1 << ashifts[group][row])
                w_scale = wcodes[group][col] / float(1 << wshifts[group][col])
                corr16 = fp16_ftz(np.float32(corr))
                with np.errstate(over="ignore", invalid="ignore"):
                    f16 = fp16_mul_ip(
                        fp16_mul_ip(corr16, np.float16(a_scale)),
                        np.float16(w_scale),
                    )
                f16_guard = int(np.trunc(float(fp16_to_fp32_ip(f16)) * (1 << 24)))
                corr32 = np.float32(corr)
                scale32 = np.float32(np.float32(a_scale) * np.float32(w_scale))
                f32_guard = round_even_s42(np.float32(corr32 * scale32))
                mac_acc[row][col] += corr
                sc_acc[row][col] += sc
                f16_acc[row][col] += f16_guard
                f32_acc[row][col] += f32_guard
                fp16_group_zeros += f16_guard == 0

    OUT.mkdir(parents=True, exist_ok=True)
    handles = {
        name: (OUT / name).open("w", encoding="ascii")
        for name in [
            "act_u8.mem", "weight_s8.mem", "zp_rows.mem", "scalecode_meta.mem",
            "fp16_meta.mem", "fp32_meta.mem", "expected_mac_s24.mem",
            "expected_scalecode_s24.mem", "expected_fp16_s24.mem",
            "expected_fp32_s24.mem",
        ]
    }
    try:
        for group in range(GROUPS):
            handles["act_u8.mem"].write(
                f"{pack(sum(acts[group], []), 8):0{ROWS*K*2}x}\n"
            )
            handles["weight_s8.mem"].write(
                f"{pack(sum(weights[group], []), 8):0{COLS*K*2}x}\n"
            )
            handles["zp_rows.mem"].write(
                f"{pack(zps[group], 8):0{ROWS*2}x}\n"
            )
            scmeta = []
            f16meta = []
            f32meta = []
            for row in range(ROWS):
                scmeta.append(acodes[group][row] | (ashifts[group][row] << 8))
                scale = acodes[group][row] / float(1 << ashifts[group][row])
                f16meta.append(fp16_bits(scale))
                f32meta.append(fp32_bits(scale))
            for col in range(COLS):
                scmeta.append(wcodes[group][col] | (wshifts[group][col] << 8))
                scale = wcodes[group][col] / float(1 << wshifts[group][col])
                f16meta.append(fp16_bits(scale))
                f32meta.append(fp32_bits(scale))
            handles["scalecode_meta.mem"].write(
                f"{pack(scmeta, 16):0{(ROWS+COLS)*4}x}\n"
            )
            handles["fp16_meta.mem"].write(
                f"{pack(f16meta, 16):0{(ROWS+COLS)*4}x}\n"
            )
            handles["fp32_meta.mem"].write(
                f"{pack(f32meta, 32):0{(ROWS+COLS)*8}x}\n"
            )
        for name, values in [
            ("expected_mac_s24.mem", mac_acc),
            ("expected_scalecode_s24.mem", sc_acc),
            ("expected_fp16_s24.mem", f16_acc),
            ("expected_fp32_s24.mem", f32_acc),
        ]:
            flattened = [sat_s24(values[row][col]) for row in range(ROWS)
                         for col in range(COLS)]
            handles[name].write(f"{pack(flattened, 24):0{ROWS*COLS*6}x}\n")
    finally:
        for handle in handles.values():
            handle.close()

    manifest = {
        "schema": "hap_m4_matched_projection_tile_v1",
        "seed": SEED,
        "rows": ROWS,
        "cols": COLS,
        "groups": GROUPS,
        "group_size": K,
        "macs": ROWS * COLS * GROUPS * K,
        "common_output": "8x16 signed S24 after S42 accumulation",
        "centering": "pre-MAC a-zp",
        "fp16_ip_semantics": "(corr*act_scale)*weight_scale; half denormals FTZ",
        "fp16_group_lane_zero_count": fp16_group_zeros,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("M4_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
