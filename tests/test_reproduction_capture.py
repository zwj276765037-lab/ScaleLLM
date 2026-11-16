"""Failure boundaries for the public benchmark's reference capture hooks."""
import dataclasses
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "project/hardware"))

from resource_optimization.deployment.benchmark_capture import BenchmarkCapture, LAYER_BYTES


def descriptor(cid, mask=0xffff):
    position, offset = divmod(cid - 1, 64)
    words = [0] * 64
    for slot in range(16):
        words[32 + slot * 2:34 + slot * 2] = [position, 1]
    return types.SimpleNamespace(command_id=cid, layer=offset // 2,
                                 opcode=1 + offset % 2, active_mask=mask,
                                 words=lambda: tuple(words))


class Session:
    def __init__(self, short=False):
        self.calls = []
        self.short = short

    def c2h_read_local(self, channel, length, address, chunk):
        self.calls.append((channel, length, address, chunk))
        return b"\0" * (length - int(self.short))


class Backend:
    def __init__(self, short=False):
        self.pending = None
        self.receipts = []
        self.session = Session(short)

    def require_quiescent(self):
        if self.pending is not None:
            raise ValueError("Not quiescent")


@dataclasses.dataclass
class State:
    epoch: int
    prompt: tuple
    max_new_tokens: int
    position: int
    generated: list
    finished: bool


class ReproductionCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "new-run"
        self.capture = BenchmarkCapture(self.output)

    def test_factory_does_not_create_runner_output(self):
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        self.capture.before_step(None, 0)
        self.assertTrue((self.output / "captures").is_dir())

    def test_existing_capture_directory_is_not_overwritten(self):
        (self.output / "captures").mkdir(parents=True)
        marker = self.output / "captures" / "existing"
        marker.write_bytes(b"retain evidence")
        with self.assertRaises(FileExistsError):
            self.capture.before_step(None, 0)
        self.assertEqual(marker.read_bytes(), b"retain evidence")

    def test_bad_order_and_inactive_slot_rejected_before_io(self):
        backend = Backend()
        for desc in (descriptor(2), descriptor(1, 0xfffe)):
            with self.assertRaises(ValueError):
                self.capture.before_command(backend, desc, b"input")
        self.assertEqual(backend.session.calls, [])

    def test_unacknowledged_completion_is_not_counted(self):
        self.output.mkdir()
        backend = Backend()
        self.capture.before_command(backend, descriptor(1), b"input")
        backend.pending = object()
        with self.assertRaises(ValueError):
            self.capture.after_command(backend, descriptor(1), b"input", b"output")
        self.assertEqual(self.capture.commands, 0)
        self.assertFalse((self.output / "benchmark_commands.jsonl").exists())

    def test_short_live_kv_capture_rejected(self):
        self.output.mkdir()
        self.capture.commands = 1984
        backend = Backend(short=True)
        with self.assertRaisesRegex(ValueError, "Short KV"):
            self.capture.before_command(backend, descriptor(1985), b"input")
        self.assertEqual(len(backend.session.calls), 1)
        self.assertEqual(backend.session.calls[0][1], LAYER_BYTES)

    def test_published_operator_output_mismatch_is_rejected(self):
        self.output.mkdir()
        self.capture.commands = 1985
        backend = Backend()
        desc = descriptor(1986)
        self.capture.before_command(backend, desc, b"input")
        backend.receipts = [{"command_id": 1986, "cycles": 100}]
        with self.assertRaisesRegex(ValueError, "published operator reference"):
            self.capture.after_command(backend, desc, b"input", b"wrong output")
        self.assertFalse(self.capture.after[1986]["reference_match"])

    def test_wrong_token_blocks_snapshot_read(self):
        self.output.mkdir()
        self.capture.commands = 8192
        states = [State(1, tuple(self.capture.tokens[str(i)]["prompt_token_ids"]),
                        len(self.capture.tokens[str(i)]["generated_token_ids"]), 128,
                        list(self.capture.tokens[str(i)]["generated_token_ids"]), True)
                  for i in range(16)]
        states[0].generated[-1] += 1
        backend = Backend()
        runtime = types.SimpleNamespace(slots=states, backend=backend)
        with self.assertRaisesRegex(ValueError, "token/state mismatch"):
            self.capture.after_step(runtime, 127, {i: s.generated[-1] for i, s in enumerate(states)})
        self.assertEqual(backend.session.calls, [])

    def test_model_complete_does_not_establish_capture_pass(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "Incomplete benchmark capture"):
            self.capture.finalize({"execution": "COMPLETE", "handles_closed": True,
                                   "final_quiescent": True, "steps": [{}] * 128})
        result = json.loads((self.output / "benchmark_capture.json").read_text())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["commands_completed"], 0)

    def test_failed_run_keeps_incomplete_receipt(self):
        self.output.mkdir()
        self.capture.finalize({"execution": "FAIL", "handles_closed": True})
        result = json.loads((self.output / "benchmark_capture.json").read_text())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIsNone(result["snapshot"])


if __name__ == "__main__":
    unittest.main()
