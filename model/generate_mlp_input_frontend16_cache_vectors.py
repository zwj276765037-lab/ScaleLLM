#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path

from fixbit_v2 import hadamard32_normalized, minmax_a8_quantize


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_input_frontend16_cache"
GROUPS, ROWS, LANES = 128, 16, 32


def signed(value: int, width: int) -> int:
    if not -(1 << (width-1)) <= value < (1 << (width-1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value


def twos(value: int, width: int) -> int:
    return signed(value, width) & ((1 << width)-1)


def hadamard(values: list[int]) -> tuple[list[int], int]:
    result = hadamard32_normalized(values)
    return list(result.values), result.saturation_count


def quantize(values: list[int]) -> tuple[list[int], int]:
    result = minmax_a8_quantize(values)
    return list(result.values), result.metadata


def build_row(rng: random.Random, group: int, row: int) -> list[int]:
    mode = (group+row) % 6
    if mode == 0:
        return [0]*LANES
    if mode == 1:
        return [(lane-16) << 14 for lane in range(LANES)]
    if mode == 2:
        return [-(1 << 23) if lane & 1 else (1 << 23)-1
                for lane in range(LANES)]
    if mode == 3:
        return [rng.randint(-(2 << 16), (2 << 16)-1) for _ in range(LANES)]
    if mode == 4:
        impulse = [0]*LANES
        impulse[(group*ROWS+row) % LANES] = rng.randint(
            -(64 << 16), (64 << 16)-1)
        return impulse
    return [rng.randint(-(64 << 16), (64 << 16)-1) for _ in range(LANES)]


def main() -> None:
    rng = random.Random(0x16_CACE)
    OUT.mkdir(parents=True, exist_ok=True)
    input_rows, u8_rows, meta_rows = [], [], []
    saturation_total = 0
    for group in range(GROUPS):
        inputs, outputs, metadata = [], [], []
        for row in range(ROWS):
            values = build_row(rng, group, row)
            transformed = hadamard32_normalized(values)
            quantized = minmax_a8_quantize(transformed.values)
            inputs.extend(values)
            outputs.extend(quantized.values)
            metadata.append(quantized.metadata)
            saturation_total += transformed.saturation_count
        input_rows.append(f"{sum(twos(v, 24) << (i*24) for i,v in enumerate(inputs)):03072x}")
        u8_rows.append(f"{sum(v << (i*8) for i,v in enumerate(outputs)):01024x}")
        meta_rows.append(f"{sum(v << (i*24) for i,v in enumerate(metadata)):096x}")
    for name, rows in (
        ("input_s24x16x32.mem", input_rows),
        ("expected_u8x16x32.mem", u8_rows),
        ("expected_meta_u24x16.mem", meta_rows),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "groups": GROUPS, "requests": ROWS, "lanes": LANES,
        "hadamard_saturation_count": saturation_total,
        "seed": "0x16cace",
    }, indent=2)+"\n", encoding="utf-8")
    print("PASS: generated cohort16 MLP input frontend/cache vectors "
          f"saturation={saturation_total}")


if __name__ == "__main__":
    main()
