#!/usr/bin/env python3
"""Generate the full 16x4096 MLP Down A8W4 comparison workload.

The activation payload is shared by every output tile in one intermediate
group.  Weight payloads are stored group-major, matching the production Down
scheduler: index = group * TILES + tile.  The final physical tile has four
valid columns and eight masked columns.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data"
ROWS, COLS, GROUPS, TILES, K = 16, 12, 448, 342, 32
VALID_COLUMNS = 4096
SEEDS = [0x1201, 0x1202, 0x1203, 0x1204, 0x1205, 0x1206,
         0x1207, 0x1208, 0x1209, 0x120A, 0x120B, 0x120C]
HEX = np.frombuffer(b"0123456789abcdef", dtype=np.uint8)


def pack(values: np.ndarray | list[int], width: int) -> int:
    result = 0
    mask = (1 << width) - 1
    for index, value in enumerate(values):
        result |= (int(value) & mask) << (index * width)
    return result


def fp16_bits(value: float | np.floating) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def fp16_ftz_array(value: np.ndarray) -> np.ndarray:
    rounded = np.asarray(value, dtype=np.float16).copy()
    bits = rounded.view(np.uint16)
    subnormal = (bits & np.uint16(0x7C00)) == 0
    bits[subnormal] &= np.uint16(0x8000)
    return bits.view(np.float16)


def fp16_mul_ip_array(lhs: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Model AMD half multiply, including the minimum-normal boundary.

    The generated floating-point IP decides underflow before an IEEE rounding
    promotion from the largest subnormal interval to ``0x0400``.  M02's
    generated-IP characterization measured the transition at one quarter of a
    half subnormal below the minimum normal value.  A plain NumPy cast followed
    by FTZ therefore retains ``0x0400`` for a narrow interval that the IP emits
    as signed zero.
    """
    lhs_ftz = fp16_ftz_array(lhs)
    rhs_ftz = fp16_ftz_array(rhs)
    product = lhs_ftz.astype(np.float32) * rhs_ftz.astype(np.float32)
    rounded = fp16_ftz_array(product)
    threshold = (
        float(np.finfo(np.float16).tiny) -
        float(np.finfo(np.float16).smallest_subnormal) / 4.0
    )
    underflow = (np.abs(product) > 0.0) & (np.abs(product) < threshold)
    rounded_bits = rounded.view(np.uint16)
    signed_zero = np.where(np.signbit(product), 0x8000, 0).astype(np.uint16)
    return np.where(underflow, signed_zero, rounded_bits).astype(
        np.uint16).view(np.float16)


def verify_fp16_mul_ip_boundary() -> int:
    """Fail closed if the measured AMD minimum-normal semantics drift."""
    cases = (
        (0x2425, 0x1BB8, 0x0000),
        (0xA5D1, 0x1980, 0x8000),
        (0x2425, 0x1BB9, 0x0400),
    )
    for lhs_bits, rhs_bits, expected_bits in cases:
        lhs = np.asarray([lhs_bits], dtype=np.uint16).view(np.float16)
        rhs = np.asarray([rhs_bits], dtype=np.uint16).view(np.float16)
        actual_bits = int(fp16_mul_ip_array(lhs, rhs).view(np.uint16)[0])
        if actual_bits != expected_bits:
            raise AssertionError(
                "AMD FP16 multiply boundary drift: "
                f"0x{lhs_bits:04x} * 0x{rhs_bits:04x} "
                f"expected=0x{expected_bits:04x} actual=0x{actual_bits:04x}")
    return len(cases)


def round_sat_s24_array(real_value: np.ndarray) -> np.ndarray:
    scaled = np.rint(np.asarray(real_value, dtype=np.float64) * (1 << 16))
    scaled = np.nan_to_num(
        scaled, nan=(1 << 23) - 1, posinf=(1 << 23) - 1,
        neginf=-(1 << 23),
    )
    return np.clip(scaled, -(1 << 23), (1 << 23) - 1).astype(np.int64)


def sc_round_sat_array(acc_s45: np.ndarray) -> np.ndarray:
    acc = np.asarray(acc_s45, dtype=np.int64)
    magnitude = np.abs(acc)
    rounded = (magnitude + 128) >> 8
    rounded = np.where(acc < 0, -rounded, rounded)
    return np.clip(rounded, -(1 << 23), (1 << 23) - 1).astype(np.int64)


def metrics(reference: np.ndarray, reconstructed: np.ndarray) -> dict[str, float]:
    ref = np.asarray(reference, dtype=np.float64).reshape(-1)
    got = np.asarray(reconstructed, dtype=np.float64).reshape(-1)
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


def packed_nibbles_hex(values: np.ndarray) -> str:
    """Pack signed/unsigned 4-bit values with element zero in the LSB."""
    nibbles = np.bitwise_and(np.asarray(values).reshape(-1), 0xF)
    return HEX[nibbles[::-1]].tobytes().decode("ascii")


