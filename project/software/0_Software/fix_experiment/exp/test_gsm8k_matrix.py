#!/usr/bin/env python3
"""CPU-only matrix fault tests; temporary fixtures are never experiment runs.

GPU workers are not invoked. Supervisor process tests substitute a short-lived
CPU Python process and inject launch failures, then reap it even on test failure.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

os.environ["CUDA_VISIBLE_DEVICES"] = ""
ENTRY_SOURCE_HASHES = {
    name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name in ("run_gsm8k_matrix.py", "run_gsm8k_worker.py", "test_gsm8k_matrix.py")
}

import run_gsm8k_matrix as matrix
import run_gsm8k_worker as worker
from gsm8k_protocol import DEFAULT_PLAN, atomic_json, canonical_hash, load_plan, prepare_requests, sha256_file
from test_gsm8k_integrity_contract import attach_integrity, save_integrity, INTEGRITY_CONTRACT_ID, GPU0, GPU1


class MatrixSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = {stage: prepare_requests(DEFAULT_PLAN, stage) for stage in ("smoke", "pilot", "formal")}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gsm8k_cpu_matrix_test_")
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "run"
        self.root.mkdir()
        self.model = "Llama-3.2-3B-Instruct"
        self.group = {"model": self.model, "case": "bf16", "n_expected": 1319, "state": "pending"}
        self.plan = deepcopy(load_plan(DEFAULT_PLAN))
        self.plan["matrix"] = [self.group]
        # These temporary fault fixtures explicitly model two allocated slots;
        # the original planning-only default predates the two-GPU authorization.
        self.plan["resources"]["gpu_workers_max"] = 2
        self.plan_path = self.directory / "plan.json"
        atomic_json(self.plan_path, self.plan)
        shutil.copyfile(DEFAULT_PLAN.parent / "fewshot_indices.json", self.directory / "fewshot_indices.json")
        self.sources = {str(Path(worker.__file__).with_name("gsm8k_protocol.py").resolve()):
                        sha256_file(Path(worker.__file__).with_name("gsm8k_protocol.py"))}
        self.contract = {
            "plan_sha256": sha256_file(self.plan_path),
            "protocol_sha256": canonical_hash(self.plan["protocol"]),
            "stage_requests_sha256": {stage: canonical_hash(rows) for stage, rows in self.requests.items()},
            "model_fingerprints": {self.model: "f" * 64}, "source_hashes": self.sources,
            "package_versions": {"fixture": "cpu_only"},
            "verification_contract_id": matrix.verification_contract_id(self.plan),
            "scheduling_schema": "fixed_gpu_slots_v1",
            "gpu_uuids": ["GPU-11111111-1111-4111-8111-111111111111", "GPU-22222222-2222-4222-8222-222222222222"],
            "group_gpu_uuids": {matrix.group_key(self.group): "GPU-11111111-1111-4111-8111-111111111111"},
        }
        atomic_json(self.root / "frozen_contract.json", self.contract)

    def tearDown(self):
        self.temporary.cleanup()

    def write_lines(self, path, rows):
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def complete_attempt(self, stage, *, number=1, group=None, caps=0):
        group = group or self.group
        directory = self.root / stage / group["model"] / group["case"] / f"AT{number:03d}"
        directory.mkdir(parents=True)
        requests = self.requests[stage]
        identity = {
            "protocol_id": self.plan["protocol_id"], "plan_sha256": self.contract["plan_sha256"],
            "protocol_sha256": self.contract["protocol_sha256"], "data": self.plan["data"],
            "requests_sha256": canonical_hash(requests), "stage": stage, "case": group["case"],
            "seed": self.plan["protocol"]["seed"], "model_fingerprint_sha256": "f" * 64,
            "tokenizer": {"class": "CPUFixtureTokenizer", "vocab_sha256": "v" * 64},
            "generation": {"effective_generation_config": {"max_new_tokens": 64 if stage == "smoke" else 4096}, "eos_token_ids": [999]},
            "method": {"case": group["case"]}, "code_sha256": self.sources,
            "package_versions": {"fixture": "cpu_only"},
        }
        digest = canonical_hash(identity)
        rows = []
        for index, request in enumerate(requests):
            text = "#### 2"
            rows.append({
                "schema": worker.ROW_SCHEMA, "status": "complete", "identity_sha256": digest,
                **{key: request[key] for key in ("sample_id", "row_index", "split", "prompt_sha256", "fewshot_train_indices", "gold", "question_sha256")},
                "new_token_ids": list(text.encode()), "output_tokens": len(text.encode()),
                "raw_text": text, "scoring_text": text, "stop_strings": ["Question:"],
                "input_tokens": 2, "input_token_ids_sha256": canonical_hash([1, 2]),
                "stop_reason": "length" if index < caps else "eos", "length_capped": index < caps,
                "elapsed_seconds": 0.01, "peak_memory_allocated_bytes": 0,
                "peak_memory_reserved_bytes": 0, "source_attempt": str(directory), "use_cache": True,
            })
        self.write_lines(directory / "generation.jsonl", rows)
        self.write_lines(directory / "scores.jsonl", [worker.score_row(row) for row in rows])
        atomic_json(directory / "requests.json", requests)
        summary = worker.make_summary(rows, len(requests), stage, .1, "complete")
        summary.update(model=group["model"], case=group["case"], identity_sha256=digest)
        atomic_json(directory / "summary.json", summary)
        manifest = {
            "schema": worker.MANIFEST_SCHEMA, "state": "complete", "identity": identity,
            "identity_sha256": digest, "stage": stage, "model": group["model"], "case": group["case"],
            "pid": 1001 if stage == "smoke" else 1002, "started_at": f"CPU_FIXTURE_{stage}",
            "n_expected": len(requests), "n_completed": len(requests),
            "request_ids": [r["sample_id"] for r in requests], "full_split": stage == "formal",
            "generation": identity["generation"],
            "environment": {"device": "cuda:0",
                "gpu_uuid": self.contract["group_gpu_uuids"][matrix.group_key(group)].removeprefix("GPU-"),
                "CUDA_VISIBLE_DEVICES": self.contract["group_gpu_uuids"][matrix.group_key(group)]},
            "artifacts": {name: sha256_file(directory / name) for name in ("generation.jsonl", "scores.jsonl", "requests.json")},
        }
        atomic_json(directory / "manifest.json", manifest)
        if stage in {"smoke", "pilot"}:
            records = [{
                "sample_id": row["sample_id"], "prompt_sha256": row["prompt_sha256"],
                "repeatability_prefix_32_token_ids": list(range(32)),
                "cache_on_32_token_ids": list(range(32)), "cache_off_16_token_ids": list(range(16)),
                "repeat_32_token_ids": list(range(32)), "greedy_16_equal": True,
                "same_process_repeat_32_equal": True, "logits_allclose": True,
                "logits_max_abs_difference": 0, "logits_comparisons": 17, "atol": .125, "rtol": .01,
            } for row in self.requests["smoke"][:2]]
            atomic_json(directory / "verification.json", {
                "schema": "scalellm_gsm8k_generation_verification_v1", "passed": True,
                "records": records, "qdq_projection_calls": {},
                "all_qdq_projections_prefill_and_decode": True,
                "independent_process_repeatability": "pending_scheduler_comparison",
            })
            self.change_json(directory / "manifest.json", lambda m: m.update(
                generation_verification=json.loads((directory / "verification.json").read_text())))
        return directory

    def change_json(self, path, change):
        value = json.loads(path.read_text(encoding="utf-8"))
        change(value)
        atomic_json(path, value)

    def rehash_artifacts(self, directory):
        self.change_json(directory / "manifest.json", lambda m: m.update(
            artifacts={name: sha256_file(directory / name) for name in ("generation.jsonl", "scores.jsonl", "requests.json")}))

    def reidentify(self, directory, change):
        manifest = json.loads((directory / "manifest.json").read_text())
        change(manifest["identity"])
        manifest["identity_sha256"] = canonical_hash(manifest["identity"])
        for name in ("generation.jsonl", "scores.jsonl"):
            rows = [json.loads(line) for line in (directory / name).read_text().split("\n") if line]
            for row in rows:
                row["identity_sha256"] = manifest["identity_sha256"]
            self.write_lines(directory / name, rows)
        manifest["artifacts"] = {name: sha256_file(directory / name) for name in ("generation.jsonl", "scores.jsonl", "requests.json")}
        atomic_json(directory / "manifest.json", manifest)
        self.change_json(directory / "summary.json", lambda s: s.update(identity_sha256=manifest["identity_sha256"]))

    def convert_to_v2(self, directory):
        verification = json.loads((directory / "verification.json").read_text())
        verification["verification_contract_id"] = matrix.NATIVE_VERIFICATION
        for key in matrix.NATIVE_HARD_GATES:
            verification[key] = True
        for row in verification["records"]:
            row.update({key: True for key in matrix.NATIVE_HARD_GATES})
            row.update(greedy_16_equal=False, logits_allclose=False,
                native_generated_token_ids=list(range(17)), native_logits_count=17,
                native_prefix_matches_32=True, negative_control_detected=True,
                negative_control_status="detected", steps=[{
                    "step": step, "native_generate_exact": True, "rebuilt_cache_exact": True,
                    "cache_structure_valid": True, "finite": True,
                } for step in range(17)])
        atomic_json(directory / "verification.json", verification)
        self.change_json(directory / "manifest.json", lambda m: m.update(generation_verification=verification))

    def enable_integrity(self, directory):
        for name in ("run_eval_worker.py", "run_gsm8k_worker.py", "gsm8k_weight_integrity.py"):
            path = self.directory / "synthetic_sources" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("explicit temporary CPU fixture source")
            self.sources[str(path)] = sha256_file(path)
        self.contract["source_hashes"] = self.sources
        self.contract["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        atomic_json(self.root / "frozen_contract.json", self.contract)
        self.reidentify(directory, lambda i: i.update(integrity_contract_id=INTEGRITY_CONTRACT_ID,
                                                     code_sha256=self.sources))
        m = json.loads((directory / "manifest.json").read_text())
        s = json.loads((directory / "summary.json").read_text())
        requests = json.loads((directory / "requests.json").read_text())
        data = attach_integrity(directory, m, s, [r["sample_id"] for r in requests])
        return m, s, data

    def test_completed_integrity_attempt_reuse_validates_full_evidence(self):
        directory = self.complete_attempt("smoke")
        m, s, data = self.enable_integrity(directory)
        matrix.validate_completed_attempt(self.root, directory, "smoke", self.group)
        data["phase_checks"].pop()
        save_integrity(directory, m, s, data)
        with self.assertRaisesRegex(ValueError, "stage completion"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_old_smoke_cannot_be_relabelled_as_integrity_pass(self):
        directory = self.complete_attempt("smoke")
        self.contract["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        atomic_json(self.root / "frozen_contract.json", self.contract)
        with self.assertRaisesRegex(ValueError, "integrity contract"):
            matrix.validate_completed_attempt(self.root, directory, "smoke", self.group)

    def test_failed_integrity_attempt_rows_are_never_imported(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m.update(state="failed"))
        self.assertEqual(matrix.importable_resume_sources([directory], self.contract, self.group), [directory])
        self.contract["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        self.assertEqual(matrix.importable_resume_sources([directory], self.contract, self.group), [])
        self.assertTrue((directory / "generation.jsonl").exists())

    def test_integrity_plan_enforces_reviewed_gpu0_cpu_and_single_worker(self):
        self.plan["protocol"]["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        self.plan["resources"].update(gpu_workers_max=1, allowed_gpu_uuids=[GPU0], suggested_cpu_affinity=[[16,17]])
        matrix.validate_resource_allocation(self.plan, [GPU0], ["16,17"])
        for devices, cpus in [([GPU1], ["16,17"]), ([GPU0], ["18,19"]), ([GPU0,GPU1], ["16,17","18,19"])]:
            with self.subTest(devices=devices, cpus=cpus), self.assertRaises(ValueError):
                matrix.validate_resource_allocation(self.plan, devices, cpus)

    def test_actual_device_uuid_must_match_frozen_group(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m["environment"].update(
            gpu_uuid="22222222-2222-4222-8222-222222222222", CUDA_VISIBLE_DEVICES=self.contract["gpu_uuids"][1]))
        with self.assertRaisesRegex(ValueError, "GPU UUID"):
            matrix.stage_sources(self.root, "smoke", [self.group])
        self.change_json(directory / "manifest.json", lambda m: m.update(state="failed"))
        args = self.supervisor_args(allow_resume=True)
        with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "GPU UUID"):
                matrix.main()
            launch.assert_not_called()

    def test_visible_device_selector_cannot_substitute_for_actual_uuid(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m["environment"].update(gpu_uuid="unknown"))
        with self.assertRaisesRegex(ValueError, "GPU UUID"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_visibility_must_be_one_matching_gpu(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m["environment"].update(
            CUDA_VISIBLE_DEVICES=",".join(self.contract["gpu_uuids"])))
        with self.assertRaisesRegex(ValueError, "GPU UUID"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_cross_process_repeatability_requires_the_same_actual_gpu(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.change_json(pilot / "manifest.json", lambda m: m["environment"].update(
            gpu_uuid="22222222-2222-4222-8222-222222222222", CUDA_VISIBLE_DEVICES=self.contract["gpu_uuids"][1]))
        with self.assertRaisesRegex(ValueError, "GPU UUID"):
            matrix.paired_verification(smoke, pilot)

    def test_full_uuid_format_variants_match_but_alias_duplicates_fail(self):
        gpu = self.contract["gpu_uuids"][0]
        self.assertEqual(matrix.canonical_gpu_uuid(gpu.lower()), matrix.canonical_gpu_uuid(gpu[4:].upper()))
        with self.assertRaises(ValueError):
            matrix.fixed_gpu_assignments([self.group], [gpu, gpu[4:]])
        for invalid in ("0", "unknown", "", None, "MIG-" + gpu[4:]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                matrix.canonical_gpu_uuid(invalid)

    def test_v2_false_old_diagnostics_are_retained_without_waiving_hard_gates(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.convert_to_v2(smoke)
        self.convert_to_v2(pilot)
        self.assertTrue(matrix.paired_verification(smoke, pilot)["passed"])
        self.assertFalse(json.loads((smoke / "verification.json").read_text())["records"][0]["logits_allclose"])
        for key in matrix.NATIVE_HARD_GATES:
            verification = json.loads((pilot / "verification.json").read_text())
            verification["records"][0][key] = False
            with self.subTest(hard_gate=key), self.assertRaises(ValueError):
                matrix.validate_generation_verification(verification, matrix.NATIVE_VERIFICATION, matrix.read_manifest(pilot))

    def test_v2_cannot_mix_with_v1_or_unsupported_contract(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.convert_to_v2(pilot)
        with self.assertRaisesRegex(ValueError, "contract"):
            matrix.paired_verification(smoke, pilot)
        self.change_json(pilot / "verification.json", lambda v: v.update(verification_contract_id="future_unknown"))
        with self.assertRaisesRegex(ValueError, "contract"):
            matrix.paired_verification(smoke, pilot)

    def test_v2_requires_every_native_step_not_just_aggregate_true(self):
        directory = self.complete_attempt("smoke")
        self.convert_to_v2(directory)
        original = json.loads((directory / "verification.json").read_text())
        for change in (
            lambda v: v["records"][0]["steps"].pop(),
            lambda v: v["records"][0]["steps"][3].update(native_generate_exact=False),
            lambda v: v["records"][0]["steps"][3].update(finite=False),
            lambda v: v["records"][0]["steps"][3].update(step=4),
        ):
            value = deepcopy(original)
            change(value)
            with self.assertRaises(ValueError):
                matrix.validate_generation_verification(value, matrix.NATIVE_VERIFICATION, matrix.read_manifest(directory))

    def test_v2_negative_control_na_only_for_one_terminal_eos(self):
        directory = self.complete_attempt("smoke")
        self.convert_to_v2(directory)
        value = json.loads((directory / "verification.json").read_text())
        row = value["records"][0]
        row.update(native_generated_token_ids=[999], native_logits_count=1,
            repeatability_prefix_32_token_ids=[999], repeat_32_token_ids=[999],
            steps=[row["steps"][0]], negative_control_detected=None,
            negative_control_status="not_applicable_early_eos_no_prior_cache")
        self.assertEqual(matrix.validate_generation_verification(value, matrix.NATIVE_VERIFICATION,
                         matrix.read_manifest(directory)), matrix.NATIVE_VERIFICATION)
        row.update(native_generated_token_ids=[998], repeatability_prefix_32_token_ids=[998], repeat_32_token_ids=[998])
        with self.assertRaisesRegex(ValueError, "N/A"):
            matrix.validate_generation_verification(value, matrix.NATIVE_VERIFICATION, matrix.read_manifest(directory))

    def test_old_run_without_fixed_gpu_contract_is_not_migrated(self):
        directory = self.complete_attempt("smoke")
        self.change_json(self.root / "frozen_contract.json", lambda c: c.pop("scheduling_schema"))
        with self.assertRaisesRegex(ValueError, "new R"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_stable_assignment_is_independent_of_input_order(self):
        groups = [{**self.group, "case": case} for case in ("bf16", "a8w8_fp32", "a8w4_fp32", "a8w4_fp16")]
        expected = matrix.fixed_gpu_assignments(groups, self.contract["gpu_uuids"])
        self.assertEqual(expected, matrix.fixed_gpu_assignments(list(reversed(groups)), self.contract["gpu_uuids"]))
        self.assertEqual(list(expected.values()), self.contract["gpu_uuids"] * 2)

    def test_valid_completed_smoke_and_pilot_sources(self):
        for stage in ("smoke", "pilot"):
            directory = self.complete_attempt(stage)
            selected = matrix.stage_sources(self.root, stage, [self.group])
            self.assertEqual(Path(selected[0]["attempt"]), directory.resolve())

    def test_stale_plan_with_consistent_checksums_is_rejected(self):
        directory = self.complete_attempt("smoke")
        self.reidentify(directory, lambda identity: identity.update(plan_sha256="0" * 64))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_stale_checkpoint_with_consistent_checksums_is_rejected(self):
        directory = self.complete_attempt("smoke")
        self.reidentify(directory, lambda identity: identity.update(model_fingerprint_sha256="0" * 64))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_stale_code_with_consistent_checksums_is_rejected(self):
        directory = self.complete_attempt("smoke")
        self.reidentify(directory, lambda identity: identity.update(code_sha256={next(iter(self.sources)): "0" * 64}))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_relabelled_identity_checksum_is_rejected(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m["identity"].update(case="a8w8_fp32"))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_tampered_committed_artifact_is_rejected(self):
        directory = self.complete_attempt("smoke")
        with (directory / "generation.jsonl").open("a") as handle:
            handle.write("{}\n")
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_duplicate_rows_are_rejected_even_with_rehashed_artifacts(self):
        directory = self.complete_attempt("smoke")
        rows = [json.loads(line) for line in (directory / "generation.jsonl").read_text().split("\n") if line]
        rows[-1] = deepcopy(rows[0])
        self.write_lines(directory / "generation.jsonl", rows)
        self.rehash_artifacts(directory)
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_missing_or_wrong_row_identity_is_rejected(self):
        directory = self.complete_attempt("smoke")
        rows = [json.loads(line) for line in (directory / "generation.jsonl").read_text().split("\n") if line]
        rows[0]["identity_sha256"] = "0" * 64
        self.write_lines(directory / "generation.jsonl", rows)
        self.rehash_artifacts(directory)
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_duplicate_score_ids_are_rejected_after_artifact_rehash(self):
        directory = self.complete_attempt("smoke")
        scores = [json.loads(line) for line in (directory / "scores.jsonl").read_text().split("\n") if line]
        scores[-1] = deepcopy(scores[0])
        self.write_lines(directory / "scores.jsonl", scores)
        self.rehash_artifacts(directory)
        with self.assertRaisesRegex(ValueError, "scores"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_stale_score_identity_is_rejected_after_artifact_rehash(self):
        directory = self.complete_attempt("smoke")
        scores = [json.loads(line) for line in (directory / "scores.jsonl").read_text().split("\n") if line]
        scores[0]["identity_sha256"] = "0" * 64
        self.write_lines(directory / "scores.jsonl", scores)
        self.rehash_artifacts(directory)
        with self.assertRaisesRegex(ValueError, "score identity"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_forged_score_value_is_rejected_after_artifact_rehash(self):
        directory = self.complete_attempt("smoke")
        scores = [json.loads(line) for line in (directory / "scores.jsonl").read_text().split("\n") if line]
        scores[0]["correct_strict"] = not scores[0]["correct_strict"]
        self.write_lines(directory / "scores.jsonl", scores)
        self.rehash_artifacts(directory)
        with self.assertRaisesRegex(ValueError, "scoring"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_verification_file_is_bound_to_completed_manifest(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "verification.json", lambda v: v.update(passed=False))
        with self.assertRaisesRegex(ValueError, "verification"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_missing_embedded_verification_is_rejected(self):
        directory = self.complete_attempt("smoke")
        self.change_json(directory / "manifest.json", lambda m: m.pop("generation_verification"))
        with self.assertRaisesRegex(ValueError, "verification"):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_partial_summary_cannot_claim_completed_stage(self):
        directory = self.complete_attempt("pilot")
        self.change_json(directory / "summary.json", lambda s: s.update(n_completed=31))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "pilot", [self.group])

    def test_formal_requires_full_split(self):
        directory = self.complete_attempt("formal")
        self.assertEqual(len(matrix.stage_sources(self.root, "formal", [self.group])), 1)
        self.change_json(directory / "summary.json", lambda s: s.update(full_split=False))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "formal", [self.group])

    def test_latest_failed_attempt_is_not_silently_replaced_by_older_complete(self):
        self.complete_attempt("smoke")
        directory = self.complete_attempt("smoke", number=2)
        self.change_json(directory / "manifest.json", lambda m: m.update(state="failed"))
        with self.assertRaises(ValueError):
            matrix.stage_sources(self.root, "smoke", [self.group])

    def test_worker_records_schema_reordered_is_supported(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.change_json(pilot / "verification.json", lambda v: v["records"].reverse())
        self.assertTrue(matrix.paired_verification(smoke, pilot)["passed"])

    def test_changed_cross_process_prefix_is_rejected(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.change_json(pilot / "verification.json", lambda v: v["records"][0]["repeatability_prefix_32_token_ids"].__setitem__(3, 999))
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, pilot)

    def test_changed_verification_prompt_is_rejected(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.change_json(pilot / "verification.json", lambda v: v["records"][0].update(prompt_sha256="0" * 64))
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, pilot)

    def test_duplicate_verification_sample_is_rejected(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        self.change_json(pilot / "verification.json", lambda v: v["records"].__setitem__(1, deepcopy(v["records"][0])))
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, pilot)

    def test_empty_prefixes_do_not_establish_32_token_repeatability(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        for directory in (smoke, pilot):
            self.change_json(directory / "verification.json", lambda v: [r.update(repeatability_prefix_32_token_ids=[]) for r in v["records"]])
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, pilot)

    def test_same_attempt_cannot_establish_fresh_process_repeatability(self):
        smoke = self.complete_attempt("smoke")
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, smoke)

    def test_short_terminal_eos_prefix_is_supported(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        for directory in (smoke, pilot):
            self.change_json(directory / "verification.json", lambda v: [
                r.update(repeatability_prefix_32_token_ids=[1, 999]) for r in v["records"]])
        self.assertTrue(matrix.paired_verification(smoke, pilot)["passed"])

    def test_short_nonterminal_prefix_is_rejected(self):
        smoke, pilot = self.complete_attempt("smoke"), self.complete_attempt("pilot")
        for directory in (smoke, pilot):
            self.change_json(directory / "verification.json", lambda v: [
                r.update(repeatability_prefix_32_token_ids=[1, 2]) for r in v["records"]])
        with self.assertRaises(ValueError):
            matrix.paired_verification(smoke, pilot)

    def test_one_length_cap_passes_but_two_of_32_blocks_formal(self):
        self.complete_attempt("smoke")
        pilot = self.complete_attempt("pilot", caps=1)
        self.assertTrue(matrix.pilot_gate(self.root, [self.group], self.plan)["passed"])
        rows = [json.loads(line) for line in (pilot / "generation.jsonl").read_text().split("\n") if line]
        rows[1].update(length_capped=True, stop_reason="length")
        self.write_lines(pilot / "generation.jsonl", rows)
        self.rehash_artifacts(pilot)
        self.change_json(pilot / "summary.json", lambda s: s.update(length_capped=2))
        with self.assertRaises(ValueError):
            matrix.pilot_gate(self.root, [self.group], self.plan)
        gate = json.loads((self.root / "pilot_gate.json").read_text())
        self.assertFalse(gate["passed"])

    def test_missing_smoke_blocks_pilot_dependency(self):
        self.complete_attempt("pilot")
        with self.assertRaises(ValueError):
            matrix.pilot_gate(self.root, [self.group], self.plan)

    def test_formal_memory_uses_reserved_peak_and_both_device_free_values(self):
        pilot = self.complete_attempt("pilot")
        self.change_json(pilot / "summary.json", lambda s: s.update(
            peak_memory_allocated_bytes=100, peak_memory_reserved_bytes=200))
        args = argparse.Namespace(python=sys.executable, gpu_uuids=["GPU-11111111-1111-4111-8111-111111111111", "GPU-22222222-2222-4222-8222-222222222222"])
        with mock.patch.object(matrix, "query_cuda_memory", return_value={"free_bytes": 240, "total_bytes": 1000}) as query:
            matrix.verify_formal_memory(self.root, [self.group], args)
        self.assertEqual(query.call_args_list, [mock.call(sys.executable, gpu) for gpu in args.gpu_uuids])
        gate = json.loads((self.root / "formal_memory_gate.json").read_text())
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["required_free_bytes"], 240)

    def test_formal_memory_one_insufficient_device_blocks(self):
        pilot = self.complete_attempt("pilot")
        self.change_json(pilot / "summary.json", lambda s: s.update(
            peak_memory_allocated_bytes=300, peak_memory_reserved_bytes=200))
        args = argparse.Namespace(python=sys.executable, gpu_uuids=["GPU-11111111-1111-4111-8111-111111111111", "GPU-22222222-2222-4222-8222-222222222222"])
        with mock.patch.object(matrix, "query_cuda_memory", side_effect=[
                {"free_bytes": 1000, "total_bytes": 1000}, {"free_bytes": 359, "total_bytes": 1000}]):
            with self.assertRaisesRegex(ValueError, "memory gate"):
                matrix.verify_formal_memory(self.root, [self.group], args)
        gate = json.loads((self.root / "formal_memory_gate.json").read_text())
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["required_free_bytes"], 360)

    def test_formal_memory_zero_pilot_peak_is_not_evidence(self):
        self.complete_attempt("pilot")
        args = argparse.Namespace(python=sys.executable, gpu_uuids=["GPU-11111111-1111-4111-8111-111111111111"])
        with mock.patch.object(matrix, "query_cuda_memory", return_value={"free_bytes": 1000, "total_bytes": 1000}):
            with self.assertRaisesRegex(ValueError, "memory gate"):
                matrix.verify_formal_memory(self.root, [self.group], args)

    def supervisor_args(self, *, stages="smoke", allow_resume=False, two_groups=False):
        identities = self.directory / "identities"
        identities.mkdir(exist_ok=True)
        atomic_json(identities / f"{self.model}.json", {"fingerprint_sha256": "f" * 64})
        if two_groups:
            self.plan["matrix"] = [self.group, {**self.group, "case": "a8w8_fp32"}]
            atomic_json(self.plan_path, self.plan)
        self.contract["plan_sha256"] = sha256_file(self.plan_path)
        self.contract["group_gpu_uuids"] = matrix.fixed_gpu_assignments(self.plan["matrix"], self.contract["gpu_uuids"])
        atomic_json(self.root / "frozen_contract.json", self.contract)
        readiness_path = self.directory / "readiness.json"
        atomic_json(readiness_path, {"ready": True, "plan_sha256": sha256_file(self.plan_path),
                    "source_hashes": self.sources, "evidence_hashes": {}, "package_versions": self.contract["package_versions"],
                    "gpu_uuids": ["GPU-11111111-1111-4111-8111-111111111111", "GPU-22222222-2222-4222-8222-222222222222"]})
        return argparse.Namespace(plan=self.plan_path, readiness=readiness_path,
            run_root=self.root, model_identities=identities, model_root=self.directory / "models",
            gpu_uuids=["GPU-11111111-1111-4111-8111-111111111111", "GPU-22222222-2222-4222-8222-222222222222"], cpu_sets=["8", "9"],
            python=sys.executable, stages=stages, driver_library_dir=None, allow_resume=allow_resume)

    def main_patches(self, args):
        stack = ExitStack()
        fake_here = self.directory / "exp"
        fake_here.mkdir(exist_ok=True)
        stack.enter_context(mock.patch.object(matrix, "HERE", fake_here))
        stack.enter_context(mock.patch.object(matrix, "parse_args", return_value=args))
        stack.enter_context(mock.patch.object(matrix, "load_plan", return_value=self.plan))
        stack.enter_context(mock.patch.object(matrix, "host_memory_ok", return_value=True))
        return stack

    def sync_supervisor_contract(self, args):
        atomic_json(self.plan_path, self.plan)
        self.contract.update(plan_sha256=sha256_file(self.plan_path),
            protocol_sha256=canonical_hash(self.plan["protocol"]),
            verification_contract_id=matrix.verification_contract_id(self.plan),
            gpu_uuids=[matrix.canonical_gpu_uuid(gpu) for gpu in args.gpu_uuids],
            group_gpu_uuids=matrix.fixed_gpu_assignments(self.plan["matrix"], args.gpu_uuids))
        atomic_json(self.root / "frozen_contract.json", self.contract)
        self.change_json(args.readiness, lambda r: r.update(plan_sha256=sha256_file(self.plan_path)))

    def test_fixed_slot_survives_unequal_worker_durations_across_all_stages(self):
        args = self.supervisor_args(stages="smoke,pilot,formal")
        self.plan["matrix"] = [{**self.group, "case": case} for case in
                               ("bf16", "a8w8_fp32", "a8w4_fp32", "a8w4_fp16")]
        self.sync_supervisor_contract(args)
        launches = []

        class CPUProcessFixture:
            def __init__(self, polls, pid):
                self.remaining, self.pid = polls, pid
            def poll(self):
                self.remaining -= 1
                return None if self.remaining > 0 else 0

        def launch(command, **kwargs):
            stage, case = command[command.index("--stage") + 1], command[command.index("--case") + 1]
            group = next(g for g in self.plan["matrix"] if g["case"] == case)
            folder = self.complete_attempt(stage, group=group)
            gpu = kwargs["env"]["CUDA_VISIBLE_DEVICES"]
            self.change_json(folder / "manifest.json", lambda m: m["environment"].update(
                gpu_uuid=gpu.removeprefix("GPU-"), CUDA_VISIBLE_DEVICES=gpu))
            if stage == "pilot":
                self.change_json(folder / "summary.json", lambda s: s.update(
                    peak_memory_allocated_bytes=100, peak_memory_reserved_bytes=200))
            launches.append((stage, case, gpu))
            slow = (stage == "smoke" and case == "bf16") or (stage == "pilot" and case == "a8w8_fp32")
            return CPUProcessFixture(4 if slow else 1, 100000 + len(launches))

        with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen", side_effect=launch), \
                mock.patch.object(matrix.time, "sleep"), mock.patch.object(matrix, "query_cuda_memory",
                    return_value={"free_bytes": 1000, "total_bytes": 1000}), redirect_stdout(io.StringIO()):
            matrix.main()
        self.assertEqual(len(launches), 12)
        for stage, case, gpu in launches:
            self.assertEqual(gpu, self.contract["group_gpu_uuids"][f"{self.model}/{case}"], (stage, case))
        state = json.loads((self.root / "current_state.json").read_text())
        self.assertEqual(state["state"], "generated_pending_review")

    def test_reversing_device_order_does_not_silently_rebind_existing_run(self):
        args = self.supervisor_args(allow_resume=True)
        self.complete_attempt("smoke")
        args.gpu_uuids.reverse()
        with self.main_patches(args), self.assertRaisesRegex(ValueError, "another frozen"):
            matrix.main()

    def test_finalizer_logs_use_supervisor_attempt_and_stay_cpu_only(self):
        args = self.supervisor_args(stages="formal", allow_resume=True)
        self.complete_attempt("smoke")
        pilot = self.complete_attempt("pilot")
        self.change_json(pilot / "summary.json", lambda s: s.update(
            peak_memory_allocated_bytes=100, peak_memory_reserved_bytes=200))
        self.complete_attempt("formal")
        fake_here = self.directory / "exp"
        fake_here.mkdir()
        entry = fake_here / "summarize_gsm8k.py"
        entry.write_text("# Explicit CPU finalizer test fixture\n")
        command = [args.python, "-B", str(entry)]
        atomic_json(self.root / "finalizer_readiness.json", {"ready": True,
            "source_hashes": {str(entry): sha256_file(entry)}, "commands": [command]})
        with self.main_patches(args), mock.patch.object(matrix, "query_cuda_memory", return_value={
                "free_bytes": 1000, "total_bytes": 1000}), mock.patch.object(matrix.subprocess, "run") as finalizer:
            matrix.main()
            matrix.main()
        self.assertEqual(finalizer.call_count, 2)
        self.assertTrue(all(call.kwargs["env"]["CUDA_VISIBLE_DEVICES"] == "" for call in finalizer.call_args_list))
        self.assertTrue((self.root / "finalizer_supervisor_AT001_1.log").exists())
        self.assertTrue((self.root / "finalizer_supervisor_AT002_1.log").exists())

    def test_reuse_cannot_bypass_identity_validation(self):
        args = self.supervisor_args(allow_resume=True)
        directory = self.complete_attempt("smoke")
        self.reidentify(directory, lambda identity: identity.update(plan_sha256="0" * 64))
        with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen") as launch:
            with self.assertRaises(ValueError):
                matrix.main()
            launch.assert_not_called()

    def test_valid_completed_reuse_does_not_launch_a_new_worker(self):
        args = self.supervisor_args(allow_resume=True)
        self.complete_attempt("smoke")
        with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen") as launch:
            matrix.main()
            launch.assert_not_called()
        state = json.loads((self.root / "current_state.json").read_text())
        self.assertEqual(state["state"], "completed")
        self.assertTrue(state["completed"][0]["reused"])

    def test_formal_cannot_launch_before_pilot_gate(self):
        args = self.supervisor_args(stages="formal")
        with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen") as launch:
            with self.assertRaises(ValueError):
                matrix.main()
            launch.assert_not_called()

    def test_failed_pilot_gate_does_not_query_cuda_or_launch_formal(self):
        args = self.supervisor_args(stages="formal")
        self.complete_attempt("smoke")
        self.complete_attempt("pilot", caps=2)
        with self.main_patches(args), mock.patch.object(matrix, "query_cuda_memory") as query, \
                mock.patch.object(matrix.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "pilot gate"):
                matrix.main()
            launch.assert_not_called()
            query.assert_not_called()

    def test_failed_formal_memory_gate_prevents_worker_launch(self):
        args = self.supervisor_args(stages="formal")
        self.complete_attempt("smoke")
        pilot = self.complete_attempt("pilot")
        self.change_json(pilot / "summary.json", lambda s: s.update(
            peak_memory_allocated_bytes=100, peak_memory_reserved_bytes=200))
        with self.main_patches(args), mock.patch.object(matrix, "query_cuda_memory", return_value={
                "free_bytes": 239, "total_bytes": 1000}) as query, \
                mock.patch.object(matrix.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "memory gate"):
                matrix.main()
            launch.assert_not_called()
            self.assertEqual(query.call_count, 2)

    def test_second_slot_launch_failure_drains_live_cpu_child_and_inherits_lock(self):
        args = self.supervisor_args(two_groups=True)
        real_popen = subprocess.Popen
        children, inherited_fds = [], []
        marker = self.directory / "explicit_cpu_standin.txt"
        program = "import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); p.write_text('CPU test running'); time.sleep(.15); p.write_text('CPU test complete')"

        def launch(command, **kwargs):
            if children:
                raise OSError("injected second-slot CPU launch failure")
            inherited_fds.extend(kwargs.get("pass_fds", ()))
            kwargs["env"] = {**kwargs.get("env", {}), "CUDA_VISIBLE_DEVICES": ""}
            child = real_popen([sys.executable, "-c", program, str(marker)], **kwargs)
            children.append(child)
            return child

        try:
            with self.main_patches(args), mock.patch.object(matrix.subprocess, "Popen", side_effect=launch):
                with self.assertRaisesRegex(OSError, "injected second-slot"):
                    matrix.main()
            self.assertEqual(len(children), 1, "fault test must actually launch the explicit CPU stand-in")
            self.assertIsNotNone(children[0].poll(), "supervisor released its locks while a child remained alive")
            self.assertTrue(inherited_fds, "child must inherit its GPU lock FD across supervisor exit")
            self.assertEqual(marker.read_text(), "CPU test complete")
            state = json.loads((self.root / "current_state.json").read_text())
            self.assertEqual(state["state"], "failed")
            self.assertFalse(state["active"], "drained children must not remain registered as active")
        finally:
            for child in children:
                child.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    os.sched_setaffinity(0, {8, 9})
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MatrixSafetyTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    final_hashes = {name: sha256_file(Path(__file__).with_name(name)) for name in ENTRY_SOURCE_HASHES}
    sources_stable = final_hashes == ENTRY_SOURCE_HASHES
    if not sources_stable:
        print("Source changed during CPU audit; evidence is not qualified for either version", file=sys.stderr)
    if args.audit_output:
        atomic_json(args.audit_output, {
            "schema": "scalellm_gsm8k_matrix_cpu_safety_audit_v1",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "success": result.wasSuccessful() and sources_stable, "tests_run": result.testsRun,
            "failures": [{"test": str(test), "traceback": detail} for test, detail in result.failures],
            "errors": [{"test": str(test), "traceback": detail} for test, detail in result.errors],
            "matrix_sha256": ENTRY_SOURCE_HASHES["run_gsm8k_matrix.py"],
            "worker_sha256": ENTRY_SOURCE_HASHES["run_gsm8k_worker.py"],
            "test_sha256": ENTRY_SOURCE_HASHES["test_gsm8k_matrix.py"],
            "source_hashes_at_finish": final_hashes, "sources_unchanged_during_test": sources_stable,
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "scope": "temporary CPU fixtures and explicit CPU subprocess fault injection; no GPU/EDA/model loading",
        })
    return 0 if result.wasSuccessful() and sources_stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
