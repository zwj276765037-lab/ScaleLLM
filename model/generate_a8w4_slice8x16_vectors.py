#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "a8w4_slice8x16_group"
VECTOR_COUNT = 64


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack_signed(values: list[int], width: int) -> int:
    output = 0
    for index, value in enumerate(values):
        output |= twos(value, width) << (index * width)
    return output


def pack_unsigned(values: list[int], width: int) -> int:
    output = 0
    for index, value in enumerate(values):
        if not 0 <= value < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        output |= value << (index * width)
    return output


def align(raw: int, total_shift: int) -> int:
    value = raw << (24 - total_shift) if total_shift < 24 else \
        raw >> (total_shift - 24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError(f"guard overflow: {value}")
    return value


def main() -> None:
    rng = random.Random(0x8_16_36)
    OUT.mkdir(parents=True, exist_ok=True)
    activation_rows: list[str] = []
    weight_rows: list[str] = []
    activation_meta_rows: list[str] = []
    weight_meta_rows: list[str] = []
    expected_rows: list[str] = []
    for vector in range(VECTOR_COUNT):
        activations = [
            [rng.randint(-255, 255) for _ in range(32)]
            for _ in range(8)
        ]
        weights = [
            [rng.randint(-8, 7) for _ in range(32)]
            for _ in range(16)
        ]
        act_codes = [rng.randint(1, 255) for _ in range(8)]
        act_shifts = [rng.randint(8, 22) for _ in range(8)]
        weight_codes = [rng.randint(1, 255) for _ in range(16)]
        weight_shifts: list[int] = []
        for column in range(16):
            # A shared weight shift must be legal for all eight request rows.
            low = max(0, max(21-shift for shift in act_shifts))
            high = min(18, min(44-shift for shift in act_shifts))
            weight_shifts.append(rng.randint(low, high))
        if vector == 0:
            act_shifts[0] = 8
            # The W4 metadata is shared by every row.  After lowering row0's
            # activation shift, keep all 16 columns legal for that row.
            weight_shifts = [max(13, shift) for shift in weight_shifts]
            weight_shifts[0] = 13  # exercise total_shift=21 left shift
        guards: list[int] = []
        for row in range(8):
            for column in range(16):
                dot = sum(
                    a*w for a, w in zip(
                        activations[row], weights[column], strict=True))
                raw = dot * act_codes[row] * weight_codes[column]
                guards.append(align(
                    raw, act_shifts[row] + weight_shifts[column]))
        activation_rows.append(
            f"{pack_signed([v for row in activations for v in row], 9):0576x}")
        weight_rows.append(
            f"{pack_signed([v for col in weights for v in col], 4):0512x}")
        act_meta = pack_unsigned(act_codes, 8) | \
            (pack_unsigned(act_shifts, 6) << 64)
        weight_meta = pack_unsigned(weight_codes, 8) | \
            (pack_unsigned(weight_shifts, 6) << 128)
        activation_meta_rows.append(f"{act_meta:028x}")
        weight_meta_rows.append(f"{weight_meta:056x}")
        expected_rows.append(f"{pack_signed(guards, 36):01152x}")
    for name, rows in (
        ("activation_s9x8x32.mem", activation_rows),
        ("weights_s4x16x32.mem", weight_rows),
        ("activation_meta_u112.mem", activation_meta_rows),
        ("weight_meta_u224.mem", weight_meta_rows),
        ("expected_s36x8x16.mem", expected_rows),
    ):
        (OUT / name).write_text("\n".join(rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "vectors": VECTOR_COUNT,
        "seed": "0x81636",
        "rows": 8,
        "columns": 16,
        "group": 32,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {VECTOR_COUNT} 8x16 group vectors in {OUT}")


if __name__ == "__main__":
    main()
