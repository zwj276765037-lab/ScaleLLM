"""R007 equal-width intermediate nearest-even candidate; frozen production copied below.
Only Linear group alignment and optional PV term alignment change. Final rounding,
guards, accumulator wrapping and saturation remain the copied production rules.
"""
from __future__ import annotations
from contextlib import contextmanager
import torch
import triton
import triton.language as tl
from numerical_reference.model_compat import production_module
_v5=production_module()
GROUP=_v5.GROUP
S24_MIN=_v5.S24_MIN
S24_MAX=_v5.S24_MAX
_round_shift_away=_v5._round_shift_away


def round_shift_even(value, shift):
    """Exact signed floor quotient/remainder RNE; nonpositive shifts are exact."""
    shift=torch.as_tensor(shift,device=value.device,dtype=torch.int64)
    right=shift.clamp_min(0)
    left=(-shift).clamp_min(0)
    quotient=value >> right
    remainder=value-(quotient << right)
    half=torch.ones((),device=value.device,dtype=torch.int64) << (right-1).clamp_min(0)
    increment=(right>0)&((remainder>half)|((remainder==half)&((quotient&1)!=0)))
    return (quotient+increment.to(torch.int64)) << left


@triton.jit
def _rne_vector(xp,sp,yp,N:tl.constexpr,B:tl.constexpr):
    i=tl.program_id(0)*B+tl.arange(0,B)
    x=tl.load(xp+i,i<N,0).to(tl.int64)
    s=tl.load(sp+i,i<N,0).to(tl.int32)
    rshift=tl.maximum(s,0)
    q=x >> rshift
    r=x-(q << rshift)
    h=tl.full((),1,tl.int64) << tl.maximum(rshift-1,0)
    inc=(s>0)&((r>h)|((r==h)&((q&1)!=0)))
    y=(q+inc.to(tl.int64)) << tl.maximum(-s,0)
    tl.store(yp+i,y,i<N)

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
        # Inactive code metadata may carry shift63+63; clamp before shifts.
        active = (act_code[:, None] != 0) & (weight_code[None, :] != 0)
        right = tl.where(active, tl.maximum(delta, 0), 0)
        left = tl.where(active, tl.maximum(-delta, 0), 0)
        quotient = raw >> right
        remainder = raw - (quotient << right)
        half = tl.full((), 1, tl.int64) << tl.maximum(right - 1, 0)
        increment = (right > 0) & ((remainder > half) | ((remainder == half) & ((quotient & 1) != 0)))
        aligned = (quotient + increment.to(tl.int64)) << left
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
            guard = round_shift_even(product, shift_amount.permute(0, 2, 1)[
                :, :, None, :, None
            ])
            accumulator = guard.sum(dim=3)
            rounded = _round_shift_away(accumulator, 8)
            saturated = rounded.clamp(S24_MIN, S24_MAX)
            audit.add("pv_output_saturation", (rounded != saturated).sum())
            output[:, head_start:head_end, :, group, :] = saturated.to(
                torch.int32
            )
    return output.reshape(batch, heads, query_count, 128)

@contextmanager
def candidate_context(v5, state, arm):
    if arm not in ('linear_last1','linear_all32','linear_pv_all32'):
        raise ValueError('undeclared R007 candidate')
    marker='_m005_arithmetic_context_active'
    if getattr(v5,marker,False):raise RuntimeError('nested arithmetic context')
    original_linear=v5.grouped_linear_s24
    original_pv=v5._pv_s24
    def selected_linear(*args,**kwargs):
        if arm!='linear_last1' or state['layer']==31:
            return grouped_linear_s24(*args,**kwargs)
        return original_linear(*args,**kwargs)
    try:
        setattr(v5,marker,True)
        v5.grouped_linear_s24=selected_linear
        if arm=='linear_pv_all32':v5._pv_s24=_pv_s24
        yield
    finally:
        v5.grouped_linear_s24=original_linear
        v5._pv_s24=original_pv
        delattr(v5,marker)
