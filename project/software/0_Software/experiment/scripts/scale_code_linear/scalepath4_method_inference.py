#!/usr/bin/env python3

from __future__ import annotations

import math
from dataclasses import dataclass
import torch
import torch.nn.functional as F


TARGET_OPS = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj", "gate_up_proj"}


@dataclass
class ScalePathAttachSummary:
    case: str
    target_scope: str
    module_count: int
    per_op: dict[str, int]
    hadamard_block: int
    group_size: int
    act_bits: int
    weight_bits: int
    scale_code_bits: int
    payload_format: str


_H_CACHE: dict[tuple[str, int, torch.dtype], torch.Tensor] = {}


def hadamard(size: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (str(device), size, dtype)
    if key in _H_CACHE:
        return _H_CACHE[key]
    if size < 1 or size & (size - 1):
        raise ValueError(f"hadamard size must be a power of two, got {size}")
    h = torch.ones((1, 1), device=device, dtype=torch.float32)
    while h.shape[0] < size:
        h = torch.cat([torch.cat([h, h], dim=1), torch.cat([h, -h], dim=1)], dim=0)
    h = (h / math.sqrt(float(size))).to(dtype=dtype)
    _H_CACHE[key] = h
    return h


def local_h_right(x: torch.Tensor, block: int) -> torch.Tensor:
    c = x.shape[-1]
    main = (c // block) * block
    if main == 0:
        return x
    h = hadamard(block, x.device, x.dtype)
    x_main = x[..., :main].reshape(*x.shape[:-1], main // block, block)
    y_main = torch.matmul(x_main, h).reshape(*x.shape[:-1], main)
    if main == c:
        return y_main
    return torch.cat([y_main, x[..., main:]], dim=-1)


def fold_weight_left(weight_out_in: torch.Tensor, block: int) -> torch.Tensor:
    w = weight_out_in.transpose(0, 1).contiguous()
    main = (w.shape[0] // block) * block
    if main == 0:
        return w
    h = hadamard(block, w.device, w.dtype)
    w_main = w[:main, :].reshape(main // block, block, w.shape[1])
    folded = torch.matmul(h.transpose(0, 1), w_main).reshape(main, w.shape[1])
    if main == w.shape[0]:
        return folded
    return torch.cat([folded, w[main:, :]], dim=0)


def encode_scale(scale: torch.Tensor, bits: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    code_max = (1 << bits) - 1
    safe = scale.detach().to(torch.float32).clamp_min(1e-30)
    shift = torch.floor(torch.log2(float(code_max) / safe)).clamp(min=0, max=255).to(torch.int64)
    code = torch.round(safe * torch.pow(2.0, shift.to(torch.float32))).clamp(0, code_max).to(torch.int64)
    decoded = code.to(torch.float32) * torch.pow(2.0, -shift.to(torch.float32))
    return decoded, code, shift


def qdq_weight_iah_scale_code(
    weight_out_in: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    weight_bits: int,
    scale_code_bits: int,
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
    scale_dec, _code, _shift = encode_scale(scale, scale_code_bits)
    q = torch.round(wg / scale.unsqueeze(-1)).clamp(-qmax - 1, qmax)
    dq = (q * scale_dec.unsqueeze(-1)).permute(1, 2, 0).reshape(groups * group_size, out_features)
    dq = dq[:in_features, :].transpose(0, 1).contiguous()
    return dq.to(dtype=out_dtype)


def qdq_activation_iah_scale_code(
    x: torch.Tensor,
    *,
    hadamard_block: int,
    group_size: int,
    act_bits: int,
    scale_code_bits: int,
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
    scale_dec, _code, _shift = encode_scale(scale, scale_code_bits)
    q = torch.round(xg / scale.unsqueeze(-1) + zp.unsqueeze(-1)).clamp(0, qmax)
    dq = (q - zp.unsqueeze(-1)) * scale_dec.unsqueeze(-1)
    dq = dq.reshape(*xp.shape)[:, :c] if dq.dim() == 2 else dq.reshape(*xp.shape)[..., :c]
    return dq.reshape(*xh.shape).to(dtype=input_dtype)


class ScalePathIAHScaleCodeLinear(torch.nn.Module):
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
        scale_code_bits: int,
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
        self.scale_code_bits = int(scale_code_bits)
        weight = qdq_weight_iah_scale_code(
            original.weight,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            weight_bits=self.weight_bits,
            scale_code_bits=self.scale_code_bits,
            out_dtype=compute_dtype,
        )
        self.register_buffer("weight", weight, persistent=False)
        bias = original.bias.detach().to(dtype=compute_dtype).clone() if original.bias is not None else None
        self.register_buffer("bias", bias, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        x_qdq = qdq_activation_iah_scale_code(
            x,
            hadamard_block=self.hadamard_block,
            group_size=self.group_size,
            act_bits=self.act_bits,
            scale_code_bits=self.scale_code_bits,
        )
        y = F.linear(x_qdq, self.weight.to(device=x.device), self.bias.to(device=x.device) if self.bias is not None else None)
        return y.to(dtype=input_dtype)


def _get_parent_module(model: torch.nn.Module, module_name: str) -> tuple[torch.nn.Module, str]:
    parts = module_name.split(".")
    parent = model
    for part in parts[:-1]:
        parent = getattr(parent, part)
    return parent, parts[-1]


def _target_op_from_name(name: str) -> str | None:
    op = name.rsplit(".", 1)[-1]
    return op if op in TARGET_OPS else None


def attach_scalepath_iah_scale_code(
    model: torch.nn.Module,
    *,
    hadamard_block: int = 32,
    group_size: int = 32,
    act_bits: int = 8,
    weight_bits: int = 8,
    scale_code_bits: int = 8,
    compute_dtype: torch.dtype = torch.bfloat16,
    include_ops: set[str] | None = None,
) -> ScalePathAttachSummary:
    include_ops = include_ops or TARGET_OPS
    targets: list[tuple[str, str]] = []
    for name, module in model.named_modules():
        op = _target_op_from_name(name)
        if op is None or op not in include_ops:
            continue
        if isinstance(module, torch.nn.Linear):
            targets.append((name, op))
    per_op: dict[str, int] = {}
    for name, op in targets:
        parent, attr = _get_parent_module(model, name)
        module = getattr(parent, attr)
        replacement = ScalePathIAHScaleCodeLinear(
            module,
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
        if torch.cuda.is_available() and replacement.weight.is_cuda:
            torch.cuda.empty_cache()
    return ScalePathAttachSummary(
        case="iah_scale_code_qdq_reference",
        target_scope="q/k/v/o/gate/up/down linear modules; GLM gate_up_proj fused module included; lm_head excluded",
        module_count=len(targets),
        per_op=per_op,
        hadamard_block=hadamard_block,
        group_size=group_size,
        act_bits=act_bits,
        weight_bits=weight_bits,
        scale_code_bits=scale_code_bits,
        payload_format="uint8 code + uint8 shift_bits for activation and folded-weight scales",
    )
