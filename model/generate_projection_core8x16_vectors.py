#!/usr/bin/env python3
"""Generate input S24 -> H+A8 cache -> native 8x16 projection vectors."""

from __future__ import annotations

import json
import random
from pathlib import Path

from fixbit_v2 import (
    FORMAT_ID,
    a8w8_group32_guard_s42,
    hadamard32_normalized,
    pack_lanes,
    robust_a8_quantize,
    round_sat_guard_s42_to_s24,
    self_test,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "projection_core8x16"
ROWS = 8
COLS = 16
GROUPS = 128
TILES = 2
SEED = 0x50_52_4F_4A_4838_4102


def pack_unsigned(values: list[int], width: int) -> int:
    packed = 0
    for index, value in enumerate(values):
        packed |= int(value) << (index * width)
    return packed


def main() -> None:
    self_test()
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    accum_tiles = [[0] * (ROWS * COLS) for _ in range(TILES)]
    input_saturation = 0
    output_saturation = 0
    with (OUT_DIR / "input_s24.mem").open("w", encoding="ascii") as input_file, \
            (OUT_DIR / "weight_s8.mem").open("w", encoding="ascii") as weight_file, \
            (OUT_DIR / "weight_meta16.mem").open("w", encoding="ascii") as meta_file:
        for group in range(GROUPS):
            inputs = []
            activations = []
            for row in range(ROWS):
                source = [rng.randint(-(3 << 16), 3 << 16) for _ in range(32)]
                inputs.append(source)
                transformed = hadamard32_normalized(source)
                input_saturation += transformed.saturation_count
                activations.append(robust_a8_quantize(transformed.values))
            input_file.write(f"{pack_lanes([v for row in inputs for v in row], 24):01536x}\n")
            for tile in range(TILES):
                for col in range(COLS):
                    weights = [rng.randint(-127, 127) for _ in range(32)]
                    weight_code = rng.randint(1, 192)
                    min_act_shift = min(a.scale_shift for a in activations if a.scale_code)
                    max_act_shift = max(a.scale_shift for a in activations if a.scale_code)
                    minimum = max(0, 26 - min_act_shift)
                    maximum = min(32, 47 - max_act_shift)
                    weight_shift = rng.randint(minimum, maximum)
                    weight_file.write(f"{pack_lanes(weights, 8):064x}\n")
                    meta_file.write(f"{((weight_shift << 8) | weight_code):04x}\n")
                    for row in range(ROWS):
                        activation = activations[row]
                        contribution = a8w8_group32_guard_s42(
                            activation.values, weights, activation.zero_point,
                            activation.scale_code, activation.scale_shift,
                            weight_code, weight_shift)
                        accum_tiles[tile][row * COLS + col] += contribution
    with (OUT_DIR / "expected_s24.mem").open("w", encoding="ascii") as output_file:
        for accum in accum_tiles:
            packed_output = 0
            for lane, value in enumerate(accum):
                output, saturated = round_sat_guard_s42_to_s24(value)
                output_saturation += int(saturated)
                packed_output |= (output & 0xffffff) << (lane * 24)
            output_file.write(f"{packed_output:0768x}\n")
    manifest = {
        "schema": "hap_fixbit_v2_projection_core8x16_vectors_v1",
        "format_id": f"0x{FORMAT_ID:08x}",
        "seed": SEED,
        "rows": ROWS,
        "cols": COLS,
        "groups": GROUPS,
        "projection_tiles_from_one_cache_fill": TILES,
        "frontend_hadamard_saturation": input_saturation,
        "projection_saturation": output_saturation,
        "array_steady_ii": 2,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("PROJECTION_CORE8X16_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: Projection core8x16 vectors generated.")


if __name__ == "__main__":
    main()
