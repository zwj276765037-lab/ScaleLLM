"""Small independent CPU controls; no model or CUDA initialization."""
import copy
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
IMPLEMENTATION = HERE.parent / "implementation"
EXP = HERE.parents[5] / "exp"
sys.path.insert(0, str(EXP))
import torch
import gsm8k_weight_integrity as legacy

spec = importlib.util.spec_from_file_location("independent_bytewise_candidate", IMPLEMENTATION / "gsm8k_integrity_bytewise.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def literal_snapshot(value, raw, *, chunk=17, factory=candidate.ChunkTransfer):
    manifest = {"w": {"sha256": hashlib.sha256(raw).hexdigest(), "shape": list(value.shape), "dtype": str(value.dtype), "role": "parameter"}}
    return candidate.ImmutableTensorSnapshot({"w": value}, manifest, roles={"w": "parameter"}, chunk_bytes=chunk, transfer_factory=factory)


class IndependentControls(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.environ.get("CUDA_VISIBLE_DEVICES"), "")
        self.assertEqual(set(os.sched_getaffinity(0)), {8, 9})
        self.assertFalse(torch.cuda.is_initialized())
        torch.set_num_threads(2)

    def tearDown(self):
        self.assertFalse(torch.cuda.is_initialized())

    def test_literal_nonperiodic_bytes_and_derived_digest(self):
        raw = bytes(((i * 131) ^ (i >> 2) ^ 0x5A) & 255 for i in range(269))
        value = torch.tensor(list(raw), dtype=torch.uint8)
        snapshot = literal_snapshot(value, raw)
        observed, errors, evidence = snapshot.compare({"w": value}, roles={"w": "parameter"})
        self.assertEqual(errors, [])
        self.assertEqual(observed["w"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(evidence["expected_bytes"], 269)
        self.assertEqual(evidence["equal_bytes"], evidence["compared_bytes"])
        self.assertEqual(evidence["compared_bytes"], 269)
        self.assertFalse(evidence["direct_sha256_this_phase"])

    def test_each_boundary_and_both_memcmp_directions_reject(self):
        raw = bytes((i * 73 + 31) & 255 for i in range(83))
        value = torch.tensor(list(raw), dtype=torch.uint8)
        snapshot = literal_snapshot(value, raw, chunk=19)
        for offset in (0, 18, 19, 38, 75, 82):
            original = int(value[offset])
            for changed in (0, 255):
                if changed == original:
                    continue
                with self.subTest(offset=offset, changed=changed):
                    value[offset] = changed
                    observed, _, evidence = snapshot.compare({"w": value}, roles={"w": "parameter"})
                    self.assertFalse(evidence["full_coverage_exact"])
                    self.assertEqual(evidence["compared_bytes"], 83)
                    self.assertNotEqual(observed, snapshot.baseline_manifest())
                    value[offset] = original
        self.assertTrue(snapshot.compare({"w": value}, roles={"w": "parameter"})[2]["full_coverage_exact"])

    def test_distinct_alias_objects_with_nonzero_offset_and_roles(self):
        base = torch.arange(200, dtype=torch.uint8)
        left, right = base[13:104], base[13:104]
        self.assertIsNot(left, right)
        raw = bytes(range(13, 104))
        roles = {"left": "parameter", "right": "static_buffer"}
        tensors = {"left": left, "right": right}
        manifest = {name: {"sha256": hashlib.sha256(raw).hexdigest(), "shape": [91], "dtype": "torch.uint8", "role": role} for name, role in roles.items()}
        snapshot = candidate.ImmutableTensorSnapshot(tensors, manifest, roles=roles, chunk_bytes=13)
        self.assertEqual(snapshot.unique_baseline_bytes, 91)
        self.assertEqual(snapshot.expected_bytes, 182)
        self.assertTrue(snapshot.compare(tensors, roles=roles)[2]["full_coverage_exact"])
        base[103] ^= 128
        evidence = snapshot.compare(tensors, roles=roles)[2]
        self.assertFalse(evidence["full_coverage_exact"])
        self.assertEqual(evidence["compared_bytes"], 182)
        self.assertEqual(set(evidence["per_tensor"]), set(tensors))
        self.assertFalse(any(r["exact"] for r in evidence["per_tensor"].values()))

    def test_relocated_storage_during_copy_is_rejected(self):
        value = torch.arange(43, dtype=torch.uint8)

        class MoveAfterCopy(candidate.ChunkTransfer):
            trigger = False

            def copy(self, raw, offset, size):
                super().copy(raw, offset, size)
                if self.trigger:
                    value.set_(value.clone())
                    self.trigger = False

        snapshot = literal_snapshot(value, bytes(range(43)), factory=MoveAfterCopy)
        snapshot.transfer.trigger = True
        _, errors, evidence = snapshot.compare({"w": value}, roles={"w": "parameter"})
        self.assertFalse(evidence["full_coverage_exact"])
        self.assertIn("w:storage_changed_during_comparison", errors)

    def test_guard_transfer_BaseException_fails_terminal(self):
        value = torch.arange(31, dtype=torch.uint8)
        snapshot = literal_snapshot(value, bytes(range(31)))
        Guard = candidate.make_integrity_class(legacy)
        guard = Guard.__new__(Guard)
        guard._snapshot = snapshot
        guard._runtime_evidence = None
        baseline = snapshot.baseline_manifest()
        guard.data = {"state": "running", "qualified": False, "baseline_manifest": baseline, "baseline_root_sha256": legacy.canonical_hash(baseline)}
        guard._runtime_entries = lambda: ({"w": value}, {"w": "parameter"})
        saves = []
        guard._save = lambda terminal=False: saves.append((terminal, copy.deepcopy(guard.data)))

        def interrupted(*args):
            raise KeyboardInterrupt("CPU injected interruption")

        snapshot.transfer.copy = interrupted
        with self.assertRaises(KeyboardInterrupt):
            guard.check("sample:train:0000:after")
        self.assertEqual(guard.data["state"], "failed")
        self.assertFalse(guard.data["qualified"])
        self.assertTrue(saves[-1][0])
        self.assertIsNone(guard._runtime_evidence)
        with self.assertRaises(legacy.IntegrityError):
            guard.check("retry")

    def test_memcmp_signature_and_unsupported_meta_are_fail_closed(self):
        self.assertEqual(candidate._memcmp.argtypes, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t))
        self.assertEqual(candidate._memcmp.restype, ctypes.c_int)
        value = torch.empty(2, device="meta")
        manifest = {"w": {"sha256": "0" * 64, "shape": [2], "dtype": "torch.float32", "role": "parameter"}}
        with self.assertRaises(candidate.BytewiseIntegrityError):
            candidate.ImmutableTensorSnapshot({"w": value}, manifest, roles={"w": "parameter"}, chunk_bytes=7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
