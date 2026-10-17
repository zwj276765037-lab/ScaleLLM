#!/usr/bin/env python3

import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from model import generate_scalellm_workload_reference as generator
from model.generate_scalellm_workload_reference import (
    EXPECTED_LINEAR_COUNTS,
    _validate_legacy_method_contract,
)
from tests.test_scalellm_board import EXPECTED_CURRENT_NUMERIC_CONTRACT


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


def current_method():
    return {
        "case": "v5_production_fullchain",
        "manifest": "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
        "attention_format_id": "0x48384103",
        "mlp_full_format_id": "0x48384605",
        "layers": 32, "max_context": 128, "cohort_rows": 16,
        "attention_weight_bits": 8, "mlp_weight_bits": 4,
        "activation_bits": 8, "kv_bits": 12,
        "host_residual_rmsnorm": "FP32", "lm_head": "FP32 host",
        "strict_total_shift": True, "total_shift_policy": "strict_rtl",
        "software_reference_not_hardware": False,
        "node_trace_layers": [], "mlp_total_shift_range": [12, 44],
        "mlp_group_guard_compute_width": 45,
        "mlp_gate_up_accumulator_compute_width": 44,
        "mlp_down_accumulator_compute_width": 54,
        "mlp_down_output_width": 32,
    }


class ScaleLLMReferenceTests(unittest.TestCase):
    def test_exact_llama31_8b_quantized_coverage_passes(self):
        _validate_legacy_method_contract(valid_method())

    def test_partial_attention_coverage_is_rejected(self):
        method = copy.deepcopy(valid_method())
        method.linear_summary["per_op"]["q_proj"] = 31
        with self.assertRaisesRegex(RuntimeError, "linear coverage drifted"):
            _validate_legacy_method_contract(method)

    def test_mlp_weight_bit_drift_is_rejected(self):
        method = copy.deepcopy(valid_method())
        method.linear_summary["per_op_weight_bits"]["down_proj"] = 8
        with self.assertRaisesRegex(RuntimeError, "A8W8/A8W4"):
            _validate_legacy_method_contract(method)


