#!/usr/bin/env python3
"""Derive the 72-row M07 PV workload from the frozen real Llama trace."""

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
KV_GROUP_START = 0
KV_GROUP_LANES = 32
TILE_START = 0
TILE_LANES = 16
S24_SCALE = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
U16_MAX = (1 << 16) - 1

sys.path.insert(0, str(base.ROOT / "model"))
from fixbit_v2 import kv12_quantize_s24, pv_row_tile16_s24  # noqa: E402


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
    widened = np.asarray(array, dtype=np.uint32) << np.uint32(16)
    return widened.view(np.float32)


def quantize_probability(value: float) -> tuple[int, bool]:
    if not math.isfinite(value):
        raise AssertionError("non-finite probability in source trace")
    rounded = int(np.rint(float(value) * S24_SCALE))
    clipped = min(U16_MAX, max(0, rounded))
    return clipped, clipped != rounded


def quantize_s24_group(values: np.ndarray) -> tuple[list[int], int]:
    if values.shape != (KV_GROUP_LANES,):
        raise AssertionError(f"unexpected KV group shape {values.shape}")
    output: list[int] = []
    saturation_count = 0
    for value_raw in values:
        value = float(value_raw)
        if not math.isfinite(value):
            raise AssertionError("non-finite V value in source trace")
        rounded = int(np.rint(value * S24_SCALE))
        clipped = min(S24_MAX, max(S24_MIN, rounded))
        output.append(clipped)
        saturation_count += int(clipped != rounded)
    return output, saturation_count


def clipped_s24_real(value: float) -> float:
    return min(S24_MAX / S24_SCALE, max(S24_MIN / S24_SCALE, value))


def metric(values: list[int], ideal: list[float]) -> dict[str, float]:
    return base.accuracy_metrics(values, ideal)


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


