#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_v5_dual_slice16x12"
ROWS = 16
COLS = 12
GROUP = 32
GATE_GROUPS = 128
DOWN_GROUPS = 5
DOWN_TILES = 4


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack_signed(values: list[int], width: int) -> int:
    return sum(twos(value, width) << (index * width)
               for index, value in enumerate(values))


def pack_unsigned(values: list[int], width: int) -> int:
    return sum(value << (index * width)
               for index, value in enumerate(values))


def align(raw: int, total_shift: int) -> int:
    value = raw << (24-total_shift) if total_shift < 24 else \
        raw >> (total_shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 guard overflow")
    return value


def round_away(value: int) -> int:
    return (value + 128) >> 8 if value >= 0 else -((-value + 128) >> 8)


def project(accumulator: list[int]) -> tuple[list[int], int]:
    output = []
    saturation = 0
    for value in accumulator:
        rounded = round_away(value)
        saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
        saturation += int(rounded != saturated)
        output.append(saturated)
    return output, saturation


def make_transaction(rng: random.Random, mask: int) -> tuple[
        list[list[int]], list[list[int]], list[int], list[int],
        list[int], list[int], list[int]]:
    activations = [[rng.randint(-63, 63) for _ in range(GROUP)]
                   for _ in range(ROWS)]
    weights = [[rng.randint(-8, 7) for _ in range(GROUP)]
               for _ in range(COLS)]
    act_codes = [rng.randint(1, 63) for _ in range(ROWS)]
    act_shifts = [rng.randint(12, 20) for _ in range(ROWS)]
    weight_codes = [rng.randint(1, 63) for _ in range(COLS)]
    weight_shifts = []
    for _ in range(COLS):
        low = max(4, max(21-shift for shift in act_shifts))
        high = min(20, min(44-shift for shift in act_shifts))
        weight_shifts.append(rng.randint(low, high))
    guards = []
    for row in range(ROWS):
        for column in range(COLS):
            if not (mask >> column) & 1:
                guards.append(0)
                continue
            dot = sum(a*w for a, w in zip(
                activations[row], weights[column], strict=True))
            guards.append(align(
                dot * act_codes[row] * weight_codes[column],
                act_shifts[row] + weight_shifts[column]))
    return (activations, weights, act_codes, act_shifts,
            weight_codes, weight_shifts, guards)


def append_transaction(rows: dict[str, list[str]], transaction: tuple,
                       mask: int) -> None:
    activations, weights, act_codes, act_shifts, \
        weight_codes, weight_shifts, _guards = transaction
    rows["activation_s9x16x32.mem"].append(
        f"{pack_signed([v for row in activations for v in row], 9):01152x}")
    rows["weights_s4x12x32.mem"].append(
        f"{pack_signed([v for column in weights for v in column], 4):0384x}")
    rows["activation_meta_u224.mem"].append(
        f"{(pack_unsigned(act_codes, 8) | (pack_unsigned(act_shifts, 6) << 128)):056x}")
    rows["weight_meta_u168.mem"].append(
        f"{(pack_unsigned(weight_codes, 8) | (pack_unsigned(weight_shifts, 6) << 96)):042x}")
    rows["column_valid_u12.mem"].append(f"{mask:03x}")


def main() -> None:
    rng = random.Random(0x512_4512)
    OUT.mkdir(parents=True, exist_ok=True)
    gate_rows = {name: [] for name in (
        "activation_s9x16x32.mem", "weights_s4x12x32.mem",
        "activation_meta_u224.mem", "weight_meta_u168.mem",
        "column_valid_u12.mem")}
    gate_accum = [0] * (ROWS*COLS)
    gate_guard_rows: list[str] = []
    for _group in range(GATE_GROUPS):
        transaction = make_transaction(rng, 0xFFF)
        append_transaction(gate_rows, transaction, 0xFFF)
        gate_guard_rows.append(
            f"{pack_signed(transaction[-1], 36):01728x}")
        for index, value in enumerate(transaction[-1]):
            gate_accum[index] += value
    gate_expected, gate_saturation = project(gate_accum)

    down_rows = {name: [] for name in gate_rows}
    down_accum = [[0] * (ROWS*COLS) for _ in range(DOWN_TILES)]
    for group in range(DOWN_GROUPS):
        for tile in range(DOWN_TILES):
            # The last tile uses the formal down 4-column mask.  This proves
            # masked lanes remain zero through both kernel and S45 state.
            mask = 0x00F if tile == DOWN_TILES-1 else 0xFFF
            transaction = make_transaction(rng, mask)
            append_transaction(down_rows, transaction, mask)
            for index, value in enumerate(transaction[-1]):
                down_accum[tile][index] += value
    down_expected = []
    down_saturation = 0
    for accumulator in down_accum:
        projection, saturation = project(accumulator)
        down_expected.append(projection)
        down_saturation += saturation

    for name, rows in gate_rows.items():
        (OUT / f"gate_{name}").write_text(
            "\n".join(rows) + "\n", encoding="ascii")
    for name, rows in down_rows.items():
        (OUT / f"down_{name}").write_text(
            "\n".join(rows) + "\n", encoding="ascii")
    (OUT / "gate_expected_s24x16x12.mem").write_text(
        f"{pack_signed(gate_expected, 24):01152x}\n", encoding="ascii")
    (OUT / "gate_expected_s36x16x12.mem").write_text(
        "\n".join(gate_guard_rows) + "\n", encoding="ascii")
    (OUT / "down_expected_s24x16x12.mem").write_text(
        "\n".join(f"{pack_signed(values, 24):01152x}"
                  for values in down_expected) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "rows": ROWS, "columns": COLS, "group": GROUP,
        "gate_groups": GATE_GROUPS,
        "down_groups": DOWN_GROUPS,
        "down_tiles": DOWN_TILES,
        "down_last_tile_mask": "0x00f",
        "gate_saturation": gate_saturation,
        "down_saturation": down_saturation,
        "seed": "0x5124512",
    }, indent=2) + "\n", encoding="utf-8")
    print("PASS: generated V5 dual-slice gate/down vectors "
          f"gate_sat={gate_saturation} down_sat={down_saturation}")


if __name__ == "__main__":
    main()
