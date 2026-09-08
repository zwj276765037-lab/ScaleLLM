#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_gate_up_dual_slice_s43"
TILES = 1
GROUPS = 128
ROWS = 16
COLS = 16


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack_signed(values: list[int], width: int) -> int:
    return sum(twos(value, width) << (index*width)
               for index, value in enumerate(values))


def pack_unsigned(values: list[int], width: int) -> int:
    output = 0
    for index, value in enumerate(values):
        if not 0 <= value < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        output |= value << (index*width)
    return output


def align(raw: int, total_shift: int) -> int:
    value = raw << (24-total_shift) if total_shift < 24 else \
        raw >> (total_shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 guard overflow")
    return value


def round_away(value: int) -> int:
    return (value + 128) >> 8 if value >= 0 else -((-value + 128) >> 8)


def main() -> None:
    rng = random.Random(0x16_43_128)
    OUT.mkdir(parents=True, exist_ok=True)
    activation_rows: list[str] = []
    weight_rows: list[str] = []
    activation_meta_rows: list[str] = []
    weight_meta_rows: list[str] = []
    expected_rows: list[str] = []
    saturation_total = 0

    for _tile in range(TILES):
        accum = [0] * (ROWS*COLS)
        for _group in range(GROUPS):
            activations = [[rng.randint(-63, 63) for _ in range(32)]
                           for _ in range(ROWS)]
            weights = [[rng.randint(-8, 7) for _ in range(32)]
                       for _ in range(COLS)]
            act_codes = [rng.randint(1, 63) for _ in range(ROWS)]
            act_shifts = [rng.randint(13, 20) for _ in range(ROWS)]
            weight_codes = [rng.randint(1, 63) for _ in range(COLS)]
            weight_shifts: list[int] = []
            for _column in range(COLS):
                low = max(12, max(21-shift for shift in act_shifts))
                high = min(18, min(44-shift for shift in act_shifts))
                weight_shifts.append(rng.randint(low, high))

            for row in range(ROWS):
                for column in range(COLS):
                    dot = sum(a*w for a, w in zip(
                        activations[row], weights[column], strict=True))
                    raw = dot * act_codes[row] * weight_codes[column]
                    accum[row*COLS+column] += align(
                        raw, act_shifts[row]+weight_shifts[column])

            activation_payload = pack_signed(
                [v for row in activations for v in row], 9)
            weight_payload = pack_signed(
                [v for column in weights for v in column], 4)
            activation_rows.append(f"{activation_payload:01152x}")
            weight_rows.append(f"{weight_payload:0512x}")
            activation_meta = pack_unsigned(act_codes, 8) | \
                (pack_unsigned(act_shifts, 6) << 128)
            weight_meta = pack_unsigned(weight_codes, 8) | \
                (pack_unsigned(weight_shifts, 6) << 128)
            activation_meta_rows.append(f"{activation_meta:056x}")
            weight_meta_rows.append(f"{weight_meta:056x}")

        projection: list[int] = []
        for value in accum:
            rounded = round_away(value)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation_total += int(saturated != rounded)
            projection.append(saturated)
        expected_rows.append(f"{pack_signed(projection, 24):01536x}")

    for name, rows in (
        ("activation_s9x16x32.mem", activation_rows),
        ("weights_s4x16x32.mem", weight_rows),
        ("activation_meta_u224.mem", activation_meta_rows),
        ("weight_meta_u224.mem", weight_meta_rows),
        ("expected_s24x16x16.mem", expected_rows),
    ):
        (OUT / name).write_text("\n".join(rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "tiles": TILES,
        "groups_per_tile": GROUPS,
        "requests": ROWS,
        "columns": COLS,
        "expected_saturation_count": saturation_total,
        "seed": "0x1643128",
        "ddr_weight_reads_per_group": 1,
        "local_weight_copies": 2,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {TILES} dual-slice S43 tile in {OUT}")


if __name__ == "__main__":
    main()
