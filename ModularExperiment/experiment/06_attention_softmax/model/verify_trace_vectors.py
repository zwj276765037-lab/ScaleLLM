#!/usr/bin/env python3
"""Regenerate M06 payloads and compare manifest metrics reproducibly."""

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
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    if (manifest.get("schema") !=
            "scalellm_modular_m06_softmax_real_trace_v1"):
        raise AssertionError("unexpected M06 trace schema")
    if manifest["rows"] != 72 or manifest["scores"] != 4236:
        raise AssertionError("M06 trace geometry mismatch")
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

    with tempfile.TemporaryDirectory(prefix="m06_trace_verify_") as temporary:
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
        "M06_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files']) + 1} rows={manifest['rows']} "
        f"scores={manifest['scores']} source_tensors="
        f"{len(manifest['source_score_tensors'])} "
        "manifest_numeric_rel_tol=1e-13 manifest_sha256="
        f"{sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
