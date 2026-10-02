#!/usr/bin/env python3
"""Derive the 72-row M06 workload from the frozen real Llama trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import generate_boundary_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    ROOT / "result/trace/raw/20260909_221332_llama31_8b_replayable_trace")
SHAPES = (128, 112, 64, 32, 16, 1)
SAMPLES = (0, 1)
LAYERS = (0, 15, 31)
HEADS = (0, 17)
SCORE_SCALE = 1 << 14
S20_MIN = -(1 << 19)
S20_MAX = (1 << 19) - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--output-dir", type=Path,
                        default=MODULE / "data_trace")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_hash(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def softmax_fp64(values: list[float]) -> list[float]:
    maximum = max(values)
    exponents = [math.exp(value - maximum) for value in values]
    total = sum(exponents)
    return [value / total for value in exponents]


def metric_rows_with_ideal(
        rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    return [{**row, "ideal": row[key]} for row in rows]


def verify_source_trace(trace_run: Path) -> tuple[Path, dict[str, object]]:
    trace_run = trace_run.resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="utf-8").strip() != "PASS":
        raise AssertionError("source trace STATUS is not PASS")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("source trace exit status is nonzero")
    trace_dir = trace_run / "trace"
    manifest_path = trace_dir / "manifest.json"
    expected = (trace_dir / "MANIFEST_SHA256").read_text(
        encoding="utf-8").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("source trace manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "scalellm_modular_llama_trace_v1" or
            manifest.get("layers") != list(LAYERS)):
        raise AssertionError("source trace contract mismatch")
    if [sample["sample"] for sample in manifest["samples"]] != list(SAMPLES):
        raise AssertionError("source trace sample contract mismatch")
    return trace_dir, manifest


def main() -> None:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace_dir, trace_manifest = verify_source_trace(args.trace_run)
    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }

    row_key_counts: list[int] = []
    score_records: list[int] = []
    mask_records: list[int] = []
    score16_records: list[int] = []
    score32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    metric_rows: list[dict[str, object]] = []
    provenance_rows: list[dict[str, object]] = []
    source_records_used: dict[str, dict[str, object]] = {}
    score_quantization_errors: list[float] = []
    saturation_count = 0

    row_index = 0
    for sample in SAMPLES:
        for layer in LAYERS:
            key = (sample, layer, "score_raw_fp32")
            record = tensor_records[key]
            path = trace_dir / record["file"]
            if sha256_file(path) != record["file_sha256"]:
                raise AssertionError(f"source score file hash mismatch: {path}")
            array = np.load(path, allow_pickle=False)
            if (list(array.shape) != record["shape"] or
                    str(array.dtype) != record["storage_dtype"] or
                    payload_hash(array) != record["payload_sha256"]):
                raise AssertionError(f"source score payload mismatch: {path}")
            source_records_used[record["file"]] = {
                "sample": sample,
                "layer": layer,
                "file_sha256": record["file_sha256"],
                "payload_sha256": record["payload_sha256"],
                "shape": record["shape"],
                "storage_dtype": record["storage_dtype"],
            }

            for key_count in SHAPES:
                query_token = key_count - 1
                for head in HEADS:
                    raw = [float(value) for value in
                           array[query_token, head, :key_count]]
                    rounded = np.rint(np.asarray(raw, dtype=np.float64) *
                                      SCORE_SCALE).astype(np.int64)
                    saturation_count += int(np.count_nonzero(
                        (rounded < S20_MIN) | (rounded > S20_MAX)))
                    quantized = np.clip(rounded, S20_MIN, S20_MAX)
                    scores = [int(value) for value in quantized]
                    decoded = [score / SCORE_SCALE for score in scores]
                    score_quantization_errors.extend(
                        abs(source - restored)
                        for source, restored in zip(raw, decoded, strict=True))
                    masks = [False] * key_count
                    padded_scores = scores + [0] * (128 - key_count)
                    padded_masks = masks + [True] * (128 - key_count)
                    sc_row = list(base.softmax_row_u16(
                        padded_scores, padded_masks)[0])[:key_count]
                    fp16_row = base.fp_softmax_u16(scores, masks, 16)
                    fp32_row = base.fp_softmax_u16(scores, masks, 32)
                    ideal_trace = softmax_fp64(raw)
                    ideal_common = softmax_fp64(decoded)

                    row_key_counts.append(key_count)
                    score_records.extend(scores)
                    mask_records.extend(0 for _ in scores)
                    score16_records.extend(
                        base.fp16_bits(score / SCORE_SCALE) for score in scores)
                    score32_records.extend(
                        base.fp32_bits(score / SCORE_SCALE) for score in scores)
                    expected_sc.extend(sc_row)
                    expected16.extend(fp16_row)
                    expected32.extend(fp32_row)
                    metric_rows.append({
                        "sc": sc_row, "fp16": fp16_row, "fp32": fp32_row,
                        "ideal_trace": ideal_trace,
                        "ideal_common": ideal_common,
                        "masks": masks,
                    })
                    provenance_rows.append({
                        "row": row_index,
                        "sample": sample,
                        "layer": layer,
                        "query_token": query_token,
                        "q_head": head,
                        "key_count": key_count,
                        "source_tensor_file": record["file"],
                        "source_tensor_payload_sha256":
                            record["payload_sha256"],
                    })
                    row_index += 1

    rows = len(SAMPLES) * len(LAYERS) * len(SHAPES) * len(HEADS)
    scores = len(SAMPLES) * len(LAYERS) * len(HEADS) * sum(SHAPES)
    if rows != 72 or scores != 4236:
        raise AssertionError("trace schedule no longer matches M06 TB geometry")
    if not (len(row_key_counts) == rows and len(score_records) == scores and
            len(expected_sc) == scores):
        raise AssertionError("trace-derived record count mismatch")

    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "score_s20.mem": (score_records, 5),
        "mask.mem": (mask_records, 1),
        "score_fp16.mem": (score16_records, 4),
        "score_fp32.mem": (score32_records, 8),
        "expected_sc_u16.mem": (expected_sc, 4),
        "expected_fp16_u16.mem": (expected16, 4),
        "expected_fp32_u16.mem": (expected32, 4),
    }
    files: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        base.write_mem(output / filename, values, digits)
        files[filename] = {
            "records": len(values), "hex_digits": digits,
            "sha256": sha256_file(output / filename),
        }

    provenance_path = output / "trace_rows.csv"
    with provenance_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(provenance_rows[0]))
        writer.writeheader()
        writer.writerows(provenance_rows)
    files[provenance_path.name] = {
        "records": len(provenance_rows), "hex_digits": 0,
        "sha256": sha256_file(provenance_path),
    }

    squared = [value * value for value in score_quantization_errors]
    trace_metric_rows = metric_rows_with_ideal(metric_rows, "ideal_trace")
    common_metric_rows = metric_rows_with_ideal(metric_rows, "ideal_common")
    trace_manifest_path = trace_dir / "manifest.json"
    manifest = {
        "schema": "scalellm_modular_m06_softmax_real_trace_v1",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(trace_manifest_path),
        "samples": list(SAMPLES),
        "layers": list(LAYERS),
        "q_heads": list(HEADS),
        "shapes": list(SHAPES),
        "row_schedule": "sample, layer, shape descending, q_head",
        "query_token": "key_count-1 for exact causal prefix",
        "rows": rows,
        "scores": scores,
        "common_input": "real Llama score rounded nearest-even to signed S20 Q6.14",
        "common_output": "U16 Q0.16 probability",
        "score_quantization_vs_trace": {
            "saturation_count": saturation_count,
            "max_abs": max(score_quantization_errors),
            "mean_abs": sum(score_quantization_errors) /
                        len(score_quantization_errors),
            "rmse": math.sqrt(sum(squared) / len(squared)),
        },
        "accuracy_vs_raw_trace_fp64_softmax": {
            version: base.accuracy_metrics(trace_metric_rows, version)
            for version in ("sc", "fp16", "fp32")
        },
        "accuracy_vs_common_quantized_fp64_softmax": {
            version: base.accuracy_metrics(common_metric_rows, version)
            for version in ("sc", "fp16", "fp32")
        },
        "source_score_tensors": [source_records_used[name]
                                 | {"file": name}
                                 for name in sorted(source_records_used)],
        "files": files,
        "production_model": str(base.ROOT / "model" / "fixbit_v2.py"),
        "production_model_sha256": sha256_file(
            base.ROOT / "model" / "fixbit_v2.py"),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M06_TRACE_VECTOR_PASS "
        f"rows={rows} scores={scores} source_tensors={len(source_records_used)} "
        f"saturation={saturation_count} manifest_sha256="
        f"{sha256_file(output / 'manifest.json')}")


if __name__ == "__main__":
    main()