def build_inputs() -> tuple[np.ndarray, ...]:
    activation_rng = np.random.default_rng(0x12A8_448)
    activations = activation_rng.integers(
        -32, 33, size=(GROUPS, ROWS, K), dtype=np.int16)
    activation_codes = activation_rng.integers(
        96, 256, size=(GROUPS, ROWS), dtype=np.uint16)
    activation_shifts = activation_rng.integers(
        12, 15, size=(GROUPS, ROWS), dtype=np.uint8)

    # Directed zero and signed-boundary groups are shared across all tiles.
    activations[0, :, :] = 0
    activations[1, :, :] = np.where(
        np.indices((ROWS, K)).sum(axis=0) & 1, 255, -255)
    activation_codes[0, :] = 0
    activation_shifts[0, :] = 12
    activation_codes[1, :] = 255
    activation_shifts[1, :] = 14

    weights = np.empty((GROUPS, TILES, COLS, K), dtype=np.int8)
    weight_codes = np.empty((GROUPS, TILES, COLS), dtype=np.uint16)
    weight_shifts = np.empty((GROUPS, TILES, COLS), dtype=np.uint8)
    for tile in range(TILES):
        seed = SEEDS[tile % len(SEEDS)] ^ (tile * 0x9E37)
        rng = np.random.default_rng(seed)
        weights[:, tile, :, :] = rng.integers(
            -8, 8, size=(GROUPS, COLS, K), dtype=np.int8)
        weight_codes[:, tile, :] = rng.integers(
            96, 256, size=(GROUPS, COLS), dtype=np.uint16)
        weight_shifts[:, tile, :] = rng.integers(
            13, 16, size=(GROUPS, COLS), dtype=np.uint8)

    weights[0, :, :, :] = 0
    weight_codes[0, :, :] = 0
    weight_shifts[0, :, :] = 13
    weights[1, 0, :, :] = np.where(
        np.indices((COLS, K)).sum(axis=0) & 1, 7, -8)
    weight_codes[1, 0, :] = 255
    weight_shifts[1, 0, :] = 15

    # The physical tail contains only output columns 4092..4095.
    weights[:, -1, 4:, :] = 0
    weight_codes[:, -1, 4:] = 0
    weight_shifts[:, -1, 4:] = 13
    return (activations, activation_codes, activation_shifts,
            weights, weight_codes, weight_shifts)


