"""Offline synthetic contract tests; these are not quality measurements."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

try:
    from .common import text_sha, identity
    from .pack import RUBRIC, build_packets, validate_score
    from .aggregate import resolve_clusters, summarize, verify_pack, wilson95
    from .plot import render
except ImportError:
    from common import text_sha, identity
    from pack import RUBRIC, build_packets, validate_score
    from aggregate import resolve_clusters, summarize, verify_pack, wilson95
    from plot import render


def inputs(turns=1):
    prompt = {"prompt_id": "synthetic:0", "cluster_id": "cluster0", "dataset": "synthetic",
        "source_revision": "fixture", "category": "fixture", "category_kind": "test_only", "turns": [f"Question {i}" for i in range(turns)]}
    responses = [{"prompt_id": prompt["prompt_id"], "cluster_id": prompt["cluster_id"], "dataset": "synthetic",
        "source_revision": "fixture", "turn_index": i, "user_prompt": question,
        "responses": {"current": {"text": "Answer one.", "truncated": False, "stop_reason": "eos"},
                      "output_only": {"text": "Answer two.", "truncated": False, "stop_reason": "eos"}},
        "pair": {"both_complete": True}} for i, question in enumerate(prompt["turns"])]
    return [prompt], responses


def score(case, decision):
    return {"schema_version": 1, "case_id": case["case_id"], "decision": decision,
        "reason": "Synthetic test explanation only.", "evidence_a": case["turns"][0]["response_a"],
        "evidence_b": case["turns"][0]["response_b"], "confidence": "medium", "flags": [],
        "judge_run_id": "fixture_only", "rubric_sha256": text_sha(RUBRIC)}


class AssessmentTests(unittest.TestCase):
    def packets(self, turns=1):
        prompts, responses = inputs(turns)
        return build_packets(prompts, responses, b"synthetic-test-seed-not-a-real-run", 1)

    def resolve(self, cases, private, scores):
        return resolve_clusters(private, cases, scores, text_sha(RUBRIC), "fixture_only")

    def test_public_allowlist_and_true_swap(self):
        cases, private, batches = self.packets(2)
        self.assertEqual(len(batches), 2)
        for case in cases:
            self.assertEqual(set(case), {"case_id", "turns"})
            self.assertTrue(all(set(t) == {"user", "response_a", "response_b"} for t in case["turns"]))
            self.assertEqual(len(case["turns"]), 2)
        self.assertEqual(cases[0]["turns"][0]["response_a"], cases[1]["turns"][0]["response_b"])
        self.assertEqual({c["a_arm"] for c in private[0]["cases"]}, {"current", "output_only"})

    def test_two_orders_two_turns_are_one_question(self):
        cases, private, _ = self.packets(2)
        orientations = {c["case_id"]: c["a_arm"] for c in private[0]["cases"]}
        scores = [score(c, "A_BETTER" if orientations[c["case_id"]] == "current" else "B_BETTER") for c in cases]
        rows = self.resolve(cases, private, scores)
        self.assertEqual(rows[0]["label"], "Better")
        stat = summarize(rows, 1000)
        self.assertEqual(stat["planned_question_clusters"], 1)
        self.assertEqual(stat["resolved_question_clusters"], 1)
        self.assertEqual(stat["counts"]["Better"], 1)

    def test_same_position_bias_is_conflict_not_comparable(self):
        cases, private, _ = self.packets()
        rows = self.resolve(cases, private, [score(c, "A_BETTER") for c in cases])
        self.assertIsNone(rows[0]["label"])
        self.assertIn("order_conflict", rows[0]["reasons"])

    def test_missing_order_and_truncation_not_comparable(self):
        cases, private, _ = self.packets()
        rows = self.resolve(cases, private, [score(cases[0], "COMPARABLE")])
        self.assertIn("missing_order_score", rows[0]["reasons"])
        stat = summarize(rows, 1000)
        self.assertEqual(stat["unresolved_question_clusters"], 1)
        self.assertIsNone(stat["percent_of_resolved"]["Comparable"])
        prompts, responses = inputs()
        responses[0]["responses"]["current"]["truncated"] = True
        cases, private, _ = build_packets(prompts, responses, b"a-test-seed-at-least-16-bytes")
        self.assertEqual(cases, [])
        self.assertEqual(private[0]["eligibility"], "unresolved_generation")

    def test_duplicate_records_rejected(self):
        prompts, responses = inputs()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_packets(prompts, responses * 2, b"a-test-seed-at-least-16-bytes")
        cases, private, _ = self.packets()
        s = score(cases[0], "COMPARABLE")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.resolve(cases, private, [s, s])

    def test_prompt_source_mismatch_rejected(self):
        prompts, responses = inputs()
        responses[0]["user_prompt"] = "Silently truncated request"
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_packets(prompts, responses, b"a-test-seed-at-least-16-bytes")

    def test_bad_evidence_is_invalid_not_counted(self):
        cases, private, _ = self.packets()
        scores = [score(c, "COMPARABLE") for c in cases]
        scores[0]["evidence_a"] = "Not in either answer"
        rows = self.resolve(cases, private, scores)
        self.assertEqual(rows[0]["status"], "unresolved")
        self.assertTrue(any(r.startswith("invalid_score") for r in rows[0]["reasons"]))

    def test_case_tamper_and_extra_score_key_rejected(self):
        cases, private, _ = self.packets()
        original = copy.deepcopy(cases)
        cases[0]["turns"][0]["response_a"] += "modified"
        with self.assertRaisesRegex(ValueError, "changed"):
            self.resolve(cases, private, [])
        s = score(original[0], "COMPARABLE")
        s["current_model"] = "must not be accepted"
        with self.assertRaisesRegex(ValueError, "strict schema"):
            validate_score(s, original[0], text_sha(RUBRIC))

    def test_all_submitted_denominator_and_bootstrap(self):
        rows = [{"status": "resolved", "label": label, "reasons": []} for label in ["Better", "Comparable", "Comparable", "Worse"]]
        rows += [{"status": "unresolved", "label": None, "reasons": ["order_conflict"]}]
        a, b = summarize(rows, 2000), summarize(rows, 2000)
        self.assertEqual(a, b)
        self.assertEqual(a["percent_of_resolved"]["Comparable"], 50)
        self.assertEqual(a["percent_of_all_submitted"]["Comparable"], 40)
        self.assertEqual(a["assessment_coverage_percent"], 80)
        self.assertEqual(a["conditional_cluster_bootstrap_95_ci_percent"]["Better"], {"low": 0.0, "high": 75.0})

    def test_no_generation_is_preserved_separately(self):
        prompts, _ = inputs()
        cases, private, _ = build_packets(prompts, [], b"a-test-seed-at-least-16-bytes")
        rows = self.resolve(cases, private, [])
        stat = summarize(rows, 1000)
        self.assertEqual(stat["planned_question_clusters"], 1)
        self.assertEqual(stat["submitted_generation_question_clusters"], 0)
        self.assertIsNone(stat["percent_of_all_submitted"]["Better"])
        self.assertEqual(stat["assessment_coverage_percent"], 0)

    def test_pack_manifest_binds_private_map_and_sources(self):
        with tempfile.TemporaryDirectory(prefix="assessment_test_") as tmp:
            root = Path(tmp)
            required = ["private/private_map.json", "public/blind_records.jsonl", "public/rubric.txt", "public/score_schema.json"]
            for name in required:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic-only")
            manifest = {"schema": "scalellm_blind_pack_manifest_v1", "execution_state": "completed", "inputs": [],
                        "outputs": [identity(root / name) for name in required]}
            (root / "pack_manifest.json").write_text(json.dumps(manifest))
            verify_pack(root)
            (root / "private/private_map.json").write_text("modified orientation")
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_pack(root)

    def test_no_results_no_figure(self):
        with self.assertRaisesRegex(ValueError, "no resolved"):
            render({"schema": "scalellm_response_quality_aggregate_v1", "execution_state": "completed",
                "datasets": [{"overall": {"resolved_question_clusters": 0}}]}, None)

    def test_wilson_zero_all_and_one_question(self):
        self.assertIsNone(wilson95(0, 0))
        zero = wilson95(0, 10)
        all_ = wilson95(10, 10)
        self.assertEqual(zero["low"], 0)
        self.assertAlmostEqual(zero["high"], 27.753279986288923)
        self.assertEqual(all_["high"], 100)
        self.assertAlmostEqual(all_["low"], 100 - zero["high"])
        self.assertGreater(wilson95(0, 1)["high"], 79)
        self.assertLess(wilson95(1, 1)["low"], 21)
        with self.assertRaises(ValueError):
            wilson95(2, 1)


if __name__ == "__main__":
    unittest.main()
