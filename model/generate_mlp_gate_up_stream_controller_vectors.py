#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path

from generate_mlp_input_frontend16_cache_vectors import (
    GROUPS, ROWS, build_row, hadamard, quantize,
)
from mlp_fixed import (
    build_silu_lut, hadamard32_product_normalized,
    robust_a8_quantize_s35, swiglu_product_s32,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_gate_up_stream_controller16_q4"
TILES, COLS = 4, 16


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


def align(raw: int, total_shift: int) -> int:
    result = raw << (24-total_shift) if total_shift < 24 else \
        raw >> (total_shift-24)
    if not -(1 << 35) <= result < (1 << 35):
        raise ValueError("S36 guard overflow")
    return result


def round_away(value: int) -> int:
    return (value+128) >> 8 if value >= 0 else -((-value+128) >> 8)


def main() -> None:
    rng = random.Random(0x6475_016)
    activation_rng = random.Random(0x16_CACE)
    silu_table = build_silu_lut()
    OUT.mkdir(parents=True, exist_ok=True)
    cache_u8_rows, cache_meta_rows = [], []
    centered_groups: list[list[list[int]]] = []
    act_codes_groups: list[list[int]] = []
    act_shifts_groups: list[list[int]] = []

    for group in range(GROUPS):
        quantized_rows, metadata = [], []
        centered_rows, act_codes, act_shifts = [], [], []
        for row in range(ROWS):
            source = build_row(activation_rng, group, row)
            transformed, _ = hadamard(source)
            quantized, meta = quantize(transformed)
            zero, code, shift = meta & 0xff, (meta >> 8) & 0xff, \
                (meta >> 16) & 0x3f
            quantized_rows.extend(quantized)
            metadata.append(meta)
            centered_rows.append([value-zero for value in quantized])
            act_codes.append(code)
            act_shifts.append(shift)
        cache_u8_rows.append(f"{pack(quantized_rows, 8):01024x}")
        cache_meta_rows.append(f"{pack(metadata, 24):096x}")
        centered_groups.append(centered_rows)
        act_codes_groups.append(act_codes)
        act_shifts_groups.append(act_shifts)

    weights_rows, weight_meta_rows, projections = [], [], []
    saturation_total = 0
    for tile in range(TILES):
        accum = [0]*(ROWS*COLS)
        for group in range(GROUPS):
            weights = [[rng.randint(-8, 7) for _ in range(32)]
                       for _ in range(COLS)]
            weight_codes = [rng.randint(1, 31) for _ in range(COLS)]
            weight_shifts = []
            act_shifts = act_shifts_groups[group]
            nonzero_act_shifts = [
                shift for code, shift in zip(
                    act_codes_groups[group], act_shifts, strict=True)
                if code != 0
            ]
            for _column in range(COLS):
                low = max(12, max(21-shift for shift in nonzero_act_shifts))
                high = min(18, min(44-shift for shift in nonzero_act_shifts))
                weight_shifts.append(rng.randint(low, high))
            for row in range(ROWS):
                for column in range(COLS):
                    dot = sum(a*w for a, w in zip(
                        centered_groups[group][row], weights[column],
                        strict=True))
                    raw = dot*act_codes_groups[group][row]*weight_codes[column]
                    accum[row*COLS+column] += align(
                        raw, act_shifts[row]+weight_shifts[column])
            weights_rows.append(
                f"{pack([value for column in weights for value in column], 4, True):0512x}")
            meta = pack(weight_codes, 8) | (pack(weight_shifts, 6) << 128)
            weight_meta_rows.append(f"{meta:056x}")
        projection = []
        for value in accum:
            rounded = round_away(value)
            saturated = max(-(1 << 23), min((1 << 23)-1, rounded))
            saturation_total += int(saturated != rounded)
            projection.append(saturated)
        projections.append(projection)

    expected_u8, expected_meta = [], []
    for row in range(ROWS):
        product = []
        for column in range(32):
            half = 0 if column < 16 else 2
            index = row*COLS+(column & 15)
            gate = projections[half][index]
            up = projections[half+1][index]
            product.append(swiglu_product_s32(gate, up, silu_table))
        transformed = hadamard32_product_normalized(product)
        quant = robust_a8_quantize_s35(transformed.values)
        expected_u8.extend(quant.values)
        expected_meta.append(quant.metadata)

    for name, rows in (
        ("cache_u8x16x32.mem", cache_u8_rows),
        ("cache_meta_u24x16.mem", cache_meta_rows),
        ("weights_s4x16x32.mem", weights_rows),
        ("weight_meta_u224.mem", weight_meta_rows),
        ("expected_activation_u8x16x32.mem", [f"{pack(expected_u8, 8):01024x}"]),
        ("expected_activation_meta_u24x16.mem", [f"{pack(expected_meta, 24):096x}"]),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "projection_tiles": TILES,
        "groups_per_tile": GROUPS,
        "weight_transactions": TILES*GROUPS,
        "down_activation_groups": TILES//4,
        "expected_projection_saturation": saturation_total,
        "seed": "0x6475016",
    }, indent=2)+"\n", encoding="utf-8")
    print("PASS: generated gate/up stream-controller vectors "
          f"saturation={saturation_total}")


if __name__ == "__main__":
    main()
