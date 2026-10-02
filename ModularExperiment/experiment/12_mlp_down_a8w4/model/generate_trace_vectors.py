#!/usr/bin/env python3
"""Build full-shape M12 Down workloads from frozen Llama trace/checkpoint data.

Each selected layer is one independent 16-row hardware replay.  Activations
come from the captured BF16 ``down_proj`` pre-hook tensor.  We run the fixed-
point Hadamard followed by raw-Min/Max A8, then keep its centered S9
payload and decoded ScaleCode scale common across SC, FP16, and FP32.  This
isolates the downstream scale representation/application cost without charging
the M11 producer a second time.

Weights come from the matching checkpoint layer and are transformed and
quantized with the production V5 artifact exporter.  In particular, W4 uses
group-32 normalized folded weights, max-abs/7 scaling, ScaleCode U8/shift6,
and signed S4 rounding against the *decoded* ScaleCode scale.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Iterable

import numpy as np

import generate_vectors as base


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
SCALELLM_ROOT = EXPERIMENT_ROOT.parent
DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
)
DEFAULT_OUTPUT = MODULE / "data_trace"
PRODUCTION_MODEL_DIR = SCALELLM_ROOT / "model"
if str(PRODUCTION_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCTION_MODEL_DIR))

import export_scalellm_llama31_artifacts as exporter  # noqa: E402
import mlp_fixed  # noqa: E402

MODULAR_MODEL = EXPERIMENT_ROOT / "tools" / "model"
if str(MODULAR_MODEL) not in sys.path:
    sys.path.insert(0, str(MODULAR_MODEL))
import minmax_a8  # noqa: E402


SAMPLES = (0, 1)
LAYERS = (0, 15, 31)
TOKENS = (0, 1, 15, 31, 63, 95, 111, 127)
ROWS = len(SAMPLES) * len(TOKENS)
GROUPS = 448
TILES = 342
COLS = 12
K = 32
INTERMEDIATE = 14336
HIDDEN = 4096
TRANSACTIONS = GROUPS * TILES
S32_SCALE = 1 << 16
S32_MIN = -(1 << 31)
S32_MAX = (1 << 31) - 1
S36_MIN = -(1 << 35)
S36_MAX = (1 << 35) - 1
S45_MIN = -(1 << 44)
S45_MAX = (1 << 44) - 1


def parse_layers(text: str) -> tuple[int, ...]:
    try:
        values = tuple(int(value) for value in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("layers must be comma-separated ints") from exc
    if not values or len(set(values)) != len(values) or any(
            value not in LAYERS for value in values):
        raise argparse.ArgumentTypeError(
            f"layers must be a unique subset of {','.join(map(str, LAYERS))}")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--layers", type=parse_layers, default=LAYERS)
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
        raise AssertionError(f"expected uint16 BF16 storage, got {array.dtype}")
    return (np.asarray(array, dtype=np.uint32) << np.uint32(16)).view(
        np.float32)


def metrics(reference: np.ndarray, reconstructed: np.ndarray) -> dict[str, float]:
    ref = np.asarray(reference, dtype=np.float64).reshape(-1)
    got = np.asarray(reconstructed, dtype=np.float64).reshape(-1)
    error = got - ref
    denominator = float(np.linalg.norm(ref) * np.linalg.norm(got))
    return {
        "max_abs": float(np.max(np.abs(error))),
        "mean_abs": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "cosine": float(np.dot(ref, got) / denominator)
        if denominator else 1.0,
    }


class StreamingMetrics:
    def __init__(self) -> None:
        self.count = 0
        self.max_abs = 0.0
        self.sum_abs = 0.0
        self.sum_square = 0.0
        self.dot = 0.0
        self.ref_square = 0.0
        self.got_square = 0.0

    def update(self, reference: np.ndarray, reconstructed: np.ndarray) -> None:
        ref = np.asarray(reference, dtype=np.float64).reshape(-1)
        got = np.asarray(reconstructed, dtype=np.float64).reshape(-1)
        if ref.shape != got.shape or not np.all(np.isfinite(ref)) or not np.all(
                np.isfinite(got)):
            raise AssertionError("streaming metric received invalid arrays")
        error = got - ref
        self.count += int(ref.size)
        self.max_abs = max(self.max_abs, float(np.max(np.abs(error))))
        self.sum_abs += float(np.sum(np.abs(error), dtype=np.float64))
        self.sum_square += float(np.sum(error * error, dtype=np.float64))
        self.dot += float(np.sum(ref * got, dtype=np.float64))
        self.ref_square += float(np.sum(ref * ref, dtype=np.float64))
        self.got_square += float(np.sum(got * got, dtype=np.float64))

    def result(self) -> dict[str, float | int]:
        if not self.count:
            raise AssertionError("empty streaming metric")
        denominator = math.sqrt(self.ref_square * self.got_square)
        return {
            "elements": self.count,
            "max_abs": self.max_abs,
            "mean_abs": self.sum_abs / self.count,
            "rmse": math.sqrt(self.sum_square / self.count),
            "cosine": self.dot / denominator if denominator else 1.0,
        }


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
            manifest.get("layers") != list(LAYERS) or
            [sample["sample"] for sample in manifest["samples"]] !=
            list(SAMPLES)):
        raise AssertionError("source trace contract mismatch")
    return trace_dir, manifest


def load_source_tensor(
        trace_dir: Path, record: dict[str, object],
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


def verify_checkpoint(
        model_dir: Path, trace_manifest: dict[str, object],
        layers: tuple[int, ...],
) -> tuple[exporter.LlamaCheckpoint, list[dict[str, object]]]:
    model_dir = model_dir.resolve(strict=True)
    config = model_dir / "config.json"
    index = model_dir / "model.safetensors.index.json"
    if sha256_file(config) != trace_manifest["config_sha256"]:
        raise AssertionError("checkpoint config hash mismatch")
    if sha256_file(index) != trace_manifest["checkpoint_index_sha256"]:
        raise AssertionError("checkpoint index hash mismatch")
    raw_index = json.loads(index.read_text(encoding="utf-8"))
    checkpoint_records = {
        record["name"]: record for record in trace_manifest["checkpoint_files"]
    }
    selected: list[dict[str, object]] = []
    verified_shards: set[str] = set()
    for layer in layers:
        tensor = f"model.layers.{layer}.mlp.down_proj.weight"
        shard = raw_index["weight_map"].get(tensor)
        if not isinstance(shard, str) or shard not in checkpoint_records:
            raise AssertionError(f"checkpoint mapping missing for {tensor}")
        if shard not in verified_shards:
            path = model_dir / shard
            record = checkpoint_records[shard]
            if (path.stat().st_size != record["bytes"] or
                    sha256_file(path) != record["sha256"]):
                raise AssertionError(f"checkpoint shard mismatch: {path}")
            selected.append({
                "name": shard,
                "bytes": int(record["bytes"]),
                "sha256": str(record["sha256"]),
            })
            verified_shards.add(shard)
    return exporter.LlamaCheckpoint(model_dir), selected


def select_rows(
        trace_dir: Path, tensor_records: dict[tuple[int, int, str], dict],
        layer: int,
) -> tuple[np.ndarray, list[dict[str, object]], list[dict[str, object]]]:
    rows: list[np.ndarray] = []
    coordinates: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for sample in SAMPLES:
        record = tensor_records[(sample, layer, "swiglu_down_input_bf16")]
        tensor = load_source_tensor(trace_dir, record)
        if tensor.shape != (128, INTERMEDIATE):
            raise AssertionError("unexpected Down input trace shape")
        sources.append({
            "sample": sample,
            "layer": layer,
            "name": record["name"],
            "file": record["file"],
            "file_sha256": record["file_sha256"],
            "payload_sha256": record["payload_sha256"],
            "shape": record["shape"],
            "storage_dtype": record["storage_dtype"],
        })
        for token in TOKENS:
            row_index = len(rows)
            rows.append(np.asarray(tensor[token], dtype=np.float32))
            coordinates.append({
                "row": row_index, "sample": sample,
                "layer": layer, "token": token,
                "source_tensor": record["file"],
                "source_payload_sha256": record["payload_sha256"],
            })
    output = np.stack(rows)
    if output.shape != (ROWS, INTERMEDIATE) or not np.all(np.isfinite(output)):
        raise AssertionError("selected Down rows are invalid")
    return output, coordinates, sources


def build_activation_payload(raw_rows: np.ndarray) -> tuple[dict[str, np.ndarray], dict]:
    scaled = np.rint(raw_rows.astype(np.float64) * S32_SCALE)
    fixed = np.clip(scaled, S32_MIN, S32_MAX).astype(np.int64)
    input_saturation = int(np.count_nonzero(fixed != scaled))
    centered = np.empty((GROUPS, ROWS, K), dtype=np.int16)
    codes = np.empty((GROUPS, ROWS), dtype=np.uint8)
    shifts = np.empty((GROUPS, ROWS), dtype=np.uint8)
    transformed = np.empty((GROUPS, ROWS, K), dtype=np.int64)
    hadamard_saturation = 0
    scale_format_overflow_rows = 0
    for group in range(GROUPS):
        for row in range(ROWS):
            source = fixed[row, group*K:(group+1)*K].tolist()
            hadamard = mlp_fixed.hadamard32_product_normalized(source)
            quantized = minmax_a8.quantize_s35(hadamard.values)
            centered[group, row] = np.asarray(
                quantized.values, dtype=np.int16) - quantized.zero_point
            codes[group, row] = quantized.scale_code
            shifts[group, row] = quantized.scale_shift
            transformed[group, row] = hadamard.values
            hadamard_saturation += hadamard.saturation_count
            scale_format_overflow_rows += int(
                quantized.scale_format_overflow)
    decoded = np.ldexp(
        codes.astype(np.float64), -shifts.astype(np.int16))
    reconstructed = centered.astype(np.float64) * decoded[:, :, None]
    raw_hadamard = exporter.fwht32_normalized(
        raw_rows.reshape(ROWS, GROUPS, K)).transpose(1, 0, 2)
    input_reconstructed = fixed.astype(np.float64) / S32_SCALE
    result = {
        "centered": centered,
        "codes": codes,
        "shifts": shifts,
        "decoded": decoded,
        "fixed": fixed,
        "transformed": transformed,
    }
    stats = {
        "input_saturation_count": input_saturation,
        "hadamard_saturation_count": hadamard_saturation,
        "scale_format_overflow_rows": scale_format_overflow_rows,
        "scale_code_min": int(codes.min()),
        "scale_code_max": int(codes.max()),
        "scale_shift_min": int(shifts.min()),
        "scale_shift_max": int(shifts.max()),
        "input_s32_vs_raw_bf16": metrics(raw_rows, input_reconstructed),
        "reconstructed_vs_raw_bf16_hadamard": metrics(
            raw_hadamard, reconstructed),
        "reconstructed_vs_hardware_s35_hadamard": metrics(
            transformed.astype(np.float64) / S32_SCALE, reconstructed),
    }
    return result, stats


def write_activation_files(
        directory: Path, activation: dict[str, np.ndarray],
) -> dict[str, dict[str, int | str]]:
    paths = {
        "activation_s9x16x32.mem": (1152, GROUPS),
        "activation_meta_sc_u224.mem": (56, GROUPS),
        "activation_scale_fp16x16.mem": (64, GROUPS),
        "activation_scale_fp32x16.mem": (128, GROUPS),
    }
    handles = {
        name: (directory / name).open("w", encoding="ascii") for name in paths
    }
    try:
        for group in range(GROUPS):
            base.write_word(
                handles["activation_s9x16x32.mem"],
                base.pack(activation["centered"][group].reshape(-1), 9),
                ROWS*K*9,
            )
            base.write_word(
                handles["activation_meta_sc_u224.mem"],
                base.pack(activation["codes"][group], 8) |
                (base.pack(activation["shifts"][group], 6) << (ROWS*8)),
                ROWS*14,
            )
            decoded = activation["decoded"][group]
            scale16 = base.fp16_ftz_array(decoded)
            scale32 = decoded.astype(np.float32)
            base.write_word(
                handles["activation_scale_fp16x16.mem"],
                base.pack([base.fp16_bits(value) for value in scale16], 16),
                ROWS*16,
            )
            base.write_word(
                handles["activation_scale_fp32x16.mem"],
                base.pack([base.fp32_bits(value) for value in scale32], 32),
                ROWS*32,
            )
    finally:
        for handle in handles.values():
            handle.close()
    return {
        name: {
            "records": records, "hex_digits": digits,
            "sha256": sha256_file(directory / name),
        }
        for name, (digits, records) in paths.items()
    }


def align_sc_group(raw: np.ndarray, total_shift: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw, dtype=np.int64)
    total_shift = np.asarray(total_shift, dtype=np.int16)
    nonzero = raw != 0
    invalid = nonzero & ((total_shift < 21) | (total_shift > 44))
    if np.any(invalid):
        indices = np.argwhere(invalid)[0].tolist()
        raise AssertionError(
            f"nonzero MLP ScaleCode total shift outside [21,44] at {indices}")
    result = np.zeros(raw.shape, dtype=np.int64)
    left = nonzero & (total_shift < 24)
    right = nonzero & ~left
    if np.any(left):
        result[left] = np.left_shift(raw[left], 24-total_shift[left])
    if np.any(right):
        result[right] = np.right_shift(raw[right], total_shift[right]-24)
    if np.any(result < S36_MIN) or np.any(result > S36_MAX):
        raise AssertionError("aligned ScaleCode group does not fit S36")
    return result


def padded_tile(values: np.ndarray, tile: int, fill=0) -> np.ndarray:
    start = tile * COLS
    stop = min(HIDDEN, start + COLS)
    result = np.full((COLS,) + values.shape[1:], fill,
                     dtype=values.dtype)
    result[:stop-start] = values[start:stop]
    return result


def write_layer(
        checkpoint: exporter.LlamaCheckpoint, layer: int,
        raw_rows: np.ndarray, activation: dict[str, np.ndarray],
        final_dir: Path,
) -> tuple[dict, dict[str, dict[str, int | str]], dict[str, np.ndarray]]:
    if final_dir.exists():
        raise FileExistsError(f"refusing to replace existing trace layer: {final_dir}")
    partial = final_dir.with_name(final_dir.name + f".partial.{os.getpid()}")
    partial.mkdir(parents=True)
    files = write_activation_files(partial, activation)
    weight_specs = {
        "weights_s4x12x32.mem": (384, TRANSACTIONS),
        "weight_meta_sc_u168.mem": (42, TRANSACTIONS),
        "weight_scale_fp16x12.mem": (48, TRANSACTIONS),
        "weight_scale_fp32x12.mem": (96, TRANSACTIONS),
    }
    handles = {
        name: (partial / name).open("w", encoding="ascii")
        for name in weight_specs
    }
    sc_acc = np.zeros((ROWS, HIDDEN), dtype=np.int64)
    fp16_acc = np.zeros((ROWS, HIDDEN), dtype=np.float32)
    fp32_acc = np.zeros((ROWS, HIDDEN), dtype=np.float32)
    common_acc = np.zeros((ROWS, HIDDEN), dtype=np.float64)
    raw_acc = np.zeros((ROWS, HIDDEN), dtype=np.float64)
    weight_metric = StreamingMetrics()
    weight_clip_count = 0
    fp16_zero_contributions = 0
    weight_code_min, weight_code_max = 255, 0
    weight_shift_min, weight_shift_max = 255, 0
    total_shift_min, total_shift_max = 255, 0
    down_name = f"model.layers.{layer}.mlp.down_proj.weight"
    try:
        for group in range(GROUPS):
            source = checkpoint.float32(
                down_name, columns=slice(group*K, (group+1)*K))
            if source.shape != (HIDDEN, K) or not np.all(np.isfinite(source)):
                raise AssertionError("invalid checkpoint Down weight group")
            quantized, codes_2d, shifts_2d = exporter.quantize_folded_rows(
                source, 4)
            q = quantized[:, 0, :]
            codes = codes_2d[:, 0]
            shifts = shifts_2d[:, 0]
            decoded = np.ldexp(
                codes.astype(np.float64), -shifts.astype(np.int16))
            folded = exporter.fwht32_normalized(
                source.reshape(HIDDEN, 1, K))[:, 0, :]
            reconstructed = q.astype(np.float64) * decoded[:, None]
            weight_metric.update(folded, reconstructed)
            divisor = np.where(codes == 0, 1.0, decoded)
            before_clip = exporter.round_away(folded / divisor[:, None])
            weight_clip_count += int(np.count_nonzero(
                (before_clip < -8) | (before_clip > 7)))
            weight_code_min = min(weight_code_min, int(codes.min()))
            weight_code_max = max(weight_code_max, int(codes.max()))
            weight_shift_min = min(weight_shift_min, int(shifts.min()))
            weight_shift_max = max(weight_shift_max, int(shifts.max()))

            act = activation["centered"][group].astype(np.int32)
            corr = np.matmul(act, q.astype(np.int32).T).astype(np.int64)
            total_shift = (
                activation["shifts"][group, :, None].astype(np.int16) +
                shifts[None, :].astype(np.int16)
            )
            raw = (
                corr * activation["codes"][group, :, None].astype(np.int64) *
                codes[None, :].astype(np.int64)
            )
            nonzero = raw != 0
            if np.any(nonzero):
                total_shift_min = min(
                    total_shift_min, int(total_shift[nonzero].min()))
                total_shift_max = max(
                    total_shift_max, int(total_shift[nonzero].max()))
            sc_acc += align_sc_group(raw, total_shift)
            if np.any(sc_acc < S45_MIN) or np.any(sc_acc > S45_MAX):
                raise AssertionError("ScaleCode Down accumulator escaped S45")

            act_scale = activation["decoded"][group]
            act_scale16 = base.fp16_ftz_array(act_scale)
            act_scale32 = act_scale.astype(np.float32)
            weight_scale16 = base.fp16_ftz_array(decoded)
            weight_scale32 = decoded.astype(np.float32)
            corr16 = base.fp16_ftz_array(corr.astype(np.float32))
            term16 = base.fp16_mul_ip_array(
                base.fp16_mul_ip_array(
                    corr16, act_scale16[:, None]),
                weight_scale16[None, :],
            )
            fp16_zero_contributions += int(np.count_nonzero(
                (term16.view(np.uint16) & np.uint16(0x7FFF)) == 0))
            fp16_acc = np.asarray(
                fp16_acc + term16.astype(np.float32), dtype=np.float32)
            term32 = np.asarray(
                corr.astype(np.float32) * act_scale32[:, None],
                dtype=np.float32)
            term32 = np.asarray(
                term32 * weight_scale32[None, :], dtype=np.float32)
            fp32_acc = np.asarray(fp32_acc + term32, dtype=np.float32)
            common_acc += (
                corr.astype(np.float64) * act_scale[:, None] *
                decoded[None, :]
            )
            raw_acc += np.matmul(
                raw_rows[:, group*K:(group+1)*K].astype(np.float64),
                source.T.astype(np.float64),
            )

            for tile in range(TILES):
                q_tile = padded_tile(q, tile)
                code_tile = padded_tile(codes, tile)
                shift_tile = padded_tile(shifts, tile)
                decoded_tile = padded_tile(decoded, tile)
                handles["weights_s4x12x32.mem"].write(
                    base.packed_nibbles_hex(q_tile) + "\n")
                base.write_word(
                    handles["weight_meta_sc_u168.mem"],
                    base.pack(code_tile, 8) |
                    (base.pack(shift_tile, 6) << (COLS*8)), COLS*14)
                scale16 = base.fp16_ftz_array(decoded_tile)
                scale32 = decoded_tile.astype(np.float32)
                base.write_word(
                    handles["weight_scale_fp16x12.mem"],
                    base.pack([base.fp16_bits(value) for value in scale16], 16),
                    COLS*16)
                base.write_word(
                    handles["weight_scale_fp32x12.mem"],
                    base.pack([base.fp32_bits(value) for value in scale32], 32),
                    COLS*32)
            if group % 32 == 31 or group + 1 == GROUPS:
                print(
                    f"M12_TRACE_LAYER_PROGRESS layer={layer} "
                    f"groups={group+1}/{GROUPS}", flush=True)
    finally:
        for handle in handles.values():
            handle.close()

    for name, (digits, records) in weight_specs.items():
        files[name] = {
            "records": records, "hex_digits": digits,
            "sha256": sha256_file(partial / name),
        }

    masks = [0x00F if tile == TILES-1 else 0xFFF for tile in range(TILES)]
    mask_path = partial / "column_mask_u12.mem"
    with mask_path.open("w", encoding="ascii") as handle:
        for value in masks:
            base.write_word(handle, value, 12)
    files[mask_path.name] = {
        "records": TILES, "hex_digits": 3,
        "sha256": sha256_file(mask_path),
    }

    sc_rounded_unclipped = np.where(
        sc_acc < 0, -((np.abs(sc_acc) + 128) >> 8),
        (sc_acc + 128) >> 8)
    sc_out = np.clip(
        sc_rounded_unclipped, -(1 << 23), (1 << 23)-1).astype(np.int64)
    fp16_unclipped = np.rint(fp16_acc.astype(np.float64) * S32_SCALE)
    fp32_unclipped = np.rint(fp32_acc.astype(np.float64) * S32_SCALE)
    fp16_out = np.clip(
        fp16_unclipped, -(1 << 23), (1 << 23)-1).astype(np.int64)
    fp32_out = np.clip(
        fp32_unclipped, -(1 << 23), (1 << 23)-1).astype(np.int64)
    expected = {
        "expected_sc_s24x16x12.mem": sc_out,
        "expected_fp16_s24x16x12.mem": fp16_out,
        "expected_fp32_s24x16x12.mem": fp32_out,
    }
    for name, values in expected.items():
        path = partial / name
        with path.open("w", encoding="ascii") as handle:
            for tile in range(TILES):
                tile_values = np.zeros((ROWS, COLS), dtype=np.int64)
                start = tile * COLS
                stop = min(HIDDEN, start + COLS)
                tile_values[:, :stop-start] = values[:, start:stop]
                base.write_word(
                    handle, base.pack(tile_values.reshape(-1), 24),
                    ROWS*COLS*24)
        files[name] = {
            "records": TILES, "hex_digits": 1152,
            "sha256": sha256_file(path),
        }

    reconstructed = {
        "sc": sc_out.astype(np.float64) / S32_SCALE,
        "fp16": fp16_out.astype(np.float64) / S32_SCALE,
        "fp32": fp32_out.astype(np.float64) / S32_SCALE,
        "common": common_acc,
        "raw": raw_acc,
    }
    stats = {
        "layer": layer,
        "weight_quantization": {
            "contract": (
                "production V5 normalized folded group32 W4; maxabs/7; "
                "round-half-away against decoded ScaleCode; clamp [-8,7]"),
            "reconstructed_vs_folded_checkpoint_bf16": weight_metric.result(),
            "pre_clamp_count": weight_clip_count,
            "scale_code_min": weight_code_min,
            "scale_code_max": weight_code_max,
            "scale_shift_min": weight_shift_min,
            "scale_shift_max": weight_shift_max,
        },
        "nonzero_total_shift_min": total_shift_min,
        "nonzero_total_shift_max": total_shift_max,
        "fp16_zero_group_contributions": fp16_zero_contributions,
        "saturation_count": {
            "sc": int(np.count_nonzero(
                sc_out != sc_rounded_unclipped)),
            "fp16": int(np.count_nonzero(
                fp16_out.astype(np.float64) != fp16_unclipped)),
            "fp32": int(np.count_nonzero(
                fp32_out.astype(np.float64) != fp32_unclipped)),
        },
        "accuracy_vs_raw_bf16_checkpoint_fp64_dot": {
            name: metrics(raw_acc, reconstructed[name])
            for name in ("sc", "fp16", "fp32")
        },
        "accuracy_vs_common_quantized_fp64": {
            name: metrics(common_acc, reconstructed[name])
            for name in ("sc", "fp16", "fp32")
        },
    }
    partial.replace(final_dir)
    return stats, {
        f"layer{layer:02d}/{name}": record for name, record in files.items()
    }, reconstructed


def write_rows_csv(
        path: Path, coordinates: Iterable[dict[str, object]],
) -> dict[str, int | str]:
    rows = list(coordinates)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "row", "sample", "layer", "token", "source_tensor",
            "source_payload_sha256"))
        writer.writeheader()
        writer.writerows(rows)
    return {
        "records": len(rows), "hex_digits": 0,
        "sha256": sha256_file(path),
    }


def main() -> None:
    args = parse_args()
    base.verify_fp16_mul_ip_boundary()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(
            f"output directory must be empty for deterministic generation: {output}")
    trace_dir, trace_manifest = verify_source_trace(args.trace_run)
    model_dir = (args.model_dir or Path(str(trace_manifest["checkpoint"])))
    checkpoint, checkpoint_shards = verify_checkpoint(
        model_dir, trace_manifest, args.layers)
    tensor_records = {
        (record["sample"], record["layer"], record["name"]): record
        for record in trace_manifest["tensors"]
    }

    all_coordinates: list[dict[str, object]] = []
    all_sources: list[dict[str, object]] = []
    layer_stats: list[dict] = []
    all_files: dict[str, dict[str, int | str]] = {}
    aggregate: dict[str, list[np.ndarray]] = {
        name: [] for name in ("sc", "fp16", "fp32", "common", "raw")
    }
    for layer in args.layers:
        raw_rows, coordinates, sources = select_rows(
            trace_dir, tensor_records, layer)
        activation, activation_stats = build_activation_payload(raw_rows)
        stats, files, reconstructed = write_layer(
            checkpoint, layer, raw_rows, activation,
            output / f"layer{layer:02d}")
        stats["activation"] = activation_stats
        stats["row_coordinates"] = coordinates
        layer_stats.append(stats)
        all_coordinates.extend(coordinates)
        all_sources.extend(sources)
        all_files.update(files)
        for name in aggregate:
            aggregate[name].append(reconstructed[name])
        print(
            f"M12_TRACE_LAYER_PASS layer={layer} rows={ROWS} "
            f"groups={GROUPS} tiles={TILES}", flush=True)

    rows_path = output / "trace_rows.csv"
    all_files[rows_path.name] = write_rows_csv(rows_path, all_coordinates)
    combined = {
        name: np.concatenate(values, axis=0)
        for name, values in aggregate.items()
    }
    generator = Path(__file__).resolve()
    fp_semantics_model = Path(base.__file__).resolve()
    production_exporter = Path(exporter.__file__).resolve()
    production_model = Path(mlp_fixed.__file__).resolve()
    manifest = {
        "schema": "scalellm_modular_m12_down_real_trace_v1",
        "layers": list(args.layers),
        "samples": list(SAMPLES),
        "tokens": list(TOKENS),
        "rows_per_layer": ROWS,
        "groups": GROUPS,
        "tiles": TILES,
        "physical_columns": COLS,
        "valid_output_columns": HIDDEN,
        "group_size": K,
        "transactions_per_layer": TRANSACTIONS,
        "ordering": "per layer, group-major: index=group*342+tile",
        "tail_mask": "0x00f",
        "comparison_boundary": (
            "common raw-Min/Max centered S9 activation/W4 payload and decoded "
            "ScaleCode scale; SC keeps code+shift, FP baselines receive that "
            "same scale encoded as IEEE FP16/FP32; M11 producer counted once"),
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "source_trace_run": str(args.trace_run.resolve()),
        "source_trace_manifest_sha256": sha256_file(trace_dir / "manifest.json"),
        "checkpoint": str(Path(model_dir).resolve()),
        "checkpoint_index_sha256": str(
            trace_manifest["checkpoint_index_sha256"]),
        "checkpoint_shards": checkpoint_shards,
        "source_tensors": all_sources,
        "layer_results": layer_stats,
        "aggregate_accuracy_vs_raw_bf16_checkpoint_fp64_dot": {
            name: metrics(combined["raw"], combined[name])
            for name in ("sc", "fp16", "fp32")
        },
        "aggregate_accuracy_vs_common_quantized_fp64": {
            name: metrics(combined["common"], combined[name])
            for name in ("sc", "fp16", "fp32")
        },
        "files": dict(sorted(all_files.items())),
        "generator_sha256": sha256_file(generator),
        "fp_semantics_model": str(fp_semantics_model),
        "fp_semantics_model_sha256": sha256_file(fp_semantics_model),
        "production_exporter": str(production_exporter),
        "production_exporter_sha256": sha256_file(production_exporter),
        "production_model": str(production_model),
        "production_model_sha256": sha256_file(production_model),
        "minmax_reference": str(Path(minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(Path(minmax_a8.__file__)),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M12_TRACE_VECTOR_PASS "
        f"layers={len(args.layers)} rows={len(args.layers)*ROWS} "
        f"transactions={len(args.layers)*TRANSACTIONS} "
        f"valid_outputs={len(args.layers)*ROWS*HIDDEN} "
        f"source_tensors={len(all_sources)} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Keep layer-level partial directories as failure evidence, but remove
        # an empty root produced before any meaningful artifact was written.
        output_arg = None
        for index, argument in enumerate(sys.argv[:-1]):
            if argument == "--output-dir":
                output_arg = Path(sys.argv[index+1]).resolve()
        if output_arg is not None and output_arg.is_dir() and not any(
                output_arg.iterdir()):
            output_arg.rmdir()
        raise
