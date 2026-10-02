#!/usr/bin/env python3
"""Regenerate and byte-compare the M08 real MLP frontend workload."""

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
CAPTURE_VERIFIER = HERE / "verify_trace_mlp_inputs.py"
CONTRACT = {
    "input_s24.mem": (128, 3072),
    "expected_sc_u8.mem": (128, 1024),
    "expected_sc_meta.mem": (128, 96),
    "expected_fp_u8.mem": (128, 1024),
    "expected_fp16_meta.mem": (128, 96),
    "expected_fp32_meta.mem": (128, 160),
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
            "scalellm_modular_m08_mlp_frontend_real_trace_v1" or
            manifest.get("rows") != 16 or
            manifest.get("groups") != 128 or
            manifest.get("lanes") != 32 or
            manifest.get("bundles") != 128 or
            len(manifest.get("coordinates", [])) != 16 or
            len(manifest.get("source_tensors", [])) != 6):
        raise AssertionError("M08 trace manifest contract mismatch")
    for path_key, hash_key in (
            (None, "generator_sha256"),
            ("base_model", "base_model_sha256"),
            ("production_model", "production_model_sha256"),
            ("hadamard_reference", "hadamard_reference_sha256"),
            ("minmax_reference", "minmax_reference_sha256"),
            ("capture_script", "capture_script_sha256"),
            ("capture_verifier", "capture_verifier_sha256")):
        path = GENERATOR if path_key is None else Path(manifest[path_key])
        if sha256_file(path) != manifest[hash_key]:
            raise AssertionError(f"M08 trace dependency changed: {hash_key}")
    capture = Path(manifest["mlp_input_capture"]).resolve(strict=True)
    if sha256_file(capture / "manifest.json") != manifest[
            "mlp_input_manifest_sha256"]:
        raise AssertionError("M08 MLP input capture changed")
    subprocess.run([
        sys.executable, str(CAPTURE_VERIFIER),
        "--capture-dir", str(capture),
    ], check=True)

    expected_files = set(CONTRACT) | {"trace_rows.csv"}
    if set(manifest["files"]) != expected_files:
        raise AssertionError("M08 trace file inventory mismatch")
    for name, record in manifest["files"].items():
        path = FORMAL / name
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M08 trace file hash mismatch: {name}")
        if name in CONTRACT:
            records, digits = CONTRACT[name]
            lines = path.read_text(encoding="ascii").splitlines()
            if ((record["records"], record["hex_digits"]) !=
                    (records, digits) or len(lines) != records or
                    any(len(line) != digits or
                        any(character not in "0123456789abcdef"
                            for character in line) for line in lines)):
                raise AssertionError(f"M08 trace record mismatch: {name}")
    if manifest["files"]["trace_rows.csv"]["records"] != 16:
        raise AssertionError("M08 trace row count mismatch")

    with tempfile.TemporaryDirectory(prefix="m08_trace_verify_") as temporary:
        regenerated = Path(temporary)
        subprocess.run([
            sys.executable, str(GENERATOR),
            "--capture-dir", str(capture),
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
            raise AssertionError("M08 regenerated inventory mismatch")
        for name in sorted(formal_files):
            if (FORMAL / name).read_bytes() != (
                    regenerated / name).read_bytes():
                raise AssertionError(f"M08 regeneration mismatch: {name}")

    print(
        "M08_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files'])+1} rows=16 groups=128 lanes=32 "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
