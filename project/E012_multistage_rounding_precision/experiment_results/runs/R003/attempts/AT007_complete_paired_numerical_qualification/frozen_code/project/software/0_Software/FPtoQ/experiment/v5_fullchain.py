#!/usr/bin/env python3
"""Executable V5 production numeric twin for Llama-3.1-8B quality tests.

The model deliberately follows the arithmetic selected by
``attention_mlp_production_v5_cohort16_sources.list``.  It is not a QDQ
approximation: projection outputs, RoPE, KV cache values, QK scores,
probabilities, PV outputs, and the SwiGLU product cross the same integer
boundaries as the production RTL.

Only scheduling and physical tiling are abstracted.  The fused Triton linear
kernel evaluates the same Group32 correlation, ScaleCode multiply/shift,
Q*.24 accumulation, final round-half-away, and S24 saturation as the RTL.
"""

from __future__ import annotations

from dataclasses import dataclass
import gc
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

import triton
import triton.language as tl


THIS_DIR = Path(__file__).resolve().parent
SCALELLM_ROOT = THIS_DIR.parents[2]
if str(SCALELLM_ROOT) not in sys.path:
    sys.path.insert(0, str(SCALELLM_ROOT))

from model.export_scalellm_llama31_artifacts import (  # noqa: E402
    LlamaCheckpoint,
    llama3_inv_freq,
    quantize_folded_rows,
    round_away as numpy_round_away,
)
from model.fixbit_v2 import build_softmax_exp_lut_u17  # noqa: E402


GROUP = 32
Q16 = 1 << 16
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
INV_SQRT32_Q16 = 11_585
SCALE_EXACT_LIMIT = 4_261_478_400
SCALE_ROUND_LIMIT = 4_269_834_239
KV_QMAX = 2_047
KV_DENOM_Q16 = KV_QMAX << 16
KV_HALF_DENOM_Q16 = KV_DENOM_Q16 // 2
KV_SHIFT_MIN = 8
KV_SHIFT_MAX = 32
HEAD_SCALE_Q16 = 5_793
SCORE_LIMIT_Q14 = 16 << 14
SILU_LIMIT_Q16 = 16 << 16
SILU_STEP_Q16 = 1 << 8


def _round_shift_away(values: torch.Tensor, shift: int) -> torch.Tensor:
    if shift == 0:
        return values
    half = 1 << (shift - 1)
    return torch.where(
        values >= 0,
        (values + half) >> shift,
        -(((-values) + half) >> shift),
    )


def _round_div_even(
    numerator: torch.Tensor, denominator: torch.Tensor
) -> torch.Tensor:
    quotient = torch.div(numerator, denominator, rounding_mode="floor")
    remainder = numerator - quotient * denominator
    doubled = remainder << 1
    increment = (doubled > denominator) | (
        (doubled == denominator) & ((quotient & 1) != 0)
    )
    return quotient + increment.to(torch.int64)


