#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_down_ddr_command16_s45"
GROUPS, TILES, ROWS, COLS = 4, 4, 16, 16


def twos(value: int, width: int) -> int:
    if not -(1 << (width-1)) <= value < (1 << (width-1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width)-1)


def pack(values: list[int], width: int, signed: bool = False) -> int:
    result = 0
    for index, value in enumerate(values):
        encoded = twos(value, width) if signed else value
        if not signed and not 0 <= encoded < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        result |= encoded << (index*width)
    return result


def align(raw: int, shift: int) -> int:
    value = raw << (24-shift) if shift < 24 else raw >> (shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 guard overflow")
    return value


def round_away(value: int) -> int:
    return (value+128) >> 8 if value >= 0 else -((-value+128) >> 8)


def main() -> None:
    rng = random.Random(0xDD4C_016)
    OUT.mkdir(parents=True, exist_ok=True)
    activation_rows, activation_meta_rows = [], []
    weight_rows, weight_meta_rows = [], []
    accum = [[0]*(ROWS*COLS) for _ in range(TILES)]

    for group in range(GROUPS):
        centered = [[rng.randint(-31, 31) for _ in range(32)]
                    for _ in range(ROWS)]
        zero_points = [rng.randint(64, 191) for _ in range(ROWS)]
        activation_u8 = [value+zero_points[row]
                         for row, values in enumerate(centered)
                         for value in values]
        act_codes = [rng.randint(1, 31) for _ in range(ROWS)]
        act_shifts = [rng.randint(13, 20) for _ in range(ROWS)]
        activation_rows.append(f"{pack(activation_u8, 8):01024x}")
        activation_meta = sum((zero_points[row] | (act_codes[row] << 8) |
                               (act_shifts[row] << 16)) << (row*24)
                              for row in range(ROWS))
        activation_meta_rows.append(f"{activation_meta:096x}")

        for tile in range(TILES):
            weights = [[rng.randint(-8, 7) for _ in range(32)]
                       for _ in range(COLS)]
            weight_codes = [rng.randint(1, 31) for _ in range(COLS)]
            weight_shifts = []
            for _column in range(COLS):
                low = max(12, max(21-shift for shift in act_shifts))
                high = min(18, min(44-shift for shift in act_shifts))
                weight_shifts.append(rng.randint(low, high))
            for row in range(ROWS):
                for column in range(COLS):
                    dot = sum(a*w for a, w in zip(
                        centered[row], weights[column], strict=True))
                    raw = dot*act_codes[row]*weight_codes[column]
                    accum[tile][row*COLS+column] += align(
                        raw, act_shifts[row]+weight_shifts[column])
            weight_rows.append(f"{pack([v for col in weights for v in col], 4, True):0512x}")
            weight_meta = pack(weight_codes, 8) | \
                (pack(weight_shifts, 6) << 128)
            weight_meta_rows.append(f"{weight_meta:056x}")

    expected_rows, saturation = [], 0
    for tile in range(TILES):
        values = []
        for accumulated in accum[tile]:
            rounded = round_away(accumulated)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation += int(rounded != saturated)
            values.append(saturated)
        expected_rows.append(f"{pack(values, 24, True):01536x}")

    for name, rows in (
        ("activation_u8x16x32.mem", activation_rows),
        ("activation_meta_u24x16.mem", activation_meta_rows),
        ("weights_s4x16x32.mem", weight_rows),
        ("weight_meta_u224.mem", weight_meta_rows),
        ("expected_s24x16x16.mem", expected_rows),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "groups": GROUPS, "tiles": TILES,
        "weight_transactions": GROUPS*TILES,
        "beats_per_channel": GROUPS*TILES*2,
        "bursts_per_channel": GROUPS*TILES//8,
        "expected_saturation_count": saturation,
        "seed": "0xdd4c016",
    }, indent=2)+"\n", encoding="utf-8")
    print(f"PASS: generated MLP DDR command vectors saturation={saturation}")


if __name__ == "__main__":
    main()
