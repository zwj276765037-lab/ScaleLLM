"""CPU controls: bytewise readiness must bind its actual canonical sources."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

candidate = os.environ.get("GSM8K_READINESS_CANDIDATE_PATH")
if candidate:
    spec = importlib.util.spec_from_file_location("reviewed_readiness_candidate", candidate)
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
else:
    import run_gsm8k_matrix as matrix
from gsm8k_protocol import INTEGRITY_CONTRACT_ID, INTEGRITY_IMPLEMENTATION_ID, atomic_json, sha256_file


class BytewiseReadinessSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="CPU_only_readiness_fixture_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.here = self.root / "canonical_exp"
        self.here.mkdir()
        self.patch = mock.patch.object(matrix, "HERE", self.here)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.plan_path, self.readiness_path = self.root / "plan.json", self.root / "readiness.json"
        self.plan = {"protocol": {"integrity_contract_id": INTEGRITY_CONTRACT_ID,
                                 "integrity_implementation_id": INTEGRITY_IMPLEMENTATION_ID}}
        self.sources = {}
        for name in ("run_gsm8k_worker.py", "run_eval_worker.py", "gsm8k_protocol.py",
                     "gsm8k_weight_integrity.py", "gsm8k_integrity_bytewise.py"):
            path = self.here / name
            path.write_text("# explicitly synthetic CPU-only readiness source " + name)
            self.sources[str(path.resolve())] = sha256_file(path)
        self.gpu = "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"
        self.readiness = {"ready": True, "source_hashes": deepcopy(self.sources),
                          "evidence_hashes": {}, "gpu_uuids": [self.gpu]}
        self.args = SimpleNamespace(plan=self.plan_path, readiness=self.readiness_path, gpu_uuids=[self.gpu])

    def verify(self):
        atomic_json(self.plan_path, self.plan)
        self.readiness["plan_sha256"] = sha256_file(self.plan_path)
        atomic_json(self.readiness_path, self.readiness)
        return matrix.verify_readiness(self.args)

    def test_fast_canonical_sources_pass(self):
        self.assertEqual(self.verify(), self.readiness)

    def test_missing_bytewise_helper_is_rejected(self):
        del self.readiness["source_hashes"][str(self.here / "gsm8k_integrity_bytewise.py")]
        with self.assertRaisesRegex(ValueError, "canonical source identity.*gsm8k_integrity_bytewise"):
            self.verify()

    def test_missing_legacy_helper_is_rejected(self):
        del self.readiness["source_hashes"][str(self.here / "gsm8k_weight_integrity.py")]
        with self.assertRaisesRegex(ValueError, "canonical source identity.*gsm8k_weight_integrity"):
            self.verify()

    def test_missing_each_worker_or_protocol_source_is_rejected(self):
        for name in ("run_gsm8k_worker.py", "run_eval_worker.py", "gsm8k_protocol.py"):
            with self.subTest(name=name):
                self.readiness["source_hashes"] = deepcopy(self.sources)
                del self.readiness["source_hashes"][str(self.here / name)]
                with self.assertRaisesRegex(ValueError, "canonical source identity"):
                    self.verify()

    def test_same_basename_elsewhere_cannot_substitute_for_canonical_helper(self):
        for name in ("gsm8k_weight_integrity.py", "gsm8k_integrity_bytewise.py"):
            with self.subTest(name=name):
                self.readiness["source_hashes"] = deepcopy(self.sources)
                digest = self.readiness["source_hashes"].pop(str(self.here / name))
                other = self.root / name
                other.write_bytes((self.here / name).read_bytes())
                self.readiness["source_hashes"][str(other)] = digest
                with self.assertRaisesRegex(ValueError, "canonical source identity"):
                    self.verify()

    def test_invalid_helper_sha_is_rejected(self):
        for value in (None, True, 12, "", "a"*63, "G"*64, "A"*64, "b"*64):
            with self.subTest(value=value):
                self.readiness["source_hashes"] = deepcopy(self.sources)
                self.readiness["source_hashes"][str(self.here / "gsm8k_integrity_bytewise.py")] = value
                with self.assertRaises(ValueError):
                    self.verify()

    def test_explicit_null_or_unknown_mode_is_rejected(self):
        for value in (None, False, "other", "", [], {}):
            with self.subTest(value=value):
                self.plan["protocol"]["integrity_implementation_id"] = value
                with self.assertRaisesRegex(ValueError, "implementation"):
                    self.verify()

    def test_fast_mode_requires_static_semantic_contract(self):
        self.plan["protocol"].pop("integrity_contract_id")
        with self.assertRaisesRegex(ValueError, "implementation"):
            self.verify()

    def test_missing_mode_preserves_legacy_partial_source_behavior(self):
        self.plan["protocol"].pop("integrity_implementation_id")
        self.readiness["source_hashes"] = {str(self.here / "run_gsm8k_worker.py"):
            self.sources[str(self.here / "run_gsm8k_worker.py")]}
        self.assertEqual(self.verify(), self.readiness)

    def test_source_changes_are_rejected_for_both_modes(self):
        for fast in (True, False):
            with self.subTest(fast=fast):
                if not fast:
                    self.plan["protocol"].pop("integrity_implementation_id")
                (self.here / "run_gsm8k_worker.py").write_text("# changed synthetic fixture")
                with self.assertRaisesRegex(ValueError, "Source changed"):
                    self.verify()

    def test_fast_mode_requires_dictionary_source_map(self):
        for value in (None, [], ""):
            with self.subTest(value=value):
                self.readiness["source_hashes"] = value
                with self.assertRaisesRegex(ValueError, "canonical implementation sources"):
                    self.verify()


if __name__ == "__main__":
    unittest.main(verbosity=2)
