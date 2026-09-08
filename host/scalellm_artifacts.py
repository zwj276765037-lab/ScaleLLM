#!/usr/bin/env python3
"""ScaleCode artifact manifest validation and XDMA staging."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Protocol, Tuple

from .scalellm_hardware import (
    ATTENTION_FORMAT_ID,
    MLP_FORMAT_ID,
    LayerStager,
)
from .scalellm_memory import (
    ATTENTION_BYTES_PER_CHANNEL,
    ATTENTION_META_BYTES,
    LAYER_COUNT,
    MLP_DOWN_BYTES_PER_CHANNEL,
    MLP_DOWN_META_BYTES,
    MLP_GATE_META_BYTES,
    MLP_GATE_UP_BYTES_PER_CHANNEL,
    ROPE_BYTES,
    MemoryRegion,
    matrix_regions,
)
from .scalellm_runtime import RuntimeContractError


MANIFEST_SCHEMA_VERSION = 1
MATRIX_ARTIFACT_SIZES = {
    "attention_c0": ATTENTION_BYTES_PER_CHANNEL,
    "attention_c1": ATTENTION_BYTES_PER_CHANNEL,
    "mlp_gate_up_c0": MLP_GATE_UP_BYTES_PER_CHANNEL,
    "mlp_gate_up_c1": MLP_GATE_UP_BYTES_PER_CHANNEL,
    "mlp_down_c0": MLP_DOWN_BYTES_PER_CHANNEL,
    "mlp_down_c1": MLP_DOWN_BYTES_PER_CHANNEL,
}
METADATA_ARTIFACT_SIZES = {
    "attention_meta": ATTENTION_META_BYTES,
    "mlp_gate_meta": MLP_GATE_META_BYTES,
    "mlp_down_meta": MLP_DOWN_META_BYTES,
}
LAYER_ARTIFACT_SIZES = {
    **MATRIX_ARTIFACT_SIZES,
    **METADATA_ARTIFACT_SIZES,
}


@dataclass(frozen=True)
class ArtifactRecord:
    path: Path
    size: int
    sha256: str

    def verify_hash(self, chunk_bytes: int = 8 << 20) -> None:
        if chunk_bytes <= 0:
            raise ValueError("hash chunk size must be positive")
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            while chunk := stream.read(chunk_bytes):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != self.sha256:
            raise RuntimeContractError(
                f"artifact SHA256 mismatch: {self.path} "
                f"expected={self.sha256} actual={actual}"
            )

    def read_verified(self) -> bytes:
        data = self.path.read_bytes()
        if len(data) != self.size:
            raise RuntimeContractError(
                f"artifact size changed: {self.path} "
                f"expected={self.size} actual={len(data)}"
            )
        actual = hashlib.sha256(data).hexdigest()
        if actual != self.sha256:
            raise RuntimeContractError(
                f"artifact SHA256 mismatch: {self.path} "
                f"expected={self.sha256} actual={actual}"
            )
        return data


@dataclass(frozen=True)
class LayerArtifacts:
    layer_id: int
    artifacts: Mapping[str, ArtifactRecord]


@dataclass(frozen=True)
class ScaleCodeArtifactManifest:
    manifest_path: Path
    model_id: str
    checkpoint_id: str
    checkpoint_sha256: str
    layers: Tuple[LayerArtifacts, ...]
    rope: ArtifactRecord

    @classmethod
    def load(
        cls, manifest_path: str | Path, verify_hashes: bool = True
    ) -> "ScaleCodeArtifactManifest":
        path = Path(manifest_path).resolve(strict=True)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeContractError(
                f"cannot parse artifact manifest {path}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise RuntimeContractError("artifact manifest root must be an object")
        required_top = {
            "schema_version", "model_id", "checkpoint_id",
            "checkpoint_sha256", "layer_count", "attention_format_id",
            "mlp_format_id", "rope", "layers",
        }
        if set(raw) != required_top:
            raise RuntimeContractError(
                f"artifact manifest fields mismatch: "
                f"expected={sorted(required_top)} actual={sorted(raw)}"
            )
        if (type(raw["schema_version"]) is not int or
                raw["schema_version"] != MANIFEST_SCHEMA_VERSION):
            raise RuntimeContractError("unsupported artifact manifest schema")
        if (type(raw["layer_count"]) is not int or
                raw["layer_count"] != LAYER_COUNT):
            raise RuntimeContractError("artifact manifest must contain 32 layers")
        if (type(raw["attention_format_id"]) is not int or
                raw["attention_format_id"] != ATTENTION_FORMAT_ID):
            raise RuntimeContractError("Attention format ID mismatch")
        if (type(raw["mlp_format_id"]) is not int or
                raw["mlp_format_id"] != MLP_FORMAT_ID):
            raise RuntimeContractError("MLP format ID mismatch")
        for key in ("model_id", "checkpoint_id"):
            if not isinstance(raw[key], str) or not raw[key].strip():
                raise RuntimeContractError(f"manifest {key} is empty")
        checkpoint_sha = cls._require_sha(
            raw["checkpoint_sha256"], "checkpoint_sha256"
        )
        root = path.parent
        rope = cls._parse_artifact(root, raw["rope"], ROPE_BYTES, "rope")
        if not isinstance(raw["layers"], list) or len(raw["layers"]) != LAYER_COUNT:
            raise RuntimeContractError("manifest layers must be a 32-item list")

        layers = []
        all_paths = {rope.path}
        for expected_layer, item in enumerate(raw["layers"]):
            if not isinstance(item, dict) or set(item) != {"layer_id", "artifacts"}:
                raise RuntimeContractError(
                    f"layer {expected_layer} manifest shape is invalid"
                )
            if (type(item["layer_id"]) is not int or
                    item["layer_id"] != expected_layer):
                raise RuntimeContractError(
                    f"layer order mismatch: expected={expected_layer} "
                    f"actual={item['layer_id']}"
                )
            artifacts_raw = item["artifacts"]
            if not isinstance(artifacts_raw, dict) or (
                set(artifacts_raw) != set(LAYER_ARTIFACT_SIZES)
            ):
                raise RuntimeContractError(
                    f"layer {expected_layer} artifact keys mismatch"
                )
            artifacts: Dict[str, ArtifactRecord] = {}
            for name, expected_size in LAYER_ARTIFACT_SIZES.items():
                record = cls._parse_artifact(
                    root, artifacts_raw[name], expected_size,
                    f"layer {expected_layer} {name}",
                )
                if record.path in all_paths:
                    raise RuntimeContractError(
                        f"artifact path reused: {record.path}"
                    )
                all_paths.add(record.path)
                artifacts[name] = record
            layers.append(LayerArtifacts(expected_layer, artifacts))

        result = cls(
            manifest_path=path,
            model_id=raw["model_id"],
            checkpoint_id=raw["checkpoint_id"],
            checkpoint_sha256=checkpoint_sha,
            layers=tuple(layers),
            rope=rope,
        )
        if verify_hashes:
            for artifact in result.iter_all_artifacts():
                artifact.verify_hash()
        return result

    @staticmethod
    def _require_sha(value: object, label: str) -> str:
        if not isinstance(value, str) or len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise RuntimeContractError(f"{label} must be lowercase SHA256")
        return value

    @classmethod
    def _parse_artifact(
        cls, root: Path, raw: object, expected_size: int, label: str
    ) -> ArtifactRecord:
        if not isinstance(raw, dict) or set(raw) != {"path", "size", "sha256"}:
            raise RuntimeContractError(f"{label} artifact shape is invalid")
        raw_path = raw["path"]
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise RuntimeContractError(f"{label} path must be nonempty and relative")
        try:
            path = (root / raw_path).resolve(strict=True)
            path.relative_to(root)
        except (OSError, ValueError) as exc:
            raise RuntimeContractError(
                f"{label} path escapes or is missing: {raw_path}"
            ) from exc
        if not path.is_file():
            raise RuntimeContractError(f"{label} is not a regular file: {path}")
        if (type(raw["size"]) is not int or
                raw["size"] != expected_size or
                path.stat().st_size != expected_size):
            raise RuntimeContractError(
                f"{label} size mismatch: expected={expected_size} "
                f"manifest={raw['size']} file={path.stat().st_size}"
            )
        return ArtifactRecord(
            path=path,
            size=expected_size,
            sha256=cls._require_sha(raw["sha256"], f"{label} sha256"),
        )

    def layer_artifact(self, layer_id: int, name: str) -> ArtifactRecord:
        if layer_id not in range(LAYER_COUNT):
            raise ValueError("layer_id must be in 0..31")
        try:
            return self.layers[layer_id].artifacts[name]
        except KeyError as exc:
            raise ValueError(f"unknown layer artifact {name}") from exc

    def iter_all_artifacts(self) -> Iterable[ArtifactRecord]:
        yield self.rope
        for layer in self.layers:
            yield from layer.artifacts.values()

    def iter_matrix_loads(
        self,
    ) -> Iterable[Tuple[MemoryRegion, ArtifactRecord]]:
        region_by_name = {region.name: region for region in matrix_regions()}
        for layer in self.layers:
            for name in MATRIX_ARTIFACT_SIZES:
                stem, channel_text = name.rsplit("_c", 1)
                region_name = f"{stem}_layer{layer.layer_id:02d}_c{channel_text}"
                yield region_by_name[region_name], layer.artifacts[name]


class XdmaDataSession(Protocol):
    def h2c_write_local(
        self, channel: int, data: bytes, local_offset: int, chunk_bytes: int
    ) -> int:
        """Write one channel-local artifact through XDMA."""


class XdmaReadSession(Protocol):
    def c2h_read_local(
        self, channel: int, size: int, local_offset: int, chunk_bytes: int
    ) -> bytes:
        """Read one channel-local range through XDMA."""


class XdmaLayerStager(LayerStager):
    def __init__(
        self, session: XdmaDataSession, manifest: ScaleCodeArtifactManifest,
        chunk_bytes: int = 4 << 20,
    ) -> None:
        if chunk_bytes <= 0:
            raise ValueError("XDMA chunk size must be positive")
        self.session = session
        self.manifest = manifest
        self.chunk_bytes = chunk_bytes

    def _write(self, artifact: ArtifactRecord, local_base: int) -> None:
        data = artifact.read_verified()
        written = self.session.h2c_write_local(
            0, data, local_base, self.chunk_bytes
        )
        if written != len(data):
            raise RuntimeContractError(
                f"short XDMA staging write for {artifact.path}: {written}"
            )

    def stage_attention(
        self, layer_id: int, local_base: int, expected_bytes: int
    ) -> None:
        artifact = self.manifest.layer_artifact(layer_id, "attention_meta")
        if artifact.size != expected_bytes:
            raise RuntimeContractError("Attention metadata size contract drifted")
        self._write(artifact, local_base)

    def stage_mlp(
        self, layer_id: int, bank: int, gate_local_base: int,
        gate_bytes: int, down_local_base: int, down_bytes: int
    ) -> None:
        if bank not in (0, 1):
            raise ValueError("MLP metadata bank must be 0 or 1")
        gate = self.manifest.layer_artifact(layer_id, "mlp_gate_meta")
        down = self.manifest.layer_artifact(layer_id, "mlp_down_meta")
        if gate.size != gate_bytes or down.size != down_bytes:
            raise RuntimeContractError("MLP metadata size contract drifted")
        self._write(gate, gate_local_base)
        self._write(down, down_local_base)

    def stage_rope(self, local_base: int, expected_bytes: int) -> None:
        if self.manifest.rope.size != expected_bytes:
            raise RuntimeContractError("RoPE size contract drifted")
        self._write(self.manifest.rope, local_base)


def preload_all_matrices(
    session: XdmaDataSession, manifest: ScaleCodeArtifactManifest,
    chunk_bytes: int = 4 << 20,
) -> int:
    if chunk_bytes <= 0:
        raise ValueError("XDMA chunk size must be positive")
    total = 0
    for region, artifact in manifest.iter_matrix_loads():
        data = artifact.read_verified()
        written = session.h2c_write_local(
            region.channel, data, region.local_start, chunk_bytes
        )
        if written != region.size:
            raise RuntimeContractError(
                f"short matrix preload for {artifact.path}: {written}"
            )
        total += written
    return total


def verify_resident_matrix_samples(
    session: XdmaReadSession, manifest: ScaleCodeArtifactManifest,
    sample_bytes: int = 4096, chunk_bytes: int = 1 << 20,
) -> dict:
    """Compare the head and tail of every resident matrix artifact."""
    if sample_bytes <= 0 or chunk_bytes <= 0:
        raise ValueError("readback sample/chunk sizes must be positive")
    comparisons = 0
    verified_bytes = 0
    digest = hashlib.sha256()
    channels = set()
    for region, artifact in manifest.iter_matrix_loads():
        if sample_bytes > artifact.size:
            raise ValueError(
                f"readback sample exceeds artifact size: {artifact.path}"
            )
        channels.add(region.channel)
        offsets = (0, artifact.size - sample_bytes)
        with artifact.path.open("rb") as stream:
            for artifact_offset in dict.fromkeys(offsets):
                stream.seek(artifact_offset)
                expected = stream.read(sample_bytes)
                if len(expected) != sample_bytes:
                    raise RuntimeContractError(
                        f"short artifact sample read: {artifact.path}"
                    )
                actual = session.c2h_read_local(
                    region.channel, sample_bytes,
                    region.local_start + artifact_offset, chunk_bytes,
                )
                if actual != expected:
                    raise RuntimeContractError(
                        "resident matrix sampled readback mismatch: "
                        f"artifact={artifact.path} channel={region.channel} "
                        f"offset=0x{artifact_offset:x}"
                    )
                digest.update(region.channel.to_bytes(1, "little"))
                digest.update(region.local_start.to_bytes(4, "little"))
                digest.update(artifact_offset.to_bytes(4, "little"))
                digest.update(actual)
                comparisons += 1
                verified_bytes += len(actual)
    if channels != {0, 1}:
        raise RuntimeContractError(
            f"matrix sampled readback did not cover both DDR channels: {channels}"
        )
    return {
        "status": "PASS",
        "artifact_count": sum(1 for _ in manifest.iter_matrix_loads()),
        "comparisons": comparisons,
        "verified_bytes": verified_bytes,
        "sample_bytes": sample_bytes,
        "sha256": digest.hexdigest(),
    }
