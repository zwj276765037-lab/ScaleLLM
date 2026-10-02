#!/usr/bin/env python3
"""Audit and independently regenerate the formal M12 real-trace workload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import generate_vectors as fp_semantics


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
FORMAL = MODULE / "data_trace"
GENERATOR = HERE / "generate_trace_vectors.py"
EXPECTED_LAYERS = [0, 15, 31]
MEM_CONTRACT = {
    "activation_s9x16x32.mem": (448, 1152),
    "activation_meta_sc_u224.mem": (448, 56),
    "activation_scale_fp16x16.mem": (448, 64),
    "activation_scale_fp32x16.mem": (448, 128),
    "weights_s4x12x32.mem": (153216, 384),
    "weight_meta_sc_u168.mem": (153216, 42),
    "weight_scale_fp16x12.mem": (153216, 48),
    "weight_scale_fp32x12.mem": (153216, 96),
    "column_mask_u12.mem": (342, 3),
    "expected_sc_s24x16x12.mem": (342, 1152),
    "expected_fp16_s24x16x12.mem": (342, 1152),
    "expected_fp32_s24x16x12.mem": (342, 1152),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", type=Path, default=FORMAL,
        help="trace directory to audit (defaults to the formal data_trace)",
    )
    parser.add_argument(
        "--integrity-only", action="store_true",
        help="check provenance, hashes, geometry, and file contents without "
             "performing the expensive byte-for-byte regeneration",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_hex_file(
        path: Path, expected_records: int, expected_digits: int,
) -> None:
    records = 0
    with path.open("r", encoding="ascii") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.rstrip("\n")
            if (len(line) != expected_digits or
                    any(character not in "0123456789abcdef"
                        for character in line)):
                raise AssertionError(
                    f"invalid hex at {path}:{line_number}")
            records += 1
    if records != expected_records:
        raise AssertionError(
            f"record count mismatch for {path}: "
            f"expected={expected_records} actual={records}")


def validate_manifest(manifest: dict) -> None:
    exact = {
        "schema": "scalellm_modular_m12_down_real_trace_v1",
        "layers": EXPECTED_LAYERS,
        "samples": [0, 1],
        "tokens": [0, 1, 15, 31, 63, 95, 111, 127],
        "rows_per_layer": 16,
        "groups": 448,
        "tiles": 342,
        "physical_columns": 12,
        "valid_output_columns": 4096,
        "group_size": 32,
        "transactions_per_layer": 153216,
        "tail_mask": "0x00f",
    }
    for name, expected in exact.items():
        if manifest.get(name) != expected:
            raise AssertionError(
                f"M12 trace manifest {name} mismatch: "
                f"expected={expected!r} actual={manifest.get(name)!r}")
    if len(manifest.get("layer_results", [])) != 3:
        raise AssertionError("M12 trace must contain three layer results")
    if len(manifest.get("source_tensors", [])) != 6:
        raise AssertionError("M12 trace must bind six source tensors")
    if len(manifest.get("checkpoint_shards", [])) != 3:
        raise AssertionError("M12 trace must bind three checkpoint shards")
    for layer_result, expected_layer in zip(
            manifest["layer_results"], EXPECTED_LAYERS, strict=True):
        if layer_result.get("layer") != expected_layer:
            raise AssertionError("M12 trace layer ordering changed")
        rows = layer_result.get("row_coordinates", [])
        if len(rows) != 16 or len({
                (row["sample"], row["layer"], row["token"])
                for row in rows}) != 16:
            raise AssertionError("M12 trace row coordinates are incomplete")
        if not 21 <= layer_result["nonzero_total_shift_min"] <= (
                layer_result["nonzero_total_shift_max"]
        ) <= 44:
            raise AssertionError("M12 trace violates RTL total-shift range")
    if "M11 producer counted once" not in manifest["comparison_boundary"]:
        raise AssertionError("M12 comparison-boundary contract changed")


def validate_sources(manifest: dict) -> None:
    if sha256_file(GENERATOR) != manifest["generator_sha256"]:
        raise AssertionError("M12 trace generator hash changed")
    fp_semantics_model = Path(manifest["fp_semantics_model"]).resolve(
        strict=True)
    expected_fp_semantics_model = (HERE / "generate_vectors.py").resolve()
    if fp_semantics_model != expected_fp_semantics_model:
        raise AssertionError("M12 FP semantics model path changed")
    if sha256_file(fp_semantics_model) != manifest[
            "fp_semantics_model_sha256"]:
        raise AssertionError("M12 FP semantics model changed")
    production_exporter = Path(manifest["production_exporter"])
    production_model = Path(manifest["production_model"])
    if sha256_file(production_exporter) != manifest[
            "production_exporter_sha256"]:
        raise AssertionError("M12 production artifact exporter changed")
    if sha256_file(production_model) != manifest[
            "production_model_sha256"]:
        raise AssertionError("M12 production fixed-point model changed")
    minmax_reference = Path(manifest["minmax_reference"])
    if sha256_file(minmax_reference) != manifest[
            "minmax_reference_sha256"]:
        raise AssertionError("M12 Min/Max reference changed")
    trace_run = Path(manifest["source_trace_run"])
    if (trace_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("M12 source trace STATUS changed")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M12 source trace exit status changed")
    source_manifest = trace_run / "trace/manifest.json"
    if sha256_file(source_manifest) != manifest[
            "source_trace_manifest_sha256"]:
        raise AssertionError("M12 source trace manifest changed")
    checkpoint = Path(manifest["checkpoint"])
    index = checkpoint / "model.safetensors.index.json"
    if sha256_file(index) != manifest["checkpoint_index_sha256"]:
        raise AssertionError("M12 checkpoint index changed")
    for record in manifest["checkpoint_shards"]:
        path = checkpoint / record["name"]
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M12 checkpoint shard changed: {path}")


def validate_files(manifest: dict, formal: Path) -> None:
    expected_paths = {"trace_rows.csv"}
    for layer in EXPECTED_LAYERS:
        for name in MEM_CONTRACT:
            expected_paths.add(f"layer{layer:02d}/{name}")
    if set(manifest["files"]) != expected_paths:
        raise AssertionError("M12 trace file inventory changed")
    for relative, record in manifest["files"].items():
        path = formal / relative
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise AssertionError(f"M12 trace file hash mismatch: {relative}")
        if relative.endswith(".mem"):
            name = Path(relative).name
            records, digits = MEM_CONTRACT[name]
            if (record["records"], record["hex_digits"]) != (records, digits):
                raise AssertionError(f"M12 manifest geometry drift: {relative}")
            verify_hex_file(path, records, digits)
    if manifest["files"]["trace_rows.csv"]["records"] != 48:
        raise AssertionError("M12 trace row provenance count changed")
    for layer in EXPECTED_LAYERS:
        masks = (formal / f"layer{layer:02d}/column_mask_u12.mem").read_text(
            encoding="ascii").splitlines()
        if masks != (["fff"] * 341 + ["00f"]):
            raise AssertionError(f"M12 layer {layer} tail mask changed")


def compare_regeneration(manifest: dict, formal: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="m12_trace_verify_") as temporary:
        regenerated = Path(temporary) / "data_trace"
        subprocess.run([
            sys.executable, str(GENERATOR),
            "--trace-run", manifest["source_trace_run"],
            "--model-dir", manifest["checkpoint"],
            "--output-dir", str(regenerated),
            "--layers", "0,15,31",
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           text=True)
        formal_files = {
            path.relative_to(formal).as_posix()
            for path in formal.rglob("*") if path.is_file()
        }
        regenerated_files = {
            path.relative_to(regenerated).as_posix()
            for path in regenerated.rglob("*") if path.is_file()
        }
        if formal_files != regenerated_files:
            raise AssertionError("M12 regenerated file inventory mismatch")
        for relative in sorted(formal_files):
            if (formal / relative).read_bytes() != (
                    regenerated / relative).read_bytes():
                raise AssertionError(
                    f"M12 trace regeneration mismatch: {relative}")


def main() -> None:
    args = parse_args()
    semantic_cases = fp_semantics.verify_fp16_mul_ip_boundary()
    formal = args.data_dir.resolve(strict=True)
    manifest_path = formal / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    validate_sources(manifest)
    validate_files(manifest, formal)
    if not args.integrity_only:
        compare_regeneration(manifest, formal)
    print(
        "M12_TRACE_VECTOR_VERIFY_PASS "
        f"files={len(manifest['files']) + 1} layers=3 rows=48 "
        f"transactions={3*153216} valid_outputs={3*16*4096} "
        f"regenerated={int(not args.integrity_only)} "
        f"fp16_boundary_cases={semantic_cases} "
        f"source_tensors={len(manifest['source_tensors'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
