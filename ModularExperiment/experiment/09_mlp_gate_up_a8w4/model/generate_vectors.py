#!/usr/bin/env python3
"""Generate deterministic multi-seed Gate/Up A8W4 projection tiles."""

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
ROWS, COLS, GROUPS, K = 16, 12, 128, 32
SEEDS = [0x9041, 0x9042, 0x9043, 0x9044, 0x9045,
         0x9046, 0x9047, 0x9048, 0x9049, 0x904A, 0x904B, 0x904C]
MASKS = [0xFFF, 0xFFF, 0x0FF, 0xFFF, 0x00F, 0xFFF,
         0xFFF, 0x0FF, 0xFFF, 0xFFF, 0xFFF, 0x0FF]


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
    product = np.float32(fp16_ftz(lhs)) * np.float32(fp16_ftz(rhs))
    tiny = float(np.finfo(np.float16).tiny)
    threshold = tiny - float(np.finfo(np.float16).smallest_subnormal) / 4.0
    if 0.0 < abs(float(product)) < threshold:
        return np.float16(-0.0 if np.signbit(product) else 0.0)
    return fp16_ftz(product)


def fp16_accum_result_ip(value: float) -> np.float16:
    """Model Floating-Point accumulator result truncation toward zero."""
    rounded = np.float16(value)
    if (math.isfinite(value) and np.isfinite(rounded) and
            abs(float(rounded)) > abs(value)):
        rounded = np.nextafter(rounded, np.float16(0.0), dtype=np.float16)
    return fp16_ftz(rounded)


def fp32_accum_result_ip(value: float) -> np.float32:
    """Model Floating-Point accumulator result truncation toward zero."""
    rounded = np.float32(value)
    if (math.isfinite(value) and np.isfinite(rounded) and
            abs(float(rounded)) > abs(value)):
        rounded = np.nextafter(rounded, np.float32(0.0), dtype=np.float32)
    return rounded


def round_sat_s24(real_value: float) -> int:
    if not math.isfinite(real_value):
        return -(1 << 23) if real_value < 0 else (1 << 23) - 1
    scaled = int(np.rint(real_value * (1 << 16)))
    return max(-(1 << 23), min((1 << 23) - 1, scaled))


def sc_round_sat(acc_s43: int) -> int:
    magnitude = abs(acc_s43)
    rounded = (magnitude + 128) >> 8
    rounded = -rounded if acc_s43 < 0 else rounded
    return max(-(1 << 23), min((1 << 23) - 1, rounded))


def metrics(reference: list[float], reconstructed: list[float]) -> dict[str, float]:
    ref = np.asarray(reference, dtype=np.float64)
    got = np.asarray(reconstructed, dtype=np.float64)
    error = got - ref
    denom = float(np.linalg.norm(ref) * np.linalg.norm(got))
    return {
        "max_abs": float(np.max(np.abs(error))),
        "mean_abs": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "cosine": float(np.dot(ref, got) / denom) if denom else 1.0,
    }


