#!/usr/bin/env python3
"""Verify and optionally regenerate the formal M02 real-trace workload."""

from __future__ import annotations

import argparse
import csv
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
    MODULE.parents[1] /
    "experiment/03_attention_rope/model/verify_trace_projection_inputs.py"
)
TILES = 18
TRANSACTIONS = TILES * 128
CONTRACT = {
    "act_u8.mem": (TRANSACTIONS, 512),
    "weight_s8.mem": (TRANSACTIONS, 1024),
    "zp_rows.mem": (TRANSACTIONS, 16),
    "scalecode_meta.mem": (TRANSACTIONS, 96),
    "fp16_meta.mem": (TRANSACTIONS, 96),
    "fp32_meta.mem": (TRANSACTIONS, 192),
    "expected_scalecode_s24.mem": (TILES, 768),
    "expected_fp16_s24.mem": (TILES, 768),
    "expected_fp32_s24.mem": (TILES, 768),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integrity-only", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=FORMAL)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_hashed_run_file(path: Path) -> None:
    run_dir = path.parent
    if (run_dir / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("M02 semantic source STATUS changed")
    if int((run_dir / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M02 semantic source exit status changed")
    matches = []
    for line in (run_dir / "SHA256SUMS").read_text(
            encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        if Path(name).resolve() == path:
            matches.append(digest)
    if matches != [sha256_file(path)]:
        raise AssertionError("M02 semantic source directory hash mismatch")


def main() -> None:
    args = parse_args()
    formal = args.data_dir.resolve(strict=True)
    manifest_path = formal / "manifest.json"
    manifest_hash_path = formal / "MANIFEST_SHA256"
    expected_manifest_hash = manifest_hash_path.read_text(
        encoding="ascii").split()[0]
    if sha256_file(manifest_path) != expected_manifest_hash:
        raise AssertionError("M02 trace manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m02_projection_real_trace_v1" or
            manifest.get("tiles") != TILES or manifest.get("rows") != 8 or
            manifest.get("cols") != 16 or
            manifest.get("groups_per_tile") != 128 or
            manifest.get("group_size") != 32 or
            manifest.get("transactions") != TRANSACTIONS or
            manifest.get("valid_outputs") != TILES * 8 * 16 or
            len(manifest.get("tile_coordinates", [])) != TILES):
        raise AssertionError("M02 trace manifest contract mismatch")
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M02 trace generator changed")
    for path_key, hash_key in (
            ("legacy_boundary_model", "legacy_boundary_model_sha256"),
            ("production_exporter", "production_exporter_sha256"),
            ("production_fixed_model", "production_fixed_model_sha256"),
            ("minmax_reference", "minmax_reference_sha256"),
            ("capture_verifier", "capture_verifier_sha256")):
        path = Path(manifest[path_key]).resolve(strict=True)
        if sha256_file(path) != manifest[hash_key]:
            raise AssertionError(f"M02 trace dependency changed: {path_key}")

    trace_run = Path(manifest["source_trace_run"]).resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("M02 trace source STATUS changed")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M02 trace source exit status changed")
    if sha256_file(trace_run / "trace/manifest.json") != manifest[
            "source_trace_manifest_sha256"]:
        raise AssertionError("M02 source trace manifest changed")
    capture = Path(manifest["projection_input_capture"]).resolve(strict=True)
    if sha256_file(capture / "manifest.json") != manifest[
            "projection_input_manifest_sha256"]:
        raise AssertionError("M02 projection input capture changed")
    semantic_map = Path(manifest["fp16_semantic_map"]).resolve(strict=True)
    if sha256_file(semantic_map) != manifest["fp16_semantic_map_sha256"]:
        raise AssertionError("M02 FP16 semantic map changed")
    verify_hashed_run_file(semantic_map)
    semantic_payload = json.loads(semantic_map.read_text(encoding="utf-8"))
    if semantic_payload.get("source_summary_sha256") != manifest[
            "fp16_semantic_source_summary_sha256"]:
        raise AssertionError("M02 FP16 semantic provenance changed")

    expected_files = set(CONTRACT) | {"trace_tiles.csv"}
    if set(manifest.get("files", {})) != expected_files:
        raise AssertionError("M02 trace file inventory mismatch")
    for name, record in manifest["files"].items():
        path = formal / name
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M02 trace file hash mismatch: {name}")
        if name in CONTRACT:
            records, digits = CONTRACT[name]
            lines = path.read_text(encoding="ascii").splitlines()
            if ((record["records"], record["hex_digits"]) !=
                    (records, digits) or len(lines) != records or
                    any(len(line) != digits or
                        any(character not in "0123456789abcdef"
                            for character in line) for line in lines)):
                raise AssertionError(f"M02 trace record mismatch: {name}")
    with (formal / "trace_tiles.csv").open(
            newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != TILES:
        raise AssertionError("M02 trace coordinate count mismatch")
    for index, (row, frozen) in enumerate(zip(
            rows, manifest["tile_coordinates"])):
        if int(row["tile"]) != index or int(frozen["tile"]) != index:
            raise AssertionError("M02 tile order mismatch")
        if row != {key: str(value) for key, value in frozen.items()}:
            raise AssertionError(f"M02 tile CSV mismatch at tile {index}")

    events = manifest.get("numeric_events", {})
    required_events = {
        "input_s24_saturation", "hadamard_saturation",
        "activation_clip_lanes", "pre_quant_clip_lanes",
        "activation_zero_scale_groups",
        "weight_preclamp_lanes", "fp16_correlation_nonfinite",
        "fp16_contribution_nonfinite", "fp16_zero_contributions",
        "sc_s42_overflow", "fp16_s42_overflow", "fp32_s42_overflow",
    }
    if set(events) != required_events or any(
            not isinstance(value, int) or value < 0 for value in events.values()):
        raise AssertionError("M02 numeric-event contract mismatch")
    if events["fp16_correlation_nonfinite"] <= 0:
        raise AssertionError("M02 workload lost FP16 overflow coverage")
    if events["activation_clip_lanes"] != 0 or \
            events["pre_quant_clip_lanes"] != 0:
        raise AssertionError("M02 activation quantization clipped a valid lane")
    ranges = manifest.get("correlation_ranges", {})
    if set(ranges) != {"Q", "K", "V"} or any(
            not -(1 << 20) <= ranges[kind][bound] < (1 << 20)
            for kind in ranges for bound in ("min", "max")):
        raise AssertionError("M02 correlation-range contract mismatch")
    if not 26 <= manifest["total_shift_min"] <= \
            manifest["total_shift_max"] <= 47:
        raise AssertionError("M02 total-shift contract mismatch")

    if args.integrity_only:
        subprocess.run([
            sys.executable, str(CAPTURE_VERIFIER),
            "--capture-dir", str(capture),
        ], check=True)
    else:
        with tempfile.TemporaryDirectory(
                prefix="m02_trace_verify_") as temporary:
            regenerated = Path(temporary)
            subprocess.run([
                sys.executable, str(GENERATOR),
                "--trace-run", str(trace_run),
                "--capture-dir", str(capture),
                "--model-dir", manifest["checkpoint"],
                "--semantic-map", str(semantic_map),
                "--output-dir", str(regenerated),
            ], check=True, stdout=subprocess.PIPE,
               stderr=subprocess.STDOUT, text=True)
            formal_files = {
                path.name for path in formal.iterdir() if path.is_file()
            }
            regenerated_files = {
                path.name for path in regenerated.iterdir() if path.is_file()
            }
            if formal_files != regenerated_files:
                raise AssertionError("M02 regenerated inventory mismatch")
            for name in sorted(formal_files):
                if (formal / name).read_bytes() != (
                        regenerated / name).read_bytes():
                    raise AssertionError(
                        f"M02 trace regeneration mismatch: {name}")

    print(
        "M02_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files'])+2} tiles={TILES} "
        f"transactions={TRANSACTIONS} "
        f"valid_outputs={TILES*8*16} "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"regenerated={int(not args.integrity_only)} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
