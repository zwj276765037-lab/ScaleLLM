#!/usr/bin/env python3

from __future__ import annotations

import json
import random
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUPS = 5
TILES = 8


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def round_away(value: int) -> int:
    return (value + 128) >> 8 if value >= 0 else -((-value + 128) >> 8)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lanes", type=int, default=128,
                        choices=(96, 128))
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "data" / "mlp_down_group_major_accum_s45")
    args = parser.parse_args()
    lanes = args.lanes
    out = args.out if args.out.is_absolute() else ROOT / args.out
    rng = random.Random(0xD045_8256)
    out.mkdir(parents=True, exist_ok=True)
    accum = [[0 for _ in range(lanes)] for _ in range(TILES)]
    guard_rows: list[str] = []
    for group in range(GROUPS):
        for tile in range(TILES):
            guards = [rng.randint(-(1 << 31), (1 << 31)-1)
                      for _ in range(lanes)]
            if group == 0 and tile == 0:
                guards[0] = (1 << 35)-1
                guards[1] = -(1 << 35)
            for lane, value in enumerate(guards):
                accum[tile][lane] += value
            payload = sum(twos(value, 36) << (lane*36)
                          for lane, value in enumerate(guards))
            guard_rows.append(f"{payload:0{lanes * 9}x}")

    expected_rows: list[str] = []
    saturation_count = 0
    for tile in range(TILES):
        projection = []
        for value in accum[tile]:
            rounded = round_away(value)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation_count += int(saturated != rounded)
            projection.append(saturated)
        payload = sum(twos(value, 24) << (lane*24)
                      for lane, value in enumerate(projection))
        expected_rows.append(f"{payload:0{lanes * 6}x}")

    (out / "guard_s36x8.mem").write_text(
        "\n".join(guard_rows) + "\n", encoding="ascii")
    (out / "expected_s24x8.mem").write_text(
        "\n".join(expected_rows) + "\n", encoding="ascii")
    (out / "expected_saturation.mem").write_text(
        f"{saturation_count:08x}\n", encoding="ascii")
    (out / "manifest.json").write_text(json.dumps({
        "groups": GROUPS,
        "tiles": TILES,
        "lanes": lanes,
        "expected_saturation_count": saturation_count,
        "seed": "0xd0458256",
        "loop_order": "input_group_then_output_tile",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated group-major down accumulator vectors, lanes={lanes}, saturation={saturation_count}")


if __name__ == "__main__":
    main()
