#!/usr/bin/env python3
"""Audit the M12 AMD-FP16 golden correction against the frozen failed run."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

import generate_vectors as current_model


MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
CURRENT = MODULE / "data_trace"
LEGACY = MODULE / "data_trace_fp16_round_then_ftz_legacy_20260910"
DIAGNOSTIC = (
    ROOT / "result/12_mlp_down_a8w4/raw/fp16/xsim/"
    "20260910_135832_down_a8w4_trace_l00_full_448x342_group_major"
)
EXPECTED_DIFFS = {"00": (314, 200), "15": (117, 80), "31": (17, 15)}
CURRENT_MANIFEST_SHA256 = (
    "4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c"
)
LEGACY_MANIFEST_SHA256 = (
    "fa773a6baa0942bb2d873b10e2df54189743ad1f9c77858fc7cbbec21eba63f7"
)
CURRENT_MODEL_SHA256 = (
    "751afbead80f4e393c99fedbed609f997301eaab88b43ed39ddbb9f276e2a09b"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_directory_hashes(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        path = directory / name.lstrip("*")
        if sha256(path) != expected:
            raise AssertionError(f"diagnostic directory hash mismatch: {path}")


def changed_elements_and_tiles(old: Path, new: Path) -> tuple[int, set[int]]:
    old_rows = old.read_text(encoding="ascii").splitlines()
    new_rows = new.read_text(encoding="ascii").splitlines()
    if len(old_rows) != 342 or len(new_rows) != 342:
        raise AssertionError("FP16 expected payload must contain 342 tiles")
    changed_elements = 0
    changed_tiles: set[int] = set()
    mask = (1 << 24) - 1
    for tile, (old_row, new_row) in enumerate(zip(old_rows, new_rows)):
        old_word = int(old_row, 16)
        new_word = int(new_row, 16)
        element_changes = sum(
            ((old_word >> (lane * 24)) & mask) !=
            ((new_word >> (lane * 24)) & mask)
            for lane in range(16 * 12)
        )
        if element_changes:
            changed_tiles.add(tile)
            changed_elements += element_changes
    return changed_elements, changed_tiles


def main() -> None:
    if sha256(CURRENT / "manifest.json") != CURRENT_MANIFEST_SHA256:
        raise AssertionError("current trace manifest SHA-256 changed")
    if sha256(LEGACY / "manifest.json") != LEGACY_MANIFEST_SHA256:
        raise AssertionError("legacy trace manifest SHA-256 changed")
    model_path = Path(current_model.__file__).resolve()
    if sha256(model_path) != CURRENT_MODEL_SHA256:
        raise AssertionError("corrected FP semantics model SHA-256 changed")
    if current_model.verify_fp16_mul_ip_boundary() != 3:
        raise AssertionError("AMD FP16 directed boundary cases changed")

    old_files = {path.relative_to(LEGACY) for path in LEGACY.rglob("*")
                 if path.is_file()}
    new_files = {path.relative_to(CURRENT) for path in CURRENT.rglob("*")
                 if path.is_file()}
    if old_files != new_files:
        raise AssertionError("current/legacy trace file inventories differ")

    allowed_changes = {Path("manifest.json")} | {
        Path(f"layer{layer}/expected_fp16_s24x16x12.mem")
        for layer in EXPECTED_DIFFS
    }
    observed_changes = {
        relative for relative in sorted(new_files)
        if sha256(CURRENT / relative) != sha256(LEGACY / relative)
    }
    if observed_changes != allowed_changes:
        raise AssertionError(
            "unexpected current/legacy payload changes: "
            f"{sorted(map(str, observed_changes ^ allowed_changes))}")

    layer_tiles: dict[str, set[int]] = {}
    total_elements = 0
    total_tiles = 0
    for layer, expected in EXPECTED_DIFFS.items():
        relative = Path(f"layer{layer}/expected_fp16_s24x16x12.mem")
        elements, tiles = changed_elements_and_tiles(
            LEGACY / relative, CURRENT / relative)
        if (elements, len(tiles)) != expected:
            raise AssertionError(
                f"layer {layer} correction changed {(elements, len(tiles))}, "
                f"expected {expected}")
        layer_tiles[layer] = tiles
        total_elements += elements
        total_tiles += len(tiles)

    if (DIAGNOSTIC / "STATUS").read_text().strip() != "FAIL":
        raise AssertionError("frozen FP16 diagnostic STATUS is not FAIL")
    if (DIAGNOSTIC / "exit_status.txt").read_text().strip() != "1":
        raise AssertionError("frozen FP16 diagnostic exit status is not 1")
    verify_directory_hashes(DIAGNOSTIC)
    diagnostic_text = (DIAGNOSTIC / "summary.txt").read_text()
    mismatch_tiles = {
        int(tile) for tile in re.findall(
            r"MISMATCH: M12 case=1 expected_tile=(\d+) got_tile=\d+",
            diagnostic_text)
    }
    if len(re.findall(r"MISMATCH: M12 case=1", diagnostic_text)) != 200:
        raise AssertionError("frozen diagnostic mismatch line count is not 200")
    if mismatch_tiles != layer_tiles["00"]:
        raise AssertionError("layer-0 corrected tiles do not match RTL mismatch tiles")
    if "mismatch=200 tx=153216 groups=448 outputs=342 ii=1" not in diagnostic_text:
        raise AssertionError("frozen diagnostic final protocol gate changed")

    lhs = np.asarray([0x2425], dtype=np.uint16).view(np.float16)
    rhs = np.asarray([0x1BB8], dtype=np.uint16).view(np.float16)
    old_bits = int(current_model.fp16_ftz_array(
        lhs.astype(np.float32) * rhs.astype(np.float32)).view(np.uint16)[0])
    new_bits = int(current_model.fp16_mul_ip_array(lhs, rhs).view(np.uint16)[0])
    if old_bits != 0x0400 or new_bits != 0x0000:
        raise AssertionError(
            f"representative FP16 boundary changed: old=0x{old_bits:04x} "
            f"new=0x{new_bits:04x}")

    print(
        "M12_FP16_CORRECTION_VERIFY_PASS "
        f"files={len(new_files)} changed_payloads=3 "
        f"changed_elements={total_elements} changed_tiles={total_tiles} "
        "layer0_rtl_mismatch_tiles=200 fp16_boundary_cases=3 "
        f"manifest_sha256={CURRENT_MANIFEST_SHA256}"
    )


if __name__ == "__main__":
    main()