def write_word(handle, value: int, bits: int) -> None:
    handle.write(f"{value & ((1 << bits) - 1):0{(bits + 3) // 4}x}\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = [
        "activation_s9x16x32.mem", "weights_s4x12x32.mem",
        "activation_meta_sc_u224.mem", "weight_meta_sc_u168.mem",
        "activation_scale_fp16x16.mem", "weight_scale_fp16x12.mem",
        "activation_scale_fp32x16.mem", "weight_scale_fp32x12.mem",
        "column_mask_u12.mem", "expected_sc_s24x16x12.mem",
        "expected_fp16_s24x16x12.mem", "expected_fp32_s24x16x12.mem",
    ]
    handles = {name: (OUT / name).open("w", encoding="ascii") for name in names}
    ref_values: list[float] = []
    sc_values: list[float] = []
    fp16_values: list[float] = []
    fp32_values: list[float] = []
    fp16_zero_contributions = 0
    fp16_nonfinite = 0
    total_transactions = 0

    try:
        for tile, seed in enumerate(SEEDS):
            rng = random.Random(seed)
            mask = MASKS[tile]
            sc_acc = [[0 for _ in range(COLS)] for _ in range(ROWS)]
            fp16_terms = [[[] for _ in range(COLS)] for _ in range(ROWS)]
            fp32_terms = [[[] for _ in range(COLS)] for _ in range(ROWS)]
            real_acc = [[0.0 for _ in range(COLS)] for _ in range(ROWS)]

            for group in range(GROUPS):
                if tile == 0 and group == 0:
                    activations = [[0] * K for _ in range(ROWS)]
                    weights = [[0] * K for _ in range(COLS)]
                else:
                    activations = [
                        [rng.randrange(-32, 33) for _ in range(K)]
                        for _ in range(ROWS)
                    ]
                    weights = [
                        [rng.randrange(-8, 8) for _ in range(K)]
                        for _ in range(COLS)
                    ]
                acodes = [rng.randrange(96, 256) for _ in range(ROWS)]
                ashifts = [rng.randrange(12, 15) for _ in range(ROWS)]
                wcodes = [rng.randrange(96, 256) for _ in range(COLS)]
                wshifts = [rng.randrange(13, 16) for _ in range(COLS)]

                # Keep every legal path inside the production total-shift set.
                for row in range(ROWS):
                    for col in range(COLS):
                        assert 25 <= ashifts[row] + wshifts[col] <= 29

                act_scale_real = [
                    acodes[row] / float(1 << ashifts[row])
                    for row in range(ROWS)
                ]
                weight_scale_real = [
                    wcodes[col] / float(1 << wshifts[col])
                    if (mask >> col) & 1 else 0.0
                    for col in range(COLS)
                ]
                act_scale16 = [fp16_ftz(value) for value in act_scale_real]
                weight_scale16 = [fp16_ftz(value) for value in weight_scale_real]
                act_scale32 = [np.float32(value) for value in act_scale_real]
                weight_scale32 = [np.float32(value) for value in weight_scale_real]

                write_word(handles["activation_s9x16x32.mem"],
                           pack(sum(activations, []), 9), ROWS*K*9)
                write_word(handles["weights_s4x12x32.mem"],
                           pack(sum(weights, []), 4), COLS*K*4)
                write_word(handles["activation_meta_sc_u224.mem"],
                           pack(acodes, 8) | (pack(ashifts, 6) << (ROWS*8)),
                           ROWS*14)
                write_word(handles["weight_meta_sc_u168.mem"],
                           pack(wcodes, 8) | (pack(wshifts, 6) << (COLS*8)),
                           COLS*14)
                write_word(handles["activation_scale_fp16x16.mem"],
                           pack([fp16_bits(v) for v in act_scale16], 16),
                           ROWS*16)
                write_word(handles["weight_scale_fp16x12.mem"],
                           pack([fp16_bits(v) for v in weight_scale16], 16),
                           COLS*16)
                write_word(handles["activation_scale_fp32x16.mem"],
                           pack([fp32_bits(v) for v in act_scale32], 32),
                           ROWS*32)
                write_word(handles["weight_scale_fp32x12.mem"],
                           pack([fp32_bits(v) for v in weight_scale32], 32),
                           COLS*32)
                write_word(handles["column_mask_u12.mem"], mask, 12)

                for row in range(ROWS):
                    for col in range(COLS):
                        corr = sum(a * w for a, w in
                                   zip(activations[row], weights[col]))
                        if not ((mask >> col) & 1):
                            corr = 0
                        total_shift = ashifts[row] + wshifts[col]
                        raw = corr * acodes[row] * wcodes[col]
                        sc_term = (raw << (24-total_shift)
                                   if total_shift < 24
                                   else raw >> (total_shift-24))
                        sc_acc[row][col] += sc_term
                        real_term = (corr * act_scale_real[row] *
                                     weight_scale_real[col])
                        real_acc[row][col] += real_term

                        corr16 = fp16_ftz(np.float32(corr))
                        term16 = fp16_mul_ip(
                            fp16_mul_ip(corr16, act_scale16[row]),
                            weight_scale16[col],
                        )
                        if not np.isfinite(term16):
                            fp16_nonfinite += 1
                        if int(term16.view(np.uint16)) & 0x7FFF == 0:
                            fp16_zero_contributions += 1
                        fp16_terms[row][col].append(term16)

                        term32 = np.float32(
                            np.float32(np.float32(corr) * act_scale32[row]) *
                            weight_scale32[col]
                        )
                        fp32_terms[row][col].append(term32)
                total_transactions += 1

            expected_sc: list[int] = []
            expected_fp16: list[int] = []
            expected_fp32: list[int] = []
            for row in range(ROWS):
                for col in range(COLS):
                    sc_out = sc_round_sat(sc_acc[row][col])
                    # Accumulator IP uses an extended fixed accumulator and
                    # rounds only its completed packet back to port precision.
                    # Floating-Point accumulator v7.1 keeps an extended fixed
                    # sum and truncates its packet result toward zero when it
                    # narrows back to the selected port precision.
                    sum16 = fp16_accum_result_ip(sum(
                        float(v) for v in fp16_terms[row][col]))
                    sum32 = fp32_accum_result_ip(sum(
                        float(v) for v in fp32_terms[row][col]))
                    f16_out = round_sat_s24(float(sum16))
                    f32_out = round_sat_s24(float(sum32))
                    expected_sc.append(sc_out)
                    expected_fp16.append(f16_out)
                    expected_fp32.append(f32_out)
                    if (mask >> col) & 1:
                        ref_values.append(real_acc[row][col])
                        sc_values.append(sc_out / float(1 << 16))
                        fp16_values.append(f16_out / float(1 << 16))
                        fp32_values.append(f32_out / float(1 << 16))

            write_word(handles["expected_sc_s24x16x12.mem"],
                       pack(expected_sc, 24), ROWS*COLS*24)
            write_word(handles["expected_fp16_s24x16x12.mem"],
                       pack(expected_fp16, 24), ROWS*COLS*24)
            write_word(handles["expected_fp32_s24x16x12.mem"],
                       pack(expected_fp32, 24), ROWS*COLS*24)
    finally:
        for handle in handles.values():
            handle.close()

    file_hashes = {
        name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        for name in names
    }
    manifest = {
        "schema": "scalellm_m09_gate_up_a8w4_v1",
        "rows": ROWS,
        "columns": COLS,
        "groups_per_tile": GROUPS,
        "group_size": K,
        "tiles": len(SEEDS),
        "transactions": total_transactions,
        "seeds": SEEDS,
        "column_masks": MASKS,
        "fp16_zero_contributions": fp16_zero_contributions,
        "fp16_nonfinite_contributions": fp16_nonfinite,
        "reference": "exact integer dot times exact code/2^shift scales",
        "fp_accumulator": "AMD rate-1 extended accumulator, TLAST per 128 groups",
        "accuracy": {
            "sc": metrics(ref_values, sc_values),
            "fp16": metrics(ref_values, fp16_values),
            "fp32": metrics(ref_values, fp32_values),
        },
        "sha256": file_hashes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("M09_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
