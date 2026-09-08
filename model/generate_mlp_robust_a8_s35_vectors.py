#!/usr/bin/env python3
"""Generate deterministic S35 Robust-A8 vectors."""

from __future__ import annotations

import json
from pathlib import Path
import random

from mlp_fixed import (
    GROUP_SIZE, S35_MAX, S35_MIN, robust_a8_quantize_s35, sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_robust_a8_s35"
COUNT = 64


def pack_signed(values: list[int], width: int) -> str:
    packed = sum((value & ((1 << width)-1)) << (lane*width)
                 for lane, value in enumerate(values))
    return f"{packed:0{len(values)*width//4}x}"


def main() -> None:
    rng = random.Random(0x5333354138)
    vectors = [
        [0]*GROUP_SIZE,
        [1 << 16]*GROUP_SIZE,
        [-(1 << 16)]*GROUP_SIZE,
        [(lane-16) << 16 for lane in range(GROUP_SIZE)],
        [-(16384 << 16) if lane & 1 else (16384 << 16)-1
         for lane in range(GROUP_SIZE)],
        [0]*30 + [-(16384 << 16), (16384 << 16)-1],
        [12345]*31 + [12346],
        [-12345]*31 + [-12346],
    ]
    while len(vectors) < COUNT:
        mode = len(vectors) % 4
        if mode == 0:
            values = [rng.randint(-(16384 << 16), (16384 << 16)-1)
                      for _ in range(GROUP_SIZE)]
        elif mode == 1:
            values = [rng.randint(-(16384 << 16), (16384 << 16)-1)
                      for _ in range(GROUP_SIZE)]
        elif mode == 2:
            base = rng.randint(-(64 << 16), (64 << 16)-1)
            values = [max(S35_MIN, min(S35_MAX,
                      base+rng.randint(-32768, 32768)))
                      for _ in range(GROUP_SIZE)]
        else:
            values = [rng.choice((-(16384 << 16), (16384 << 16)-1,
                                   -65536, -1, 0, 1, 65536))
                      for _ in range(GROUP_SIZE)]
        vectors.append(values)

    OUT.mkdir(parents=True, exist_ok=True)
    input_path = OUT / "input_s35.mem"
    q_path = OUT / "expected_u8.mem"
    meta_path = OUT / "expected_meta.mem"
    results = [robust_a8_quantize_s35(values) for values in vectors]
    input_path.write_text("\n".join(pack_signed(v, 35) for v in vectors)+"\n")
    q_path.write_text("\n".join(pack_signed(list(r.values), 8)
                                 for r in results)+"\n")
    meta_path.write_text("\n".join(f"{r.metadata:06x}" for r in results)+"\n")
    manifest = {
        "schema": "hap_mlp_robust_a8_s35_vectors_v1",
        "vectors": COUNT, "input": "32 lanes S35 Q19.16",
        "output": "32 lanes U8 plus meta24",
        "scale_shift_min": min(r.scale_shift for r in results),
        "scale_shift_max": max(r.scale_shift for r in results),
        "files": {p.name: {"bytes": p.stat().st_size,
                             "sha256": sha256_file(p)}
                  for p in (input_path, q_path, meta_path)},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
