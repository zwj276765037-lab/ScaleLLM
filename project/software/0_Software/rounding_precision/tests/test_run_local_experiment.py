import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiment"))
import run_local_experiment as runner
from prepare_replay_data import synthetic_samples, write_synthetic


class RunnerTests(unittest.TestCase):
    def test_duplicate_sample_ids_rejected_before_evaluation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text('{"sample_id":"same"}\n{"sample_id":"same"}\n')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                runner.load_rows(path)

    def test_jsonl_blank_or_non_object_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            for content in ["\n", "[]\n", "{}\n", '{"sample_id":"bad","extra":NaN}\n']:
                path.write_text(content)
                with self.assertRaises(ValueError):
                    runner.load_rows(path)

    def test_low_memory_receipt_preserves_input_and_does_not_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text('{"sample_id":"only"}\n')
            attempt = Path(temp) / "attempt"
            args = argparse.Namespace(input=path, attempt_dir=attempt, threads=2,
                                      memory_gib=8, wall_seconds=10, max_samples=100)
            with patch.object(runner, "memory_available_bytes", return_value=1), \
                    patch.object(runner.platform, "platform", return_value="unit-test-platform"), \
                    patch.object(runner.subprocess, "Popen") as launch:
                self.assertEqual(runner.run(args), 75)
                launch.assert_not_called()
            receipt = json.loads((attempt / "execution_receipt.json").read_text())
            self.assertEqual(receipt["execution_state"], "blocked")
            original = (attempt / "manifest.json").read_bytes()
            with self.assertRaises(FileExistsError):
                runner.run(args)
            self.assertEqual((attempt / "manifest.json").read_bytes(), original)

    def test_seeded_input_identity_and_synthetic_provenance(self):
        rows = synthetic_samples(14, 2)
        self.assertEqual(rows, synthetic_samples(14, 2))
        self.assertEqual(len({row["sample_id"] for row in rows}), len(rows))
        self.assertTrue(all(row["provenance"]["kind"] == "synthetic" for row in rows))
        self.assertEqual({row["profile"] for row in rows}, {"attention", "mlp_gate_up", "mlp_down"})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            manifest = write_synthetic(path, 14, 2)
            self.assertEqual(manifest["sha256"], runner.identity(path)["sha256"])
            with self.assertRaises(FileExistsError):
                write_synthetic(path, 14, 2)

    def test_real_source_hash_checked_without_changing_numerical_input(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            path = base / "slice.json"
            path.write_text("frozen integer slice")
            row = {"provenance": {"kind": "real_trace", "source_files": [
                {"path": "slice.json", "sha256": runner.identity(path)["sha256"]}]}}
            self.assertTrue(runner.validate_source_files(row, base, {})["verified"])
            row["provenance"]["source_files"][0]["sha256"] = "0" * 64
            self.assertFalse(runner.validate_source_files(row, base, {})["verified"])
            row["provenance"]["source_files"][0]["path"] = "absent"
            result = runner.validate_source_files(row, base, {})
            self.assertFalse(result["verified"])
            self.assertEqual(result["files"][0]["reason"], "source_file_missing")


if __name__ == "__main__":
    unittest.main()
