#!/usr/bin/env python3
"""Generate real 8x16x128 Q/K/V projection tiles for M02.

The common U8/S8 payload is derived from the independently verified attention
input capture and checkpoint weights with the production Hadamard, raw-Min/Max A8,
and normalized folded-W8 models.  FP16 nonfinite conversion is never guessed:
the generator refuses to run until a PASSed AMD-IP semantic probe map exists.
"""

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


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
EXPERIMENT_ROOT = MODULE.parents[1]
SCALELLM_ROOT = EXPERIMENT_ROOT.parent
LEGACY_MODEL = MODULE / "legacy_seed"
if str(LEGACY_MODEL) not in sys.path:
    sys.path.insert(0, str(LEGACY_MODEL))
if str(SCALELLM_ROOT / "model") not in sys.path:
    sys.path.insert(0, str(SCALELLM_ROOT / "model"))

import generate_vectors as base  # noqa: E402
import export_scalellm_llama31_artifacts as exporter  # noqa: E402
import fixbit_v2  # noqa: E402

MODULAR_MODEL = EXPERIMENT_ROOT / "tools" / "model"
if str(MODULAR_MODEL) not in sys.path:
    sys.path.insert(0, str(MODULAR_MODEL))
import minmax_a8  # noqa: E402


DEFAULT_TRACE_RUN = (
    EXPERIMENT_ROOT /
    "result/trace/raw/20260909_221332_llama31_8b_replayable_trace"
)
DEFAULT_CAPTURE = (
    EXPERIMENT_ROOT /
    "experiment/03_attention_rope/data_trace_projection_input"
)
CAPTURE_VERIFIER = (
    EXPERIMENT_ROOT /
    "experiment/03_attention_rope/model/verify_trace_projection_inputs.py"
)
DEFAULT_SEMANTIC_ROOT = (
    EXPERIMENT_ROOT /
    "result/02_attention_a8w8_projection/raw/fp16/semantic_probe"
)
DEFAULT_OUTPUT = MODULE / "data_trace"
ROWS, COLS, GROUPS, GROUP_SIZE = 8, 16, 128, 32
LAYERS = (0, 15, 31)
SAMPLES = (0, 1)
KINDS = ("q", "k", "v")
S24_MIN, S24_MAX = -(1 << 23), (1 << 23) - 1
S42_MIN, S42_MAX = -(1 << 41), (1 << 41) - 1
MASK42 = (1 << 42) - 1
BASE_TOKENS = (0, 1, 15, 31, 63, 95, 111, 127)
Q_SPREAD_ROWS = (0, 1, 63, 64, 127, 128, 511, 512, 1023, 1024,
                 1535, 2048, 2559, 3072, 3583, 4095)
KV_SPREAD_ROWS = (0, 1, 63, 64, 127, 128, 255, 256,
                  511, 512, 767, 768, 895, 896, 1022, 1023)

# These coordinates are inherited from the provenance-checked M03 real
# projection-tail workload.  Including both RoPE-pair rows and the exact token
# guarantees that Q/K trace tiles preserve its measured FP16 range events.
M03_SPECIAL = {
    (0, 0, "q"): (0, (0, 64)),
    (0, 0, "k"): (64, (529, 593)),
    (0, 15, "q"): (31, (2207, 2271)),
    (0, 15, "k"): (63, (687, 751)),
    (0, 31, "q"): (127, (4031, 4095)),
    (0, 31, "k"): (95, (897, 961)),
    (1, 0, "q"): (1, (1032, 1096)),
    (1, 0, "k"): (111, (280, 344)),
    (1, 15, "q"): (15, (2984, 3048)),
    (1, 15, "k"): (127, (824, 888)),
    (1, 31, "q"): (63, (2063, 2127)),
    (1, 31, "k"): (31, (416, 480)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-run", type=Path, default=DEFAULT_TRACE_RUN)
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--semantic-map", type=Path)
    parser.add_argument("--semantic-root", type=Path,
                        default=DEFAULT_SEMANTIC_ROOT)
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
        sys.executable, str(CAPTURE_VERIFIER), "--capture-dir", str(capture),
    ], check=True)
    return json.loads((capture / "manifest.json").read_text(encoding="utf-8"))


