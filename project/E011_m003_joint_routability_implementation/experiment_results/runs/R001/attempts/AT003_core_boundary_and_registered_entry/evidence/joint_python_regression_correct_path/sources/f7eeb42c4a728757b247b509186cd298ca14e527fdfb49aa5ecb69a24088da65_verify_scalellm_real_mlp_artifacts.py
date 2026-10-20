#!/usr/bin/env python3
"""Verify real Llama MLP artifacts against the frozen V5 integer ABI."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

try:
    from .export_scalellm_llama31_artifacts import (
        COLS,
        DOWN_RECORDS,
        GATE_UP_RECORDS,
        GROUP,
        HIDDEN,
        HIDDEN_GROUPS,
        INTERMEDIATE,
        LlamaCheckpoint,
        MODEL_ID,
        quantize_folded_rows,
        sha256_file,
        write_json_atomic,
    )
    from .mlp_fixed import a8w4_group32_two_column
except ImportError:  # Direct execution from HAP/model.
    from export_scalellm_llama31_artifacts import (
        COLS,
        DOWN_RECORDS,
        GATE_UP_RECORDS,
        GROUP,
        HIDDEN,
        HIDDEN_GROUPS,
        INTERMEDIATE,
        LlamaCheckpoint,
        MODEL_ID,
        quantize_folded_rows,
        sha256_file,
        write_json_atomic,
    )
    from mlp_fixed import a8w4_group32_two_column


MLP_CHANNEL_RECORD_BYTES = 128
MLP_META_RECORD_BYTES = 32
GATE_TILES_PER_PRODUCT_GROUP = 4
DOWN_TILES = HIDDEN // COLS

DEFAULT_GATE_RECORDS = (
    0, 127, 128, 255, 256, 383, 384, 511, 512,
    GATE_UP_RECORDS // 2, GATE_UP_RECORDS - 1,
)
DEFAULT_DOWN_RECORDS = (
    0, 255, 256, 511, 512, DOWN_RECORDS // 2, DOWN_RECORDS - 1,
)


@dataclass(frozen=True)
class MLPRecordLocation:
    record: int
    operation: str
    output_start: int
    input_group: int


def gate_record_location(record: int) -> MLPRecordLocation:
    if record not in range(GATE_UP_RECORDS):
        raise ValueError(f"gate/up record must be in 0..{GATE_UP_RECORDS - 1}")
    product_group, within = divmod(
        record, GATE_TILES_PER_PRODUCT_GROUP * HIDDEN_GROUPS
    )
    tile, input_group = divmod(within, HIDDEN_GROUPS)
    operation = "gate_proj" if tile in (0, 2) else "up_proj"
    output_start = product_group * GROUP + (COLS if tile >= 2 else 0)
    return MLPRecordLocation(
        record, operation, output_start, input_group
    )


def down_record_location(record: int) -> MLPRecordLocation:
    if record not in range(DOWN_RECORDS):
        raise ValueError(f"down record must be in 0..{DOWN_RECORDS - 1}")
    input_group, output_tile = divmod(record, DOWN_TILES)
    return MLPRecordLocation(
        record, "down_proj", output_tile * COLS, input_group
    )


def decode_w4_channel_record(raw: bytes) -> np.ndarray:
    if len(raw) != MLP_CHANNEL_RECORD_BYTES:
        raise ValueError("MLP channel record must contain exactly 128 bytes")
    packed = np.frombuffer(raw, dtype=np.uint8)
    nibbles = np.empty(packed.size * 2, dtype=np.uint8)
    nibbles[0::2] = packed & np.uint8(0xF)
    nibbles[1::2] = packed >> np.uint8(4)
    signed = nibbles.astype(np.int8)
    signed[signed >= 8] -= 16
    return signed.reshape(8, GROUP)


def decode_mlp_meta_record(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    if len(raw) != MLP_META_RECORD_BYTES:
        raise ValueError("MLP metadata record must contain exactly 32 bytes")
    if raw[28:] != bytes(4):
        raise ValueError("MLP metadata padding must be zero")
    codes = np.frombuffer(raw[:COLS], dtype=np.uint8).copy()
    shift_word = int.from_bytes(raw[COLS:28], "little")
    shifts = np.asarray(
        [(shift_word >> (6 * column)) & 0x3F for column in range(COLS)],
        dtype=np.uint8,
    )
    return codes, shifts


def _read_record(path: Path, record: int, record_bytes: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(record * record_bytes)
        raw = stream.read(record_bytes)
    if len(raw) != record_bytes:
        raise RuntimeError(
            f"short artifact record: path={path} record={record} "
            f"expected={record_bytes} actual={len(raw)}"
        )
    return raw


def _parse_layer_manifest(
    artifact_root: Path, layer_id: int, verify_hashes: bool,
) -> tuple[str, dict[str, Path], dict[str, str]]:
    root = artifact_root.resolve(strict=True)
    manifest_path = root / f"layer_{layer_id:02d}/layer_manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="ascii"))
    required_top = {"schema", "checkpoint_sha256", "layer_id", "artifacts"}
    if set(raw) != required_top or raw["schema"] != (
        "scalellm_v5_layer_artifacts_v1"
    ) or raw["layer_id"] != layer_id:
        raise RuntimeError(f"invalid layer manifest: {manifest_path}")
    checkpoint_sha = raw["checkpoint_sha256"]
    if not isinstance(checkpoint_sha, str) or len(checkpoint_sha) != 64:
        raise RuntimeError("invalid layer checkpoint SHA256")

    names = (
        "mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta",
        "mlp_down_c0", "mlp_down_c1", "mlp_down_meta",
    )
    expected_sizes = {
        "mlp_gate_up_c0": GATE_UP_RECORDS * MLP_CHANNEL_RECORD_BYTES,
        "mlp_gate_up_c1": GATE_UP_RECORDS * MLP_CHANNEL_RECORD_BYTES,
        "mlp_gate_meta": GATE_UP_RECORDS * MLP_META_RECORD_BYTES,
        "mlp_down_c0": DOWN_RECORDS * MLP_CHANNEL_RECORD_BYTES,
        "mlp_down_c1": DOWN_RECORDS * MLP_CHANNEL_RECORD_BYTES,
        "mlp_down_meta": DOWN_RECORDS * MLP_META_RECORD_BYTES,
    }
    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for name in names:
        try:
            record = raw["artifacts"][name]
            relative = record["path"]
            expected_hash = record["sha256"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"missing {name} artifact record") from exc
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise RuntimeError(f"invalid relative artifact path for {name}")
        path = (root / relative).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"artifact escapes root: {path}") from exc
        expected_size = expected_sizes[name]
        if record.get("size") != expected_size or path.stat().st_size != expected_size:
            raise RuntimeError(f"artifact size mismatch for {name}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise RuntimeError(f"invalid artifact SHA256 for {name}")
        if verify_hashes and sha256_file(path) != expected_hash:
            raise RuntimeError(f"artifact SHA256 mismatch for {name}")
        paths[name] = path
        hashes[name] = expected_hash
    return checkpoint_sha, paths, hashes


def _verify_checkpoint_binding(
    checkpoint: LlamaCheckpoint, artifact_root: Path, checkpoint_sha: str,
) -> None:
    identity_path = artifact_root / "checkpoint_identity.json"
    identity = json.loads(identity_path.read_text(encoding="ascii"))
    actual_sha, actual_identity = checkpoint.source_identity()
    actual_identity["checkpoint_sha256"] = actual_sha
    if actual_sha != checkpoint_sha or identity != actual_identity:
        raise RuntimeError("artifact checkpoint identity does not bind Instruct files")


def _activation_for_record(record: int) -> list[int]:
    return [
        ((lane * 37 + record * 13 + 19) % 511) - 255
        for lane in range(GROUP)
    ]


def _verify_integer_dots(
    activation: list[int], weights: np.ndarray, label: str,
) -> int:
    comparisons = 0
    for column in range(0, COLS, 2):
        packed_dots = a8w4_group32_two_column(
            activation, weights[column], weights[column + 1]
        )
        direct_dots = (
            int(np.dot(
                np.asarray(activation, dtype=np.int64),
                weights[column].astype(np.int64),
            )),
            int(np.dot(
                np.asarray(activation, dtype=np.int64),
                weights[column + 1].astype(np.int64),
            )),
        )
        if packed_dots != direct_dots:
            raise RuntimeError(
                f"A8W4 integer dot mismatch at {label} columns {column}/{column + 1}: "
                f"packed={packed_dots} direct={direct_dots}"
            )
        comparisons += 2
    return comparisons


def _verify_record(
    checkpoint: LlamaCheckpoint, layer_id: int, location: MLPRecordLocation,
    c0_path: Path, c1_path: Path, meta_path: Path,
) -> int:
    input_start = location.input_group * GROUP
    source = checkpoint.float32(
        f"model.layers.{layer_id}.mlp.{location.operation}.weight",
        rows=slice(location.output_start, location.output_start + COLS),
        columns=slice(input_start, input_start + GROUP),
    )
    expected_weights, expected_codes, expected_shifts = quantize_folded_rows(
        source, 4
    )
    expected_weights = expected_weights[:, 0, :]
    expected_codes = expected_codes[:, 0]
    expected_shifts = expected_shifts[:, 0]

    actual_weights = np.concatenate((
        decode_w4_channel_record(_read_record(
            c0_path, location.record, MLP_CHANNEL_RECORD_BYTES
        )),
        decode_w4_channel_record(_read_record(
            c1_path, location.record, MLP_CHANNEL_RECORD_BYTES
        )),
    ))
    actual_codes, actual_shifts = decode_mlp_meta_record(_read_record(
        meta_path, location.record, MLP_META_RECORD_BYTES
    ))
    if not np.array_equal(actual_weights, expected_weights):
        mismatch = np.argwhere(actual_weights != expected_weights)[0]
        row, lane = (int(value) for value in mismatch)
        raise RuntimeError(
            f"W4 mismatch at {location} row={row} lane={lane}: "
            f"artifact={actual_weights[row, lane]} expected={expected_weights[row, lane]}"
        )
    if not np.array_equal(actual_codes, expected_codes):
        raise RuntimeError(f"ScaleCode code mismatch at {location}")
    if not np.array_equal(actual_shifts, expected_shifts):
        raise RuntimeError(f"ScaleCode shift mismatch at {location}")

    activation = _activation_for_record(location.record)
    comparisons = _verify_integer_dots(
        activation, actual_weights,
        f"record={location.record} operation={location.operation}",
    )
    expected_direct = expected_weights.astype(np.int64) @ np.asarray(
        activation, dtype=np.int64
    )
    actual_direct = actual_weights.astype(np.int64) @ np.asarray(
        activation, dtype=np.int64
    )
    if not np.array_equal(actual_direct, expected_direct):
        raise RuntimeError(f"artifact/direct integer projection mismatch at {location}")
    return comparisons + COLS


def verify_layer(
    model_dir: Path, artifact_root: Path, layer_id: int = 0,
    verify_hashes: bool = True,
) -> dict:
    model_dir = model_dir.resolve(strict=True)
    artifact_root = artifact_root.resolve(strict=True)
    if layer_id not in range(32):
        raise ValueError("layer_id must be in 0..31")
    checkpoint_sha, paths, hashes = _parse_layer_manifest(
        artifact_root, layer_id, verify_hashes
    )
    checkpoint = LlamaCheckpoint(model_dir)
    _verify_checkpoint_binding(checkpoint, artifact_root, checkpoint_sha)

    gate_locations = tuple(gate_record_location(record)
                           for record in DEFAULT_GATE_RECORDS)
    down_locations = tuple(down_record_location(record)
                           for record in DEFAULT_DOWN_RECORDS)
    integer_comparisons = 0
    for location in gate_locations:
        integer_comparisons += _verify_record(
            checkpoint, layer_id, location,
            paths["mlp_gate_up_c0"], paths["mlp_gate_up_c1"],
            paths["mlp_gate_meta"],
        )
    for location in down_locations:
        integer_comparisons += _verify_record(
            checkpoint, layer_id, location,
            paths["mlp_down_c0"], paths["mlp_down_c1"],
            paths["mlp_down_meta"],
        )

    evidence = {
        "schema": "scalellm_v5_real_mlp_integer_golden_v1",
        "status": "PASS",
        "model": MODEL_ID,
        "checkpoint_sha256": checkpoint_sha,
        "layer_id": layer_id,
        "weight_bits": 4,
        "group_size": GROUP,
        "channels": 2,
        "artifact_hashes_verified": verify_hashes,
        "artifact_sha256": hashes,
        "gate_up_records": [asdict(item) for item in gate_locations],
        "down_records": [asdict(item) for item in down_locations],
        "integer_comparisons": integer_comparisons,
        "contracts": [
            "Hadamard32-normalized checkpoint rows",
            "gate-low/up-low/gate-high/up-high tile order",
            "down group-major then 256 output tiles",
            "channel0 rows 0..7 and channel1 rows 8..15",
            "low-nibble-first signed W4 payload",
            "16 code8 plus tightly packed 16 shift6 plus zero padding",
            "one-DSP A8W4 two-output-column integer correction",
        ],
    }
    canonical = json.dumps(
        evidence, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    evidence["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-artifact-hashes", action="store_true")
    args = parser.parse_args()
    evidence = verify_layer(
        args.model_dir, args.artifact_root, args.layer,
        verify_hashes=not args.skip_artifact_hashes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, evidence)
    print(
        "SCALELLM_REAL_MLP_INTEGER_GOLDEN_PASS "
        f"layer={args.layer} comparisons={evidence['integer_comparisons']} "
        f"evidence_sha256={evidence['evidence_sha256']}"
    )


if __name__ == "__main__":
    main()
