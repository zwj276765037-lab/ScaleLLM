#!/usr/bin/env python3

from __future__ import annotations

import unittest

from merge_eval_shards import canonical_method
from protocol import TASK_ORDER, TASK_SOURCES, build_task, load_rows, validate_protocol


class ProtocolTest(unittest.TestCase):
    def test_official_split_sizes(self) -> None:
        for task in TASK_ORDER:
            source = TASK_SOURCES[task]
            self.assertEqual(len(load_rows(source)), source.expected_rows, task)

    def test_first_requests_match_frozen_templates(self) -> None:
        expected = {
            "piqa": "Question: How do I ready a guinea pig cage for it's new occupants?\nAnswer:",
            "arc_easy": (
                "Question: Which statement best explains why photosynthesis is the "
                "foundation of most food webs?\nAnswer:"
            ),
            "arc_challenge": (
                "Question: An astronomer observes that a planet rotates faster after a "
                "meteorite impact. Which is the most likely effect of this increase in "
                "rotation?\nAnswer:"
            ),
            "hellaswag": "Roof shingle removal: A man is sitting on a roof. He",
            "winogrande": "Sarah was a much better surgeon than Maria so Sarah",
        }
        for task, context in expected.items():
            configured = build_task(task)
            configured.build_all_requests(
                limit=1, rank=0, world_size=1, cache_requests=False
            )
            self.assertEqual(configured.instances[0].args[0], context, task)

    def test_v5_cannot_be_mislabeled_as_2048(self) -> None:
        for case in (
            "v5_attention",
            "v5_mlp",
            "v5_mlp_down_s32_ablation",
            "v5",
            "v5_down_s32_ablation",
            "v5_algorithm",
        ):
            with self.subTest(case=case):
                with self.assertRaisesRegex(ValueError, "would not be valid"):
                    validate_protocol("literature_2048", case, None)

    def test_reference_qdq_is_literature_comparable_at_2048(self) -> None:
        protocol = validate_protocol("literature_2048", "reference_qdq", None)
        self.assertTrue(protocol["literature_comparable"])
        self.assertFalse(protocol["hardware_constrained"])
        self.assertEqual(protocol["context_length"], 2048)

    def test_limit_is_never_literature_comparable(self) -> None:
        protocol = validate_protocol("literature_2048", "bf16", 1)
        self.assertFalse(protocol["literature_comparable"])
        self.assertFalse(protocol["full_split"])

    def test_legacy_down_width_default_is_merge_compatible(self) -> None:
        legacy = {"method": {"case": "v5_production_fullchain"}}
        explicit_s24 = {
            "method": {
                "case": "v5_production_fullchain",
                "mlp_down_output_width": 24,
            }
        }
        diagnostic_s32 = {
            "method": {
                "case": "v5_production_fullchain",
                "mlp_down_output_width": 32,
            }
        }
        self.assertEqual(canonical_method(legacy), canonical_method(explicit_s24))
        self.assertNotEqual(
            canonical_method(legacy), canonical_method(diagnostic_s32)
        )


if __name__ == "__main__":
    unittest.main()
