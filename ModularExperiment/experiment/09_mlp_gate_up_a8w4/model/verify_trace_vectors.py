#!/usr/bin/env python3
"""Regenerate and byte-compare the M09 real Gate/Up workload."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
FORMAL = MODULE / "data_trace"
GENERATOR = HERE / "generate_trace_vectors.py"
CAPTURE_VERIFIER = (
    MODULE.parents[1] / "experiment/08_mlp_input_hadamard_a8/model" /
    "verify_trace_mlp_inputs.py"
)
TRANSACTIONS = 6 * 128
CONTRACT = {
    "activation_s9x16x32.mem": (TRANSACTIONS, 1152),
    "weights_s4x12x32.mem": (TRANSACTIONS, 384),
    "activation_meta_sc_u224.mem": (TRANSACTIONS, 56),
    "weight_meta_sc_u168.mem": (TRANSACTIONS, 42),
    "activation_scale_fp16x16.mem": (TRANSACTIONS, 64),
    "weight_scale_fp16x12.mem": (TRANSACTIONS, 48),
    "activation_scale_fp32x16.mem": (TRANSACTIONS, 128),
    "weight_scale_fp32x12.mem": (TRANSACTIONS, 96),
    "column_mask_u12.mem": (TRANSACTIONS, 3),
    "expected_sc_s24x16x12.mem": (6, 1152),
    "expected_fp16_s24x16x12.mem": (6, 1152),
    "expected_fp32_s24x16x12.mem": (6, 1152),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest_path = FORMAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m09_gate_up_real_trace_v1" or
            manifest.get("rows") != 16 or
            manifest.get("columns") != 12 or
            manifest.get("groups_per_tile") != 128 or
            manifest.get("group_size") != 32 or
            manifest.get("tiles") != 6 or
            manifest.get("transactions") != TRANSACTIONS or
            manifest.get("valid_outputs") != 1024 or
            len(manifest.get("row_coordinates", [])) != 16 or
            len(manifest.get("tile_coordinates", [])) != 6 or
            len(manifest.get("source_tensors", [])) != 6 or
            len(manifest.get("weight_sources", [])) != 6):
        raise AssertionError("M09 trace manifest contract mismatch")
    for path_key, hash_key in (
            (None, "generator_sha256"),
            ("base_model", "base_model_sha256"),
            ("production_exporter", "production_exporter_sha256"),
            ("production_fixed_model", "production_fixed_model_sha256"),
            ("minmax_reference", "minmax_reference_sha256"),
            ("capture_verifier", "capture_verifier_sha256")):
        path = GENERATOR if path_key is None else Path(manifest[path_key])
        if sha256_file(path) != manifest[hash_key]:
            raise AssertionError(f"M09 trace dependency changed: {hash_key}")
    capture = Path(manifest["mlp_input_capture"]).resolve(strict=True)
    if sha256_file(capture / "manifest.json") != manifest[
            "mlp_input_manifest_sha256"]:
        raise AssertionError("M09 MLP-input capture changed")
    subprocess.run([
        sys.executable, str(CAPTURE_VERIFIER),
        "--capture-dir", str(capture),
    ], check=True)

    expected_files = set(CONTRACT) | {"trace_tiles.csv"}
    if set(manifest["files"]) != expected_files:
        raise AssertionError("M09 trace file inventory mismatch")
    for name, record in manifest["files"].items():
        path = FORMAL / name
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M09 trace file hash mismatch: {name}")
        if name in CONTRACT:
            records, digits = CONTRACT[name]
            lines = path.read_text(encoding="ascii").splitlines()
            if ((record["records"], record["hex_digits"]) !=
                    (records, digits) or len(lines) != records or
                    any(len(line) != digits or
                        any(character not in "0123456789abcdef"
                            for character in line) for line in lines)):
                raise AssertionError(f"M09 trace record mismatch: {name}")
    if manifest["files"]["trace_tiles.csv"]["records"] != 6:
        raise AssertionError("M09 trace tile-coordinate count mismatch")
    if (manifest["correlation_min"] < -(1 << 16) or
            manifest["correlation_max"] >= (1 << 16) or
            manifest["fp16_nonfinite_contributions"] != 0):
        raise AssertionError("M09 real trace escaped finite S17/FP16 contract")

    with tempfile.TemporaryDirectory(prefix="m09_trace_verify_") as temporary:
        regenerated = Path(temporary)
        subprocess.run([
            sys.executable, str(GENERATOR),
            "--capture-dir", str(capture),
            "--model-dir", manifest["checkpoint"],
            "--output-dir", str(regenerated),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           text=True)
        formal_files = {
            path.name for path in FORMAL.iterdir() if path.is_file()
        }
        regenerated_files = {
            path.name for path in regenerated.iterdir() if path.is_file()
        }
        if formal_files != regenerated_files:
            raise AssertionError("M09 regenerated inventory mismatch")
        for name in sorted(formal_files):
            if (FORMAL / name).read_bytes() != (
                    regenerated / name).read_bytes():
                raise AssertionError(f"M09 regeneration mismatch: {name}")

    print(
        "M09_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files'])+1} tiles=6 "
        f"transactions={TRANSACTIONS} valid_outputs=1024 "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
