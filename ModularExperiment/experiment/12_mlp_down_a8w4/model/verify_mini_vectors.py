#!/usr/bin/env python3
"""Verify the deterministic nonzero M12 full-lane mini workload."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import generate_vectors as full


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
DATA = MODULE / "data_mini"
FULL_DATA = MODULE / "data"
EXPECTED = {
    "payload_sc_u6656.mem": (80, 6656),
    "payload_fp16_u6656.mem": (80, 6656),
    "payload_fp32_u7168.mem": (80, 7168),
    "expected_sc_s24x16x12.mem": (16, 4608),
    "expected_fp16_s24x16x12.mem": (16, 4608),
    "expected_fp32_s24x16x12.mem": (16, 4608),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_lines(path: Path, indices: set[int]) -> dict[int, int]:
    selected: dict[int, int] = {}
    with path.open("r", encoding="ascii") as handle:
        for index, line in enumerate(handle):
            if index in indices:
                selected[index] = int(line.strip(), 16)
    if set(selected) != indices:
        raise AssertionError(f"missing selected rows in {path}")
    return selected


def verify_full_subset_binding(data: Path) -> None:
    source_tiles = list(range(15)) + [341]
    activation_indices = set(range(5))
    transaction_indices = {
        group * 342 + source_tile
        for group in range(5) for source_tile in source_tiles
    }
    activations = selected_lines(
        FULL_DATA / "activation_s9x16x32.mem", activation_indices)
    activation_sc = selected_lines(
        FULL_DATA / "activation_meta_sc_u224.mem", activation_indices)
    activation_fp16 = selected_lines(
        FULL_DATA / "activation_scale_fp16x16.mem", activation_indices)
    activation_fp32 = selected_lines(
        FULL_DATA / "activation_scale_fp32x16.mem", activation_indices)
    weights = selected_lines(
        FULL_DATA / "weights_s4x12x32.mem", transaction_indices)
    weight_sc = selected_lines(
        FULL_DATA / "weight_meta_sc_u168.mem", transaction_indices)
    weight_fp16 = selected_lines(
        FULL_DATA / "weight_scale_fp16x12.mem", transaction_indices)
    weight_fp32 = selected_lines(
        FULL_DATA / "weight_scale_fp32x12.mem", transaction_indices)
    masks = selected_lines(
        FULL_DATA / "column_mask_u12.mem", set(source_tiles))
    mini_payloads = {
        variant: [int(row, 16) for row in
                  (data / name).read_text(encoding="ascii").splitlines()]
        for variant, name in {
            "sc": "payload_sc_u6656.mem",
            "fp16": "payload_fp16_u6656.mem",
            "fp32": "payload_fp32_u7168.mem",
        }.items()
    }

    for group in range(5):
        for local_tile, source_tile in enumerate(source_tiles):
            mini_index = group * 16 + local_tile
            full_index = group * 342 + source_tile
            common = activations[group] | (weights[full_index] << 4608)
            flags = (
                (masks[source_tile] << 6536) | (local_tile << 6548) |
                ((group == 0) << 6557) | ((group == 4) << 6558)
            )
            expected_sc = (
                common | (activation_sc[group] << 6144) |
                (weight_sc[full_index] << 6368) | flags
            )
            flags_fp16 = (
                (masks[source_tile] << 6592) | (local_tile << 6604) |
                ((group == 0) << 6613) | ((group == 4) << 6614)
            )
            expected_fp16 = (
                common | (activation_fp16[group] << 6144) |
                (weight_fp16[full_index] << 6400) | flags_fp16
            )
            flags_fp32 = (
                (masks[source_tile] << 7040) | (local_tile << 7052) |
                ((group == 0) << 7061) | ((group == 4) << 7062)
            )
            expected_fp32 = (
                common | (activation_fp32[group] << 6144) |
                (weight_fp32[full_index] << 6656) | flags_fp32
            )
            expected_payloads = {
                "sc": expected_sc,
                "fp16": expected_fp16,
                "fp32": expected_fp32,
            }
            for variant, expected in expected_payloads.items():
                if mini_payloads[variant][mini_index] != expected:
                    raise AssertionError(
                        f"{variant} mini/full subset mismatch at "
                        f"group={group} tile={local_tile} "
                        f"source_tile={source_tile}")


def verify_data(data: Path) -> dict:
    manifest_path = data / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema": "scalellm_m12_down_a8w4_full_lane_mini_v1",
        "rows": 16,
        "physical_columns": 12,
        "groups": 5,
        "tiles": 16,
        "transactions": 80,
        "group_size": 32,
        "source_tiles": list(range(15)) + [341],
        "tail_mask": "0x00f",
        "expected_bits": 4608,
        "fp16_boundary_cases": 3,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise AssertionError(
                f"mini manifest {key}: expected {expected}, "
                f"got {manifest.get(key)}")
    if set(manifest.get("files", {})) != set(EXPECTED):
        raise AssertionError("mini manifest file inventory changed")
    if full.verify_fp16_mul_ip_boundary() != 3:
        raise AssertionError("FP16 directed boundary coverage changed")

    for name, (lines_expected, bits) in EXPECTED.items():
        path = data / name
        rows = path.read_text(encoding="ascii").splitlines()
        if len(rows) != lines_expected:
            raise AssertionError(
                f"{name}: expected {lines_expected} rows, got {len(rows)}")
        digits = (bits + 3) // 4
        for index, row in enumerate(rows):
            if len(row) != digits:
                raise AssertionError(
                    f"{name}:{index}: expected {digits} hex digits, "
                    f"got {len(row)}")
            int(row, 16)
        entry = manifest["files"][name]
        if entry.get("bits") != bits:
            raise AssertionError(f"{name}: manifest width changed")
        if entry.get("bytes") != path.stat().st_size:
            raise AssertionError(f"{name}: manifest byte count changed")
        if entry.get("sha256") != sha256(path):
            raise AssertionError(f"{name}: payload SHA-256 mismatch")

    for variant in ("sc", "fp16", "fp32"):
        if manifest["payload_nonzero_transactions"].get(variant) != 80:
            raise AssertionError(f"{variant}: mini payload is not fully nonzero")
        if manifest["expected_nonzero_elements"].get(variant, 0) <= 0:
            raise AssertionError(f"{variant}: mini expected output is all zero")
        if manifest["arithmetic_nonzero_group_tiles"].get(variant, 0) <= 0:
            raise AssertionError(f"{variant}: mini arithmetic is all zero")
    if manifest["arithmetic_nonzero_group_tiles"].get("correlation", 0) <= 0:
        raise AssertionError("mini integer correlation is all zero")
    verify_full_subset_binding(data)

    generator = Path(manifest["generator"])
    semantics = Path(manifest["fp_semantics_model"])
    if generator.resolve() != (HERE / "generate_mini_vectors.py").resolve():
        raise AssertionError("mini generator path changed")
    if semantics.resolve() != (HERE / "generate_vectors.py").resolve():
        raise AssertionError("mini FP semantics path changed")
    if manifest["generator_sha256"] != sha256(generator):
        raise AssertionError("mini generator SHA-256 changed")
    if manifest["fp_semantics_model_sha256"] != sha256(semantics):
        raise AssertionError("mini FP semantics SHA-256 changed")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true")
    args = parser.parse_args()
    verify_data(DATA)

    if args.regenerate:
        with tempfile.TemporaryDirectory(prefix="m12_mini_regen_") as temp:
            regenerated = Path(temp)
            subprocess.run(
                [sys.executable, str(HERE / "generate_mini_vectors.py"),
                 "--out", str(regenerated)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            verify_data(regenerated)
            for name in sorted([*EXPECTED, "manifest.json"]):
                if (DATA / name).read_bytes() != (regenerated / name).read_bytes():
                    raise AssertionError(f"mini regeneration mismatch: {name}")

    print(
        "M12_MINI_VECTOR_VERIFY_PASS "
        f"files={len(EXPECTED) + 1} groups=5 tiles=16 transactions=80 "
        "nonzero_variants=3 fp16_boundary_cases=3 "
        "full_subset_bound=1 "
        f"regenerated={int(args.regenerate)} "
        f"manifest_sha256={sha256(DATA / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
