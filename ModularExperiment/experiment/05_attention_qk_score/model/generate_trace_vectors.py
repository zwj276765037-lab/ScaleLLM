#!/usr/bin/env python3
"""Derive the 72-row M05 QK workload from the frozen real Llama trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

import generate_boundary_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace")
SHAPES = (128, 112, 64, 32, 16, 1)
SAMPLES = (0, 1)
LAYERS = (0, 15, 31)
Q_HEADS = (0, 17)
Q_HEADS_PER_KV_HEAD = 4
GROUPS = 4
LANES = 32
S24_SCALE = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
TRACE_HEAD_SCALE = 1.0 / math.sqrt(GROUPS * LANES)

sys.path.insert(0, str(base.ROOT / "model"))
from fixbit_v2 import (  # noqa: E402
    kv12_quantize_s24,
    q24k12_group_dot_s40,
    score_finalize_s20,
    score_group_q14_s35,
)


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


def bf16_bits_to_fp32(array: np.ndarray) -> np.ndarray:
    if array.dtype != np.uint16:
        raise AssertionError(f"expected uint16 BF16 storage, got {array.dtype}")
    return (np.asarray(array, dtype=np.uint32) << np.uint32(16)).view(
        np.float32)


def quantize_s24_vector(values: np.ndarray) -> tuple[list[int], int]:
    output: list[int] = []
    saturation_count = 0
    for raw_value in values:
        value = float(raw_value)
        if not math.isfinite(value):
            raise AssertionError("non-finite Q/K value in source trace")
        rounded = int(np.rint(value * S24_SCALE))
        clipped = min(S24_MAX, max(S24_MIN, rounded))
        output.append(clipped)
        saturation_count += int(clipped != rounded)
    return output, saturation_count


def clipped_score(value: float) -> float:
    return min(16.0, max(-16.0, value))


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


def load_source_tensor(
        trace_dir: Path,
        record: dict[str, object],
) -> np.ndarray:
    path = trace_dir / str(record["file"])
    if sha256_file(path) != record["file_sha256"]:
        raise AssertionError(f"source tensor file hash mismatch: {path}")
    array = np.load(path, allow_pickle=False)
    if (list(array.shape) != record["shape"] or
            str(array.dtype) != record["storage_dtype"] or
            payload_hash(array) != record["payload_sha256"]):
        raise AssertionError(f"source tensor payload mismatch: {path}")
    return array


def source_record_summary(record: dict[str, object]) -> dict[str, object]:
    return {
        "sample": record["sample"],
        "layer": record["layer"],
        "name": record["name"],
        "file_sha256": record["file_sha256"],
        "payload_sha256": record["payload_sha256"],
        "shape": record["shape"],
        "storage_dtype": record["storage_dtype"],
    }


def input_error_metrics(errors: list[float], **counts: int) -> dict[str, float | int]:
    squares = [value * value for value in errors]
    return {
        "max_abs": max(errors),
        "mean_abs": sum(errors) / len(errors),
        "rmse": math.sqrt(sum(squares) / len(squares)),
        **counts,
    }


def main() -> None:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace_dir, trace_manifest = verify_source_trace(args.trace_run)
    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }

    query_s24_records: list[int] = []
    query_cache16_records: list[int] = []
    query_cache32_records: list[int] = []
    key_s12_records: list[int] = []
    key_meta_records: list[int] = []
    key_scale16_records: list[int] = []
    key_scale32_records: list[int] = []
    key_cache16_records: list[int] = []
    key_cache32_records: list[int] = []
    row_key_counts: list[int] = []
    masks: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    captured_reference: list[float] = []
    common_reference: list[float] = []
    query_s24_errors: list[float] = []
    key_s24_errors: list[float] = []
    key_kv12_errors_vs_s24: list[float] = []
    key_kv12_errors_vs_trace: list[float] = []
    captured_score_recompute_errors: list[float] = []
    clip_counts = {"sc": 0, "fp16": 0, "fp32": 0}
    query_s24_saturation_count = 0
    key_s24_saturation_count = 0
    kv12_clip_count = 0
    zero_scale_records = 0
    fp16_scale_subnormal_records = 0
    fp16_zero_key_lanes_from_nonzero_inputs = 0
    provenance_rows: list[dict[str, object]] = []
    source_records_used: dict[str, dict[str, object]] = {}

    row_index = 0
    for sample in SAMPLES:
        for layer in LAYERS:
            q_record = tensor_records[(sample, layer, "q_post_rope_bf16")]
            k_record = tensor_records[(sample, layer, "k_post_rope_bf16")]
            score_record = tensor_records[(sample, layer, "score_raw_fp32")]
            q_bits = load_source_tensor(trace_dir, q_record)
            k_bits = load_source_tensor(trace_dir, k_record)
            score_array = load_source_tensor(trace_dir, score_record)
            q_array = bf16_bits_to_fp32(q_bits)
            k_array = bf16_bits_to_fp32(k_bits)
            for record in (q_record, k_record, score_record):
                source_records_used[str(record["file"])] = \
                    source_record_summary(record)

            for key_count in SHAPES:
                query_token = key_count - 1
                for q_head in Q_HEADS:
                    kv_head = q_head // Q_HEADS_PER_KV_HEAD
                    q_trace = q_array[query_token, q_head]
                    query_values, query_saturations = quantize_s24_vector(
                        q_trace)
                    query_s24_saturation_count += query_saturations
                    for source, quantized in zip(
                            q_trace, query_values, strict=True):
                        query_s24_errors.append(abs(
                            float(source) - quantized / S24_SCALE))

                    query_groups = [
                        query_values[group * LANES:(group + 1) * LANES]
                        for group in range(GROUPS)
                    ]
                    query16_groups: list[list[np.float16]] = []
                    query32_groups: list[list[np.float32]] = []
                    for group_values in query_groups:
                        lanes32 = [np.float32(value / S24_SCALE)
                                   for value in group_values]
                        lanes16 = [base.ftz16(np.float16(value))
                                   for value in lanes32]
                        query_s24_records.append(
                            base.pack_lanes(group_values, 24))
                        query_cache16_records.append(base.pack_lanes(
                            [base.fp16_bits(value) for value in lanes16], 16))
                        query_cache32_records.append(base.pack_lanes(
                            [base.fp32_bits(value) for value in lanes32], 32))
                        query16_groups.append(lanes16)
                        query32_groups.append(lanes32)

                    q16_flat = [value for values in query16_groups
                                for value in values]
                    q32_flat = [value for values in query32_groups
                                for value in values]
                    q64_flat = [value / S24_SCALE for value in query_values]
                    q16_scaled = [
                        base.mul16(value, base.bits_fp16(0x2DA8))
                        for value in q16_flat
                    ]
                    row_key_counts.append(key_count)

                    for key_index in range(key_count):
                        sc_groups: list[int] = []
                        k16_flat: list[np.float16] = []
                        k32_flat: list[np.float32] = []
                        k64_flat: list[float] = []
                        k_trace = k_array[key_index, kv_head]
                        for group in range(GROUPS):
                            trace_group = k_trace[
                                group * LANES:(group + 1) * LANES]
                            s24_group, key_saturations = quantize_s24_vector(
                                trace_group)
                            key_s24_saturation_count += key_saturations
                            quantized = kv12_quantize_s24(s24_group)
                            kv12_clip_count += quantized.clip_count
                            zero_scale_records += int(
                                quantized.scale_code == 0)
                            scale = (quantized.scale_code /
                                     float(1 << quantized.scale_shift)
                                     if quantized.scale_code else 0.0)
                            scale16 = np.float16(scale)
                            scale32 = np.float32(scale)
                            if (quantized.scale_code and
                                    (base.fp16_bits(scale16) & 0x7C00) == 0):
                                fp16_scale_subnormal_records += 1
                            lanes16 = [
                                base.mul16(np.float16(value), scale16)
                                for value in quantized.values
                            ]
                            lanes32 = [
                                np.float32(np.float32(value) * scale32)
                                for value in quantized.values
                            ]
                            fp16_zero_key_lanes_from_nonzero_inputs += sum(
                                int(value != 0 and
                                    base.fp16_bits(restored) in (0, 0x8000))
                                for value, restored in zip(
                                    quantized.values, lanes16, strict=True))
                            for source, s24, qvalue in zip(
                                    trace_group, s24_group,
                                    quantized.values, strict=True):
                                s24_real = s24 / S24_SCALE
                                restored = qvalue * scale
                                key_s24_errors.append(abs(
                                    float(source) - s24_real))
                                key_kv12_errors_vs_s24.append(abs(
                                    s24_real - restored))
                                key_kv12_errors_vs_trace.append(abs(
                                    float(source) - restored))

                            key_s12_records.append(base.pack_lanes(
                                list(quantized.values), 12))
                            key_meta_records.append(quantized.metadata)
                            key_scale16_records.append(
                                base.fp16_bits(scale16))
                            key_scale32_records.append(
                                base.fp32_bits(scale32))
                            key_cache16_records.append(base.pack_lanes(
                                [base.fp16_bits(value) for value in lanes16],
                                16))
                            key_cache32_records.append(base.pack_lanes(
                                [base.fp32_bits(value) for value in lanes32],
                                32))
                            k16_flat.extend(lanes16)
                            k32_flat.extend(lanes32)
                            k64_flat.extend(
                                value * scale for value in quantized.values)
                            if quantized.scale_code == 0:
                                sc_groups.append(0)
                            else:
                                dot = q24k12_group_dot_s40(
                                    query_groups[group], quantized.values)
                                sc_groups.append(score_group_q14_s35(
                                    dot, quantized.scale_code,
                                    quantized.scale_shift))

                        sc_score, sc_clip = score_finalize_s20(sc_groups)
                        products16 = [
                            np.float32(base.mul16(qvalue, kvalue))
                            for qvalue, kvalue in zip(
                                q16_scaled, k16_flat, strict=True)
                        ]
                        sum16 = base.balanced_sum_f32(products16)
                        score16, clip16 = base.clip_score(int(np.rint(
                            float(sum16) * (1 << 14))))
                        products32 = [
                            np.float32(qvalue * kvalue)
                            for qvalue, kvalue in zip(
                                q32_flat, k32_flat, strict=True)
                        ]
                        sum32 = base.balanced_sum_f32(products32)
                        scaled32 = np.float32(
                            sum32 * base.bits_fp32(0x3DB50800))
                        score32, clip32 = base.clip_score(int(np.rint(
                            float(scaled32) * (1 << 14))))
                        reference_common = float(np.dot(
                            np.asarray(q64_flat, dtype=np.float64),
                            np.asarray(k64_flat, dtype=np.float64)) *
                            (base.HEAD_SCALE_Q16 / S24_SCALE))
                        reference_captured = float(
                            score_array[query_token, q_head, key_index])
                        recomputed_trace = float(np.dot(
                            np.asarray(q_trace, dtype=np.float64),
                            np.asarray(k_trace, dtype=np.float64)) *
                            TRACE_HEAD_SCALE)
                        captured_score_recompute_errors.append(abs(
                            reference_captured - recomputed_trace))

                        expected_sc.append(sc_score)
                        expected16.append(score16)
                        expected32.append(score32)
                        captured_reference.append(
                            clipped_score(reference_captured))
                        common_reference.append(
                            clipped_score(reference_common))
                        clip_counts["sc"] += int(sc_clip)
                        clip_counts["fp16"] += int(clip16)
                        clip_counts["fp32"] += int(clip32)
                        masks.append(0)

                    provenance_rows.append({
                        "row": row_index,
                        "sample": sample,
                        "layer": layer,
                        "shape": key_count,
                        "query_token": query_token,
                        "q_head": q_head,
                        "kv_head": kv_head,
                        "query_source_tensor": q_record["file"],
                        "query_source_payload_sha256":
                            q_record["payload_sha256"],
                        "key_source_tensor": k_record["file"],
                        "key_source_payload_sha256":
                            k_record["payload_sha256"],
                        "score_source_tensor": score_record["file"],
                        "score_source_payload_sha256":
                            score_record["payload_sha256"],
                    })
                    row_index += 1

    rows = len(SAMPLES) * len(LAYERS) * len(SHAPES) * len(Q_HEADS)
    scores = len(SAMPLES) * len(LAYERS) * len(Q_HEADS) * sum(SHAPES)
    key_groups = scores * GROUPS
    if rows != 72 or scores != 4236 or key_groups != 16944:
        raise AssertionError("M05 trace schedule no longer matches TB geometry")
    if not (len(row_key_counts) == rows and
            len(query_s24_records) == rows * GROUPS and
            len(key_s12_records) == key_groups and
            len(expected_sc) == scores and len(masks) == scores):
        raise AssertionError("M05 trace-derived record count mismatch")

    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "query_group_s24.mem": (query_s24_records, 192),
        "query_cache_fp16.mem": (query_cache16_records, 128),
        "query_cache_fp32.mem": (query_cache32_records, 256),
        "key_group_s12.mem": (key_s12_records, 96),
        "key_meta_sc_u16.mem": (key_meta_records, 4),
        "key_scale_fp16.mem": (key_scale16_records, 4),
        "key_scale_fp32.mem": (key_scale32_records, 8),
        "key_cache_fp16.mem": (key_cache16_records, 128),
        "key_cache_fp32.mem": (key_cache32_records, 256),
        "mask.mem": (masks, 1),
        "expected_sc.mem": (expected_sc, 5),
        "expected_fp16.mem": (expected16, 5),
        "expected_fp32.mem": (expected32, 5),
        "clip_count_sc.mem": ([clip_counts["sc"]], 8),
        "clip_count_fp16.mem": ([clip_counts["fp16"]], 8),
        "clip_count_fp32.mem": ([clip_counts["fp32"]], 8),
    }
    files: dict[str, dict[str, int | str]] = {}
    for filename, (values, digits) in outputs.items():
        base.write_mem(output / filename, values, digits)
        files[filename] = {
            "records": len(values),
            "hex_digits": digits,
            "sha256": sha256_file(output / filename),
        }

    provenance_path = output / "trace_rows.csv"
    with provenance_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(provenance_rows[0]))
        writer.writeheader()
        writer.writerows(provenance_rows)
    files[provenance_path.name] = {
        "records": len(provenance_rows),
        "hex_digits": 0,
        "sha256": sha256_file(provenance_path),
    }

    trace_manifest_path = trace_dir / "manifest.json"
    production_model = base.ROOT / "model" / "fixbit_v2.py"
    manifest = {
        "schema": "scalellm_modular_m05_qk_real_trace_v1",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(trace_manifest_path),
        "samples": list(SAMPLES),
        "layers": list(LAYERS),
        "q_heads": list(Q_HEADS),
        "gqa_q_heads_per_kv_head": Q_HEADS_PER_KV_HEAD,
        "kv_heads": [head // Q_HEADS_PER_KV_HEAD for head in Q_HEADS],
        "shapes": list(SHAPES),
        "row_schedule": "sample, layer, shape descending, q_head",
        "query_token": "key_count-1 for exact causal prefix",
        "rows": rows,
        "scores": scores,
        "key_groups": key_groups,
        "groups_per_score": GROUPS,
        "lanes_per_group": LANES,
        "common_input": (
            "post-RoPE BF16 Q rounded nearest-even to S24 Q8.16 plus "
            "post-RoPE BF16 K converted to S24 then production KV12/native metadata"),
        "common_output": "signed S20 Q6.14 with explicit +/-16 clip",
        "head_scale": {
            "trace": TRACE_HEAD_SCALE,
            "production_q16": base.HEAD_SCALE_Q16,
            "production_real": base.HEAD_SCALE_Q16 / S24_SCALE,
        },
        "input_quantization_vs_trace": {
            "query_bf16_to_s24": input_error_metrics(
                query_s24_errors,
                saturation_count=query_s24_saturation_count),
            "key_bf16_to_s24": input_error_metrics(
                key_s24_errors,
                saturation_count=key_s24_saturation_count),
            "key_kv12_vs_s24": input_error_metrics(
                key_kv12_errors_vs_s24, clip_count=kv12_clip_count),
            "key_kv12_vs_trace": input_error_metrics(
                key_kv12_errors_vs_trace),
            "fp64_bf16_dot_vs_captured_fp32_score": input_error_metrics(
                captured_score_recompute_errors),
        },
        "coverage": {
            "zero_scale_records": zero_scale_records,
            "fp16_scale_subnormal_records":
                fp16_scale_subnormal_records,
            "fp16_zero_key_lanes_from_nonzero_inputs":
                fp16_zero_key_lanes_from_nonzero_inputs,
            "masked_scores": sum(masks),
        },
        "clip_counts": clip_counts,
        "accuracy_vs_captured_trace_score": {
            "sc": base.error_metrics(expected_sc, captured_reference),
            "fp16": base.error_metrics(expected16, captured_reference),
            "fp32": base.error_metrics(expected32, captured_reference),
        },
        "accuracy_vs_common_quantized_fp64_score": {
            "sc": base.error_metrics(expected_sc, common_reference),
            "fp16": base.error_metrics(expected16, common_reference),
            "fp32": base.error_metrics(expected32, common_reference),
        },
        "numeric_models": {
            "sc": "production fixed dot, ScaleCode group shift, accum4, clip",
            "fp16": "explicit KV12 dequant with FTZ plus balanced FP QK",
            "fp32": "explicit KV12 dequant plus balanced FP QK",
            "captured_reference": "frozen model score_raw_fp32",
            "common_reference": "FP64 common S24/KV12 dot times 5793/65536",
        },
        "source_tensors": [
            source_records_used[name] | {"file": name}
            for name in sorted(source_records_used)
        ],
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M05_TRACE_VECTOR_PASS "
        f"rows={rows} scores={scores} key_groups={key_groups} "
        f"source_tensors={len(source_records_used)} "
        f"manifest_sha256={sha256_file(output / 'manifest.json')}")


if __name__ == "__main__":
    main()
