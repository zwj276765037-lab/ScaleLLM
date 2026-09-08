#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path

import generate_mlp_gate_up_stream_controller_vectors as gate


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_serial_ddr_command16_s45"
GATE_OUT = ROOT / "data" / "mlp_gate_up_stream_controller16_q4"
ROWS, COLS, GROUPS, TILES = 16, 16, 1, 8


def unpack(value: int, count: int, width: int, signed: bool = False) -> list[int]:
    mask = (1 << width)-1
    result = []
    for index in range(count):
        item = (value >> (index*width)) & mask
        if signed and item & (1 << (width-1)):
            item -= 1 << width
        result.append(item)
    return result


def align(raw: int, shift: int) -> int:
    value = raw << (24-shift) if shift < 24 else raw >> (shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 guard overflow")
    return value


def round_away(value: int) -> int:
    return (value+128) >> 8 if value >= 0 else -((-value+128) >> 8)


def main() -> None:
    # Reuse the signed-off gate/up vector construction so the integrated test
    # checks the exact same first phase before applying independently generated
    # down weights to its bit-exact A8 product result.
    gate.main()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("cache_u8x16x32.mem", "cache_meta_u24x16.mem",
                 "weights_s4x16x32.mem", "weight_meta_u224.mem"):
        (OUT/f"gate_{name}").write_text(
            (GATE_OUT/name).read_text(encoding="ascii"), encoding="ascii")

    activation_word = int((GATE_OUT/"expected_activation_u8x16x32.mem")
                          .read_text(encoding="ascii").strip(), 16)
    meta_word = int((GATE_OUT/"expected_activation_meta_u24x16.mem")
                    .read_text(encoding="ascii").strip(), 16)
    activation = unpack(activation_word, ROWS*32, 8)
    metadata = unpack(meta_word, ROWS, 24)
    centered = []
    act_codes, act_shifts = [], []
    for row in range(ROWS):
        zero = metadata[row] & 0xff
        act_codes.append((metadata[row] >> 8) & 0xff)
        act_shifts.append((metadata[row] >> 16) & 0x3f)
        centered.append([activation[row*32+lane]-zero for lane in range(32)])

    rng = random.Random(0x5E21_A1)
    weight_rows, weight_meta_rows = [], []
    accum = [[0]*(ROWS*COLS) for _ in range(TILES)]
    for tile in range(TILES):
        weights = [[rng.randint(-8, 7) for _ in range(32)]
                   for _ in range(COLS)]
        weight_codes = [rng.randint(1, 31) for _ in range(COLS)]
        nonzero_shifts = [shift for code, shift in zip(
            act_codes, act_shifts, strict=True) if code != 0]
        weight_shifts = []
        for _column in range(COLS):
            low = max(12, max(21-shift for shift in nonzero_shifts))
            high = min(18, min(44-shift for shift in nonzero_shifts))
            weight_shifts.append(rng.randint(low, high))
        for row in range(ROWS):
            for column in range(COLS):
                dot = sum(a*w for a, w in zip(
                    centered[row], weights[column], strict=True))
                raw = dot*act_codes[row]*weight_codes[column]
                accum[tile][row*COLS+column] += align(
                    raw, act_shifts[row]+weight_shifts[column])
        weight_rows.append(
            f"{gate.pack([v for col in weights for v in col], 4, True):0512x}")
        weight_meta_rows.append(
            f"{(gate.pack(weight_codes,8)|(gate.pack(weight_shifts,6)<<128)):056x}")

    expected_rows, saturation = [], 0
    for tile in range(TILES):
        values = []
        for accumulated in accum[tile]:
            rounded = round_away(accumulated)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation += int(saturated != rounded)
            values.append(saturated)
        expected_rows.append(
            f"{gate.pack(values,24,True):01536x}")

    for name, rows in (
        ("down_weights_s4x16x32.mem", weight_rows),
        ("down_weight_meta_u224.mem", weight_meta_rows),
        ("expected_s24x16x16.mem", expected_rows),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "gate_tiles": gate.TILES,
        "hidden_groups": gate.GROUPS,
        "gate_transactions": gate.TILES*gate.GROUPS,
        "down_groups": GROUPS,
        "down_tiles": TILES,
        "down_transactions": GROUPS*TILES,
        "expected_saturation": saturation,
        "seed": "0x5e21a1",
    }, indent=2)+"\n", encoding="utf-8")
    print("PASS: generated serial gate/up+down DDR vectors "
          f"down_saturation={saturation}")


if __name__ == "__main__":
    main()
