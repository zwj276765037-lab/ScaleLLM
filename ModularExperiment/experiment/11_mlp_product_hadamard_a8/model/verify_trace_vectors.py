#!/usr/bin/env python3
"""Independently regenerate and byte-compare the M11 real-trace workload."""

from __future__ import annotations

import hashlib
import json
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


def main() -> None:
    manifest_path = FORMAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m11_product_frontend_real_trace_v1"):
        raise AssertionError("unexpected M11 trace schema")
    if (manifest["groups"] != 448 or manifest["rows"] != 16 or
            manifest["lanes"] != 32 or
            manifest["full_intermediate_channels"] != 14336 or
            len(manifest["row_coordinates"]) != 16):
        raise AssertionError("M11 trace geometry mismatch")
    if len({(row["sample"], row["layer"], row["token"])
            for row in manifest["row_coordinates"]}) != 16:
        raise AssertionError("M11 trace row coordinates are not unique")
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M11 trace generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest["production_model_sha256"]:
        raise AssertionError("M11 trace production model hash changed")
    minmax_reference = Path(manifest["minmax_reference"])
    if sha256_file(minmax_reference) != manifest["minmax_reference_sha256"]:
        raise AssertionError("M11 Min/Max reference hash changed")
    source_run = Path(manifest["source_trace_run"])
    if (source_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("M11 source trace STATUS changed")
    if int((source_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M11 source trace exit status changed")
    source_manifest = source_run / "trace/manifest.json"
    if sha256_file(source_manifest) != manifest["source_trace_manifest_sha256"]:
        raise AssertionError("M11 source trace manifest changed")

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

    with tempfile.TemporaryDirectory(prefix="m11_trace_verify_") as temporary:
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
            if (FORMAL / filename).read_bytes() != (
                    regenerated / filename).read_bytes():
                raise AssertionError(f"regeneration mismatch: {filename}")

    print(
        "M11_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files']) + 1} groups={manifest['groups']} "
        f"rows={manifest['rows']} lanes={manifest['lanes']} "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
