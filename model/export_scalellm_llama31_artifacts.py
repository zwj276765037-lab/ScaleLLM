#!/usr/bin/env python3
"""Stream a real Llama-3.1-8B checkpoint into the frozen V5 DDR ABI."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from typing import Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = Path(__file__).resolve().parents[3] / (
    "configs/models/Llama-3.1-8B"
)
DEFAULT_OUTPUT = ROOT / "artifacts/llama31_8b_scalellm_v5"

LAYERS = 32
HIDDEN = 4096
INTERMEDIATE = 14336
HEADS = 32
KV_HEADS = 8
HEAD_DIM = 128
VOCAB_SIZE = 128256
GROUP = 32
HIDDEN_GROUPS = HIDDEN // GROUP
INTERMEDIATE_GROUPS = INTERMEDIATE // GROUP
COLS = 16
ATTENTION_TILES = 640
ATTENTION_RECORDS = ATTENTION_TILES * HIDDEN_GROUPS
GATE_UP_TILES = 2 * INTERMEDIATE // COLS
GATE_UP_RECORDS = GATE_UP_TILES * HIDDEN_GROUPS
DOWN_TILES = HIDDEN // COLS
DOWN_RECORDS = INTERMEDIATE_GROUPS * DOWN_TILES
ATTENTION_CHANNEL_BYTES = ATTENTION_RECORDS * 256
ATTENTION_META_BYTES = ATTENTION_RECORDS * 32
MLP_GATE_CHANNEL_BYTES = GATE_UP_RECORDS * 128
MLP_GATE_META_BYTES = GATE_UP_RECORDS * 32
MLP_DOWN_CHANNEL_BYTES = DOWN_RECORDS * 128
MLP_DOWN_META_BYTES = DOWN_RECORDS * 32
ROPE_BYTES = 1024 * 8

ATTENTION_FORMAT_ID = 0x4838_4103
MLP_FORMAT_ID = 0x4838_4605
SCHEMA_VERSION = 1


def sha256_file(path: Path, chunk_bytes: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk_bytes):
            digest.update(block)
    return digest.hexdigest()


class SafeTensorNumpy:
    """Strict read-only safetensors memory map with native BF16 conversion."""

    _DTYPES = {
        "BF16": "<u2", "F32": "<f4", "F16": "<f2", "I8": "i1",
        "U8": "u1", "I16": "<i2", "U16": "<u2", "I32": "<i4",
        "U32": "<u4", "I64": "<i8", "U64": "<u8",
    }

    def __init__(self, path: Path) -> None:
        self.path = path.resolve(strict=True)
        with self.path.open("rb") as stream:
            header_bytes = stream.read(8)
            if len(header_bytes) != 8:
                raise ValueError(f"truncated safetensors header: {self.path}")
            header_length = struct.unpack("<Q", header_bytes)[0]
            if header_length <= 0 or header_length > (64 << 20):
                raise ValueError(f"invalid safetensors header length: {header_length}")
            raw_header = stream.read(header_length)
            if len(raw_header) != header_length:
                raise ValueError(f"truncated safetensors JSON: {self.path}")
        self.header = json.loads(raw_header)
        if not isinstance(self.header, dict):
            raise ValueError("safetensors header must be an object")
        self.data_offset = 8 + header_length

    def info(self, name: str) -> dict:
        info = self.header.get(name)
        if not isinstance(info, dict) or name == "__metadata__":
            raise KeyError(name)
        if set(info) != {"dtype", "shape", "data_offsets"}:
            raise ValueError(f"unexpected safetensors entry shape for {name}")
        return info

    def raw(self, name: str) -> np.memmap:
        info = self.info(name)
        try:
            dtype = np.dtype(self._DTYPES[info["dtype"]])
        except KeyError as exc:
            raise ValueError(
                f"unsupported safetensors dtype {info['dtype']}"
            ) from exc
        shape = tuple(int(value) for value in info["shape"])
        start, end = (int(value) for value in info["data_offsets"])
        expected = math.prod(shape) * dtype.itemsize
        if start < 0 or end - start != expected:
            raise ValueError(f"invalid safetensors extent for {name}")
        if self.data_offset + end > self.path.stat().st_size:
            raise ValueError(f"safetensors extent exceeds {self.path}")
        return np.memmap(
            self.path, mode="r", dtype=dtype,
            offset=self.data_offset + start, shape=shape, order="C",
        )

    def float32(self, name: str, rows=None, columns=None) -> np.ndarray:
        info = self.info(name)
        selected = self.raw(name)
        if rows is not None:
            selected = selected[rows]
        if columns is not None:
            selected = selected[..., columns]
        if info["dtype"] == "BF16":
            words = np.asarray(selected, dtype=np.uint32)
            return (words << np.uint32(16)).view(np.float32)
        return np.asarray(selected, dtype=np.float32)


class LlamaCheckpoint:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir.resolve(strict=True)
        self.config_path = self.model_dir / "config.json"
        self.index_path = self.model_dir / "model.safetensors.index.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.weight_map = index.get("weight_map")
        if not isinstance(self.weight_map, dict):
            raise ValueError("checkpoint index has no weight_map")
        self._validate_config()
        self._readers: dict[str, SafeTensorNumpy] = {}

    def _validate_config(self) -> None:
        exact = {
            "hidden_size": HIDDEN,
            "intermediate_size": INTERMEDIATE,
            "num_hidden_layers": LAYERS,
            "num_attention_heads": HEADS,
            "num_key_value_heads": KV_HEADS,
            "vocab_size": VOCAB_SIZE,
        }
        for name, expected in exact.items():
            if type(self.config.get(name)) is not int or (
                self.config[name] != expected
            ):
                raise ValueError(
                    f"checkpoint {name} must be {expected}, "
                    f"got {self.config.get(name)!r}"
                )
        if self.config.get("architectures") != ["LlamaForCausalLM"]:
            raise ValueError("checkpoint must be LlamaForCausalLM")
        if float(self.config.get("rms_norm_eps", 0.0)) != 1e-5:
            raise ValueError("checkpoint rms_norm_eps must be 1e-5")

    def _reader(self, tensor: str) -> SafeTensorNumpy:
        try:
            relative = self.weight_map[tensor]
        except KeyError as exc:
            raise KeyError(f"checkpoint tensor is missing: {tensor}") from exc
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError(f"invalid checkpoint shard path: {relative!r}")
        path = (self.model_dir / relative).resolve(strict=True)
        try:
            path.relative_to(self.model_dir)
        except ValueError as exc:
            raise ValueError(f"checkpoint shard escapes model directory: {path}") from exc
        if relative not in self._readers:
            self._readers[relative] = SafeTensorNumpy(path)
        return self._readers[relative]

    def float32(self, tensor: str, rows=None, columns=None) -> np.ndarray:
        return self._reader(tensor).float32(tensor, rows, columns)

    @property
    def shard_paths(self) -> tuple[Path, ...]:
        return tuple(sorted({
            (self.model_dir / relative).resolve(strict=True)
            for relative in self.weight_map.values()
        }))

    def source_identity(self) -> tuple[str, dict]:
        records = []
        for path in (self.config_path, self.index_path, *self.shard_paths):
            records.append({
                "path": path.relative_to(self.model_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
        encoded = json.dumps(
            records, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest(), {
            "schema": "scalellm_checkpoint_identity_v1",
            "files": records,
        }


class HashedWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.temporary = path.with_name(path.name + ".partial")
        self.stream = self.temporary.open("wb")
        self.digest = hashlib.sha256()
        self.size = 0

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.stream.write(data)
        self.digest.update(data)
        self.size += len(data)

    def finish(self, expected_size: int) -> dict:
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        if self.size != expected_size:
            self.temporary.unlink(missing_ok=True)
            raise RuntimeError(
                f"artifact size mismatch for {self.path.name}: "
                f"expected={expected_size} actual={self.size}"
            )
        self.temporary.replace(self.path)
        return {
            "path": self.path.as_posix(),
            "size": self.size,
            "sha256": self.digest.hexdigest(),
        }

    def abort(self) -> None:
        if not self.stream.closed:
            self.stream.close()
        self.temporary.unlink(missing_ok=True)


def round_away(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    return np.copysign(
        np.floor(np.abs(source) + 0.5), source
    ).astype(np.int64)


def fwht32_normalized(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=np.float32).copy()
    if result.shape[-1] != GROUP:
        raise ValueError("Hadamard input must end in 32 lanes")
    distance = 1
    while distance < GROUP:
        shaped = result.reshape(*result.shape[:-1], -1, 2 * distance)
        low = shaped[..., :distance].copy()
        high = shaped[..., distance:2 * distance].copy()
        shaped[..., :distance] = low + high
        shaped[..., distance:2 * distance] = low - high
        result = shaped.reshape(result.shape)
        distance *= 2
    return result * np.float32(1.0 / math.sqrt(GROUP))


def encode_scales(scales: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source = np.asarray(scales, dtype=np.float64)
    if np.any(~np.isfinite(source)) or np.any(source < 0):
        raise ValueError("ScaleCode scales must be finite and non-negative")
    codes = np.zeros(source.shape, dtype=np.uint8)
    shifts = np.zeros(source.shape, dtype=np.uint8)
    active = source > 0
    selected = source[active]
    shift = np.floor(np.log2(255.0 / selected)).astype(np.int64)
    shift = np.clip(shift, 0, 63)
    code = np.floor(np.ldexp(selected, shift) + 0.5).astype(np.int64)
    while np.any(code > 255):
        adjust = code > 255
        if np.any(shift[adjust] == 0):
            raise ValueError("ScaleCode value is not representable")
        shift[adjust] -= 1
        code[adjust] = np.floor(
            np.ldexp(selected[adjust], shift[adjust]) + 0.5
        ).astype(np.int64)
    if np.any(code < 1):
        raise ValueError("ScaleCode underflow")
    codes[active] = code.astype(np.uint8)
    shifts[active] = shift.astype(np.uint8)
    decoded = np.ldexp(codes.astype(np.float64), -shifts.astype(np.int64))
    return codes, shifts, decoded.astype(np.float32)


def quantize_folded_rows(
    source_out_in: np.ndarray, weight_bits: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source = np.asarray(source_out_in, dtype=np.float32)
    if source.ndim != 2 or source.shape[1] % GROUP:
        raise ValueError("weight rows must have a group32 input dimension")
    qmax = (1 << (weight_bits - 1)) - 1
    qmin = -qmax if weight_bits == 8 else -(qmax + 1)
    folded = fwht32_normalized(
        source.reshape(source.shape[0], -1, GROUP)
    )
    target = np.max(np.abs(folded), axis=-1) / np.float32(qmax)
    codes, shifts, decoded = encode_scales(target)
    divisor = np.where(codes == 0, np.float32(1.0), decoded)
    quantized = np.clip(
        round_away(folded / divisor[..., None]), qmin, qmax
    ).astype(np.int8)
    if np.any((codes == 0) & np.any(quantized != 0, axis=-1)):
        raise AssertionError("zero ScaleCode group has nonzero weights")
    return quantized, codes, shifts


def pack_attention_meta(codes: np.ndarray, shifts: np.ndarray) -> bytes:
    codes = np.asarray(codes, dtype=np.uint8).reshape(COLS)
    shifts = np.asarray(shifts, dtype=np.uint8).reshape(COLS)
    if np.any(shifts > 63):
        raise ValueError("Attention weight shift exceeds six bits")
    result = np.empty((COLS, 2), dtype=np.uint8)
    result[:, 0] = codes
    result[:, 1] = shifts
    return result.tobytes()


def pack_mlp_meta(codes: np.ndarray, shifts: np.ndarray) -> bytes:
    codes = np.asarray(codes, dtype=np.uint8).reshape(COLS)
    shifts = np.asarray(shifts, dtype=np.uint8).reshape(COLS)
    if np.any(shifts > 63):
        raise ValueError("MLP weight shift exceeds six bits")
    word = 0
    for column, value in enumerate(codes):
        word |= int(value) << (column * 8)
    for column, value in enumerate(shifts):
        word |= int(value) << (128 + column * 6)
    return word.to_bytes(28, "little") + bytes(4)


def pack_w4(values: np.ndarray) -> bytes:
    flat = np.asarray(values, dtype=np.int8).reshape(-1)
    if flat.size % 2 or np.any(flat < -8) or np.any(flat > 7):
        raise ValueError("W4 payload must contain an even number of S4 values")
    nibble = np.bitwise_and(flat.astype(np.int16), 0xF).astype(np.uint8)
    return (nibble[0::2] | (nibble[1::2] << 4)).tobytes()


def interleaved_rope_row_map(heads: int) -> np.ndarray:
    mapping = []
    for head in range(heads):
        base = head * HEAD_DIM
        for index in range(HEAD_DIM // 2):
            mapping.extend((base + index, base + HEAD_DIM // 2 + index))
    return np.asarray(mapping, dtype=np.int64)


def llama3_inv_freq(config: dict) -> np.ndarray:
    inv = 1.0 / (float(config["rope_theta"]) ** (
        np.arange(0, HEAD_DIM, 2, dtype=np.float64) / HEAD_DIM
    ))
    scaling = config["rope_scaling"]
    if scaling.get("rope_type") != "llama3":
        raise ValueError("checkpoint must use Llama-3 RoPE scaling")
    factor = float(scaling["factor"])
    low_factor = float(scaling["low_freq_factor"])
    high_factor = float(scaling["high_freq_factor"])
    original = float(scaling["original_max_position_embeddings"])
    wavelength = 2.0 * math.pi / inv
    low_wavelength = original / low_factor
    high_wavelength = original / high_factor
    smooth = (
        original / wavelength - low_factor
    ) / (high_factor - low_factor)
    smoothed = (1.0 - smooth) * inv / factor + smooth * inv
    return np.where(
        wavelength < high_wavelength, inv,
        np.where(wavelength > low_wavelength, inv / factor, smoothed),
    )


def build_rope(config: dict, query_start: int = 0, rows: int = 16) -> bytes:
    if query_start < 0 or rows != 16:
        raise ValueError("V5 RoPE artifact requires one nonnegative cohort16")
    positions = np.arange(query_start, query_start + rows, dtype=np.float64)
    angles = positions[:, None] * llama3_inv_freq(config)[None, :]
    cos_q16 = np.clip(round_away(np.cos(angles) * 65536.0), -65536, 65536)
    sin_q16 = np.clip(round_away(np.sin(angles) * 65536.0), -65536, 65536)
    records = bytearray()
    for row in range(rows):
        for group in range(4):
            for pair in range(16):
                index = group * 16 + pair
                word = (
                    (int(cos_q16[row, index]) & 0x3FFFF)
                    | ((int(sin_q16[row, index]) & 0x3FFFF) << 18)
                )
                records.extend(word.to_bytes(8, "little"))
    if len(records) != ROPE_BYTES:
        raise AssertionError("RoPE payload size drifted")
    return bytes(records)


def _finish_writers(
    writers: dict[str, HashedWriter], expected: dict[str, int],
    relative_root: Path,
) -> dict:
    output = {}
    for name, writer in writers.items():
        record = writer.finish(expected[name])
        record["path"] = writer.path.relative_to(relative_root).as_posix()
        output[name] = record
    return output


def _abort_writers(writers: Iterable[HashedWriter]) -> None:
    for writer in writers:
        writer.abort()


def export_attention(
    checkpoint: LlamaCheckpoint, layer_id: int, layer_dir: Path,
    artifact_root: Path,
) -> dict:
    writers = {
        "attention_c0": HashedWriter(layer_dir / "attention_c0.bin"),
        "attention_c1": HashedWriter(layer_dir / "attention_c1.bin"),
        "attention_meta": HashedWriter(layer_dir / "attention_meta.bin"),
    }
    prefix = f"model.layers.{layer_id}.self_attn"
    sections = (
        ("q_proj", 4096, interleaved_rope_row_map(HEADS)),
        ("k_proj", 1024, interleaved_rope_row_map(KV_HEADS)),
        ("v_proj", 1024, None),
        ("o_proj", 4096, None),
    )
    try:
        for operation, outputs, permutation in sections:
            name = f"{prefix}.{operation}.weight"
            for output_start in range(0, outputs, COLS):
                hardware_rows = np.arange(output_start, output_start + COLS)
                rows = hardware_rows if permutation is None else (
                    permutation[hardware_rows]
                )
                source = checkpoint.float32(name, rows=rows)
                quantized, codes, shifts = quantize_folded_rows(source, 8)
                for group in range(HIDDEN_GROUPS):
                    writers["attention_c0"].write(
                        quantized[:8, group, :].tobytes()
                    )
                    writers["attention_c1"].write(
                        quantized[8:, group, :].tobytes()
                    )
                    writers["attention_meta"].write(
                        pack_attention_meta(codes[:, group], shifts[:, group])
                    )
        return _finish_writers(writers, {
            "attention_c0": ATTENTION_CHANNEL_BYTES,
            "attention_c1": ATTENTION_CHANNEL_BYTES,
            "attention_meta": ATTENTION_META_BYTES,
        }, artifact_root)
    except BaseException:
        _abort_writers(writers.values())
        raise


def _write_mlp_tile(
    writers: dict[str, HashedWriter], quantized: np.ndarray,
    codes: np.ndarray, shifts: np.ndarray, group_count: int,
) -> None:
    for group in range(group_count):
        writers["c0"].write(pack_w4(quantized[:8, group, :]))
        writers["c1"].write(pack_w4(quantized[8:, group, :]))
        writers["meta"].write(pack_mlp_meta(
            codes[:, group], shifts[:, group]
        ))


def export_mlp(
    checkpoint: LlamaCheckpoint, layer_id: int, layer_dir: Path,
    artifact_root: Path,
) -> dict:
    gate = {
        "c0": HashedWriter(layer_dir / "mlp_gate_up_c0.bin"),
        "c1": HashedWriter(layer_dir / "mlp_gate_up_c1.bin"),
        "meta": HashedWriter(layer_dir / "mlp_gate_meta.bin"),
    }
    down = {
        "c0": HashedWriter(layer_dir / "mlp_down_c0.bin"),
        "c1": HashedWriter(layer_dir / "mlp_down_c1.bin"),
        "meta": HashedWriter(layer_dir / "mlp_down_meta.bin"),
    }
    prefix = f"model.layers.{layer_id}.mlp"
    try:
        # Four consecutive tiles are gate[0:16], up[0:16], gate[16:32],
        # up[16:32] for one 32-wide SwiGLU product group.
        for output_start in range(0, INTERMEDIATE, 2 * COLS):
            row_halves = (
                ("gate_proj", output_start),
                ("up_proj", output_start),
                ("gate_proj", output_start + COLS),
                ("up_proj", output_start + COLS),
            )
            for operation, row_start in row_halves:
                rows = slice(row_start, row_start + COLS)
                source = checkpoint.float32(
                    f"{prefix}.{operation}.weight", rows=rows
                )
                quantized, codes, shifts = quantize_folded_rows(source, 4)
                _write_mlp_tile(
                    gate, quantized, codes, shifts, HIDDEN_GROUPS
                )

        # The down frontend consumes group-major order: one product group is
        # replayed against all 256 output tiles before the next group.
        down_name = f"{prefix}.down_proj.weight"
        for input_start in range(0, INTERMEDIATE, GROUP):
            columns = slice(input_start, input_start + GROUP)
            source = checkpoint.float32(down_name, columns=columns)
            quantized, codes, shifts = quantize_folded_rows(source, 4)
            for output_start in range(0, HIDDEN, COLS):
                rows = slice(output_start, output_start + COLS)
                _write_mlp_tile(
                    down, quantized[rows], codes[rows], shifts[rows], 1
                )

        gate_records = _finish_writers(gate, {
            "c0": MLP_GATE_CHANNEL_BYTES,
            "c1": MLP_GATE_CHANNEL_BYTES,
            "meta": MLP_GATE_META_BYTES,
        }, artifact_root)
        down_records = _finish_writers(down, {
            "c0": MLP_DOWN_CHANNEL_BYTES,
            "c1": MLP_DOWN_CHANNEL_BYTES,
            "meta": MLP_DOWN_META_BYTES,
        }, artifact_root)
        return {
            "mlp_gate_up_c0": gate_records["c0"],
            "mlp_gate_up_c1": gate_records["c1"],
            "mlp_gate_meta": gate_records["meta"],
            "mlp_down_c0": down_records["c0"],
            "mlp_down_c1": down_records["c1"],
            "mlp_down_meta": down_records["meta"],
        }
    except BaseException:
        _abort_writers((*gate.values(), *down.values()))
        raise


def _validate_completed_layer(
    layer_manifest: Path, layer_id: int, checkpoint_sha256: str,
) -> dict | None:
    if not layer_manifest.is_file():
        return None
    try:
        raw = json.loads(layer_manifest.read_text(encoding="ascii"))
        if set(raw) != {
            "schema", "checkpoint_sha256", "layer_id", "artifacts"
        } or raw["schema"] != "scalellm_v5_layer_artifacts_v1" or (
            raw["checkpoint_sha256"] != checkpoint_sha256
        ) or raw["layer_id"] != layer_id:
            return None
        for record in raw["artifacts"].values():
            path = layer_manifest.parents[1] / record["path"]
            if path.stat().st_size != record["size"] or (
                sha256_file(path) != record["sha256"]
            ):
                return None
        return raw["artifacts"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def write_json_atomic(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--start-layer", type=int, default=0)
    parser.add_argument("--end-layer", type=int, default=LAYERS)
    args = parser.parse_args()
    if not 0 <= args.start_layer < args.end_layer <= LAYERS:
        raise SystemExit("layer interval must satisfy 0 <= start < end <= 32")
    if (args.start_layer, args.end_layer) != (0, LAYERS):
        raise SystemExit(
            "partial intervals are diagnostic only; production manifest "
            "requires --start-layer 0 --end-layer 32"
        )

    checkpoint = LlamaCheckpoint(args.model_dir)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_sha256, source_identity = checkpoint.source_identity()
    source_identity["checkpoint_sha256"] = checkpoint_sha256
    write_json_atomic(output / "checkpoint_identity.json", source_identity)

    rope_path = output / "rope.bin"
    rope = build_rope(checkpoint.config)
    rope_path.write_bytes(rope)
    rope_record = {
        "path": "rope.bin", "size": len(rope),
        "sha256": hashlib.sha256(rope).hexdigest(),
    }

    layers = []
    for layer_id in range(LAYERS):
        layer_dir = output / f"layer_{layer_id:02d}"
        layer_dir.mkdir(exist_ok=True)
        layer_manifest = layer_dir / "layer_manifest.json"
        artifacts = _validate_completed_layer(
            layer_manifest, layer_id, checkpoint_sha256
        ) if args.resume else None
        if artifacts is None:
            artifacts = export_attention(
                checkpoint, layer_id, layer_dir, output
            )
            artifacts.update(export_mlp(
                checkpoint, layer_id, layer_dir, output
            ))
            write_json_atomic(layer_manifest, {
                "schema": "scalellm_v5_layer_artifacts_v1",
                "checkpoint_sha256": checkpoint_sha256,
                "layer_id": layer_id,
                "artifacts": artifacts,
            })
        layers.append({"layer_id": layer_id, "artifacts": artifacts})
        print(f"SCALellm_EXPORT_LAYER_PASS layer={layer_id}", flush=True)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "model_id": "meta-llama/Llama-3.1-8B",
        "checkpoint_id": checkpoint_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "layer_count": LAYERS,
        "attention_format_id": ATTENTION_FORMAT_ID,
        "mlp_format_id": MLP_FORMAT_ID,
        "rope": rope_record,
        "layers": layers,
    }
    write_json_atomic(output / "scalecode_manifest.json", manifest)
    print(f"SCALellm_EXPORT_PASS manifest={output / 'scalecode_manifest.json'}")


if __name__ == "__main__":
    main()
