#!/usr/bin/env python3
"""Verify M07 boundary vector structure, hashes and production SC golden."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DATA = HERE.parent / "data_boundary"
sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import pv_row_tile16_s24  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_mem(filename: str) -> list[int]:
    return [int(line, 16) for line in
            (DATA / filename).read_text(encoding="ascii").splitlines()]


def signed(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def unpack_lanes(record: int, width: int, lanes: int) -> list[int]:
    mask = (1 << width) - 1
    return [signed((record >> (lane * width)) & mask, width)
            for lane in range(lanes)]


def pack_lanes(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (lane * width)
               for lane, value in enumerate(values))


def main() -> None:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "scalellm_modular_pv_boundary_inclusive_v1":
        raise AssertionError("unexpected M07 boundary schema")
    if len(manifest["seeds"]) < 10:
        raise AssertionError("M07 boundary workload requires at least 10 seeds")
    if manifest["rows"] != len(manifest["seeds"]) * len(manifest["shapes"]):
        raise AssertionError("M07 row count mismatch")
    if manifest["keys"] != sum(manifest["shapes"]) * len(manifest["seeds"]):
        raise AssertionError("M07 key count mismatch")
    if sha256_file(HERE / "generate_boundary_vectors.py") != \
            manifest["generator_sha256"]:
        raise AssertionError("M07 generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M07 production model hash changed")
    for filename, spec in manifest["files"].items():
        path = DATA / filename
        lines = path.read_text(encoding="ascii").splitlines()
        if len(lines) != spec["records"]:
            raise AssertionError(f"{filename}: record count changed")
        if any(len(line) != spec["hex_digits"] for line in lines):
            raise AssertionError(f"{filename}: hex width changed")
        if any(not line or any(char not in "0123456789abcdef" for char in line)
               for line in lines):
            raise AssertionError(f"{filename}: non-lowercase-hex data")
        if sha256_file(path) != spec["sha256"]:
            raise AssertionError(f"{filename}: sha256 changed")

    row_counts = read_mem("row_key_count_u8.mem")
    expected_schedule = [shape for shape in manifest["shapes"]
                         for _ in manifest["seeds"]]
    if row_counts != expected_schedule:
        raise AssertionError("M07 row schedule changed")
    probabilities = read_mem("probability_u16.mem")
    value_records = read_mem("value_s12x16.mem")
    metadata = read_mem("value_meta_sc_u16.mem")
    expected_sc = read_mem("expected_sc_s24x16.mem")
    offset = 0
    rebuilt: list[int] = []
    rebuilt_saturation = 0
    for key_count in row_counts:
        row_probabilities = probabilities[offset:offset + key_count]
        row_values = [unpack_lanes(value, 12, 16) for value in
                      value_records[offset:offset + key_count]]
        row_codes = [value & 0xFF for value in metadata[offset:offset + key_count]]
        row_shifts = [(value >> 8) & 0x3F
                      for value in metadata[offset:offset + key_count]]
        row_probabilities += [0] * (128 - key_count)
        row_values += [[0] * 16 for _ in range(128 - key_count)]
        row_codes += [0] * (128 - key_count)
        row_shifts += [0] * (128 - key_count)
        output, saturation = pv_row_tile16_s24(
            row_probabilities, row_values, row_codes, row_shifts)
        rebuilt.append(pack_lanes(list(output), 24))
        rebuilt_saturation += saturation
        offset += key_count
    if offset != manifest["keys"] or rebuilt != expected_sc:
        raise AssertionError("M07 SC golden does not match production model")
    if rebuilt_saturation != manifest["saturation_counts"]["sc"]:
        raise AssertionError("M07 SC saturation count changed")
    for value in metadata:
        code = value & 0xFF
        shift = (value >> 8) & 0x3F
        if (code == 0 and shift != 0) or \
                (code != 0 and not 8 <= shift <= 32):
            raise AssertionError("M07 invalid native scale metadata")
    for key in ("zero_probabilities", "fp16_scale_subnormal_records",
                "fp16_probability_ftz_records",
                "fp16_zero_v_lanes_from_nonzero_inputs"):
        if manifest["coverage"][key] <= 0:
            raise AssertionError(f"M07 boundary misses coverage: {key}")
    print("M07_BOUNDARY_VECTOR_VERIFY_PASS "
          f"files={len(manifest['files'])} rows={manifest['rows']} "
          f"keys={manifest['keys']} lanes={manifest['lanes']}")


if __name__ == "__main__":
    main()
