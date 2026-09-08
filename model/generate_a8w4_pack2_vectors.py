#!/usr/bin/env python3
"""Generate deterministic bit-exact vectors for the packed A8W4 leaf."""

from __future__ import annotations

import json
from pathlib import Path
import random

from mlp_fixed import a8w4_two_column_packed, sha256_file, twos_hex


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "a8w4_pack2"
VECTOR_COUNT = 8192
SEED = 0xA8_04_2025


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    activations = [-255, -254, -129, -128, -17, -16, -1, 0, 1, 15,
                   16, 127, 128, 254, 255]
    vectors: list[tuple[int, int, int]] = []
    for activation in activations:
        for weight0 in range(-8, 8):
            for weight1 in range(-8, 8):
                vectors.append((activation, weight0, weight1))
    while len(vectors) < VECTOR_COUNT:
        vectors.append((rng.randint(-255, 255), rng.randint(-8, 7),
                        rng.randint(-8, 7)))
    vectors = vectors[:VECTOR_COUNT]

    paths = {
        "activation_s9": OUT / "activation_s9.mem",
        "weights_s4x2": OUT / "weights_s4x2.mem",
        "expected_s12x2": OUT / "expected_s12x2.mem",
    }
    with paths["activation_s9"].open("w", encoding="ascii") as act_file, \
            paths["weights_s4x2"].open("w", encoding="ascii") as w_file, \
            paths["expected_s12x2"].open("w", encoding="ascii") as exp_file:
        for activation, weight0, weight1 in vectors:
            product0, product1 = a8w4_two_column_packed(
                activation, weight0, weight1)
            act_file.write(twos_hex(activation, 9) + "\n")
            w_file.write(twos_hex(weight1, 4) + twos_hex(weight0, 4) + "\n")
            exp_file.write(twos_hex(product1, 12) +
                           twos_hex(product0, 12) + "\n")

    manifest = {
        "schema": "hap_a8w4_pack2_vectors_v1",
        "vector_count": VECTOR_COUNT,
        "seed": SEED,
        "activation": "S9 constrained to [-255,255]",
        "weights": "two S4 values [-8,7]",
        "outputs": "two exact S12 products",
        "sha256": {name: sha256_file(path) for name, path in paths.items()},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
