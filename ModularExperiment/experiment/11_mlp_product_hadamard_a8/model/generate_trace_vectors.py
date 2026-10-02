#!/usr/bin/env python3
"""Derive full-shape M11 product-Hadamard/A8 data from real Llama trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

import generate_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace")
GROUPS = 448
ROWS = 16
LANES = 32
S32_SCALE = 1 << 16
S32_MIN = -(1 << 31)
S32_MAX = (1 << 31) - 1
ROW_COORDINATES = (
    (0, 0, 0), (0, 0, 64), (0, 0, 127),
    (0, 15, 0), (0, 15, 64), (0, 15, 127),
    (0, 31, 32), (0, 31, 96),
    (1, 0, 0), (1, 0, 64), (1, 0, 127),
    (1, 15, 0), (1, 15, 64), (1, 15, 127),
    (1, 31, 32), (1, 31, 96),
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


def quantize_s32_vector(values: np.ndarray) -> tuple[list[int], int]:
    output: list[int] = []
    saturation_count = 0
    for raw_value in values:
        value = float(raw_value)
        if not math.isfinite(value):
            raise AssertionError("non-finite SwiGLU value in source trace")
        rounded = int(np.rint(value * S32_SCALE))
        clipped = min(S32_MAX, max(S32_MIN, rounded))
        output.append(clipped)
        saturation_count += int(clipped != rounded)
    return output, saturation_count


def hadamard_real(values: list[float]) -> list[float]:
    if len(values) != LANES:
        raise AssertionError("M11 real Hadamard requires 32 lanes")
    work = list(values)
    distance = 1
    while distance < LANES:
        next_work = work.copy()
        for offset_base in range(0, LANES, distance * 2):
            for offset in range(distance):
                lhs = work[offset_base + offset]
                rhs = work[offset_base + offset + distance]
                next_work[offset_base + offset] = lhs + rhs
                next_work[offset_base + offset + distance] = lhs - rhs
        work = next_work
        distance *= 2
    normalization = 1.0 / math.sqrt(LANES)
    return [value * normalization for value in work]


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
    if manifest.get("schema") != "scalellm_modular_llama_trace_v1":
        raise AssertionError("source trace contract mismatch")
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
    return bf16_bits_to_fp32(array)


def main() -> None:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    trace_dir, trace_manifest = verify_source_trace(args.trace_run)
    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }
    if len(ROW_COORDINATES) != ROWS or len(set(ROW_COORDINATES)) != ROWS:
        raise AssertionError("M11 requires 16 unique row coordinates")

    source_arrays: dict[tuple[int, int], np.ndarray] = {}
    source_records_used: dict[str, dict[str, object]] = {}
    for sample, layer, _token in ROW_COORDINATES:
        key = (sample, layer)
        if key in source_arrays:
            continue
        record = tensor_records[
            (sample, layer, "swiglu_down_input_bf16")]
        source_arrays[key] = load_source_tensor(trace_dir, record)
        source_records_used[str(record["file"])] = {
            "sample": sample,
            "layer": layer,
            "name": record["name"],
            "file_sha256": record["file_sha256"],
            "payload_sha256": record["payload_sha256"],
            "shape": record["shape"],
            "storage_dtype": record["storage_dtype"],
        }

    input_records: list[int] = []
    sc_u8_records: list[int] = []
    sc_meta_records: list[int] = []
    fp_u8_records: list[int] = []
    fp16_meta_records: list[int] = []
    fp32_meta_records: list[int] = []
    reference_trace: list[float] = []
    reference_common: list[float] = []
    reconstructed_sc: list[float] = []
    reconstructed_fp16: list[float] = []
    reconstructed_fp32: list[float] = []
    input_errors: list[float] = []
    input_saturations = 0
    hadamard_saturations = 0
    zero_diff_rows = 0
    fp16_nonfinite_scales = 0
    scale_format_overflow_rows = 0

    for group in range(GROUPS):
        inputs: list[int] = []
        sc_u8: list[int] = []
        sc_meta: list[int] = []
        fp_u8: list[int] = []
        fp16_meta: list[int] = []
        fp32_meta: list[int] = []
        channel_start = group * LANES
        for sample, layer, token in ROW_COORDINATES:
            trace_values_array = source_arrays[(sample, layer)][
                token, channel_start:channel_start + LANES]
            trace_values = [float(value) for value in trace_values_array]
            source, saturations = quantize_s32_vector(trace_values_array)
            input_saturations += saturations
            input_errors.extend(abs(trace_value - fixed / S32_SCALE)
                                for trace_value, fixed in zip(
                                    trace_values, source, strict=True))
            transformed_result = base.mlp_fixed.hadamard32_product_normalized(
                source)
            transformed = list(transformed_result.values)
            trace_transformed = hadamard_real(trace_values)
            sc = base.minmax_a8.quantize_s35(transformed)
            fp_values, fp_zp, scale_q24 = base.native_fp_a8(transformed)
            scale_real = scale_q24 / float(1 << 24)
            scale16_bits = base.fp16_bits(scale_real)
            scale32_bits = base.fp32_bits(scale_real)
            scale16 = float(np.asarray(
                [scale16_bits], dtype=np.uint16).view(np.float16)[0])
            scale32 = float(np.asarray(
                [scale32_bits], dtype=np.uint32).view(np.float32)[0])

            inputs.extend(source)
            sc_u8.extend(sc.values)
            sc_meta.append(sc.metadata)
            fp_u8.extend(fp_values)
            fp16_meta.append((scale16_bits << 8) | fp_zp)
            fp32_meta.append((scale32_bits << 8) | fp_zp)
            hadamard_saturations += transformed_result.saturation_count
            zero_diff_rows += int(scale_q24 == 0)
            fp16_nonfinite_scales += int(not math.isfinite(scale16))
            scale_format_overflow_rows += int(sc.scale_format_overflow)
            sc_scale = (sc.scale_code / float(1 << sc.scale_shift)
                        if sc.scale_code else 0.0)
            for transformed_value, trace_value, sc_q, fp_q in zip(
                    transformed, trace_transformed, sc.values, fp_values,
                    strict=True):
                reference_trace.append(trace_value)
                reference_common.append(transformed_value / S32_SCALE)
                reconstructed_sc.append(
                    (sc_q - sc.zero_point) * sc_scale)
                reconstructed_fp16.append((fp_q - fp_zp) * scale16)
                reconstructed_fp32.append((fp_q - fp_zp) * scale32)

        input_records.append(base.pack(inputs, 32))
        sc_u8_records.append(base.pack(sc_u8, 8))
        sc_meta_records.append(base.pack(sc_meta, 24))
        fp_u8_records.append(base.pack(fp_u8, 8))
        fp16_meta_records.append(base.pack(fp16_meta, 24))
        fp32_meta_records.append(base.pack(fp32_meta, 40))

    if not (len(input_records) == len(sc_u8_records) == GROUPS and
            len(reference_trace) == GROUPS * ROWS * LANES):
        raise AssertionError("M11 trace-derived record count mismatch")

    outputs: dict[str, tuple[list[int], int]] = {
        "input_s32.mem": (input_records, 4096),
        "expected_sc_u8.mem": (sc_u8_records, 1024),
        "expected_sc_meta.mem": (sc_meta_records, 96),
        "expected_fp_u8.mem": (fp_u8_records, 1024),
        "expected_fp16_meta.mem": (fp16_meta_records, 96),
        "expected_fp32_meta.mem": (fp32_meta_records, 160),
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
        writer = csv.DictWriter(handle, fieldnames=(
            "row", "sample", "layer", "token", "source_tensor",
            "source_payload_sha256"))
        writer.writeheader()
        for row, (sample, layer, token) in enumerate(ROW_COORDINATES):
            record = tensor_records[
                (sample, layer, "swiglu_down_input_bf16")]
            writer.writerow({
                "row": row,
                "sample": sample,
                "layer": layer,
                "token": token,
                "source_tensor": record["file"],
                "source_payload_sha256": record["payload_sha256"],
            })
    files[provenance_path.name] = {
        "records": ROWS,
        "hex_digits": 0,
        "sha256": sha256_file(provenance_path),
    }

    squares = [value * value for value in input_errors]
    trace_manifest_path = trace_dir / "manifest.json"
    production_model = Path(base.mlp_fixed.__file__).resolve()
    manifest = {
        "schema": "scalellm_modular_m11_product_frontend_real_trace_v1",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(trace_manifest_path),
        "row_coordinates": [
            {"row": row, "sample": sample, "layer": layer, "token": token}
            for row, (sample, layer, token) in enumerate(ROW_COORDINATES)
        ],
        "groups": GROUPS,
        "rows": ROWS,
        "lanes": LANES,
        "full_intermediate_channels": GROUPS * LANES,
        "input": (
            "16 selected real SwiGLU rows x 14,336 channels, BF16 rounded "
            "nearest-even to signed S32 Q16.16"),
        "sc_output": "16x32 U8 plus 16x(meta24 zp/code/shift)",
        "fp16_output": "16x32 U8 plus 16x(zp8 + IEEE FP16 scale)",
        "fp32_output": "16x32 U8 plus 16x(zp8 + IEEE FP32 scale)",
        "input_quantization_vs_trace": {
            "max_abs": max(input_errors),
            "mean_abs": sum(input_errors) / len(input_errors),
            "rmse": math.sqrt(sum(squares) / len(squares)),
            "saturation_count": input_saturations,
        },
        "hadamard_saturation_count": hadamard_saturations,
        "zero_diff_rows": zero_diff_rows,
        "fp16_nonfinite_scale_count": fp16_nonfinite_scales,
        "scale_format_overflow_rows": scale_format_overflow_rows,
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "accuracy_vs_raw_trace_hadamard": {
            "sc": base.metrics(reconstructed_sc, reference_trace),
            "fp16": base.metrics(reconstructed_fp16, reference_trace),
            "fp32": base.metrics(reconstructed_fp32, reference_trace),
        },
        "accuracy_vs_common_s35_hadamard": {
            "sc": base.metrics(reconstructed_sc, reference_common),
            "fp16": base.metrics(reconstructed_fp16, reference_common),
            "fp32": base.metrics(reconstructed_fp32, reference_common),
        },
        "source_tensors": [
            source_records_used[name] | {"file": name}
            for name in sorted(source_records_used)
        ],
        "files": files,
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "minmax_reference": str(Path(base.minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(
            Path(base.minmax_a8.__file__)),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M11_TRACE_VECTOR_PASS "
        f"groups={GROUPS} rows={ROWS} lanes={LANES} "
        f"source_tensors={len(source_records_used)} "
        f"manifest_sha256={sha256_file(output / 'manifest.json')}")


if __name__ == "__main__":
    main()
