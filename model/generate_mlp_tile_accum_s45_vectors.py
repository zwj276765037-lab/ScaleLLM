#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_tile_accum_s45"
TILES = 2
GROUPS = 448
LANES = 128


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def round_away(value: int) -> int:
    return (value + 128) >> 8 if value >= 0 else -((-value + 128) >> 8)


def main() -> None:
    rng = random.Random(0x45_448)
    OUT.mkdir(parents=True, exist_ok=True)
    guards_rows: list[str] = []
    expected_rows: list[str] = []
    saturation_total = 0

    for tile in range(TILES):
        accum = [0] * LANES
        for group in range(GROUPS):
            guards: list[int] = []
            for lane in range(LANES):
                if tile == 0 and lane == 0:
                    value = (1 << 34) - 1
                elif tile == 0 and lane == 1:
                    value = -(1 << 34)
                elif group == 0 and lane == 2:
                    value = 127
                elif group == 0 and lane == 3:
                    value = -128
                else:
                    value = rng.randint(-(1 << 29), (1 << 29)-1)
                guards.append(value)
                accum[lane] += value
                if not -(1 << 44) <= accum[lane] < (1 << 44):
                    raise ValueError("S45 accumulator overflow in vector")
            packed = sum(twos(value, 36) << (lane*36)
                         for lane, value in enumerate(guards))
            guards_rows.append(f"{packed:01152x}")

        projection: list[int] = []
        for value in accum:
            rounded = round_away(value)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation_total += int(saturated != rounded)
            projection.append(saturated)
        packed_projection = sum(twos(value, 24) << (lane*24)
                                for lane, value in enumerate(projection))
        expected_rows.append(f"{packed_projection:0768x}")

    (OUT / "guard_s36x128.mem").write_text(
        "\n".join(guards_rows) + "\n", encoding="ascii")
    (OUT / "expected_s24x128.mem").write_text(
        "\n".join(expected_rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "tiles": TILES,
        "groups_per_tile": GROUPS,
        "lanes": LANES,
        "accumulator": "S45 Q21.24",
        "output": "S24 Q8.16",
        "rounding": "half away from zero / 2^8",
        "expected_saturation_count": saturation_total,
        "seed": "0x45448",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {TILES} S45 accumulator tiles in {OUT}")


if __name__ == "__main__":
    main()
