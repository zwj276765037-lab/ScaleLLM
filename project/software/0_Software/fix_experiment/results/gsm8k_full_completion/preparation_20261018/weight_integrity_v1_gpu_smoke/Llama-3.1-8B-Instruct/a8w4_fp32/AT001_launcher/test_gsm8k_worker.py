"""CPU checks for committed evidence, strict resume identity and generation policy."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import run_gsm8k_worker as worker


def request(index: int = 0, split: str = "train") -> dict:
    prompt = "Question: 1+1?\nAnswer:"
    return {"sample_id": f"{split}:{index:04d}", "row_index": index, "split": split,
            "question": "1+1?", "gold": "calculation\n#### 2", "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "fewshot_train_indices": [1, 2, 3, 4, 5]}


def complete_row(req: dict, identity: str, text: str = "#### 2") -> dict:
    return {"schema": worker.ROW_SCHEMA, "status": "complete", "identity_sha256": identity,
            **{key: req[key] for key in ("sample_id", "row_index", "split", "prompt_sha256",
                                        "fewshot_train_indices", "gold")},
            "question_sha256": hashlib.sha256(req["question"].encode()).hexdigest(),
            "new_token_ids": list(text.encode()), "output_tokens": len(text.encode()),
            "raw_text": text, "scoring_text": text, "stop_strings": ["Question:"],
            "input_tokens": 2, "input_token_ids_sha256": worker.canonical_hash([1, 2]),
            "stop_reason": "eos", "length_capped": False, "elapsed_seconds": 1.25,
            "peak_memory_allocated_bytes": 100, "peak_memory_reserved_bytes": 200,
            "source_attempt": "original", "use_cache": True}


class Tokenizer:
    pad_token_id = 0
    bos_token_id = 1
    eos_token_id = 3
    padding_side = "right"
    special_tokens_map = {"bos_token": "<bos>", "eos_token": "<eos>"}

    def encode(self, text, **kwargs):
        return list(text.encode())

    def decode(self, tokens, skip_special_tokens=True, **kwargs):
        if isinstance(tokens, int):
            tokens = [tokens]
        if skip_special_tokens:
            tokens = [token for token in tokens if token not in (0, 1, 3)]
        return bytes(tokens).decode()

    def get_vocab(self):
        return {str(index): index for index in range(256)}


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.identity = {"protocol": "frozen", "model": "abc"}
        self.digest = worker.canonical_hash(self.identity)
        self.req = request()
        self.row = complete_row(self.req, self.digest)

    def tearDown(self):
        self.temp.cleanup()

    def attempt(self, name, rows, tail=b"", identity=None):
        folder = self.root / name
        folder.mkdir()
        identity = self.identity if identity is None else identity
        worker.atomic_json(folder / "manifest.json", {"schema": worker.MANIFEST_SCHEMA,
                           "identity": identity, "identity_sha256": worker.canonical_hash(identity),
                           "state": "failed"})
        with (folder / "generation.jsonl").open("wb") as handle:
            for row in rows:
                handle.write(json.dumps(row).encode() + b"\n")
            handle.write(tail)
        return folder

    def test_import_complete_rows_and_leave_missing_samples(self):
        folder = self.attempt("AT001", [self.row])
        imported, provenance = worker.import_resumable([folder], self.digest, [self.req, request(1)])
        self.assertEqual(set(imported), {"train:0000"})
        self.assertEqual(imported["train:0000"]["imported_from_attempt"], str(folder))
        self.assertEqual(provenance[0]["imported_rows"], 1)

    def test_truncated_tail_is_preserved_and_never_imported(self):
        folder = self.attempt("AT001", [self.row], b'{"sample_id":"train:0001"')
        before = (folder / "generation.jsonl").read_bytes()
        imported, provenance = worker.import_resumable([folder], self.digest, [self.req, request(1)])
        self.assertEqual(len(imported), 1)
        self.assertEqual(provenance[0]["ignored_tail"]["line"], 2)
        self.assertEqual((folder / "generation.jsonl").read_bytes(), before)

    def test_committed_corrupt_json_fails(self):
        folder = self.attempt("AT001", [self.row], b'{"bad":\n')
        with self.assertRaisesRegex(ValueError, "corrupt committed"):
            worker.import_resumable([folder], self.digest, [self.req])

    def test_duplicate_id_in_one_attempt_is_fatal(self):
        folder = self.attempt("AT001", [self.row, self.row])
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            worker.import_resumable([folder], self.digest, [self.req])

    def test_changed_protocol_or_model_identity_is_fatal(self):
        for field in ("protocol", "model"):
            changed = {**self.identity, field: "changed"}
            folder = self.attempt(field, [self.row], identity=changed)
            with self.assertRaisesRegex(ValueError, "execution identity mismatch"):
                worker.import_resumable([folder], self.digest, [self.req])

    def test_manifest_identity_cannot_be_relabelled(self):
        folder = self.attempt("AT001", [self.row])
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["identity"]["model"] = "changed"
        worker.atomic_json(folder / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            worker.import_resumable([folder], self.digest, [self.req])

    def test_same_id_conflicting_answer_across_attempts_fails(self):
        a = self.attempt("AT001", [self.row])
        b = self.attempt("AT002", [complete_row(self.req, self.digest, "#### 2.")])
        with self.assertRaisesRegex(ValueError, "conflicting completed answers"):
            worker.import_resumable([a, b], self.digest, [self.req])

    def test_identical_import_across_attempts_does_not_duplicate(self):
        a = self.attempt("AT001", [self.row])
        b = self.attempt("AT002", [{**self.row, "source_attempt": "copied"}])
        imported, _ = worker.import_resumable([a, b], self.digest, [self.req])
        self.assertEqual(len(imported), 1)

    def test_error_is_not_scored_or_imported(self):
        folder = self.attempt("AT001", [{"sample_id": self.req["sample_id"], "status": "error"}])
        imported, _ = worker.import_resumable([folder], self.digest, [self.req])
        self.assertEqual(imported, {})

    def test_changed_gold_prompt_or_token_evidence_fails(self):
        for field, value in (("gold", "#### 999"), ("prompt_sha256", "new"),
                             ("output_tokens", 0), ("elapsed_seconds", float("nan"))):
            bad = {**self.row, field: value}
            with self.assertRaises(ValueError):
                worker.validate_completed_row(bad, self.req, self.digest)

    def test_tokenizer_recomputes_text_and_input_identity(self):
        worker.validate_completed_row(self.row, self.req, self.digest, Tokenizer(), [1, 2])
        with self.assertRaisesRegex(ValueError, "input token identity"):
            worker.validate_completed_row(self.row, self.req, self.digest, Tokenizer(), [2, 1])
        with self.assertRaisesRegex(ValueError, "inconsistent with saved token"):
            worker.validate_completed_row({**self.row, "scoring_text": "#### 999"},
                                          self.req, self.digest, Tokenizer(), [1, 2])


class PolicyTests(unittest.TestCase):
    def test_cli_stage_defaults_and_budget_mismatch(self):
        plan = worker.load_plan()
        plan["protocol"]["verification_contract_id"] = worker.VERIFICATION_CONTRACT_ID
        for stage, expected in (("smoke", 64), ("pilot", 4096), ("formal", 4096)):
            args = worker.parse_args(["--stage", stage, "--model", "x", "--case", "bf16",
                                      "--model-identity", "id.json", "--output", "AT001"])
            worker.validate_args(args, plan)
            self.assertEqual(args.max_gen_toks, expected)
            args.max_gen_toks = 7
            with self.assertRaisesRegex(ValueError, "budget differs"):
                worker.validate_args(args, plan)

    def test_prompt_is_not_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, "budget violation"):
            worker.audit_prompts([request()], Tokenizer(), 32, 16, 16)
        encoded, audit = worker.audit_prompts([request()], Tokenizer(), 128, 16, 100)
        self.assertEqual(encoded["train:0000"], list(request()["prompt"].encode()))
        self.assertFalse(audit["input_truncation"])

    def test_earliest_stop_and_final_answer_marker(self):
        text = "reasoning #### 2\nQuestion: leaked </s>"
        scoring, stop = worker.trim_scoring_text(text, ["</s>", "Question:"])
        self.assertEqual(scoring, "reasoning #### 2\n")
        self.assertEqual(stop, "Question:")
        self.assertEqual(worker.trim_scoring_text("#### 2", ["Question:"]), ("#### 2", None))

    def test_only_continuation_is_scored(self):
        req = request()
        req["prompt"] = "Question: example\nAnswer: #### 999\nQuestion: real\nAnswer:"
        row = complete_row(req, "id", "#### 2")
        self.assertTrue(worker.score_row(row)["correct_strict"])
        row["scoring_text"] = "no answer"
        self.assertFalse(worker.score_row(row)["correct_strict"])

    def test_partial_summary_retains_expected_denominator(self):
        row = complete_row(request(), "id")
        result = worker.make_summary([row, {"status": "error"}], 4, "smoke", 2, "failed")
        self.assertEqual(result["exact_match,strict-match"], .25)
        self.assertEqual(result["n_errors"], 1)
        self.assertFalse(result["full_split"])

    def test_full_split_requires_formal_exact_test_ids_and_complete(self):
        rows = [complete_row(request(index, "test"), "id") for index in range(1319)]
        self.assertTrue(worker.make_summary(rows, 1319, "formal", 1, "complete")["full_split"])
        self.assertFalse(worker.make_summary(rows, 1319, "pilot", 1, "complete")["full_split"])
        self.assertFalse(worker.make_summary(rows, 1319, "formal", 1, "failed")["full_split"])
        rows[-1]["sample_id"] = "test:0000"
        self.assertFalse(worker.make_summary(rows, 1319, "formal", 1, "complete")["full_split"])

    def test_fresh_config_clears_checkpoint_generation_side_effects(self):
        from transformers import GenerationConfig
        model = SimpleNamespace(generation_config=GenerationConfig(
            do_sample=True, temperature=.7, top_p=.8, num_beams=4,
            repetition_penalty=1.2, forced_eos_token_id=42, eos_token_id=[3, 4]))
        config, saved = worker.resolve_generation(model, Tokenizer(), 64)
        self.assertFalse(config.do_sample)
        self.assertEqual(config.num_beams, 1)
        self.assertEqual(config.repetition_penalty, 1)
        self.assertIsNone(config.forced_eos_token_id)
        self.assertEqual(config.eos_token_id, [3, 4])
        self.assertTrue(config.use_cache)
        self.assertEqual(config.cache_implementation, "dynamic")
        self.assertFalse(saved["temperature_argument_passed"])

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "AT001"
            output.mkdir()
            marker = output / "preserve.txt"
            marker.write_text("old evidence")
            args = worker.parse_args(["--stage", "smoke", "--model", "x", "--case", "bf16",
                                      "--model-identity", "id.json", "--output", str(output)])
            with self.assertRaises(FileExistsError):
                worker.run(args)
            self.assertEqual(marker.read_text(), "old evidence")

    def test_early_validation_error_is_persisted_as_failed(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "AT001"
            args = worker.parse_args(["--stage", "smoke", "--model", "x", "--case", "bf16",
                                      "--model-identity", "id.json", "--output", str(output), "--batch-size", "2"])
            with self.assertRaisesRegex(ValueError, "batch=1"):
                worker.run(args)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "failed")
            self.assertNotIn("full_split", manifest)


class CheckpointTests(unittest.TestCase):
    def test_weight_contents_are_rehashed_even_when_size_is_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "Llama-3.2-3B-Instruct"
            model.mkdir()
            (model / "config.json").write_text(json.dumps({"model_type": "llama",
                "architectures": ["LlamaForCausalLM"], "num_hidden_layers": 28}))
            (model / "tokenizer_config.json").write_text("{}")
            weight = model / "model.safetensors"
            weight.write_bytes(b"first")
            entries = [{"name": path.name, "bytes": path.stat().st_size,
                        "sha256": worker.sha256_file(path)} for path in sorted(model.iterdir())]
            identity = {"schema": "scalellm_checkpoint_identity_v1", "checkpoint_name": model.name,
                        "resolved_path": str(model), "files": entries,
                        "fingerprint_sha256": hashlib.sha256(json.dumps(entries, sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest(),
                        "file_count": len(entries), "total_bytes": sum(e["bytes"] for e in entries)}
            identity_path = Path(folder) / "identity.json"
            worker.atomic_json(identity_path, identity)
            self.assertEqual(worker.verify_checkpoint(model, identity_path), identity)
            weight.write_bytes(b"other")
            with self.assertRaisesRegex(ValueError, "content changed"):
                worker.verify_checkpoint(model, identity_path)


def fixture_cache_model(**modes):
    """CPU cache fixture with independently allocated full K/V and greedy logits."""
    import torch
    class Cache:
        def __init__(self, keys, values):
            self.layers = [SimpleNamespace(keys=keys, values=values)]
        def get_seq_length(self, index=0):
            return self.layers[index].keys.shape[-2]
    class Model:
        config = SimpleNamespace(num_hidden_layers=1)
        def named_modules(self):
            return []
        def __call__(self, **kwargs):
            ids = kwargs["input_ids"].float().reshape(1, 1, -1, 1)
            past = kwargs.get("past_key_values")
            if past is None:
                cache = Cache(ids.clone(), ids.clone()+1)
            else:
                cache = past
                if modes.get("mutate_prefix"):
                    cache.layers[0].keys[..., 0, :] += 1
                cache.layers[0].keys = torch.cat((cache.layers[0].keys, ids), dim=-2)
                cache.layers[0].values = torch.cat((cache.layers[0].values, ids+1), dim=-2)
            offset = ids.sum()*.001 if modes.get("ignore_cache") else cache.layers[0].values.sum()*.001
            logits = torch.zeros((1, 1, 16)) + offset
            logits[:, :, 3 if modes.get("early_eos") else 8] += 1
            if not kwargs["use_cache"] and modes.get("cache_off_drift"):
                logits += .5
            return SimpleNamespace(logits=logits, past_key_values=cache)
        def generate(self, **kwargs):
            inputs, cfg = kwargs["input_ids"], kwargs["generation_config"]
            sequence, past, outputs = inputs.clone(), None, []
            count = 1 if modes.get("early_eos") else cfg.max_new_tokens
            for _ in range(count):
                out = self(input_ids=sequence if past is None or not cfg.use_cache else sequence[:, -1:],
                           past_key_values=past if cfg.use_cache else None, use_cache=cfg.use_cache)
                raw = out.logits[:, -1, :].float().clone()
                token = raw.argmax(dim=-1).reshape(1, 1)
                if cfg.output_logits:
                    outputs.append(raw+.5 if modes.get("native_mismatch") else raw)
                past = out.past_key_values
                sequence = torch.cat((sequence, token), dim=1)
            return SimpleNamespace(sequences=sequence, past_key_values=past, logits=tuple(outputs) if cfg.output_logits else None)
    return Model()


class GenerationTests(unittest.TestCase):
    def test_generation_records_only_new_tokens_and_stops_before_next_question(self):
        import torch
        from transformers import GenerationConfig
        req = request()
        suffix = list(b"#### 2\nQuestion:")
        config = GenerationConfig(max_new_tokens=64, eos_token_id=[3], use_cache=True)
        class Model:
            def generate(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(sequences=torch.tensor([[10, 11] + suffix]))
        model = Model()
        with patch.object(torch.cuda, "synchronize"), patch.object(torch.cuda, "reset_peak_memory_stats"), \
             patch.object(torch.cuda, "max_memory_allocated", return_value=123), \
             patch.object(torch.cuda, "max_memory_reserved", return_value=456):
            row = worker.generate_one(model, Tokenizer(), req, [10, 11], config,
                                      ["Question:"], "cpu", "id", Path("AT001"))
        self.assertEqual(row["new_token_ids"], suffix)
        self.assertEqual(row["raw_text"], "#### 2\nQuestion:")
        self.assertEqual(row["scoring_text"], "#### 2\n")
        self.assertEqual(row["stop_reason"], "stop_string")
        self.assertFalse(row["length_capped"])
        self.assertTrue(model.kwargs["generation_config"].use_cache)
        self.assertTrue(worker.score_row(row)["correct_strict"])

    def verify_fixture(self, **modes):
        from transformers import GenerationConfig
        cfg = GenerationConfig(max_new_tokens=64, eos_token_id=[3], return_dict_in_generate=True)
        with patch("run_eval_worker.configure_reproducibility"):
            return worker.verify_generation(fixture_cache_model(**modes), Tokenizer(), [request(), request(1)], cfg, "cpu", 1)

    def test_native_parity_and_fresh_cache_rebuild_check_every_step(self):
        passed = self.verify_fixture()
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["verification_contract_id"], "native_cache_call_parity_v2")
        self.assertEqual(len(passed["records"]), 2)
        self.assertEqual(len(passed["records"][0]["repeatability_prefix_32_token_ids"]), 32)
        self.assertEqual([row["step"] for row in passed["records"][0]["steps"]], list(range(17)))
        self.assertTrue(passed["negative_control_qualified"])
        self.assertTrue(passed["negative_control_detected"])

    def test_native_logit_mismatch_cannot_pass_even_when_tokens_repeat(self):
        failed = self.verify_fixture(native_mismatch=True)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["native_generate_exact"])
        self.assertTrue(failed["same_process_repeat_32_equal"])

    def test_cache_off_drift_is_preserved_as_diagnostic_without_faking_pass(self):
        result = self.verify_fixture(cache_off_drift=True)
        self.assertTrue(result["passed"])
        self.assertFalse(result["records"][0]["logits_allclose"])
        self.assertEqual(result["records"][0]["atol"], .125)
        self.assertEqual(result["records"][0]["rtol"], .01)

    def test_negative_control_detects_a_model_that_ignores_cached_values(self):
        failed = self.verify_fixture(ignore_cache=True)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["negative_control_detected"])
        self.assertFalse(failed["negative_control_qualified"])

    def test_old_prefix_mutation_fails_cache_structure(self):
        failed = self.verify_fixture(mutate_prefix=True)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["cache_structure_valid"])

    def test_immediate_eos_records_qualified_na_without_claiming_detection(self):
        passed = self.verify_fixture(early_eos=True)
        self.assertTrue(passed["passed"])
        for row in passed["records"]:
            self.assertEqual(row["native_generated_token_ids"], [3])
            self.assertEqual(row["native_logits_count"], 1)
            self.assertIsNone(row["negative_control_detected"])
            self.assertEqual(row["negative_control_status"], "not_applicable_early_eos_no_prior_cache")
            self.assertTrue(row["negative_control_qualified"])

    def test_storage_alias_views_are_rejected(self):
        import torch
        tensor = torch.ones((1, 1, 8, 1))
        a = SimpleNamespace(layers=[SimpleNamespace(keys=tensor[..., :4, :], values=tensor[..., :4, :])])
        b = SimpleNamespace(layers=[SimpleNamespace(keys=tensor[..., 4:, :], values=tensor[..., 4:, :])])
        self.assertFalse(worker.caches_disjoint(a, b))

    def test_step_evidence_is_persisted(self):
        from transformers import GenerationConfig
        cfg = GenerationConfig(max_new_tokens=64, eos_token_id=[3], return_dict_in_generate=True)
        with tempfile.TemporaryDirectory() as folder, patch("run_eval_worker.configure_reproducibility"):
            path = Path(folder) / "verification.json"
            returned = worker.verify_generation(fixture_cache_model(), Tokenizer(), [request(), request(1)],
                                                cfg, "cpu", 1, evidence_path=path)
            saved = json.loads(path.read_text())
        self.assertEqual(saved, returned)
        self.assertEqual(len(saved["records"][0]["steps"]), 17)
        self.assertTrue(saved["passed"])

    def test_actual_verifier_json_matches_matrix_consumer_normal_and_eos(self):
        from run_gsm8k_matrix import validate_generation_verification, NATIVE_VERIFICATION
        for early in (False, True):
            result = self.verify_fixture(early_eos=early)
            contract = validate_generation_verification(result, NATIVE_VERIFICATION,
                {"generation": {"eos_token_ids": [3]}})
            self.assertEqual(contract, NATIVE_VERIFICATION)

    def test_real_cpu_tiny_llama_native_cache_and_repeatability(self):
        import torch
        from transformers import LlamaConfig, LlamaForCausalLM
        torch.set_num_threads(2)
        torch.manual_seed(17)
        model = LlamaForCausalLM(LlamaConfig(vocab_size=256, hidden_size=32, intermediate_size=64,
            num_hidden_layers=1, num_attention_heads=4, num_key_value_heads=2,
            max_position_embeddings=512, bos_token_id=1, eos_token_id=3, pad_token_id=0,
            attn_implementation="eager")).eval()
        config, _ = worker.resolve_generation(model, Tokenizer(), 64)
        # No CUDA probes or seeding: all actual model arithmetic remains on CPU.
        with patch("run_eval_worker.configure_reproducibility"):
            result = worker.verify_generation(model, Tokenizer(), [request(), request(1)], config, "cpu", 17)
        self.assertTrue(result["passed"])
        self.assertTrue(result["native_generate_exact"])
        self.assertTrue(result["rebuilt_cache_exact"])
        self.assertTrue(result["cache_structure_valid"])
        self.assertLess(max(row["logits_max_abs_difference"] for row in result["records"]), 1e-5)


if __name__ == "__main__":
    unittest.main()
