#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path

from mlp_fixed import (
    build_silu_lut,
    hadamard32_product_normalized,
    robust_a8_quantize_s35,
    swiglu_product_s32,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_swiglu_product_frontend16_q4"
GROUPS = 3
ROWS = 16
COLS = 32


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack_signed(values: list[int], width: int) -> int:
    return sum(twos(value, width) << (index * width)
               for index, value in enumerate(values))


def main() -> None:
    rng = random.Random(0x516_1604)
    table = build_silu_lut()
    OUT.mkdir(parents=True, exist_ok=True)
    input_tiles: list[str] = []
    expected_u8: list[str] = []
    expected_meta: list[str] = []

    for group in range(GROUPS):
        gate = [[rng.randint(-(20 << 16), (20 << 16) - 1)
                 for _ in range(COLS)] for _ in range(ROWS)]
        up = [[rng.randint(-(8 << 16), (8 << 16) - 1)
               for _ in range(COLS)] for _ in range(ROWS)]
        if group == 0:
            gate[0] = [0] * COLS
            up[0] = [0] * COLS
            gate[1][0:4] = [-(20 << 16), -(16 << 16),
                            16 << 16, (20 << 16) - 1]

        # Required scheduler order: gate0, up0, gate1, up1.  Each tile is
        # row-major 16 requests x 16 intermediate columns.
        for second_half in (False, True):
            base = 16 if second_half else 0
            for source in (gate, up):
                tile = [source[row][base + column]
                        for row in range(ROWS) for column in range(16)]
                input_tiles.append(f"{pack_signed(tile, 24):01536x}")

        quantized: list[int] = []
        metadata: list[int] = []
        for row in range(ROWS):
            product = [swiglu_product_s32(gate[row][column],
                                           up[row][column], table)
                       for column in range(COLS)]
            hadamard = hadamard32_product_normalized(product)
            quant = robust_a8_quantize_s35(hadamard.values)
            quantized.extend(quant.values)
            metadata.append(quant.metadata)
        quant_payload = sum(value << (index * 8)
                            for index, value in enumerate(quantized))
        meta_payload = sum(value << (index * 24)
                           for index, value in enumerate(metadata))
        expected_u8.append(f"{quant_payload:01024x}")
        expected_meta.append(f"{meta_payload:096x}")

    (OUT / "projection_tiles_s24x16x16.mem").write_text(
        "\n".join(input_tiles) + "\n", encoding="ascii")
    (OUT / "expected_u8x16x32.mem").write_text(
        "\n".join(expected_u8) + "\n", encoding="ascii")
    (OUT / "expected_meta_u24x16.mem").write_text(
        "\n".join(expected_meta) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "groups": GROUPS,
        "requests": ROWS,
        "columns_per_group": COLS,
        "projection_tiles_per_group": 4,
        "silu_lanes": 2,
        "quantizers": 4,
        "seed": "0x5161604",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {GROUPS} SwiGLU/frontend groups in {OUT}")


if __name__ == "__main__":
    main()