def _fwht32_int(groups: torch.Tensor) -> torch.Tensor:
    work = groups
    distance = 1
    while distance < GROUP:
        shaped = work.reshape(-1, GROUP // (2 * distance), 2, distance)
        low = shaped[:, :, 0, :].clone()
        high = shaped[:, :, 1, :].clone()
        shaped[:, :, 0, :] = low + high
        shaped[:, :, 1, :] = low - high
        distance *= 2
    return work


@dataclass
class PreparedActivation:
    values_u8: torch.Tensor
    codes_u8: torch.Tensor
    shifts_u8: torch.Tensor
    zero_points_u8: torch.Tensor
    leading_shape: tuple[int, ...]

    @property
    def rows(self) -> int:
        return int(self.values_u8.shape[0])

    @property
    def groups(self) -> int:
        return int(self.values_u8.shape[1])


class V5Audit:
    """GPU-resident counters; collection synchronizes only once at the end."""

    COUNTERS = (
        "fp_to_fixed_saturation",
        "hadamard_saturation",
        "activation_scale_format_error",
        "linear_total_shift_format_error",
        "linear_group_guard_overflow_s37",
        "linear_software_group_guard_overflow",
        "linear_accumulator_overflow",
        "linear_software_accumulator_overflow",
        "linear_output_saturation",
        "rope_output_saturation",
        "kv12_clip",
        "qk_score_clip",
        "pv_output_saturation",
        "swiglu_output_overflow",
    )
    LINEAR_KERNEL_COUNTERS = (
        "linear_group_guard_overflow_s37",
        "linear_software_group_guard_overflow",
        "linear_accumulator_overflow",
        "linear_software_accumulator_overflow",
        "linear_output_saturation",
    )

    def __init__(self, device: torch.device) -> None:
        self.device = device
        self.node_trace: Any = None
        self.linear_values: dict[str, dict[str, torch.Tensor]] = {}
        self.values = {
            name: torch.zeros((), dtype=torch.int64, device=device)
            for name in self.COUNTERS
        }
        self.activation_elements = torch.zeros(
            (), dtype=torch.int64, device=device
        )

    def add(self, name: str, value: torch.Tensor | int) -> None:
        if name not in self.values:
            raise KeyError(name)
        if isinstance(value, int):
            self.values[name].add_(value)
        else:
            self.values[name].add_(value.to(torch.int64))

    def collect(self) -> dict[str, int]:
        output = {"activation_elements": int(self.activation_elements.item())}
        for name, value in self.values.items():
            total = int(value.item())
            if name in self.LINEAR_KERNEL_COUNTERS:
                total += sum(
                    int(counters[name].item())
                    for counters in self.linear_values.values()
                )
            output[name] = total
        return output

    def register_linear(self, module_name: str) -> dict[str, torch.Tensor]:
        if module_name in self.linear_values:
            raise ValueError(f"duplicate V5 linear audit name: {module_name}")
        counters = {
            name: torch.zeros((), dtype=torch.int64, device=self.device)
            for name in self.LINEAR_KERNEL_COUNTERS
        }
        counters["linear_total_shift_min"] = torch.full(
            (), 127, dtype=torch.int64, device=self.device
        )
        counters["linear_total_shift_max"] = torch.full(
            (), -1, dtype=torch.int64, device=self.device
        )
        self.linear_values[module_name] = counters
        return counters

    def collect_linear(self) -> dict[str, dict[str, int]]:
        return {
            module_name: {
                name: int(value.item()) for name, value in counters.items()
            }
            for module_name, counters in self.linear_values.items()
        }


def fp_to_fixed_raw(
    source: torch.Tensor,
    width: int,
    audit: V5Audit | None = None,
) -> torch.Tensor:
    value = source.detach().to(torch.float32)
    magnitude = torch.floor(value.abs() * Q16 + 0.5)
    raw = torch.where(value < 0, -magnitude, magnitude).to(torch.int64)
    low = -(1 << (width - 1))
    high = (1 << (width - 1)) - 1
    if audit is not None:
        audit.activation_elements.add_(value.numel())
        audit.add(
            "fp_to_fixed_saturation", ((raw < low) | (raw > high)).sum()
        )
    return raw.clamp(low, high)


def prepare_fixed_activation(
    raw: torch.Tensor,
    *,
    input_width: int,
    hadamard_width: int,
    audit: V5Audit | None = None,
) -> PreparedActivation:
    """Run the production integer H32 and asymmetric MinMax U8 frontend."""
    if raw.shape[-1] % GROUP:
        raise ValueError("V5 activation width must be divisible by Group32")
    low = -(1 << (input_width - 1))
    high = (1 << (input_width - 1)) - 1
    if raw.dtype != torch.int64:
        raw = raw.to(torch.int64)
    outside = (raw < low) | (raw > high)
    if bool(outside.any().item()):
        raise ValueError(
            f"fixed activation does not fit S{input_width}: "
            f"min={int(raw.amin().item())} max={int(raw.amax().item())} "
            f"outside={int(outside.sum().item())}/{raw.numel()}"
        )

    leading_shape = tuple(int(v) for v in raw.shape[:-1])
    groups = raw.reshape(-1, raw.shape[-1] // GROUP, GROUP).contiguous()
    transformed = _fwht32_int(groups.clone())
    normalized_unclipped = _round_shift_away(
        transformed * INV_SQRT32_Q16, 16
    )
    h_low = -(1 << (hadamard_width - 1))
    h_high = (1 << (hadamard_width - 1)) - 1
    h_saturation = (
        (normalized_unclipped < h_low) | (normalized_unclipped > h_high)
    )
    normalized = normalized_unclipped.clamp(h_low, h_high)

    minimum = torch.minimum(
        normalized.amin(dim=-1),
        torch.zeros((), dtype=torch.int64, device=raw.device),
    )
    maximum = torch.maximum(
        normalized.amax(dim=-1),
        torch.zeros((), dtype=torch.int64, device=raw.device),
    )
    diff = maximum - minimum
    active = diff > 0
    shifted = diff.clone()
    scale_shift = torch.zeros_like(diff)
    for _ in range(63):
        advance = active & ((shifted << 1) <= SCALE_EXACT_LIMIT)
        shifted = torch.where(advance, shifted << 1, shifted)
        scale_shift.add_(advance.to(torch.int64))

    denom = torch.full_like(shifted, 255 << 16)
    encoded = _round_div_even(shifted, denom).clamp(1, 255)
    scale_code = torch.where(active, encoded, torch.zeros_like(encoded))
    safe_diff = torch.where(active, diff, torch.ones_like(diff))
    zero_point = _round_div_even(-minimum * 255, safe_diff).clamp(0, 255)
    zero_point = torch.where(
        active, zero_point, torch.zeros_like(zero_point)
    )
    numerator = normalized * 255 + zero_point[..., None] * diff[..., None]
    quantized = _round_div_even(
        numerator.clamp_min(0), safe_diff[..., None]
    ).clamp(0, 255)
    quantized = torch.where(
        active[..., None], quantized, torch.zeros_like(quantized)
    )

    if audit is not None:
        audit.add("hadamard_saturation", h_saturation.sum())
        audit.add(
            "activation_scale_format_error", (diff > SCALE_ROUND_LIMIT).sum()
        )
    return PreparedActivation(
        quantized.to(torch.uint8).contiguous(),
        scale_code.to(torch.uint8).contiguous(),
        scale_shift.to(torch.uint8).contiguous(),
        zero_point.to(torch.uint8).contiguous(),
        leading_shape,
    )


@triton.jit
def _v5_grouped_linear_kernel(
    act_ptr,
    act_code_ptr,
    act_shift_ptr,
    act_zp_ptr,
    weight_ptr,
    weight_code_ptr,
    weight_shift_ptr,
    output_ptr,
    saturation_count_ptr,
    group_guard_overflow_count_ptr,
    software_group_guard_overflow_count_ptr,
    accumulator_overflow_count_ptr,
    software_accumulator_overflow_count_ptr,
    rows: tl.constexpr,
    columns: tl.constexpr,
    group_count: tl.constexpr,
    GROUP_SIZE: tl.constexpr,
    OUTPUT_MIN: tl.constexpr,
    OUTPUT_MAX: tl.constexpr,
    SHIFT_MIN: tl.constexpr,
    SHIFT_MAX: tl.constexpr,
    HARDWARE_ACCUM_MIN: tl.constexpr,
    HARDWARE_ACCUM_MAX: tl.constexpr,
    COMPUTE_ACCUM_MIN: tl.constexpr,
    COMPUTE_ACCUM_MAX: tl.constexpr,
    COMPUTE_ACCUM_MASK: tl.constexpr,
    COMPUTE_GUARD_MIN: tl.constexpr,
    COMPUTE_GUARD_MAX: tl.constexpr,
    ZERO_INVALID_GUARD: tl.constexpr,
    AUDIT_HARDWARE_GROUP_GUARD: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    row_ids = tl.program_id(0) * BLOCK_M + tl.arange(0, BLOCK_M)
    column_ids = tl.program_id(1) * BLOCK_N + tl.arange(0, BLOCK_N)
    lane_ids = tl.arange(0, GROUP_SIZE)
    row_mask = row_ids < rows
    column_mask = column_ids < columns
    accumulator = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.int64)
    group_guard_overflow_total = tl.zeros((), dtype=tl.int64)
    software_group_guard_overflow_total = tl.zeros((), dtype=tl.int64)
    accumulator_overflow_total = tl.zeros((), dtype=tl.int64)
    software_accumulator_overflow_total = tl.zeros((), dtype=tl.int64)

    for group in tl.range(0, group_count):
        act_offsets = (
            (row_ids[:, None] * group_count + group) * GROUP_SIZE
            + lane_ids[None, :]
        )
        weight_offsets = (
            (column_ids[None, :] * group_count + group) * GROUP_SIZE
            + lane_ids[:, None]
        )
        act = tl.load(
            act_ptr + act_offsets,
            mask=row_mask[:, None],
            other=0,
        ).to(tl.int32)
        zp = tl.load(
            act_zp_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int32)
        weight = tl.load(
            weight_ptr + weight_offsets,
            mask=column_mask[None, :],
            other=0,
        ).to(tl.int32)
        centered = act - zp[:, None]
        correlation = tl.dot(
            centered.to(tl.float32),
            weight.to(tl.float32),
            # centered A8 and W8/W4 are small exact integers.  Their Group32
            # dot is bounded by 32*255*127=1,036,320 < 2^20, so TF32 inputs,
            # products and FP32 accumulation remain integer-exact while using
            # Ampere Tensor Cores.  Scalar conformance tests cover this path.
            input_precision="tf32",
            out_dtype=tl.float32,
        ).to(tl.int64)
        act_code = tl.load(
            act_code_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int64)
        act_shift = tl.load(
            act_shift_ptr + row_ids * group_count + group,
            mask=row_mask,
            other=0,
        ).to(tl.int32)
        weight_code = tl.load(
            weight_code_ptr + column_ids * group_count + group,
            mask=column_mask,
            other=0,
        ).to(tl.int64)
        weight_shift = tl.load(
            weight_shift_ptr + column_ids * group_count + group,
            mask=column_mask,
            other=0,
        ).to(tl.int32)
        raw = correlation * act_code[:, None] * weight_code[None, :]
        delta = act_shift[:, None] + weight_shift[None, :] - 24
        right = tl.maximum(delta, 0)
        left = tl.maximum(-delta, 0)
        aligned = (raw >> right) << left
        pair_active = (act_code[:, None] != 0) & (weight_code[None, :] != 0)
        legal_shift = (delta + 24 >= SHIFT_MIN) & (delta + 24 <= SHIFT_MAX)
        valid_output = row_mask[:, None] & column_mask[None, :]
        if AUDIT_HARDWARE_GROUP_GUARD:
            guard_overflow = valid_output & pair_active & (
                (aligned < COMPUTE_GUARD_MIN)
                | (aligned > COMPUTE_GUARD_MAX)
            )
            group_guard_overflow_total += tl.sum(tl.sum(
                guard_overflow.to(tl.int64), axis=1
            ), axis=0)
        software_guard_overflow = valid_output & pair_active & (
            (aligned < COMPUTE_GUARD_MIN) | (aligned > COMPUTE_GUARD_MAX)
        )
        software_group_guard_overflow_total += tl.sum(tl.sum(
            software_guard_overflow.to(tl.int64), axis=1
        ), axis=0)
        # strict_rtl and rtl_zero_guard reproduce the production error path.
        # software_extended retains the mathematically aligned contribution
        # while still auditing it against the production RTL widths.
        if ZERO_INVALID_GUARD:
            guard = tl.where(pair_active & ~legal_shift, 0, aligned)
        else:
            guard = aligned
        next_accumulator = accumulator + guard
        accumulator_overflow = valid_output & (
            (next_accumulator < HARDWARE_ACCUM_MIN)
            | (next_accumulator > HARDWARE_ACCUM_MAX)
        )
        overflow_count = tl.sum(tl.sum(
            accumulator_overflow.to(tl.int64), axis=1
        ), axis=0)
        accumulator_overflow_total += overflow_count
        software_accumulator_overflow = valid_output & (
            (next_accumulator < COMPUTE_ACCUM_MIN)
            | (next_accumulator > COMPUTE_ACCUM_MAX)
        )
        software_accumulator_overflow_total += tl.sum(tl.sum(
            software_accumulator_overflow.to(tl.int64), axis=1
        ), axis=0)
        accumulator = (
            (next_accumulator - COMPUTE_ACCUM_MIN) & COMPUTE_ACCUM_MASK
        ) + COMPUTE_ACCUM_MIN

    rounded = tl.where(
        accumulator >= 0,
        (accumulator + 128) >> 8,
        -(((-accumulator) + 128) >> 8),
    )
    saturated = tl.minimum(tl.maximum(rounded, OUTPUT_MIN), OUTPUT_MAX)
    saturation_mask = row_mask[:, None] & column_mask[None, :] & (
        rounded != saturated
    )
    saturation_count = tl.sum(
        tl.sum(saturation_mask.to(tl.int64), axis=1), axis=0
    )
    tl.atomic_add(saturation_count_ptr, saturation_count)
    tl.atomic_add(group_guard_overflow_count_ptr, group_guard_overflow_total)
    tl.atomic_add(
        software_group_guard_overflow_count_ptr,
        software_group_guard_overflow_total,
    )
    tl.atomic_add(accumulator_overflow_count_ptr, accumulator_overflow_total)
    tl.atomic_add(
        software_accumulator_overflow_count_ptr,
        software_accumulator_overflow_total,
    )
    output_offsets = row_ids[:, None] * columns + column_ids[None, :]
    tl.store(
        output_ptr + output_offsets,
        saturated.to(tl.int32),
        mask=row_mask[:, None] & column_mask[None, :],
    )


def grouped_linear_s24(
    activation: PreparedActivation,
    weight_s8: torch.Tensor,
    weight_codes_u8: torch.Tensor,
    weight_shifts_u8: torch.Tensor,
    shift_min: int,
    shift_max: int,
    hardware_accumulator_width: int,
    compute_accumulator_width: int,
    compute_group_guard_width: int,
    zero_invalid_guard: bool,
    audit_hardware_group_guard: bool,
    saturation_count: torch.Tensor,
    group_guard_overflow_count: torch.Tensor,
    software_group_guard_overflow_count: torch.Tensor,
    accumulator_overflow_count: torch.Tensor,
    software_accumulator_overflow_count: torch.Tensor,
    output_min: int = S24_MIN,
    output_max: int = S24_MAX,
) -> torch.Tensor:
    if not weight_s8.is_cuda:
        raise ValueError("V5 grouped linear requires CUDA")
    rows = activation.rows
    columns, groups, lanes = weight_s8.shape
    if groups != activation.groups or lanes != GROUP:
        raise ValueError("activation/weight Group32 geometry mismatch")
    output = torch.empty(
        (rows, columns), dtype=torch.int32, device=weight_s8.device
    )
    # tl.dot requires an M tile of at least 16 on the CUDA backend.  Rows
    # below 16 are handled by the load/store masks.
    block_m = 16
    block_n = 16
    grid = (triton.cdiv(rows, block_m), triton.cdiv(columns, block_n))
    _v5_grouped_linear_kernel[grid](
        activation.values_u8,
        activation.codes_u8,
        activation.shifts_u8,
        activation.zero_points_u8,
        weight_s8,
        weight_codes_u8,
        weight_shifts_u8,
        output,
        saturation_count,
        group_guard_overflow_count,
        software_group_guard_overflow_count,
        accumulator_overflow_count,
        software_accumulator_overflow_count,
        rows=rows,
        columns=columns,
        group_count=groups,
        GROUP_SIZE=GROUP,
        OUTPUT_MIN=output_min,
        OUTPUT_MAX=output_max,
        SHIFT_MIN=shift_min,
        SHIFT_MAX=shift_max,
        HARDWARE_ACCUM_MIN=-(1 << (hardware_accumulator_width - 1)),
        HARDWARE_ACCUM_MAX=(1 << (hardware_accumulator_width - 1)) - 1,
        COMPUTE_ACCUM_MIN=-(1 << (compute_accumulator_width - 1)),
        COMPUTE_ACCUM_MAX=(1 << (compute_accumulator_width - 1)) - 1,
        COMPUTE_ACCUM_MASK=(1 << compute_accumulator_width) - 1,
        COMPUTE_GUARD_MIN=-(1 << (compute_group_guard_width - 1)),
        COMPUTE_GUARD_MAX=(1 << (compute_group_guard_width - 1)) - 1,
        ZERO_INVALID_GUARD=zero_invalid_guard,
        AUDIT_HARDWARE_GROUP_GUARD=audit_hardware_group_guard,
        BLOCK_M=block_m,
        BLOCK_N=block_n,
        num_warps=4,
    )
    return output.reshape(*activation.leading_shape, columns)


class V5ProductionLinear(nn.Module):
    def __init__(
        self,
        *,
        module_name: str,
        op_name: str,
        weight_s8: np.ndarray,
        weight_codes_u8: np.ndarray,
        weight_shifts_u8: np.ndarray,
        input_width: int,
        hadamard_width: int,
        output_width: int = 24,
        device: torch.device,
        audit: V5Audit,
        strict_total_shift: bool = True,
        software_extended: bool = False,
        down_shift12_candidate: bool = False,
    ) -> None:
        super().__init__()
        self.module_name = module_name
        self.op_name = op_name
        self.input_width = int(input_width)
        self.hadamard_width = int(hadamard_width)
        self.output_width = int(output_width)
        if self.output_width not in {24, 32}:
            raise ValueError("V5 linear output width must be S24 or S32")
        self.audit = audit
        self.linear_audit = audit.register_linear(module_name)
        self.strict_total_shift = bool(strict_total_shift)
        self.software_extended = bool(software_extended)
        self.down_shift12_candidate = bool(down_shift12_candidate)
        if self.strict_total_shift and self.software_extended:
            raise ValueError(
                "software_extended cannot be combined with strict_total_shift"
            )
        self.register_buffer(
            "weight_s8",
            torch.from_numpy(np.asarray(weight_s8, dtype=np.int8)).to(device),
            persistent=False,
        )
        histogram = np.zeros((weight_shifts_u8.shape[1], 64), dtype=np.int32)
        code_array = np.asarray(weight_codes_u8, dtype=np.uint8)
        shift_array = np.asarray(weight_shifts_u8, dtype=np.uint8)
        for group_index in range(shift_array.shape[1]):
            selected = shift_array[code_array[:, group_index] != 0, group_index]
            histogram[group_index] = np.bincount(selected, minlength=64)
        self.register_buffer(
            "weight_shift_cumulative",
            torch.from_numpy(
                histogram.cumsum(axis=1, dtype=np.int64)
            ).to(device),
            persistent=False,
        )
        self.register_buffer(
            "group_ids",
            torch.arange(histogram.shape[0], dtype=torch.int64, device=device),
            persistent=False,
        )
        self.register_buffer(
            "weight_codes_u8",
            torch.from_numpy(
                np.asarray(weight_codes_u8, dtype=np.uint8)
            ).to(device),
            persistent=False,
        )
        self.register_buffer(
            "weight_shifts_u8",
            torch.from_numpy(
                np.asarray(weight_shifts_u8, dtype=np.uint8)
            ).to(device),
            persistent=False,
        )
        self.in_features = int(self.weight_s8.shape[1] * GROUP)
        self.out_features = int(self.weight_s8.shape[0])

    def prepare_float(self, source: torch.Tensor) -> PreparedActivation:
        raw = fp_to_fixed_raw(source, self.input_width, self.audit)
        return self.prepare_raw(raw)

    def prepare_raw(self, raw: torch.Tensor) -> PreparedActivation:
        return prepare_fixed_activation(
            raw,
            input_width=self.input_width,
            hadamard_width=self.hadamard_width,
            audit=self.audit,
        )

    def project_prepared(self, activation: PreparedActivation) -> torch.Tensor:
        # Check the dynamic ScaleCode exponent contract without materializing
        # the rows x columns x groups Cartesian product.
        low_limit = 26 if self.op_name in {
            "q_proj", "k_proj", "v_proj", "o_proj"
        } else (
            12
            if self.op_name == "down_proj" and self.down_shift12_candidate
            else 20
        )
        high_limit = 47 if low_limit == 26 else 44
        active = activation.codes_u8 != 0
        act_shift = activation.shifts_u8.to(torch.int16)
        weight_shift = self.weight_shifts_u8.to(torch.int16)
        weight_active = self.weight_codes_u8 != 0
        minimum = torch.where(
            weight_active,
            weight_shift,
            torch.full_like(weight_shift, 127),
        ).amin(dim=0)
        maximum = torch.where(
            weight_active,
            weight_shift,
            torch.full_like(weight_shift, -127),
        ).amax(dim=0)
        valid_pair = active & (minimum.unsqueeze(0) < 127)
        observed_minimum = torch.where(
            valid_pair,
            act_shift + minimum.unsqueeze(0),
            torch.full_like(act_shift, 127),
        ).amin()
        observed_maximum = torch.where(
            valid_pair,
            act_shift + maximum.unsqueeze(0),
            torch.full_like(act_shift, -1),
        ).amax()
        torch.minimum(
            self.linear_audit["linear_total_shift_min"],
            observed_minimum.to(torch.int64),
            out=self.linear_audit["linear_total_shift_min"],
        )
        torch.maximum(
            self.linear_audit["linear_total_shift_max"],
            observed_maximum.to(torch.int64),
            out=self.linear_audit["linear_total_shift_max"],
        )
        invalid_low = active & (act_shift + minimum.unsqueeze(0) < low_limit)
        invalid_high = active & (act_shift + maximum.unsqueeze(0) > high_limit)
        invalid = invalid_low | invalid_high
        invalid_exists = (
            bool(invalid.any().item()) if self.strict_total_shift else False
        )

        # Non-strict diagnostic/reference modes stay asynchronous: count every
        # offending row/group/column pair without a per-linear GPU sync.
        if not self.strict_total_shift or invalid_exists:
            cumulative = self.weight_shift_cumulative
            total_weights = cumulative[:, -1]
            group_ids = self.group_ids[None, :].expand_as(act_shift)
            lower_threshold = low_limit - act_shift - 1
            lower_count = cumulative[
                group_ids, lower_threshold.clamp(0, 63).to(torch.int64)
            ]
            lower_count = torch.where(
                lower_threshold < 0,
                torch.zeros_like(lower_count),
                torch.where(
                    lower_threshold >= 63,
                    total_weights[None, :].expand_as(lower_count),
                    lower_count,
                ),
            )
            upper_threshold = high_limit - act_shift
            at_or_below = cumulative[
                group_ids, upper_threshold.clamp(0, 63).to(torch.int64)
            ]
            upper_count = total_weights[None, :].expand_as(at_or_below) - at_or_below
            upper_count = torch.where(
                upper_threshold < 0,
                total_weights[None, :].expand_as(upper_count),
                torch.where(
                    upper_threshold >= 63,
                    torch.zeros_like(upper_count),
                    upper_count,
                ),
            )
            error_events = torch.where(
                active, lower_count + upper_count, torch.zeros_like(lower_count)
            ).sum()
            self.audit.add("linear_total_shift_format_error", error_events)

        if invalid_exists:
            use_high = bool(invalid_high.any().item())
            selected = invalid_high if use_high else invalid_low
            row_index, group_index = [
                int(value) for value in selected.nonzero()[0].tolist()
            ]
            candidates = weight_active[:, group_index]
            candidate_shifts = weight_shift[:, group_index]
            masked = torch.where(
                candidates,
                candidate_shifts,
                torch.full_like(candidate_shifts, -127 if use_high else 127),
            )
            column_index = int(
                (masked.argmax() if use_high else masked.argmin()).item()
            )
            activation_shift = int(act_shift[row_index, group_index].item())
            selected_weight_shift = int(
                weight_shift[column_index, group_index].item()
            )
            raise ValueError(
                f"{self.module_name} observed a production-invalid total shift: "
                f"row={row_index} group={group_index} column={column_index} "
                f"activation_shift={activation_shift} "
                f"weight_shift={selected_weight_shift} "
                f"total={activation_shift + selected_weight_shift} "
                f"legal=[{low_limit},{high_limit}]"
            )
        # Current production format-v3 widened the MLP Group32 guard and
        # accumulators specifically so total_shift=20 is representable:
        # S37 guard, S44 Gate/Up accumulator and S46 Down accumulator.
        hardware_accumulator_width = (
            42
            if low_limit == 26
            else (
                54
                if self.op_name == "down_proj" and self.down_shift12_candidate
                else (46 if self.op_name == "down_proj" else 44)
            )
        )
        compute_accumulator_width = hardware_accumulator_width
        compute_group_guard_width = (
            42
            if low_limit == 26
            else (
                45
                if self.op_name == "down_proj" and self.down_shift12_candidate
                else 37
            )
        )
        output = grouped_linear_s24(
            activation,
            self.weight_s8,
            self.weight_codes_u8,
            self.weight_shifts_u8,
            low_limit,
            high_limit,
            hardware_accumulator_width,
            compute_accumulator_width,
            compute_group_guard_width,
            not self.software_extended,
            low_limit == 20,
            self.linear_audit["linear_output_saturation"],
            self.linear_audit["linear_group_guard_overflow_s37"],
            self.linear_audit["linear_software_group_guard_overflow"],
            self.linear_audit["linear_accumulator_overflow"],
            self.linear_audit["linear_software_accumulator_overflow"],
            output_min=-(1 << (self.output_width - 1)),
            output_max=(1 << (self.output_width - 1)) - 1,
        )
        if self.output_width == 24:
            # RTL carries this boundary on a packed signed [23:0] wire.  A
            # small subset of large production tiles can reach PyTorch as the
            # corresponding zero-extended 24-bit bit pattern (0x800000 through
            # 0xffffff) even though the Triton result storage is int32.  Make
            # the signed-wire semantics explicit before any S24 consumer.
            # Correctly sign-extended int32 values are unchanged, while a
            # genuine value above the 24-bit payload range remains visible to
            # the downstream contract check instead of being masked.
            packed_negative = (output > S24_MAX) & (output <= (1 << 24) - 1)
            output = torch.where(
                packed_negative,
                output - (1 << 24),
                output,
            )
        # The fused kernel already saturates.  Exact pre-saturation counting
        # is provided by the scalar conformance test, while model runs retain
        # all other saturation/error counters.
        return output

    def forward_raw(self, source: torch.Tensor) -> torch.Tensor:
        return self.project_prepared(self.prepare_float(source))

    def forward_raw_fixed(self, raw: torch.Tensor) -> torch.Tensor:
        return self.project_prepared(self.prepare_raw(raw))

    def forward(self, source: torch.Tensor) -> torch.Tensor:
        return self.forward_raw(source).to(torch.float32) / Q16


def _fixed_rope(
    raw: torch.Tensor,
    cos_q16: torch.Tensor,
    sin_q16: torch.Tensor,
    audit: V5Audit,
) -> torch.Tensor:
    # raw: B,T,H,128; coefficients: B,T,64
    low = raw[..., :64].to(torch.int64)
    high = raw[..., 64:].to(torch.int64)
    cos = cos_q16[:, :, None, :].to(torch.int64)
    sin = sin_q16[:, :, None, :].to(torch.int64)
    low_cos = _round_shift_away(low * cos, 16)
    high_sin = _round_shift_away(high * sin, 16)
    low_sin = _round_shift_away(low * sin, 16)
    high_cos = _round_shift_away(high * cos, 16)
    first_unclipped = low_cos - high_sin
    second_unclipped = low_sin + high_cos
    saturation = (
        ((first_unclipped < S24_MIN) | (first_unclipped > S24_MAX)).sum()
        + ((second_unclipped < S24_MIN) | (second_unclipped > S24_MAX)).sum()
    )
    audit.add("rope_output_saturation", saturation)
    return torch.cat(
        [
            first_unclipped.clamp(S24_MIN, S24_MAX),
            second_unclipped.clamp(S24_MIN, S24_MAX),
        ],
        dim=-1,
    ).to(torch.int32)


def _logical_to_interleaved_head(raw: torch.Tensor) -> torch.Tensor:
    """Match the V5 Q/K DDR row map: x0,x64,x1,x65,... per head."""
    if raw.shape[-1] != 128:
        raise ValueError("V5 Q/K head dimension must be 128")
    return torch.stack([raw[..., :64], raw[..., 64:]], dim=-1).reshape(
        *raw.shape[:-1], 128
    )


@dataclass
class KV12:
    values_s12: torch.Tensor
    codes_u8: torch.Tensor
    shifts_u8: torch.Tensor


def _kv12_quantize(raw_s24: torch.Tensor, audit: V5Audit) -> KV12:
    # B,T,KVH,128 -> B,T,KVH,4,32
    groups = raw_s24.to(torch.int64).reshape(*raw_s24.shape[:-1], 4, 32)
    max_abs = groups.abs().amax(dim=-1)
    active = max_abs != 0
    shifted = max_abs << KV_SHIFT_MIN
    shifts = torch.full_like(max_abs, KV_SHIFT_MIN)
    threshold = 256 * KV_DENOM_Q16 - KV_HALF_DENOM_Q16 - 1
    for _ in range(KV_SHIFT_MAX - KV_SHIFT_MIN):
        advance = active & (shifts < KV_SHIFT_MAX) & (
            (shifted << 1) <= threshold
        )
        shifted = torch.where(advance, shifted << 1, shifted)
        shifts.add_(advance.to(torch.int64))
    codes = (shifted + KV_HALF_DENOM_Q16) // KV_DENOM_Q16
    codes = torch.where(active, codes, torch.zeros_like(codes))
    shifts = torch.where(active, shifts, torch.zeros_like(shifts))
    safe_max = torch.where(active, max_abs, torch.ones_like(max_abs))
    magnitude_unclipped = (
        groups.abs() * KV_QMAX + safe_max[..., None] // 2
    ) // safe_max[..., None]
    audit.add("kv12_clip", (magnitude_unclipped > KV_QMAX).sum())
    magnitude = magnitude_unclipped.clamp_max(KV_QMAX)
    values = torch.where(groups < 0, -magnitude, magnitude)
    values = torch.where(active[..., None], values, torch.zeros_like(values))
    return KV12(
        values.to(torch.int16), codes.to(torch.uint8), shifts.to(torch.uint8)
    )


def _qk_scores_s20(
    query_s24: torch.Tensor,
    keys: KV12,
    num_key_value_groups: int,
    audit: V5Audit,
) -> torch.Tensor:
    batch, query_count, heads, _ = query_s24.shape
    key_count = int(keys.values_s12.shape[1])
    query = query_s24.reshape(batch, query_count, heads, 4, 32)
    query = query.permute(0, 2, 3, 1, 4).to(torch.float64)
    key = keys.values_s12.repeat_interleave(
        num_key_value_groups, dim=2
    ).permute(0, 2, 3, 1, 4).to(torch.float64)
    # All products and partial sums are below 2^40, hence FP64 GEMM is an
    # exact integer dot-product implementation here (53-bit mantissa).
    dot_s40 = torch.matmul(query, key.transpose(-1, -2)).to(torch.int64)
    codes = keys.codes_u8.repeat_interleave(
        num_key_value_groups, dim=2
    ).permute(0, 2, 3, 1).to(torch.int64)
    shifts = keys.shifts_u8.repeat_interleave(
        num_key_value_groups, dim=2
    ).permute(0, 2, 3, 1).to(torch.int64)
    scaled_s61 = dot_s40 * codes[..., None, :] * HEAD_SCALE_Q16
    group_q14 = scaled_s61 >> (shifts[..., None, :] + 18)
    score_unclipped = group_q14.sum(dim=2)
    clipped = score_unclipped.clamp(-SCORE_LIMIT_Q14, SCORE_LIMIT_Q14)
    audit.add("qk_score_clip", (clipped != score_unclipped).sum())
    return clipped


def _softmax_u16(
    score_s20: torch.Tensor,
    valid_mask: torch.Tensor,
    lut_u17: torch.Tensor,
) -> torch.Tensor:
    sentinel = torch.full_like(score_s20, -(1 << 19))
    row_max = torch.where(valid_mask, score_s20, sentinel).amax(
        dim=-1, keepdim=True
    )
    delta = (score_s20 - row_max).clamp(-SCORE_LIMIT_Q14, 0)
    magnitude = -delta
    index = magnitude >> 10
    fraction = magnitude & 0x3FF
    high = lut_u17[index]
    low = lut_u17[(index + 1).clamp_max(256)]
    interpolation = ((high - low) * fraction + 512) >> 10
    exponent = torch.where(valid_mask, high - interpolation, 0)
    row_sum = exponent.sum(dim=-1, keepdim=True)
    row_has_key = valid_mask.any(dim=-1, keepdim=True)
    if bool((row_has_key & (row_sum < 65536)).any().item()):
        raise ValueError("V5 Softmax row has no valid key")
    # lm_eval left-pads variable-length requests within a batch.  A padded
    # query row can be fully masked, but it is not a model token and is never
    # scored.  Production hardware receives only real token rows.  Use an
    # all-zero probability/context row for that software-only padding slot so
    # it cannot affect any real query while retaining strict checks for every
    # row that has at least one valid key.
    safe_row_sum = torch.where(row_has_key, row_sum, 65536)
    reciprocal = ((1 << 32) + safe_row_sum // 2) // safe_row_sum
    probability = ((exponent * reciprocal + 32768) >> 16).clamp_max(65535)
    return torch.where(
        row_has_key, probability, torch.zeros_like(probability)
    ).to(torch.int64)


def _pv_s24(
    probability_u16: torch.Tensor,
    values: KV12,
    num_key_value_groups: int,
    audit: V5Audit,
    head_chunk: int = 4,
) -> torch.Tensor:
    batch, heads, query_count, key_count = probability_u16.shape
    values_h = values.values_s12.repeat_interleave(
        num_key_value_groups, dim=2
    ).to(torch.int64)
    codes_h = values.codes_u8.repeat_interleave(
        num_key_value_groups, dim=2
    ).to(torch.int64)
    shifts_h = values.shifts_u8.repeat_interleave(
        num_key_value_groups, dim=2
    ).to(torch.int64)
    output = torch.empty(
        (batch, heads, query_count, 4, 32),
        dtype=torch.int32,
        device=probability_u16.device,
    )
    for head_start in range(0, heads, head_chunk):
        head_end = min(head_start + head_chunk, heads)
        prob = probability_u16[:, head_start:head_end]
        for group in range(4):
            value = values_h[:, :, head_start:head_end, group, :]
            code = codes_h[:, :, head_start:head_end, group]
            shift = shifts_h[:, :, head_start:head_end, group]
            value_code = value * code[..., None]
            product = (
                prob[..., None]
                * value_code.permute(0, 2, 1, 3)[:, :, None, :, :]
            )
            shift_amount = torch.where(
                code != 0, shift - 8, torch.zeros_like(shift)
            )
            guard = product >> shift_amount.permute(0, 2, 1)[
                :, :, None, :, None
            ]
            accumulator = guard.sum(dim=3)
            rounded = _round_shift_away(accumulator, 8)
            saturated = rounded.clamp(S24_MIN, S24_MAX)
            audit.add("pv_output_saturation", (rounded != saturated).sum())
            output[:, head_start:head_end, :, group, :] = saturated.to(
                torch.int32
            )
    return output.reshape(batch, heads, query_count, 128)


class V5NodeTrace:
    """Bounded real-activation error trace for fixed Attention and MLP nodes."""

    def __init__(self, layers: set[int], max_calls_per_layer: int = 1) -> None:
        self.layers = {int(layer) for layer in layers}
        self.max_calls_per_layer = int(max_calls_per_layer)
        self.attention_calls = {layer: 0 for layer in self.layers}
        self.mlp_calls = {layer: 0 for layer in self.layers}
        self.rows: list[dict[str, Any]] = []

    def enabled(self, layer_id: int, domain: str = "attention") -> bool:
        calls = self.attention_calls if domain == "attention" else self.mlp_calls
        return (
            layer_id in self.layers
            and calls[layer_id] < self.max_calls_per_layer
        )

    @staticmethod
    def _metrics(
        node: str,
        approximate: torch.Tensor,
        reference: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        lhs = approximate.detach().to(torch.float64)
        rhs = reference.detach().to(torch.float64)
        if mask is not None:
            selected = mask.to(torch.bool)
            lhs = lhs[selected]
            rhs = rhs[selected]
        else:
            lhs = lhs.reshape(-1)
            rhs = rhs.reshape(-1)
        difference = lhs - rhs
        reference_energy = torch.sum(rhs * rhs)
        denominator = torch.linalg.vector_norm(lhs) * torch.linalg.vector_norm(rhs)
        cosine = torch.where(
            denominator > 0,
            torch.sum(lhs * rhs) / denominator,
            torch.ones((), dtype=torch.float64, device=lhs.device),
        )
        nmse = torch.where(
            reference_energy > 0,
            torch.sum(difference * difference) / reference_energy,
            torch.zeros((), dtype=torch.float64, device=lhs.device),
        )
        return {
            "node": node,
            "elements": int(lhs.numel()),
            "cosine": float(cosine.item()),
            "nmse": float(nmse.item()),
            "mae": float(difference.abs().mean().item()),
            "max_abs_error": float(difference.abs().amax().item()),
            "reference_abs_max": float(rhs.abs().amax().item()),
        }

    @staticmethod
    def _kv12_dequant(cache: KV12, repeat_heads: int = 1) -> torch.Tensor:
        values = cache.values_s12.to(torch.float64)
        codes = cache.codes_u8.to(torch.float64)
        shifts = cache.shifts_u8.to(torch.int32)
        scale = torch.ldexp(codes, -shifts)
        dequantized = values * scale[..., None]
        if repeat_heads != 1:
            dequantized = dequantized.repeat_interleave(repeat_heads, dim=2)
        return dequantized

    def record(
        self,
        *,
        layer_id: int,
        query_before_rope: torch.Tensor,
        key_before_rope: torch.Tensor,
        query_after_rope: torch.Tensor,
        key_after_rope: torch.Tensor,
        cos_q16: torch.Tensor,
        sin_q16: torch.Tensor,
        query_interleaved: torch.Tensor,
        key_interleaved: torch.Tensor,
        value_s24: torch.Tensor,
        key_cache: KV12,
        value_cache: KV12,
        scores_s20: torch.Tensor,
        valid_mask: torch.Tensor,
        probability_u16: torch.Tensor,
        context_s24: torch.Tensor,
        num_key_value_groups: int,
    ) -> None:
        if not self.enabled(layer_id):
            return
        rows: list[dict[str, Any]] = []
        cos = cos_q16[:, :, None, :].to(torch.float64) / Q16
        sin = sin_q16[:, :, None, :].to(torch.float64) / Q16

        def rope_reference(source: torch.Tensor) -> torch.Tensor:
            low = source[..., :64].to(torch.float64) / Q16
            high = source[..., 64:].to(torch.float64) / Q16
            return torch.cat(
                [low * cos - high * sin, low * sin + high * cos], dim=-1
            )

        rows.append(self._metrics(
            "rope_q_local",
            query_after_rope.to(torch.float64) / Q16,
            rope_reference(query_before_rope),
        ))
        rows.append(self._metrics(
            "rope_k_local",
            key_after_rope.to(torch.float64) / Q16,
            rope_reference(key_before_rope),
        ))

        key_dequant = self._kv12_dequant(key_cache)
        value_dequant = self._kv12_dequant(value_cache)
        rows.append(self._metrics(
            "kv12_key",
            key_dequant,
            key_interleaved.reshape_as(key_dequant).to(torch.float64) / Q16,
        ))
        rows.append(self._metrics(
            "kv12_value",
            value_dequant,
            value_s24.reshape_as(value_dequant).to(torch.float64) / Q16,
        ))

        batch, query_count, heads, _ = query_interleaved.shape
        query_real = query_interleaved.reshape(
            batch, query_count, heads, 4, 32
        ).to(torch.float64) / Q16
        key_real = key_dequant.repeat_interleave(
            num_key_value_groups, dim=2
        )
        score_reference = torch.einsum(
            "bqhgd,bkhgd->bhqk", query_real, key_real
        ) / math.sqrt(128.0)
        score_reference = score_reference.clamp(-16.0, 16.0)
        rows.append(self._metrics(
            "qk_score_cumulative",
            scores_s20.to(torch.float64) / (1 << 14),
            score_reference,
            valid_mask,
        ))

        score_real = scores_s20.to(torch.float64) / (1 << 14)
        softmax_reference = torch.softmax(
            score_real.masked_fill(~valid_mask, -torch.inf), dim=-1
        )
        probability_real = probability_u16.to(torch.float64) / Q16
        rows.append(self._metrics(
            "softmax_local",
            probability_real,
            softmax_reference,
            valid_mask,
        ))

        value_real = value_dequant.repeat_interleave(
            num_key_value_groups, dim=2
        ).reshape(batch, value_s24.shape[1], heads, 128)
        context_reference = torch.einsum(
            "bhqk,bkhd->bhqd", probability_real, value_real
        )
        rows.append(self._metrics(
            "pv_local",
            context_s24.to(torch.float64) / Q16,
            context_reference,
        ))
        score_clipped = int(
            ((score_reference <= -16.0) | (score_reference >= 16.0))
            .logical_and(valid_mask)
            .sum()
            .item()
        )
        valid_scores = int(valid_mask.sum().item())
        for row in rows:
            row.update({
                "layer": int(layer_id),
                "trace_call": int(self.attention_calls[layer_id]),
                "trace_domain": "attention",
                "tokens": int(query_count),
                "valid_scores": valid_scores,
                "reference_score_boundary_count": score_clipped,
            })
        self.rows.extend(rows)
        self.attention_calls[layer_id] += 1

    def record_mlp(
        self,
        *,
        layer_id: int,
        hidden_states: torch.Tensor,
        gate_s24: torch.Tensor,
        up_s24: torch.Tensor,
        product_s32: torch.Tensor,
        output_s24: torch.Tensor,
        silu_lut_s24: torch.Tensor,
        gate_weight: torch.Tensor,
        up_weight: torch.Tensor,
        down_weight: torch.Tensor,
    ) -> None:
        if not self.enabled(layer_id, "mlp"):
            return
        # The checkpoint stores BF16 weights.  FP32 accumulation here is the
        # local floating reference for the same real activation, while the
        # approximate tensors are the exact integer values crossing RTL nodes.
        source = hidden_states.detach().to(torch.float32)
        gate_reference = F.linear(source, gate_weight.to(torch.float32))
        up_reference = F.linear(source, up_weight.to(torch.float32))
        gate_real = gate_s24.to(torch.float64) / Q16
        up_real = up_s24.to(torch.float64) / Q16

        gate_i64 = gate_s24.to(torch.int64)
        address = ((gate_i64 + SILU_LIMIT_Q16 + 128) >> 8).clamp(0, 8192)
        lookup = silu_lut_s24[address].to(torch.int64)
        silu_s24 = torch.where(
            gate_i64 <= -SILU_LIMIT_Q16,
            torch.zeros_like(gate_i64),
            torch.where(gate_i64 >= SILU_LIMIT_Q16, gate_i64, lookup),
        )
        silu_real = silu_s24.to(torch.float64) / Q16
        product_real = product_s32.to(torch.float64) / Q16
        output_real = output_s24.to(torch.float64) / Q16

        product_reference = F.silu(gate_reference) * up_reference
        down_local_reference = F.linear(
            product_real.to(torch.float32), down_weight.to(torch.float32)
        )
        down_cumulative_reference = F.linear(
            product_reference, down_weight.to(torch.float32)
        )
        rows = [
            self._metrics("mlp_gate_projection", gate_real, gate_reference),
            self._metrics("mlp_up_projection", up_real, up_reference),
            self._metrics("mlp_silu_lut_local", silu_real, F.silu(gate_real)),
            self._metrics(
                "mlp_swiglu_round_local",
                product_real,
                silu_real * up_real,
            ),
            self._metrics(
                "mlp_swiglu_cumulative",
                product_real,
                product_reference,
            ),
            self._metrics(
                "mlp_down_projection_local",
                output_real,
                down_local_reference,
            ),
            self._metrics(
                "mlp_down_projection_cumulative",
                output_real,
                down_cumulative_reference,
            ),
        ]
        tokens = int(hidden_states.numel() // hidden_states.shape[-1])
        for row in rows:
            row.update({
                "layer": int(layer_id),
                "trace_call": int(self.mlp_calls[layer_id]),
                "trace_domain": "mlp",
                "tokens": tokens,
            })
        self.rows.extend(rows)
        self.mlp_calls[layer_id] += 1

    def collect(self) -> dict[str, Any]:
        return {
            "schema": "scalellm_v5_attention_mlp_node_trace_v2",
            "layers": sorted(self.layers),
            "max_calls_per_layer": self.max_calls_per_layer,
            "attention_calls": self.attention_calls,
            "mlp_calls": self.mlp_calls,
            "rows": self.rows,
        }


class V5Attention(nn.Module):
    def __init__(
        self,
        original: nn.Module,
        q_proj: V5ProductionLinear,
        k_proj: V5ProductionLinear,
        v_proj: V5ProductionLinear,
        o_proj: V5ProductionLinear,
        audit: V5Audit,
        rope_cos_q16: torch.Tensor,
        rope_sin_q16: torch.Tensor,
        output_dtype: torch.dtype | None = None,
        node_trace: V5NodeTrace | None = None,
    ) -> None:
        super().__init__()
        self.q_proj = q_proj
        self.k_proj = k_proj
        self.v_proj = v_proj
        self.o_proj = o_proj
        self.audit = audit
        self.config = original.config
        self.layer_idx = original.layer_idx
        self.num_heads = int(original.num_heads)
        self.num_key_value_heads = int(original.num_key_value_heads)
        self.num_key_value_groups = int(original.num_key_value_groups)
        self.head_dim = int(original.head_dim)
        self.hidden_size = int(original.hidden_size)
        self.output_dtype = output_dtype
        self.node_trace = node_trace
        self.register_buffer(
            "rope_cos_q16", rope_cos_q16.to(torch.int32), persistent=False
        )
        self.register_buffer(
            "rope_sin_q16", rope_sin_q16.to(torch.int32), persistent=False
        )
        self.register_buffer(
            "softmax_lut_u17",
            torch.tensor(
                build_softmax_exp_lut_u17(),
                dtype=torch.int64,
                device=rope_cos_q16.device,
            ),
            persistent=False,
        )

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        position_ids: torch.Tensor | None = None,
        past_key_value: Any = None,
        output_attentions: bool = False,
        use_cache: bool = False,
        cache_position: torch.Tensor | None = None,
        position_embeddings: Any = None,
        **kwargs: Any,
    ) -> tuple[torch.Tensor, torch.Tensor | None, None]:
        del cache_position, position_embeddings, kwargs
        if past_key_value is not None or use_cache:
            raise ValueError("V5 quality twin currently requires use_cache=False")
        batch, tokens, _ = hidden_states.shape
        if tokens > 128:
            raise ValueError(
                f"V5 production Attention supports at most 128 keys, got {tokens}"
            )
        prepared = self.q_proj.prepare_float(hidden_states)
        query_raw = self.q_proj.project_prepared(prepared)
        key_raw = self.k_proj.project_prepared(prepared)
        value_raw = self.v_proj.project_prepared(prepared)

        query_raw = query_raw.reshape(
            batch, tokens, self.num_heads, self.head_dim
        )
        key_raw = key_raw.reshape(
            batch, tokens, self.num_key_value_heads, self.head_dim
        )
        value_raw = value_raw.reshape(
            batch, tokens, self.num_key_value_heads, self.head_dim
        )
        if position_ids is None:
            position_ids = torch.arange(tokens, device=hidden_states.device)[
                None, :
            ].expand(batch, -1)
        if bool((position_ids < 0).any().item()) or bool(
            (position_ids >= 128).any().item()
        ):
            raise ValueError("V5 production RoPE table is limited to positions 0..127")
        cos = self.rope_cos_q16[position_ids]
        sin = self.rope_sin_q16[position_ids]
        query_before_rope = query_raw
        key_before_rope = key_raw
        query_after_rope = _fixed_rope(query_raw, cos, sin, self.audit)
        key_after_rope = _fixed_rope(key_raw, cos, sin, self.audit)
        query_raw = _logical_to_interleaved_head(query_after_rope)
        key_raw = _logical_to_interleaved_head(key_after_rope)
        key_cache = _kv12_quantize(key_raw, self.audit)
        value_cache = _kv12_quantize(value_raw, self.audit)
        scores = _qk_scores_s20(
            query_raw, key_cache, self.num_key_value_groups, self.audit
        )

        if attention_mask is None:
            valid = torch.ones(
                (batch, 1, tokens, tokens),
                dtype=torch.bool,
                device=hidden_states.device,
            ).tril()
        else:
            valid = attention_mask[:, :, :tokens, :tokens] == 0
        valid = valid.expand(batch, self.num_heads, tokens, tokens)
        probability = _softmax_u16(scores, valid, self.softmax_lut_u17)
        context = _pv_s24(
            probability,
            value_cache,
            self.num_key_value_groups,
            self.audit,
        )
        if self.node_trace is not None and self.node_trace.enabled(self.layer_idx):
            self.node_trace.record(
                layer_id=self.layer_idx,
                query_before_rope=query_before_rope,
                key_before_rope=key_before_rope,
                query_after_rope=query_after_rope,
                key_after_rope=key_after_rope,
                cos_q16=cos,
                sin_q16=sin,
                query_interleaved=query_raw,
                key_interleaved=key_raw,
                value_s24=value_raw,
                key_cache=key_cache,
                value_cache=value_cache,
                scores_s20=scores,
                valid_mask=valid,
                probability_u16=probability,
                context_s24=context,
                num_key_value_groups=self.num_key_value_groups,
            )
        context = context.permute(0, 2, 1, 3).reshape(
            batch, tokens, self.hidden_size
        )
        output_raw = self.o_proj.forward_raw_fixed(context.to(torch.int64))
        output = output_raw.to(torch.float32) / Q16
        if self.output_dtype is not None:
            output = output.to(self.output_dtype)
        attention = (
            probability.to(torch.float32) / Q16 if output_attentions else None
        )
        return output, attention, None


def _build_silu_lut(device: torch.device) -> torch.Tensor:
    x = np.arange(-16.0, 16.0 + 1.0 / 256.0, 1.0 / 256.0)
    silu = np.where(
        x >= 0,
        x / (1.0 + np.exp(-x)),
        x * np.exp(x) / (1.0 + np.exp(x)),
    )
    raw = numpy_round_away(silu * Q16).clip(S24_MIN, S24_MAX)
    if raw.size != 8193:
        raise AssertionError("SiLU LUT geometry drifted")
    return torch.from_numpy(raw.astype(np.int32)).to(device)


def _swiglu_s32(
    gate_s24: torch.Tensor,
    up_s24: torch.Tensor,
    table: torch.Tensor,
    audit: V5Audit,
    layer_idx: int | None = None,
) -> torch.Tensor:
    # A full MCQA batch contains tens of millions of MLP elements.  Computing
    # int64 conversion, contract masks, address, lookup, SiLU and product over
    # the entire tensor at once caused reproducible transient-buffer corruption
    # on the evaluation GPU.  Chunking is numerically identical and keeps every
    # temporary alive within a bounded allocation.
    if gate_s24.shape != up_s24.shape:
        raise ValueError("SwiGLU Gate/Up shape mismatch")
    gate_flat = gate_s24.reshape(-1)
    up_flat = up_s24.reshape(-1)
    product_flat = torch.empty(
        gate_flat.numel(), dtype=torch.int32, device=gate_s24.device
    )
    overflow_total = torch.zeros(
        (), dtype=torch.int64, device=gate_s24.device
    )
    low = -(1 << 31)
    high = (1 << 31) - 1
    chunk_elements = 1 << 20
    for start in range(0, gate_flat.numel(), chunk_elements):
        end = min(start + chunk_elements, gate_flat.numel())
        gate_chunk = gate_flat[start:end].to(torch.int64)
        up_chunk = up_flat[start:end].to(torch.int64)
        # Match the signed [23:0] interpretation at the RTL consumer.  A
        # zero-extended packed negative is canonicalized; values outside the
        # 24-bit payload itself remain visible to the contract check.
        gate_chunk = torch.where(
            (gate_chunk > S24_MAX) & (gate_chunk <= (1 << 24) - 1),
            gate_chunk - (1 << 24),
            gate_chunk,
        )
        up_chunk = torch.where(
            (up_chunk > S24_MAX) & (up_chunk <= (1 << 24) - 1),
            up_chunk - (1 << 24),
            up_chunk,
        )
        input_overflow = (
            (gate_chunk < S24_MIN)
            | (gate_chunk > S24_MAX)
            | (up_chunk < S24_MIN)
            | (up_chunk > S24_MAX)
        )
        if bool(input_overflow.any().item()):
            first = int(input_overflow.nonzero()[0, 0].item())
            raise ValueError(
                "SwiGLU received a value outside its S24 input contract: "
                f"layer={layer_idx} chunk=[{start},{end}) "
                f"gate_min={int(gate_chunk.amin().item())} "
                f"gate_max={int(gate_chunk.amax().item())} "
                f"up_min={int(up_chunk.amin().item())} "
                f"up_max={int(up_chunk.amax().item())} "
                f"outside={int(input_overflow.sum().item())}/{input_overflow.numel()} "
                f"first_flat={start + first} "
                f"first_gate={int(gate_chunk[first].item())} "
                f"first_up={int(up_chunk[first].item())}"
            )
        address = (
            (gate_chunk + SILU_LIMIT_Q16 + 128) >> 8
        ).clamp(0, 8192)
        lookup = table[address].to(torch.int64)
        silu = torch.where(
            gate_chunk <= -SILU_LIMIT_Q16,
            torch.zeros_like(gate_chunk),
            torch.where(gate_chunk >= SILU_LIMIT_Q16, gate_chunk, lookup),
        )
        product = _round_shift_away(silu * up_chunk, 16)
        overflow_total.add_(((product < low) | (product > high)).sum())
        product_flat[start:end] = product.to(torch.int32)
    audit.add("swiglu_output_overflow", overflow_total)
    if int(overflow_total.item()):
        raise ValueError("production SwiGLU product overflowed S32")
    return product_flat.reshape(gate_s24.shape)


class V5MLP(nn.Module):
    def __init__(
        self,
        gate_proj: V5ProductionLinear,
        up_proj: V5ProductionLinear,
        down_proj: V5ProductionLinear,
        device: torch.device,
        audit: V5Audit,
        output_dtype: torch.dtype | None = None,
        layer_idx: int | None = None,
        node_trace: V5NodeTrace | None = None,
        reference_gate_weight: torch.Tensor | None = None,
        reference_up_weight: torch.Tensor | None = None,
        reference_down_weight: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.gate_proj = gate_proj
        self.up_proj = up_proj
        self.down_proj = down_proj
        self.audit = audit
        self.output_dtype = output_dtype
        self.layer_idx = layer_idx
        self.node_trace = node_trace
        self.register_buffer(
            "silu_lut_s24", _build_silu_lut(device), persistent=False
        )
        self.register_buffer(
            "reference_gate_weight", reference_gate_weight, persistent=False
        )
        self.register_buffer(
            "reference_up_weight", reference_up_weight, persistent=False
        )
        self.register_buffer(
            "reference_down_weight", reference_down_weight, persistent=False
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        prepared = self.gate_proj.prepare_float(hidden_states)
        gate = self.gate_proj.project_prepared(prepared)
        up = self.up_proj.project_prepared(prepared)
        product = _swiglu_s32(
            gate,
            up,
            self.silu_lut_s24,
            self.audit,
            self.layer_idx,
        )
        down_prepared = self.down_proj.prepare_raw(product)
        output = self.down_proj.project_prepared(down_prepared)
        if (
            self.node_trace is not None
            and self.layer_idx is not None
            and self.node_trace.enabled(self.layer_idx, "mlp")
        ):
            if any(weight is None for weight in (
                self.reference_gate_weight,
                self.reference_up_weight,
                self.reference_down_weight,
            )):
                raise RuntimeError("MLP node trace is missing checkpoint weights")
            self.node_trace.record_mlp(
                layer_id=self.layer_idx,
                hidden_states=hidden_states,
                gate_s24=gate,
                up_s24=up,
                product_s32=product,
                output_s24=output,
                silu_lut_s24=self.silu_lut_s24,
                gate_weight=self.reference_gate_weight,
                up_weight=self.reference_up_weight,
                down_weight=self.reference_down_weight,
            )
        result = output.to(torch.float32) / Q16
        return result if self.output_dtype is None else result.to(self.output_dtype)


class HostFP32RMSNorm(nn.Module):
    """Host-side FP32 residual/RMSNorm boundary used by the V5 contract."""

    def __init__(self, original: nn.Module, device: torch.device) -> None:
        super().__init__()
        self.variance_epsilon = float(original.variance_epsilon)
        self.register_buffer(
            "weight",
            original.weight.detach().to(device=device, dtype=torch.float32),
            persistent=False,
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        value = hidden_states.to(torch.float32)
        variance = value.pow(2).mean(-1, keepdim=True)
        return self.weight * value * torch.rsqrt(variance + self.variance_epsilon)


def _quantized_linear_from_checkpoint(
    *,
    checkpoint: LlamaCheckpoint,
    tensor_name: str,
    op_name: str,
    weight_bits: int,
    input_width: int,
    hadamard_width: int,
    output_width: int = 24,
    device: torch.device,
    audit: V5Audit,
    strict_total_shift: bool,
    software_extended: bool,
    down_shift12_candidate: bool = False,
) -> V5ProductionLinear:
    source = checkpoint.float32(tensor_name)
    quantized, codes, shifts = quantize_folded_rows(source, weight_bits)
    module = V5ProductionLinear(
        module_name=tensor_name,
        op_name=op_name,
        weight_s8=quantized,
        weight_codes_u8=codes,
        weight_shifts_u8=shifts,
        input_width=input_width,
        hadamard_width=hadamard_width,
        output_width=output_width,
        device=device,
        audit=audit,
        strict_total_shift=strict_total_shift,
        software_extended=software_extended,
        down_shift12_candidate=down_shift12_candidate,
    )
    del source, quantized, codes, shifts
    gc.collect()
    return module


def _rope_tables(config: Any, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    raw_config = config.to_dict() if hasattr(config, "to_dict") else dict(config)
    inv_freq = llama3_inv_freq(raw_config)
    positions = np.arange(128, dtype=np.float64)
    angles = positions[:, None] * inv_freq[None, :]
    cos = np.clip(numpy_round_away(np.cos(angles) * Q16), -Q16, Q16)
    sin = np.clip(numpy_round_away(np.sin(angles) * Q16), -Q16, Q16)
    return (
        torch.from_numpy(cos.astype(np.int32)).to(device),
        torch.from_numpy(sin.astype(np.int32)).to(device),
    )


def attach_v5_fullchain(
    model: nn.Module,
    *,
    checkpoint_dir: Path,
    device: torch.device,
    strict_total_shift: bool = True,
    software_extended: bool = False,
    trace_layers: set[int] | None = None,
    trace_max_calls_per_layer: int = 1,
    down_output_width: int = 24,
    down_shift12_candidate: bool = False,
) -> tuple[dict[str, Any], V5Audit]:
    """Replace all 32 Llama Attention/MLP blocks with the V5 numeric twin."""
    if strict_total_shift and software_extended:
        raise ValueError(
            "software_extended cannot be combined with strict_total_shift"
        )
    if len(model.model.layers) != 32:
        raise ValueError("V5 artifact contract requires exactly 32 decoder layers")
    checkpoint = LlamaCheckpoint(checkpoint_dir)
    audit = V5Audit(device)
    node_trace = (
        V5NodeTrace(trace_layers, trace_max_calls_per_layer)
        if trace_layers
        else None
    )
    audit.node_trace = node_trace
    rope_cos, rope_sin = _rope_tables(model.config, device)

    for layer_id, layer in enumerate(model.model.layers):
        attn_prefix = f"model.layers.{layer_id}.self_attn"
        mlp_prefix = f"model.layers.{layer_id}.mlp"
        original_mlp = layer.mlp
        trace_mlp = node_trace is not None and layer_id in node_trace.layers
        reference_gate_weight = (
            original_mlp.gate_proj.weight.detach() if trace_mlp else None
        )
        reference_up_weight = (
            original_mlp.up_proj.weight.detach() if trace_mlp else None
        )
        reference_down_weight = (
            original_mlp.down_proj.weight.detach() if trace_mlp else None
        )
        q_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{attn_prefix}.q_proj.weight",
            op_name="q_proj",
            weight_bits=8,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        k_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{attn_prefix}.k_proj.weight",
            op_name="k_proj",
            weight_bits=8,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        v_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{attn_prefix}.v_proj.weight",
            op_name="v_proj",
            weight_bits=8,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        o_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{attn_prefix}.o_proj.weight",
            op_name="o_proj",
            weight_bits=8,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        attention = V5Attention(
            layer.self_attn,
            q_proj,
            k_proj,
            v_proj,
            o_proj,
            audit,
            rope_cos,
            rope_sin,
            node_trace=node_trace,
        )

        gate_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{mlp_prefix}.gate_proj.weight",
            op_name="gate_proj",
            weight_bits=4,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        up_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{mlp_prefix}.up_proj.weight",
            op_name="up_proj",
            weight_bits=4,
            input_width=24,
            hadamard_width=27,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
        )
        down_proj = _quantized_linear_from_checkpoint(
            checkpoint=checkpoint,
            tensor_name=f"{mlp_prefix}.down_proj.weight",
            op_name="down_proj",
            weight_bits=4,
            input_width=32,
            hadamard_width=35,
            output_width=down_output_width,
            device=device,
            audit=audit,
            strict_total_shift=strict_total_shift,
            software_extended=software_extended,
            down_shift12_candidate=down_shift12_candidate,
        )
        layer.self_attn = attention
        layer.mlp = V5MLP(
            gate_proj,
            up_proj,
            down_proj,
            device,
            audit,
            layer_idx=layer_id,
            node_trace=node_trace,
            reference_gate_weight=reference_gate_weight,
            reference_up_weight=reference_up_weight,
            reference_down_weight=reference_down_weight,
        )
        layer.input_layernorm = HostFP32RMSNorm(layer.input_layernorm, device)
        layer.post_attention_layernorm = HostFP32RMSNorm(
            layer.post_attention_layernorm, device
        )
        gc.collect()
        torch.cuda.empty_cache()
        print(f"[V5 attach] layer {layer_id + 1}/32", flush=True)

    model.model.norm = HostFP32RMSNorm(model.model.norm, device)
    # The LM head is a host-side operation, outside the FPGA graph.  FP32
    # avoids silently recasting the FP32 residual/RMSNorm state to BF16.
    model.lm_head = model.lm_head.to(device=device, dtype=torch.float32)
    return (
        {
            "case": (
                "v5_algorithm_software_reference"
                if software_extended
                else "v5_production_fullchain"
            ),
            "manifest": "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
            "attention_format_id": "0x48384103",
            "mlp_full_format_id": (
                "0x48384605" if down_shift12_candidate else "0x48384603"
            ),
            "layers": 32,
            "max_context": 128,
            "cohort_rows": 16,
            "attention_weight_bits": 8,
            "mlp_weight_bits": 4,
            "activation_bits": 8,
            "kv_bits": 12,
            "host_residual_rmsnorm": "FP32",
            "lm_head": "FP32 host",
            "strict_total_shift": strict_total_shift,
            "total_shift_policy": (
                "software_extended"
                if software_extended
                else ("strict_rtl" if strict_total_shift else "rtl_zero_guard")
            ),
            "software_reference_not_hardware": software_extended,
            "node_trace_layers": sorted(trace_layers or ()),
            "mlp_total_shift_range": [
                12 if down_shift12_candidate else 20,
                44,
            ],
            "mlp_group_guard_compute_width": (
                45 if down_shift12_candidate else 37
            ),
            "mlp_gate_up_accumulator_compute_width": 44,
            "mlp_down_accumulator_compute_width": (
                54 if down_shift12_candidate else 46
            ),
            "mlp_down_output_width": down_output_width,
        },
        audit,
    )


def attach_v5_attention_only(
    model: nn.Module,
    *,
    checkpoint_dir: Path,
    device: torch.device,
    strict_total_shift: bool = True,
    software_extended: bool = False,
    trace_layers: set[int] | None = None,
    trace_max_calls_per_layer: int = 1,
) -> tuple[dict[str, Any], V5Audit]:
    """Replace only Attention with the production integer numeric twin.

    The surrounding RMSNorm, residual, MLP and LM head stay on the checkpoint's
    native BF16 path.  Casting the S24 Wo boundary back to BF16 makes this a
    controlled Attention ablation; ``attach_v5_fullchain`` remains the exact
    host-FP32/full-hardware boundary model.
    """
    if strict_total_shift and software_extended:
        raise ValueError(
            "software_extended cannot be combined with strict_total_shift"
        )
    if len(model.model.layers) != 32:
        raise ValueError("V5 artifact contract requires exactly 32 decoder layers")
    checkpoint = LlamaCheckpoint(checkpoint_dir)
    audit = V5Audit(device)
    node_trace = (
        V5NodeTrace(trace_layers, trace_max_calls_per_layer)
        if trace_layers
        else None
    )
    audit.node_trace = node_trace
    rope_cos, rope_sin = _rope_tables(model.config, device)

    for layer_id, layer in enumerate(model.model.layers):
        prefix = f"model.layers.{layer_id}.self_attn"
        projections: dict[str, V5ProductionLinear] = {}
        for op_name in ("q_proj", "k_proj", "v_proj", "o_proj"):
            projections[op_name] = _quantized_linear_from_checkpoint(
                checkpoint=checkpoint,
                tensor_name=f"{prefix}.{op_name}.weight",
                op_name=op_name,
                weight_bits=8,
                input_width=24,
                hadamard_width=27,
                device=device,
                audit=audit,
                strict_total_shift=strict_total_shift,
                software_extended=software_extended,
            )
        layer.self_attn = V5Attention(
            layer.self_attn,
            projections["q_proj"],
            projections["k_proj"],
            projections["v_proj"],
            projections["o_proj"],
            audit,
            rope_cos,
            rope_sin,
            output_dtype=torch.bfloat16,
            node_trace=node_trace,
        )
        gc.collect()
        torch.cuda.empty_cache()
        print(f"[V5 attention-only attach] layer {layer_id + 1}/32", flush=True)

    return (
        {
            "case": "v5_attention_only_controlled_ablation",
            "manifest": (
                "vivado/manifests/"
                "attention_mlp_production_v5_cohort16_sources.list"
            ),
            "attention_format_id": "0x48384103",
            "layers": 32,
            "max_context": 128,
            "attention_weight_bits": 8,
            "activation_bits": 8,
            "kv_bits": 12,
            "fixed_operators": [
                "QKV projection",
                "RoPE",
                "KV12",
                "QK",
                "Softmax",
                "PV",
                "Wo projection",
            ],
            "floating_operators": [
                "RMSNorm",
                "residual",
                "MLP",
                "LM head",
            ],
            "attention_output_boundary": "S24 Q8.16 then BF16 ablation cast",
            "strict_total_shift": strict_total_shift,
            "software_reference_not_hardware": software_extended,
            "node_trace_layers": sorted(trace_layers or ()),
        },
        audit,
    )


def attach_v5_mlp_only(
    model: nn.Module,
    *,
    checkpoint_dir: Path,
    device: torch.device,
    strict_total_shift: bool = True,
    software_extended: bool = False,
    trace_layers: set[int] | None = None,
    trace_max_calls_per_layer: int = 1,
    down_output_width: int = 24,
    down_shift12_candidate: bool = False,
) -> tuple[dict[str, Any], V5Audit]:
    """Replace only the format-v3 MLP with its integer numeric twin."""
    if strict_total_shift and software_extended:
        raise ValueError(
            "software_extended cannot be combined with strict_total_shift"
        )
    if len(model.model.layers) != 32:
        raise ValueError("V5 artifact contract requires exactly 32 decoder layers")
    checkpoint = LlamaCheckpoint(checkpoint_dir)
    audit = V5Audit(device)
    node_trace = (
        V5NodeTrace(trace_layers, trace_max_calls_per_layer)
        if trace_layers
        else None
    )
    audit.node_trace = node_trace
    for layer_id, layer in enumerate(model.model.layers):
        prefix = f"model.layers.{layer_id}.mlp"
        original_mlp = layer.mlp
        trace_mlp = node_trace is not None and layer_id in node_trace.layers
        reference_gate_weight = (
            original_mlp.gate_proj.weight.detach() if trace_mlp else None
        )
        reference_up_weight = (
            original_mlp.up_proj.weight.detach() if trace_mlp else None
        )
        reference_down_weight = (
            original_mlp.down_proj.weight.detach() if trace_mlp else None
        )
        projections: dict[str, V5ProductionLinear] = {}
        for op_name, input_width, hadamard_width in (
            ("gate_proj", 24, 27),
            ("up_proj", 24, 27),
            ("down_proj", 32, 35),
        ):
            projections[op_name] = _quantized_linear_from_checkpoint(
                checkpoint=checkpoint,
                tensor_name=f"{prefix}.{op_name}.weight",
                op_name=op_name,
                weight_bits=4,
                input_width=input_width,
                hadamard_width=hadamard_width,
                output_width=(
                    down_output_width if op_name == "down_proj" else 24
                ),
                device=device,
                audit=audit,
                strict_total_shift=strict_total_shift,
                software_extended=software_extended,
                down_shift12_candidate=down_shift12_candidate,
            )
        layer.mlp = V5MLP(
            projections["gate_proj"],
            projections["up_proj"],
            projections["down_proj"],
            device,
            audit,
            output_dtype=torch.bfloat16,
            layer_idx=layer_id,
            node_trace=node_trace,
            reference_gate_weight=reference_gate_weight,
            reference_up_weight=reference_up_weight,
            reference_down_weight=reference_down_weight,
        )
        gc.collect()
        torch.cuda.empty_cache()
        print(f"[V5 MLP-only attach] layer {layer_id + 1}/32", flush=True)
    return (
        {
            "case": "v5_mlp_only_controlled_ablation",
            "mlp_full_format_id": (
                "0x48384605"
                if down_shift12_candidate
                else "0x48384603"
            ),
            "layers": 32,
            "max_context": 128,
            "mlp_weight_bits": 4,
            "activation_bits": 8,
            "mlp_total_shift_range": [
                12 if down_shift12_candidate else 20,
                44,
            ],
            "mlp_group_guard_width": (
                45 if down_shift12_candidate else 37
            ),
            "mlp_gate_up_accumulator_width": 44,
            "mlp_down_accumulator_width": (
                54 if down_shift12_candidate else 46
            ),
            "mlp_down_output_width": down_output_width,
            "fixed_operators": [
                "Gate projection",
                "Up projection",
                "SiLU LUT",
                "SwiGLU product",
                "Down projection",
            ],
            "floating_operators": [
                "RMSNorm",
                "residual",
                "Attention",
                "RoPE",
                "Softmax",
                "LM head",
            ],
            "mlp_output_boundary": (
                "S24 Q8.16 then BF16 ablation cast"
                if down_output_width == 24
                else "diagnostic S32 Q16 then BF16 ablation cast"
            ),
            "strict_total_shift": strict_total_shift,
            "software_reference_not_hardware": software_extended,
            "node_trace_layers": sorted(trace_layers or ()),
        },
        audit,
    )
