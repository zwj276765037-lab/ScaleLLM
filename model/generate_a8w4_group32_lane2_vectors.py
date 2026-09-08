#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "a8w4_group32_lane2"
VECTOR_COUNT = 2048


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack(values: list[int], width: int) -> int:
    output = 0
    for index, value in enumerate(values):
        output |= twos(value, width) << (index * width)
    return output


def align(raw: int, total_shift: int) -> int:
    value = raw << (24 - total_shift) if total_shift < 24 else \
        raw >> (total_shift - 24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError(f"guard overflow: {value}")
    return value


def main() -> None:
    rng = random.Random(0xA8_04_36)
    OUT.mkdir(parents=True, exist_ok=True)
    activations: list[str] = []
    weights: list[str] = []
    metadata: list[str] = []
    expected: list[str] = []
    for index in range(VECTOR_COUNT):
        if index == 0:
            acts = [255] * 32
            w0 = [-8] * 32
            w1 = [7] * 32
            act_code, act_shift = 255, 8
            w0_code, w0_shift = 255, 13
            w1_code, w1_shift = 255, 16
        elif index == 1:
            acts = [-255] * 32
            w0 = [-8] * 32
            w1 = [7] * 32
            act_code, act_shift = 255, 22
            w0_code, w0_shift = 255, 18
            w1_code, w1_shift = 255, 18
        else:
            acts = [rng.randint(-255, 255) for _ in range(32)]
            w0 = [rng.randint(-8, 7) for _ in range(32)]
            w1 = [rng.randint(-8, 7) for _ in range(32)]
            act_shift = rng.randint(8, 22)
            total0 = rng.randint(max(21, act_shift), min(44, act_shift + 18))
            total1 = rng.randint(max(21, act_shift), min(44, act_shift + 18))
            w0_shift = total0 - act_shift
            w1_shift = total1 - act_shift
            act_code = rng.randint(1, 255)
            w0_code = rng.randint(1, 255)
            w1_code = rng.randint(1, 255)
        dot0 = sum(a * w for a, w in zip(acts, w0, strict=True))
        dot1 = sum(a * w for a, w in zip(acts, w1, strict=True))
        guard0 = align(dot0 * act_code * w0_code, act_shift + w0_shift)
        guard1 = align(dot1 * act_code * w1_code, act_shift + w1_shift)
        activations.append(f"{pack(acts, 9):072x}")
        packed_weights = pack(w0, 4) | (pack(w1, 4) << 128)
        weights.append(f"{packed_weights:064x}")
        packed_meta = act_code | (act_shift << 8) | (w0_code << 14) | \
            (w0_shift << 22) | (w1_code << 28) | (w1_shift << 36)
        metadata.append(f"{packed_meta:011x}")
        expected.append(
            f"{(twos(guard1, 36) << 36) | twos(guard0, 36):018x}")
    for name, rows in (
        ("activation_s9x32.mem", activations),
        ("weights_s4x64.mem", weights),
        ("metadata_u42.mem", metadata),
        ("expected_s36x2.mem", expected),
    ):
        (OUT / name).write_text("\n".join(rows) + "\n", encoding="ascii")
    (OUT / "manifest.json").write_text(json.dumps({
        "vectors": VECTOR_COUNT,
        "seed": "0xA80436",
        "contract": "S17 dot * code8 * code8 aligned to S36 Q12.24",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: generated {VECTOR_COUNT} vectors in {OUT}")


if __name__ == "__main__":
    main()
