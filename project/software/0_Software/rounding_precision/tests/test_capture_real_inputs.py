import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiment"))
import capture_real_inputs as capture


class CaptureResourceTests(unittest.TestCase):
    def test_prompt_source_line_and_text_identity_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prompt.jsonl"
            path.write_text('{"text":"first"}\n{"text":"second"}\n')
            text, record = capture.read_prompt(path, 1)
            self.assertEqual(text, "second")
            self.assertEqual(record["line_index_zero_based"], 1)
            self.assertNotEqual(record["line_sha256"], record["text_sha256"])
            with self.assertRaises(ValueError):
                capture.read_prompt(path, 4)

    def test_selected_geometry_rejects_dropped_token_or_wrong_down_width(self):
        capture.validate_geometry(31, "down_proj", (1, 32, 14336), 32)
        for shape in [(1, 31, 14336), (1, 32, 4096), (2, 32, 14336)]:
            with self.assertRaises(ValueError):
                capture.validate_geometry(31, "down_proj", shape, 32)
        self.assertEqual(capture.selected_module_name(15, "k_proj"), "layers.15.self_attn.k_proj")

    def test_collect_without_root_admission_never_inspects_device(self):
        args = argparse.Namespace(mode="collect", gpu0_qualified=False)
        with self.assertRaisesRegex(RuntimeError, "admission|qualified"):
            capture.supervise(args)

    def test_termination_reaps_only_fresh_owned_process_group(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"], start_new_session=True)
        capture.terminate_owned_group(process)
        self.assertIsNotNone(process.returncode)
        capture.terminate_owned_group(process)


if __name__ == "__main__":
    unittest.main()
