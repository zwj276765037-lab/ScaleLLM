#!/usr/bin/env python3
"""CPU evidence against the *installed*, unmodified lm_eval task interfaces."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from gsm8k_protocol import (
    DEFAULT_PLAN, atomic_json, build_prompt, canonical_hash, load_plan,
    load_verified_inputs, prepare_requests, score_response, sha256_file,
)


EVIDENCE: dict = {}


def installed_harness_task(datasets, *, evaluate_train=False):
    """Use installed task YAML, sampling, templating, filters, and metrics.

    Only the download hook is replaced, with the independently mapped frozen
    local export. No templates, samplers, or metric functions are patched.
    """
    import datasets as hf_datasets
    import lm_eval
    from lm_eval.api.task import ConfigurableTask
    import yaml

    root = Path(lm_eval.__file__).parent
    path = root / "tasks/gsm8k/gsm8k.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if evaluate_train:
        config["test_split"] = "train"

    class OfflineGSM8K(ConfigurableTask):
        def download(self, *args, **kwargs):
            self.dataset = hf_datasets.DatasetDict({
                split: hf_datasets.Dataset.from_list(rows)
                for split, rows in datasets.items()
            })

    return OfflineGSM8K(config=config), path


def independent_rows(plan_path=DEFAULT_PLAN):
    # Map source fields independently of the implementation under test.
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    root = Path(plan["data"]["root"])
    if not root.is_absolute():
        root = Path(plan_path).parent / root
    data = {}
    for split in ("train", "test"):
        # JSONL separates rows only at LF; str.splitlines also treats U+2028
        # inside legitimate question strings as a row boundary.
        raw = [json.loads(line) for line in (root / f"{split}.jsonl").read_text(encoding="utf-8").split("\n") if line]
        data[split] = [{"question": row["instruction"], "answer": row["output"]} for row in raw]
    return data


def harness_score(task, response, gold):
    from lm_eval.filters.extraction import RegexFilter
    from lm_eval.filters.selection import TakeFirstFilter

    result = {}
    for pipeline in task.config.filter_list:
        kwargs = {key: value for key, value in pipeline["filter"][0].items() if key != "function"}
        extracted = list(TakeFirstFilter().apply(
            RegexFilter(**kwargs).apply([[response]], [{}]), [{}]
        ))[0]
        score = task.process_results({"answer": gold}, [extracted])["exact_match"]
        result[pipeline["name"]] = {"prediction": extracted, "correct": bool(score)}
    return result


def scoring_cases():
    cases = [
        ("#### 42", "calculation\n#### 42"),
        ("#### 1\n#### 42", "#### 42"),
        ("#### 42\n#### 1", "#### 42"),
        ("No final marker. The answer is 42.", "#### 42"),
        ("####42", "#### 42"),
        ("####  42", "#### 42"),
        ("#### +42", "#### 42"),
        ("#### -42", "#### -42"),
        ("#### $1,234.00", "#### 1234.00"),
        ("#### 1,234", "#### 1234"),
        ("#### 42.", "#### 42"),
        ("#### 42.0", "#### 42"),
        ("#### .5", "#### 0.5"),
        ("#### -0", "#### 0"),
        ("#### 00042", "#### 42"),
        ("#### 1/2", "#### 1"),
        ("#### 4e2", "#### 4"),
        ("#### ４２", "#### 42"),
        ("\\boxed{42}", "#### 42"),
        ("#### 42 apples, later 99", "#### 42"),
        ("#### -1,234.50.", "work\n#### -1234.50"),
        ("one number 3", "#### 3"),
        ("numbers 11 and -7", "#### -7"),
        ("#### 42", "work\n#### 42\n"),
        ("#### 42", "work\n#### 42 "),
        ("#### 42", "#### 0\n#### 42"),
        ("#### 42", "#### $42."),
        ("", "#### 42"),
        (None, "#### 42"),
        (123, "#### 123"),
        ("The answer is zero.", "#### 0"),
        ("[invalid]", "#### 0"),
        ("#### --42", "#### -42"),
        ("#### 1.2.3", "#### 1.2.3"),
        ("#### ,", "#### 0"),
    ]
    rng = random.Random(20260913)
    for _ in range(100):
        a, b = rng.randrange(-10000, 10001), rng.randrange(-10000, 10001)
        cases.extend([
            (f"work {a}\n#### {b:,}", f"work\n#### {b}"),
            (f"#### {a}\nother {b}", f"#### {a}"),
            (f"Reasoned result is ${b:,}.", f"#### {b}"),
        ])
    return cases


class GSM8KProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = load_plan()
        _, cls.data, cls.schedule = load_verified_inputs()
        cls.formal = prepare_requests(DEFAULT_PLAN, "formal")
        cls.oracle_data = independent_rows()

    def test_all_1319_prompts_match_installed_harness(self):
        task, path = installed_harness_task(self.oracle_data)
        task.set_fewshot_seed(self.plan["protocol"]["seed"])
        for request, doc in zip(self.formal, task.eval_docs):
            actual = task.fewshot_context(doc, num_fewshot=5, apply_chat_template=False)
            self.assertEqual(request["prompt"].encode("utf-8"), actual.encode("utf-8"), request["sample_id"])
        self.assertEqual(len(task.eval_docs), len(self.formal))
        EVIDENCE["formal_prompt_byte_parity"] = {"compared": len(self.formal), "mismatches": 0}
        EVIDENCE["harness"] = {
            "version": importlib.metadata.version("lm_eval"),
            "task_yaml": str(path), "task_yaml_sha256": sha256_file(path),
            "metadata_version": task.config.metadata["version"],
        }

    def test_train_32_prompts_match_installed_harness_and_smoke(self):
        task, _ = installed_harness_task(self.oracle_data, evaluate_train=True)
        task.set_fewshot_seed(self.plan["protocol"]["seed"])
        pilot = prepare_requests(DEFAULT_PLAN, "pilot")
        for request, doc in zip(pilot, task.eval_docs):
            actual = task.fewshot_context(doc, num_fewshot=5, apply_chat_template=False)
            self.assertEqual(request["prompt"].encode("utf-8"), actual.encode("utf-8"), request["sample_id"])
            self.assertNotIn(request["row_index"], request["fewshot_train_indices"])
        self.assertEqual(prepare_requests(DEFAULT_PLAN, "smoke"), pilot[:4])
        EVIDENCE["train_prompt_byte_parity"] = {"pilot_compared": len(pilot), "smoke_compared": 4, "mismatches": 0}

    def test_scores_match_installed_filters_and_task_metrics(self):
        task, _ = installed_harness_task(self.oracle_data)
        rows = []
        for response, gold in scoring_cases():
            actual = score_response(response, gold)
            expected = harness_score(task, response, gold)
            self.assertEqual(actual["strict_prediction"], expected["strict-match"]["prediction"])
            self.assertEqual(actual["flexible_prediction"], expected["flexible-extract"]["prediction"])
            self.assertEqual(actual["correct_strict"], expected["strict-match"]["correct"], (response, gold))
            self.assertEqual(actual["correct_flexible"], expected["flexible-extract"]["correct"], (response, gold))
            self.assertEqual(actual["invalid_strict"], expected["strict-match"]["prediction"] == "[invalid]")
            rows.append({"response": response, "gold": gold, "local": actual, "harness": expected})
        EVIDENCE["score_cases"] = rows
        EVIDENCE["score_case_parity"] = {"compared": len(rows), "mismatches": 0, "seed": 20260913}

    def test_all_official_gold_responses_match_harness(self):
        task, _ = installed_harness_task(self.oracle_data)
        for request in self.formal:
            result = score_response(request["gold"], request["gold"])
            expected = harness_score(task, request["gold"], request["gold"])
            self.assertTrue(result["correct_strict"])
            self.assertTrue(result["correct_flexible"])
            self.assertEqual(result["correct_strict"], expected["strict-match"]["correct"])
            self.assertEqual(result["correct_flexible"], expected["flexible-extract"]["correct"])
        EVIDENCE["official_gold_score_parity"] = {"compared": len(self.formal), "mismatches": 0}

    def test_formal_ids_hashes_and_fewshot_schedule(self):
        import hashlib
        self.assertEqual([r["sample_id"] for r in self.formal], [f"test:{i:04d}" for i in range(1319)])
        for row, fixed in zip(self.formal, self.schedule["formal"]):
            self.assertEqual(row["fewshot_train_indices"], fixed["train_row_indices"])
            self.assertEqual(row["prompt_sha256"], hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest())
        self.assertEqual(prepare_requests(DEFAULT_PLAN, "formal"), self.formal)

    def test_prompt_does_not_read_evaluated_answer(self):
        # The builder accepts only the evaluated question; corrupt all evaluated
        # answers and prove every formal prompt stays byte-for-byte unchanged.
        modified = deepcopy(self.data["test"])
        for row in modified:
            row["answer"] = "TEST_GOLD_LEAK_SENTINEL #### 999999999"
        for row, request in zip(modified, self.formal):
            prompt = build_prompt(row["question"], self.data["train"], request["fewshot_train_indices"])
            self.assertEqual(prompt, request["prompt"])
            self.assertNotIn("TEST_GOLD_LEAK_SENTINEL", prompt)
        EVIDENCE["test_gold_isolation"] = {"perturbed_answers": len(modified), "prompt_changes": 0}

    def test_dataset_and_schedule_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data_root = directory / "data"
            data_root.mkdir()
            source_root = Path(self.plan["data"]["root"])
            for split in ("train", "test"):
                shutil.copyfile(source_root / f"{split}.jsonl", data_root / f"{split}.jsonl")
            schedule_path = directory / "fewshot_indices.json"
            shutil.copyfile(DEFAULT_PLAN.parent / "fewshot_indices.json", schedule_path)
            plan = deepcopy(self.plan)
            plan["data"]["root"] = "data"
            path = directory / "plan.json"
            atomic_json(path, plan)
            self.assertEqual(prepare_requests(path, "formal"), self.formal)
            with (data_root / "test.jsonl").open("ab") as handle:
                handle.write(b"\n")
            with self.assertRaisesRegex(ValueError, "dataset SHA-256 mismatch"):
                prepare_requests(path, "formal")
            shutil.copyfile(source_root / "test.jsonl", data_root / "test.jsonl")
            with schedule_path.open("ab") as handle:
                handle.write(b"\n")
            with self.assertRaisesRegex(ValueError, "schedule SHA-256 mismatch"):
                prepare_requests(path, "formal")
        EVIDENCE["snapshot_and_tamper_guards"] = {"portable_relative_snapshot": "passed", "dataset_tamper": "rejected", "fewshot_tamper": "rejected"}

    def test_unknown_stage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown stage"):
            prepare_requests(DEFAULT_PLAN, "validation")

    def test_json_identity_is_order_independent_and_atomic(self):
        self.assertEqual(canonical_hash({"b": 2, "a": "数学"}), canonical_hash({"a": "数学", "b": 2}))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested" / "record.json"
            atomic_json(path, {"v": 1})
            atomic_json(path, {"v": 2})
            self.assertEqual(json.loads(path.read_text()), {"v": 2})
            self.assertEqual([p.name for p in path.parent.iterdir()], ["record.json"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GSM8KProtocolTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.audit_output:
        EVIDENCE.update({
            "schema": "scalellm_gsm8k_cpu_protocol_parity_v1",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "success": result.wasSuccessful(), "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "plan_sha256": sha256_file(DEFAULT_PLAN),
            "implementation_sha256": sha256_file(Path(__file__).with_name("gsm8k_protocol.py")),
            "test_sha256": sha256_file(Path(__file__)),
        })
        atomic_json(args.audit_output, EVIDENCE)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
