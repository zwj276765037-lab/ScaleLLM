#!/usr/bin/env python3
"""Verify and optionally regenerate the formal M03 real-trace workload."""

from __future__ import annotations

import argparse
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
CAPTURE_VERIFIER = HERE / "verify_trace_projection_inputs.py"
CONTRACT = {
    "correlation_s21_pair.mem": (1536, 11),
    "scale_meta_sc_u42.mem": (1536, 11),
    "scale_fp16x3.mem": (1536, 12),
    "scale_fp32x3.mem": (1536, 24),
    "coeff_s18_pair.mem": (12, 9),
    "expected_sc_s24_pair.mem": (12, 12),
    "expected_fp16_s24_pair.mem": (12, 12),
    "expected_fp32_s24_pair.mem": (12, 12),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integrity-only", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    manifest_path = FORMAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m03_projection_rope_real_trace_v1" or
            manifest.get("pairs") != 12 or
            manifest.get("groups_per_pair") != 128 or
            manifest.get("transactions") != 1536 or
            len(manifest.get("coordinates", [])) != 12):
        raise AssertionError("M03 trace manifest contract mismatch")
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M03 trace generator changed")
    for path_key, hash_key in (
            ("boundary_model", "boundary_model_sha256"),
            ("production_exporter", "production_exporter_sha256"),
            ("production_fixed_model", "production_fixed_model_sha256"),
            ("minmax_reference", "minmax_reference_sha256"),
            ("capture_verifier", "capture_verifier_sha256")):
        if sha256_file(Path(manifest[path_key])) != manifest[hash_key]:
            raise AssertionError(f"M03 trace dependency changed: {path_key}")

    trace_run = Path(manifest["source_trace_run"]).resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("M03 trace source STATUS changed")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M03 trace source exit status changed")
    if sha256_file(trace_run / "trace/manifest.json") != manifest[
            "source_trace_manifest_sha256"]:
        raise AssertionError("M03 source trace manifest changed")
    capture = Path(manifest["projection_input_capture"]).resolve(strict=True)
    if sha256_file(capture / "manifest.json") != manifest[
            "projection_input_manifest_sha256"]:
        raise AssertionError("M03 projection input capture changed")

    expected_files = set(CONTRACT) | {"trace_pairs.csv"}
    if set(manifest["files"]) != expected_files:
        raise AssertionError("M03 trace file inventory mismatch")
    for name, record in manifest["files"].items():
        path = FORMAL / name
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M03 trace file hash mismatch: {name}")
        if name in CONTRACT:
            records, digits = CONTRACT[name]
            lines = path.read_text(encoding="ascii").splitlines()
            if ((record["records"], record["hex_digits"]) !=
                    (records, digits) or len(lines) != records or
                    any(len(line) != digits or
                        any(character not in "0123456789abcdef"
                            for character in line) for line in lines)):
                raise AssertionError(f"M03 trace record mismatch: {name}")
    if manifest["files"]["trace_pairs.csv"]["records"] != 12:
        raise AssertionError("M03 trace coordinate count mismatch")

    if args.integrity_only:
        subprocess.run([
            sys.executable, str(CAPTURE_VERIFIER),
            "--capture-dir", str(capture),
        ], check=True)
    else:
        with tempfile.TemporaryDirectory(
                prefix="m03_trace_verify_") as temporary:
            regenerated = Path(temporary)
            subprocess.run([
                sys.executable, str(GENERATOR),
                "--trace-run", str(trace_run),
                "--capture-dir", str(capture),
                "--model-dir", manifest["checkpoint"],
                "--output-dir", str(regenerated),
            ], check=True, stdout=subprocess.PIPE,
               stderr=subprocess.STDOUT, text=True)
            formal_files = {
                path.name for path in FORMAL.iterdir() if path.is_file()
            }
            regenerated_files = {
                path.name for path in regenerated.iterdir() if path.is_file()
            }
            if formal_files != regenerated_files:
                raise AssertionError("M03 regenerated inventory mismatch")
            for name in sorted(formal_files):
                if (FORMAL / name).read_bytes() != (
                        regenerated / name).read_bytes():
                    raise AssertionError(
                        f"M03 trace regeneration mismatch: {name}")

    print(
        "M03_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files'])+1} pairs=12 transactions=1536 "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"regenerated={int(not args.integrity_only)} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
