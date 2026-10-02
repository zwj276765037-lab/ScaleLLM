#!/usr/bin/env python3
"""Generate the M01 frontend/cache workload from real attention inputs."""

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
DEFAULT_CAPTURE = (
    EXPERIMENT_ROOT / "experiment/03_attention_rope" /
    "data_trace_projection_input"
)
DEFAULT_OUTPUT = MODULE / "data_trace"
CAPTURE_SCRIPT = (
    EXPERIMENT_ROOT / "experiment/03_attention_rope/model" /
    "capture_trace_projection_inputs.py"
)
CAPTURE_VERIFIER = (
    EXPERIMENT_ROOT / "experiment/03_attention_rope/model" /
    "verify_trace_projection_inputs.py"
)
ROWS = 8
GROUPS = 128
LANES = 32
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
ROW_COORDINATES = (
    (0, 0, 0),
    (0, 0, 64),
    (0, 15, 31),
    (0, 31, 127),
    (1, 0, 1),
    (1, 15, 63),
    (1, 31, 95),
    (1, 31, 111),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE)
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


def load_capture(capture: Path) -> tuple[dict[str, Any], dict[tuple[int, int], np.ndarray]]:
    capture = capture.resolve(strict=True)
    manifest_path = capture / "manifest.json"
    expected = (capture / "MANIFEST_SHA256").read_text(
        encoding="ascii").split()[0]
    if sha256_file(manifest_path) != expected:
        raise AssertionError("M01 projection-input capture manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") !=
            "scalellm_modular_m03_projection_input_trace_v1" or
            manifest.get("samples") != [0, 1] or
            manifest.get("layers") != [0, 15, 31]):
        raise AssertionError("M01 projection-input capture contract mismatch")
    if (Path(manifest["capture_script"]).resolve() !=
            CAPTURE_SCRIPT.resolve() or
            sha256_file(CAPTURE_SCRIPT) != manifest["capture_script_sha256"]):
        raise AssertionError("M01 projection-input capture script changed")
    arrays: dict[tuple[int, int], np.ndarray] = {}
    for record in manifest["files"]:
        path = capture / record["file"]
        if (path.stat().st_size != record["bytes"] or
                sha256_file(path) != record["file_sha256"]):
            raise AssertionError(f"M01 capture file changed: {path}")
        bits = np.load(path, allow_pickle=False)
        if (bits.shape != (128, 4096) or bits.dtype != np.uint16 or
                payload_hash(bits) != record["payload_sha256"]):
            raise AssertionError(f"M01 capture payload changed: {path}")
        arrays[(record["sample"], record["layer"])] = \
            bf16_bits_to_fp32(bits)
    if len(arrays) != 6:
        raise AssertionError("M01 capture tensor count mismatch")
    return manifest, arrays


