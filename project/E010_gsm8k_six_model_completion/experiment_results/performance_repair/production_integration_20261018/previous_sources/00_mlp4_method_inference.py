#!/usr/bin/env python3

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F


ARCHIVE_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SCALE_CODE_DIR = ARCHIVE_SCRIPTS_DIR / "scale_code_linear"
if str(SCALE_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(SCALE_CODE_DIR))

from scalepath4_method_inference import (  # noqa: E402
    TARGET_OPS,
    ScalePathIAHScaleCodeLinear,
    _get_parent_module,
    _target_op_from_name,
    fold_weight_left,
    local_h_right,
)


ATTENTION_OPS = {"q_proj", "k_proj", "v_proj", "o_proj"}
MLP_OPS = {"gate_proj", "up_proj", "down_proj", "gate_up_proj"}
FP16_MIN_SUBNORMAL = 2.0**-24


@dataclass
class MLP4AttachSummary:
    case: str
    target_scope: str
    module_count: int
    per_op: dict[str, int]
    per_op_weight_bits: dict[str, int]
    hadamard_block: int
    group_size: int
    act_bits: int
    attention_weight_bits: int
    mlp_weight_bits: int
    scale_code_bits: int
    payload_format: str
    invariant: str


def weight_bits_for_op(op: str, *, attention_weight_bits: int, mlp_weight_bits: int) -> int:
    if op in MLP_OPS:
        return int(mlp_weight_bits)
    if op in ATTENTION_OPS:
        return int(attention_weight_bits)
    raise ValueError(f"unsupported target op for MLP4 experiment: {op}")


def attach_scalepath_iah_scale_code_mlp_w4(
    model: torch.nn.Module,
    *,
    hadamard_block: int = 32,
    group_size: int = 32,
    act_bits: int = 8,
    attention_weight_bits: int = 8,
    mlp_weight_bits: int = 4,
    scale_code_bits: int = 8,
    compute_dtype: torch.dtype = torch.bfloat16,
    include_ops: set[str] | None = None,
) -> MLP4AttachSummary:
    include_ops = include_ops or TARGET_OPS
    targets: list[tuple[str, str]] = []
    for name, module in model.named_modules():
        op = _target_op_from_name(name)
        if op is None or op not in include_ops:
            continue
        if isinstance(module, torch.nn.Linear):
            targets.append((name, op))

    per_op: dict[str, int] = {}
    per_op_weight_bits: dict[str, int] = {}
    for name, op in targets:
        parent, attr = _get_parent_module(model, name)
        module = getattr(parent, attr)
        op_weight_bits = weight_bits_for_op(
            op,
            attention_weight_bits=attention_weight_bits,
            mlp_weight_bits=mlp_weight_bits,
        )
        replacement = ScalePathIAHScaleCodeLinear(
            module,
            module_name=name,
            op_name=op,
            hadamard_block=hadamard_block,
            group_size=group_size,
            act_bits=act_bits,
            weight_bits=op_weight_bits,
            scale_code_bits=scale_code_bits,
            compute_dtype=compute_dtype,
        )
        setattr(parent, attr, replacement)
        per_op[op] = per_op.get(op, 0) + 1
        per_op_weight_bits[op] = op_weight_bits
        if torch.cuda.is_available() and replacement.weight.is_cuda:
            torch.cuda.empty_cache()

    return MLP4AttachSummary(
        case=f"iah_scale_code_mlp_w{int(mlp_weight_bits)}_qdq_reference",
        target_scope=(
            f"q/k/v/o remain IA-H scale-code A8W{int(attention_weight_bits)}; "
            f"MLP gate/up/down remain IA-H scale-code A8W{int(mlp_weight_bits)}; "
            "GLM fused gate_up_proj is treated as MLP; lm_head excluded"
        ),
        module_count=len(targets),
        per_op=per_op,
        per_op_weight_bits=per_op_weight_bits,
        hadamard_block=int(hadamard_block),
        group_size=int(group_size),
        act_bits=int(act_bits),
        attention_weight_bits=int(attention_weight_bits),
        mlp_weight_bits=int(mlp_weight_bits),
        scale_code_bits=int(scale_code_bits),
        payload_format="uint8 code + uint8 shift_bits for activation and folded-weight scales",
        invariant=(
            "Only MLP folded-weight quantization bits differ from the ScalaPath4.0 "
            f"iah_scale_code A8W{int(attention_weight_bits)} reference."
        ),
    )


def _payload_scale(scale: torch.Tensor, scale_format: str) -> torch.Tensor:
    if scale_format == "fp16":
        safe = scale.to(torch.float32).clamp_min(FP16_MIN_SUBNORMAL)
        return safe.to(torch.float16).to(torch.float32).clamp_min(FP16_MIN_SUBNORMAL)
    if scale_format == "fp32":
        return scale.to(torch.float32)
    raise ValueError(f"unsupported payload scale format: {scale_format}")


