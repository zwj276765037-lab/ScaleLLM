#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_shared_slice8x12"
ROWS, COLS, K = 8, 12, 32
GATE_GROUPS, DOWN_GROUPS = 128, 448
TRANSACTIONS = GATE_GROUPS + DOWN_GROUPS


def twos(value: int, width: int) -> int:
    if not -(1 << (width-1)) <= value < (1 << (width-1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width)-1)


def pack(values: list[int], width: int, signed: bool = False) -> int:
    output = 0
    for index, value in enumerate(values):
        encoded = twos(value, width) if signed else value
        if not signed and not 0 <= encoded < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        output |= encoded << (index*width)
    return output


def align(raw: int, total_shift: int) -> int:
    value = raw << (24-total_shift) if total_shift < 24 else \
        raw >> (total_shift-24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 overflow")
    return value


def round_away(value: int) -> int:
    return (value+128) >> 8 if value >= 0 else -((-value+128) >> 8)


def main() -> None:
    rng = random.Random(0x8_12_4345)
    OUT.mkdir(parents=True, exist_ok=True)
    activation_rows: list[str] = []
    weight_rows: list[str] = []
    activation_meta_rows: list[str] = []
    weight_meta_rows: list[str] = []
    tag_rows: list[str] = []
    mask_rows: list[str] = []
    gate_accum = [0]*(ROWS*COLS)
    down_accum = [0]*(ROWS*COLS)

    for transaction in range(TRANSACTIONS):
        down = transaction >= GATE_GROUPS
        group = transaction-GATE_GROUPS if down else transaction
        groups = DOWN_GROUPS if down else GATE_GROUPS
        # Tail masks are exercised on interior groups so the first/last tags
        # retain the production accumulator contract.
        column_mask = (0x0FF if group % 29 == 7 else
                       0x00F if group % 31 == 11 else 0xFFF)
        activations = [[rng.randint(-31, 31) for _ in range(K)]
                       for _ in range(ROWS)]
        weights = [[rng.randint(-8, 7) for _ in range(K)]
                   for _ in range(COLS)]
        act_codes = [rng.randint(1, 31) for _ in range(ROWS)]
        act_shifts = [rng.randint(13, 20) for _ in range(ROWS)]
        weight_codes = [rng.randint(1, 31) for _ in range(COLS)]
        weight_shifts: list[int] = []
        for _column in range(COLS):
            low = max(12, max(21-shift for shift in act_shifts))
            high = min(18, min(44-shift for shift in act_shifts))
            weight_shifts.append(rng.randint(low, high))
        target = down_accum if down else gate_accum
        for row in range(ROWS):
            for column in range(COLS):
                if not (column_mask >> column) & 1:
                    continue
                dot = sum(a*w for a, w in zip(
                    activations[row], weights[column], strict=True))
                raw = dot*act_codes[row]*weight_codes[column]
                target[row*COLS+column] += align(
                    raw, act_shifts[row]+weight_shifts[column])
        activation_rows.append(
            f"{pack([v for row in activations for v in row], 9, True):0576x}")
        weight_rows.append(
            f"{pack([v for col in weights for v in col], 4, True):0384x}")
        activation_meta_rows.append(
            f"{(pack(act_codes, 8)|(pack(act_shifts, 6)<<(ROWS*8))):028x}")
        weight_meta_rows.append(
            f"{(pack(weight_codes, 8)|(pack(weight_shifts, 6)<<(COLS*8))):042x}")
        # bit2=down, bit1=first, bit0=last
        tag_rows.append(f"{(int(down)<<2)|(int(group==0)<<1)|int(group==groups-1):01x}")
        mask_rows.append(f"{column_mask:03x}")

    def finish(accum: list[int]) -> list[int]:
        return [max(-(1 << 23), min((1 << 23)-1, round_away(value)))
                for value in accum]

    expected_gate = finish(gate_accum)
    expected_down = finish(down_accum)
    for name, rows in (
        ("activation_s9x8x32.mem", activation_rows),
        ("weights_s4x12x32.mem", weight_rows),
        ("activation_meta_u112.mem", activation_meta_rows),
        ("weight_meta_u168.mem", weight_meta_rows),
        ("tags_u3.mem", tag_rows),
        ("column_valid_u12.mem", mask_rows),
        ("expected_gate_s24x8x12.mem",
         [f"{pack(expected_gate, 24, True):0576x}"]),
        ("expected_down_s24x8x12.mem",
         [f"{pack(expected_down, 24, True):0576x}"]),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "rows": ROWS, "columns": COLS,
        "gate_groups": GATE_GROUPS, "down_groups": DOWN_GROUPS,
        "transactions": TRANSACTIONS,
        "seed": "0x8124345",
        "lane_order": "row*12+column",
    }, indent=2)+"\n", encoding="utf-8")
    print("PASS: generated V5 shared 8x12 S43/S45 vectors "
          f"transactions={TRANSACTIONS}")


if __name__ == "__main__":
    main()