def unpack_expected(records: list[int]) -> list[int]:
    result: list[int] = []
    for record in records:
        for lane in range(TILE_LANES):
            value = (record >> (lane * 24)) & 0xFFFFFF
            result.append(value - (1 << 24) if value & (1 << 23) else value)
    return result


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
    probability_records: list[int] = []
    value_records: list[int] = []
    meta_records: list[int] = []
    probability16_records: list[int] = []
    probability32_records: list[int] = []
    scale16_records: list[int] = []
    scale32_records: list[int] = []
    value16_records: list[int] = []
    value32_records: list[int] = []
    expected_sc: list[int] = []
    expected16: list[int] = []
    expected32: list[int] = []
    ideal_trace: list[float] = []
    ideal_common: list[float] = []
    provenance_rows: list[dict[str, object]] = []
    source_records_used: dict[str, dict[str, object]] = {}
    probability_errors: list[float] = []
    v_s24_errors: list[float] = []
    v_kv12_errors_vs_s24: list[float] = []
    v_kv12_errors_vs_trace: list[float] = []
    probability_saturation_count = 0
    v_s24_saturation_count = 0
    kv12_clip_count = 0
    zero_scale_records = 0
    fp16_scale_subnormal_records = 0
    fp16_probability_ftz_records = 0
    fp16_zero_v_lanes_from_nonzero_inputs = 0
    saturation = {"sc": 0, "fp16": 0, "fp32": 0}

    row_index = 0
    for sample in SAMPLES:
        for layer in LAYERS:
            probability_record = tensor_records[
                (sample, layer, "probability_fp32")]
            value_record = tensor_records[(sample, layer, "v_bf16")]
            probability_array = load_source_tensor(
                trace_dir, probability_record)
            value_bits = load_source_tensor(trace_dir, value_record)
            value_array = bf16_bits_to_fp32(value_bits)
            source_records_used[str(probability_record["file"])] = \
                source_record_summary(probability_record)
            source_records_used[str(value_record["file"])] = \
                source_record_summary(value_record)

            for key_count in SHAPES:
                query_token = key_count - 1
                for q_head in Q_HEADS:
                    kv_head = q_head // Q_HEADS_PER_KV_HEAD
                    raw_probabilities = [
                        float(value) for value in
                        probability_array[query_token, q_head, :key_count]
                    ]
                    probabilities: list[int] = []
                    row_values: list[list[int]] = []
                    row_codes: list[int] = []
                    row_shifts: list[int] = []
                    row_p16: list[np.float16] = []
                    row_p32: list[np.float32] = []
                    row_v16: list[list[np.float16]] = []
                    row_v32: list[list[np.float32]] = []
                    row_trace_v: list[list[float]] = []
                    row_common_v: list[list[float]] = []

                    for key_index, raw_probability in enumerate(
                            raw_probabilities):
                        probability, probability_saturated = \
                            quantize_probability(raw_probability)
                        probability_saturation_count += int(
                            probability_saturated)
                        probability_errors.append(abs(
                            raw_probability - probability / S24_SCALE))

                        raw_group = value_array[
                            key_index, kv_head,
                            KV_GROUP_START:KV_GROUP_START + KV_GROUP_LANES]
                        s24_group, group_saturations = quantize_s24_group(
                            raw_group)
                        v_s24_saturation_count += group_saturations
                        quantized = kv12_quantize_s24(s24_group)
                        kv12_clip_count += quantized.clip_count
                        zero_scale_records += int(quantized.scale_code == 0)
                        tile_values = list(quantized.values[
                            TILE_START:TILE_START + TILE_LANES])
                        trace_v = [
                            float(value) for value in raw_group[
                                TILE_START:TILE_START + TILE_LANES]
                        ]
                        scale = (quantized.scale_code /
                                 float(1 << quantized.scale_shift)
                                 if quantized.scale_code else 0.0)
                        common_v = [value * scale for value in tile_values]
                        for source, s24, restored in zip(
                                trace_v,
                                s24_group[TILE_START:TILE_START + TILE_LANES],
                                common_v, strict=True):
                            s24_real = s24 / S24_SCALE
                            v_s24_errors.append(abs(source - s24_real))
                            v_kv12_errors_vs_s24.append(abs(
                                s24_real - restored))
                            v_kv12_errors_vs_trace.append(abs(
                                source - restored))

                        scale16 = np.float16(scale)
                        scale32 = np.float32(scale)
                        if (quantized.scale_code and
                                (base.fp16_bits(scale16) & 0x7C00) == 0):
                            fp16_scale_subnormal_records += 1
                        values16 = [
                            base.mul16(np.float16(value), scale16)
                            for value in tile_values
                        ]
                        values32 = [
                            np.float32(np.float32(value) * scale32)
                            for value in tile_values
                        ]
                        probability16_raw = np.float16(
                            probability / S24_SCALE)
                        probability16 = base.ftz16(probability16_raw)
                        probability32 = np.float32(
                            probability / S24_SCALE)
                        fp16_probability_ftz_records += int(
                            probability != 0 and
                            base.fp16_bits(probability16) in (0, 0x8000))
                        fp16_zero_v_lanes_from_nonzero_inputs += sum(
                            int(value != 0 and
                                base.fp16_bits(converted) in (0, 0x8000))
                            for value, converted in zip(
                                tile_values, values16, strict=True))

                        probability_records.append(probability)
                        value_records.append(base.pack_lanes(tile_values, 12))
                        meta_records.append(quantized.metadata)
                        probability16_records.append(
                            base.fp16_bits(probability16))
                        probability32_records.append(
                            base.fp32_bits(probability32))
                        scale16_records.append(base.fp16_bits(scale16))
                        scale32_records.append(base.fp32_bits(scale32))
                        value16_records.append(base.pack_lanes(
                            [base.fp16_bits(value) for value in values16], 16))
                        value32_records.append(base.pack_lanes(
                            [base.fp32_bits(value) for value in values32], 32))
                        probabilities.append(probability)
                        row_values.append(tile_values)
                        row_codes.append(quantized.scale_code)
                        row_shifts.append(quantized.scale_shift)
                        row_p16.append(probability16)
                        row_p32.append(probability32)
                        row_v16.append(values16)
                        row_v32.append(values32)
                        row_trace_v.append(trace_v)
                        row_common_v.append(common_v)

                    padded_count = 128 - key_count
                    sc_row, sc_saturation = pv_row_tile16_s24(
                        probabilities + [0] * padded_count,
                        row_values + [[0] * TILE_LANES] * padded_count,
                        row_codes + [0] * padded_count,
                        row_shifts + [0] * padded_count)
                    accum16 = [np.float16(0.0)] * TILE_LANES
                    accum32 = [np.float32(0.0)] * TILE_LANES
                    accum_trace = [0.0] * TILE_LANES
                    accum_common = [0.0] * TILE_LANES
                    for key_index in range(key_count):
                        for lane in range(TILE_LANES):
                            accum16[lane] = base.add16(
                                accum16[lane], base.mul16(
                                    row_p16[key_index],
                                    row_v16[key_index][lane]))
                            accum32[lane] = np.float32(
                                accum32[lane] + np.float32(
                                    row_p32[key_index] *
                                    row_v32[key_index][lane]))
                            accum_trace[lane] += (
                                raw_probabilities[key_index] *
                                row_trace_v[key_index][lane])
                            accum_common[lane] += (
                                probabilities[key_index] / S24_SCALE *
                                row_common_v[key_index][lane])

                    fp16_row: list[int] = []
                    fp32_row: list[int] = []
                    for lane in range(TILE_LANES):
                        value16, sat16 = base.s24_from_float(
                            float(accum16[lane]))
                        value32, sat32 = base.s24_from_float(
                            float(accum32[lane]))
                        fp16_row.append(value16)
                        fp32_row.append(value32)
                        saturation["fp16"] += int(sat16)
                        saturation["fp32"] += int(sat32)
                    saturation["sc"] += sc_saturation
                    expected_sc.append(base.pack_lanes(list(sc_row), 24))
                    expected16.append(base.pack_lanes(fp16_row, 24))
                    expected32.append(base.pack_lanes(fp32_row, 24))
                    ideal_trace.extend(
                        clipped_s24_real(value) for value in accum_trace)
                    ideal_common.extend(
                        clipped_s24_real(value) for value in accum_common)
                    row_key_counts.append(key_count)
                    provenance_rows.append({
                        "row": row_index,
                        "sample": sample,
                        "layer": layer,
                        "shape": key_count,
                        "query_token": query_token,
                        "q_head": q_head,
                        "kv_head": kv_head,
                        "kv_group_start": KV_GROUP_START,
                        "kv_group_lanes": KV_GROUP_LANES,
                        "tile_start_within_group": TILE_START,
                        "tile_lanes": TILE_LANES,
                        "probability_source_tensor":
                            probability_record["file"],
                        "probability_source_payload_sha256":
                            probability_record["payload_sha256"],
                        "value_source_tensor": value_record["file"],
                        "value_source_payload_sha256":
                            value_record["payload_sha256"],
                    })
                    row_index += 1

    rows = len(SAMPLES) * len(LAYERS) * len(SHAPES) * len(Q_HEADS)
    keys = len(SAMPLES) * len(LAYERS) * len(Q_HEADS) * sum(SHAPES)
    if rows != 72 or keys != 4236:
        raise AssertionError("trace schedule no longer matches M07 TB geometry")
    if not (len(row_key_counts) == rows and
            len(probability_records) == keys and
            len(value_records) == keys and len(expected_sc) == rows):
        raise AssertionError("M07 trace-derived record count mismatch")

    outputs: dict[str, tuple[list[int], int]] = {
        "row_key_count_u8.mem": (row_key_counts, 2),
        "probability_u16.mem": (probability_records, 4),
        "value_s12x16.mem": (value_records, 48),
        "value_meta_sc_u16.mem": (meta_records, 4),
        "probability_fp16.mem": (probability16_records, 4),
        "probability_fp32.mem": (probability32_records, 8),
        "value_scale_fp16.mem": (scale16_records, 4),
        "value_scale_fp32.mem": (scale32_records, 8),
        "value_cache_fp16x16.mem": (value16_records, 64),
        "value_cache_fp32x16.mem": (value32_records, 128),
        "expected_sc_s24x16.mem": (expected_sc, 96),
        "expected_fp16_s24x16.mem": (expected16, 96),
        "expected_fp32_s24x16.mem": (expected32, 96),
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

    def error_metrics(errors: list[float]) -> dict[str, float]:
        squares = [value * value for value in errors]
        return {
            "max_abs": max(errors),
            "mean_abs": sum(errors) / len(errors),
            "rmse": math.sqrt(sum(squares) / len(squares)),
        }

    output_values = {
        "sc": unpack_expected(expected_sc),
        "fp16": unpack_expected(expected16),
        "fp32": unpack_expected(expected32),
    }
    trace_manifest_path = trace_dir / "manifest.json"
    production_model = base.ROOT / "model" / "fixbit_v2.py"
    manifest = {
        "schema": "scalellm_modular_m07_pv_real_trace_v1",
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
        "kv_quantization": {
            "source": "BF16 V trace",
            "s24_conversion": "nearest-even to signed S24 Q8.16, then saturate",
            "production_quantizer": "kv12_quantize_s24 over the full 32-lane group",
            "group_start": KV_GROUP_START,
            "group_lanes": KV_GROUP_LANES,
            "tile_start_within_group": TILE_START,
            "tile_lanes": TILE_LANES,
            "tile_head_dimensions": [
                KV_GROUP_START + TILE_START,
                KV_GROUP_START + TILE_START + TILE_LANES - 1,
            ],
        },
        "rows": rows,
        "keys": keys,
        "lanes": TILE_LANES,
        "common_input": (
            "real Llama probability rounded nearest-even to U16 Q0.16 plus "
            "production KV12 S12x16/native metadata derived from BF16 V"),
        "common_output": "signed S24 Q8.16 context16",
        "input_quantization_vs_trace": {
            "probability": error_metrics(probability_errors) | {
                "saturation_count": probability_saturation_count,
            },
            "v_bf16_to_s24": error_metrics(v_s24_errors) | {
                "saturation_count": v_s24_saturation_count,
            },
            "v_kv12_vs_s24": error_metrics(v_kv12_errors_vs_s24) | {
                "clip_count": kv12_clip_count,
            },
            "v_kv12_vs_trace": error_metrics(v_kv12_errors_vs_trace),
        },
        "coverage": {
            "zero_probabilities": sum(
                value == 0 for value in probability_records),
            "zero_scale_records": zero_scale_records,
            "fp16_scale_subnormal_records":
                fp16_scale_subnormal_records,
            "fp16_probability_ftz_records":
                fp16_probability_ftz_records,
            "fp16_zero_v_lanes_from_nonzero_inputs":
                fp16_zero_v_lanes_from_nonzero_inputs,
        },
        "saturation_counts": saturation,
        "accuracy_vs_raw_trace_pv": {
            version: metric(output_values[version], ideal_trace)
            for version in ("sc", "fp16", "fp32")
        },
        "accuracy_vs_common_quantized_fp64_pv": {
            version: metric(output_values[version], ideal_common)
            for version in ("sc", "fp16", "fp32")
        },
        "numeric_models": {
            "sc": "production pv_row_tile16_s24 ScaleCode shift/accumulate/finalize",
            "fp16": "U16/S12 to FP16 with FTZ, native scale multiply, sequential FP16 MAC",
            "fp32": "U16/S12 to FP32, native scale multiply, sequential FP32 MAC",
            "trace_reference": "FP64 accumulation over captured FP32 probability and BF16 V",
            "common_reference": "FP64 accumulation over common U16 and exact ScaleCode-decoded KV12 V",
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
        "M07_TRACE_VECTOR_PASS "
        f"rows={rows} keys={keys} lanes={TILE_LANES} "
        f"source_tensors={len(source_records_used)} "
        f"saturation_sc={saturation['sc']} "
        f"manifest_sha256={sha256_file(output / 'manifest.json')}")


if __name__ == "__main__":
    main()
