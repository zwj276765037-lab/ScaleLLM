#!/usr/bin/env python3
"""Torch adapters for model-level software/pre-Q/RTL-frontend A/B tests."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import torch
import torch.nn.functional as F


THIS_DIR = Path(__file__).resolve().parent
ARCHIVE_ROOT = THIS_DIR.parents[1]
ARCHIVE_SCRIPTS = ARCHIVE_ROOT / "experiment" / "scripts"
SCALE_CODE_DIR = ARCHIVE_SCRIPTS / "scale_code_linear"
MLP4_DIR = ARCHIVE_SCRIPTS / "accuracy_MLP_4bit"
for path in (SCALE_CODE_DIR, MLP4_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scalepath4_method_inference import (  # noqa: E402
    TARGET_OPS,
    ScalePathIAHScaleCodeLinear,
    _get_parent_module,
    _target_op_from_name,
    qdq_activation_iah_scale_code,
)
from mlp4_method_inference import weight_bits_for_op  # noqa: E402


Q_SCALE = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
S27_MIN = -(1 << 26)
S27_MAX = (1 << 26) - 1
INV_SQRT32_Q16 = 11_585
SCALE_EXACT_LIMIT = 4_261_478_400
SCALE_ROUND_LIMIT = 4_269_834_239
DENOM_SCALE_Q16 = 255 << 16


def fp_to_q16_raw(x: torch.Tensor, width: int) -> torch.Tensor:
    source = x.detach().to(torch.float32)
    magnitude = torch.floor(source.abs() * Q_SCALE + 0.5)
    signed = torch.where(source < 0, -magnitude, magnitude).to(torch.int64)
    low = -(1 << (width - 1))
    high = (1 << (width - 1)) - 1
    return signed.clamp(low, high)


def fp_to_s24_raw(x: torch.Tensor) -> torch.Tensor:
    return fp_to_q16_raw(x, 24)


def _round_shift_away(values: torch.Tensor, shift: int) -> torch.Tensor:
    half = 1 << (shift - 1)
    return torch.where(values >= 0, (values + half) >> shift,
                       -(((-values) + half) >> shift))


def _round_div_even(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    quotient = torch.div(numerator, denominator, rounding_mode="floor")
    remainder = numerator - quotient * denominator
    doubled = remainder * 2
    increment = (doubled > denominator) | (
        (doubled == denominator) & ((quotient & 1) != 0))
    return quotient + increment.to(torch.int64)


def _fwht_int(groups: torch.Tensor) -> torch.Tensor:
    work = groups
    distance = 1
    while distance < 32:
        shaped = work.reshape(-1, 32 // (2 * distance), 2, distance)
        lhs = shaped[:, :, 0, :].clone()
        rhs = shaped[:, :, 1, :].clone()
        shaped[:, :, 0, :] = lhs + rhs
        shaped[:, :, 1, :] = lhs - rhs
        distance *= 2
    return work


def rtl_activation_qdq(
    x: torch.Tensor, *, input_width: int = 24, output_width: int = 27,
    return_audit: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Production fixed-Q*.16/Hadamard/MinMax-A8 frontend on a Torch tensor."""
    input_dtype = x.dtype
    width = x.shape[-1]
    if width % 32:
        raise ValueError(f"RTL frontend requires a multiple of 32, got {width}")
    original_shape = x.shape
    source = x.detach().to(torch.float32)
    magnitude = torch.floor(source.abs() * Q_SCALE + 0.5)
    signed_unclipped = torch.where(source < 0, -magnitude, magnitude).to(torch.int64)
    input_low = -(1 << (input_width - 1))
    input_high = (1 << (input_width - 1)) - 1
    input_saturation = (signed_unclipped < input_low) | (signed_unclipped > input_high)
    raw_input = signed_unclipped.clamp(input_low, input_high).reshape(-1, 32)
    unscaled = _fwht_int(raw_input.clone())
    raw_h_unclipped = _round_shift_away(unscaled * INV_SQRT32_Q16, 16)
    output_low = -(1 << (output_width - 1))
    output_high = (1 << (output_width - 1)) - 1
    hadamard_saturation = (
        (raw_h_unclipped < output_low) | (raw_h_unclipped > output_high))
    raw_h = raw_h_unclipped.clamp(output_low, output_high)

    low = torch.minimum(raw_h.amin(dim=1), torch.zeros((), device=x.device,
                                                       dtype=torch.int64))
    high = torch.maximum(raw_h.amax(dim=1), torch.zeros((), device=x.device,
                                                        dtype=torch.int64))
    diff = high - low
    active = diff > 0

    shifted = diff.clone()
    scale_shift = torch.zeros_like(diff)
    for _ in range(63):
        advance = active & ((shifted << 1) <= SCALE_EXACT_LIMIT)
        shifted = torch.where(advance, shifted << 1, shifted)
        scale_shift = scale_shift + advance.to(torch.int64)
    scale_code = torch.zeros_like(diff)
    safe_diff = torch.where(active, diff, torch.ones_like(diff))
    encoded = _round_div_even(
        shifted, torch.full_like(shifted, DENOM_SCALE_Q16)).clamp(1, 255)
    scale_code = torch.where(active, encoded, scale_code)

    zero_point = _round_div_even((-low) * 255, safe_diff).clamp(0, 255)
    zero_point = torch.where(active, zero_point, torch.zeros_like(zero_point))
    numerator = raw_h * 255 + zero_point[:, None] * diff[:, None]
    safe_numerator = numerator.clamp_min(0)
    q = _round_div_even(safe_numerator, safe_diff[:, None]).clamp(0, 255)
    q = torch.where(active[:, None], q, torch.zeros_like(q))

    decoded_scale = torch.ldexp(scale_code.to(torch.float32),
                                -scale_shift.to(torch.int32))
    dq = (q - zero_point[:, None]).to(torch.float32) * decoded_scale[:, None]
    result = dq.reshape(original_shape).to(input_dtype)
    if not return_audit:
        return result
    audit = {
        "elements": torch.tensor(source.numel(), device=x.device, dtype=torch.int64),
        "groups": torch.tensor(raw_h.shape[0], device=x.device, dtype=torch.int64),
        "input_saturation_elements": input_saturation.sum(dtype=torch.int64),
        "hadamard_saturation_elements": hadamard_saturation.sum(dtype=torch.int64),
        "scale_format_error_groups": (
            (diff > SCALE_ROUND_LIMIT).sum(dtype=torch.int64)
            if output_width == 35 else torch.zeros((), device=x.device, dtype=torch.int64)
        ),
        "input_min": source.amin(),
        "input_max": source.amax(),
    }
    return result, audit