def main() -> None:
    verify_fp16_mul_ip_boundary()
    OUT.mkdir(parents=True, exist_ok=True)
    (activations, activation_codes, activation_shifts,
     weights, weight_codes, weight_shifts) = build_inputs()

    names = [
        "activation_s9x16x32.mem", "activation_meta_sc_u224.mem",
        "activation_scale_fp16x16.mem", "activation_scale_fp32x16.mem",
        "weights_s4x12x32.mem", "weight_meta_sc_u168.mem",
        "weight_scale_fp16x12.mem", "weight_scale_fp32x12.mem",
        "column_mask_u12.mem", "expected_sc_s24x16x12.mem",
        "expected_fp16_s24x16x12.mem", "expected_fp32_s24x16x12.mem",
    ]
    handles = {name: (OUT / name).open("w", encoding="ascii") for name in names}

    act_scale_real = activation_codes.astype(np.float64) / np.exp2(
        activation_shifts.astype(np.int16))
    act_scale16 = fp16_ftz_array(act_scale_real)
    act_scale32 = act_scale_real.astype(np.float32)
    weight_scale_real = weight_codes.astype(np.float64) / np.exp2(
        weight_shifts.astype(np.int16))
    weight_scale16 = fp16_ftz_array(weight_scale_real)
    weight_scale32 = weight_scale_real.astype(np.float32)
    reference_values: list[np.ndarray] = []
    sc_values: list[np.ndarray] = []
    fp16_values: list[np.ndarray] = []
    fp32_values: list[np.ndarray] = []
    fp16_zero_contributions = 0

    try:
        for group in range(GROUPS):
            write_word(handles["activation_s9x16x32.mem"],
                       pack(activations[group].reshape(-1), 9), ROWS*K*9)
            write_word(
                handles["activation_meta_sc_u224.mem"],
                pack(activation_codes[group], 8) |
                (pack(activation_shifts[group], 6) << (ROWS*8)),
                ROWS*14,
            )
            write_word(
                handles["activation_scale_fp16x16.mem"],
                pack([fp16_bits(v) for v in act_scale16[group]], 16),
                ROWS*16,
            )
            write_word(
                handles["activation_scale_fp32x16.mem"],
                pack([fp32_bits(v) for v in act_scale32[group]], 32),
                ROWS*32,
            )

        for tile in range(TILES):
            write_word(handles["column_mask_u12.mem"],
                       0x00F if tile == TILES-1 else 0xFFF, 12)

        # Compute each tile across all 448 groups, then retain one 16x12
        # completed projection.  NumPy performs the 32-element dots in C.
        expected_sc_all: list[np.ndarray] = []
        expected_fp16_all: list[np.ndarray] = []
        expected_fp32_all: list[np.ndarray] = []
        for tile in range(TILES):
            corr = np.einsum(
                "grk,gck->grc", activations.astype(np.int32),
                weights[:, tile].astype(np.int32), optimize=True,
            ).astype(np.int64)
            shifts = (activation_shifts[:, :, None].astype(np.int16) +
                      weight_shifts[:, tile, None, :].astype(np.int16))
            raw = (corr * activation_codes[:, :, None].astype(np.int64) *
                   weight_codes[:, tile, None, :].astype(np.int64))
            sc_terms = np.right_shift(raw, shifts - 24)
            sc_acc = np.sum(sc_terms, axis=0, dtype=np.int64)
            sc_out = sc_round_sat_array(sc_acc)

            corr16 = fp16_ftz_array(corr.astype(np.float32))
            term16 = fp16_mul_ip_array(
                fp16_mul_ip_array(corr16, act_scale16[:, :, None]),
                weight_scale16[:, tile, None, :],
            )
            fp16_zero_contributions += int(np.count_nonzero(
                (term16.view(np.uint16) & np.uint16(0x7FFF)) == 0))
            accum16 = np.zeros((ROWS, COLS), dtype=np.float32)
            accum32 = np.zeros((ROWS, COLS), dtype=np.float32)
            for group in range(GROUPS):
                accum16 = np.asarray(
                    accum16 + term16[group].astype(np.float32),
                    dtype=np.float32,
                )
                term32 = np.asarray(
                    np.asarray(corr[group], dtype=np.float32) *
                    act_scale32[group, :, None], dtype=np.float32)
                term32 = np.asarray(
                    term32 * weight_scale32[group, tile, None, :],
                    dtype=np.float32)
                accum32 = np.asarray(accum32 + term32, dtype=np.float32)

            fp16_out = round_sat_s24_array(accum16)
            fp32_out = round_sat_s24_array(accum32)
            real_acc = np.sum(
                corr.astype(np.float64) * act_scale_real[:, :, None] *
                weight_scale_real[:, tile, None, :], axis=0,
            )

            expected_sc_all.append(sc_out)
            expected_fp16_all.append(fp16_out)
            expected_fp32_all.append(fp32_out)
            valid = 4 if tile == TILES-1 else COLS
            reference_values.append(real_acc[:, :valid].reshape(-1))
            sc_values.append(sc_out[:, :valid].reshape(-1) / float(1 << 16))
            fp16_values.append(
                fp16_out[:, :valid].reshape(-1) / float(1 << 16))
            fp32_values.append(
                fp32_out[:, :valid].reshape(-1) / float(1 << 16))

        for group in range(GROUPS):
            for tile in range(TILES):
                handles["weights_s4x12x32.mem"].write(
                    packed_nibbles_hex(weights[group, tile]) + "\n")
                write_word(
                    handles["weight_meta_sc_u168.mem"],
                    pack(weight_codes[group, tile], 8) |
                    (pack(weight_shifts[group, tile], 6) << (COLS*8)),
                    COLS*14,
                )
                write_word(
                    handles["weight_scale_fp16x12.mem"],
                    pack([fp16_bits(v) for v in
                          weight_scale16[group, tile]], 16), COLS*16,
                )
                write_word(
                    handles["weight_scale_fp32x12.mem"],
                    pack([fp32_bits(v) for v in
                          weight_scale32[group, tile]], 32), COLS*32,
                )

        for tile in range(TILES):
            write_word(handles["expected_sc_s24x16x12.mem"],
                       pack(expected_sc_all[tile].reshape(-1), 24),
                       ROWS*COLS*24)
            write_word(handles["expected_fp16_s24x16x12.mem"],
                       pack(expected_fp16_all[tile].reshape(-1), 24),
                       ROWS*COLS*24)
            write_word(handles["expected_fp32_s24x16x12.mem"],
                       pack(expected_fp32_all[tile].reshape(-1), 24),
                       ROWS*COLS*24)
    finally:
        for handle in handles.values():
            handle.close()

    file_hashes = {
        name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        for name in names
    }
    ref = np.concatenate(reference_values)
    sc = np.concatenate(sc_values)
    fp16 = np.concatenate(fp16_values)
    fp32 = np.concatenate(fp32_values)
    generator = Path(__file__).resolve()
    manifest = {
        "schema": "scalellm_m12_down_a8w4_full_v1",
        "rows": ROWS,
        "physical_columns": COLS,
        "valid_output_columns": VALID_COLUMNS,
        "groups": GROUPS,
        "tiles": TILES,
        "transactions": GROUPS*TILES,
        "group_size": K,
        "ordering": "group-major: index=group*342+tile",
        "tail_mask": "0x00f",
        "seeds": SEEDS,
        "rng": "numpy PCG64; tile seed = seeds[tile%12] xor tile*0x9e37",
        "fp16_path": (
            "int17->FP32->FP16, two FP16 multiplies, "
            "FP16->FP32, FP32 state/add"
        ),
        "fp32_path": "int17->fp32, two FP32 multiplies, FP32 state/add",
        "fp16_zero_contributions": fp16_zero_contributions,
        "accuracy": {
            "sc": metrics(ref, sc),
            "fp16": metrics(ref, fp16),
            "fp32": metrics(ref, fp32),
        },
        "generator": str(generator),
        "generator_sha256": hashlib.sha256(generator.read_bytes()).hexdigest(),
        "sha256": file_hashes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("M12_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
