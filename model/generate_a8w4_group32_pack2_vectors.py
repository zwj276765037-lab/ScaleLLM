#!/usr/bin/env python3
"""Generate group32 A8W4 two-column dot-product vectors."""

from __future__ import annotations

import json
from pathlib import Path
import random

from mlp_fixed import a8w4_group32_two_column, sha256_file


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "a8w4_group32_pack2"
VECTOR_COUNT = 2048
SEED = 0x32_A8_04


def pack_signed(values: list[int], width: int) -> int:
    result = 0
    mask = (1 << width) - 1
    for lane, value in enumerate(values):
        result |= (value & mask) << (lane * width)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    vectors: list[tuple[list[int], list[int], list[int]]] = [
        ([-255] * 32, [-8] * 32, [7] * 32),
        ([255] * 32, [-8] * 32, [7] * 32),
        ([0] * 32, [-8] * 32, [7] * 32),
        ([(-255 if lane & 1 else 255) for lane in range(32)],
         [(-8 if lane & 1 else 7) for lane in range(32)],
         [(7 if lane & 1 else -8) for lane in range(32)]),
    ]
    while len(vectors) < VECTOR_COUNT:
        vectors.append((
            [rng.randint(-255, 255) for _ in range(32)],
            [rng.randint(-8, 7) for _ in range(32)],
            [rng.randint(-8, 7) for _ in range(32)],
        ))

    paths = {
        "activation_s9x32": OUT / "activation_s9x32.mem",
        "weights_s4x64": OUT / "weights_s4x64.mem",
        "expected_s17x2": OUT / "expected_s17x2.mem",
    }
    with paths["activation_s9x32"].open("w", encoding="ascii") as act_file, \
            paths["weights_s4x64"].open("w", encoding="ascii") as w_file, \
            paths["expected_s17x2"].open("w", encoding="ascii") as exp_file:
        for activations, weights0, weights1 in vectors:
            dot0, dot1 = a8w4_group32_two_column(
                activations, weights0, weights1)
            packed_weights = 0
            for lane in range(32):
                packed_weights |= (weights0[lane] & 0xF) << (lane * 8)
                packed_weights |= (weights1[lane] & 0xF) << (lane * 8 + 4)
            act_file.write(f"{pack_signed(activations, 9):072x}\n")
            w_file.write(f"{packed_weights:064x}\n")
            expected = (dot0 & 0x1FFFF) | ((dot1 & 0x1FFFF) << 17)
            exp_file.write(f"{expected:09x}\n")

    manifest = {
        "schema": "hap_a8w4_group32_pack2_vectors_v1",
        "vector_count": VECTOR_COUNT,
        "seed": SEED,
        "sha256": {name: sha256_file(path) for name, path in paths.items()},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
