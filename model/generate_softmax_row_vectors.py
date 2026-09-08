#!/usr/bin/env python3
"""Generate deterministic 128-key Softmax row vectors."""

from __future__ import annotations

import json
import random
from pathlib import Path

from fixbit_v2 import FORMAT_ID, softmax_row_u16, self_test


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "softmax_row_128"
ROW_COUNT = 32
KEY_COUNT = 128
SEED = 0x53_4D_52_4F_57_4838_4102


def build_rows() -> list[tuple[list[int], list[bool]]]:
    rng = random.Random(SEED)
    rows: list[tuple[list[int], list[bool]]] = []
    # Single visible key exercises U0.16 clamp semantics (65535, not 65536).
    rows.append(([0] * KEY_COUNT, [False] + [True] * (KEY_COUNT - 1)))
    # Maximum sum and tied maxima exercise the exact U24 2^23 endpoint.
    rows.append(([0] * KEY_COUNT, [False] * KEY_COUNT))
    rows.append(([(16 << 14) if index & 1 else -(16 << 14)
                  for index in range(KEY_COUNT)], [False] * KEY_COUNT))
    # Causal prefixes including boundaries.
    for visible in (2, 17, 64, 127):
        scores = [rng.randint(-(16 << 14), 16 << 14)
                  for _ in range(KEY_COUNT)]
        rows.append((scores, [index >= visible for index in range(KEY_COUNT)]))
    while len(rows) < ROW_COUNT:
        scores = [rng.randint(-(16 << 14), 16 << 14)
                  for _ in range(KEY_COUNT)]
        masks = [rng.random() < 0.2 for _ in range(KEY_COUNT)]
        masks[rng.randrange(KEY_COUNT)] = False
        rows.append((scores, masks))
    return rows


def main() -> None:
    self_test()
    rows = build_rows()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sums: list[int] = []
    reciprocals: list[int] = []
    clamp_total = 0
    with (OUT_DIR / "input.mem").open("w", encoding="ascii") as input_file, \
            (OUT_DIR / "expected_prob.mem").open("w", encoding="ascii") as prob_file, \
            (OUT_DIR / "expected_exp.mem").open("w", encoding="ascii") as exp_file:
        for scores, masks in rows:
            probabilities, exponents, row_sum, reciprocal = \
                softmax_row_u16(scores, masks)
            sums.append(row_sum)
            reciprocals.append(reciprocal)
            for score, mask, probability, exponent in zip(
                    scores, masks, probabilities, exponents):
                input_file.write(f"{((int(mask) << 20) | (score & 0xfffff)):06x}\n")
                prob_file.write(f"{probability:04x}\n")
                exp_file.write(f"{exponent:05x}\n")
                clamp_total += int(probability == 65535)
    manifest = {
        "schema": "hap_fixbit_v2_softmax_row_128_vectors_v1",
        "format_id": f"0x{FORMAT_ID:08x}",
        "seed": SEED,
        "rows": ROW_COUNT,
        "keys_per_row": KEY_COUNT,
        "row_sum_min": min(sums),
        "row_sum_max": max(sums),
        "reciprocal_min": min(reciprocals),
        "reciprocal_max": max(reciprocals),
        "probability_65535_count": clamp_total,
        "includes_all_masked_error_test": True,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("SOFTMAX_ROW_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: Softmax row vectors generated.")


if __name__ == "__main__":
    main()
