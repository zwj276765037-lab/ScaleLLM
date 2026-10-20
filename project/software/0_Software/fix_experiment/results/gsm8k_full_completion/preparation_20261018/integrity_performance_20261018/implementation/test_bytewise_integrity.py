"""CPU-only positive/corruption controls plus unchanged legacy loader tests."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[4] / "exp"
sys.path.insert(0, str(EXP))
import gsm8k_weight_integrity as legacy
import test_gsm8k_weight_integrity as original_tests
from gsm8k_integrity_bytewise import (
    BytewiseIntegrityError, ChunkTransfer, ImmutableTensorSnapshot,
    METHOD_ID, make_integrity_class,
)

Candidate = make_integrity_class(legacy)


def snapshot(tensors, *, roles=None, chunk_bytes=16, **kwargs):
    roles = roles or {n: "parameter" for n in tensors}
    manifest = {n: legacy.tensor_descriptor(t, roles[n]) for n, t in tensors.items()}
    return ImmutableTensorSnapshot(tensors, manifest, roles=roles, chunk_bytes=chunk_bytes, **kwargs)


class CandidateLegacyRegression(original_tests.IntegrityTests):
    """Run original loader/native-QDQ controls against explicitly injected class."""
    def fixture(self, *args, **kwargs):
        with patch.object(original_tests, "StaticContentIntegrity", Candidate):
            return super().fixture(*args, **kwargs)

    def test_phase_coverage_and_derived_root_are_explicit(self):
        guard, model, _, out = self.fixture()
        self.freeze(guard, model)
        guard.check("sample:train:0000:before")
        guard.check("sample:train:0000:after")
        guard.finish()
        data = json.loads((out / "integrity.json").read_text())
        self.assertEqual(data["runtime_comparison_implementation"]["method_id"], METHOD_ID)
        for row in data["phase_checks"]:
            if row["label"] in {"cpu_loaded", "gpu_loaded", "qdq_rebuild"}:
                self.assertNotIn("content_comparison", row)
                continue
            comp = row["content_comparison"]
            self.assertTrue(comp["full_coverage_exact"])
            self.assertFalse(comp["direct_sha256_this_phase"])
            self.assertEqual(comp["compared_bytes"], comp["expected_bytes"])
            self.assertEqual(comp["equal_bytes"], comp["expected_bytes"])
            self.assertEqual(comp["derived_root_sha256"], data["baseline_root_sha256"])
            self.assertEqual(set(comp["per_tensor"]), set(data["baseline_manifest"]))

    def test_transfer_copy_exception_terminal_and_never_qualified(self):
        guard, model, _, out = self.fixture()
        self.freeze(guard, model)
        with patch.object(guard._snapshot.transfer, "copy", side_effect=RuntimeError("copy_failed")):
            with self.assertRaisesRegex(RuntimeError, "copy_failed"):
                guard.check("sample:train:0000:after")
        self.assertEqual(guard.data["state"], "failed")
        self.assertFalse(json.loads((out / "integrity.json").read_text())["qualified"])
        with self.assertRaises(legacy.IntegrityError):
            guard.check("retry_is_not_allowed")

    def test_synchronization_exception_terminal(self):
        guard, model, _, _ = self.fixture()
        self.freeze(guard, model)
        with patch.object(guard._snapshot.transfer, "synchronize", side_effect=RuntimeError("sync_failed")):
            with self.assertRaisesRegex(RuntimeError, "sync_failed"):
                guard.check("sample:train:0000:after")
        self.assertEqual(guard.data["state"], "failed")

    def test_public_manifest_mutation_rejected(self):
        guard, model, _, _ = self.fixture()
        self.freeze(guard, model)
        guard.data["baseline_manifest"]["proj.weight"]["sha256"] = "0" * 64
        with self.assertRaises(legacy.IntegrityError):
            guard.check("sample:train:0000:before")

    def test_incomplete_coverage_cannot_derive_a_successful_phase(self):
        guard, model, _, _ = self.fixture()
        self.freeze(guard, model)
        result = (guard._snapshot.baseline_manifest(), [], {"full_coverage_exact": False})
        with patch.object(guard._snapshot, "compare", return_value=result):
            with self.assertRaises(legacy.IntegrityError):
                guard.check("sample:train:0000:before")
        self.assertEqual(guard.data["state"], "failed")
        self.assertNotIn("derived_root_sha256", guard.checks[-1]["content_comparison"])


class BytewiseCPUControls(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)

    def assert_pass(self, snap, tensors, roles=None):
        roles = roles or {n: "parameter" for n in tensors}
        observed, errors, evidence = snap.compare(tensors, roles=roles)
        self.assertFalse(errors)
        self.assertEqual(observed, snap.baseline_manifest())
        self.assertTrue(evidence["full_coverage_exact"])
        self.assertEqual(evidence["compared_bytes"], evidence["expected_bytes"])
        self.assertEqual(evidence["equal_bytes"], evidence["expected_bytes"])
        return evidence

    def assert_fail(self, snap, tensors, roles=None):
        roles = roles or {n: "parameter" for n in tensors}
        _, _, evidence = snap.compare(tensors, roles=roles)
        self.assertFalse(evidence["full_coverage_exact"])
        return evidence

    def test_every_single_byte_and_first_last_bits_cross_chunks(self):
        value = torch.arange(129, dtype=torch.uint8)
        tensors = {"weight": value}
        snap = snapshot(tensors)
        self.assert_pass(snap, tensors)
        # Independent controls visit EVERY byte, crossing chunk edges and the
        # final partial chunk; each failure must be restored before the next.
        for offset in range(value.numel()):
            for bit in (1, 128):
                with self.subTest(offset=offset, bit=bit):
                    value[offset] ^= bit
                    evidence = self.assert_fail(snap, tensors)
                    self.assertEqual(evidence["compared_bytes"], 129)
                    value[offset] ^= bit
        self.assert_pass(snap, tensors)

    def test_nan_payload_and_negative_zero_raw_representation(self):
        raw = torch.tensor([0x7FC00001, 0x7FC00002, -2147483648, 0], dtype=torch.int32)
        value = raw.view(torch.float32)
        snap = snapshot({"weight": value}, chunk_bytes=3)
        self.assert_pass(snap, {"weight": value})
        for offset in (0, 4, 11, 15):
            with self.subTest(offset=offset):
                value.view(torch.uint8)[offset] ^= 1
                self.assert_fail(snap, {"weight": value})
                value.view(torch.uint8)[offset] ^= 1
        # -0 and +0 compare numerically equal, but integrity must reject them.
        value[2] = 0.
        self.assert_fail(snap, {"weight": value})

    def test_scalar_empty_and_native_dtypes_sha_equivalence(self):
        dtypes = [torch.bfloat16, torch.float16, torch.float32, torch.float64,
                  torch.int8, torch.uint8, torch.int16, torch.int32, torch.int64,
                  torch.bool, torch.complex64, torch.complex128]
        for dtype in dtypes:
            for shape in ((), (0,), (2, 0, 3), (3, 5)):
                with self.subTest(dtype=dtype, shape=shape):
                    tensors = {"w": torch.ones(shape, dtype=dtype)}
                    snap = snapshot(tensors, chunk_bytes=7)
                    self.assert_pass(snap, tensors)
                    saved = b"".join(snap._ImmutableTensorSnapshot__chunks["w"])
                    self.assertEqual(hashlib.sha256(saved).hexdigest(), legacy.tensor_descriptor(tensors["w"], "parameter")["sha256"])

    def test_tied_aliases_dedup_bytes_but_compare_each_logical_name(self):
        tensor = torch.arange(35, dtype=torch.uint8)
        tensors = {"embedding.weight": tensor, "lm_head.weight": tensor}
        snap = snapshot(tensors)
        self.assertEqual(snap.unique_baseline_bytes, 35)
        self.assertEqual(snap.expected_bytes, 70)
        evidence = self.assert_pass(snap, tensors)
        self.assertEqual(len(evidence["per_tensor"]), 2)
        tensor[-1] ^= 1
        self.assert_fail(snap, tensors)

    def test_immutable_baseline_has_no_model_alias_and_no_mutable_chunks(self):
        tensor = torch.arange(17, dtype=torch.uint8)
        snap = snapshot({"w": tensor})
        chunks = snap._ImmutableTensorSnapshot__chunks
        before = b"".join(chunks["w"])
        with self.assertRaises(TypeError):
            chunks["w"] = ()
        with self.assertRaises(TypeError):
            chunks["w"][0][0] = 7
        tensor[0] ^= 1
        self.assertEqual(b"".join(chunks["w"]), before)
        self.assert_fail(snap, {"w": tensor})

    def test_capture_sha_uses_actual_saved_bytes_and_rejects_wrong_baseline(self):
        tensor = torch.arange(31, dtype=torch.uint8)
        manifest = {"w": legacy.tensor_descriptor(tensor, "parameter")}
        tensor[-1] ^= 1
        with self.assertRaisesRegex(BytewiseIntegrityError, "captured bytes SHA differs"):
            ImmutableTensorSnapshot({"w": tensor}, manifest, roles={"w": "parameter"}, chunk_bytes=8)

    def test_capture_transfer_corruption_rejected(self):
        class CorruptCapture(ChunkTransfer):
            def copy(self, raw, offset, size):
                super().copy(raw, offset, size)
                self.buffer[0] ^= 1
        with self.assertRaisesRegex(BytewiseIntegrityError, "captured bytes SHA differs"):
            snapshot({"w": torch.arange(17, dtype=torch.uint8)}, transfer_factory=CorruptCapture)

    def test_copy_complete_before_memcmp_and_buffer_reuse(self):
        class DeferredCopy(ChunkTransfer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pending = None
            def copy(self, raw, offset, size):
                if self.pending is not None:
                    raise AssertionError("buffer reused before completed copy")
                self.pending = (raw, offset, size)
                self.buffer.zero_()
            def synchronize(self, raw):
                if self.pending is None:
                    raise AssertionError("sync without copy")
                source, offset, size = self.pending
                super().copy(source, offset, size)
                self.pending = None
        tensor = torch.arange(67, dtype=torch.uint8)
        snap = snapshot({"w": tensor}, transfer_factory=DeferredCopy)
        self.assert_pass(snap, {"w": tensor})
        tensor[-1] ^= 1
        self.assert_fail(snap, {"w": tensor})

    def test_new_storage_equal_content_rejected(self):
        tensor = torch.arange(17, dtype=torch.uint8)
        snap = snapshot({"w": tensor})
        self.assert_fail(snap, {"w": tensor.clone()})

    def test_shape_dtype_and_stride_changes_rejected(self):
        for mutation in (lambda t: t.reshape(3, 8), lambda t: t.view(torch.int16),
                         lambda t: t.reshape(3, 8).t()):
            tensor = torch.arange(24, dtype=torch.uint8)
            snap = snapshot({"w": tensor})
            self.assert_fail(snap, {"w": mutation(tensor)})

    def test_missing_added_renamed_or_role_changed_rejected(self):
        tensor = torch.arange(17, dtype=torch.uint8)
        snap = snapshot({"w": tensor})
        self.assert_fail(snap, {})
        self.assert_fail(snap, {"w": tensor, "extra": tensor})
        self.assert_fail(snap, {"renamed": tensor})
        self.assert_fail(snap, {"w": tensor}, roles={"w": "static_buffer"})
        self.assert_fail(snap, {"w": tensor}, roles={"w": "parameter", "extra": "parameter"})

    def test_noncontiguous_and_conjugate_explicitly_rejected(self):
        tensors = [torch.arange(12).reshape(3, 4).t(), torch.ones(3, dtype=torch.complex64).conj()]
        for tensor in tensors:
            with self.assertRaises(BytewiseIntegrityError):
                # Build metadata independently; no old descriptor needed for
                # the unsupported conjugate-view compatibility boundary.
                manifest = {"w": {"shape": list(tensor.shape), "dtype": str(tensor.dtype), "role": "parameter", "sha256": "unused"}}
                ImmutableTensorSnapshot({"w": tensor}, manifest, roles={"w": "parameter"})

    def test_capture_inventory_and_storage_mismatch_rejected(self):
        tensor = torch.ones(3)
        manifest = {"w": legacy.tensor_descriptor(tensor, "parameter")}
        with self.assertRaises(BytewiseIntegrityError):
            ImmutableTensorSnapshot({}, manifest, roles={"w": "parameter"})
        storage = {"w": legacy.storage_identity(tensor)}
        storage["w"]["storage_offset"] += 1
        with self.assertRaises(BytewiseIntegrityError):
            ImmutableTensorSnapshot({"w": tensor}, manifest, roles={"w": "parameter"}, expected_storage=storage)

    def test_read_only_manifest_copy_and_no_legacy_module_replacement(self):
        original = sys.modules["gsm8k_weight_integrity"]
        snap = snapshot({"w": torch.ones(3)})
        manifest = snap.baseline_manifest()
        manifest["w"]["sha256"] = "invalid"
        self.assertNotEqual(snap.baseline_manifest(), manifest)
        self.assertIs(sys.modules["gsm8k_weight_integrity"], original)
        self.assertIsNot(legacy.StaticContentIntegrity, Candidate)

    def test_cpu_did_not_initialize_cuda(self):
        self.assertEqual(os.environ.get("CUDA_VISIBLE_DEVICES"), "")
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main(verbosity=2)
