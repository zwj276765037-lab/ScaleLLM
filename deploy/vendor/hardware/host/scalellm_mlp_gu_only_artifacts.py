"""Read-only strict schema2/schema3 adapter; runtime v7 is not weight ABI."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .scalellm_artifacts import (ScaleCodeArtifactManifest, LayerArtifacts,
                                 LAYER_ARTIFACT_SIZES, MODEL_ID, ROPE_BYTES)
from .scalellm_hardware import ATTENTION_ABI, ATTENTION_FORMAT_ID, MLP_FORMAT_ID
from .scalellm_runtime import RuntimeContractError
from .scalellm_mlp_gu_only import DownWeights
from .scalellm_mlp_gu_only_abi import IDS


def normalize_weight_manifest_header(raw):
    """Validate exact fields and normalize legacy v5 weight identity in memory."""
    common = {"schema_version", "model_id", "checkpoint_id", "checkpoint_sha256",
              "layer_count", "attention_format_id", "attention_abi", "mlp_format_id",
              "rope", "layers"}
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int:
        raise RuntimeContractError("artifact schema must be2 or3")
    version = raw["schema_version"]
    if version == 2:
        if set(raw) != common | {"mlp_abi"} or type(raw.get("mlp_abi")) is not int or raw["mlp_abi"] != 0x00050000:
            raise RuntimeContractError("schema2 requires original v5 weight ABI and exact fields")
    elif version == 3:
        if set(raw) != common | {"mlp_weight_layout_id"} or type(raw.get("mlp_weight_layout_id")) is not int or raw["mlp_weight_layout_id"] != IDS["weight_layout"]:
            raise RuntimeContractError("schema3 requires original W4F5 layout and exact fields")
    else:
        raise RuntimeContractError("unsupported artifact schema")
    for name, expected in (("layer_count", 32), ("attention_format_id", ATTENTION_FORMAT_ID),
                           ("attention_abi", ATTENTION_ABI), ("mlp_format_id", MLP_FORMAT_ID)):
        if type(raw[name]) is not int or raw[name] != expected:
            raise RuntimeContractError(f"artifact {name} mismatch")
    if raw["model_id"] != MODEL_ID:
        raise RuntimeContractError("artifact model ID mismatch")
    sha = ScaleCodeArtifactManifest._require_sha(raw["checkpoint_sha256"], "checkpoint_sha256")
    if raw["checkpoint_id"] != sha:
        raise RuntimeContractError("checkpoint identity mismatch")
    return {"schema_version": version, "weight_layout_id": IDS["weight_layout"]}


@dataclass(frozen=True)
class GuOnlyArtifactManifest:
    original: ScaleCodeArtifactManifest
    schema_version: int
    manifest_sha256: str
    weight_layout_id: int = IDS["weight_layout"]

    @classmethod
    def load(cls, path, *, verify_hashes=True):
        """Strict paths/sizes/order always; all hashes by default, original bytes unchanged."""
        path = Path(path).resolve(strict=True)
        payload = path.read_bytes()
        try:
            raw = json.loads(payload)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeContractError("cannot parse artifact manifest") from exc
        identity = normalize_weight_manifest_header(raw)
        # Reuse original strict path/record parser and fixed artifact sizes.
        rope = ScaleCodeArtifactManifest._parse_artifact(path.parent, raw["rope"], ROPE_BYTES, "rope")
        if not isinstance(raw["layers"], list) or len(raw["layers"]) != 32:
            raise RuntimeContractError("manifest must contain exactly32 layers")
        layers, paths = [], {rope.path}
        for layer, item in enumerate(raw["layers"]):
            if not isinstance(item, dict) or set(item) != {"layer_id", "artifacts"} or type(item["layer_id"]) is not int or item["layer_id"] != layer:
                raise RuntimeContractError("artifact layer order/identity mismatch")
            records = item["artifacts"]
            if not isinstance(records, dict) or set(records) != set(LAYER_ARTIFACT_SIZES):
                raise RuntimeContractError("artifact names mismatch")
            parsed = {}
            for name, size in LAYER_ARTIFACT_SIZES.items():
                record = ScaleCodeArtifactManifest._parse_artifact(path.parent, records[name], size, f"layer{layer}:{name}")
                if record.path in paths:
                    raise RuntimeContractError("artifact path reused")
                paths.add(record.path)
                parsed[name] = record
            layers.append(LayerArtifacts(layer, parsed))
        original = ScaleCodeArtifactManifest(path, raw["model_id"], raw["checkpoint_id"],
                                             raw["checkpoint_sha256"], tuple(layers), rope)
        if verify_hashes:
            for record in original.iter_all_artifacts():
                record.verify_hash()
        return cls(original, identity["schema_version"], hashlib.sha256(payload).hexdigest())

    def down_weights(self, layer):
        if type(layer) is not int or not 0 <= layer < 32:
            raise RuntimeContractError("Down layer must be in0..31")
        records = self.original.layers[layer].artifacts
        # Even a catalog opened with verify_hashes=False cannot bypass the
        # production Down read's independent strict size/SHA verification.
        return DownWeights.from_artifact_records(records["mlp_down_c0"], records["mlp_down_c1"],
                                                  records["mlp_down_meta"], layer_id=layer)