class CurrentGeneratorDispatchTests(unittest.TestCase):
    def test_main_passes_exact_v5_flags_and_records_method_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.jsonl"
            dataset.write_text('{"text":"fixture"}\n', encoding="ascii")
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            artifact = root / "artifact.json"
            artifact.write_text(json.dumps({
                "schema_version": 2,
                "model_id": "meta-llama/Llama-3.1-8B-Instruct",
                "layer_count": 32,
                "checkpoint_sha256": "a" * 64,
                "checkpoint_id": "a" * 64,
                "attention_format_id": 0x4838_4103,
                "attention_abi": 0x0002_0000,
                "mlp_format_id": 0x4838_4605,
                "mlp_abi": 0x0005_0000,
            }), encoding="ascii")
            output = root / "output"

            method = current_method()
            names = {
                f"model.layers.{layer}.{scope}.{op}.weight"
                for layer in range(32)
                for scope, ops in (
                    ("self_attn", ("q_proj", "k_proj", "v_proj", "o_proj")),
                    ("mlp", ("gate_proj", "up_proj", "down_proj")),
                ) for op in ops
            }
            self.assertEqual(len(names), 224)
            audit = SimpleNamespace(
                linear_values={name: {} for name in names},
                collect=lambda: {"activation_elements": 32},
                collect_linear=lambda: {name: {} for name in names},
            )
            model = SimpleNamespace(config=SimpleNamespace(use_cache=True))
            model.to = lambda device: model
            model.eval = lambda: model
            calls = []

            def attach(actual_model, **kwargs):
                calls.append((actual_model, kwargs))
                return method, audit

            torch = ModuleType("torch")
            torch.__version__ = "fixture"
            torch.version = SimpleNamespace(cuda="fixture")
            torch.backends = SimpleNamespace(
                cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)),
                cudnn=SimpleNamespace(allow_tf32=True),
            )
            torch.set_num_threads = lambda count: None
            torch.manual_seed = lambda seed: None
            torch.use_deterministic_algorithms = lambda enabled: None
            class FakeDevice:
                def __init__(self, name):
                    self.name = name
                    self.type = name.split(":", 1)[0]

                def __str__(self):
                    return self.name

            torch.device = FakeDevice
            torch.cuda = SimpleNamespace(
                is_available=lambda: True,
                set_device=lambda device: None,
                get_device_name=lambda device: "fixture-gpu",
            )
            torch.bfloat16 = "bfloat16"
            torch.float16 = "float16"
            torch.float32 = "float32"
            transformers = ModuleType("transformers")
            transformers.AutoTokenizer = SimpleNamespace(
                from_pretrained=lambda *args, **kwargs: object()
            )
            transformers.AutoModelForCausalLM = SimpleNamespace(
                from_pretrained=lambda *args, **kwargs: model
            )
            samples = [
                {"sample_id": f"sample-{index}",
                 "input_token_ids": [index + 1] * 16,
                 "target_token_ids": [index + 2] * 16,
                 "valid_tokens": 16}
                for index in range(2)
            ]
            records = [{"sample_id": item["sample_id"], "nll_sum": 8.0}
                       for item in samples]
            sources = [generator.file_record(path) for path in (
                generator.SCRIPT_PATH,
                generator.HAP_ROOT / "model" / "freeze_scalellm_workload.py",
                generator.GOLDEN_PATH,
                generator.HAP_ROOT / "model" / "export_scalellm_llama31_artifacts.py",
                generator.HAP_ROOT / "model" / "fixbit_v2.py",
            )]
            checkpoint_instance = SimpleNamespace(
                source_identity=lambda: ("a" * 64, [])
            )
            args = [
                "--dataset", str(dataset), "--model-dir", str(checkpoint),
                "--artifact-manifest", str(artifact), "--output-dir", str(output),
                "--sample-count", "2",
            ]

            def write_fixture_manifest(**kwargs):
                path = kwargs["output"]
                path.write_text('{"fixture":"dispatch-only"}\n', encoding="ascii")
                return path

            with mock.patch.dict(sys.modules, {
                "torch": torch, "transformers": transformers,
            }), mock.patch.object(generator, "_load_current_attach", return_value=attach) as load_attach, \
                    mock.patch.object(generator, "_legacy_imports", side_effect=AssertionError("legacy path")), \
                    mock.patch.object(generator, "_source_records", return_value=sources) as source_records, \
                    mock.patch.object(generator, "LlamaCheckpoint", return_value=checkpoint_instance), \
                    mock.patch.object(generator, "build_samples", return_value=samples), \
                    mock.patch.object(generator, "_evaluate", return_value=(records, 0.5)), \
                    mock.patch.object(generator, "write_workload_manifest", side_effect=write_fixture_manifest) as writer, \
                    redirect_stdout(io.StringIO()):
                generator.main(args)

            load_attach.assert_called_once_with()
            self.assertEqual(len(calls), 1)
            self.assertIs(calls[0][0], model)
            self.assertEqual(calls[0][1], {
                "checkpoint_dir": checkpoint.resolve(),
                "device": calls[0][1]["device"],
                "strict_total_shift": True,
                "software_extended": False,
                "down_output_width": 32,
                "down_shift12_candidate": True,
            })
            self.assertEqual(calls[0][1]["device"].type, "cuda")
            self.assertEqual(str(calls[0][1]["device"]), "cuda:0")
            self.assertEqual(source_records.call_count, 2)
            self.assertTrue(all(call.kwargs["attach"] is attach
                                for call in source_records.call_args_list))
            self.assertEqual(writer.call_args.kwargs["software_id"],
                             generator.SOFTWARE_ID)
            self.assertEqual(writer.call_args.kwargs["reference_profile"],
                             generator.CURRENT_PROFILE)
            evidence = json.loads((output / "software_reference.json").read_text())
            self.assertEqual(evidence["quantization"]["method"], method)
            self.assertEqual(evidence["quantization"]["fixedpoint"],
                             EXPECTED_CURRENT_NUMERIC_CONTRACT)
            self.assertEqual(evidence["audit"]["counters"]["activation_elements"], 32)
            self.assertEqual(len(evidence["audit"]["linear"]), 224)
            self.assertEqual(evidence["source_files"], sources)
            self.assertEqual((evidence["schema"], evidence["profile"]),
                             (generator.CURRENT_SCHEMA, generator.CURRENT_PROFILE))

    def test_current_method_rejects_old_down_width_and_missing_linear(self):
        method = current_method()
        method["mlp_down_output_width"] = 24
        audit = SimpleNamespace(collect=lambda: {}, collect_linear=lambda: {},
                                linear_values={})
        with self.assertRaisesRegex(RuntimeError, "mlp_down_output_width"):
            generator._validate_current_method(method, audit)
        method["mlp_down_output_width"] = 32
        with self.assertRaisesRegex(RuntimeError, "224 linear operations"):
            generator._validate_current_method(method, audit)


if __name__ == "__main__":
    unittest.main()
