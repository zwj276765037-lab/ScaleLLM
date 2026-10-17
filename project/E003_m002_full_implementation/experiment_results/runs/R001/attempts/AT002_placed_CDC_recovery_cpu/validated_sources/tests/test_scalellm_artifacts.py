#!/usr/bin/env python3

import copy
import hashlib
import json
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from host.scalellm_artifacts import (
    ArtifactRecord,
    LAYER_ARTIFACT_SIZES,
    MATRIX_ARTIFACT_SIZES,
    LayerArtifacts,
    ScaleCodeArtifactManifest,
    XdmaLayerStager,
    preload_all_matrices,
    verify_resident_matrix_samples,
)
from host.scalellm_memory import LAYER_COUNT, MATRIX_BYTES_PER_CHANNEL, ROPE_BYTES
from host.scalellm_runtime import RuntimeContractError


TARGET_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
ATTENTION_FORMAT_03 = 0x4838_4103
ATTENTION_ABI_02 = 0x0002_0000
MLP_FORMAT_05 = 0x4838_4605
MLP_ABI_05 = 0x0005_0000


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
            "schema_version": 2,
            "model_id": TARGET_MODEL_ID,
            "checkpoint_id": "1" * 64,
            "checkpoint_sha256": "1" * 64,
            "layer_count": LAYER_COUNT,
            "attention_format_id": ATTENTION_FORMAT_03,
            "attention_abi": ATTENTION_ABI_02,
            "mlp_format_id": MLP_FORMAT_05,
            "mlp_abi": MLP_ABI_05,
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
        self.assertEqual(manifest.model_id, TARGET_MODEL_ID)
        self.assertEqual(len(manifest.layers), LAYER_COUNT)

        loads = list(manifest.iter_matrix_loads())
        self.assertEqual(len(loads), LAYER_COUNT * 2)
        self.assertEqual(loads[0][0].name, "attention_layer00_c0")
        self.assertEqual(loads[0][0].local_start, 0)
        self.assertEqual(loads[1][0].name, "attention_layer00_c1")
        self.assertEqual(loads[-1][0].name, "attention_layer31_c1")
        self.assertEqual(sum(region.size for region, _ in loads),
                         MATRIX_BYTES_PER_CHANNEL)

    def test_rejects_old_mlp_formats_and_command_abis(self):
        for format_id in (0x4838_4602, 0x4838_4603, 0x4838_4604):
            with self.subTest(format_id=format_id):
                raw = copy.deepcopy(self.raw)
                raw["mlp_format_id"] = format_id
                with self.assertRaisesRegex(RuntimeContractError, "MLP format ID mismatch"):
                    ScaleCodeArtifactManifest.load(
                        self.write_manifest(raw, f"mlp_format_{format_id:x}.json"),
                        verify_hashes=False,
                    )
        for abi in (0x0004_0003, 0x0004_0004, 0x0005_0001):
            with self.subTest(abi=abi):
                raw = copy.deepcopy(self.raw)
                raw["mlp_abi"] = abi
                with self.assertRaisesRegex(RuntimeContractError, "MLP command ABI mismatch"):
                    ScaleCodeArtifactManifest.load(
                        self.write_manifest(raw, f"mlp_abi_{abi:x}.json"),
                        verify_hashes=False,
                    )

    def test_rejects_schema1_missing_and_wrong_abis(self):
        mutations = (
            ("schema1", lambda raw: raw.__setitem__("schema_version", 1), "schema"),
            ("missing_attention", lambda raw: raw.pop("attention_abi"), "fields mismatch"),
            ("missing_mlp", lambda raw: raw.pop("mlp_abi"), "fields mismatch"),
            ("wrong_attention", lambda raw: raw.__setitem__("attention_abi", 0x0001_0000), "Attention command ABI mismatch"),
            ("wrong_mlp", lambda raw: raw.__setitem__("mlp_abi", 0x0004_0003), "MLP command ABI mismatch"),
        )
        for name, mutate, expected_error in mutations:
            with self.subTest(name=name):
                raw = copy.deepcopy(self.raw)
                mutate(raw)
                with self.assertRaisesRegex(RuntimeContractError, expected_error):
                    ScaleCodeArtifactManifest.load(
                        self.write_manifest(raw, f"{name}.json"),
                        verify_hashes=False,
                    )

    def test_rejects_base_model_artifact(self):
        raw = copy.deepcopy(self.raw)
        raw["model_id"] = "meta-llama/Llama-3.1-8B"
        with self.assertRaisesRegex(RuntimeContractError, "model_id"):
            ScaleCodeArtifactManifest.load(
                self.write_manifest(raw, "base_model.json"), verify_hashes=False
            )

    def test_rejects_checkpoint_label_without_matching_sha(self):
        raw = copy.deepcopy(self.raw)
        raw["checkpoint_id"] = "2" * 64
        with self.assertRaisesRegex(RuntimeContractError, "checkpoint_id disagrees"):
            ScaleCodeArtifactManifest.load(
                self.write_manifest(raw, "checkpoint_label.json"),
                verify_hashes=False,
            )

    def test_rejects_non_integer_numeric_contract_fields(self):
        mutations = (
            lambda raw: raw.__setitem__("schema_version", True),
            lambda raw: raw.__setitem__("layer_count", 32.0),
            lambda raw: raw.__setitem__(
                "attention_format_id", float(ATTENTION_FORMAT_03)
            ),
            lambda raw: raw.__setitem__("attention_abi", True),
            lambda raw: raw.__setitem__("mlp_abi", float(MLP_ABI_05)),
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
                (1, 0x2000, 4096, 4),
                (1, 0x3000, 4096, 4),
                (0, 0x4000, 4096, 4),
            ],
        )

        with self.assertRaises(RuntimeContractError):
            XdmaLayerStager(FakeXdmaSession(short=True), manifest).stage_rope(
                0x4000, 4
            )

    def test_mlp_slot_stages_all_four_half_groups_on_ddr1_and_reuses_layer(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "mlp_slot.json"), verify_hashes=False)
        session = FakeXdmaSession()
        stager = XdmaLayerStager(session, manifest)
        with patch.object(ArtifactRecord, "read_verified",
                          lambda record: SizedPayload(record.size)):
            with stager.mlp_weights(7):
                self.assertEqual([(c, o, n) for c, o, _, n in session.writes],
                                 [(1, 0, 28 << 20), (1, 28 << 20, 28 << 20),
                                  (1, 56 << 20, 14 << 20), (1, 70 << 20, 14 << 20)])
            with stager.mlp_weights(7):
                self.assertEqual(len(session.writes), 4)
            with stager.mlp_weights(31):
                self.assertEqual(len(session.writes), 8)
                self.assertEqual(sum(n for _, _, _, n in session.writes), 168 << 20)

    def test_other_layer_cannot_overwrite_a_leased_mlp_slot(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "mlp_lease.json"), verify_hashes=False)
        session = FakeXdmaSession()
        stager = XdmaLayerStager(session, manifest)
        waiting = threading.Event()
        entered = threading.Event()

        def other_layer():
            waiting.set()
            with stager.mlp_weights(9):
                entered.set()

        with patch.object(ArtifactRecord, "read_verified",
                          lambda record: SizedPayload(record.size)):
            with ThreadPoolExecutor(max_workers=1) as pool:
                with stager.mlp_weights(3):
                    future = pool.submit(other_layer)
                    self.assertTrue(waiting.wait(1))
                    self.assertFalse(entered.wait(0.02))
                    self.assertEqual(len(session.writes), 4)
                future.result(timeout=1)
                self.assertTrue(entered.is_set())
                self.assertEqual(len(session.writes), 8)

    def test_failed_or_unretired_lease_blocks_all_future_weight_writes(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "mlp_poison.json"), verify_hashes=False)
        for short_write in (False, True):
            with self.subTest(short_write=short_write):
                session = FakeXdmaSession(short=short_write)
                stager = XdmaLayerStager(session, manifest)
                with patch.object(ArtifactRecord, "read_verified",
                                  lambda record: SizedPayload(record.size)):
                    with self.assertRaises(RuntimeContractError):
                        with stager.mlp_weights(0):
                            raise RuntimeContractError("simulated unretired hardware timeout")
                    count = len(session.writes)
                    with self.assertRaisesRegex(RuntimeContractError, "RESET-REQUIRED"):
                        with stager.mlp_weights(1):
                            self.fail("poisoned slot must never be yielded")
                    self.assertEqual(len(session.writes), count)

    def test_preload_only_resident_attention_without_large_allocations(self):
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
        self.assertEqual(total, MATRIX_BYTES_PER_CHANNEL)
        self.assertEqual(len(session.writes), 32 * 2)
        self.assertEqual(session.writes[0][:3], (0, 0, 2 << 20))
        self.assertEqual(session.writes[1][:3], (0, 20 << 20, 2 << 20))
        self.assertEqual(
            {channel for channel, _, _, _ in session.writes}, {0}
        )

    def test_sampled_readback_covers_resident_attention_head_tail(self):
        manifest = ScaleCodeArtifactManifest.load(
            self.write_manifest(self.raw, "readback.json"), verify_hashes=False
        )
        session = FakeXdmaSession()
        result = verify_resident_matrix_samples(
            session, manifest, sample_bytes=64, chunk_bytes=4096
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["artifact_count"], 32 * 2)
        self.assertEqual(result["comparisons"], 32 * 2 * 2)
        self.assertEqual(result["verified_bytes"], 32 * 2 * 2 * 64)
        self.assertEqual({item[0] for item in session.reads}, {0})
        with self.assertRaisesRegex(RuntimeContractError, "readback mismatch"):
            verify_resident_matrix_samples(
                FakeXdmaSession(corrupt_read=True), manifest,
                sample_bytes=64, chunk_bytes=4096,
            )


if __name__ == "__main__":
    unittest.main()
