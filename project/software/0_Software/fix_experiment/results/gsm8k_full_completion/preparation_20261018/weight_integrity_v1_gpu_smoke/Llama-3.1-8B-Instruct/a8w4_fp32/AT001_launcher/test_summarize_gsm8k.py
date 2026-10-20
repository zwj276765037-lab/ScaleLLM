"""Synthetic temporary fixtures for independent GSM8K validation; no GPU runs."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import summarize_gsm8k as summary
import render_accuracy_table as renderer
from gsm8k_protocol import atomic_json, canonical_hash, load_plan, sha256_file
from six_model_matrix import FIVE_CONFIG_CASES, MODEL_SPECS
from test_gsm8k_integrity_contract import attach_integrity, save_integrity, INTEGRITY_CONTRACT_ID, GPU0


class FixtureTokenizer:
    bos_token_id, eos_token_id, pad_token_id = 1, 3, 0
    padding_side = "right"
    special_tokens_map = {"eos_token": "fixture_eos"}

    def get_vocab(self):
        return {str(index): index for index in range(256)}

    def encode(self, text, **kwargs):
        return [10, 11]

    def decode(self, ids, skip_special_tokens=True, **kwargs):
        return bytes([token for token in ids if not skip_special_tokens or token != 3]).decode()


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class GroupFixture:
    """Clearly synthetic files live exclusively under TemporaryDirectory."""
    def __init__(self, root):
        self.root = root
        self.attempt = root / "synthetic_AT001"
        self.attempt.mkdir()
        self.tokenizer = FixtureTokenizer()
        self.plan = load_plan()
        self.plan["data"] = {"fixture_only": True}
        self.plan_hash = "fixture_plan_sha256"
        self.model, self.case = "Llama-3.2-3B-Instruct", "bf16"
        self.oracle = summary.HarnessOracle(self.plan["protocol"])
        self.requests = []
        for index in range(1319):
            prompt, question = f"fixture prompt {index}", f"fixture question {index}"
            self.requests.append({"sample_id": f"test:{index:04d}", "row_index": index, "split": "test",
                "question": question, "gold": "fixture reasoning\n#### 2", "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "fewshot_train_indices": [0, 1, 2, 3, 4]})
        entries = [{"name": name, "bytes": 1, "sha256": "a" * 64}
                   for name in ("config.json", "model.safetensors", "tokenizer_config.json")]
        model_identity = {"schema": "scalellm_checkpoint_identity_v1", "checkpoint_name": self.model,
            "files": entries, "file_count": 3, "total_bytes": 3, "resolved_path": str(root / self.model),
            "fingerprint_sha256": hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
        codes = {}
        for name in summary.NUMERICAL_FILES:
            file = root / name
            file.write_text("synthetic test source " + name)
            codes[str(file)] = sha256_file(file)
        self.historical_codes = summary.hash_by_name(codes)
        method = {"case": "bf16", "dtype": "bfloat16", "attention_implementation": "eager", "use_cache": True}
        self.generation = {"effective_generation_config": {"do_sample": False, "num_beams": 1,
            "num_return_sequences": 1, "max_new_tokens": 4096, "use_cache": True,
            "repetition_penalty": 1., "no_repeat_ngram_size": 0, "cache_implementation": "dynamic"},
            "context_length": 8192, "temperature_argument_passed": False,
            "stop_strings": ["Question:", "</s>", "<|im_end|>"], "eos_token_ids": [3]}
        encoded = {req["sample_id"]: [10, 11] for req in self.requests}
        self.identity = {"protocol_id": self.plan["protocol_id"], "plan_sha256": self.plan_hash,
            "protocol_sha256": canonical_hash(self.plan["protocol"]), "data": self.plan["data"],
            "requests_sha256": canonical_hash(self.requests), "stage": "formal", "case": "bf16",
            "seed": self.plan["protocol"]["seed"], "model_fingerprint_sha256": model_identity["fingerprint_sha256"],
            "method": method, "generation": self.generation, "code_sha256": codes,
            "package_versions": {"lm_eval": "0.4.11"},
            "token_audit": {"input_token_ids_sha256": canonical_hash(encoded), "input_truncation": False},
            "tokenizer": {"class": type(self.tokenizer).__module__ + ".FixtureTokenizer",
                "vocab_sha256": canonical_hash(self.tokenizer.get_vocab()), "special_tokens_map": self.tokenizer.special_tokens_map,
                "bos_token_id": 1, "eos_token_id": 3, "pad_token_id": 0, "add_bos_token": None, "padding_side": "right"}}
        self.identity_hash = canonical_hash(self.identity)
        self.manifest = {"schema": "scalellm_gsm8k_worker_manifest_v1", "state": "complete", "stage": "formal",
            "model": self.model, "case": self.case, "identity": self.identity, "identity_sha256": self.identity_hash,
            "model_identity": model_identity, "method": method, "generation": self.generation}
        self.historical = {"model_identity": copy.deepcopy(model_identity), "method": {**method, "use_cache": False}}
        self.contract = {"plan_sha256": self.plan_hash, "protocol_sha256": self.identity["protocol_sha256"],
            "package_versions": self.identity["package_versions"], "stage_requests_sha256": {"formal": self.identity["requests_sha256"]},
            "model_fingerprints": {self.model: self.identity["model_fingerprint_sha256"]}, "source_hashes": codes}
        self.rows, self.scores = [], []
        for req in self.requests:
            tokens = list(b"#### 2") + [3]
            row = {"schema": "scalellm_gsm8k_generation_v1", "status": "complete", "identity_sha256": self.identity_hash,
                **{key: req[key] for key in ("sample_id", "row_index", "split", "prompt_sha256", "fewshot_train_indices", "gold")},
                "question_sha256": hashlib.sha256(req["question"].encode()).hexdigest(),
                "input_tokens": 2, "input_token_ids_sha256": canonical_hash([10, 11]), "new_token_ids": tokens,
                "output_tokens": len(tokens), "raw_text": "#### 2\x03", "decoded_text_skip_special_tokens": "#### 2",
                "scoring_text": "#### 2", "stop_strings": self.generation["stop_strings"], "eos_token_ids": [3],
                "stop_reason": "eos", "matched_stop_string": None, "length_capped": False,
                "generation_limit_reached": False, "use_cache": True, "elapsed_seconds": .5,
                "peak_memory_allocated_bytes": 100, "peak_memory_reserved_bytes": 200}
            self.rows.append(row)
            self.scores.append({"sample_id": row["sample_id"], "identity_sha256": self.identity_hash,
                "scoring_text": "#### 2", "gold": req["gold"], **self.oracle.score("#### 2", req["gold"])})
        self.worker_summary = {"state": "complete", "stage": "formal", "n_expected": 1319,
            "n_completed": 1319, "n_errors": 0, "full_split": True, "correct_strict": 1319,
            "correct_flexible": 1319, "invalid_strict": 0, "length_capped": 0,
            "exact_match,strict-match": 1., "exact_match,flexible-extract": 1.}
        self.save()

    def save(self, update_hashes=True):
        atomic_json(self.attempt / "requests.json", self.requests)
        write_jsonl(self.attempt / "generation.jsonl", self.rows)
        write_jsonl(self.attempt / "scores.jsonl", self.scores)
        atomic_json(self.attempt / "summary.json", self.worker_summary)
        if update_hashes:
            self.manifest["artifacts"] = {name: sha256_file(self.attempt / name)
                for name in ("generation.jsonl", "scores.jsonl", "requests.json")}
        atomic_json(self.attempt / "manifest.json", self.manifest)

    def validate(self):
        return summary.validate_group(self.attempt, self.model, self.case, self.plan, self.plan_hash,
            self.requests, self.historical, self.historical_codes, self.contract, self.oracle, self.tokenizer)


class IndependentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = GroupFixture(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def enable_integrity(self):
        f = self.fixture
        f.plan["protocol"]["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        f.identity.update(integrity_contract_id=INTEGRITY_CONTRACT_ID,
                          protocol_sha256=canonical_hash(f.plan["protocol"]))
        f.contract.update(integrity_contract_id=INTEGRITY_CONTRACT_ID,
                          protocol_sha256=f.identity["protocol_sha256"],
                          group_gpu_uuids={f"{f.model}/{f.case}": GPU0})
        for name in ("gsm8k_weight_integrity.py", "run_eval_worker.py", "run_gsm8k_worker.py", "gsm8k_protocol.py"):
            path = f.root / name
            path.write_text("explicit CPU fixture source " + name)
            f.identity["code_sha256"][str(path)] = sha256_file(path)
        f.contract["source_hashes"] = f.identity["code_sha256"]
        f.identity_hash = canonical_hash(f.identity)
        f.manifest.update(identity=f.identity, identity_sha256=f.identity_hash,
                          environment={"gpu_uuid": GPU0, "CUDA_VISIBLE_DEVICES": GPU0, "device": "cuda:0"})
        for row in f.rows + f.scores:
            row["identity_sha256"] = f.identity_hash
        f.save()
        return attach_integrity(f.attempt, f.manifest, f.worker_summary,
                                [r["sample_id"] for r in f.requests])

    def test_formal_integrity_contents_and_terminal_guard_are_required(self):
        f = self.fixture
        data = self.enable_integrity()
        _, _, evidence = f.validate()
        self.assertEqual(evidence["integrity"]["contract_id"], INTEGRITY_CONTRACT_ID)
        data["phase_checks"][-1]["observed_root_sha256"] = "f" * 64
        save_integrity(f.attempt, f.manifest, f.worker_summary, data)
        with self.assertRaisesRegex(ValueError, "phase content"):
            f.validate()

    def test_formal_integrity_missing_sample_guard_cannot_pass_after_rehash(self):
        f = self.fixture
        data = self.enable_integrity()
        data["phase_checks"].pop(-2)
        save_integrity(f.attempt, f.manifest, f.worker_summary, data)
        with self.assertRaisesRegex(ValueError, "all calls"):
            f.validate()

    def test_formal_legacy_evidence_cannot_gain_integrity_qualification(self):
        f = self.fixture
        f.plan["protocol"]["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        f.contract["integrity_contract_id"] = INTEGRITY_CONTRACT_ID
        # This is rejected at the frozen identity boundary, before accepting any score.
        with self.assertRaises(ValueError):
            f.validate()

    def test_complete_1319_rows_are_independently_validated(self):
        result, rows, source = self.fixture.validate()
        self.assertEqual(result["correct_strict"], 1319)
        self.assertEqual(result["strict_em"], 1.)
        self.assertTrue(result["full_split"])
        self.assertEqual(len(rows), 1319)
        self.assertTrue(source["accepted"])

    def test_correctness_tampering_fails_even_after_artifact_rehash(self):
        f = self.fixture
        f.scores[0]["correct_strict"] = False
        f.save()
        with self.assertRaisesRegex(ValueError, "independent harness score mismatch"):
            f.validate()

    def test_raw_text_tampering_fails_even_after_artifact_rehash(self):
        f = self.fixture
        f.rows[0]["raw_text"] = "#### 999"
        f.save()
        with self.assertRaisesRegex(ValueError, "continuation mismatch"):
            f.validate()

    def test_natural_wrong_answer_is_valid_execution_and_scores_zero(self):
        f = self.fixture
        f.rows[0].update(new_token_ids=list(b"#### 3")+[3], raw_text="#### 3\x03",
                         decoded_text_skip_special_tokens="#### 3", scoring_text="#### 3")
        f.scores[0].update(scoring_text="#### 3", **f.oracle.score("#### 3", f.requests[0]["gold"]))
        f.worker_summary.update(correct_strict=1318, correct_flexible=1318,
            **{"exact_match,strict-match": 1318/1319, "exact_match,flexible-extract": 1318/1319})
        f.save()
        result, _, _ = f.validate()
        self.assertEqual(result["correct_strict"], 1318)
        self.assertTrue(result["full_split"])

    def test_artifact_hash_tampering_is_detected(self):
        f = self.fixture
        f.scores[0]["correct_strict"] = False
        f.save(update_hashes=False)
        with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
            f.validate()

    def test_duplicate_and_missing_generation_ids_are_rejected(self):
        f = self.fixture
        original = copy.deepcopy(f.rows)
        f.rows[-1] = copy.deepcopy(f.rows[0])
        f.save()
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            f.validate()
        f.rows = original[:-1]
        f.save()
        with self.assertRaisesRegex(ValueError, "missing, extra"):
            f.validate()

    def test_duplicate_and_missing_score_ids_are_rejected(self):
        f = self.fixture
        original = copy.deepcopy(f.scores)
        f.scores[-1] = copy.deepcopy(f.scores[0])
        f.save()
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            f.validate()
        f.scores = original[:-1]
        f.save()
        with self.assertRaisesRegex(ValueError, "missing, extra"):
            f.validate()

    def test_different_protocol_identity_is_rejected(self):
        f = self.fixture
        f.identity["protocol_sha256"] = "changed"
        f.manifest["identity_sha256"] = canonical_hash(f.identity)
        f.save()
        with self.assertRaisesRegex(ValueError, "execution identity mismatch"):
            f.validate()

    def test_different_historical_checkpoint_is_rejected(self):
        f = self.fixture
        f.historical["model_identity"]["fingerprint_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "historical checkpoint fingerprint"):
            f.validate()

    def test_different_numerical_source_is_rejected(self):
        f = self.fixture
        f.historical_codes["mlp4_method_inference.py"] = "changed"
        with self.assertRaisesRegex(ValueError, "numerical code identity mismatch"):
            f.validate()

    def test_summary_recount_and_tokenizer_identity_are_enforced(self):
        f = self.fixture
        f.worker_summary["correct_strict"] = 1318
        f.save()
        with self.assertRaisesRegex(ValueError, "independent full-test recount"):
            f.validate()
        f.worker_summary["correct_strict"] = 1319
        f.identity["tokenizer"]["vocab_sha256"] = "changed"
        f.manifest["identity_sha256"] = canonical_hash(f.identity)
        f.save()
        with self.assertRaisesRegex(ValueError, "tokenizer runtime identity"):
            f.validate()

    def test_completed_truncated_jsonl_is_rejected(self):
        f = self.fixture
        file = f.attempt / "generation.jsonl"
        file.write_bytes(file.read_bytes()[:-1])
        f.manifest["artifacts"]["generation.jsonl"] = sha256_file(file)
        atomic_json(f.attempt / "manifest.json", f.manifest)
        with self.assertRaisesRegex(ValueError, "unterminated JSONL"):
            f.validate()


def fake_history():
    return {(spec.name, case): {"values": {task: .2 for task in summary.HISTORICAL_TASKS},
        "run": {"model_identity": {"fingerprint_sha256": "fixture"}}}
        for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES}


class MergeRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def csv(self, rows):
        file = self.root / "synthetic_six_task.csv"
        summary.write_csv(file, rows, ["model", "case", "model_fingerprint_sha256", *summary.TASKS,
            "macro_accuracy", "status", "gsm8k_full_split", "gsm8k_independent_harness_validated",
            "gsm8k_protocol_id", "gsm8k_attempt"])
        count = sum(row["gsm8k"] != "" for row in rows)
        atomic_json(self.root / "validation.json", {"schema": "scalellm_gsm8k_independent_validation_v1",
            "groups_validated": count, "full_validated": count == 30,
            "artifacts": {"six_task_with_gsm8k.csv": sha256_file(file)}})
        return file

    def test_partial_merge_never_computes_five_task_average(self):
        rows = summary.merge_rows(fake_history(), {})
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(row["gsm8k"] == row["macro_accuracy"] == "" for row in rows))
        result = {"strict_em": .6, "protocol_id": "fixture_protocol", "attempt": "synthetic"}
        rows = summary.merge_rows(fake_history(), {(MODEL_SPECS[0].name, "bf16"): result})
        self.assertAlmostEqual(rows[0]["macro_accuracy"], (5*.2+.6)/6)
        self.assertTrue(all(row["macro_accuracy"] == "" for row in rows[1:]))

    def test_partial_summarizer_writes_missing_status_without_claiming_completion(self):
        run = self.root / "synthetic_run"
        run.mkdir()
        atomic_json(run / "frozen_contract.json", {})
        with patch.object(summary, "load_history", return_value=(fake_history(), {"numerical_code_hashes": {}})), \
             patch.object(summary, "prepare_requests", return_value=[]):
            validation = summary.summarize(run, summary.DEFAULT_PLAN, self.root / "allowed_partial", True)
            with self.assertRaisesRegex(ValueError, "not fully validated: 0/30"):
                summary.summarize(run, summary.DEFAULT_PLAN, self.root / "rejected_partial", False)
        self.assertFalse(validation["full_validated"])
        self.assertEqual(validation["groups_validated"], 0)
        self.assertEqual(len(validation["missing"]), 30)
        with (self.root / "allowed_partial/six_task_with_gsm8k.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(row["gsm8k"] == row["macro_accuracy"] == "" for row in rows))

    def test_duplicate_formal_source_selection_is_rejected_even_with_partial_flag(self):
        run = self.root / "synthetic_run"
        run.mkdir()
        atomic_json(run / "frozen_contract.json", {})
        group = {"model": MODEL_SPECS[0].name, "case": "bf16", "attempt": "synthetic"}
        atomic_json(run / "formal_sources.json", {"groups": [group, group]})
        with patch.object(summary, "load_history", return_value=(fake_history(), {"numerical_code_hashes": {}})), \
             patch.object(summary, "prepare_requests", return_value=[]):
            with self.assertRaisesRegex(ValueError, "duplicate/unexpected"):
                summary.summarize(run, summary.DEFAULT_PLAN, self.root / "rejected_duplicate_sources", True)

    def test_renderer_rejects_a_partial_row_with_fake_average(self):
        rows = summary.merge_rows(fake_history(), {})
        rows[0]["macro_accuracy"] = .2
        with self.assertRaisesRegex(ValueError, "partial row must not"):
            renderer.load_rows(self.csv(rows))

    def test_renderer_rejects_unvalidated_score_and_wrong_average(self):
        result = {"strict_em": .6, "protocol_id": "fixture_protocol", "attempt": "synthetic"}
        rows = summary.merge_rows(fake_history(), {(MODEL_SPECS[0].name, "bf16"): result})
        rows[0]["gsm8k_independent_harness_validated"] = False
        with self.assertRaisesRegex(ValueError, "lacks independent"):
            renderer.load_rows(self.csv(rows))
        rows[0]["gsm8k_independent_harness_validated"] = True
        rows[0]["macro_accuracy"] = .2
        with self.assertRaisesRegex(ValueError, "average differs"):
            renderer.load_rows(self.csv(rows))

    def test_renderer_creates_three_formats_and_preserves_existing_outputs(self):
        result = {"strict_em": .6, "protocol_id": "fixture_protocol", "attempt": "synthetic"}
        rows = summary.merge_rows(fake_history(), {(MODEL_SPECS[0].name, "bf16"): result})
        file = self.csv(rows)
        output = self.root / "synthetic_render"
        manifest = renderer.render(file, output)
        self.assertEqual(manifest["gsm8k_groups_validated"], 1)
        self.assertEqual(manifest["font_family"], "STIXGeneral")
        self.assertTrue((output / "accuracy_table.png").read_bytes().startswith(b"\x89PNG"))
        self.assertTrue((output / "accuracy_table.pdf").read_bytes().startswith(b"%PDF"))
        md = (output / "accuracy_table.md").read_text()
        self.assertIn("**1/30**", md)
        self.assertIn("26.67", md)
        self.assertIn("5-shot", md)
        self.assertIn("0-shot", md)
        self.assertNotIn("PPL", md)
        old = (output / "accuracy_table.png").read_bytes()
        with self.assertRaises(FileExistsError):
            renderer.render(file, output)
        self.assertEqual((output / "accuracy_table.png").read_bytes(), old)

    def test_renderer_requires_validation_artifact_identity(self):
        result = {"strict_em": .6, "protocol_id": "fixture_protocol", "attempt": "synthetic"}
        rows = summary.merge_rows(fake_history(), {(MODEL_SPECS[0].name, "bf16"): result})
        file = self.csv(rows)
        (self.root / "validation.json").unlink()
        with self.assertRaisesRegex(ValueError, "requires the independent"):
            renderer.render(file, self.root / "no_proof")
        self.csv(rows)
        proof = json.loads((self.root / "validation.json").read_text())
        proof["artifacts"]["six_task_with_gsm8k.csv"] = "changed"
        atomic_json(self.root / "validation.json", proof)
        with self.assertRaisesRegex(ValueError, "differs from its independent"):
            renderer.render(file, self.root / "bad_proof")


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = load_plan()
        self.groups = []
        for spec in MODEL_SPECS:
            for case in FIVE_CONFIG_CASES:
                repeat = {"passed": True}
                for stage in ("smoke", "pilot"):
                    folder = self.root / stage / spec.name / case / "synthetic_AT001"
                    folder.mkdir(parents=True)
                    verification = {"passed": True, "all_qdq_projections_prefill_and_decode": True,
                        "records": [{"sample_id": f"train:{index:04d}", "prompt_sha256": f"fixture{index}",
                            "repeatability_prefix_32_token_ids": [8] * 32,
                            "greedy_16_equal": True, "same_process_repeat_32_equal": True,
                            "logits_allclose": True, "atol": .125, "rtol": .01} for index in range(2)]}
                    atomic_json(folder / "verification.json", verification)
                    atomic_json(folder / "manifest.json", {"state": "complete", "stage": stage,
                        "model": spec.name, "case": case, "generation": {"eos_token_ids": [3]},
                        "environment": {"gpu_uuid": "fixture_gpu_uuid"}})
                    repeat[stage] = str(folder)
                    repeat[f"{stage}_verification_sha256"] = sha256_file(folder / "verification.json")
                self.groups.append({"model": spec.name, "case": case, "passed": True,
                                    "n": 32, "length_capped_count": 0, "repeatability": repeat})
        self.save()

    def save(self):
        atomic_json(self.root / "pilot_gate.json", {"passed": True, "groups": self.groups})

    def tearDown(self):
        self.temp.cleanup()

    def test_requires_passed_30_group_pilot_qualification(self):
        result = summary.validate_generation_qualification(self.root, self.plan)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["groups"]), 30)
        self.groups.pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "30-group"):
            summary.validate_generation_qualification(self.root, self.plan)

    def test_changed_independent_process_prefix_is_rejected(self):
        repeat = self.groups[0]["repeatability"]
        file = Path(repeat["pilot"]) / "verification.json"
        data = json.loads(file.read_text())
        data["records"][0]["repeatability_prefix_32_token_ids"][0] = 9
        atomic_json(file, data)
        repeat["pilot_verification_sha256"] = sha256_file(file)
        self.save()
        with self.assertRaisesRegex(ValueError, "differ across independent"):
            summary.validate_generation_qualification(self.root, self.plan)

    def test_repeatability_requires_actual_same_gpu_uuid(self):
        repeat = self.groups[0]["repeatability"]
        file = Path(repeat["pilot"]) / "manifest.json"
        manifest = json.loads(file.read_text())
        manifest["environment"]["gpu_uuid"] = "different_fixture_gpu_uuid"
        atomic_json(file, manifest)
        with self.assertRaisesRegex(ValueError, "different GPU devices"):
            summary.validate_generation_qualification(self.root, self.plan)
        manifest["environment"]["gpu_uuid"] = "unknown"
        atomic_json(file, manifest)
        with self.assertRaisesRegex(ValueError, "lacks actual GPU UUID"):
            summary.validate_generation_qualification(self.root, self.plan)

    def test_pilot_length_gate_and_unchanged_tolerance_are_enforced(self):
        self.groups[0]["length_capped_count"] = 2
        self.save()
        with self.assertRaisesRegex(ValueError, "length budget"):
            summary.validate_generation_qualification(self.root, self.plan)
        self.groups[0]["length_capped_count"] = 0
        repeat = self.groups[0]["repeatability"]
        file = Path(repeat["pilot"]) / "verification.json"
        data = json.loads(file.read_text())
        data["records"][0]["atol"] = .25
        atomic_json(file, data)
        repeat["pilot_verification_sha256"] = sha256_file(file)
        self.save()
        with self.assertRaisesRegex(ValueError, "tolerance changed"):
            summary.validate_generation_qualification(self.root, self.plan)


class OracleTests(unittest.TestCase):
    def test_harness_first_strict_last_flexible_and_numeric_string_policy(self):
        oracle = summary.HarnessOracle(load_plan()["protocol"])
        result = oracle.score("thinking\n#### 18\n#### 19", "rationale\n#### 18")
        self.assertTrue(result["correct_strict"])
        self.assertFalse(result["correct_flexible"])
        self.assertEqual(result["strict_prediction"], "18")
        self.assertEqual(result["flexible_prediction"], "19")
        self.assertFalse(oracle.score("#### 18.0", "#### 18")["correct_strict"])
        self.assertTrue(oracle.score("#### 1,234.", "#### 1234")["correct_strict"])
        self.assertTrue(oracle.score("no final marker", "#### 18")["invalid_strict"])


class NativeQualificationTests(unittest.TestCase):
    def test_real_producer_json_is_accepted_and_fake_na_or_step_flags_are_rejected(self):
        from test_gsm8k_worker import fixture_cache_model, Tokenizer, request
        from run_gsm8k_worker import verify_generation, resolve_generation
        from transformers import GenerationConfig
        config = GenerationConfig(max_new_tokens=64, eos_token_id=[3], return_dict_in_generate=True)
        with patch("run_eval_worker.configure_reproducibility"):
            ordinary = verify_generation(fixture_cache_model(cache_off_drift=True), Tokenizer(),
                                          [request(), request(1)], config, "cpu", 1)
            early = verify_generation(fixture_cache_model(early_eos=True), Tokenizer(),
                                       [request(), request(1)], config, "cpu", 1)
        for row in ordinary["records"] + early["records"]:
            summary.validate_native_record(row, [3], 1)
        self.assertFalse(ordinary["records"][0]["logits_allclose"])
        bad = copy.deepcopy(ordinary["records"][0])
        bad.update(negative_control_detected=None, negative_control_status="not_applicable_early_eos_no_prior_cache",
                   negative_control_qualified=True, negative_control={"prior_cache_available": False})
        with self.assertRaisesRegex(ValueError, "single native EOS"):
            summary.validate_native_record(bad, [3], 1)
        bad = copy.deepcopy(early["records"][0])
        bad["steps"][0]["finite"] = False
        with self.assertRaisesRegex(ValueError, "per-step hard evidence"):
            summary.validate_native_record(bad, [3], 1)
        bad = copy.deepcopy(ordinary["records"][0])
        bad["steps"][1]["kv_layers"][0]["value_exact"] = False
        with self.assertRaisesRegex(ValueError, "full K/V comparison failed"):
            summary.validate_native_record(bad, [3], 1)


if __name__ == "__main__":
    unittest.main()
