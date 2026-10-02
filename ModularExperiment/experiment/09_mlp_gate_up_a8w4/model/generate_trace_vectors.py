#!/usr/bin/env python3
"""Generate real Gate/Up A8W4 tiles from captured pre-MLP activations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np

import generate_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
SCALELLM_ROOT = EXPERIMENT_ROOT.parent
PRODUCTION_MODEL_DIR = SCALELLM_ROOT / "model"
if str(PRODUCTION_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCTION_MODEL_DIR))
import export_scalellm_llama31_artifacts as exporter  # noqa: E402
import fixbit_v2  # noqa: E402

MODULAR_MODEL = EXPERIMENT_ROOT / "tools" / "model"
if str(MODULAR_MODEL) not in sys.path:
    sys.path.insert(0, str(MODULAR_MODEL))
import minmax_a8  # noqa: E402


DEFAULT_CAPTURE = (
    EXPERIMENT_ROOT / "experiment/08_mlp_input_hadamard_a8" /
    "data_trace_mlp_input"
)
DEFAULT_OUTPUT = MODULE / "data_trace"
CAPTURE_VERIFIER = (
    EXPERIMENT_ROOT / "experiment/08_mlp_input_hadamard_a8/model" /
    "verify_trace_mlp_inputs.py"
)
ROWS = 16
COLS = 12
GROUPS = 128
LANES = 32
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
ROW_COORDINATES = (
    (0, 0), (0, 15), (0, 31), (0, 47),
    (0, 63), (0, 79), (0, 95), (0, 127),
    (1, 1), (1, 16), (1, 32), (1, 48),
    (1, 64), (1, 80), (1, 96), (1, 111),
)
TILES = (
    (0, "gate_proj", 0, 12),
    (0, "up_proj", 2048, 12),
    (15, "gate_proj", 4096, 12),
    (15, "up_proj", 7168, 12),
    (31, "gate_proj", 10240, 12),
    (31, "up_proj", 14332, 4),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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


def load_capture(
        capture: Path,
) -> tuple[dict[str, Any], dict[tuple[int, int], np.ndarray]]:
    manifest_path = capture / "manifest.json"
    expected = (capture / "MANIFEST_SHA256").read_text(
        encoding="ascii").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("M09 MLP-input capture manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m08_mlp_input_trace_v1" or
            manifest.get("samples") != [0, 1] or
            manifest.get("layers") != [0, 15, 31]):
        raise AssertionError("M09 MLP-input capture contract mismatch")
    arrays: dict[tuple[int, int], np.ndarray] = {}
    for record in manifest["files"]:
        path = capture / record["file"]
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["file_sha256"]):
            raise AssertionError(f"M09 capture file changed: {path}")
        bits = np.load(path, allow_pickle=False)
        if (bits.shape != (128, 4096) or bits.dtype != np.uint16 or
                payload_hash(bits) != record["payload_sha256"]):
            raise AssertionError(f"M09 capture payload changed: {path}")
        arrays[(record["sample"], record["layer"])] = \
            bf16_bits_to_fp32(bits)
    if len(arrays) != 6:
        raise AssertionError("M09 capture tensor count mismatch")
    return manifest, arrays


def write_mem(path: Path, values: list[int], digits: int) -> dict[str, Any]:
    mask = (1 << (digits * 4)) - 1
    path.write_text(
        "".join(f"{int(value) & mask:0{digits}x}\n" for value in values),
        encoding="ascii")
    return {
        "records": len(values),
        "hex_digits": digits,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    np.seterr(over="ignore", invalid="ignore")
    args = parse_args()
    capture_dir = args.capture_dir.resolve(strict=True)
    subprocess.run([
        sys.executable, str(CAPTURE_VERIFIER),
        "--capture-dir", str(capture_dir),
    ], check=True)
    capture_manifest, arrays = load_capture(capture_dir)
    model_dir = Path(args.model_dir or capture_manifest["checkpoint"]).resolve(
        strict=True)
    if model_dir != Path(capture_manifest["checkpoint"]).resolve(strict=True):
        raise AssertionError("model-dir must match the verified capture")
    checkpoint = exporter.LlamaCheckpoint(model_dir)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    activation_words: list[int] = []
    weight_words: list[int] = []
    activation_sc_words: list[int] = []
    weight_sc_words: list[int] = []
    activation_fp16_words: list[int] = []
    weight_fp16_words: list[int] = []
    activation_fp32_words: list[int] = []
    weight_fp32_words: list[int] = []
    mask_words: list[int] = []
    expected_sc_words: list[int] = []
    expected_fp16_words: list[int] = []
    expected_fp32_words: list[int] = []
    reference_common: list[float] = []
    reference_checkpoint: list[float] = []
    reconstructed_sc: list[float] = []
    reconstructed_fp16: list[float] = []
    reconstructed_fp32: list[float] = []
    provenance: list[dict[str, Any]] = []
    weight_sources: list[dict[str, Any]] = []

    input_s24_saturation = 0
    hadamard_saturation = 0
    activation_clip_lanes = 0
    activation_zero_scale_groups = 0
    weight_preclamp_lanes = 0
    fp16_zero_contributions = 0
    fp16_nonfinite_contributions = 0
    correlation_values: list[int] = []
    total_shifts: list[int] = []
    output_saturation = {"sc": 0, "fp16": 0, "fp32": 0}

    for tile, (layer, operation, start_column, valid_columns) in enumerate(
            TILES):
        raw_rows = np.stack([
            arrays[(sample, layer)][token]
            for sample, token in ROW_COORDINATES
        ])
        scaled = np.rint(raw_rows.astype(np.float64) * (1 << 16))
        fixed_rows = np.clip(scaled, S24_MIN, S24_MAX).astype(np.int64)
        input_s24_saturation += int(np.count_nonzero(fixed_rows != scaled))

        quantized_activations = []
        for row in range(ROWS):
            groups = []
            for group in range(GROUPS):
                source = fixed_rows[
                    row, group*LANES:(group+1)*LANES].tolist()
                transformed = fixbit_v2.hadamard32_normalized(source)
                hadamard_saturation += transformed.saturation_count
                quantized = minmax_a8.quantize_s27(transformed.values)
                activation_zero_scale_groups += int(
                    quantized.scale_code == 0)
                activation_clip_lanes += sum(
                    value < quantized.low or
                    value > quantized.high
                    for value in transformed.values)
                groups.append(quantized)
            quantized_activations.append(groups)

        tensor_name = f"model.layers.{layer}.mlp.{operation}.weight"
        selected_rows = list(range(start_column, start_column + valid_columns))
        raw_weights = checkpoint.float32(tensor_name, rows=selected_rows)
        quantized_weights, weight_codes, weight_shifts = \
            exporter.quantize_folded_rows(raw_weights, 4)
        folded_weights = exporter.fwht32_normalized(
            raw_weights.reshape(valid_columns, GROUPS, LANES))
        decoded_weight_scales = np.ldexp(
            weight_codes.astype(np.float64),
            -weight_shifts.astype(np.int64))
        before_clamp = exporter.round_away(
            folded_weights.astype(np.float64) /
            decoded_weight_scales[..., None])
        weight_preclamp_lanes += int(np.count_nonzero(
            (before_clamp < -8) | (before_clamp > 7)))
        weight_sources.append({
            "tile": tile,
            "tensor": tensor_name,
            "rows": selected_rows,
            "raw_payload_sha256": payload_hash(raw_weights),
        })

        sc_acc = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        fp16_terms = [[[] for _ in range(COLS)] for _ in range(ROWS)]
        fp32_terms = [[[] for _ in range(COLS)] for _ in range(ROWS)]
        real_acc = [[0.0 for _ in range(COLS)] for _ in range(ROWS)]
        column_mask = (1 << valid_columns) - 1

        for group in range(GROUPS):
            centered_rows: list[list[int]] = []
            act_codes: list[int] = []
            act_shifts: list[int] = []
            for row in range(ROWS):
                activation = quantized_activations[row][group]
                centered_rows.append([
                    int(value) - activation.zero_point
                    for value in activation.values
                ])
                act_codes.append(activation.scale_code)
                act_shifts.append(activation.scale_shift)

            weight_rows: list[list[int]] = []
            weight_code_row: list[int] = []
            weight_shift_row: list[int] = []
            for column in range(COLS):
                if column < valid_columns:
                    weight_rows.append(
                        quantized_weights[column, group].astype(
                            np.int64).tolist())
                    weight_code_row.append(int(weight_codes[column, group]))
                    weight_shift_row.append(int(weight_shifts[column, group]))
                else:
                    weight_rows.append([0] * LANES)
                    weight_code_row.append(0)
                    weight_shift_row.append(0)

            activation_words.append(base.pack(
                [value for row in centered_rows for value in row], 9))
            weight_words.append(base.pack(
                [value for row in weight_rows for value in row], 4))
            activation_sc_words.append(
                base.pack(act_codes, 8) |
                (base.pack(act_shifts, 6) << (ROWS * 8)))
            weight_sc_words.append(
                base.pack(weight_code_row, 8) |
                (base.pack(weight_shift_row, 6) << (COLS * 8)))

            act_scale_real = [
                code / float(1 << shift) if code else 0.0
                for code, shift in zip(act_codes, act_shifts, strict=True)
            ]
            weight_scale_real = [
                code / float(1 << shift) if code else 0.0
                for code, shift in zip(
                    weight_code_row, weight_shift_row, strict=True)
            ]
            act_scale16 = [base.fp16_ftz(value) for value in act_scale_real]
            weight_scale16 = [
                base.fp16_ftz(value) for value in weight_scale_real
            ]
            act_scale32 = [np.float32(value) for value in act_scale_real]
            weight_scale32 = [
                np.float32(value) for value in weight_scale_real
            ]
            activation_fp16_words.append(base.pack(
                [base.fp16_bits(value) for value in act_scale16], 16))
            weight_fp16_words.append(base.pack(
                [base.fp16_bits(value) for value in weight_scale16], 16))
            activation_fp32_words.append(base.pack(
                [base.fp32_bits(value) for value in act_scale32], 32))
            weight_fp32_words.append(base.pack(
                [base.fp32_bits(value) for value in weight_scale32], 32))
            mask_words.append(column_mask)

            for row in range(ROWS):
                for column in range(COLS):
                    corr = sum(
                        activation * weight
                        for activation, weight in zip(
                            centered_rows[row], weight_rows[column],
                            strict=True))
                    correlation_values.append(corr)
                    if column >= valid_columns:
                        if corr != 0:
                            raise AssertionError("masked M09 correlation nonzero")
                        fp16_terms[row][column].append(np.float16(0.0))
                        fp32_terms[row][column].append(np.float32(0.0))
                        continue
                    total_shift = (
                        act_shifts[row] + weight_shift_row[column])
                    if not 26 <= total_shift <= 47:
                        raise AssertionError(
                            "real M09 total shift outside [26,47]")
                    total_shifts.append(total_shift)
                    raw = (corr * act_codes[row] *
                           weight_code_row[column])
                    sc_acc[row][column] += raw >> (total_shift - 24)
                    real_term = (corr * act_scale_real[row] *
                                 weight_scale_real[column])
                    real_acc[row][column] += real_term

                    corr16 = base.fp16_ftz(np.float32(corr))
                    term16 = base.fp16_mul_ip(
                        base.fp16_mul_ip(corr16, act_scale16[row]),
                        weight_scale16[column])
                    fp16_nonfinite_contributions += int(
                        not np.isfinite(term16))
                    fp16_zero_contributions += int(
                        (base.fp16_bits(term16) & 0x7FFF) == 0)
                    fp16_terms[row][column].append(term16)
                    term32 = np.float32(
                        np.float32(
                            np.float32(corr) * act_scale32[row]) *
                        weight_scale32[column])
                    fp32_terms[row][column].append(term32)

        expected_sc: list[int] = []
        expected_fp16: list[int] = []
        expected_fp32: list[int] = []
        for row in range(ROWS):
            for column in range(COLS):
                if column >= valid_columns:
                    sc_out = f16_out = f32_out = 0
                else:
                    sc_out = base.sc_round_sat(sc_acc[row][column])
                    sum16 = base.fp16_accum_result_ip(sum(
                        float(value)
                        for value in fp16_terms[row][column]))
                    sum32 = base.fp32_accum_result_ip(sum(
                        float(value)
                        for value in fp32_terms[row][column]))
                    f16_out = base.round_sat_s24(float(sum16))
                    f32_out = base.round_sat_s24(float(sum32))
                    reference_common.append(real_acc[row][column])
                    reconstructed_sc.append(sc_out / float(1 << 16))
                    reconstructed_fp16.append(f16_out / float(1 << 16))
                    reconstructed_fp32.append(f32_out / float(1 << 16))
                expected_sc.append(sc_out)
                expected_fp16.append(f16_out)
                expected_fp32.append(f32_out)
                output_saturation["sc"] += int(
                    sc_out in (S24_MIN, S24_MAX))
                output_saturation["fp16"] += int(
                    f16_out in (S24_MIN, S24_MAX))
                output_saturation["fp32"] += int(
                    f32_out in (S24_MIN, S24_MAX))

        expected_sc_words.append(base.pack(expected_sc, 24))
        expected_fp16_words.append(base.pack(expected_fp16, 24))
        expected_fp32_words.append(base.pack(expected_fp32, 24))

        checkpoint_values = raw_weights.astype(np.float64) @ \
            raw_rows.astype(np.float64).T
        reference_checkpoint.extend(
            checkpoint_values.T.reshape(-1).tolist())
        provenance.append({
            "tile": tile,
            "layer": layer,
            "operation": operation,
            "start_column": start_column,
            "valid_columns": valid_columns,
            "column_mask": f"0x{column_mask:03x}",
            "weight_tensor": tensor_name,
        })

    outputs = {
        "activation_s9x16x32.mem": (activation_words, 1152),
        "weights_s4x12x32.mem": (weight_words, 384),
        "activation_meta_sc_u224.mem": (activation_sc_words, 56),
        "weight_meta_sc_u168.mem": (weight_sc_words, 42),
        "activation_scale_fp16x16.mem": (activation_fp16_words, 64),
        "weight_scale_fp16x12.mem": (weight_fp16_words, 48),
        "activation_scale_fp32x16.mem": (activation_fp32_words, 128),
        "weight_scale_fp32x12.mem": (weight_fp32_words, 96),
        "column_mask_u12.mem": (mask_words, 3),
        "expected_sc_s24x16x12.mem": (expected_sc_words, 1152),
        "expected_fp16_s24x16x12.mem": (expected_fp16_words, 1152),
        "expected_fp32_s24x16x12.mem": (expected_fp32_words, 1152),
    }
    files = {
        name: write_mem(output / name, values, digits)
        for name, (values, digits) in outputs.items()
    }
    coordinates_path = output / "trace_tiles.csv"
    with coordinates_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(provenance[0]))
        writer.writeheader()
        writer.writerows(provenance)
    files[coordinates_path.name] = {
        "records": len(provenance),
        "hex_digits": 0,
        "bytes": coordinates_path.stat().st_size,
        "sha256": sha256_file(coordinates_path),
    }

    generator = Path(__file__).resolve()
    base_model = Path(base.__file__).resolve()
    exporter_model = Path(exporter.__file__).resolve()
    fixed_model = Path(fixbit_v2.__file__).resolve()
    manifest = {
        "schema": "scalellm_modular_m09_gate_up_real_trace_v1",
        "rows": ROWS,
        "columns": COLS,
        "groups_per_tile": GROUPS,
        "group_size": LANES,
        "tiles": len(TILES),
        "transactions": len(TILES) * GROUPS,
        "valid_outputs": sum(item[3] for item in TILES) * ROWS,
        "row_coordinates": [
            {"row": row, "sample": sample, "token": token}
            for row, (sample, token) in enumerate(ROW_COORDINATES)
        ],
        "tile_coordinates": provenance,
        "comparison_boundary": (
            "common centered S9 activation and S4 folded-weight group32 "
            "payload; SC code/shift recovery versus FP16/FP32 decoded-scale "
            "application and rate-one accumulation"),
        "mlp_input_capture": str(capture_dir),
        "mlp_input_manifest_sha256": sha256_file(
            capture_dir / "manifest.json"),
        "checkpoint": str(model_dir),
        "checkpoint_index_sha256": capture_manifest[
            "checkpoint_index_sha256"],
        "checkpoint_shards": capture_manifest["checkpoint_shards"],
        "source_tensors": capture_manifest["files"],
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "weight_sources": weight_sources,
        "input_s24_saturation": input_s24_saturation,
        "hadamard_saturation": hadamard_saturation,
        "activation_clip_lanes": activation_clip_lanes,
        "pre_quant_clip_lanes": activation_clip_lanes,
        "activation_zero_scale_groups": activation_zero_scale_groups,
        "weight_preclamp_lanes": weight_preclamp_lanes,
        "correlation_min": min(correlation_values),
        "correlation_max": max(correlation_values),
        "total_shift_min": min(total_shifts),
        "total_shift_max": max(total_shifts),
        "fp16_zero_contributions": fp16_zero_contributions,
        "fp16_nonfinite_contributions": fp16_nonfinite_contributions,
        "output_saturation": output_saturation,
        "accuracy_vs_common_quantized_fp64": {
            "sc": base.metrics(reference_common, reconstructed_sc),
            "fp16": base.metrics(reference_common, reconstructed_fp16),
            "fp32": base.metrics(reference_common, reconstructed_fp32),
        },
        "accuracy_vs_captured_input_checkpoint_fp64": {
            "sc": base.metrics(reference_checkpoint, reconstructed_sc),
            "fp16": base.metrics(reference_checkpoint, reconstructed_fp16),
            "fp32": base.metrics(reference_checkpoint, reconstructed_fp32),
        },
        "files": dict(sorted(files.items())),
        "generator_sha256": sha256_file(generator),
        "base_model": str(base_model),
        "base_model_sha256": sha256_file(base_model),
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
        "M09_TRACE_VECTOR_PASS "
        f"files={len(files)+1} tiles={len(TILES)} "
        f"transactions={len(TILES)*GROUPS} valid_outputs="
        f"{sum(item[3] for item in TILES)*ROWS} "
        f"source_tensors={len(capture_manifest['files'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
