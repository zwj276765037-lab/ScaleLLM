#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path

from mlp_fixed import hadamard32_product_normalized, minmax_a8_quantize_s35


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_product_frontend16_q4"
GROUPS = 4
ROWS = 16


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def main() -> None:
    rng = random.Random(0xF16_04)
    OUT.mkdir(parents=True, exist_ok=True)
    product_rows: list[str] = []
    expected_u8_rows: list[str] = []
    expected_meta_rows: list[str] = []

    for group in range(GROUPS):
        products: list[int] = []
        quantized: list[int] = []
        metadata: list[int] = []
        for row in range(ROWS):
            if group == 0 and row == 0:
                values = [0] * 32
            elif group == 0 and row == 1:
                values = [((lane % 9)-4) << 16 for lane in range(32)]
            else:
                values = [rng.randint(-(64 << 16), (64 << 16)-1)
                          for _ in range(32)]
            hadamard = hadamard32_product_normalized(values)
            quant = minmax_a8_quantize_s35(hadamard.values)
            products.extend(values)
            quantized.extend(quant.values)
            metadata.append(quant.metadata)
        product_payload = sum(twos(value, 32) << (index*32)
                              for index, value in enumerate(products))
        quant_payload = sum(value << (index*8)
                            for index, value in enumerate(quantized))
        meta_payload = sum(value << (index*24)
                           for index, value in enumerate(metadata))
        product_rows.append(f"{product_payload:04096x}")
        expected_u8_rows.append(f"{quant_payload:01024x}")
        expected_meta_rows.append(f"{meta_payload:096x}")

    (OUT / "product_s32x16x32.mem").write_text(
        "\n".join(product_rows) + "\n", encoding="ascii")
    (OUT / "expected_u8x16x32.mem").write_text(
        "\n".join(expected_u8_rows) + "\n", encoding="ascii")
    (OUT / "expected_meta_u24x16.mem").write_text(
        "\n".join(expected_meta_rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "groups": GROUPS,
        "rows": ROWS,
        "lanes": 32,
        "quantizers": 4,
        "seed": "0xf1604",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {GROUPS} cohort16 product frontend vectors")


if __name__ == "__main__":
    main()
