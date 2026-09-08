#!/usr/bin/env python3
"""Generate deterministic S32-to-S35 normalized Hadamard32 vectors."""

from __future__ import annotations

import json
from pathlib import Path
import random

from mlp_fixed import (
    GROUP_SIZE, S32_MAX, S32_MIN, hadamard32_product_normalized,
    sha256_file, twos_hex,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_hadamard_s32"
VECTOR_COUNT = 96


def pack(values: list[int], width: int) -> str:
    packed = 0
    for lane, value in enumerate(values):
        packed |= (value & ((1 << width) - 1)) << (lane * width)
    return f"{packed:0{GROUP_SIZE * width // 4}x}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(0x533235484150)
    groups = [
        [0] * GROUP_SIZE,
        [1 << 16] + [0] * (GROUP_SIZE - 1),
        [S32_MAX] + [0] * (GROUP_SIZE - 1),
        [S32_MIN] + [0] * (GROUP_SIZE - 1),
        [S32_MAX] * GROUP_SIZE,
        [S32_MIN] * GROUP_SIZE,
        [S32_MAX if lane & 1 else S32_MIN for lane in range(GROUP_SIZE)],
        [(lane - 16) << 16 for lane in range(GROUP_SIZE)],
    ]
    while len(groups) < VECTOR_COUNT:
        limit = (1 << 30) if len(groups) % 11 == 0 else (64 << 16)
        groups.append([rng.randint(-limit, limit - 1)
                       for _ in range(GROUP_SIZE)])

    expected = [hadamard32_product_normalized(group) for group in groups]
    if any(item.saturation_count for item in expected):
        raise AssertionError("S32 Hadamard unexpectedly saturated")

    input_path = OUT / "input_s32.mem"
    expected_path = OUT / "expected_s35.mem"
    input_path.write_text("\n".join(pack(group, 32) for group in groups) + "\n")
    expected_path.write_text(
        "\n".join(pack(list(item.values), 35) for item in expected) + "\n")
    manifest = {
        "schema": "hap_mlp_hadamard_s32_vectors_v1",
        "vectors": VECTOR_COUNT,
        "input": "32 lanes S32 Q16.16",
        "output": "32 lanes S35 Q19.16",
        "coefficient_q16": 11_585,
        "expected_saturation_count": 0,
        "files": {
            path.name: {"bytes": path.stat().st_size,
                        "sha256": sha256_file(path)}
            for path in (input_path, expected_path)
        },
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
