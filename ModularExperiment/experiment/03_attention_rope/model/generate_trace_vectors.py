#!/usr/bin/env python3
"""Generate the real M03 projection-tail -> RoPE boundary workload.

The input activation comes from the independently verified projection-input
supplement.  Q/K weights come from the exact checkpoint and are quantized with
the production V5 normalized folded group32 W8 exporter.  For every selected
RoPE pair we reconstruct all 128 pre-centered correlations and native scale
metadata; no correlation or metadata is inferred from post-projection Q/K.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any

import numpy as np

import generate_boundary_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
SCALELLM_ROOT = EXPERIMENT_ROOT.parent
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
)
DEFAULT_CAPTURE = MODULE / "data_trace_projection_input"
DEFAULT_OUTPUT = MODULE / "data_trace"
CAPTURE_VERIFIER = HERE / "verify_trace_projection_inputs.py"
PRODUCTION_MODEL_DIR = SCALELLM_ROOT / "model"
if str(PRODUCTION_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCTION_MODEL_DIR))

import export_scalellm_llama31_artifacts as exporter  # noqa: E402
import fixbit_v2  # noqa: E402

MODULAR_MODEL = EXPERIMENT_ROOT / "tools" / "model"
if str(MODULAR_MODEL) not in sys.path:
    sys.path.insert(0, str(MODULAR_MODEL))
import minmax_a8  # noqa: E402


GROUPS = 128
GROUP_SIZE = 32
MASK21 = (1 << 21) - 1
MASK24 = (1 << 24) - 1
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
COORDINATES = (
    (0, 0, "q", 0, 0, 0),
    (0, 0, "k", 64, 4, 17),
    (0, 15, "q", 31, 17, 31),
    (0, 15, "k", 63, 5, 47),
    (0, 31, "q", 127, 31, 63),
    (0, 31, "k", 95, 7, 1),
    (1, 0, "q", 1, 8, 8),
    (1, 0, "k", 111, 2, 24),
    (1, 15, "q", 15, 23, 40),
    (1, 15, "k", 127, 6, 56),
    (1, 31, "q", 63, 16, 15),
    (1, 31, "k", 31, 3, 32),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
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


def bf16_bits_to_fp32(array: np.ndarray) -> np.ndarray:
    if array.dtype != np.uint16:
        raise AssertionError("expected raw BF16 uint16")
    return (np.asarray(array, dtype=np.uint32) << np.uint32(16)).view(
        np.float32)


def load_array(path: Path, record: dict[str, Any]) -> np.ndarray:
    if (path.stat().st_size != record["bytes"] or
            sha256_file(path) != record["file_sha256"]):
        raise AssertionError(f"source file mismatch: {path}")
    array = np.load(path, allow_pickle=False)
    if (list(array.shape) != record["shape"] or
            str(array.dtype) != record["storage_dtype"] or
            payload_hash(array) != record["payload_sha256"]):
        raise AssertionError(f"source payload mismatch: {path}")
    return array


def verify_trace(trace_run: Path) -> tuple[Path, dict[str, Any]]:
    trace_run = trace_run.resolve(strict=True)
    if (trace_run / "STATUS").read_text(encoding="ascii").strip() != "PASS":
        raise AssertionError("source trace STATUS is not PASS")
    if int((trace_run / "exit_status.txt").read_text().strip()) != 0:
        raise AssertionError("source trace exit status is nonzero")
    trace_dir = trace_run / "trace"
    manifest_path = trace_dir / "manifest.json"
    expected = (trace_dir / "MANIFEST_SHA256").read_text(
        encoding="ascii").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("source trace manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "scalellm_modular_llama_trace_v1":
        raise AssertionError("source trace schema mismatch")
    return trace_dir, manifest


def verify_capture(capture: Path) -> dict[str, Any]:
    capture = capture.resolve(strict=True)
    subprocess.run([
        sys.executable, str(CAPTURE_VERIFIER),
        "--capture-dir", str(capture),
    ], check=True)
    manifest_path = capture / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest


def fp32_bits(value: float | np.floating) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def pack_pair(y0: int, y1: int) -> int:
    return ((y1 & MASK24) << 24) | (y0 & MASK24)


def write_mem(path: Path, values: list[int], digits: int) -> dict[str, Any]:
    mask = (1 << (4 * digits)) - 1
    path.write_text(
        "".join(f"{value & mask:0{digits}x}\n" for value in values),
        encoding="ascii")
    return {
        "records": len(values),
        "hex_digits": digits,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def pair_metrics(
        actual: list[tuple[int, int]], reference: list[tuple[float, float]],
) -> dict[str, float]:
    return base.metrics(actual, reference)


def fp16_rope_nonfinite_count(
        x0_fp32: np.float32, x1_fp32: np.float32,
        cos_s18: int, sin_s18: int,
) -> int:
    x0 = base.fp16_ftz(x0_fp32)
    x1 = base.fp16_ftz(x1_fp32)
    cos_value = base.fp16_ftz(base.fp32(cos_s18 / float(1 << 16)))
    sin_value = base.fp16_ftz(base.fp32(sin_s18 / float(1 << 16)))
    products = (
        base.fp16_mul(x0, cos_value),
        base.fp16_mul(x1, sin_value),
        base.fp16_mul(x0, sin_value),
        base.fp16_mul(x1, cos_value),
    )
    outputs = (
        base.fp16_sub(products[0], products[1]),
        base.fp16_add(products[2], products[3]),
    )
    return sum(not np.isfinite(value) for value in (*products, *outputs))


def main() -> None:
    # Real S21 correlations can exceed FP16's finite range.  The event counts
    # below preserve that negative evidence, so expected overflows/NaNs do not
    # need to emit thousands of NumPy runtime warnings as well.
    np.seterr(over="ignore", invalid="ignore")
    args = parse_args()
    trace_run = args.trace_run.resolve(strict=True)
    trace_dir, trace_manifest = verify_trace(trace_run)
    capture_dir = args.capture_dir.resolve(strict=True)
    capture_manifest = verify_capture(capture_dir)
    if (capture_manifest["source_trace_manifest_sha256"] !=
            sha256_file(trace_dir / "manifest.json")):
        raise AssertionError("capture and frozen trace do not match")
    model_dir = Path(args.model_dir or capture_manifest["checkpoint"]).resolve(
        strict=True)
    if model_dir != Path(capture_manifest["checkpoint"]).resolve(strict=True):
        raise AssertionError("model-dir must match the verified capture")
    checkpoint = exporter.LlamaCheckpoint(model_dir)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    capture_records = {
        (record["sample"], record["layer"]): record
        for record in capture_manifest["files"]
    }
    trace_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }
    activation_cache: dict[tuple[int, int], np.ndarray] = {}
    frozen_cache: dict[tuple[int, int, str], np.ndarray] = {}
    source_tensors: dict[str, dict[str, Any]] = {}

    correlations: list[int] = []
    sc_meta: list[int] = []
    fp16_scale_words: list[int] = []
    fp32_scale_words: list[int] = []
    coefficients: list[int] = []
    expected_sc: list[tuple[int, int]] = []
    expected_fp16: list[tuple[int, int]] = []
    expected_fp32: list[tuple[int, int]] = []
    reference_common: list[tuple[float, float]] = []
    reference_checkpoint: list[tuple[float, float]] = []
    reference_frozen: list[tuple[float, float]] = []
    provenance: list[dict[str, Any]] = []

    input_s24_saturation = 0
    hadamard_saturation = 0
    activation_clip_lanes = 0
    activation_zero_scale_groups = 0
    weight_preclamp_lanes = 0
    fp16_zero_contributions = 0
    fp16_correlation_nonfinite = 0
    fp16_scale_underflow_inputs = 0
    fp16_contribution_nonfinite = 0
    fp16_final_bank_nonfinite = 0
    fp16_projection_nonfinite = 0
    fp16_rope_nonfinite_intermediates = 0
    fp16_pairs_with_nonfinite = 0
    projection_saturation = {"sc": 0, "fp16": 0, "fp32": 0}
    rope_saturation = {"sc": 0, "fp16": 0, "fp32": 0}
    total_shifts: list[int] = []
    correlation_values: list[int] = []
    inv_freq = exporter.llama3_inv_freq(checkpoint.config)

    for pair_index, (sample, layer, kind, token, head, rope_pair) in enumerate(
            COORDINATES):
        activation_key = (sample, layer)
        if activation_key not in activation_cache:
            record = capture_records[activation_key]
            bits = load_array(capture_dir / record["file"], record)
            activation_cache[activation_key] = bf16_bits_to_fp32(bits)
            source_tensors[f"capture/{record['file']}"] = {
                "role": "attention_input_bf16",
                "sample": sample,
                "layer": layer,
                "file": record["file"],
                "file_sha256": record["file_sha256"],
                "payload_sha256": record["payload_sha256"],
                "shape": record["shape"],
                "storage_dtype": record["storage_dtype"],
            }
        raw_activation = activation_cache[activation_key][token]
        scaled = np.rint(raw_activation.astype(np.float64) * (1 << 16))
        fixed = np.clip(scaled, S24_MIN, S24_MAX).astype(np.int64)
        input_s24_saturation += int(np.count_nonzero(fixed != scaled))

        activations = []
        for group in range(GROUPS):
            source = fixed[group*GROUP_SIZE:(group+1)*GROUP_SIZE]
            transformed = fixbit_v2.hadamard32_normalized(source.tolist())
            hadamard_saturation += transformed.saturation_count
            quantized = minmax_a8.quantize_s27(transformed.values)
            activation_zero_scale_groups += int(quantized.scale_code == 0)
            activation_clip_lanes += sum(
                value < quantized.low or value > quantized.high
                for value in transformed.values)
            activations.append(quantized)

        operation = "q_proj" if kind == "q" else "k_proj"
        heads = 32 if kind == "q" else 8
        row0 = head * 128 + rope_pair
        row1 = row0 + 64
        tensor_name = f"model.layers.{layer}.self_attn.{operation}.weight"
        raw_weights = checkpoint.float32(tensor_name, rows=[row0, row1])
        quantized_weights, weight_codes, weight_shifts = \
            exporter.quantize_folded_rows(raw_weights, 8)
        folded_weights = exporter.fwht32_normalized(
            raw_weights.reshape(2, GROUPS, GROUP_SIZE))
        decoded_weight_scales = np.ldexp(
            weight_codes.astype(np.float64),
            -weight_shifts.astype(np.int64))
        before_clamp = exporter.round_away(
            folded_weights.astype(np.float64) /
            decoded_weight_scales[..., None])
        weight_preclamp_lanes += int(np.count_nonzero(
            (before_clamp < -127) | (before_clamp > 127)))

        angle = float(token) * float(inv_freq[rope_pair])
        cos_s18 = int(np.clip(
            exporter.round_away(np.asarray([math.cos(angle) * 65536.0]))[0],
            -65536, 65536))
        sin_s18 = int(np.clip(
            exporter.round_away(np.asarray([math.sin(angle) * 65536.0]))[0],
            -65536, 65536))
        coefficients.append(
            ((sin_s18 & ((1 << 18) - 1)) << 18) |
            (cos_s18 & ((1 << 18) - 1)))

        sc_accum = [0, 0]
        fp16_banks = [[base.fp32(0.0) for _ in range(6)] for _ in range(2)]
        fp32_banks = [[base.fp32(0.0) for _ in range(6)] for _ in range(2)]
        common_accum = [0.0, 0.0]

        for group, activation in enumerate(activations):
            centered = (
                np.asarray(activation.values, dtype=np.int64) -
                activation.zero_point)
            corr = [int(np.dot(
                centered,
                quantized_weights[lane, group].astype(np.int64)))
                for lane in range(2)]
            if any(not -(1 << 20) <= value < (1 << 20) for value in corr):
                raise AssertionError("real M03 correlation escaped signed S21")
            correlation_values.extend(corr)
            correlations.append(
                ((corr[1] & MASK21) << 21) | (corr[0] & MASK21))

            act_code = activation.scale_code
            act_shift = activation.scale_shift
            weight0_code = int(weight_codes[0, group])
            weight1_code = int(weight_codes[1, group])
            weight0_shift = int(weight_shifts[0, group])
            weight1_shift = int(weight_shifts[1, group])
            if min(act_code, weight0_code, weight1_code) <= 0:
                raise AssertionError("real M03 has a zero native scale")
            shift0 = act_shift + weight0_shift
            shift1 = act_shift + weight1_shift
            if not 26 <= shift0 <= 47 or not 26 <= shift1 <= 47:
                raise AssertionError("real M03 total shift outside [26,47]")
            total_shifts.extend((shift0, shift1))
            sc_meta.append(
                act_code | (act_shift << 8) |
                (weight0_code << 14) | (weight0_shift << 22) |
                (weight1_code << 28) | (weight1_shift << 36))

            act_scale = act_code / float(1 << act_shift)
            weight_scales = (
                weight0_code / float(1 << weight0_shift),
                weight1_code / float(1 << weight1_shift),
            )
            fp16_scale_words.append(
                base.fp16_bits(act_scale) |
                (base.fp16_bits(weight_scales[0]) << 16) |
                (base.fp16_bits(weight_scales[1]) << 32))
            fp32_scale_words.append(
                fp32_bits(act_scale) |
                (fp32_bits(weight_scales[0]) << 32) |
                (fp32_bits(weight_scales[1]) << 64))

            bank = group % 6
            for lane in range(2):
                raw = corr[lane] * act_code * (
                    weight0_code if lane == 0 else weight1_code)
                shift = shift0 if lane == 0 else shift1
                sc_accum[lane] += raw >> (shift - 24)
                common_accum[lane] += (
                    corr[lane] * act_scale * weight_scales[lane])

                corr16 = base.fp16_ftz(base.fp32(corr[lane]))
                act16 = base.fp16_ftz(base.fp32(act_scale))
                weight16 = base.fp16_ftz(base.fp32(weight_scales[lane]))
                fp16_correlation_nonfinite += int(not np.isfinite(corr16))
                fp16_scale_underflow_inputs += int(
                    act_scale != 0.0 and
                    (base.fp16_bits(act16) & 0x7FFF) == 0)
                fp16_scale_underflow_inputs += int(
                    weight_scales[lane] != 0.0 and
                    (base.fp16_bits(weight16) & 0x7FFF) == 0)
                contribution16 = base.fp16_mul(
                    base.fp16_mul(corr16, act16), weight16)
                fp16_contribution_nonfinite += int(
                    not np.isfinite(contribution16))
                fp16_zero_contributions += int(
                    (base.fp16_bits(contribution16) & 0x7FFF) == 0)
                fp16_banks[lane][bank] = base.fp32_add(
                    fp16_banks[lane][bank], base.fp32(contribution16))

                contribution32 = base.fp32(
                    base.fp32(base.fp32(corr[lane]) * base.fp32(act_scale)) *
                    base.fp32(weight_scales[lane]))
                fp32_banks[lane][bank] = base.fp32_add(
                    fp32_banks[lane][bank], contribution32)

        projection_sc = [
            base.round_s42_q24_to_s24_q16(value) for value in sc_accum
        ]
        fp16_projection = [base.reduce_six(values) for values in fp16_banks]
        fp32_projection = [base.reduce_six(values) for values in fp32_banks]
        final_bank_nonfinite = sum(
            not np.isfinite(value)
            for lane_banks in fp16_banks for value in lane_banks)
        projection_nonfinite = sum(
            not np.isfinite(value) for value in fp16_projection)
        fp16_final_bank_nonfinite += final_bank_nonfinite
        fp16_projection_nonfinite += projection_nonfinite
        fp16_pairs_with_nonfinite += int(
            final_bank_nonfinite > 0 or projection_nonfinite > 0)
        for name, values in (
                ("sc", projection_sc),
                ("fp16", [base.fp_to_s24(value) for value in fp16_projection]),
                ("fp32", [base.fp_to_s24(value) for value in fp32_projection])):
            projection_saturation[name] += sum(
                value in (S24_MIN, S24_MAX) for value in values)

        result_sc = base.sc_rope(
            projection_sc[0], projection_sc[1], cos_s18, sin_s18)
        result_fp16 = base.fp16_rope(
            fp16_projection[0], fp16_projection[1], cos_s18, sin_s18)
        fp16_rope_nonfinite_intermediates += fp16_rope_nonfinite_count(
            fp16_projection[0], fp16_projection[1], cos_s18, sin_s18)
        result_fp32 = base.fp32_rope(
            fp32_projection[0], fp32_projection[1], cos_s18, sin_s18)
        expected_sc.append(result_sc)
        expected_fp16.append(result_fp16)
        expected_fp32.append(result_fp32)
        for name, values in (
                ("sc", result_sc), ("fp16", result_fp16),
                ("fp32", result_fp32)):
            rope_saturation[name] += sum(
                value in (S24_MIN, S24_MAX) for value in values)

        cos_value = cos_s18 / float(1 << 16)
        sin_value = sin_s18 / float(1 << 16)
        reference_common.append((
            common_accum[0] * cos_value - common_accum[1] * sin_value,
            common_accum[0] * sin_value + common_accum[1] * cos_value,
        ))
        raw_projection = raw_weights.astype(np.float64) @ \
            raw_activation.astype(np.float64)
        reference_checkpoint.append((
            float(raw_projection[0] * cos_value - raw_projection[1] * sin_value),
            float(raw_projection[0] * sin_value + raw_projection[1] * cos_value),
        ))

        frozen_key = (sample, layer, f"{kind}_post_rope_bf16")
        if frozen_key not in frozen_cache:
            record = trace_records[frozen_key]
            bits = load_array(trace_dir / record["file"], record)
            frozen_cache[frozen_key] = bf16_bits_to_fp32(bits)
            source_tensors[f"trace/{record['file']}"] = {
                "role": f"{kind}_post_rope_bf16_reference",
                "sample": sample,
                "layer": layer,
                "file": record["file"],
                "file_sha256": record["file_sha256"],
                "payload_sha256": record["payload_sha256"],
                "shape": record["shape"],
                "storage_dtype": record["storage_dtype"],
            }
        frozen = frozen_cache[frozen_key][token, head]
        reference_frozen.append((
            float(frozen[rope_pair]), float(frozen[rope_pair + 64])))

        provenance.append({
            "pair": pair_index,
            "sample": sample,
            "layer": layer,
            "kind": kind.upper(),
            "token": token,
            "head": head,
            "rope_pair": rope_pair,
            "weight_tensor": tensor_name,
            "weight_rows": f"{row0},{row1}",
            "capture_tensor": capture_records[activation_key]["file"],
            "frozen_reference_tensor": trace_records[frozen_key]["file"],
            "cos_s18": cos_s18,
            "sin_s18": sin_s18,
        })

    if (len(correlations) != len(COORDINATES) * GROUPS or
            len(expected_sc) != len(COORDINATES)):
        raise AssertionError("real M03 record count mismatch")

    outputs = {
        "correlation_s21_pair.mem": (correlations, 11),
        "scale_meta_sc_u42.mem": (sc_meta, 11),
        "scale_fp16x3.mem": (fp16_scale_words, 12),
        "scale_fp32x3.mem": (fp32_scale_words, 24),
        "coeff_s18_pair.mem": (coefficients, 9),
        "expected_sc_s24_pair.mem": (
            [pack_pair(*pair) for pair in expected_sc], 12),
        "expected_fp16_s24_pair.mem": (
            [pack_pair(*pair) for pair in expected_fp16], 12),
        "expected_fp32_s24_pair.mem": (
            [pack_pair(*pair) for pair in expected_fp32], 12),
    }
    files = {
        name: write_mem(output / name, values, digits)
        for name, (values, digits) in outputs.items()
    }
    coordinate_path = output / "trace_pairs.csv"
    with coordinate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(provenance[0]))
        writer.writeheader()
        writer.writerows(provenance)
    files[coordinate_path.name] = {
        "records": len(provenance),
        "hex_digits": 0,
        "bytes": coordinate_path.stat().st_size,
        "sha256": sha256_file(coordinate_path),
    }

    generator = Path(__file__).resolve()
    base_model = Path(base.__file__).resolve()
    exporter_model = Path(exporter.__file__).resolve()
    fixed_model = Path(fixbit_v2.__file__).resolve()
    manifest = {
        "schema": "scalellm_modular_m03_projection_rope_real_trace_v1",
        "pairs": len(COORDINATES),
        "groups_per_pair": GROUPS,
        "transactions": len(COORDINATES) * GROUPS,
        "coordinates": [dict(row) for row in provenance],
        "common_input": (
            "two signed S21 correlations from production quantized A8/W8 "
            "group32 dot, activation/weight native scale metadata, and S18 "
            "RoPE coefficients"),
        "source_trace_run": str(trace_run),
        "source_trace_manifest_sha256": sha256_file(
            trace_dir / "manifest.json"),
        "projection_input_capture": str(capture_dir),
        "projection_input_manifest_sha256": sha256_file(
            capture_dir / "manifest.json"),
        "checkpoint": str(model_dir),
        "checkpoint_index_sha256": capture_manifest[
            "checkpoint_index_sha256"],
        "checkpoint_shards": capture_manifest["checkpoint_shards"],
        "source_tensors": [source_tensors[name]
                           for name in sorted(source_tensors)],
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "input_s24_saturation": input_s24_saturation,
        "hadamard_saturation": hadamard_saturation,
        "activation_clip_lanes": activation_clip_lanes,
        "pre_quant_clip_lanes": activation_clip_lanes,
        "activation_zero_scale_groups": activation_zero_scale_groups,
        "weight_preclamp_lanes": weight_preclamp_lanes,
        "fp16_zero_group_contributions": fp16_zero_contributions,
        "fp16_numeric_events": {
            "correlation_nonfinite_after_s21_to_fp16":
                fp16_correlation_nonfinite,
            "nonzero_scale_underflow_inputs": fp16_scale_underflow_inputs,
            "nonfinite_group_contributions": fp16_contribution_nonfinite,
            "nonfinite_final_accumulator_banks": fp16_final_bank_nonfinite,
            "nonfinite_projection_elements": fp16_projection_nonfinite,
            "nonfinite_rope_intermediates":
                fp16_rope_nonfinite_intermediates,
            "pairs_with_nonfinite": fp16_pairs_with_nonfinite,
        },
        "correlation_min": min(correlation_values),
        "correlation_max": max(correlation_values),
        "total_shift_min": min(total_shifts),
        "total_shift_max": max(total_shifts),
        "projection_saturation": projection_saturation,
        "rope_output_saturation": rope_saturation,
        "accuracy_vs_common_quantized_fp64": {
            "sc": pair_metrics(expected_sc, reference_common),
            "fp16": pair_metrics(expected_fp16, reference_common),
            "fp32": pair_metrics(expected_fp32, reference_common),
        },
        "accuracy_vs_captured_input_checkpoint_fp64": {
            "sc": pair_metrics(expected_sc, reference_checkpoint),
            "fp16": pair_metrics(expected_fp16, reference_checkpoint),
            "fp32": pair_metrics(expected_fp32, reference_checkpoint),
        },
        "accuracy_vs_original_frozen_bf16": {
            "sc": pair_metrics(expected_sc, reference_frozen),
            "fp16": pair_metrics(expected_fp16, reference_frozen),
            "fp32": pair_metrics(expected_fp32, reference_frozen),
        },
        "files": dict(sorted(files.items())),
        "generator_sha256": sha256_file(generator),
        "boundary_model": str(base_model),
        "boundary_model_sha256": sha256_file(base_model),
        "production_exporter": str(exporter_model),
        "production_exporter_sha256": sha256_file(exporter_model),
        "production_fixed_model": str(fixed_model),
        "production_fixed_model_sha256": sha256_file(fixed_model),
        "minmax_reference": str(Path(minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(Path(minmax_a8.__file__)),
        "capture_verifier": str(CAPTURE_VERIFIER.resolve()),
        "capture_verifier_sha256": sha256_file(CAPTURE_VERIFIER),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M03_TRACE_VECTOR_PASS "
        f"files={len(files)+1} pairs={len(COORDINATES)} "
        f"transactions={len(COORDINATES)*GROUPS} "
        f"source_tensors={len(source_tensors)} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