def _fp16_payload_scale(scale: torch.Tensor) -> torch.Tensor:
    return _payload_scale(scale, "fp16")


def _fp32_reference_scale(scale: torch.Tensor) -> torch.Tensor:
    return _payload_scale(scale, "fp32")


def qdq_weight_iah_fp16_scale(
    weight_out_in: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    weight_bits: int,
    out_dtype: torch.dtype,
) -> torch.Tensor:
    qmax = (1 << (weight_bits - 1)) - 1
    w_fold = fold_weight_left(weight_out_in.detach().to(torch.float32), hadamard_block)
    in_features, out_features = w_fold.shape
    pad = (group_size - in_features % group_size) % group_size
    wp = F.pad(w_fold, (0, 0, 0, pad)) if pad else w_fold
    groups = wp.shape[0] // group_size
    wg = wp.reshape(groups, group_size, out_features).permute(2, 0, 1).contiguous()
    scale = (wg.abs().amax(dim=-1) / float(max(qmax, 1))).clamp_min(FP16_MIN_SUBNORMAL)
    scale_dec = _fp16_payload_scale(scale)
    q = torch.round(wg / scale_dec.unsqueeze(-1)).clamp(-qmax - 1, qmax)
    dq = (q * scale_dec.unsqueeze(-1)).permute(1, 2, 0).reshape(groups * group_size, out_features)
    dq = dq[:in_features, :].transpose(0, 1).contiguous()
    return dq.to(dtype=out_dtype)


def qdq_weight_iah_fp32_scale(
    weight_out_in: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    weight_bits: int,
    out_dtype: torch.dtype,
) -> torch.Tensor:
    qmax = (1 << (weight_bits - 1)) - 1
    w_fold = fold_weight_left(weight_out_in.detach().to(torch.float32), hadamard_block)
    in_features, out_features = w_fold.shape
    pad = (group_size - in_features % group_size) % group_size
    wp = F.pad(w_fold, (0, 0, 0, pad)) if pad else w_fold
    groups = wp.shape[0] // group_size
    wg = wp.reshape(groups, group_size, out_features).permute(2, 0, 1).contiguous()
    scale = (wg.abs().amax(dim=-1) / float(max(qmax, 1))).clamp_min(1e-12)
    scale_dec = _fp32_reference_scale(scale)
    q = torch.round(wg / scale.unsqueeze(-1)).clamp(-qmax - 1, qmax)
    dq = (q * scale_dec.unsqueeze(-1)).permute(1, 2, 0).reshape(groups * group_size, out_features)
    dq = dq[:in_features, :].transpose(0, 1).contiguous()
    return dq.to(dtype=out_dtype)


