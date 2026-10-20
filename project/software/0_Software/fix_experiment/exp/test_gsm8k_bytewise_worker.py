"""CPU-only production selection, resource, timing and commit-order controls."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

import benchmark_bytewise_integrity as benchmark
import gsm8k_integrity_bytewise as fast
import gsm8k_weight_integrity as legacy
import run_gsm8k_worker as worker
import test_gsm8k_worker as worker_fixtures


# Reuse the existing full-byte/raw-representation and native-QDQ regressions,
# explicitly against this imported production helper. No module replacement.
PREPARATION = Path(__file__).resolve().parents[1] / "results/gsm8k_full_completion/preparation_20261018/integrity_performance_20261018/implementation"
spec = importlib.util.spec_from_file_location("a013_prior_bytewise_controls", PREPARATION / "test_bytewise_integrity.py")
prior_controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_controls)
CandidateLegacyRegression = prior_controls.CandidateLegacyRegression
BytewiseCPUControls = prior_controls.BytewiseCPUControls

UUID = "GPU-00000000-0000-4000-8000-000000000001"


def plan_for(implementation=True):
    plan = json.loads((Path(worker.__file__).resolve().parents[1] / "source/gsm8k_execution_cache_v2_20261018/plan.json").read_text())
    plan["protocol"]["integrity_contract_id"] = worker.INTEGRITY_CONTRACT_ID
    if implementation:
        plan["protocol"]["integrity_implementation_id"] = fast.METHOD_ID
    else:
        plan["protocol"].pop("integrity_implementation_id", None)
    return plan


class SelectionAndMemoryTests(unittest.TestCase):
    def test_missing_selects_original_class_without_module_replacement(self):
        self.assertIsNone(worker.selected_integrity_implementation(plan_for(False)))
        self.assertIs(worker.integrity_guard_class(plan_for(False)), legacy.StaticContentIntegrity)

    def test_explicit_fast_selects_subclass(self):
        cls = worker.integrity_guard_class(plan_for())
        self.assertTrue(issubclass(cls, legacy.StaticContentIntegrity))
        self.assertIsNot(cls, legacy.StaticContentIntegrity)

    def test_unknown_null_and_missing_semantic_contract_fail(self):
        for value in (None, "", "unknown", 1, False):
            plan = plan_for()
            plan["protocol"]["integrity_implementation_id"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                worker.selected_integrity_implementation(plan)
        plan = plan_for()
        del plan["protocol"]["integrity_contract_id"]
        with self.assertRaises(ValueError):
            worker.selected_integrity_implementation(plan)

    def test_actual_bytes_dedup_and_exact_reserve_boundary(self):
        value = torch.ones(31, dtype=torch.bfloat16)
        tensors = {"w": value, "alias": value}
        required = 62 + fast.DEFAULT_CHUNK_BYTES + fast.MINIMUM_HOST_RESERVE_BYTES
        with patch.object(fast, "read_host_available_bytes", return_value=required):
            guard = fast.audit_capture_memory(tensors, fast.DEFAULT_CHUNK_BYTES)
        self.assertTrue(guard["passed"])
        self.assertEqual(guard["logical_static_bytes"], 124)
        self.assertEqual(guard["unique_immutable_baseline_bytes"], 62)
        self.assertEqual(guard["projected_available_after_capture_bytes"], 80 * (1 << 30))
        with patch.object(fast, "read_host_available_bytes", return_value=required - 1):
            self.assertFalse(fast.audit_capture_memory(tensors, fast.DEFAULT_CHUNK_BYTES)["passed"])

    def test_insufficient_capture_reserve_fails_before_snapshot_allocation(self):
        fixture = CandidateLegacyRegression(methodName="test_full_positive_and_all_phases")
        fixture.setUp()
        try:
            guard, model, _, out = fixture.fixture()
            fixture.load(guard, model)
            with patch.object(fast, "read_host_available_bytes", return_value=80 * (1 << 30)), \
                 patch.object(fast, "ImmutableTensorSnapshot") as allocator:
                with self.assertRaisesRegex(legacy.IntegrityError, "host reserve"):
                    guard.observe("attached", model)
                allocator.assert_not_called()
            data = json.loads((out / "integrity.json").read_text())
            self.assertEqual(data["state"], "failed")
            self.assertFalse(data["immutable_capture_resource_guard"]["passed"])
            self.assertNotIn("immutable_runtime_baseline", data)
        finally:
            fixture.tearDown()

    def test_guard_call_timing_preserves_single_execution_and_failure(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            totals, calls = {}, []
            value, elapsed = worker.timed_integrity_call("check", "sample:x:before", lambda: calls.append("once"), totals, output)
            self.assertIsNone(value)
            self.assertEqual(calls, ["once"])
            record = json.loads((output / "performance_timings.jsonl").read_text().splitlines()[0])
            self.assertEqual(record["elapsed_seconds"], elapsed)
            self.assertEqual(record["state"], "complete")
            def fail():
                raise RuntimeError("synchronization_failed")
            with self.assertRaisesRegex(RuntimeError, "synchronization_failed"):
                worker.timed_integrity_call("check", "sample:x:after", fail, totals, output)
            lines = (output / "performance_timings.jsonl").read_text().splitlines()
            self.assertEqual(json.loads(lines[-1])["state"], "failed")
            self.assertEqual(totals["integrity_call_count"], 2)

    def test_source_identity_binds_both_helpers_only_for_fast(self):
        codes = worker.code_identity(fast.METHOD_ID)
        by_name = {Path(path).name: sha for path, sha in codes.items()}
        for module in (fast, legacy):
            self.assertEqual(by_name[Path(module.__file__).name], hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest())
        old = worker.code_identity()
        self.assertNotIn("gsm8k_integrity_bytewise.py", {Path(path).name for path in old})


class BenchmarkEntryTests(unittest.TestCase):
    def test_cpu_default_has_no_cuda_initialization(self):
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": ""}):
            args = benchmark.parse_benchmark_args(["--output", "/tmp/a013_nonexistent_benchmark_output.json"])
        self.assertEqual(args.device, "cpu")
        self.assertFalse(torch.cuda.is_initialized())

    def test_full_target_visible_actual_uuid_must_agree(self):
        self.assertEqual(benchmark.validate_cuda_identity(UUID, UUID, UUID.removeprefix("GPU-")), UUID)
        for visible, actual in (("0", UUID), (UUID, "GPU-00000000-0000-4000-8000-000000000002")):
            with self.assertRaises(ValueError):
                benchmark.validate_cuda_identity(UUID, visible, actual)

    def test_shared_mode_bounded_and_mutex(self):
        base = ["--device", "cuda:0", "--gpu-uuid", UUID, "--diagnostic-shared-gpu0", "--output", "/tmp/a013_nonexistent_benchmark_output.json"]
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": UUID}):
            self.assertTrue(benchmark.parse_benchmark_args(base).diagnostic_shared_gpu0)
            for extra in (["--mib", "65"], ["--repeats", "6"], ["--repeats", "2"], ["--chunk-mib", "32"], ["--exclusive-gpu0-slot"]):
                with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    benchmark.parse_benchmark_args(base + extra)
        self.assertFalse(torch.cuda.is_initialized())

    def test_gpu_requires_full_uuid_and_explicit_allocation_mode(self):
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "0"}), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                benchmark.parse_benchmark_args(["--device", "cuda:0", "--gpu-uuid", UUID,
                    "--exclusive-gpu0-slot", "--output", "/tmp/a013_nonexistent_benchmark_output.json"])


class WorkerCommitIntegrationTests(unittest.TestCase):
    """Run worker control flow with CPU fixtures and mocked CUDA metadata only."""
    def run_fixture(self, output, *, mode=True, after_failure=False):
        plan = plan_for(mode)
        plan_path = output.parent / (output.name + "_plan.json")
        plan_path.write_text(json.dumps(plan))
        args = worker.parse_args(["--stage", "formal", "--case", "bf16", "--model", "Llama-3.1-8B-Instruct",
            "--model-identity", "unused", "--output", str(output), "--plan", str(plan_path)])
        req = worker_fixtures.request(split="test")
        events, guards = [], []
        class FakeGuard:
            def __init__(self, path, identity, out, guard_identity, **kwargs):
                self.data = {"integrity_timing": {"immutable_capture_seconds": 0.25}}
                self.identity = guard_identity
                guards.append(self)
            def observe(self, stage, model):
                events.append(stage)
            def check(self, label):
                events.append(label)
                if after_failure and label.endswith(":after"):
                    raise legacy.IntegrityError("postcheck_failed")
            def finish(self):
                self.check("stage_complete")
                return {"path": "integrity.json", "sha256": "f" * 64, "qualified": True,
                        "contract_id": worker.INTEGRITY_CONTRACT_ID, "baseline_root_sha256": "b" * 64}
            def fail(self, error):
                events.append("failed:" + type(error).__name__)
        model = torch.nn.Linear(2, 2, dtype=torch.bfloat16)
        model.config = SimpleNamespace(use_cache=True, _attn_implementation="eager")
        def load_model(args, integrity_observer=None):
            integrity_observer("cpu_loaded", model)
            integrity_observer("gpu_loaded", model)
            return model, worker_fixtures.Tokenizer(), {}, None
        def generate(*args):
            events.append("generate_one")
            identity = args[7]
            return worker_fixtures.complete_row(req, identity)
        original_append = worker.append_jsonl
        def append(handle, value):
            if handle.name.endswith("generation.jsonl"):
                events.append("commit:" + value["status"])
            return original_append(handle, value)
        import run_eval_worker as evaluator
        props = SimpleNamespace(uuid=UUID, name="CPU mocked CUDA metadata", total_memory=48 * (1 << 30))
        with contextlib.ExitStack() as stack:
            mocks = {"load_plan": lambda path: plan, "prepare_requests": lambda *a: [req],
                "verify_checkpoint": lambda *a: {"fingerprint_sha256": "m", "files": []},
                "integrity_guard_class": lambda p: FakeGuard,
                "audit_prompts": lambda *a: ({req["sample_id"]: [1, 2]}, {}),
                "resolve_generation": lambda *a: (SimpleNamespace(eos_token_id=[3]), {"eos_token_ids": [3], "effective_generation_config": {"max_new_tokens": 4096}}),
                "code_identity": lambda *a: {}, "generate_one": generate,
                "validate_integrity_evidence": lambda *a, **k: None, "append_jsonl": append}
            for key, value in mocks.items():
                stack.enter_context(patch.object(worker, key, value))
            for key, value in {"load_model": load_model, "configure_reproducibility": lambda *a: None,
                               "package_versions": lambda: {}, "ensure_evaluator_version": lambda *a: None}.items():
                stack.enter_context(patch.object(evaluator, key, value))
            stack.enter_context(patch.object(torch, "set_num_interop_threads", lambda *a: None))
            for key, value in {"is_available": lambda: True, "set_device": lambda *a: None,
                "reset_peak_memory_stats": lambda *a: None, "synchronize": lambda *a: None,
                "mem_get_info": lambda *a: (48 * (1 << 30), 48 * (1 << 30)),
                "get_device_properties": lambda *a: props, "max_memory_allocated": lambda *a: 123,
                "max_memory_reserved": lambda *a: 456}.items():
                stack.enter_context(patch.object(torch.cuda, key, value))
            if after_failure:
                with self.assertRaisesRegex(legacy.IntegrityError, "postcheck_failed"):
                    worker.run(args)
            else:
                worker.run(args)
        return events, guards

    def test_fast_identity_phase_order_and_success_committed_after_postcheck(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name) / "AT001"
            events, guards = self.run_fixture(out)
            self.assertEqual(events, ["cpu_loaded", "gpu_loaded", "attached", "setup_complete",
                "sample:test:0000:before", "generate_one", "sample:test:0000:after", "commit:complete", "stage_complete"])
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["identity"]["integrity_implementation_id"], fast.METHOD_ID)
            self.assertEqual(manifest["integrity_implementation_id"], fast.METHOD_ID)
            self.assertEqual(guards[0].identity["integrity_implementation_id"], fast.METHOD_ID)
            row = json.loads((out / "generation.jsonl").read_text())
            self.assertEqual(row["elapsed_seconds"], 1.25)
            self.assertEqual(row["performance_timing"]["native_generation_seconds_this_attempt"], 1.25)
            self.assertIn("performance_timings.jsonl", manifest["artifacts"])
            self.assertEqual(manifest["performance_timing"]["integrity_call_count"], 7)
            self.assertFalse(torch.cuda.is_initialized())

    def test_postcheck_failure_never_commits_success(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name) / "AT001"
            events, _ = self.run_fixture(out, after_failure=True)
            self.assertNotIn("commit:complete", events)
            row = json.loads((out / "generation.jsonl").read_text())
            self.assertEqual(row["status"], "error")
            self.assertEqual(json.loads((out / "manifest.json").read_text())["state"], "failed")

    def test_legacy_identity_does_not_claim_fast(self):
        with tempfile.TemporaryDirectory() as name:
            out = Path(name) / "AT001"
            _, guards = self.run_fixture(out, mode=False)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertNotIn("integrity_implementation_id", manifest["identity"])
            self.assertNotIn("integrity_implementation_id", manifest)
            self.assertNotIn("integrity_implementation_id", guards[0].identity)


if __name__ == "__main__":
    unittest.main(verbosity=2)