def write_mem(path: Path, values: list[int], digits: int) -> dict[str, Any]:
    base.write_mem(path, values, digits)
    return {
        "records": len(values),
        "hex_digits": digits,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    args = parse_args()
    capture_dir = args.capture_dir.resolve(strict=True)
    subprocess.run([
        sys.executable, str(CAPTURE_VERIFIER),
        "--capture-dir", str(capture_dir),
    ], check=True)
    capture_manifest, arrays = load_capture(capture_dir)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    raw_rows = np.stack([
        arrays[(sample, layer)][token]
        for sample, layer, token in ROW_COORDINATES
    ])
    if raw_rows.shape != (ROWS, 4096) or not np.all(np.isfinite(raw_rows)):
        raise AssertionError("M01 selected attention rows are invalid")
    scaled = np.rint(raw_rows.astype(np.float64) * (1 << 16))
    fixed_rows = np.clip(scaled, S24_MIN, S24_MAX).astype(np.int64)
    input_s24_saturation = int(np.count_nonzero(fixed_rows != scaled))

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
    sc_zero_scale_rows = 0
    fp_zero_diff_rows = 0
    pre_quant_clip_lanes = 0

    for group in range(GROUPS):
        input_values: list[int] = []
        sc_u8_values: list[int] = []
        sc_meta_values: list[int] = []
        fp_u8_values: list[int] = []
        fp16_meta_values: list[int] = []
        fp32_meta_values: list[int] = []
        for row in range(ROWS):
            source = fixed_rows[
                row, group*LANES:(group+1)*LANES].tolist()
            transformed_result = base.hadamard32_normalized(source)
            transformed = list(transformed_result.values)
            hadamard_saturations += transformed_result.saturation_count
            sc = base.minmax_a8.quantize_s27(transformed)
            fp_u8, fp_zp, scale_q24, fp_low, fp_high = \
                base.native_fp_a8(transformed)
            sc_zero_scale_rows += int(sc.scale_code == 0)
            fp_zero_diff_rows += int(scale_q24 == 0)
            pre_quant_clip_lanes += sum(
                value < sc.low or value > sc.high for value in transformed)
            if (fp_low, fp_high) != (sc.low, sc.high):
                raise AssertionError("M01 SC/FP raw Min/Max bounds diverged")

            scale_real_q24 = scale_q24 / float(1 << 24)
            scale16_bits = base.fp16_bits(scale_real_q24)
            scale32_bits = base.fp32_bits(scale_real_q24)
            scale16 = float(np.asarray(
                [scale16_bits], dtype=np.uint16).view(np.float16)[0])
            scale32 = float(np.asarray(
                [scale32_bits], dtype=np.uint32).view(np.float32)[0])
            sc_scale = (sc.scale_code / float(1 << sc.scale_shift)
                        if sc.scale_code else 0.0)

            input_values.extend(source)
            sc_u8_values.extend(sc.values)
            sc_meta_values.append(sc.metadata)
            fp_u8_values.extend(fp_u8)
            fp16_meta_values.append((scale16_bits << 8) | fp_zp)
            fp32_meta_values.append((scale32_bits << 8) | fp_zp)
            for transformed_value, sc_value, fp_value in zip(
                    transformed, sc.values, fp_u8, strict=True):
                reference.append(transformed_value / float(1 << 16))
                reconstructed_sc.append(
                    (sc_value - sc.zero_point) * sc_scale)
                reconstructed_fp16.append((fp_value - fp_zp) * scale16)
                reconstructed_fp32.append((fp_value - fp_zp) * scale32)

        input_records.append(base.pack(input_values, 24))
        sc_u8_records.append(base.pack(sc_u8_values, 8))
        sc_meta_records.append(base.pack(sc_meta_values, 24))
        fp_u8_records.append(base.pack(fp_u8_values, 8))
        fp16_meta_records.append(base.pack(fp16_meta_values, 24))
        fp32_meta_records.append(base.pack(fp32_meta_values, 40))

    outputs = {
        "input_s24.mem": (input_records, 1536),
        "expected_sc_u8.mem": (sc_u8_records, 512),
        "expected_sc_meta.mem": (sc_meta_records, 48),
        "expected_fp_u8.mem": (fp_u8_records, 512),
        "expected_fp16_meta.mem": (fp16_meta_records, 48),
        "expected_fp32_meta.mem": (fp32_meta_records, 80),
    }
    files = {
        name: write_mem(output / name, values, digits)
        for name, (values, digits) in outputs.items()
    }
    rows_path = output / "trace_rows.csv"
    with rows_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("row", "sample", "layer", "token",
                                "source_tensor", "source_payload_sha256"))
        writer.writeheader()
        for row, (sample, layer, token) in enumerate(ROW_COORDINATES):
            source = next(record for record in capture_manifest["files"]
                          if record["sample"] == sample and
                          record["layer"] == layer)
            writer.writerow({
                "row": row,
                "sample": sample,
                "layer": layer,
                "token": token,
                "source_tensor": source["file"],
                "source_payload_sha256": source["payload_sha256"],
            })
    files[rows_path.name] = {
        "records": ROWS,
        "hex_digits": 0,
        "bytes": rows_path.stat().st_size,
        "sha256": sha256_file(rows_path),
    }

    generator = Path(__file__).resolve()
    base_model = Path(base.__file__).resolve()
    production_model = SCALELLM_ROOT / "model/fixbit_v2.py"
    manifest = {
        "schema": "scalellm_modular_m01_attention_frontend_real_trace_v1",
        "rows": ROWS,
        "groups": GROUPS,
        "lanes": LANES,
        "bundles": GROUPS,
        "coordinates": [
            {"row": row, "sample": sample, "layer": layer, "token": token}
            for row, (sample, layer, token) in enumerate(ROW_COORDINATES)
        ],
        "comparison_boundary": (
            "common 8x32 S24 projection inputs; production fixed Hadamard; "
            "raw-Min/Max SC ScaleCode versus native FP affine A8 scale"),
        "activation_quantization_contract":
            "raw group32 Min/Max including zero; ideal-scale U8/zp; "
            "round-to-nearest ties-to-even; no pre-quantization clipping",
        "projection_input_capture": str(capture_dir),
        "projection_input_manifest_sha256": sha256_file(
            capture_dir / "manifest.json"),
        "source_tensors": capture_manifest["files"],
        "input_s24_saturation": input_s24_saturation,
        "hadamard_saturation_count": hadamard_saturations,
        "sc_zero_scale_rows": sc_zero_scale_rows,
        "fp_zero_diff_rows": fp_zero_diff_rows,
        "pre_quant_clip_lanes": pre_quant_clip_lanes,
        "accuracy_vs_common_hadamard_s27_real": {
            "sc": base.metrics(reconstructed_sc, reference),
            "fp16": base.metrics(reconstructed_fp16, reference),
            "fp32": base.metrics(reconstructed_fp32, reference),
        },
        "files": dict(sorted(files.items())),
        "generator_sha256": sha256_file(generator),
        "base_model": str(base_model),
        "base_model_sha256": sha256_file(base_model),
        "production_model": str(production_model.resolve()),
        "production_model_sha256": sha256_file(production_model),
        "minmax_reference": str(Path(base.minmax_a8.__file__).resolve()),
        "minmax_reference_sha256": sha256_file(
            Path(base.minmax_a8.__file__)),
        "capture_script": str(CAPTURE_SCRIPT.resolve()),
        "capture_script_sha256": sha256_file(CAPTURE_SCRIPT),
        "capture_verifier": str(CAPTURE_VERIFIER.resolve()),
        "capture_verifier_sha256": sha256_file(CAPTURE_VERIFIER),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "M01_TRACE_VECTOR_PASS "
        f"files={len(files)+1} rows={ROWS} groups={GROUPS} lanes={LANES} "
        f"source_tensors={len(capture_manifest['files'])} "
        f"manifest_sha256={sha256_file(manifest_path)}")


if __name__ == "__main__":
    main()
