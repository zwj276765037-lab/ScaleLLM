#!/usr/bin/env python3
"""Verify hashes, shapes, dtypes, and coordinate slices of a frozen trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "scalellm_modular_llama_trace_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_hash(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def verify_array(root: Path, record: dict[str, Any]) -> np.ndarray:
    path = root / record["file"]
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != record["bytes"]:
        raise AssertionError(f"file size mismatch: {path}")
    if sha256_file(path) != record["file_sha256"]:
        raise AssertionError(f"file hash mismatch: {path}")
    array = np.load(path, allow_pickle=False)
    if list(array.shape) != record["shape"]:
        raise AssertionError(f"shape mismatch: {path}")
    if str(array.dtype) != record["storage_dtype"]:
        raise AssertionError(f"dtype mismatch: {path}")
    if payload_hash(array) != record["payload_sha256"]:
        raise AssertionError(f"payload hash mismatch: {path}")
    return array


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.trace_dir.resolve(strict=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise AssertionError("unexpected trace schema")
    recorded_manifest_hash = (root / "MANIFEST_SHA256").read_text(
        encoding="utf-8").split()[0]
    if sha256_file(manifest_path) != recorded_manifest_hash:
        raise AssertionError("manifest hash mismatch")

    checkpoint = Path(manifest["checkpoint"])
    for record in manifest["checkpoint_files"]:
        path = checkpoint / record["name"]
        if path.stat().st_size != record["bytes"]:
            raise AssertionError(f"checkpoint size mismatch: {path}")
        if sha256_file(path) != record["sha256"]:
            raise AssertionError(f"checkpoint hash mismatch: {path}")
    source_hashes = {
        checkpoint / "model.safetensors.index.json":
            manifest["checkpoint_index_sha256"],
        checkpoint / "config.json": manifest["config_sha256"],
        checkpoint / "tokenizer.json": manifest["tokenizer_sha256"],
        Path(manifest["workload_source"]): manifest["workload_source_sha256"],
    }
    for path, expected in source_hashes.items():
        if sha256_file(path) != expected:
            raise AssertionError(f"source hash mismatch: {path}")

    arrays: dict[tuple[int, int, str], np.ndarray] = {}
    observed_files: set[str] = set()
    tensor_records = manifest["tensors"]
    if len(tensor_records) != manifest["tensor_count"]:
        raise AssertionError("tensor count mismatch")
    for record in tensor_records:
        key = (record["sample"], record["layer"], record["name"])
        if key in arrays:
            raise AssertionError(f"duplicate tensor record {key}")
        arrays[key] = verify_array(root, record)
        observed_files.add(record["file"])
        logical = record["logical_dtype"]
        expected_storage = "uint16" if logical == "bfloat16" else "float32"
        if record["storage_dtype"] != expected_storage:
            raise AssertionError(f"logical/storage dtype mismatch {key}")

    for sample in manifest["samples"]:
        record = sample["input_ids"]
        array = verify_array(root, record)
        observed_files.add(record["file"])
        if array.ndim != 1 or array.size != sample["token_count"]:
            raise AssertionError("input_ids shape mismatch")
        coordinates = sorted({0, array.size // 2, array.size - 1})
        if sample["selected_token_coordinates"] != coordinates:
            raise AssertionError("selected token coordinates mismatch")

    npy_files = {path.name for path in root.glob("*.npy")}
    if npy_files != observed_files:
        raise AssertionError(
            f"NPY inventory mismatch extra={sorted(npy_files-observed_files)} "
            f"missing={sorted(observed_files-npy_files)}")

    coordinate_record = manifest["coordinate_hashes"]
    coordinate_path = root / coordinate_record["file"]
    if sha256_file(coordinate_path) != coordinate_record["sha256"]:
        raise AssertionError("coordinate hash file mismatch")
    row_count = 0
    with coordinate_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            key = (int(row["sample"]), int(row["layer"]), row["tensor"])
            array = arrays[key]
            token = int(row["token"])
            if row["head"]:
                payload = array[token, int(row["head"])]
            elif row["group"]:
                group = int(row["group"])
                payload = array[token, group * 32:(group + 1) * 32]
            else:
                raise AssertionError(f"coordinate lacks head/group: {row}")
            if payload_hash(payload) != row["slice_payload_sha256"]:
                raise AssertionError(f"coordinate payload mismatch: {row}")
    if row_count != coordinate_record["rows"]:
        raise AssertionError("coordinate row count mismatch")

    # Probability is the PV input and must be a valid causal distribution.
    for key, array in arrays.items():
        if key[2] != "probability_fp32":
            continue
        if not np.isfinite(array).all():
            raise AssertionError(f"non-finite probability {key}")
        sums = array.sum(axis=-1, dtype=np.float64)
        if not np.allclose(sums, 1.0, atol=2e-6, rtol=0.0):
            raise AssertionError(f"probability sum mismatch {key}")
        for query_token in range(array.shape[0]):
            if np.any(array[query_token, :, query_token + 1:] != 0.0):
                raise AssertionError(f"causal probability leak {key}")

    print(
        f"LLAMA_TRACE_VERIFY_PASS samples={len(manifest['samples'])} "
        f"layers={len(manifest['layers'])} tensors={len(arrays)} "
        f"slices={row_count} manifest_sha256={recorded_manifest_hash}")


if __name__ == "__main__":
    main()
