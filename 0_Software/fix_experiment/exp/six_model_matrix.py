#!/usr/bin/env python3
"""Frozen six-checkpoint matrix and ScaleCode attach expectations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    name: str
    directory: str
    model_type: str
    architecture: str
    layers: int
    expected_per_op: dict[str, int]

    @property
    def expected_module_count(self) -> int:
        return sum(self.expected_per_op.values())

    @property
    def expected_weight_bits(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for op in self.expected_per_op:
            result[op] = 8 if op in {"q_proj", "k_proj", "v_proj", "o_proj"} else 4
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "expected_module_count": self.expected_module_count,
            "expected_weight_bits": self.expected_weight_bits,
        }


def _standard_ops(layers: int) -> dict[str, int]:
    return {
        "q_proj": layers,
        "k_proj": layers,
        "v_proj": layers,
        "o_proj": layers,
        "gate_proj": layers,
        "up_proj": layers,
        "down_proj": layers,
    }


MODEL_SPECS = (
    ModelSpec(
        "DeepSeek-R1-Distill-Llama-8B",
        "DeepSeek-R1-Distill-Llama-8B",
        "llama",
        "LlamaForCausalLM",
        32,
        _standard_ops(32),
    ),
    ModelSpec(
        "GLM-4-9B-0414",
        "GLM-4-9B-0414",
        "glm4",
        "Glm4ForCausalLM",
        40,
        {
            "q_proj": 40,
            "k_proj": 40,
            "v_proj": 40,
            "o_proj": 40,
            "gate_up_proj": 40,
            "down_proj": 40,
        },
    ),
    ModelSpec(
        "Llama-3.1-8B-Instruct",
        "Llama-3.1-8B-Instruct",
        "llama",
        "LlamaForCausalLM",
        32,
        _standard_ops(32),
    ),
    ModelSpec(
        "Llama-3.2-3B-Instruct",
        "Llama-3.2-3B-Instruct",
        "llama",
        "LlamaForCausalLM",
        28,
        _standard_ops(28),
    ),
    ModelSpec(
        "Qwen2.5-7B-Instruct",
        "Qwen2.5-7B-Instruct",
        "qwen2",
        "Qwen2ForCausalLM",
        28,
        _standard_ops(28),
    ),
    ModelSpec(
        "Qwen3-8B",
        "Qwen3-8B",
        "qwen3",
        "Qwen3ForCausalLM",
        36,
        _standard_ops(36),
    ),
)

MODEL_BY_DIRECTORY = {spec.directory: spec for spec in MODEL_SPECS}

FIVE_CONFIG_CASES = (
    "bf16",
    "a8w8_fp32",
    "a8w4_fp32",
    "a8w4_fp16",
    "reference_qdq",
)

QUANTIZED_CASE_SPECS = {
    "a8w8_fp32": {"mlp_weight_bits": 8, "scale_code_bits": 0, "payload": "fp32"},
    "a8w4_fp32": {"mlp_weight_bits": 4, "scale_code_bits": 0, "payload": "fp32"},
    "a8w4_fp16": {"mlp_weight_bits": 4, "scale_code_bits": 0, "payload": "fp16"},
    "reference_qdq": {"mlp_weight_bits": 4, "scale_code_bits": 8, "payload": "scalecode"},
}


def get_model_spec(model_path: Path) -> ModelSpec:
    resolved = model_path.resolve()
    try:
        spec = MODEL_BY_DIRECTORY[resolved.name]
    except KeyError as exc:
        raise ValueError(
            f"checkpoint {resolved} is not in the frozen six-model matrix"
        ) from exc
    config_path = resolved / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    observed = {
        "model_type": config.get("model_type"),
        "architecture": (config.get("architectures") or [None])[0],
        "layers": config.get("num_hidden_layers"),
    }
    expected = {
        "model_type": spec.model_type,
        "architecture": spec.architecture,
        "layers": spec.layers,
    }
    if observed != expected:
        raise ValueError(
            f"checkpoint config mismatch for {spec.name}: observed={observed}, "
            f"expected={expected}"
        )
    return spec


def validate_reference_qdq_summary(
    summary: dict[str, Any], spec: ModelSpec
) -> None:
    validate_quantized_summary(summary, spec, "reference_qdq")


def validate_quantized_summary(
    summary: dict[str, Any], spec: ModelSpec, case: str
) -> None:
    if case not in QUANTIZED_CASE_SPECS:
        raise ValueError(f"not a five-config quantized case: {case}")
    case_spec = QUANTIZED_CASE_SPECS[case]
    observed_count = int(summary.get("module_count", -1))
    if observed_count != spec.expected_module_count:
        raise ValueError(
            f"Reference-QDQ attach count mismatch for {spec.name}: "
            f"observed={observed_count}, expected={spec.expected_module_count}"
        )
    observed_per_op = {
        str(key): int(value) for key, value in summary.get("per_op", {}).items()
    }
    if observed_per_op != spec.expected_per_op:
        raise ValueError(
            f"Reference-QDQ per-op attach mismatch for {spec.name}: "
            f"observed={observed_per_op}, expected={spec.expected_per_op}"
        )
    observed_bits = {
        str(key): int(value)
        for key, value in summary.get("per_op_weight_bits", {}).items()
    }
    expected_bits = {
        op: (
            8
            if op in {"q_proj", "k_proj", "v_proj", "o_proj"}
            else int(case_spec["mlp_weight_bits"])
        )
        for op in spec.expected_per_op
    }
    if observed_bits != expected_bits:
        raise ValueError(
            f"{case} per-op bit-width mismatch for {spec.name}: "
            f"observed={observed_bits}, expected={expected_bits}"
        )
    fixed_fields = {
        "hadamard_block": 32,
        "group_size": 32,
        "act_bits": 8,
        "attention_weight_bits": 8,
        "mlp_weight_bits": int(case_spec["mlp_weight_bits"]),
        "scale_code_bits": int(case_spec["scale_code_bits"]),
    }
    for key, expected in fixed_fields.items():
        observed = summary.get(key)
        if observed != expected:
            raise ValueError(
                f"{case} {key} mismatch for {spec.name}: "
                f"observed={observed}, expected={expected}"
            )
    payload_format = str(summary.get("payload_format", "")).lower()
    expected_payload = str(case_spec["payload"])
    payload_ok = {
        "fp32": "float32" in payload_format,
        "fp16": "float16" in payload_format,
        "scalecode": "uint8 code" in payload_format,
    }[expected_payload]
    if not payload_ok:
        raise ValueError(
            f"{case} payload mismatch for {spec.name}: {payload_format!r}"
        )
