#!/usr/bin/env python3
"""Verify hashes and the frozen-Q/K provenance of the M03 input supplement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
DEFAULT_CAPTURE = MODULE / "data_trace_projection_input"
EXPECTED_SCHEMA = "scalellm_modular_m03_projection_input_trace_v1"
LAYERS = (0, 15, 31)
SAMPLES = (0, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_hash(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def main() -> None:
    args = parse_args()
    capture = args.capture_dir.resolve(strict=True)
    manifest_path = capture / "manifest.json"
    manifest_hash = sha256_file(manifest_path)
    expected_hash = (capture / "MANIFEST_SHA256").read_text(
        encoding="ascii").split()[0]
    if manifest_hash != expected_hash:
        raise AssertionError("M03 capture manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != EXPECTED_SCHEMA or
            manifest.get("samples") != list(SAMPLES) or
            manifest.get("layers") != list(LAYERS) or
            manifest.get("tokens") != 128 or
            manifest.get("hidden") != 4096):
        raise AssertionError("M03 capture contract mismatch")

    capture_script = Path(manifest["capture_script"])
    if sha256_file(capture_script) != manifest["capture_script_sha256"]:
        raise AssertionError("M03 capture script changed")

    trace_run = Path(manifest["source_trace_run"]).resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("M03 source trace STATUS changed")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("M03 source trace exit status changed")
    trace_dir = trace_run / "trace"
    trace_manifest_path = trace_dir / "manifest.json"
    if sha256_file(trace_manifest_path) != manifest[
            "source_trace_manifest_sha256"]:
        raise AssertionError("M03 source trace manifest changed")
    trace_manifest = json.loads(trace_manifest_path.read_text(encoding="utf-8"))
    tensor_records = {
        record["file"]: record for record in trace_manifest["tensors"]
    }
    sample_records = {
        record["input_ids"]["file"]: record["input_ids"]
        for record in trace_manifest["samples"]
    }

    model_dir = Path(manifest["checkpoint"]).resolve(strict=True)
    index_path = model_dir / "model.safetensors.index.json"
    if sha256_file(index_path) != manifest["checkpoint_index_sha256"]:
        raise AssertionError("M03 checkpoint index changed")
    for record in manifest["checkpoint_shards"]:
        path = model_dir / record["name"]
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["sha256"]):
            raise AssertionError(f"M03 checkpoint shard changed: {path}")

    expected_names = {
        f"s{sample:02d}_l{layer:02d}_attention_input_bf16.npy"
        for sample in SAMPLES for layer in LAYERS
    }
    records = manifest["files"]
    if {record["file"] for record in records} != expected_names:
        raise AssertionError("M03 capture file inventory mismatch")
    for record in records:
        path = capture / record["file"]
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["file_sha256"]):
            raise AssertionError(f"M03 capture file changed: {path}")
        array = np.load(path, allow_pickle=False)
        if (array.shape != (128, 4096) or array.dtype != np.uint16 or
                list(array.shape) != record["shape"] or
                str(array.dtype) != record["storage_dtype"] or
                payload_hash(array) != record["payload_sha256"]):
            raise AssertionError(f"M03 capture payload changed: {path}")

    if len(manifest["input_id_sources"]) != len(SAMPLES):
        raise AssertionError("M03 input ID provenance count mismatch")
    for record in manifest["input_id_sources"]:
        source = sample_records[record["file"]]
        if (record["file_sha256"] != source["file_sha256"] or
                record["payload_sha256"] != source["payload_sha256"]):
            raise AssertionError("M03 input ID provenance mismatch")
        if sha256_file(trace_dir / record["file"]) != record["file_sha256"]:
            raise AssertionError("M03 frozen input ID file changed")

    checks = manifest["projection_output_checks"]
    if len(checks) != len(SAMPLES) * len(LAYERS) * 2:
        raise AssertionError("M03 Q/K replay check count mismatch")
    gate = manifest.get("projection_output_gate")
    if gate != {"max_normalized_rmse": 0.02, "min_cosine": 0.9998}:
        raise AssertionError("M03 Q/K replay gate changed")
    for check in checks:
        source = tensor_records[check["frozen_tensor"]]
        if (type(check["bit_mismatches"]) is not int or
                check["bit_mismatches"] < 0 or
                not 0.0 <= float(check["normalized_rmse"]) <=
                gate["max_normalized_rmse"] or
                not gate["min_cosine"] <= float(check["cosine"]) <= 1.000001 or
                check["frozen_file_sha256"] != source["file_sha256"] or
                check["frozen_payload_sha256"] != source["payload_sha256"] or
                sha256_file(trace_dir / source["file"]) !=
                source["file_sha256"]):
            raise AssertionError("M03 frozen Q/K replay provenance mismatch")

    print(
        "M03_PROJECTION_INPUT_VERIFY_PASS "
        f"files={len(records)} samples={len(SAMPLES)} layers={len(LAYERS)} "
        f"qk_checks={len(checks)} "
        f"bit_mismatches={sum(int(item['bit_mismatches']) for item in checks)} "
        f"manifest_sha256={manifest_hash}")


if __name__ == "__main__":
    main()