def qdq_activation_iah_fp16_scale(
    x: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    act_bits: int,
) -> torch.Tensor:
    qmax = (1 << act_bits) - 1
    input_dtype = x.dtype
    xh = local_h_right(x, hadamard_block).to(torch.float32)
    c = xh.shape[-1]
    pad = (group_size - c % group_size) % group_size
    xp = F.pad(xh, (0, pad)) if pad else xh
    xg = xp.reshape(-1, xp.shape[-1] // group_size, group_size)
    xmin = torch.minimum(xg.amin(dim=-1), torch.zeros((), device=x.device))
    xmax = torch.maximum(xg.amax(dim=-1), torch.zeros((), device=x.device))
    scale = ((xmax - xmin) / float(max(qmax, 1))).clamp_min(FP16_MIN_SUBNORMAL)
    scale_dec = _fp16_payload_scale(scale)
    zp = torch.round(-xmin / scale_dec).clamp(0, qmax)
    q = torch.round(xg / scale_dec.unsqueeze(-1) + zp.unsqueeze(-1)).clamp(0, qmax)
    dq = (q - zp.unsqueeze(-1)) * scale_dec.unsqueeze(-1)
    dq = dq.reshape(*xp.shape)[:, :c] if dq.dim() == 2 else dq.reshape(*xp.shape)[..., :c]
    return dq.reshape(*xh.shape).to(dtype=input_dtype)


def qdq_activation_iah_fp32_scale(
    x: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    act_bits: int,
) -> torch.Tensor:
    qmax = (1 << act_bits) - 1
    input_dtype = x.dtype
    xh = local_h_right(x, hadamard_block).to(torch.float32)
    c = xh.shape[-1]
    pad = (group_size - c % group_size) % group_size
    xp = F.pad(xh, (0, pad)) if pad else xh
    xg = xp.reshape(-1, xp.shape[-1] // group_size, group_size)
    xmin = torch.minimum(xg.amin(dim=-1), torch.zeros((), device=x.device))
    xmax = torch.maximum(xg.amax(dim=-1), torch.zeros((), device=x.device))
    scale = ((xmax - xmin) / float(max(qmax, 1))).clamp_min(1e-12)
    zp = torch.round(-xmin / scale).clamp(0, qmax)
    scale_dec = _fp32_reference_scale(scale)
    q = torch.round(xg / scale.unsqueeze(-1) + zp.unsqueeze(-1)).clamp(0, qmax)
    dq = (q - zp.unsqueeze(-1)) * scale_dec.unsqueeze(-1)
    dq = dq.reshape(*xp.shape)[:, :c] if dq.dim() == 2 else dq.reshape(*xp.shape)[..., :c]
    return dq.reshape(*xh.shape).to(dtype=input_dtype)


class ScalePathIAHFP16ScaleLinear(torch.nn.Module):
    def __init__(
        self,
        original: torch.nn.Linear,
        *,
        module_name: str,
        op_name: str,
        hadamard_block: int,
        group_size: int,
        act_bits: int,
        weight_bits: int,
        compute_dtype: torch.dtype,
    ) -> None:
        super().__init__()
        self.in_features = original.in_features
        self.out_features = original.out_features
        self.module_name = module_name
        self.op_name = op_name
        self.hadamard_block = int(hadamard_block)
        self.group_size = int(group_size)
        self.act_bits = int(act_bits)
        self.weight_bits = int(weight_bits)
        weight = qdq_weight_iah_fp16_scale(
            original.weight,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            weight_bits=self.weight_bits,
            out_dtype=compute_dtype,
        )
        self.register_buffer("weight", weight, persistent=False)
        bias = original.bias.detach().to(dtype=compute_dtype).clone() if original.bias is not None else None
        self.register_buffer("bias", bias, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        x_qdq = qdq_activation_iah_fp16_scale(
            x,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            act_bits=self.act_bits,
        )
        y = F.linear(x_qdq, self.weight.to(device=x.device), self.bias.to(device=x.device) if self.bias is not None else None)
        return y.to(dtype=input_dtype)


class ScalePathIAHFP32ScaleLinear(torch.nn.Module):
    def __init__(
        self,
        original: torch.nn.Linear,
        *,
        module_name: str,
        op_name: str,
        hadamard_block: int,
        group_size: int,
        act_bits: int,
        weight_bits: int,
        compute_dtype: torch.dtype,
    ) -> None:
        super().__init__()
        self.in_features = original.in_features
        self.out_features = original.out_features
        self.module_name = module_name
        self.op_name = op_name
        self.hadamard_block = int(hadamard_block)
        self.group_size = int(group_size)
        self.act_bits = int(act_bits)
        self.weight_bits = int(weight_bits)
        weight = qdq_weight_iah_fp32_scale(
            original.weight,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            weight_bits=self.weight_bits,
            out_dtype=compute_dtype,
        )
        self.register_buffer("weight", weight, persistent=False)
        bias = original.bias.detach().to(dtype=compute_dtype).clone() if original.bias is not None else None
        self.register_buffer("bias", bias, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        x_qdq = qdq_activation_iah_fp32_scale(
            x,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            act_bits=self.act_bits,
        )
        y = F.linear(x_qdq, self.weight.to(device=x.device), self.bias.to(device=x.device) if self.bias is not None else None)
        return y.to(dtype=input_dtype)


def attach_scalepath_iah_fp16_scale_mlp_w4(
    model: torch.nn.Module,
    *,
    hadamard_block: int = 32,
    group_size: int = 32,
    act_bits: int = 8,
    attention_weight_bits: int = 8,
    mlp_weight_bits: int = 4,
    compute_dtype: torch.dtype = torch.bfloat16,
    include_ops: set[str] | None = None,
) -> MLP4AttachSummary:
    include_ops = include_ops or TARGET_OPS
    targets: list[tuple[str, str]] = []
    for name, module in model.named_modules():
        op = _target_op_from_name(name)
        if op is None or op not in include_ops:
            continue
        if isinstance(module, torch.nn.Linear):
            targets.append((name, op))

    per_op: dict[str, int] = {}
    per_op_weight_bits: dict[str, int] = {}
    for name, op in targets:
        parent, attr = _get_parent_module(model, name)
        module = getattr(parent, attr)
        op_weight_bits = weight_bits_for_op(
            op,
            attention_weight_bits=attention_weight_bits,
            mlp_weight_bits=mlp_weight_bits,
        )
        replacement = ScalePathIAHFP16ScaleLinear(
            module,
            module_name=name,
            op_name=op,
            hadamard_block=hadamard_block,
            group_size=group_size,
            act_bits=act_bits,
            weight_bits=op_weight_bits,
            compute_dtype=compute_dtype,
        )
        setattr(parent, attr, replacement)
        per_op[op] = per_op.get(op, 0) + 1
        per_op_weight_bits[op] = op_weight_bits
        if torch.cuda.is_available() and replacement.weight.is_cuda:
            torch.cuda.empty_cache()

    return MLP4AttachSummary(
        case=f"iah_fp16_scale_mlp_w{int(mlp_weight_bits)}_qdq_reference",
        target_scope=(
            f"q/k/v/o remain IA-H A8W{int(attention_weight_bits)} with FP16 scale; "
            f"MLP gate/up/down remain IA-H A8W{int(mlp_weight_bits)} with FP16 scale; "
            "GLM fused gate_up_proj is treated as MLP; lm_head excluded"
        ),
        module_count=len(targets),
        per_op=per_op,
        per_op_weight_bits=per_op_weight_bits,
        hadamard_block=int(hadamard_block),
        group_size=int(group_size),
        act_bits=int(act_bits),
        attention_weight_bits=int(attention_weight_bits),
        mlp_weight_bits=int(mlp_weight_bits),
        scale_code_bits=0,
        payload_format=(
            "float16 scale payload for activation and folded-weight scales; "
            f"scales are floored at FP16 min subnormal ({FP16_MIN_SUBNORMAL:.3e}) and QDQ uses the decoded FP16 scale"
        ),
        invariant=(
            f"Same IA-H A8/W{int(attention_weight_bits)} attention and "
            f"A8/W{int(mlp_weight_bits)} MLP quantization as the selected control; "
            "only the scale payload is FP16 instead of ScaleCode."
        ),
    )


def attach_scalepath_iah_fp32_scale_mlp_w4(
    model: torch.nn.Module,
    *,
    hadamard_block: int = 32,
    group_size: int = 32,
    act_bits: int = 8,
    attention_weight_bits: int = 8,
    mlp_weight_bits: int = 4,
    compute_dtype: torch.dtype = torch.bfloat16,
    include_ops: set[str] | None = None,
) -> MLP4AttachSummary:
    include_ops = include_ops or TARGET_OPS
    targets: list[tuple[str, str]] = []
    for name, module in model.named_modules():
        op = _target_op_from_name(name)
        if op is None or op not in include_ops:
            continue
        if isinstance(module, torch.nn.Linear):
            targets.append((name, op))

    per_op: dict[str, int] = {}
    per_op_weight_bits: dict[str, int] = {}
    for name, op in targets:
        parent, attr = _get_parent_module(model, name)
        module = getattr(parent, attr)
        op_weight_bits = weight_bits_for_op(
            op,
            attention_weight_bits=attention_weight_bits,
            mlp_weight_bits=mlp_weight_bits,
        )
        replacement = ScalePathIAHFP32ScaleLinear(
            module,
            module_name=name,
            op_name=op,
            hadamard_block=hadamard_block,
            group_size=group_size,
            act_bits=act_bits,
            weight_bits=op_weight_bits,
            compute_dtype=compute_dtype,
        )
        setattr(parent, attr, replacement)
        per_op[op] = per_op.get(op, 0) + 1
        per_op_weight_bits[op] = op_weight_bits
        if torch.cuda.is_available() and replacement.weight.is_cuda:
            torch.cuda.empty_cache()

    return MLP4AttachSummary(
        case=f"iah_fp32_scale_mlp_w{int(mlp_weight_bits)}_qdq_reference",
        target_scope=(
            f"q/k/v/o remain IA-H A8W{int(attention_weight_bits)} with raw FP32 scale; "
            f"MLP gate/up/down remain IA-H A8W{int(mlp_weight_bits)} with raw FP32 scale; "
            "GLM fused gate_up_proj is treated as MLP; lm_head excluded"
        ),
        module_count=len(targets),
        per_op=per_op,
        per_op_weight_bits=per_op_weight_bits,
        hadamard_block=int(hadamard_block),
        group_size=int(group_size),
        act_bits=int(act_bits),
        attention_weight_bits=int(attention_weight_bits),
        mlp_weight_bits=int(mlp_weight_bits),
        scale_code_bits=0,
        payload_format="raw float32 scale reference for activation and folded-weight scales",
        invariant=(
            f"Same IA-H A8/W{int(attention_weight_bits)} attention and "
            f"A8/W{int(mlp_weight_bits)} MLP quantization as the selected control; "
            "no scale quantization is applied."
        ),
    )
