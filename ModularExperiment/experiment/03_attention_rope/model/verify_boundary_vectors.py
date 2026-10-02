#!/usr/bin/env python3
"""Independently verify M03 boundary-vector shape, width, and hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data_boundary"
EXPECTED = {
    "correlation_s21_pair.mem": (1536, 11, 42),
    "scale_meta_sc_u42.mem": (1536, 11, 42),
    "scale_fp16x3.mem": (1536, 12, 48),
    "scale_fp32x3.mem": (1536, 24, 96),
    "coeff_s18_pair.mem": (12, 9, 36),
    "expected_sc_s24_pair.mem": (12, 12, 48),
    "expected_fp16_s24_pair.mem": (12, 12, 48),
    "expected_fp32_s24_pair.mem": (12, 12, 48),
}


def main() -> None:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "m03_projection_tail_rope_boundary_v1":
        raise ValueError("unexpected schema")
    if manifest["pairs"] != 12 or manifest["groups_per_pair"] != 128:
        raise ValueError("unexpected workload shape")
    if manifest["transactions"] != 1536 or len(manifest["seeds"]) != 12:
        raise ValueError("unexpected transaction/seed count")
    if manifest["target_input_ii"] != 2:
        raise ValueError("unexpected matched-throughput target")
    if manifest["fp_accumulator_banks"] != 6:
        raise ValueError("unexpected FP accumulator bank count")
    if manifest["fp_bank_revisit_cycles"] != 12:
        raise ValueError("unexpected FP accumulator recurrence interval")
    if manifest["fp_bank_revisit_cycles"] <= manifest["fp32_add_latency"]:
        raise ValueError("FP accumulator feedback cannot sustain target II")
    if (manifest["total_shift_min"], manifest["total_shift_max"]) != (26, 47):
        raise ValueError("ScaleCode shift-boundary coverage is missing")

    for name, (expected_lines, hex_digits, used_bits) in EXPECTED.items():
        path = DATA / name
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["sha256"][name]:
            raise ValueError(f"hash mismatch: {name}")
        lines = raw.decode("ascii").splitlines()
        if len(lines) != expected_lines:
            raise ValueError(f"line-count mismatch: {name}")
        for index, line in enumerate(lines):
            if len(line) != hex_digits:
                raise ValueError(f"hex-width mismatch: {name}:{index + 1}")
            try:
                value = int(line, 16)
            except ValueError as exc:
                raise ValueError(f"non-hex record: {name}:{index + 1}") from exc
            if value >= (1 << used_bits):
                raise ValueError(f"unused high bits set: {name}:{index + 1}")

    normal_indices = manifest["non_saturation_pair_indices"]
    if len(normal_indices) != 11 or 1 in normal_indices:
        raise ValueError("directed saturation partition changed")
    if manifest["saturation_pairs_sc"] < 1:
        raise ValueError("directed SC saturation coverage is missing")
    if manifest["fp16_zero_group_contributions"] < 1:
        raise ValueError("FP16 zero/underflow coverage is missing")
    print(f"M03_BOUNDARY_VECTOR_VERIFY_PASS files={len(EXPECTED)} "
          f"transactions={manifest['transactions']} pairs={manifest['pairs']}")


if __name__ == "__main__":
    main()