def verify_run_hash(run_dir: Path, target: Path) -> None:
    sums = run_dir / "SHA256SUMS"
    if not sums.is_file():
        raise AssertionError("semantic probe is missing SHA256SUMS")
    found = False
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        candidate = Path(name).resolve()
        if candidate == target:
            found = True
            if sha256_file(target) != digest:
                raise AssertionError("semantic map hash mismatch")
    if not found:
        raise AssertionError("semantic map is absent from probe SHA256SUMS")


def find_semantic_map(explicit: Path | None, root: Path) -> Path:
    if explicit is not None:
        candidates = [explicit.resolve(strict=True)]
    else:
        root = root.resolve()
        candidates = sorted(root.glob("*/semantic_map.json"), reverse=True)
    for candidate in candidates:
        run_dir = candidate.parent
        try:
            if (run_dir / "STATUS").read_text(encoding="ascii").strip() != "PASS":
                continue
            if int((run_dir / "exit_status.txt").read_text().strip()) != 0:
                continue
            verify_run_hash(run_dir, candidate)
            return candidate
        except (FileNotFoundError, ValueError):
            continue
    raise SystemExit(
        "M02 real trace generation is gated: no PASSed and hashed "
        "FP16 semantic_map.json exists. Run "
        "experiment/02_attention_a8w8_projection/"
        "run_fp16_nonfinite_probe.sh after the current Vivado job.")


def signed_word(word: int, width: int) -> int:
    return word - (1 << width) if word & (1 << (width - 1)) else word


