#!/usr/bin/env python3
"""Generate the versioned SiLU table and deterministic RTL vectors."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random

from mlp_fixed import (
    SILU_LIMIT_Q16, S24_MAX, S24_MIN, build_silu_lut, sha256_file,
    silu_lut_q16, silu_real, swiglu_product_s32, twos_hex,
)


def write_mem(path: Path, values, width: int) -> None:
    path.write_text("\n".join(twos_hex(int(value), width) for value in values) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--vectors", type=int, default=512)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    table = build_silu_lut()
    lut_path = args.output_dir / "mlp_silu_q16.mem"
    # The +16 endpoint (entry 8192) is a constant in RTL.  Storing only a
    # power-of-two 8192-word ROM prevents one endpoint from doubling the
    # inferred BRAM depth while preserving the 8193-entry numeric contract.
    write_mem(lut_path, table[:-1], 24)

    rng = random.Random(0x4841504D4C50)
    boundary = [
        S24_MIN, -SILU_LIMIT_Q16-1, -SILU_LIMIT_Q16,
        -SILU_LIMIT_Q16+1, -65536, -32768, -256, -128, -1, 0, 1,
        127, 128, 255, 256, 32768, 65536, SILU_LIMIT_Q16-1,
        SILU_LIMIT_Q16, SILU_LIMIT_Q16+1, S24_MAX,
    ]
    gates = list(boundary)
    ups = [boundary[(i * 7 + 3) % len(boundary)] for i in range(len(boundary))]
    while len(gates) < args.vectors:
        # Most vectors exercise realistic [-32,+32], with periodic full-S24.
        gates.append(rng.randint(-(32 << 16), (32 << 16)-1)
                     if len(gates) % 9 else rng.randint(S24_MIN, S24_MAX))
        ups.append(rng.randint(-(32 << 16), (32 << 16)-1)
                   if len(ups) % 11 else rng.randint(S24_MIN, S24_MAX))
    gates = gates[:args.vectors]
    ups = ups[:args.vectors]
    expected = [swiglu_product_s32(gate, up, table)
                for gate, up in zip(gates, ups)]
    write_mem(args.output_dir / "mlp_silu_gate_s24.mem", gates, 24)
    write_mem(args.output_dir / "mlp_silu_up_s24.mem", ups, 24)
    write_mem(args.output_dir / "mlp_silu_expected_s32.mem", expected, 32)

    max_absolute_error = 0.0
    max_relative_error = 0.0
    for gate in range(-SILU_LIMIT_Q16, SILU_LIMIT_Q16+1, 37):
        actual = silu_lut_q16(gate, table) / 65536.0
        reference = silu_real(gate / 65536.0)
        error = abs(actual-reference)
        max_absolute_error = max(max_absolute_error, error)
        # Relative error is meaningful only away from SiLU's zero tails.
        if abs(reference) > 0.1:
            max_relative_error = max(max_relative_error, error/abs(reference))

    minimum_index = min(range(len(table)), key=table.__getitem__)
    shape_left_nonincreasing = all(
        table[i] >= table[i+1] for i in range(minimum_index))
    shape_right_nondecreasing = all(
        table[i] <= table[i+1]
        for i in range(minimum_index, len(table)-1))

    files = {}
    for path in sorted(args.output_dir.glob("mlp_silu_*.mem")):
        files[path.name] = {"bytes": path.stat().st_size,
                            "sha256": sha256_file(path)}
    manifest = {
        "schema": "hap_mlp_silu_artifact_v1",
        "input": "S24 Q8.16", "silu_output": "S24 Q8.16",
        "product_output": "S32 Q16.16",
        "lut_range": [-16.0, 16.0], "lut_step": 1/256,
        "mathematical_lut_entries": len(table),
        "stored_rom_entries": len(table)-1,
        "positive_endpoint_q16_constant": table[-1],
        "vectors": len(gates),
        "max_absolute_error": max_absolute_error,
        "max_relative_error_abs_reference_gt_0_1": max_relative_error,
        "minimum": {"index": minimum_index,
                    "x": -16.0 + minimum_index/256.0,
                    "q16": table[minimum_index]},
        "shape_left_nonincreasing": shape_left_nonincreasing,
        "shape_right_nondecreasing": shape_right_nondecreasing,
        "shape_pass": shape_left_nonincreasing and shape_right_nondecreasing,
        "files": files,
    }
    (args.output_dir / "mlp_silu_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
