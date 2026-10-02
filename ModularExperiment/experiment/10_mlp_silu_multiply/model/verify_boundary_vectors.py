#!/usr/bin/env python3
"""Verify M10 boundary vector structure, hashes and production SC golden."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DATA = HERE.parent / "data_boundary"
sys.path.insert(0, str(ROOT / "model"))
from mlp_fixed import build_silu_lut, swiglu_product_s32  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_mem(filename: str) -> list[int]:
    return [int(line, 16) for line in
            (DATA / filename).read_text(encoding="ascii").splitlines()]


def signed(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def fp16_bits(value: float) -> int:
    return int(np.float16(value).view(np.uint16))


def fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def main() -> None:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "scalellm_modular_silu_boundary_inclusive_v1":
        raise AssertionError("unexpected M10 boundary schema")
    if len(manifest["seeds"]) < 10:
        raise AssertionError("M10 boundary workload requires at least 10 seeds")
    if manifest["vectors"] != \
            len(manifest["seeds"]) * manifest["vectors_per_seed"]:
        raise AssertionError("M10 vector count mismatch")
    if sha256_file(HERE / "generate_boundary_vectors.py") != \
            manifest["generator_sha256"]:
        raise AssertionError("M10 generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M10 production model hash changed")
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

    gates = [signed(value, 24) for value in read_mem("gate_s24.mem")]
    ups = [signed(value, 24) for value in read_mem("up_s24.mem")]
    expected_sc = [signed(value, 32) for value in
                   read_mem("expected_sc_s32.mem")]
    table = build_silu_lut()
    rebuilt_sc = [swiglu_product_s32(gate, up, table)
                  for gate, up in zip(gates, ups, strict=True)]
    if rebuilt_sc != expected_sc:
        raise AssertionError("M10 SC golden does not match production model")
    if [fp16_bits(value / 65536.0) for value in gates] != \
            read_mem("gate_fp16.mem") or \
            [fp16_bits(value / 65536.0) for value in ups] != \
            read_mem("up_fp16.mem"):
        raise AssertionError("M10 FP16 boundary conversion changed")
    if [fp32_bits(value / 65536.0) for value in gates] != \
            read_mem("gate_fp32.mem") or \
            [fp32_bits(value / 65536.0) for value in ups] != \
            read_mem("up_fp32.mem"):
        raise AssertionError("M10 FP32 boundary conversion changed")
    for key in ("zero_gate_records", "positive_gate_records",
                "negative_gate_records", "gate_below_silu_lut",
                "gate_above_silu_lut", "s24_endpoint_records"):
        if manifest["coverage"][key] <= 0:
            raise AssertionError(f"M10 boundary misses coverage: {key}")
    print("M10_BOUNDARY_VECTOR_VERIFY_PASS "
          f"files={len(manifest['files'])} seeds={len(manifest['seeds'])} "
          f"vectors={manifest['vectors']}")


if __name__ == "__main__":
    main()
