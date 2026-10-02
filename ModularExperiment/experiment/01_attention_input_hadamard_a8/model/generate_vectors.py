#!/usr/bin/env python3
"""Generate matched Attention frontend vectors for SC and native-FP scale paths."""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE.parent / "data"
ROWS = 8
LANES = 32
GROUPS = 128
SEED = 20260908

sys.path.insert(0, str(ROOT / "model"))
from fixbit_v2 import hadamard32_normalized  # noqa: E402

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
    # Match the Xilinx half converter's flush-to-zero handling.
    if (bits & 0x7C00) == 0:
        bits &= 0x8000
    return bits


def native_fp_a8(values: list[int]) -> tuple[list[int], int, int, int, int]:
    """Return ideal-Min/Max U8, zero point, Q24 scale, low and high."""
    return minmax_a8.native_fp_a8_s27(values)


def build_row(rng: np.random.Generator, group: int, row: int) -> list[int]:
    s24_min = -(1 << 23)
    s24_max = (1 << 23) - 1
    if group == 0:
        return [0] * LANES
    if group == 1:
        directed = [s24_min, s24_max, 0, 1, -1, 2, -2, 3, -3,
                    32768, -32768, 65536, -65536, 131072, -131072]
        return directed + [((lane + 1) * (row + 3) * 65537) % (1 << 23)
                           - (1 << 22)
                           for lane in range(LANES-len(directed))]
    if group == 2:
        magnitude = min(s24_max, (row + 1) * (1 << 18))
        return [magnitude if lane & 1 else -magnitude for lane in range(LANES)]
    if group == 3:
        constant = (row - 4) * 4096
        return [constant] * LANES
    sigma = float(1 << (11 + ((group + row) % 10)))
    if group % 11 == 0:
        raw = rng.standard_t(df=3, size=LANES) * sigma
    else:
        raw = rng.normal(0.0, sigma, size=LANES)
    return [int(value) for value in np.clip(np.rint(raw), s24_min, s24_max)]


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
    rng = np.random.default_rng(SEED)
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

    for group in range(GROUPS):
        input_rows: list[int] = []
        sc_u8_rows: list[int] = []
        sc_meta_rows: list[int] = []
        fp_u8_rows: list[int] = []
        fp16_meta_rows: list[int] = []
        fp32_meta_rows: list[int] = []
        for row in range(ROWS):
            source = build_row(rng, group, row)
            transformed_result = hadamard32_normalized(source)
            transformed = list(transformed_result.values)
            hadamard_saturations += transformed_result.saturation_count
            sc = minmax_a8.quantize_s27(transformed)
            fp_u8, fp_zp, scale_q24, _, _ = native_fp_a8(transformed)
            zero_diff_rows += int(scale_q24 == 0)
            scale_real_q24 = scale_q24 / float(1 << 24)
            scale16_bits = fp16_bits(scale_real_q24)
            scale32_bits = fp32_bits(scale_real_q24)
            scale16 = float(np.asarray([scale16_bits], dtype=np.uint16)
                            .view(np.float16)[0])
            scale32 = float(struct.unpack("<f", struct.pack("<I", scale32_bits))[0])

            input_rows.extend(source)
            sc_u8_rows.extend(sc.values)
            sc_meta_rows.append(sc.metadata)
            fp_u8_rows.extend(fp_u8)
            fp16_meta_rows.append((scale16_bits << 8) | fp_zp)
            fp32_meta_rows.append((scale32_bits << 8) | fp_zp)

            sc_scale = (sc.scale_code / float(1 << sc.scale_shift)
                        if sc.scale_code else 0.0)
            for source_value, sc_q, fp_q in zip(transformed, sc.values, fp_u8):
                reference.append(source_value / float(1 << 16))
                reconstructed_sc.append((sc_q - sc.zero_point) * sc_scale)
                reconstructed_fp16.append((fp_q - fp_zp) * scale16)
                reconstructed_fp32.append((fp_q - fp_zp) * scale32)

        input_records.append(pack(input_rows, 24))
        sc_u8_records.append(pack(sc_u8_rows, 8))
        sc_meta_records.append(pack(sc_meta_rows, 24))
        fp_u8_records.append(pack(fp_u8_rows, 8))
        fp16_meta_records.append(pack(fp16_meta_rows, 24))
        fp32_meta_records.append(pack(fp32_meta_rows, 40))

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "input_s24.mem": (input_records, 1536),
        "expected_sc_u8.mem": (sc_u8_records, 512),
        "expected_sc_meta.mem": (sc_meta_records, 48),
        "expected_fp_u8.mem": (fp_u8_records, 512),
        "expected_fp16_meta.mem": (fp16_meta_records, 48),
        "expected_fp32_meta.mem": (fp32_meta_records, 80),
    }
    for filename, (values, digits) in outputs.items():
        write_mem(OUT / filename, values, digits)

    manifest = {
        "schema": "scalellm_modular_attention_frontend_native_fp_v1",
        "seed": SEED,
        "groups": GROUPS,
        "rows": ROWS,
        "lanes": LANES,
        "input": "8 rows x 32 lanes signed S24 Q8.16",
        "sc_output": "8x32 U8 plus 8x(meta24 zp/code/shift)",
        "fp16_output": "8x32 U8 plus 8x(zp8 + IEEE FP16 scale)",
        "fp32_output": "8x32 U8 plus 8x(zp8 + IEEE FP32 scale)",
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "native_fp_scale":
            "round_even((high-low)*2^8/255) Q24, then fixed-to-float",
        "native_fp_u8":
            "same ideal-Min/Max U8 as SC; independent of ScaleCode",
        "hadamard_saturation_count": hadamard_saturations,
        "zero_diff_rows": zero_diff_rows,
        "accuracy_vs_hadamard_s27_real": {
            "sc": metrics(reconstructed_sc, reference),
            "fp16": metrics(reconstructed_fp16, reference),
            "fp32": metrics(reconstructed_fp32, reference),
        },
        "production_model": str(ROOT / "model" / "fixbit_v2.py"),
        "production_model_sha256": sha256_file(ROOT / "model" / "fixbit_v2.py"),
        "minmax_reference": str(Path(minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(Path(minmax_a8.__file__)),
        "sha256": {filename: sha256_file(OUT / filename)
                   for filename in outputs},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M1_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
    print("PASS: M1 vectors generated")


if __name__ == "__main__":
    main()
