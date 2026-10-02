#!/usr/bin/env python3
"""Generate full 448-group product-Hadamard/A8 vectors."""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE.parent / "data"
GROUPS, ROWS, LANES = 448, 16, 32
SEED = 0xF16_11

sys.path.insert(0, str(ROOT / "model"))
import mlp_fixed  # noqa: E402

MODULAR_MODEL = ROOT / "ModularExperiment" / "tools" / "model"
sys.path.insert(0, str(MODULAR_MODEL))
import minmax_a8  # noqa: E402


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((int(value) & mask) << (index * width)
               for index, value in enumerate(values))


def write_mem(path: Path, values: list[int], digits: int) -> None:
    mask = (1 << (4 * digits)) - 1
    path.write_text("".join(f"{value & mask:0{digits}x}\n" for value in values),
                    encoding="ascii")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fp32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def fp16_bits(value: float) -> int:
    rounded = np.float16(np.float32(value))
    bits = int(rounded.view(np.uint16))
    if (bits & 0x7C00) == 0:
        bits &= 0x8000
    return bits


def native_fp_a8(values: list[int]) -> tuple[list[int], int, int]:
    output, zero_point, scale_q24, _low, _high = \
        minmax_a8.native_fp_a8_s35(values)
    return output, zero_point, scale_q24


def build_row(rng: random.Random, group: int, row: int) -> list[int]:
    if group == 0 and row == 0:
        return [0] * LANES
    if group == 0 and row == 1:
        directed = [-16 << 16, -((16 << 16)-1), -1, 0, 1,
                    (16 << 16)-1, 16 << 16]
        return [directed[lane % len(directed)] for lane in range(LANES)]
    mode = (group + row) % 7
    if mode == 0:
        return [((lane - 16) * (row + 1) * 257) << 4
                for lane in range(LANES)]
    if mode == 1:
        magnitude = ((group % 64) + 1) << 16
        return [magnitude if lane & 1 else -magnitude
                for lane in range(LANES)]
    if mode == 2:
        impulse = [0] * LANES
        impulse[(group*ROWS + row) % LANES] = rng.randint(
            -(128 << 16), (128 << 16)-1)
        return impulse
    if mode == 3:
        center = ((row % 5)-2) << 16
        return [center] * LANES
    if mode == 4:
        return [rng.randint(-(8 << 16), (8 << 16)-1)
                for _ in range(LANES)]
    if mode == 5:
        return [rng.randint(-(64 << 16), (64 << 16)-1)
                for _ in range(LANES)]
    # A bounded heavy-tail mixture exercises outlier-driven Min/Max ranges
    # without leaving the realizable S32 SwiGLU product format.
    values = [rng.randint(-(32 << 16), (32 << 16)-1)
              for _ in range(LANES)]
    values[(group + row) % LANES] = rng.randint(
        -(512 << 16), (512 << 16)-1)
    return values


def metrics(measured: list[float], reference: list[float]) -> dict[str, float]:
    a = np.asarray(measured, dtype=np.float64)
    b = np.asarray(reference, dtype=np.float64)
    delta = a - b
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return {
        "max_abs_error": float(np.max(np.abs(delta))),
        "mean_abs_error": float(np.mean(np.abs(delta))),
        "rmse": float(math.sqrt(float(np.mean(delta * delta)))),
        "cosine_similarity": float(np.dot(a, b) / denominator)
        if denominator else 1.0,
    }


def main() -> None:
    rng = random.Random(SEED)
    input_records: list[int] = []
    sc_u8_records: list[int] = []
    sc_meta_records: list[int] = []
    fp_u8_records: list[int] = []
    fp16_meta_records: list[int] = []
    fp32_meta_records: list[int] = []
    reference: list[float] = []
    reconstructed_sc: list[float] = []
    reconstructed_fp16: list[float] = []
    reconstructed_fp32: list[float] = []
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
        for row in range(ROWS):
            source = build_row(rng, group, row)
            transformed_result = mlp_fixed.hadamard32_product_normalized(source)
            transformed = list(transformed_result.values)
            sc = minmax_a8.quantize_s35(transformed)
            fp_values, fp_zp, scale_q24 = native_fp_a8(transformed)
            scale_real = scale_q24 / float(1 << 24)
            scale16_bits = fp16_bits(scale_real)
            scale32_bits = fp32_bits(scale_real)
            scale16 = float(np.asarray([scale16_bits], dtype=np.uint16)
                            .view(np.float16)[0])
            scale32 = float(struct.unpack(
                "<f", struct.pack("<I", scale32_bits))[0])

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
            sc_scale = sc.scale_code / float(1 << sc.scale_shift) \
                if sc.scale_code else 0.0
            for transformed_value, sc_q, fp_q in zip(
                    transformed, sc.values, fp_values):
                reference.append(transformed_value / float(1 << 16))
                reconstructed_sc.append((sc_q - sc.zero_point) * sc_scale)
                reconstructed_fp16.append((fp_q - fp_zp) * scale16)
                reconstructed_fp32.append((fp_q - fp_zp) * scale32)

        input_records.append(pack(inputs, 32))
        sc_u8_records.append(pack(sc_u8, 8))
        sc_meta_records.append(pack(sc_meta, 24))
        fp_u8_records.append(pack(fp_u8, 8))
        fp16_meta_records.append(pack(fp16_meta, 24))
        fp32_meta_records.append(pack(fp32_meta, 40))

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "input_s32.mem": (input_records, 4096),
        "expected_sc_u8.mem": (sc_u8_records, 1024),
        "expected_sc_meta.mem": (sc_meta_records, 96),
        "expected_fp_u8.mem": (fp_u8_records, 1024),
        "expected_fp16_meta.mem": (fp16_meta_records, 96),
        "expected_fp32_meta.mem": (fp32_meta_records, 160),
    }
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)

    manifest = {
        "schema": "scalellm_modular_mlp_product_frontend_native_fp_v1",
        "seed": hex(SEED),
        "groups": GROUPS,
        "rows": ROWS,
        "lanes": LANES,
        "input": "16 rows x 32 lanes signed S32 Q16.16",
        "sc_output": "16x32 U8 plus 16x(meta24 zp/code/shift)",
        "fp16_output": "16x32 U8 plus 16x(zp8 + IEEE FP16 scale)",
        "fp32_output": "16x32 U8 plus 16x(zp8 + IEEE FP32 scale)",
        "hadamard_saturation_count": hadamard_saturations,
        "zero_diff_rows": zero_diff_rows,
        "fp16_nonfinite_scale_count": fp16_nonfinite_scales,
        "scale_format_overflow_rows": scale_format_overflow_rows,
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "accuracy_vs_hadamard_s35_real": {
            "sc": metrics(reconstructed_sc, reference),
            "fp16": metrics(reconstructed_fp16, reference),
            "fp32": metrics(reconstructed_fp32, reference),
        },
        "production_model": str(Path(mlp_fixed.__file__)),
        "production_model_sha256": sha256_file(Path(mlp_fixed.__file__)),
        "minmax_reference": str(Path(minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(Path(minmax_a8.__file__)),
        "sha256": {filename: sha256_file(OUT / filename)
                   for filename in outputs},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("M11_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M11 vectors generated")


if __name__ == "__main__":
    main()
