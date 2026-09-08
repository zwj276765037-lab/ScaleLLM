#!/usr/bin/env python3

import copy
from types import SimpleNamespace
import unittest

from model.generate_scalellm_workload_reference import (
    EXPECTED_LINEAR_COUNTS,
    _validate_method_contract,
)


def valid_method():
    weight_bits = {
        op: 8 if op in {"q_proj", "k_proj", "v_proj", "o_proj"} else 4
        for op in EXPECTED_LINEAR_COUNTS
    }
    return SimpleNamespace(
        module_count=32,
        nonlinear_modules=[f"model.layers.{index}.mlp" for index in range(32)],
        per_arch={"LlamaMLP": 32},
        linear_summary={
            "module_count": 224,
            "per_op": dict(EXPECTED_LINEAR_COUNTS),
            "per_op_weight_bits": weight_bits,
            "hadamard_block": 32,
            "group_size": 32,
            "act_bits": 8,
            "attention_weight_bits": 8,
            "mlp_weight_bits": 4,
            "scale_code_bits": 8,
        },
    )


class ScaleLLMReferenceTests(unittest.TestCase):
    def test_exact_llama31_8b_quantized_coverage_passes(self):
        _validate_method_contract(valid_method())

    def test_partial_attention_coverage_is_rejected(self):
        method = copy.deepcopy(valid_method())
        method.linear_summary["per_op"]["q_proj"] = 31
        with self.assertRaisesRegex(RuntimeError, "linear coverage drifted"):
            _validate_method_contract(method)

    def test_mlp_weight_bit_drift_is_rejected(self):
        method = copy.deepcopy(valid_method())
        method.linear_summary["per_op_weight_bits"]["down_proj"] = 8
        with self.assertRaisesRegex(RuntimeError, "A8W8/A8W4"):
            _validate_method_contract(method)


if __name__ == "__main__":
    unittest.main()