def load_semantics(path: Path) -> tuple[dict[tuple[str, int], int], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "scalellm_m02_fp16_nonfinite_semantics_v1":
        raise AssertionError("unexpected semantic-map schema")
    if payload.get("record_count") != 25 or len(payload.get("records", [])) != 25:
        raise AssertionError("semantic-map record count mismatch")
    mapping: dict[tuple[str, int], int] = {}
    invalid_mul_cases: dict[tuple[str, int], tuple[int, int]] = {}
    for record in payload["records"]:
        cls = record["widen_fp32_class"]
        if cls == "finite":
            continue
        widen = int(record["widen_fp32"], 16)
        sign = (widen >> 31) & 1
        output = signed_word(int(record["output_s42"], 16), 42)
        key = (cls, sign)
        if key in mapping and mapping[key] != output:
            raise AssertionError(f"ambiguous semantic mapping for {key}")
        mapping[key] = output
        if cls == "nan":
            act_zero = record["act_scale_fp16"] == "0x0000"
            weight_zero = record["weight_scale_fp16"] == "0x0000"
            if act_zero == weight_zero:
                raise AssertionError("NaN probe must have exactly one zero scale")
            zero_stage = "act" if act_zero else "weight"
            corr_sign = int(record["correlation_s21"] < 0)
            invalid_mul_cases[(zero_stage, corr_sign)] = (sign, output)
    if ("infinity", 0) not in mapping or ("infinity", 1) not in mapping:
        raise AssertionError("semantic map lacks signed infinity coverage")
    expected_invalid_cases = {
        ("act", 0), ("act", 1), ("weight", 0), ("weight", 1),
    }
    if set(invalid_mul_cases) != expected_invalid_cases:
        raise AssertionError("semantic map lacks signed Infinity-times-zero coverage")
    invalid_outputs = {value for _, value in invalid_mul_cases.values()}
    invalid_signs = {sign for sign, _ in invalid_mul_cases.values()}
    if len(invalid_outputs) != 1 or invalid_signs != {0}:
        raise AssertionError("AMD invalid-multiply NaN result is not canonical")
    # NumPy preserves a negative NaN payload for -Infinity * 0, while the
    # measured AMD IP canonicalizes every relevant invalid multiply to +qNaN.
    # Accept either host-side payload sign only after all four probe cases
    # above prove that they share one hardware float-to-S42 result.
    canonical_nan_output = next(iter(invalid_outputs))
    mapping[("nan", 0)] = canonical_nan_output
    mapping[("nan", 1)] = canonical_nan_output
    return mapping, payload


def fp16_class_and_sign(value: np.float16) -> tuple[str, int]:
    bits = base.fp16_bits(value)
    if (bits & 0x7c00) != 0x7c00:
        return "finite", (bits >> 15) & 1
    return ("nan" if bits & 0x03ff else "infinity", (bits >> 15) & 1)


def fp16_to_s42(value: np.float16,
                 semantics: dict[tuple[str, int], int]) -> int:
    cls, sign = fp16_class_and_sign(value)
    if cls == "finite":
        widened = base.fp16_to_fp32_ip(value)
        # Every nonzero half normal has at most ten fraction bits, so Q24 is
        # integral and exactly representable here.
        converted = int(float(widened) * (1 << 24))
        if not S42_MIN <= converted <= S42_MAX:
            raise AssertionError("finite FP16 contribution escaped S42")
        return converted
    key = (cls, sign)
    if key not in semantics:
        raise AssertionError(f"semantic map has no observed result for {key}")
    return semantics[key]


def wrap_s42(value: int) -> tuple[int, bool]:
    overflow = not S42_MIN <= value <= S42_MAX
    return signed_word(value & MASK42, 42), overflow


def add_s42(left: int, right: int) -> tuple[int, bool]:
    return wrap_s42(left + right)


def choose_tokens(sample: int, layer: int, kind: str) -> list[int]:
    tokens = list(BASE_TOKENS)
    special = M03_SPECIAL.get((sample, layer, kind))
    if special is not None and special[0] not in tokens:
        tokens[-1] = special[0]
    return sorted(tokens)


def choose_rows(sample: int, layer: int, kind: str) -> list[int]:
    rows: list[int] = []
    special = M03_SPECIAL.get((sample, layer, kind))
    if special is not None:
        rows.extend(special[1])
    spread = Q_SPREAD_ROWS if kind == "q" else KV_SPREAD_ROWS
    rows.extend(row for row in spread if row not in rows)
    if len(rows) < COLS:
        raise AssertionError("insufficient projection row coordinates")
    return rows[:COLS]


def quantize_activations(raw: np.ndarray, tokens: list[int]) -> tuple[
        list[list[Any]], dict[str, int]]:
    fixed_rows: list[np.ndarray] = []
    input_saturation = 0
    for token in tokens:
        scaled = np.rint(raw[token].astype(np.float64) * (1 << 16))
        fixed = np.clip(scaled, S24_MIN, S24_MAX).astype(np.int64)
        input_saturation += int(np.count_nonzero(fixed != scaled))
        fixed_rows.append(fixed)
    groups: list[list[Any]] = []
    hadamard_saturation = 0
    pre_quant_clip_lanes = 0
    zero_scale = 0
    for group in range(GROUPS):
        rows = []
        for fixed in fixed_rows:
            transformed = fixbit_v2.hadamard32_normalized(
                fixed[group*GROUP_SIZE:(group+1)*GROUP_SIZE].tolist())
            hadamard_saturation += transformed.saturation_count
            quantized = minmax_a8.quantize_s27(transformed.values)
            zero_scale += int(quantized.scale_code == 0)
            pre_quant_clip_lanes += sum(
                value < quantized.low or value > quantized.high
                for value in transformed.values)
            rows.append(quantized)
        groups.append(rows)
    return groups, {
        "input_s24_saturation": input_saturation,
        "hadamard_saturation": hadamard_saturation,
        "activation_clip_lanes": pre_quant_clip_lanes,
        "pre_quant_clip_lanes": pre_quant_clip_lanes,
        "activation_zero_scale_groups": zero_scale,
    }


def range_select_v(
        checkpoint: Any, layer: int, activation_groups: list[list[Any]],
) -> tuple[list[int], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tensor = f"model.layers.{layer}.self_attn.v_proj.weight"
    raw = checkpoint.float32(tensor, rows=list(range(1024)))
    quantized, codes, shifts = exporter.quantize_folded_rows(raw, 8)
    max_abs = np.zeros(1024, dtype=np.int64)
    for group, rows in enumerate(activation_groups):
        centered = np.asarray([
            np.asarray(row.values, dtype=np.int64) - row.zero_point
            for row in rows
        ], dtype=np.int64)
        correlation = centered @ quantized[:, group, :].astype(np.int64).T
        max_abs = np.maximum(max_abs, np.max(np.abs(correlation), axis=0))
    order = np.lexsort((np.arange(1024), -max_abs))[:COLS]
    selected = [int(value) for value in order]
    return (selected, raw[order], quantized[order], codes[order],
            shifts[order])


def pack_rows(rows: list[list[int]], width: int) -> int:
    return base.pack([value for row in rows for value in row], width)


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


def metrics(actual: list[int], reference: list[float]) -> dict[str, float]:
    actual_array = np.asarray(actual, dtype=np.float64) / (1 << 16)
    reference_array = np.asarray(reference, dtype=np.float64)
    error = actual_array - reference_array
    denominator = np.linalg.norm(actual_array) * np.linalg.norm(reference_array)
    cosine = float(np.dot(actual_array, reference_array) / denominator)
    return {
        "max_abs_error": float(np.max(np.abs(error))),
        "mean_abs_error": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "cosine_similarity": cosine,
    }


def main() -> None:
    np.seterr(over="ignore", invalid="ignore")
    args = parse_args()
    # Fail before hashing/cross-checking the much larger trace and checkpoint
    # inputs.  Until hardware semantics exist there is no legal FP16 golden to
    # generate, so doing expensive provenance work first only hides the true
    # gate and wastes experiment time.
    semantic_path = find_semantic_map(args.semantic_map, args.semantic_root)
    semantic_mapping, semantic_payload = load_semantics(semantic_path)
    trace_run = args.trace_run.resolve(strict=True)
    trace_dir, trace_manifest = verify_trace(trace_run)
    capture_dir = args.capture_dir.resolve(strict=True)
    capture_manifest = verify_capture(capture_dir)
    if capture_manifest["source_trace_manifest_sha256"] != sha256_file(
            trace_dir / "manifest.json"):
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

    memories: dict[str, list[int]] = {
        "act_u8.mem": [], "weight_s8.mem": [], "zp_rows.mem": [],
        "scalecode_meta.mem": [], "fp16_meta.mem": [], "fp32_meta.mem": [],
        "expected_scalecode_s24.mem": [], "expected_fp16_s24.mem": [],
        "expected_fp32_s24.mem": [],
    }
    expected = {"sc": [], "fp16": [], "fp32": []}
    references = {"common": [], "checkpoint": [], "frozen": []}
    numeric = {
        "input_s24_saturation": 0,
        "hadamard_saturation": 0,
        "activation_clip_lanes": 0,
        "pre_quant_clip_lanes": 0,
        "activation_zero_scale_groups": 0,
        "weight_preclamp_lanes": 0,
        "fp16_correlation_nonfinite": 0,
        "fp16_contribution_nonfinite": 0,
        "fp16_zero_contributions": 0,
        "sc_s42_overflow": 0,
        "fp16_s42_overflow": 0,
        "fp32_s42_overflow": 0,
    }
    correlation_ranges = {kind: [None, None] for kind in KINDS}
    total_shifts: list[int] = []
    tile_rows: list[dict[str, Any]] = []

    for sample in SAMPLES:
        for layer in LAYERS:
            activation_key = (sample, layer)
            record = capture_records[activation_key]
            if activation_key not in activation_cache:
                bits = load_array(capture_dir / record["file"], record)
                activation_cache[activation_key] = bf16_bits_to_fp32(bits)
                source_tensors[f"capture/{record['file']}"] = {
                    "role": "attention_input_bf16", "sample": sample,
                    "layer": layer, "file": record["file"],
                    "file_sha256": record["file_sha256"],
                    "payload_sha256": record["payload_sha256"],
                    "shape": record["shape"],
                    "storage_dtype": record["storage_dtype"],
                }
            raw_activation = activation_cache[activation_key]

            for kind in KINDS:
                tokens = choose_tokens(sample, layer, kind)
                activation_groups, activation_stats = quantize_activations(
                    raw_activation, tokens)
                for key, value in activation_stats.items():
                    numeric[key] += value

                operation = f"{kind}_proj"
                tensor_name = (
                    f"model.layers.{layer}.self_attn.{operation}.weight")
                if kind == "v":
                    output_rows, raw_weights, quantized_weights, weight_codes, \
                        weight_shifts = range_select_v(
                            checkpoint, layer, activation_groups)
                    row_selection = "top16 max-abs correlation over tile tokens"
                else:
                    output_rows = choose_rows(sample, layer, kind)
                    raw_weights = checkpoint.float32(
                        tensor_name, rows=output_rows)
                    quantized_weights, weight_codes, weight_shifts = \
                        exporter.quantize_folded_rows(raw_weights, 8)
                    row_selection = (
                        "M03 provenance pair plus deterministic spread rows")
                folded_weights = exporter.fwht32_normalized(
                    raw_weights.reshape(COLS, GROUPS, GROUP_SIZE))
                decoded_weight_scales = np.ldexp(
                    weight_codes.astype(np.float64),
                    -weight_shifts.astype(np.int64))
                before_clamp = exporter.round_away(
                    folded_weights.astype(np.float64) /
                    decoded_weight_scales[..., None])
                numeric["weight_preclamp_lanes"] += int(np.count_nonzero(
                    (before_clamp < -127) | (before_clamp > 127)))

                accum = {
                    name: np.zeros((ROWS, COLS), dtype=object)
                    for name in ("sc", "fp16", "fp32")
                }
                common = np.zeros((ROWS, COLS), dtype=np.float64)
                tile_overflow = {name: 0 for name in accum}

                for group, act_rows in enumerate(activation_groups):
                    act_values = [list(map(int, row.values)) for row in act_rows]
                    weight_values = quantized_weights[:, group, :].astype(
                        np.int64).tolist()
                    memories["act_u8.mem"].append(pack_rows(act_values, 8))
                    memories["weight_s8.mem"].append(
                        pack_rows(weight_values, 8))
                    memories["zp_rows.mem"].append(base.pack(
                        [int(row.zero_point) for row in act_rows], 8))

                    sc_meta = []
                    fp16_meta = []
                    fp32_meta = []
                    for row in act_rows:
                        sc_meta.append(int(row.scale_code) |
                                       (int(row.scale_shift) << 8))
                        scale = row.scale_code / float(1 << row.scale_shift)
                        fp16_meta.append(base.fp16_bits(scale))
                        fp32_meta.append(base.fp32_bits(scale))
                    for col in range(COLS):
                        code = int(weight_codes[col, group])
                        shift = int(weight_shifts[col, group])
                        sc_meta.append(code | (shift << 8))
                        scale = code / float(1 << shift)
                        fp16_meta.append(base.fp16_bits(scale))
                        fp32_meta.append(base.fp32_bits(scale))
                    memories["scalecode_meta.mem"].append(
                        base.pack(sc_meta, 16))
                    memories["fp16_meta.mem"].append(base.pack(fp16_meta, 16))
                    memories["fp32_meta.mem"].append(base.pack(fp32_meta, 32))

                    for row, activation in enumerate(act_rows):
                        centered = (
                            np.asarray(activation.values, dtype=np.int64) -
                            activation.zero_point)
                        act_code = int(activation.scale_code)
                        act_shift = int(activation.scale_shift)
                        act_scale = act_code / float(1 << act_shift)
                        for col in range(COLS):
                            corr = int(np.dot(
                                centered,
                                quantized_weights[col, group].astype(np.int64)))
                            if not -(1 << 20) <= corr < (1 << 20):
                                raise AssertionError("correlation escaped S21")
                            low, high = correlation_ranges[kind]
                            correlation_ranges[kind] = [
                                corr if low is None else min(low, corr),
                                corr if high is None else max(high, corr),
                            ]
                            weight_code = int(weight_codes[col, group])
                            weight_shift = int(weight_shifts[col, group])
                            weight_scale = weight_code / float(1 << weight_shift)
                            total_shift = act_shift + weight_shift
                            if not 26 <= total_shift <= 47:
                                raise AssertionError(
                                    "ScaleCode total shift escaped [26,47]")
                            total_shifts.append(total_shift)

                            sc_raw = (corr * act_code * weight_code) >> (
                                total_shift - 24)
                            sc_contribution, sc_overflow = wrap_s42(sc_raw)
                            corr16 = base.fp16_ftz(np.float32(corr))
                            act16 = base.fp16_ftz(np.float32(act_scale))
                            weight16 = base.fp16_ftz(np.float32(weight_scale))
                            contribution16 = base.fp16_mul_ip(
                                base.fp16_mul_ip(corr16, act16), weight16)
                            fp16_contribution = fp16_to_s42(
                                contribution16, semantic_mapping)
                            scale32 = np.float32(
                                np.float32(act_scale) * np.float32(weight_scale))
                            contribution32 = base.round_even_s42(np.float32(
                                np.float32(corr) * scale32))

                            numeric["fp16_correlation_nonfinite"] += int(
                                fp16_class_and_sign(corr16)[0] != "finite")
                            numeric["fp16_contribution_nonfinite"] += int(
                                fp16_class_and_sign(contribution16)[0] != "finite")
                            numeric["fp16_zero_contributions"] += int(
                                (base.fp16_bits(contribution16) & 0x7fff) == 0)
                            common[row, col] += (
                                corr * act_scale * weight_scale)

                            for name, contribution in (
                                    ("sc", sc_contribution),
                                    ("fp16", fp16_contribution),
                                    ("fp32", contribution32)):
                                updated, add_overflow = add_s42(
                                    int(accum[name][row, col]), contribution)
                                accum[name][row, col] = updated
                                overflow = add_overflow or (
                                    name == "sc" and sc_overflow)
                                tile_overflow[name] += int(overflow)
                                numeric[f"{name}_s42_overflow"] += int(overflow)

                for name in accum:
                    values = [
                        base.sat_s24(int(accum[name][row, col]))
                        for row in range(ROWS) for col in range(COLS)
                    ]
                    expected[name].extend(values)
                    memories[f"expected_{'scalecode' if name == 'sc' else name}_s24.mem"].append(
                        base.pack(values, 24))
                references["common"].extend(
                    float(common[row, col])
                    for row in range(ROWS) for col in range(COLS))
                checkpoint_reference = (
                    raw_activation[tokens].astype(np.float64) @
                    raw_weights.astype(np.float64).T)
                references["checkpoint"].extend(
                    checkpoint_reference.reshape(-1).tolist())

                frozen_name = (
                    f"{kind}_pre_rope_bf16" if kind in ("q", "k")
                    else "v_bf16")
                frozen_key = (sample, layer, frozen_name)
                if frozen_key not in frozen_cache:
                    frozen_record = trace_records[frozen_key]
                    frozen_bits = load_array(
                        trace_dir / frozen_record["file"], frozen_record)
                    frozen_cache[frozen_key] = bf16_bits_to_fp32(frozen_bits)
                    source_tensors[f"trace/{frozen_record['file']}"] = {
                        "role": f"{frozen_name}_reference",
                        "sample": sample, "layer": layer,
                        "file": frozen_record["file"],
                        "file_sha256": frozen_record["file_sha256"],
                        "payload_sha256": frozen_record["payload_sha256"],
                        "shape": frozen_record["shape"],
                        "storage_dtype": frozen_record["storage_dtype"],
                    }
                frozen_flat = frozen_cache[frozen_key][tokens].reshape(ROWS, -1)
                references["frozen"].extend(
                    frozen_flat[:, output_rows].astype(np.float64).reshape(
                        -1).tolist())

                tile_rows.append({
                    "tile": len(tile_rows), "sample": sample, "layer": layer,
                    "kind": kind.upper(),
                    "tokens": ",".join(map(str, tokens)),
                    "output_rows": ",".join(map(str, output_rows)),
                    "row_selection": row_selection,
                    "sc_s42_overflow": tile_overflow["sc"],
                    "fp16_s42_overflow": tile_overflow["fp16"],
                    "fp32_s42_overflow": tile_overflow["fp32"],
                })

    tiles = len(SAMPLES) * len(LAYERS) * len(KINDS)
    transactions = tiles * GROUPS
    if len(tile_rows) != tiles:
        raise AssertionError("tile count mismatch")
    for name in ("act_u8.mem", "weight_s8.mem", "zp_rows.mem",
                 "scalecode_meta.mem", "fp16_meta.mem", "fp32_meta.mem"):
        if len(memories[name]) != transactions:
            raise AssertionError(f"transaction count mismatch for {name}")
    if numeric["fp16_correlation_nonfinite"] == 0:
        raise AssertionError(
            "real workload unexpectedly lost all FP16 correlation overflows")

    digits = {
        "act_u8.mem": ROWS * GROUP_SIZE * 2,
        "weight_s8.mem": COLS * GROUP_SIZE * 2,
        "zp_rows.mem": ROWS * 2,
        "scalecode_meta.mem": (ROWS + COLS) * 4,
        "fp16_meta.mem": (ROWS + COLS) * 4,
        "fp32_meta.mem": (ROWS + COLS) * 8,
        "expected_scalecode_s24.mem": ROWS * COLS * 6,
        "expected_fp16_s24.mem": ROWS * COLS * 6,
        "expected_fp32_s24.mem": ROWS * COLS * 6,
    }
    files = {
        name: write_mem(output / name, values, digits[name])
        for name, values in memories.items()
    }
    coordinate_path = output / "trace_tiles.csv"
    with coordinate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(tile_rows[0]))
        writer.writeheader()
        writer.writerows(tile_rows)
    files[coordinate_path.name] = {
        "records": len(tile_rows), "hex_digits": 0,
        "bytes": coordinate_path.stat().st_size,
        "sha256": sha256_file(coordinate_path),
    }

    generator = Path(__file__).resolve()
    base_model = Path(base.__file__).resolve()
    exporter_model = Path(exporter.__file__).resolve()
    fixed_model = Path(fixbit_v2.__file__).resolve()
    manifest = {
        "schema": "scalellm_modular_m02_projection_real_trace_v1",
        "tiles": tiles, "rows": ROWS, "cols": COLS,
        "groups_per_tile": GROUPS, "group_size": GROUP_SIZE,
        "transactions": transactions,
        "valid_outputs": tiles * ROWS * COLS,
        "tile_coordinates": tile_rows,
        "selection_policy": (
            "Q/K include exact provenance-checked M03 pair rows/tokens plus "
            "spread rows; V selects top-16 real max-abs correlation rows "
            "over eight diverse real tokens. Range stress is intentional "
            "and disclosed; no small-correlation filtering is allowed."),
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
        "fp16_semantic_map": str(semantic_path),
        "fp16_semantic_map_sha256": sha256_file(semantic_path),
        "fp16_semantic_source_summary_sha256": semantic_payload[
            "source_summary_sha256"],
        "source_tensors": [source_tensors[name]
                           for name in sorted(source_tensors)],
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "numeric_events": numeric,
        "correlation_ranges": {
            kind.upper(): {"min": correlation_ranges[kind][0],
                           "max": correlation_ranges[kind][1]}
            for kind in KINDS
        },
        "total_shift_min": min(total_shifts),
        "total_shift_max": max(total_shifts),
        "accuracy_vs_common_quantized_fp64": {
            name: metrics(expected[name], references["common"])
            for name in expected
        },
        "accuracy_vs_captured_input_checkpoint_fp64": {
            name: metrics(expected[name], references["checkpoint"])
            for name in expected
        },
        "accuracy_vs_original_frozen_bf16": {
            name: metrics(expected[name], references["frozen"])
            for name in expected
        },
        "files": dict(sorted(files.items())),
        "generator_sha256": sha256_file(generator),
        "legacy_boundary_model": str(base_model),
        "legacy_boundary_model_sha256": sha256_file(base_model),
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
    (output / "MANIFEST_SHA256").write_text(
        f"{sha256_file(manifest_path)}  manifest.json\n", encoding="ascii")
    print(
        "M02_TRACE_VECTOR_PASS "
        f"files={len(files)+1} tiles={tiles} transactions={transactions} "
        f"valid_outputs={manifest['valid_outputs']} "
        f"fp16_nonfinite={numeric['fp16_correlation_nonfinite']} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
