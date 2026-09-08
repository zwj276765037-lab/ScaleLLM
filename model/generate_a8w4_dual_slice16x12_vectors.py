#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "a8w4_dual_slice16x12_group"
VECTOR_COUNT = 112
ROWS = 16
COLS = 12
GROUP = 32
MASK_SEQUENCE = (0xFFF, 0x0FF, 0x00F)


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack_signed(values: list[int], width: int) -> int:
    return sum(twos(value, width) << (index * width)
               for index, value in enumerate(values))


def pack_unsigned(values: list[int], width: int) -> int:
    output = 0
    for index, value in enumerate(values):
        if not 0 <= value < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        output |= value << (index * width)
    return output


def align(raw: int, total_shift: int) -> int:
    value = raw << (24-total_shift) if total_shift < 24 else \
        raw >> (total_shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError(f"S36 guard overflow: {value}")
    return value


def main() -> None:
    rng = random.Random(0x16_12_36)
    OUT.mkdir(parents=True, exist_ok=True)
    activations_rows: list[str] = []
    weights_rows: list[str] = []
    activation_meta_rows: list[str] = []
    weight_meta_rows: list[str] = []
    mask_rows: list[str] = []
    expected_rows: list[str] = []

    clear_cut_index = 48
    for vector in range(VECTOR_COUNT):
        column_mask = MASK_SEQUENCE[vector % len(MASK_SEQUENCE)]
        activations = [[rng.randint(-255, 255) for _ in range(GROUP)]
                       for _ in range(ROWS)]
        weights = [[rng.randint(-8, 7) for _ in range(GROUP)]
                   for _ in range(COLS)]
        act_codes = [rng.randint(1, 255) for _ in range(ROWS)]
        act_shifts = [rng.randint(8, 22) for _ in range(ROWS)]
        weight_codes = [rng.randint(1, 255) for _ in range(COLS)]
        weight_shifts: list[int] = []
        for _column in range(COLS):
            low = max(0, max(21-shift for shift in act_shifts))
            high = min(18, min(44-shift for shift in act_shifts))
            weight_shifts.append(rng.randint(low, high))
        if vector == 0:
            act_shifts[0] = 8
            weight_shifts = [max(13, shift) for shift in weight_shifts]
            weight_shifts[0] = 13

        guards: list[int] = []
        for row in range(ROWS):
            for column in range(COLS):
                if not (column_mask >> column) & 1:
                    guards.append(0)
                    continue
                dot = sum(a*w for a, w in zip(
                    activations[row], weights[column], strict=True))
                raw = dot * act_codes[row] * weight_codes[column]
                guards.append(align(
                    raw, act_shifts[row]+weight_shifts[column]))

        activations_rows.append(
            f"{pack_signed([v for row in activations for v in row], 9):01152x}")
        weights_rows.append(
            f"{pack_signed([v for col in weights for v in col], 4):0384x}")
        activation_meta = pack_unsigned(act_codes, 8) | \
            (pack_unsigned(act_shifts, 6) << (ROWS*8))
        weight_meta = pack_unsigned(weight_codes, 8) | \
            (pack_unsigned(weight_shifts, 6) << (COLS*8))
        activation_meta_rows.append(f"{activation_meta:056x}")
        weight_meta_rows.append(f"{weight_meta:042x}")
        mask_rows.append(f"{column_mask:03x}")
        expected_rows.append(f"{pack_signed(guards, 36):01728x}")

    for name, rows in (
        ("activation_s9x16x32.mem", activations_rows),
        ("weights_s4x12x32.mem", weights_rows),
        ("activation_meta_u224.mem", activation_meta_rows),
        ("weight_meta_u168.mem", weight_meta_rows),
        ("column_valid_u12.mem", mask_rows),
        ("expected_s36x16x12.mem", expected_rows),
    ):
        (OUT / name).write_text("\n".join(rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "vectors": VECTOR_COUNT,
        "seed": "0x161236",
        "requests": ROWS,
        "columns": COLS,
        "group": GROUP,
        "masks": ["0xfff", "0x0ff", "0x00f"],
        "tail_contract": {
            "14336_columns": 8,
            "4096_columns": 4,
        },
        "expected_kernel_dsp48e2": 3072,
        "clear_cut_index": clear_cut_index,
    }, indent=2) + "\n", encoding="utf-8")
    print("PASS: generated V5 cohort16 16x12 vectors "
          f"vectors={VECTOR_COUNT} masks=12/8/4")


if __name__ == "__main__":
    main()
