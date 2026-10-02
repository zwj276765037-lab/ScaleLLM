#!/usr/bin/env python3
"""Verify record counts, widths and hashes for M05 boundary vectors."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data_boundary"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["schema"] != "scalellm_modular_qk_boundary_inclusive_v1":
        raise AssertionError("unexpected M05 boundary schema")
    if len(manifest["seeds"]) < 10:
        raise AssertionError("M05 boundary workload requires at least 10 seeds")
    if manifest["rows"] != len(manifest["seeds"]) * len(manifest["shapes"]):
        raise AssertionError("M05 boundary row count mismatch")
    if manifest["scores"] != sum(manifest["shapes"]) * len(manifest["seeds"]):
        raise AssertionError("M05 boundary score count mismatch")
    if manifest["key_groups"] != manifest["scores"] * 4:
        raise AssertionError("M05 boundary key-group count mismatch")
    generator = Path(__file__).resolve().parent / "generate_boundary_vectors.py"
    if sha256_file(generator) != manifest["generator_sha256"]:
        raise AssertionError("M05 boundary generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M05 production numeric model hash changed")

    for filename, spec in manifest["files"].items():
        path = DATA / filename
        lines = path.read_text(encoding="ascii").splitlines()
        if len(lines) != spec["records"]:
            raise AssertionError(
                f"{filename}: expected {spec['records']} rows, got {len(lines)}")
        if any(len(line) != spec["hex_digits"] for line in lines):
            raise AssertionError(f"{filename}: wrong hex width")
        if any(not line or any(char not in "0123456789abcdef" for char in line)
               for line in lines):
            raise AssertionError(f"{filename}: non-lowercase-hex data")
        actual = sha256_file(path)
        if actual != spec["sha256"]:
            raise AssertionError(
                f"{filename}: expected sha256 {spec['sha256']}, got {actual}")

    row_counts = [int(line, 16) for line in
                  (DATA / "row_key_count_u8.mem").read_text().splitlines()]
    expected_schedule = [shape for shape in manifest["shapes"]
                         for _ in manifest["seeds"]]
    if row_counts != expected_schedule:
        raise AssertionError("M05 boundary row schedule changed")
    coverage = manifest["coverage"]
    if coverage["fp16_scale_subnormal_records"] <= 0:
        raise AssertionError("M05 boundary misses FP16 subnormal scales")
    if coverage["fp16_zero_key_lanes_from_nonzero_inputs"] <= 0:
        raise AssertionError("M05 boundary misses FP16 FTZ key contributions")
    print("M05_BOUNDARY_VECTOR_VERIFY_PASS "
          f"files={len(manifest['files'])} rows={manifest['rows']} "
          f"scores={manifest['scores']} key_groups={manifest['key_groups']}")


if __name__ == "__main__":
    main()