class PreQScalePathLinear(ScalePathIAHScaleCodeLinear):
    """Isolate FP->S24 before the unchanged archived software frontend."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        input_width = 32 if self.op_name == "down_proj" else 24
        fixed = (fp_to_q16_raw(x, input_width).to(torch.float32) / Q_SCALE).to(input_dtype)
        x_qdq = qdq_activation_iah_scale_code(
            fixed,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            act_bits=self.act_bits,
            scale_code_bits=self.scale_code_bits,
        )
        y = F.linear(
            x_qdq,
            self.weight.to(device=x.device),
            self.bias.to(device=x.device) if self.bias is not None else None,
        )
        return y.to(dtype=input_dtype)


class RTLFrontendScalePathLinear(ScalePathIAHScaleCodeLinear):
    """Use the exact integer activation frontend and unchanged folded weights."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.register_buffer(
            "audit_counts",
            torch.zeros(5, device=self.weight.device, dtype=torch.int64),
            persistent=False,
        )
        self.register_buffer(
            "audit_minmax",
            torch.tensor([float("inf"), float("-inf")],
                         device=self.weight.device, dtype=torch.float32),
            persistent=False,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        if self.op_name == "down_proj":
            x_qdq, audit = rtl_activation_qdq(
                x, input_width=32, output_width=35, return_audit=True)
        else:
            x_qdq, audit = rtl_activation_qdq(
                x, input_width=24, output_width=27, return_audit=True)
        self.audit_counts.add_(torch.stack([
            audit["elements"], audit["groups"],
            audit["input_saturation_elements"],
            audit["hadamard_saturation_elements"],
            audit["scale_format_error_groups"],
        ]))
        self.audit_minmax[0] = torch.minimum(self.audit_minmax[0], audit["input_min"])
        self.audit_minmax[1] = torch.maximum(self.audit_minmax[1], audit["input_max"])
        y = F.linear(
            x_qdq,
            self.weight.to(device=x.device),
            self.bias.to(device=x.device) if self.bias is not None else None,
        )
        return y.to(dtype=input_dtype)


def attach_frontend_case(
    model: torch.nn.Module,
    *,
    case: str,
    hadamard_block: int = 32,
    group_size: int = 32,
    act_bits: int = 8,
    attention_weight_bits: int = 8,
    mlp_weight_bits: int = 4,
    scale_code_bits: int = 8,
    compute_dtype: torch.dtype = torch.bfloat16,
) -> dict[str, Any]:
    if case not in {"pre_q_only", "rtl_exact"}:
        raise ValueError(f"unsupported frontend case: {case}")
    replacement_type = (
        PreQScalePathLinear if case == "pre_q_only" else RTLFrontendScalePathLinear)
    targets: list[tuple[str, str]] = []
    for name, module in model.named_modules():
        op = _target_op_from_name(name)
        if op in TARGET_OPS and isinstance(module, torch.nn.Linear):
            targets.append((name, op))

    per_op: dict[str, int] = {}
    for name, op in targets:
        parent, attr = _get_parent_module(model, name)
        original = getattr(parent, attr)
        weight_bits = weight_bits_for_op(
            op,
            attention_weight_bits=attention_weight_bits,
            mlp_weight_bits=mlp_weight_bits,
        )
        replacement = replacement_type(
            original,
            module_name=name,
            op_name=op,
            hadamard_block=hadamard_block,
            group_size=group_size,
            act_bits=act_bits,
            weight_bits=weight_bits,
            scale_code_bits=scale_code_bits,
            compute_dtype=compute_dtype,
        )
        setattr(parent, attr, replacement)
        per_op[op] = per_op.get(op, 0) + 1

    return {
        "case": case,
        "module_count": len(targets),
        "per_op": per_op,
        "activation_frontend": (
            "production S24 Q8.16 / S32 Q16.16 input, integer H32 and MinMax A8"
            if case == "rtl_exact"
            else "S24 Q8.16 / S32 Q16.16 boundary inserted before archived software H32 and A8"
        ),
        "weight_path": "unchanged archived folded ScaleCode W8 attention / W4 MLP",
    }


def collect_rtl_audit(model: torch.nn.Module) -> dict[str, Any]:
    """Aggregate counters accumulated by RTLFrontendScalePathLinear modules."""
    paths = {
        "s24_to_s27": {"counts": [0] * 5, "minimum": float("inf"),
                        "maximum": float("-inf")},
        "s32_to_s35": {"counts": [0] * 5, "minimum": float("inf"),
                        "maximum": float("-inf")},
    }
    for module in model.modules():
        if not isinstance(module, RTLFrontendScalePathLinear):
            continue
        key = "s32_to_s35" if module.op_name == "down_proj" else "s24_to_s27"
        counts = module.audit_counts.detach().cpu().tolist()
        for index, value in enumerate(counts):
            paths[key]["counts"][index] += int(value)
        minmax = module.audit_minmax.detach().cpu().tolist()
        paths[key]["minimum"] = min(paths[key]["minimum"], float(minmax[0]))
        paths[key]["maximum"] = max(paths[key]["maximum"], float(minmax[1]))

    output: dict[str, Any] = {}
    names = [
        "elements", "groups", "input_saturation_elements",
        "hadamard_saturation_elements", "scale_format_error_groups",
    ]
    for key, values in paths.items():
        row = dict(zip(names, values["counts"], strict=True))
        row["input_min"] = values["minimum"]
        row["input_max"] = values["maximum"]
        output[key] = row
    return output
