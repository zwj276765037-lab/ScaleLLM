#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import unittest

from transformers import AutoTokenizer

from run_eval_worker import tokenizer_boundary_safe_hflm_class


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DEEPSEEK = (
    WORKSPACE_ROOT
    / "fpga_llm_project"
    / "configs"
    / "models"
    / "DeepSeek-R1-Distill-Llama-8B"
)


class TokenizerOnlyLM:
    backend = "causal"

    def __init__(self, tokenizer: object) -> None:
        self.tokenizer = tokenizer

    def tok_encode(
        self, text: str, add_special_tokens: bool | None = None
    ) -> list[int]:
        kwargs = (
            {} if add_special_tokens is None
            else {"add_special_tokens": add_special_tokens}
        )
        return self.tokenizer.encode(text, **kwargs)


class TokenizerBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tokenizer = AutoTokenizer.from_pretrained(
            DEEPSEEK, local_files_only=True, trust_remote_code=True
        )
        cls.lm = tokenizer_boundary_safe_hflm_class(TokenizerOnlyLM)(tokenizer)

    def test_non_prefix_stable_choice_is_nonempty_and_keeps_context(self) -> None:
        context = "Question: test?\nAnswer:"
        expected_context = self.lm.tok_encode(context)
        context_ids, continuation_ids = self.lm._encode_pair(context, " no")
        self.assertEqual(context_ids, expected_context)
        self.assertTrue(continuation_ids)
        self.assertTrue(self.lm._last_boundary_fallback)

    def test_prefix_stable_choice_keeps_stock_joint_encoding(self) -> None:
        context = "Question: test?\nAnswer:"
        whole = self.lm.tok_encode(context + " yes")
        context_ids, continuation_ids = self.lm._encode_pair(context, " yes")
        self.assertEqual(context_ids + continuation_ids, whole)
        self.assertFalse(self.lm._last_boundary_fallback)


if __name__ == "__main__":
    unittest.main()
