#!/usr/bin/env python3

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from host.scalellm_artifacts import (
    ArtifactRecord,
    LAYER_ARTIFACT_SIZES,
    MANIFEST_SCHEMA_VERSION,
    MATRIX_ARTIFACT_SIZES,
    LayerArtifacts,
    ScaleCodeArtifactManifest,
    XdmaLayerStager,
    preload_all_matrices,
    verify_resident_matrix_samples,
)
from host.scalellm_hardware import ATTENTION_FORMAT_ID, MLP_FORMAT_ID
from host.scalellm_memory import LAYER_COUNT, MATRIX_BYTES_PER_CHANNEL, ROPE_BYTES
from host.scalellm_runtime import RuntimeContractError


class FakeXdmaSession:
    def __init__(self, short=False, corrupt_read=False):
        self.short = short
        self.corrupt_read = corrupt_read
        self.writes = []
        self.reads = []

    def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
        self.writes.append((channel, local_offset, chunk_bytes, len(data)))
        return len(data) - 1 if self.short else len(data)

    def c2h_read_local(self, channel, size, local_offset, chunk_bytes):
        self.reads.append((channel, local_offset, chunk_bytes, size))
        return (b"\x01" if self.corrupt_read else b"\x00") * size


class SizedPayload:
    def __init__(self, size):
        self.size = size

    def __len__(self):
        return self.size


class ScaleCodeArtifactManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        artifact_dir = cls.root / "artifacts"
        artifact_dir.mkdir()

        def sparse_record(relative_path, size):
            path = cls.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as stream:
                stream.truncate(size)
            return {
                "path": relative_path,
                "size": size,
                "sha256": "0" * 64,
            }

        layers = []
        for layer_id in range(LAYER_COUNT):
            records = {}
            for name, size in LAYER_ARTIFACT_SIZES.items():
                relative = f"artifacts/layer{layer_id:02d}_{name}.bin"
                records[name] = sparse_record(relative, size)
            layers.append({"layer_id": layer_id, "artifacts": records})
        cls.raw = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "model_id": "meta-llama/Llama-3.1-8B",
            "checkpoint_id": "fixture-checkpoint",
            "checkpoint_sha256": "1" * 64,
            "layer_count": LAYER_COUNT,
            "attention_format_id": ATTENTION_FORMAT_ID,
            "mlp_format_id": MLP_FORMAT_ID,
            "rope": sparse_record("artifacts/rope.bin", ROPE_BYTES),
            "layers": layers,
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write_manifest(self, raw, name="manifest.json"):
        path = self.root / name
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def test_loads_exact_32_layer_layout_and_matrix_mapping(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw), verify_hashes=False
        )
        self.assertEqual(manifest.model_id, "meta-llama/Llama-3.1-8B")
        self.assertEqual(len(manifest.layers), LAYER_COUNT)

        loads = list(manifest.iter_matrix_loads())
        self.assertEqual(len(loads), LAYER_COUNT * len(MATRIX_ARTIFACT_SIZES))
        self.assertEqual(loads[0][0].name, "attention_layer00_c0")
        self.assertEqual(loads[0][0].local_start, 0)
        self.assertEqual(loads[1][0].name, "attention_layer00_c1")
        self.assertEqual(loads[-1][0].name, "mlp_down_layer31_c1")
        self.assertEqual(sum(region.size for region, _ in loads),
                         2 * MATRIX_BYTES_PER_CHANNEL)

    def test_rejects_pre_s37_mlp_artifacts(self):
        raw = copy.deepcopy(self.raw)
        raw["mlp_format_id"] = 0x4838_4602
        with self.assertRaisesRegex(RuntimeContractError, "MLP format ID mismatch"):
            ScaleCodeArtifactManifest.load(
                self.write_manifest(raw, "old_mlp_format.json"),
                verify_hashes=False,
            )

    def test_rejects_non_integer_numeric_contract_fields(self):
        mutations = (
            lambda raw: raw.__setitem__("schema_version", True),
            lambda raw: raw.__setitem__("layer_count", 32.0),
            lambda raw: raw.__setitem__(
                "attention_format_id", float(ATTENTION_FORMAT_ID)
            ),
            lambda raw: raw["layers"][0].__setitem__("layer_id", False),
            lambda raw: raw["layers"][0]["artifacts"][
                "attention_c0"
            ].__setitem__("size", float(MATRIX_ARTIFACT_SIZES["attention_c0"])),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                raw = copy.deepcopy(self.raw)
                mutate(raw)
                with self.assertRaises(RuntimeContractError):
                    ScaleCodeArtifactManifest.load(
                        self.write_manifest(raw, f"numeric_{index}.json"),
                        verify_hashes=False,
                    )

    def test_rejects_path_reuse_and_escape(self):
        reused = copy.deepcopy(self.raw)
        reused["layers"][0]["artifacts"]["attention_c1"]["path"] = (
            reused["layers"][0]["artifacts"]["attention_c0"]["path"]
        )
        with self.assertRaisesRegex(RuntimeContractError, "path reused"):
            ScaleCodeArtifactManifest.load(
                self.write_manifest(reused, "reused.json"),
                verify_hashes=False,
            )

        escaped = copy.deepcopy(self.raw)
        escaped["layers"][0]["artifacts"]["attention_c0"]["path"] = (
            "../outside.bin"
        )
        with self.assertRaisesRegex(RuntimeContractError, "escapes or is missing"):
            ScaleCodeArtifactManifest.load(
                self.write_manifest(escaped, "escaped.json"),
                verify_hashes=False,
            )

    def test_record_detects_content_and_size_changes(self):
        path = self.root / "small.bin"
        path.write_bytes(b"scale")
        digest = hashlib.sha256(b"scale").hexdigest()
        record = ArtifactRecord(path, 5, digest)
        record.verify_hash(chunk_bytes=2)
        self.assertEqual(record.read_verified(), b"scale")

        path.write_bytes(b"scald")
        with self.assertRaisesRegex(RuntimeContractError, "SHA256 mismatch"):
            record.read_verified()
        path.write_bytes(b"scale!")
        with self.assertRaisesRegex(RuntimeContractError, "size changed"):
            record.read_verified()

    def test_layer_stager_hashes_and_writes_exact_payloads(self):
        def record(name, payload):
            path = self.root / name
            path.write_bytes(payload)
            return ArtifactRecord(
                path, len(payload), hashlib.sha256(payload).hexdigest()
            )

        attention = record("attention_meta.bin", b"attention")
        gate = record("gate_meta.bin", b"gate")
        down = record("down_meta.bin", b"down")
        rope = record("small_rope.bin", b"rope")
        layers = tuple(
            LayerArtifacts(
                layer_id,
                {
                    "attention_meta": attention,
                    "mlp_gate_meta": gate,
                    "mlp_down_meta": down,
                },
            )
            for layer_id in range(LAYER_COUNT)
        )
        manifest = ScaleCodeArtifactManifest(
            self.root / "synthetic.json", "model", "checkpoint", "2" * 64,
            layers, rope,
        )
        session = FakeXdmaSession()
        stager = XdmaLayerStager(session, manifest, chunk_bytes=4096)
        stager.stage_attention(7, 0x1000, len(b"attention"))
        stager.stage_mlp(7, 1, 0x2000, 4, 0x3000, 4)
        stager.stage_rope(0x4000, 4)
        self.assertEqual(
            session.writes,
            [
                (0, 0x1000, 4096, 9),
                (0, 0x2000, 4096, 4),
                (0, 0x3000, 4096, 4),
                (0, 0x4000, 4096, 4),
            ],
        )

        with self.assertRaises(RuntimeContractError):
            XdmaLayerStager(FakeXdmaSession(short=True), manifest).stage_rope(
                0x4000, 4
            )

    def test_preload_covers_both_ddr_channels_without_large_allocations(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "preload.json"), verify_hashes=False
        )
        session = FakeXdmaSession()
        with patch.object(
            ArtifactRecord,
            "read_verified",
            lambda record: SizedPayload(record.size),
        ):
            total = preload_all_matrices(session, manifest, chunk_bytes=2 << 20)
        self.assertEqual(total, 2 * MATRIX_BYTES_PER_CHANNEL)
        self.assertEqual(len(session.writes), 32 * 6)
        self.assertEqual(session.writes[0][:3], (0, 0, 2 << 20))
        self.assertEqual(session.writes[1][:3], (1, 0, 2 << 20))
        self.assertEqual(
            {channel for channel, _, _, _ in session.writes}, {0, 1}
        )

    def test_sampled_readback_covers_head_tail_and_both_channels(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "readback.json"), verify_hashes=False
        )
        session = FakeXdmaSession()
        result = verify_resident_matrix_samples(
            session, manifest, sample_bytes=64, chunk_bytes=4096
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["artifact_count"], 32 * 6)
        self.assertEqual(result["comparisons"], 32 * 6 * 2)
        self.assertEqual(result["verified_bytes"], 32 * 6 * 2 * 64)
        self.assertEqual({item[0] for item in session.reads}, {0, 1})
        with self.assertRaisesRegex(RuntimeContractError, "readback mismatch"):
            verify_resident_matrix_samples(
                FakeXdmaSession(corrupt_read=True), manifest,
                sample_bytes=64, chunk_bytes=4096,
            )


if __name__ == "__main__":
    unittest.main()
