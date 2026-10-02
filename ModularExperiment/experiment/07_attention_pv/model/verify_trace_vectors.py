#!/usr/bin/env python3
"""Regenerate M07 payloads and compare manifest metrics reproducibly."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
FORMAL = MODULE / "data_trace"
GENERATOR = HERE / "generate_trace_vectors.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_manifest_equivalent(expected: object, actual: object,
                               location: str = "$") -> None:
    """Require exact structure, allowing only floating reduction noise."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is not actual:
            raise AssertionError(f"manifest mismatch at {location}")
    elif isinstance(expected, float) or isinstance(actual, float):
        if not (isinstance(expected, (int, float)) and
                isinstance(actual, (int, float)) and
                math.isclose(float(expected), float(actual),
                             rel_tol=1.0e-13, abs_tol=1.0e-15)):
            raise AssertionError(f"manifest numeric mismatch at {location}")
    elif isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            raise AssertionError(f"manifest keys mismatch at {location}")
        for key in expected:
            assert_manifest_equivalent(
                expected[key], actual[key], f"{location}.{key}")
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise AssertionError(f"manifest length mismatch at {location}")
        for index, (left, right) in enumerate(zip(expected, actual,
                                                  strict=True)):
            assert_manifest_equivalent(
                left, right, f"{location}[{index}]")
    elif expected != actual:
        raise AssertionError(f"manifest mismatch at {location}")


def main() -> None:
    manifest_path = FORMAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "scalellm_modular_m07_pv_real_trace_v1":
        raise AssertionError("unexpected M07 trace schema")
    if (manifest["rows"] != 72 or manifest["keys"] != 4236 or
            manifest["lanes"] != 16):
        raise AssertionError("M07 trace geometry mismatch")
    if (manifest["samples"] != [0, 1] or
            manifest["layers"] != [0, 15, 31] or
            manifest["q_heads"] != [0, 17] or
            manifest["kv_heads"] != [0, 4]):
        raise AssertionError("M07 trace coordinate contract mismatch")
    quantization = manifest["kv_quantization"]
    if (quantization["group_start"] != 0 or
            quantization["group_lanes"] != 32 or
            quantization["tile_start_within_group"] != 0 or
            quantization["tile_lanes"] != 16 or
            quantization["tile_head_dimensions"] != [0, 15]):
        raise AssertionError("M07 trace KV group/tile contract mismatch")
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M07 trace generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M07 trace production model hash changed")
    source_run = Path(manifest["source_trace_run"])
    if (source_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("M07 source trace STATUS changed")
    if int((source_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M07 source trace exit status changed")
    source_manifest = source_run / "trace/manifest.json"
    if sha256_file(source_manifest) != manifest["source_trace_manifest_sha256"]:
        raise AssertionError("M07 source trace manifest changed")

    for filename, record in manifest["files"].items():
        path = FORMAL / filename
        if sha256_file(path) != record["sha256"]:
            raise AssertionError(f"formal file hash mismatch: {filename}")
        if filename.endswith(".mem"):
            lines = path.read_text(encoding="ascii").splitlines()
            if len(lines) != record["records"]:
                raise AssertionError(f"record count mismatch: {filename}")
            if any(len(line) != record["hex_digits"] or
                   any(char not in "0123456789abcdef" for char in line)
                   for line in lines):
                raise AssertionError(f"hex width/content mismatch: {filename}")

    with tempfile.TemporaryDirectory(prefix="m07_trace_verify_") as temporary:
        regenerated = Path(temporary)
        subprocess.run([
            sys.executable, str(GENERATOR),
            "--trace-run", manifest["source_trace_run"],
            "--output-dir", str(regenerated),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           text=True)
        formal_files = {path.name for path in FORMAL.iterdir() if path.is_file()}
        regenerated_files = {
            path.name for path in regenerated.iterdir() if path.is_file()}
        if formal_files != regenerated_files:
            raise AssertionError("regenerated file inventory mismatch")
        for filename in sorted(formal_files):
            if filename == "manifest.json":
                regenerated_manifest = json.loads(
                    (regenerated / filename).read_text(encoding="utf-8"))
                assert_manifest_equivalent(manifest, regenerated_manifest)
                continue
            if (FORMAL / filename).read_bytes() != (
                    regenerated / filename).read_bytes():
                raise AssertionError(f"regeneration mismatch: {filename}")

    print(
        "M07_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files']) + 1} rows={manifest['rows']} "
        f"keys={manifest['keys']} lanes={manifest['lanes']} "
        f"source_tensors={len(manifest['source_tensors'])} "
        "manifest_numeric_rel_tol=1e-13 "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
