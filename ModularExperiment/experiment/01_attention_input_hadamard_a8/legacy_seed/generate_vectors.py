#!/usr/bin/env python3
"""Generate one common S24 workload for proposed and direct-A8 frontends."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
HAP_ROOT = HERE.parents[2] / "HAP_new"
sys.path.insert(0, str(HAP_ROOT / "model"))

from fixbit_v2 import (  # noqa: E402
    FORMAT_ID,
    GROUP_SIZE,
    hadamard32_normalized,
    pack_lanes,
    robust_a8_quantize,
    self_test,
)
from generate_attention_frontend_8row_vectors import (  # noqa: E402
    GROUP_COUNT,
    ROWS,
    SEED,
    build_row,
)


OUT_DIR = HERE / "data"


def pack_unsigned(values: list[int], width: int) -> int:
    packed = 0
    for lane, value in enumerate(values):
        if not 0 <= value < (1 << width):
            raise ValueError((lane, value, width))
        packed |= value << (lane * width)
    return packed


def main() -> None:
    self_test()
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    proposed_saturations = 0

    with (OUT_DIR / "input_s24.mem").open("w", encoding="ascii") as src_file, \
            (OUT_DIR / "proposed_u8.mem").open("w", encoding="ascii") as prop_u8, \
            (OUT_DIR / "proposed_meta.mem").open("w", encoding="ascii") as prop_meta, \
            (OUT_DIR / "direct_u8.mem").open("w", encoding="ascii") as direct_u8, \
            (OUT_DIR / "direct_meta.mem").open("w", encoding="ascii") as direct_meta:
        for group in range(GROUP_COUNT):
            packed_input = 0
            packed_prop_u8 = 0
            packed_prop_meta = 0
            packed_direct_u8 = 0
            packed_direct_meta = 0
            for row in range(ROWS):
                values = build_row(rng, group, row)
                proposed_had = hadamard32_normalized(values)
                proposed = robust_a8_quantize(proposed_had.values)
                direct = robust_a8_quantize(values)
                proposed_saturations += proposed_had.saturation_count

                packed_input |= pack_lanes(values, 24) << (
                    row * GROUP_SIZE * 24)
                packed_prop_u8 |= pack_unsigned(list(proposed.values), 8) << (
                    row * GROUP_SIZE * 8)
                packed_prop_meta |= proposed.metadata << (row * 24)
                packed_direct_u8 |= pack_unsigned(list(direct.values), 8) << (
                    row * GROUP_SIZE * 8)
                packed_direct_meta |= direct.metadata << (row * 24)

            src_file.write(f"{packed_input:01536x}\n")
            prop_u8.write(f"{packed_prop_u8:0512x}\n")
            prop_meta.write(f"{packed_prop_meta:048x}\n")
            direct_u8.write(f"{packed_direct_u8:0512x}\n")
            direct_meta.write(f"{packed_direct_meta:048x}\n")

    manifest = {
        "schema": "hap_m1_frontend_common_vectors_v1",
        "format_id": f"0x{FORMAT_ID:08x}",
        "seed": SEED,
        "rows": ROWS,
        "group_size": GROUP_SIZE,
        "group_count": GROUP_COUNT,
        "input_format": "8 rows x 32 lanes S24 Q8.16",
        "common_output_format": "8 rows x 32 lanes U8 plus 8 x meta24",
        "proposed_hadamard_saturations": proposed_saturations,
        "cases": ["direct_robust_a8", "hadamard_robust_a8"],
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("M1_FRONTEND_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()

