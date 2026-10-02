#!/usr/bin/env python3
"""Regenerate and byte-compare the formal M04 K/V real-trace workload."""

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
CONTRACT = {
    "input_s24.mem": (16, 768),
    "expected_s12.mem": (64, 96),
    "expected_meta.mem": (64, 4),
    "expected_fp16.mem": (64, 128),
    "expected_fp32.mem": (64, 256),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest_path = FORMAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m04_kv_boundary_real_trace_v1" or
            manifest.get("batches") != 16 or
            manifest.get("rows_per_batch") != 4 or
            manifest.get("lanes_per_record") != 32 or
            manifest.get("k_records") != 32 or
            manifest.get("v_records") != 32 or
            len(manifest.get("coordinates", [])) != 8 or
            len(manifest.get("source_tensors", [])) != 12):
        raise AssertionError("M04 trace manifest contract mismatch")
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M04 trace generator hash changed")
    production_model = Path(manifest["production_model"])
    if sha256_file(production_model) != manifest[
            "production_model_sha256"]:
        raise AssertionError("M04 production model changed")
    trace_run = Path(manifest["source_trace_run"])
    if (trace_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("M04 source trace STATUS changed")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M04 source trace exit status changed")
    if sha256_file(trace_run / "trace/manifest.json") != manifest[
            "source_trace_manifest_sha256"]:
        raise AssertionError("M04 source trace manifest changed")

    expected_files = set(CONTRACT) | {"trace_batches.csv"}
    if set(manifest["files"]) != expected_files:
        raise AssertionError("M04 trace file inventory mismatch")
    for name, record in manifest["files"].items():
        path = FORMAL / name
        if sha256_file(path) != record["sha256"]:
            raise AssertionError(f"M04 trace file hash mismatch: {name}")
        if name in CONTRACT:
            records, digits = CONTRACT[name]
            lines = path.read_text(encoding="ascii").splitlines()
            if (record["records"], record["hex_digits"]) != (
                    records, digits) or len(lines) != records:
                raise AssertionError(f"M04 trace record mismatch: {name}")
            if any(len(line) != digits or
                   any(character not in "0123456789abcdef"
                       for character in line) for line in lines):
                raise AssertionError(f"M04 trace hex mismatch: {name}")
    if manifest["files"]["trace_batches.csv"]["records"] != 16:
        raise AssertionError("M04 trace provenance count mismatch")

    with tempfile.TemporaryDirectory(prefix="m04_trace_verify_") as temporary:
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
            raise AssertionError("M04 regenerated inventory mismatch")
        for name in sorted(formal_files):
            if (FORMAL / name).read_bytes() != (
                    regenerated / name).read_bytes():
                raise AssertionError(f"M04 regeneration mismatch: {name}")
    print(
        "M04_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files'])+1} batches=16 records=64 lanes=32 "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
